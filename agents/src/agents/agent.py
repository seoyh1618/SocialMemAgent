import json
import logging
import time
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext
from typing import Optional
from .sub_agents.memory import memory_agent  # [Fix 3] previously dead code — now connected
from .sub_agents.orchestrator import content_orchestrator
from .twitter_tools import advanced_search, get_trends
from .schemas import MemoryState
from .memory_tools import (
    memory_get_core_profile,
    memory_update_user_profile,
    memory_update_brand_voice,
    memory_update_domain_profile,
    memory_add_domain_knowledge,
    memory_get_knowledge,
    memory_add_product,
    memory_get_product,
    memory_update_product,
    memory_archive_campaign,
    memory_search_campaigns,
    memory_get_recent_campaigns,
    memory_update_working_summary,
    memory_record_generated_asset,
    memory_get_assets,
    memory_add_performance_notes,
    memory_collect_performance,
    memory_get_performance_pending,
    memory_mark_performance_asked,
    memory_get_behavior_insights,
    memory_compress_context,
    memory_get_context_status,
    memory_append_recall,
    memory_get_recall_log,
    memory_archive_conversation,
    memory_search_conversations,
    memory_update_audience_segment,
    memory_add_audience_trait,
    memory_get_audience_segments,
    read_skill_md,
    build_memory_context_block,
    _compact_recall_to_summary,
    _embed,
    _qdrant_upsert,
    _qdrant_search,
    _QDRANT_CONVERSATIONS_COLLECTION,
    is_qdrant_healthy,
)

from . import prompt

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  MemGPT Core Memory Injection — before_agent_callback
#
#  MemGPT 원본 설계의 핵심:
#    "Core Memory is ALWAYS in the context window — the agent cannot
#     choose to ignore it."
#
#  구현 방식:
#    ADK의 before_agent_callback을 사용하여 에이전트가 첫 응답을
#    생성하기 전에 session.state의 메모리를 읽고,
#    callback_context.state['_memory_block']에 포맷된 텍스트를 저장.
#    그러면 프롬프트의 {_memory_block} 플레이스홀더가 이를 자동 주입.
#
#  왜 도구 호출 방식보다 우월한가:
#    - 도구 호출(memory_get_core_profile)은 LLM이 "잊을" 수 있음
#    - callback은 Python 레벨에서 강제 실행 — 100% 신뢰성
#    - 토큰 낭비 없이 정확한 위치에 삽입
# ─────────────────────────────────────────────────────────────────────

_MEMORY_STATE_KEY = "memory"


_CTX_TURN_KEY = "_ctx_turns"
from .memory_tools import _TURNS_TO_COMPRESS as _COMPRESS_THRESHOLD_TURNS


def _load_memory_from_callback(callback_context: CallbackContext) -> MemoryState:
    """Load MemoryState from callback context state, returning default on failure."""
    raw = callback_context.state.get(_MEMORY_STATE_KEY)
    if raw is None:
        return MemoryState()
    try:
        if isinstance(raw, dict):
            return MemoryState.model_validate(raw)
        return MemoryState.model_validate_json(raw)
    except Exception:
        logger.warning("Corrupted memory state in callback — resetting to default MemoryState.")
        return MemoryState()


def _append_user_turn_to_recall(callback_context: CallbackContext, memory: MemoryState) -> str:
    """Extract user query text and append it to recall_log. Returns the extracted query."""
    from datetime import datetime, timezone

    user_query = ""
    try:
        user_content = callback_context.user_content
        if user_content and user_content.parts:
            for part in user_content.parts:
                if hasattr(part, "text") and part.text:
                    user_query = part.text[:500]
                    break

        if user_query:
            from .schemas import RecallEntry
            entry = RecallEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                role="user",
                content=user_query,
            )
            memory.recall_log.append(entry)
            _compact_recall_to_summary(memory)
            memory.last_updated = datetime.now(timezone.utc).isoformat()
            callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
    except Exception as e:
        logger.warning("Failed to auto-append user turn to recall_log: %s", e)

    return user_query


def _manage_context_window(callback_context: CallbackContext, memory: MemoryState) -> None:
    """Increment turn counter and auto-compress working_summary at threshold."""
    from datetime import datetime, timezone

    turn = int(callback_context.state.get(_CTX_TURN_KEY, 0)) + 1
    callback_context.state[_CTX_TURN_KEY] = turn

    usage_pct = round(min(turn / _COMPRESS_THRESHOLD_TURNS * 100, 100.0), 1)
    callback_context.state["_ctx_usage_pct"] = usage_pct

    if turn >= _COMPRESS_THRESHOLD_TURNS:
        _compact_recall_to_summary(memory, force=True)
        memory.last_updated = datetime.now(timezone.utc).isoformat()
        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
        callback_context.state[_CTX_TURN_KEY] = 0
        callback_context.state["_ctx_usage_pct"] = 0.0


