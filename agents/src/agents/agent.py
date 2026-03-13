import json
import logging
from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext
from typing import Optional
from .sub_agents.image_generation import image_generation_agent
from .sub_agents.video_generation import video_generation_agent
from .sub_agents.audio_generation import audio_generation_agent
from .sub_agents.idea_generation import idea_generation_agent
from .sub_agents.memory import memory_agent  # [Fix 3] previously dead code — now connected
from .twitter_tools import advanced_search, get_trends, get_user_posts
from .video_editing_tools import assemble_video_with_audio
from .schemas import SocialMediaAgentInput, SocialMediaAgentOutput, MemoryState
from .memory_tools import (
    memory_get_core_profile,
    memory_update_user_profile,
    memory_update_brand_voice,
    memory_update_domain_profile,
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
    build_memory_context_block,
    _compact_recall_to_summary,
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
    from datetime import datetime, timezone

    raw = callback_context.state.get(_MEMORY_STATE_KEY)
    if raw is None:
        memory = MemoryState()
    elif isinstance(raw, dict):
        memory = MemoryState.model_validate(raw)
    else:
        memory = MemoryState.model_validate_json(raw)

    # ── [MemGPT Fix] Recall Memory: Python-level user turn auto-append ──────
    # MemGPT 원본: 시스템이 매 user turn을 강제로 message store에 기록
    # LLM이 memory_append_recall을 잊어버려도 대화 히스토리가 보존됨
    user_query = ""
    try:
        user_content = callback_context.user_content
        if user_content and user_content.parts:
            # Extract text from the first text part
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
            # Auto-compact: summarise overflow into working_summary
            _compact_recall_to_summary(memory)
            # Save updated recall_log back to state
            memory.last_updated = datetime.now(timezone.utc).isoformat()
            callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
    except Exception as e:
        logger.warning("Failed to auto-append user turn to recall_log: %s", e)

    # Core Memory 블록을 state에 기록 — 프롬프트에서 읽어감

    # Core Memory 블록을 state에 기록 — 프롬프트에서 읽어감
    # user_query 전달 → semantic archival hint가 자동 포함됨
    callback_context.state["_memory_block"] = build_memory_context_block(memory, user_query=user_query)

    # ── Context Window Management ──────────────────────────────────────
    turn = int(callback_context.state.get(_CTX_TURN_KEY, 0)) + 1
    callback_context.state[_CTX_TURN_KEY] = turn

    usage_pct = round(min(turn / _COMPRESS_THRESHOLD_TURNS * 100, 100.0), 1)
    callback_context.state["_ctx_usage_pct"] = usage_pct

    # Auto-compress at 80% threshold
    if turn >= _COMPRESS_THRESHOLD_TURNS:
        from .memory_tools import _WORKING_SUMMARY_MAX, _SUMMARY_PREV_KEEP
        prev_summary = memory.working_summary or ""
        memory.working_summary = (
            f"[Auto-compressed at turn {turn}] {prev_summary[:_SUMMARY_PREV_KEEP]}"
        )[:_WORKING_SUMMARY_MAX]
        _compact_recall_to_summary(memory)  # ← [Gap C] recall_log도 함께 압축
        from datetime import datetime, timezone
        memory.last_updated = datetime.now(timezone.utc).isoformat()
        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
        callback_context.state[_CTX_TURN_KEY] = 0
        callback_context.state["_ctx_usage_pct"] = 0.0


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
    "advanced_search": "Twitter 검색 중",
    "get_trends": "트렌드 조회 중",
    "get_user_posts": "유저 포스트 조회 중",
    "google_search": "Google 검색 중",
    "generate_image": "이미지 생성 중",
    "generate_video": "동영상 생성 중 (최대 3분)",
    "generate_audio": "오디오 생성 중",
    "assemble_video_with_audio": "동영상 합성 중",
    "memory_record_generated_asset": "에셋 저장 중",
    "memory_archive_campaign": "캠페인 저장 중",
    "memory_search_campaigns": "캠페인 검색 중",
    "memory_update_brand_voice": "브랜드 보이스 업데이트 중",
    "memory_update_domain_profile": "도메인 프로파일 업데이트 중",
    "memory_compress_context": "컨텍스트 압축 중",
    "memory_archive_conversation": "대화 기록 저장 중",
    "memory_search_conversations": "대화 기록 검색 중",
    "memory_collect_performance": "성과 데이터 기록 중",
    "memory_get_performance_pending": "성과 수집 목록 확인 중",
    "memory_get_behavior_insights": "행동 인사이트 분석 중",
}

_HEARTBEAT_MEMORY_SEARCH_TOOLS = {"memory_search_campaigns", "memory_search_conversations"}


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
    logger.info("Tool completed: %s → %s", tool_name, status)

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
                tool_context.state.pop("_continuation_hint", None)
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
    "social_media_branding_content_agent": "content_agent_output",
    "format_agent": "formated_content_agent_output",
}