def _inject_core_memory(callback_context: CallbackContext) -> None:
    """
    [MemGPT: Core Memory Injection + Context Window Management]
    before_agent_callback으로 등록되어 에이전트 실행 직전에 호출됨.
    1. 현재 user 메시지를 recall_log에 Python 레벨에서 강제 append (LLM에 의존하지 않음)
    2. session.state['memory']를 읽어 포맷된 Core Memory 블록 생성
       - 최근 20턴 (_RECALL_WINDOW) recall_log 포함
       - 현재 user_query로 semantic 유사 캠페인 자동 주입 (Archival Hint)
    3. 대화 턴 카운터를 증가시키고 80% 임계치 도달 시 working_summary 자동 압축
    4. 현재 컨텍스트 사용률(%)을 state['_ctx_usage_pct']에 저장 → UI가 읽어감
    """
    _t0 = time.time()
    _agent_name = getattr(callback_context, 'agent_name', 'unknown')
    logger.info("[CORE_INJECT] 🔵 Starting core memory injection | agent=%s", _agent_name)

    memory = _load_memory_from_callback(callback_context)

    # ── [MemGPT Fix] Recall Memory: Python-level user turn auto-append ──────
    # MemGPT 원본: 시스템이 매 user turn을 강제로 message store에 기록
    # LLM이 memory_append_recall을 잊어버려도 대화 히스토리가 보존됨
    user_query = _append_user_turn_to_recall(callback_context, memory)
    if user_query:
        logger.info("[CORE_INJECT] 📝 User query: \"%s\"", user_query[:100])

    # Log 4-block status
    _h = memory.human_block
    _p = memory.persona_block
    _d = memory.domain_block
    _a = memory.audience_block
    logger.info(
        "[CORE_INJECT] 📝 4-Block status: human=%s, persona=%s, domain=%s, audience=%d segments",
        bool(_h.display_name), bool(_p.tone), bool(_d.industry), len(_a.segments),
    )

    # ── Detect user-attached image and store reference in state ─────────
    try:
        user_content = callback_context.user_content
        if user_content and user_content.parts:
            import base64 as _b64
            import re as _re
            for part in user_content.parts:
                # Priority 1: Inline image data (chat attachment)
                if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                    raw = part.inline_data.data
                    if isinstance(raw, bytes):
                        b64_str = _b64.b64encode(raw).decode('utf-8')
                    else:
                        b64_str = str(raw)
                    callback_context.state["_user_attached_image"] = {
                        "data": b64_str,
                        "mimeType": part.inline_data.mime_type or "image/jpeg",
                    }
                    logger.info("User attached image (inline) stored in state.")
                    break

                # Priority 2: Asset reference URL in text message [참조 에셋: ... — URL: ...]
                if hasattr(part, 'text') and part.text:
                    url_match = _re.search(r'URL:\s*(https?://\S+|data:\S+)', part.text)
                    if url_match:
                        asset_url = url_match.group(1).rstrip(']').rstrip()
                        callback_context.state["_referenced_asset_url"] = asset_url
                        logger.info("Asset reference URL extracted from message: %s", asset_url[:80])
    except Exception as e:
        logger.debug("Image extraction from user content skipped: %s", e)

    # ── [Hyper-Personalization] 과거 유사 대화 자동 검색 + 프롬프트 주입 ──
    # 사용자 메시지로 Qdrant 검색 → 유사 과거 대화를 컨텍스트에 자동 삽입
    _past_conv_block = ""
    if user_query and len(user_query) > 5:
        try:
            q_vec = _embed(user_query)
            if q_vec:
                hits = _qdrant_search(_QDRANT_CONVERSATIONS_COLLECTION, q_vec, top_k=5)
                relevant = [(cid, score, payload) for cid, score, payload in hits
                            if score > 0.45 and payload.get("content", "") != user_query[:500]]
                logger.info(
                    "[CORE_INJECT] 🔍 Qdrant past conversation search: found %d relevant hits (threshold=0.45)",
                    len(relevant),
                )
                if relevant:
                    # [MemGPT Usage Frequency] Increment access_count for retrieved conversations
                    conv_map = {r.conversation_id: r for r in memory.conversation_archive}
                    for cid, score, payload in relevant[:3]:
                        if cid in conv_map:
                            conv_map[cid].access_count = getattr(conv_map[cid], 'access_count', 0) + 1

                    lines = ["▶ RELEVANT PAST CONVERSATIONS (auto-retrieved):"]
                    for cid, score, payload in relevant[:3]:
                        role = payload.get("role", "?")
                        content = payload.get("content", "")[:200]
                        ts = payload.get("timestamp", "")[:10]
                        ac = conv_map[cid].access_count if cid in conv_map else 0
                        lines.append(f"  [{ts}] {role}: {content} (relevance: {score:.2f}, refs: {ac})")
                    lines.append("  ⚡ Use these past interactions to personalize your response.")
                    _past_conv_block = "\n".join(lines)
                    logger.info("[CORE_INJECT] 📝 Injected %d past conversations into context (with access_count)", len(relevant))
        except Exception as e:
            logger.debug("Past conversation retrieval skipped: %s", e)

    # ── Debug: Log recall_log contents for context verification ──
    import datetime as _dt_debug
    from pathlib import Path as _Path_debug
    _debug_log_path = str(_Path_debug(__file__).parent / ".." / ".." / "context_debug.log")
    try:
        with open(_debug_log_path, "a", encoding="utf-8") as _df:
            _df.write(f"\n{'='*60}\n")
            _df.write(f"[{_dt_debug.datetime.now().isoformat()}] INJECT for agent={_agent_name}\n")
            _df.write(f"user_query: {user_query[:100] if user_query else 'None'}\n")
            _df.write(f"recall_log entries: {len(memory.recall_log)}\n")
            for i, entry in enumerate(memory.recall_log[-5:]):
                _df.write(f"  recall[{i}] ({entry.role}): {entry.user_query[:80] if entry.user_query else entry.agent_response[:80] if entry.agent_response else '?'}\n")
            _df.write(f"working_summary: {(memory.working_summary or '')[:100]}\n")
    except Exception:
        pass

    # Core Memory 블록을 state에 기록 — 프롬프트에서 읽어감
    # user_query 전달 → semantic archival hint가 자동 포함됨
    memory_block = build_memory_context_block(memory, user_query=user_query)

    # ── Qdrant health note injection ─────────────────────────────────
    if not is_qdrant_healthy():
        footer = "════════════════════════════════════════"
        qdrant_note = (
            "\n\u26a0\ufe0f QDRANT VECTOR SEARCH OFFLINE \u2014 "
            "Semantic campaign/conversation search is degraded. "
            "Keyword fallback is active. Results may be less relevant."
        )
        if footer in memory_block:
            idx = memory_block.rfind(footer)
            memory_block = memory_block[:idx] + qdrant_note + "\n" + memory_block[idx:]
        else:
            memory_block += qdrant_note

    # 과거 유사 대화 블록 삽입
    if _past_conv_block:
        footer = "════════════════════════════════════════"
        if footer in memory_block:
            idx = memory_block.rfind(footer)
            memory_block = memory_block[:idx] + _past_conv_block + "\n\n" + memory_block[idx:]
        else:
            memory_block += "\n" + _past_conv_block

    # ── GAP-1 fix: Domain Signal Alert injection ───────────────────────
    # 이전 턴의 NLU에서 감지된 도메인 신호가 있으면 에이전트에게 알림
    # 에이전트가 문맥을 판단하여 memory_update_domain_profile 호출 여부 결정
    pending_signals = callback_context.state.get("_pending_domain_signals", None)
    if pending_signals is not None:
        callback_context.state["_pending_domain_signals"] = None
    if pending_signals:
        _SIGNAL_FIELD_HINT = {
            "location_mentioned": "business_location",
            "competitor_mentioned": "competitors",
            "usp_mentioned": "usp",
            "pricing_mentioned": "price_range",
            "target_audience_mentioned": "default_age_range or audience segments",
            "brand_mentioned": "display_name or industry",
        }
        hint_lines = []
        for sig in pending_signals:
            field = _SIGNAL_FIELD_HINT.get(sig, "domain_extra")
            hint_lines.append(f"  - {sig} → consider updating `{field}`")
        alert_block = (
            "\n▶ DOMAIN SIGNAL ALERT (auto-detected from previous turn)\n"
            + "\n".join(hint_lines)
            + "\n  ⚡ ACTION: Review the user's message and call `memory_update_domain_profile` "
            "if confirmed information is present. Do NOT update on vague or hypothetical mentions."
        )
        # Insert before the footer line
        footer = "════════════════════════════════════════"
        if footer in memory_block:
            idx = memory_block.rfind(footer)
            memory_block = memory_block[:idx] + alert_block + "\n" + memory_block[idx:]
        else:
            memory_block += alert_block

    # ── [Structural Fix] Inject conversation context for agent transitions ──
    conv_ctx = callback_context.state.get("_conversation_context", "")
    if conv_ctx:
        ctx_block = (
            "\n▶ RECENT CONVERSATION CONTEXT (for continuity across agent transitions)\n"
            + conv_ctx
            + "\n  ⚡ Use this context to maintain conversation flow and apply previous feedback."
        )
        footer = "════════════════════════════════════════"
        if footer in memory_block:
            idx = memory_block.rfind(footer)
            memory_block = memory_block[:idx] + ctx_block + "\n" + memory_block[idx:]
        else:
            memory_block += ctx_block

    # ── [Structural Fix] Auto-performance collection notification ──
    auto_perf = callback_context.state.get("_auto_performance_collected")
    if auto_perf:
        callback_context.state["_auto_performance_collected"] = None
        perf_block = (
            f"\n▶ PERFORMANCE AUTO-COLLECTED (previous turn)\n"
            f"  Campaign: {auto_perf.get('campaign_id', '?')}\n"
            f"  Engagement: {auto_perf.get('engagement', '?')}\n"
            f"  What worked: {auto_perf.get('worked', [])}\n"
            f"  What failed: {auto_perf.get('failed', [])}\n"
            f"  ⚡ Behavior Graph has been updated. Apply these insights to future content."
        )
        footer = "════════════════════════════════════════"
        if footer in memory_block:
            idx = memory_block.rfind(footer)
            memory_block = memory_block[:idx] + perf_block + "\n" + memory_block[idx:]
        else:
            memory_block += perf_block

    callback_context.state["_memory_block"] = memory_block
    callback_context.state["_last_tool"] = "🧠 메모리 블록 로드 완료"

    # ── [Fix] _channel_brief 기본값 설정 ─────────────────────────────
    # Strategist 프롬프트가 {{_channel_brief}}를 참조하므로 항상 값이 있어야 함.
    # Orchestrator가 tool 호출 후 더 구체적인 brief로 덮어쓸 수 있음.
    brief_parts = [memory_block]

    # 에셋/이미지 참조 정보를 brief에 포함 → 모든 채널이 동일 제품 이미지 사용
    referenced_url = callback_context.state.get("_referenced_asset_url")
    user_image = callback_context.state.get("_user_attached_image")
    if referenced_url:
        brief_parts.append(
            f"\n▶ PRODUCT IMAGE REFERENCE (MUST use for all channels):\n"
            f"  URL: {referenced_url}\n"
            f"  ⚡ Call analyze_user_image with this URL BEFORE generating any image.\n"
            f"  ⚡ All channel images must maintain consistent product appearance, colors, and branding."
        )
    elif user_image:
        brief_parts.append(
            "\n▶ USER ATTACHED PRODUCT IMAGE (MUST use for all channels):\n"
            "  Image attached inline (available via state '_user_attached_image').\n"
            "  ⚡ Call analyze_user_image BEFORE generating any image.\n"
            "  ⚡ All channel images must maintain consistent product appearance, colors, and branding."
        )

    # NLU 시그널을 b3rief에 포함 → strategist가 감정/도메인 신호 활용
    pending_signals = callback_context.state.get("_pending_domain_signals")
    if pending_signals:
        brief_parts.append(
            f"\n▶ DETECTED USER SIGNALS: {', '.join(pending_signals)}\n"
            f"  ⚡ Adapt content tone and strategy based on these signals."
        )

    _brief_text = "\n".join(brief_parts)
    callback_context.state["_channel_brief"] = _brief_text
    logger.info(
        "[CORE_INJECT] 📝 _channel_brief size: %d chars | asset_ref=%s, nlu_signals=%s, qdrant=%s",
        len(_brief_text),
        "yes" if referenced_url or user_image else "no",
        "yes" if pending_signals else "no",
        "ok" if is_qdrant_healthy() else "degraded",
    )

    # ── Context Window Management ──────────────────────────────────────
    _manage_context_window(callback_context, memory)

    logger.info(
        "[CORE_INJECT] 🟢 Core memory injection complete | memory_block=%d chars, total_time=%dms",
        len(callback_context.state.get("_memory_block", "")),
        int((time.time() - _t0) * 1000),
    )


# ─────────────────────────────────────────────────────────────────────
#  Heartbeat — after_tool_callback
#
#  도구 실행 완료 후 즉시 state에 기록:
#    _last_tool       : 방금 완료된 도구 이름
#    _tool_result_status: "success" | "error"
#
#  ADK SSE non-partial 이벤트의 state_delta로 프론트엔드에 전달됨.
#  프론트엔드는 이를 읽어 "현재 실행 중인 도구" 인디케이터를 업데이트.
# ─────────────────────────────────────────────────────────────────────

_TOOL_DISPLAY_NAMES: dict[str, str] = {
    # ── 검색/트렌드 도구 ──
    "advanced_search": "Twitter 검색 중",
    "get_trends": "트렌드 조회 중",
    "get_user_posts": "유저 포스트 조회 중",
    "google_search": "Google 검색 중",
    "get_youtube_trends": "YouTube 트렌드 조회 중",
    "get_tiktok_trends": "TikTok 트렌드 조회 중",
    "get_facebook_trends": "Facebook 트렌드 조회 중",
    "get_linkedin_trends": "LinkedIn 트렌드 조회 중",
    "get_pinterest_trends": "Pinterest 트렌드 조회 중",
    "get_kakao_trends": "카카오 트렌드 조회 중",
    "get_threads_trends": "Threads 트렌드 조회 중",
    # ── 미디어 생성 도구 ──
    "generate_image": "이미지 생성 중",
    "generate_video": "동영상 생성 중 (최대 3분)",
    "generate_audio": "오디오 생성 중",
    "assemble_video_with_audio": "동영상 합성 중",
    "analyze_user_image": "첨부 이미지 분석 중",
    # ── 메모리: 프로필/브랜드 ──
    "memory_get_core_profile": "브랜드 프로필 조회 중",
    "memory_update_user_profile": "사용자 프로필 업데이트 중",
    "memory_update_brand_voice": "브랜드 보이스 업데이트 중",
    "memory_update_domain_profile": "도메인 프로파일 업데이트 중",
    "memory_add_domain_knowledge": "도메인 지식 저장 중",
    "memory_update_audience_segment": "오디언스 세그먼트 업데이트 중",
    "memory_add_audience_trait": "오디언스 특성 추가 중",
    "memory_get_audience_segments": "오디언스 세그먼트 조회 중",
    # ── 메모리: 캠페인/에셋 ──
    "memory_record_generated_asset": "에셋 저장 중",
    "memory_get_assets": "에셋 목록 조회 중",
    "memory_archive_campaign": "캠페인 저장 중",
    "memory_search_campaigns": "캠페인 검색 중",
    "memory_get_recent_campaigns": "최근 캠페인 조회 중",
    # ── 메모리: 대화/컨텍스트 ──
    "memory_archive_conversation": "대화 기록 저장 중",
    "memory_search_conversations": "대화 기록 검색 중",
    "memory_update_working_summary": "대화 요약 업데이트 중",
    "memory_append_recall": "대화 기록 추가 중",
    "memory_get_recall_log": "대화 기록 조회 중",
    "memory_compress_context": "컨텍스트 압축 중",
    "memory_get_context_status": "컨텍스트 상태 확인 중",
    "memory_tick_turn": "턴 카운터 업데이트 중",
    # ── 메모리: 성과/행동 분석 ──
    "memory_collect_performance": "성과 데이터 기록 중",
    "memory_get_performance_pending": "성과 수집 목록 확인 중",
    "memory_mark_performance_asked": "성과 질문 완료 처리 중",
    "memory_add_performance_notes": "성과 메모 추가 중",
    "memory_get_behavior_insights": "행동 인사이트 분석 중",
    # ── 채널 Strategist AgentTool ──
    "instagram_strategist": "📱 Instagram 콘텐츠 생성 중",
    "facebook_strategist": "📘 Facebook 콘텐츠 생성 중",
    "x_strategist": "🐦 X(Twitter) 콘텐츠 생성 중",
    "tiktok_strategist": "🎵 TikTok 콘텐츠 생성 중",
    "youtube_strategist": "🎬 YouTube 콘텐츠 생성 중",
    "linkedin_strategist": "💼 LinkedIn 콘텐츠 생성 중",
    "pinterest_strategist": "📌 Pinterest 콘텐츠 생성 중",
    "threads_strategist": "🧵 Threads 콘텐츠 생성 중",
    "kakao_strategist": "💬 카카오 콘텐츠 생성 중",
    # ── Orchestrator 내부 ──
    "content_orchestrator": "🎯 콘텐츠 전략 수립 중",
    "idea_generation_agent": "💡 아이디어 생성 중",
}