def _auto_save_working_summary(callback_context: CallbackContext) -> None:
    """
    after_agent_callback: 에이전트 응답 완료 후 recall_log에 agent 턴을 자동 append.
    MemGPT 원본 패턴: 매 agent turn이 message store에 자동으로 기록됨.
    LLM이 memory_append_recall을 호출하지 않아도 대화 히스토리가 보존됨.

    [CC-2] output_key가 있는 에이전트는 실제 응답 텍스트를 캡처 (C방식).
    output_key가 없으면 sentinel fallback으로 턴 존재만 기록.
    """
    from datetime import datetime, timezone

    raw = callback_context.state.get(_MEMORY_STATE_KEY)
    if raw is None:
        return

    if isinstance(raw, dict):
        memory = MemoryState.model_validate(raw)
    else:
        memory = MemoryState.model_validate_json(raw)

    # ── [MemGPT Fix] Recall Memory: Python-level agent turn auto-append ─────
    # agent_name을 agent 응답의 식별자로 기록
    try:
        from .schemas import RecallEntry

        agent_name = callback_context.agent_name

        # [CC-2] Approach C: read actual response from session state via output_key
        actual_content = ""
        output_key = _AGENT_OUTPUT_KEYS.get(agent_name)
        if output_key:
            raw_output = callback_context.state.get(output_key)
            if raw_output:
                actual_content = str(raw_output)[:500]

        content = actual_content if actual_content else f"[{agent_name} responded]"

        entry = RecallEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            role="agent",
            content=content,
            summary_note="auto-logged by after_agent_callback",
        )
        memory.recall_log.append(entry)

        # Auto-compact overflow
        _compact_recall_to_summary(memory)

        memory.last_updated = datetime.now(timezone.utc).isoformat()
        callback_context.state[_MEMORY_STATE_KEY] = memory.model_dump(mode="json")
        logger.debug("Auto-appended agent turn to recall_log: %s", agent_name)

    except Exception as e:
        logger.warning("Failed to auto-append agent turn to recall_log: %s", e)


# ─── Content Generation Pipeline ─────────────────────────────────────
content_agent = Agent(
    name="social_media_branding_content_agent",
    model="gemini-2.5-flash",
    description=prompt.CONTENT_DESCRIPTION,
    instruction=prompt.CONTENT_INSTRUCTIONS,
    before_agent_callback=_inject_core_memory,   # ← MemGPT Core Memory 강제 주입
    after_agent_callback=_auto_save_working_summary,  # ← Auto working_summary 유지
    after_tool_callback=_tool_heartbeat,          # ← Heartbeat: 도구 완료 시 state 업데이트
    tools=[
        get_user_posts,
        advanced_search,
        AgentTool(agent=image_generation_agent),
        AgentTool(agent=video_generation_agent),
        AgentTool(agent=idea_generation_agent),
        get_trends,
        # MemGPT memory tools — 런타임 검색 및 쓰기용
        memory_get_core_profile,
        memory_archive_campaign,
        memory_search_campaigns,           # ← Vector Search 우선 semantic search
        memory_get_recent_campaigns,
        memory_archive_conversation,       # ← Archive conversation turns to archival memory
        memory_search_conversations,       # ← Semantic search over conversation history
        memory_update_brand_voice,
        memory_update_domain_profile,      # ← 도메인 프로파일 블록 업데이트
        memory_record_generated_asset,
        memory_get_assets,
        memory_add_performance_notes,
        memory_collect_performance,        # ← 구조화 성과 수집 + 행동 그래프 업데이트
        memory_get_behavior_insights,      # ← 집계 행동 그래프 인사이트 조회
        # Recall Memory tools — conversation history
        memory_append_recall,              # ← Rolling conversation log write
        memory_get_recall_log,             # ← Recall log read
        # Context window management tools
        memory_get_context_status,
        memory_compress_context,
    ],
    output_key="content_agent_output"
)

format_agent = Agent(
    name="format_agent",
    model="gemini-2.5-flash",
    description=prompt.FORMAT_DESCRIPTION,
    instruction=prompt.FORMAT_INSTRUCTIONS,
    output_key="formated_content_agent_output",
)

response_agent = Agent(
    name="response_agent",
    model="gemini-2.5-flash",
    instruction="Extract the `agent_response` from the final json format output from previous agent. Only return the agent_response as plain text.",
)

content_pipeline = SequentialAgent(
    name="content_pipeline",
    sub_agents=[content_agent, format_agent, response_agent],
    description="Full content generation pipeline. Use this when the user wants to generate, create, or modify social media content (posts, images, videos). This handles the entire workflow: content creation, formatting, and response extraction.",
)

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
        memory_get_core_profile,
        memory_update_user_profile,
        memory_update_brand_voice,
        memory_update_domain_profile,      # ← 도메인 프로파일 블록 업데이트
        memory_get_recent_campaigns,
        memory_search_campaigns,           # ← Semantic search (Vector Search 우선)
        memory_archive_conversation,       # ← Archive conversation turns to archival memory
        memory_search_conversations,       # ← Semantic search over conversation history
        memory_update_working_summary,
        memory_add_performance_notes,
        memory_collect_performance,        # ← 구조화 성과 데이터 수집 + 행동 그래프 업데이트
        memory_get_performance_pending,    # ← 성과 수집 대기 캠페인 목록
        memory_mark_performance_asked,     # ← 성과 질문 완료 마킹
        memory_get_behavior_insights,      # ← 집계 행동 그래프 인사이트 조회
        memory_append_recall,              # ← Rolling conversation log write
        memory_get_recall_log,             # ← Recall log read
        memory_get_context_status,
        memory_compress_context,
        AgentTool(agent=memory_agent),     # [Fix 3] delegate complex memory ops to dedicated agent
    ],
)

# ─── Router Agent (root) ──────────────────────────────────────────────
root_agent = Agent(
    name="agents",
    model="gemini-2.5-flash",
    description="Root router agent that delegates to specialized sub-agents based on user intent.",
    instruction=prompt.ROUTER_INSTRUCTIONS,
    sub_agents=[content_pipeline, general_chat_agent],
)