_HEARTBEAT_MEMORY_SEARCH_TOOLS = {"memory_search_campaigns", "memory_search_conversations"}


def _build_rich_step_detail(tool_name: str, display: str, args: dict, tool_response) -> str:
    """도구별 풍부한 사고 과정 설명을 생성합니다."""
    lines = [display]

    try:
        resp = tool_response if isinstance(tool_response, dict) else {}
        resp_str = tool_response if isinstance(tool_response, str) else ""

        # ── 메모리: 프로필 조회 ──
        if tool_name == "memory_get_core_profile":
            name = resp.get("display_name", "")
            industry = resp.get("industry", "")
            tone = resp.get("tone", "")
            platforms = resp.get("target_platforms", [])
            if name:
                lines.append(f"  브랜드: {name}")
            if industry:
                lines.append(f"  업종: {industry}")
            if tone:
                lines.append(f"  브랜드 톤: {tone}")
            if platforms:
                lines.append(f"  활성 채널: {', '.join(platforms)}")
            domain_type = resp.get("domain_type", "")
            usp = resp.get("usp", "")
            if domain_type:
                lines.append(f"  도메인: {domain_type}")
            if usp:
                lines.append(f"  USP: {usp[:80]}")
            if len(lines) == 1:
                lines.append("  프로필 데이터가 아직 없습니다. 대화를 통해 수집합니다.")

        # ── 메모리: 캠페인 검색 ──
        elif tool_name == "memory_search_campaigns":
            query = args.get("query", "")
            results = resp.get("results", [])
            if query:
                lines.append(f"  검색 키워드: \"{query}\"")
            if isinstance(results, list):
                lines.append(f"  검색 결과: {len(results)}건")
                for i, r in enumerate(results[:3]):
                    if isinstance(r, dict):
                        goal = r.get("goal", "")
                        perf = r.get("performance", {})
                        worked = perf.get("what_worked", []) if isinstance(perf, dict) else []
                        failed = perf.get("what_failed", []) if isinstance(perf, dict) else []
                        line = f"    [{i+1}] {goal[:50]}"
                        if worked:
                            line += f" | 효과적: {', '.join(str(w)[:30] for w in worked[:2])}"
                        if failed:
                            line += f" | 개선필요: {', '.join(str(f)[:30] for f in failed[:2])}"
                        lines.append(line)
                if not results:
                    lines.append("  이전 유사 캠페인이 없습니다. 새로운 전략으로 접근합니다.")

        # ── 메모리: 행동 인사이트 ──
        elif tool_name == "memory_get_behavior_insights":
            bp = resp.get("overall_best_platform", "")
            worked = resp.get("worked_freq", [])
            failed = resp.get("failed_freq", [])
            if bp:
                lines.append(f"  최고 성과 플랫폼: {bp}")
            if worked:
                lines.append(f"  효과적 요소: {', '.join(str(w) for w in worked[:3])}")
            if failed:
                lines.append(f"  개선 필요 요소: {', '.join(str(f) for f in failed[:3])}")
            if not bp and not worked:
                lines.append("  성과 데이터가 아직 없습니다. 첫 캠페인 이후 축적됩니다.")
            else:
                lines.append("  → 이 인사이트를 반영하여 콘텐츠를 최적화합니다.")

        # ── 메모리: 에셋 조회 ──
        elif tool_name == "memory_get_assets":
            assets = resp.get("assets", [])
            if isinstance(assets, list) and assets:
                user_uploaded = [a for a in assets if isinstance(a, dict) and a.get("is_user_uploaded")]
                generated = [a for a in assets if isinstance(a, dict) and not a.get("is_user_uploaded")]
                lines.append(f"  총 {len(assets)}개 에셋 (사용자 업로드: {len(user_uploaded)}, 생성: {len(generated)})")
                if user_uploaded:
                    lines.append("  → 사용자 업로드 에셋을 우선 참조합니다.")
            else:
                lines.append("  등록된 에셋이 없습니다.")

        # ── 채널 Strategist ──
        elif tool_name.endswith("_strategist"):
            channel = tool_name.replace("_strategist", "").replace("_", " ").title()
            goal = args.get("goal", args.get("request", ""))
            if goal:
                lines.append(f"  요청: {str(goal)[:80]}")
            if resp_str:
                # AgentTool은 문자열로 결과 반환
                preview = resp_str[:200].replace("\n", " ").strip()
                lines.append(f"  결과: {preview}")
                if len(resp_str) > 200:
                    lines[-1] += "..."
            lines.append(f"  → {channel} 채널 특성에 맞춰 콘텐츠 생성 완료")

        # ── 아이디어 생성 ──
        elif tool_name == "idea_generation_agent":
            goal = args.get("goal", args.get("request", ""))
            if goal:
                lines.append(f"  주제: {str(goal)[:80]}")
            if resp_str:
                preview = resp_str[:150].replace("\n", " ").strip()
                lines.append(f"  생성된 아이디어: {preview}...")
            lines.append("  → 텍스트/이미지 프롬프트 생성 완료")

        # ── 이미지 생성 ──
        elif tool_name in ("generate_image", "image_generation_agent"):
            prompt = args.get("img_prompt", args.get("prompt", args.get("request", "")))
            channel = args.get("channel", "")
            if channel:
                lines.append(f"  채널: {channel}")
            if prompt:
                lines.append(f"  프롬프트: {str(prompt)[:100]}...")
            if resp_str and "http" in resp_str:
                lines.append("  → 이미지 생성 및 업로드 완료")
            elif isinstance(resp, dict) and resp.get("url"):
                lines.append("  → 이미지 생성 및 업로드 완료")

        # ── 캠페인 저장 ──
        elif tool_name == "memory_archive_campaign":
            goal = args.get("goal", "")
            platforms = args.get("platforms_used", [])
            cid = resp.get("campaign_id", "")
            if goal:
                lines.append(f"  캠페인 목표: {str(goal)[:60]}")
            if platforms:
                lines.append(f"  대상 플랫폼: {', '.join(platforms)}")
            if cid:
                lines.append(f"  캠페인 ID: {cid}")
            lines.append("  → 캠페인이 Archival Memory에 저장되었습니다.")

        # ── 에셋 저장 ──
        elif tool_name == "memory_record_generated_asset":
            atype = args.get("asset_type", "")
            platform = args.get("platform", "")
            if atype:
                lines.append(f"  에셋 유형: {atype}")
            if platform:
                lines.append(f"  플랫폼: {platform}")
            lines.append("  → 에셋이 Asset Archive에 저장되었습니다.")

        # ── 성과 수집 ──
        elif tool_name == "memory_collect_performance":
            cid = args.get("campaign_id", "")
            engagement = args.get("engagement_level", "")
            worked = args.get("what_worked", [])
            failed = args.get("what_failed", [])
            if cid:
                lines.append(f"  캠페인: {cid}")
            if engagement:
                lines.append(f"  참여도: {engagement}")
            if worked:
                lines.append(f"  효과적: {', '.join(str(w) for w in worked)}")
            if failed:
                lines.append(f"  개선필요: {', '.join(str(f) for f in failed)}")
            lines.append("  → Behavior Graph 자동 갱신 완료")

        # ── 대화 검색 ──
        elif tool_name == "memory_search_conversations":
            query = args.get("query", "")
            results = resp.get("results", [])
            if query:
                lines.append(f"  검색 키워드: \"{query}\"")
            if isinstance(results, list):
                lines.append(f"  관련 대화: {len(results)}건")
                for i, r in enumerate(results[:3]):
                    if isinstance(r, dict):
                        content = r.get("content", "")[:60]
                        role = r.get("role", "")
                        lines.append(f"    [{i+1}] ({role}) {content}")
                if results:
                    lines.append("  → 이전 대화 맥락을 참조하여 콘텐츠에 반영합니다.")
                else:
                    lines.append("  관련 대화 기록이 없습니다.")

        # ── 최근 캠페인 조회 ──
        elif tool_name == "memory_get_recent_campaigns":
            campaigns = resp.get("campaigns", resp.get("results", []))
            if isinstance(campaigns, list):
                lines.append(f"  최근 캠페인: {len(campaigns)}건")
                for i, c in enumerate(campaigns[:3]):
                    if isinstance(c, dict):
                        goal = c.get("goal", "")[:40]
                        plats = c.get("platforms_used", [])
                        lines.append(f"    [{i+1}] {goal} ({', '.join(plats) if plats else ''})")
            else:
                lines.append("  캠페인 기록이 없습니다.")

        # ── Recall 로그 조회 ──
        elif tool_name == "memory_get_recall_log":
            entries = resp.get("recall_log", resp.get("entries", []))
            summary = resp.get("working_summary", "")
            if isinstance(entries, list):
                lines.append(f"  최근 대화: {len(entries)}턴")
                for e in entries[-3:]:
                    if isinstance(e, dict):
                        role = e.get("role", "")
                        content = str(e.get("user_query", e.get("content", "")))[:50]
                        lines.append(f"    ({role}) {content}")
            if summary:
                lines.append(f"  대화 요약: {summary[:80]}...")
            lines.append("  → 현재 대화 맥락을 확인했습니다.")

        # ── 도메인 프로필 업데이트 ──
        elif tool_name == "memory_update_domain_profile":
            updated_fields = [k for k, v in args.items() if v and k != "tool_context"]
            if updated_fields:
                lines.append(f"  업데이트 필드: {', '.join(updated_fields)}")
                for f in updated_fields[:5]:
                    val = str(args[f])[:60]
                    lines.append(f"    {f}: {val}")
            lines.append("  → Domain Profile이 갱신되었습니다.")

        # ── 사용자 프로필 업데이트 ──
        elif tool_name == "memory_update_user_profile":
            updated_fields = [k for k, v in args.items() if v and k != "tool_context"]
            if updated_fields:
                lines.append(f"  업데이트 필드: {', '.join(updated_fields)}")
                for f in updated_fields[:5]:
                    val = str(args[f])[:60]
                    lines.append(f"    {f}: {val}")
            lines.append("  → Human Block이 갱신되었습니다.")

        # ── 브랜드 보이스 업데이트 ──
        elif tool_name == "memory_update_brand_voice":
            updated_fields = [k for k, v in args.items() if v and k != "tool_context"]
            if updated_fields:
                for f in updated_fields[:5]:
                    val = str(args[f])[:60]
                    lines.append(f"  {f}: {val}")
            lines.append("  → Persona Block(브랜드 보이스)이 갱신되었습니다.")

        # ── 도메인 지식 추가 ──
        elif tool_name == "memory_add_domain_knowledge":
            key = args.get("key", "")
            value = args.get("value", "")
            if key:
                lines.append(f"  카테고리: {key}")
            if value:
                lines.append(f"  내용: {str(value)[:80]}")
            lines.append("  → 도메인 지식이 학습되었습니다.")

        # ── 첨부 이미지 분석 ──
        elif tool_name == "analyze_user_image":
            image_url = args.get("image_url", "")
            if image_url:
                lines.append(f"  이미지: {image_url[:60]}...")
            if resp and isinstance(resp, dict):
                analysis = resp.get("analysis", resp.get("description", ""))
                if analysis:
                    lines.append(f"  분석 결과: {str(analysis)[:120]}")
            lines.append("  → 사용자 이미지를 분석하여 콘텐츠에 반영합니다.")

        # ── 트렌드 조회 ──
        elif tool_name in ("get_trends", "advanced_search", "get_youtube_trends",
                           "get_tiktok_trends", "get_facebook_trends",
                           "get_linkedin_trends", "get_pinterest_trends",
                           "get_kakao_trends", "get_threads_trends"):
            query = args.get("query", args.get("keyword", ""))
            if query:
                lines.append(f"  검색어: \"{query}\"")
            if isinstance(resp, dict):
                trends = resp.get("trends", resp.get("results", []))
                if isinstance(trends, list) and trends:
                    lines.append(f"  트렌드: {len(trends)}건")
                    for t in trends[:3]:
                        lines.append(f"    • {str(t)[:60]}")
                    lines.append("  → 현재 트렌드를 반영하여 콘텐츠를 최적화합니다.")
                else:
                    lines.append("  관련 트렌드가 없습니다. 브랜드 고유 전략으로 접근합니다.")

        # ── 컨텍스트 압축 ──
        elif tool_name == "memory_compress_context":
            lines.append("  → 컨텍스트 윈도우를 최적화하여 메모리를 효율적으로 관리합니다.")

        # ── Working Summary 업데이트 ──
        elif tool_name == "memory_update_working_summary":
            summary = args.get("summary", "")
            if summary:
                lines.append(f"  요약: {str(summary)[:100]}...")
            lines.append("  → 대화 요약이 갱신되었습니다.")

        # ── 오디언스 관련 ──
        elif tool_name == "memory_update_audience_segment":
            segment = args.get("segment_name", args.get("name", ""))
            if segment:
                lines.append(f"  세그먼트: {segment}")
            lines.append("  → 타겟 오디언스 정보가 업데이트되었습니다.")

        elif tool_name == "memory_get_audience_segments":
            segments = resp.get("segments", [])
            if isinstance(segments, list):
                lines.append(f"  등록된 세그먼트: {len(segments)}개")
                for s in segments[:3]:
                    if isinstance(s, dict):
                        lines.append(f"    • {s.get('name', s.get('segment_name', ''))}")

        # ── 동영상/오디오 생성 ──
        elif tool_name in ("generate_video", "video_generation_agent"):
            lines.append("  → 동영상 콘텐츠를 생성 중입니다.")
        elif tool_name in ("generate_audio", "audio_generation_agent"):
            lines.append("  → 오디오/나레이션을 생성 중입니다.")
        elif tool_name == "assemble_video_with_audio":
            lines.append("  → 동영상과 오디오를 합성 중입니다.")

        # ── 기타 도구: 간단한 결과 요약 ──
        else:
            if resp and isinstance(resp, dict):
                status_msg = resp.get("status", resp.get("message", ""))
                if status_msg:
                    lines.append(f"  결과: {str(status_msg)[:100]}")
            elif resp_str and len(resp_str) > 5:
                lines.append(f"  결과: {resp_str[:100]}")

    except Exception as e:
        logger.debug(f"[_build_rich_step_detail] error: {e}")

    return "\n".join(lines)


def _tool_heartbeat(
    tool: BaseTool,
    args: dict,
    tool_context: ToolContext,
    tool_response: dict,
) -> Optional[dict]:
    """
    after_tool_callback: 도구 실행 완료 후 heartbeat 상태를 state에 기록.
    프론트엔드가 SSE state_delta를 통해 읽어 실시간 진행 표시.
    """
    tool_name = tool.name if hasattr(tool, "name") else str(tool)
    display = _TOOL_DISPLAY_NAMES.get(tool_name, f"{tool_name} 실행 중")

    # Detect error from common response patterns
    status = "success"
    if isinstance(tool_response, dict) and tool_response.get("status") == "failed":
        status = "error"
        display = f"[오류] {display}"

    tool_context.state["_last_tool"] = display
    tool_context.state["_tool_result_status"] = status

    # Build detailed reasoning step for frontend display
    _args_summary = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:3]) if args else "none"
    logger.info("[TOOL] ⚡ %s | status=%s | args_summary=%s", display, status, _args_summary)

    # Build rich reasoning step detail for frontend display
    step_detail = _build_rich_step_detail(tool_name, display, args, tool_response)
    tool_context.state["_last_tool_detail"] = step_detail
    # Use unique key per tool call to prevent state_delta batching from losing steps
    import time as _time_mod
    _step_key = f"_step_{int(_time_mod.time()*1000)}_{tool_name[:20]}"
    tool_context.state[_step_key] = step_detail

    # ── File logging for debugging SSE/state_delta issues ──
    import datetime as _dt, os as _os
    _log_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "heartbeat_debug.log")
    try:
        with open(_log_path, "a", encoding="utf-8") as _f:
            _f.write(f"\n{'='*60}\n")
            _f.write(f"[{_dt.datetime.now().isoformat()}] TOOL HEARTBEAT\n")
            _f.write(f"tool_name: {tool_name}\n")
            _f.write(f"display: {display}\n")
            _f.write(f"status: {status}\n")
            _f.write(f"args_keys: {list(args.keys()) if args else 'none'}\n")
            _f.write(f"response_type: {type(tool_response).__name__}\n")
            _resp_preview = str(tool_response)[:300] if tool_response else "None"
            _f.write(f"response_preview: {_resp_preview}\n")
            _f.write(f"step_detail:\n{step_detail}\n")
            _f.write(f"state._last_tool: {tool_context.state.get('_last_tool', 'N/A')}\n")
            _f.write(f"state._last_tool_detail set: YES\n")
    except Exception:
        pass

    # Accumulate reasoning log — each tool completion adds a step
    # Frontend reads this via state_delta to display progressive reasoning
    try:
        existing_log = list(tool_context.state.get("_reasoning_log", []))
    except Exception:
        existing_log = []
    existing_log.append(step_detail)
    # Keep last 20 steps to avoid state bloat
    if len(existing_log) > 20:
        existing_log = existing_log[-20:]
    tool_context.state["_reasoning_log"] = existing_log

    # Heartbeat loop continuation: detect empty memory search results
    if tool_name in _HEARTBEAT_MEMORY_SEARCH_TOOLS:
        try:
            result_str = tool_response if isinstance(tool_response, str) else json.dumps(tool_response)
            result_data = json.loads(result_str)
            results = result_data.get("results", None)
            if results is not None and len(results) == 0:
                query_used = args.get("query", "")
                tool_context.state["_needs_continuation"] = True
                tool_context.state["_continuation_hint"] = (
                    f"Memory search for '{query_used}' returned no results. "
                    "Try broadening the query, using different keywords, or searching the other memory store."
                )
                logger.info("Heartbeat: empty results from %s → _needs_continuation=True", tool_name)
            else:
                tool_context.state["_needs_continuation"] = False
                tool_context.state["_continuation_hint"] = None
        except Exception as e:
            logger.debug("Heartbeat continuation check failed: %s", e)

    return None  # Do not modify response


# ─────────────────────────────────────────────────────────────────────
#  Auto working_summary save — after_agent_callback
#
#  에이전트 턴 완료 후 working_summary가 비어 있으면
#  대화 요약을 자동으로 기록.
#  MemGPT "Recall Memory" 패턴 — 매 턴 자동 유지.
# ─────────────────────────────────────────────────────────────────────

# ── [CC-2] Agent name → output_key mapping for response capture ──────────
# Agents with output_key store their LLM response in session state.
# This map allows _auto_save_working_summary to read the actual response text.
_AGENT_OUTPUT_KEYS: dict[str, str] = {
    "content_orchestrator": "content_orchestrator_output",
}


_nlu_client = None


def _get_nlu_client():
    global _nlu_client
    if _nlu_client is None:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from google.genai import Client
        _nlu_client = Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    return _nlu_client


def _extract_nlu_signals(text: str) -> dict:
    """LLM-based NLU — extracts emotional signals, decisions, and domain signals from user text.

    Uses Gemini to handle complex cases: negation, compound sentiment, context reversal,
    Korean+English mixed input, multi-dimensional signals.
    Falls back to empty signals on any error.
    """
    empty: dict = {"emotions": [], "decisions": [], "domains": []}
    if not text or not text.strip():
        return empty

    prompt = f"""Analyze the following user message and extract NLU signals. The message may be in Korean, English, or mixed.

User message: {text}

Extract the following signals and return ONLY valid JSON (no markdown, no explanation):

{{
  "emotions": [list of detected emotional tones — possible values: "positive", "negative", "neutral", "frustrated", "excited", "confused", "satisfied", "disappointed"],
  "decisions": [list of detected user decisions/intent shifts — possible values: "user_decision_detected", "direction_change", "preference_stated", "rejection_stated"],
  "domains": [list of detected domain signals — possible values: "location_mentioned", "competitor_mentioned", "usp_mentioned", "pricing_mentioned", "target_audience_mentioned", "brand_mentioned"],
  "performance_feedback": {{
    "detected": true/false,
    "sentiment": "positive"/"negative"/"mixed"/"null",
    "metrics": {{"likes": number_or_null, "comments": number_or_null, "impressions": number_or_null}},
    "what_worked": [list of things user said worked well, e.g., "쫀득한 식감 사진"],
    "what_failed": [list of things user said didn't work, e.g., "해시태그"]
  }}
}}

Important rules:
- PERFORMANCE FEEDBACK detection: If user mentions campaign results like "좋아요 300개",
  "반응 좋았어", "해시태그가 약했어", "댓글 많았어", "성과가 좋았어", "별로였어" →
  set performance_feedback.detected = true and extract all relevant info.
- Handle negation carefully: "별로 좋지 않아" means NEGATIVE (not positive), "not bad" means mildly positive
- "별로" alone is negative; "좋지 않아" is negative; combinations reinforce negativity
- Context reversal: "처음엔 좋았는데 지금은 별로야" → negative (current state matters more)
- Compound sentiment: list ALL applicable emotions if multiple are genuinely present
- Only include signals that are clearly present; omit uncertain ones
- Empty arrays are valid if no signals detected"""

    try:
        import concurrent.futures
        client = _get_nlu_client()

        def _call_nlu():
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call_nlu)
            response = future.result(timeout=10)  # 10초 타임아웃

        if response is None or not hasattr(response, 'text') or response.text is None:
            logger.warning("[NLU] Empty response from Gemini")
            return {}
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json
        signals = json.loads(raw.strip())
        # Validate structure
        perf_raw = signals.get("performance_feedback", {})
        result = {
            "emotions": [str(e) for e in signals.get("emotions", [])],
            "decisions": [str(d) for d in signals.get("decisions", [])],
            "domains": [str(d) for d in signals.get("domains", [])],
            "performance_feedback": perf_raw if isinstance(perf_raw, dict) and perf_raw.get("detected") else None,
        }
        return result
    except concurrent.futures.TimeoutError:
        logger.warning("LLM NLU timed out (10s) — returning empty signals.")
        return empty
    except Exception as e:
        logger.warning("LLM NLU failed, returning empty signals: %s", e)
        return empty


def _auto_save_working_summary(callback_context: CallbackContext) -> None:
    """
    after_agent_callback: 에이전트 응답 완료 후 recall_log에 agent 턴을 자동 append.
    MemGPT 원본 패턴: 매 agent turn이 message store에 자동으로 기록됨.
    LLM이 memory_append_recall을 호출하지 않아도 대화 히스토리가 보존됨.

    [CC-2] output_key가 있는 에이전트는 실제 응답 텍스트를 캡처 (C방식).
    output_key가 없으면 sentinel fallback으로 턴 존재만 기록.
    """
    from datetime import datetime, timezone

    _t0_save = time.time()
    if callback_context.state.get(_MEMORY_STATE_KEY) is None:
        return
    memory = _load_memory_from_callback(callback_context)

    # ── [MemGPT Fix] Recall Memory: Python-level agent turn auto-append ─────
    # agent_name을 agent 응답의 식별자로 기록
    try:
        from .schemas import RecallEntry

        agent_name = callback_context.agent_name
        logger.info("[RECALL_SAVE] 🔵 Auto-saving agent turn | agent=%s", agent_name)

        # [CC-2] Approach C: read actual response from session state via output_key
        actual_content = ""
        output_key = _AGENT_OUTPUT_KEYS.get(agent_name)
        if output_key:
            raw_output = callback_context.state.get(output_key)
            if raw_output:
                actual_content = str(raw_output)[:500]

        # If content looks like orchestrator JSON, extract agent_response only
        if actual_content:
            try:
                import json as _json
                _parsed = _json.loads(actual_content) if actual_content.strip().startswith('{') else None
                if _parsed and isinstance(_parsed, dict) and "agent_response" in _parsed:
                    actual_content = _parsed["agent_response"][:500]
            except Exception:
                pass

        content = actual_content if actual_content else f"[{agent_name} responded]"
        logger.info("[RECALL_SAVE] 📝 Agent response: \"%s\"", content[:100])

        # Extract NLU signals — conditional: skip short messages (< 20 chars)
        # Selective Automation: NLU is expensive (1-3s), only run on substantive messages
        user_text = ""
        for _e in reversed(memory.recall_log):
            if getattr(_e, "role", None) == "user":
                user_text = _e.content
                break

        parts = []
        if len(user_text) >= 20:
            nlu = _extract_nlu_signals(user_text)
            if nlu["emotions"]:
                parts.append(f"emotion:{','.join(nlu['emotions'])}")
            if nlu["decisions"]:
                parts.append("decision_detected")
            if nlu["domains"]:
                parts.append(f"domain:{','.join(nlu['domains'])}")
                callback_context.state["_pending_domain_signals"] = nlu["domains"]

            # ── [Structural Fix] Auto-collect performance feedback ──
            # If NLU detects performance feedback, automatically call memory_collect_performance
            # This does NOT rely on LLM tool selection — it's guaranteed at code level.
            perf_fb = nlu.get("performance_feedback")
            if perf_fb and perf_fb.get("detected"):
                logger.info("[RECALL_SAVE] 🎯 Performance feedback detected! Auto-collecting...")
                parts.append("performance_feedback_detected")
                try:
                    # Find the most recent campaign to associate feedback with
                    recent_campaigns = memory.campaign_archive[-5:] if memory.campaign_archive else []
                    if recent_campaigns:
                        target_campaign = recent_campaigns[-1]  # Most recent
                        cid = target_campaign.campaign_id
                        # Determine engagement level
                        sentiment = perf_fb.get("sentiment", "neutral")
                        eng_map = {"positive": "high", "mixed": "medium", "negative": "low"}
                        engagement = eng_map.get(sentiment, "medium")
                        worked = perf_fb.get("what_worked", [])
                        failed = perf_fb.get("what_failed", [])
                        metrics = perf_fb.get("metrics", {})

                        # Import and call memory_collect_performance directly
                        from .memory_tools import _load_memory, _save_memory
                        _perf_data = {
                            "engagement_level": engagement,
                            "what_worked": worked,
                            "what_failed": failed,
                        }
                        if metrics.get("likes"): _perf_data["likes"] = metrics["likes"]
                        if metrics.get("comments"): _perf_data["comments"] = metrics["comments"]

                        # Update campaign performance directly
                        from .schemas import PerformanceData
                        if target_campaign.performance is None:
                            target_campaign.performance = PerformanceData()
                        target_campaign.performance.engagement_level = engagement
                        if worked: target_campaign.performance.what_worked = worked
                        if failed: target_campaign.performance.what_failed = failed
                        if metrics.get("likes"): target_campaign.performance.likes = metrics["likes"]
                        if metrics.get("comments"): target_campaign.performance.comments = metrics["comments"]

                        # Remove from performance_pending
                        memory.performance_pending = [
                            p for p in memory.performance_pending if p.campaign_id != cid
                        ]

                        # Update Behavior Graph
                        from .memory_tools import _recompute_graph_insights
                        from .schemas import ContentNode, PerformanceEdge
                        graph = memory.behavior_graph
                        for platform in (target_campaign.platforms_used or ["unknown"]):
                            node_id = f"{platform}_auto"
                            existing_node = next((n for n in graph.nodes if n.node_id == node_id), None)
                            if not existing_node:
                                graph.nodes.append(ContentNode(
                                    node_id=node_id, platform=platform,
                                    content_type="image", topic="auto-collected",
                                ))
                            graph.edges.append(PerformanceEdge(
                                edge_id=f"{cid}_{platform}_auto",
                                node_id=node_id, campaign_id=cid,
                                engagement_level=engagement,
                                what_worked=worked, what_failed=failed,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            ))
                        _recompute_graph_insights(graph)

                        # Save memory
                        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
                        logger.info(
                            "[RECALL_SAVE] ✅ Auto-collected performance for campaign %s: engagement=%s, worked=%s, failed=%s",
                            cid, engagement, worked, failed,
                        )
                        # Store for next turn's domain signal alert
                        callback_context.state["_auto_performance_collected"] = {
                            "campaign_id": cid,
                            "engagement": engagement,
                            "worked": worked,
                            "failed": failed,
                        }
                    else:
                        logger.info("[RECALL_SAVE] ⚠️ Performance feedback detected but no campaigns to associate with")
                except Exception as e:
                    logger.warning("[RECALL_SAVE] ⚠️ Auto performance collection failed: %s", e)

            logger.info(
                "[RECALL_SAVE] 📝 NLU signals (len=%d): emotions=%s, decisions=%s, domains=%s, perf=%s",
                len(user_text), nlu["emotions"], nlu["decisions"], nlu["domains"],
                bool(perf_fb and perf_fb.get("detected")),
            )
        else:
            logger.info("[RECALL_SAVE] 📝 NLU skipped — short message (%d chars)", len(user_text))
        note = "; ".join(parts) if parts else "auto-logged"

        entry = RecallEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            role="agent",
            content=content,
            summary_note=note,
        )
        memory.recall_log.append(entry)

        # Auto-compact overflow
        _compact_recall_to_summary(memory)

        memory.last_updated = datetime.now(timezone.utc).isoformat()
        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")

        # ── [Structural Fix] Store conversation context summary in state ──
        # This ensures agent transitions (transfer_to_agent) preserve context.
        # The next agent's _inject_core_memory reads this from state if recall_log is stale.
        recent_turns = memory.recall_log[-6:]  # Last 3 user + 3 agent turns
        ctx_summary = "\n".join(
            f"[{e.role}] {e.content[:150]}" for e in recent_turns
        )
        callback_context.state["_conversation_context"] = ctx_summary

        logger.info(
            "[RECALL_SAVE] 📝 Recall log size: %d entries, working_summary: %d chars",
            len(memory.recall_log), len(memory.working_summary or ""),
        )

    except Exception as e:
        logger.warning("[RECALL_SAVE] 🔴 Failed to auto-append agent turn: %s", e)

    # ── [Hyper-Personalization] 대화 자동 Qdrant 아카이빙 ──────────────
    # 매 턴 user+agent 대화를 Qdrant에 자동 임베딩 → 미래 시맨틱 검색 지원
    try:
        import uuid as _uuid
        now_iso = datetime.now(timezone.utc).isoformat()

        # User turn 아카이빙
        _user_qdrant_ok = False
        _agent_qdrant_ok = False
        if user_text:
            user_vec = _embed(user_text[:1000])
            if user_vec:
                conv_id = str(_uuid.uuid4())[:8]
                _user_qdrant_ok = _qdrant_upsert(
                    _QDRANT_CONVERSATIONS_COLLECTION,
                    f"conv_{conv_id}",
                    user_vec,
                    {"id": conv_id, "role": "user", "content": user_text[:500],
                     "timestamp": now_iso},
                )
                from .schemas import ConversationRecord
                memory.conversation_archive.append(ConversationRecord(
                    conversation_id=conv_id, timestamp=now_iso,
                    role="user", content=user_text[:1000],
                ))

        # Agent turn 아카이빙
        if content and not content.startswith("["):
            agent_vec = _embed(content[:1000])
            if agent_vec:
                conv_id = str(_uuid.uuid4())[:8]
                _agent_qdrant_ok = _qdrant_upsert(
                    _QDRANT_CONVERSATIONS_COLLECTION,
                    f"conv_{conv_id}",
                    agent_vec,
                    {"id": conv_id, "role": "agent", "content": content[:500],
                     "timestamp": now_iso},
                )
                from .schemas import ConversationRecord
                memory.conversation_archive.append(ConversationRecord(
                    conversation_id=conv_id, timestamp=now_iso,
                    role="agent", content=content[:1000],
                ))

        logger.info(
            "[RECALL_SAVE] ⚡ Qdrant auto-archive: user_turn=%s, agent_turn=%s",
            "success" if _user_qdrant_ok else "fail",
            "success" if _agent_qdrant_ok else "fail",
        )
        # 아카이빙 후 메모리 다시 저장
        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
    except Exception as e:
        logger.warning("[RECALL_SAVE] 🔴 Auto-archive conversation to Qdrant failed: %s", e)

    logger.info("[RECALL_SAVE] 🟢 Turn saved | total_time=%dms", int((time.time() - _t0_save) * 1000))


# ─── Content Orchestrator (채널별 Strategist 위임) ────────────────────
# 기존 content_pipeline (Sequential: content_agent → format_agent → response_agent)을
# content_orchestrator로 교체.
# orchestrator가 메모리 1회 조회 → 채널 파싱 → 채널별 strategist 위임.

# Apply MemGPT callbacks to orchestrator
content_orchestrator.before_agent_callback = _inject_core_memory
content_orchestrator.after_agent_callback = _auto_save_working_summary
content_orchestrator.after_tool_callback = _tool_heartbeat

# ─── General Chat Agent ────────────────────────────────────────────────
# [Fix 3 — MemGPT bug-fix Oct 15 2023]
# memory_agent was previously declared but never connected to any pipeline (dead code).
# Now exposed as AgentTool so general_chat_agent can delegate complex multi-step
# memory operations (e.g., bulk profile update + campaign search + summary write)
# to the dedicated memory manager — matching MemGPT's "function call to inner memory" pattern.
general_chat_agent = Agent(
    name="general_chat_agent",
    model="gemini-2.5-flash",
    description=prompt.GENERAL_CHAT_DESCRIPTION,
    instruction=prompt.GENERAL_CHAT_INSTRUCTIONS,
    before_agent_callback=_inject_core_memory,   # ← 채팅 에이전트도 Core Memory 주입
    after_agent_callback=_auto_save_working_summary,  # ← Auto working_summary 유지
    after_tool_callback=_tool_heartbeat,          # ← Heartbeat: 도구 완료 시 state 업데이트
    tools=[
        get_trends,
        advanced_search,
        # Core Memory 조회/수정
        memory_get_core_profile,
        memory_update_user_profile,
        memory_update_brand_voice,
        memory_update_domain_profile,
        memory_add_domain_knowledge,
        memory_get_knowledge,              # ← Knowledge ID/category 기반 조회
        # Product CRUD
        memory_add_product,                # ← 제품 생성
        memory_get_product,                # ← 제품 ID 기반 상세 조회
        memory_update_product,             # ← 제품 업데이트
        # Audience
        memory_update_audience_segment,
        memory_add_audience_trait,
        memory_get_audience_segments,
        # Campaign / Archival
        memory_get_recent_campaigns,
        memory_search_campaigns,
        memory_archive_conversation,
        memory_search_conversations,
        # Recall & Working Memory
        memory_update_working_summary,
        memory_add_performance_notes,
        memory_append_recall,
        memory_get_recall_log,
        # Performance & Behavior
        memory_collect_performance,
        memory_get_performance_pending,
        memory_mark_performance_asked,
        memory_get_behavior_insights,
        # Context Management
        memory_get_context_status,
        memory_compress_context,
        # Skill MD 참조
        read_skill_md,                     # ← 스킬 MD 파일 읽기
        # Memory Agent 위임
        AgentTool(agent=memory_agent),
    ],
)

# ─── Router Agent (root) ──────────────────────────────────────────────
root_agent = Agent(
    name="agents",
    model="gemini-2.5-flash",
    description="Root router agent that delegates to specialized sub-agents based on user intent.",
    instruction=prompt.ROUTER_INSTRUCTIONS,
    sub_agents=[content_orchestrator, general_chat_agent],
)
