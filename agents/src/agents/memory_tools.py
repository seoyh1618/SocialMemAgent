"""
MemGPT-style memory tools for SocialMediaBrandingAgent.

Architecture mirrors MemGPT's three-tier memory system:
  ┌──────────────────────────────────────────────────────────┐
  │  CORE MEMORY  (always in-context — 4 independent blocks) │
  │   • HumanBlock    → user identity & contact              │
  │   • PersonaBlock  → brand voice & style (was BrandVoice) │
  │   • DomainBlock   → business domain details              │
  │   • AudienceBlock → target audience & channels           │
  ├──────────────────────────────────────────────────────────┤
  │  ARCHIVAL MEMORY  (Qdrant vector semantic search)        │
  │   • CampaignRecord list → past campaigns, lessons        │
  │   • ConversationRecord  → past conversation turns        │
  │   Retrieval: ANN via Qdrant + text-embedding-004         │
  ├──────────────────────────────────────────────────────────┤
  │  RECALL MEMORY  (rolling conversation history)           │
  │   • recall_log      → last 20 turns verbatim             │
  │   • working_summary → condensed older turns              │
  └──────────────────────────────────────────────────────────┘

Storage layer: ADK ToolContext / session state (SQLite via ADK).
Vector search: Qdrant (external Docker service).
All tools are pure Python callables compatible with google.adk.tools.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from google.adk.tools import ToolContext

from .schemas import (
    AudienceBlock,
    AudienceBehaviorGraph,
    AudienceSegment,
    AudienceTrait,
    BrandVoice,
    CampaignRecord,
    ContentNode,
    ConversationRecord,
    DomainProfileBlock,
    GeneratedAsset,
    HumanBlock,
    MemoryState,
    PerformanceData,
    PerformanceEdge,
    PerformancePendingRequest,
    PersonaBlock,
    RecallEntry,
    UserProfile,
)

logger = logging.getLogger(__name__)

# ─── Embedding client (lazy init) ────────────────────────────────────────────
# Uses text-embedding-004 via google-generativeai (google-adk dependency).
# Lazy-initialised so unit tests can import this module without credentials.

_embed_client = None


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        from dotenv import load_dotenv
        load_dotenv()
        from google.genai import Client
        _embed_client = Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    return _embed_client


_EMBED_MODEL = "text-embedding-004"
_RECALL_WINDOW_TOKEN_BUDGET = 40_000   # Keep recent turns up to this many tokens verbatim
_RECALL_SUMMARISE_TOKEN_THRESHOLD = 80_000  # Trigger summarisation when log exceeds this total
_WORKING_SUMMARY_MAX = 2500  # Max chars for working_summary (800→2500: 장기 세션 맥락 보존 강화)
_SUMMARY_PREV_KEEP = 800    # How many chars of previous summary to retain when merging (300→800)

# ─── MemGPT Core Memory Character Limits (arXiv:2310.08560) ─────────────────
# Each core memory block has a hard character limit.
# If an update would exceed the limit, the tool returns an error (matching
# MemGPT's core_memory_append/core_memory_replace behaviour).
_CORE_CHAR_LIMIT_PROFILE = 5_000   # Human Block (HumanBlock)
_CORE_CHAR_LIMIT_VOICE   = 5_000   # Persona Block (PersonaBlock)
_CORE_CHAR_LIMIT_DOMAIN  = 3_000   # Domain Profile Block (DomainProfileBlock)

# Total char budget for build_memory_context_block() output.
# Priority order: Core (always) > Recall > Behavior/Trend > Archival
_CONTEXT_BLOCK_TOTAL_CHAR_BUDGET = 50_000

# ─── Archive Caps (SQLite blob 비대화 방지) ───────────────────────────────────
# 오래된 건 SQLite에서 제거하되 Qdrant 벡터는 영구 유지
_CONVERSATION_ARCHIVE_CAP = 100
_CAMPAIGN_ARCHIVE_CAP = 50

# ─── Hierarchical Summary Constants ───────────────────────────────────────────
_SESSION_SUMMARY_MAX = 500      # L2: 세션별 요약 최대 문자수
_SESSION_SUMMARIES_CAP = 10     # L2: 보관할 세션 요약 최대 개수
_LONG_TERM_SUMMARY_MAX = 3000   # L3: 장기 요약 최대 문자수


def _truncate_section(lines: list[str], max_chars: int) -> list[str]:
    """Truncate a section's lines to fit within max_chars (MemGPT-style).

    Keeps lines from the beginning until the budget is exhausted, then
    appends a truncation notice.  Returns the (possibly shorter) list.
    """
    if max_chars <= 0:
        return ["  (section trimmed — context budget exhausted)"]
    total = 0
    kept: list[str] = []
    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if total + line_len > max_chars:
            break
        kept.append(line)
        total += line_len
    if len(kept) < len(lines):
        kept.append(f"  … (trimmed {len(lines) - len(kept)} lines to fit context budget)")
    return kept


def _estimate_tokens(text: str) -> int:
    """Estimate token count using ~4 chars per token heuristic."""
    return max(1, len(text) // 4)


def _measure_profile_chars(profile) -> int:
    """Measure total character count for the HumanBlock."""
    parts = [
        profile.display_name or "",
        profile.twitter_handle or "",
        profile.instagram_handle or "",
        " ".join(f"{k}={v}" for k, v in profile.extra_fields.items()) if profile.extra_fields else "",
    ]
    return sum(len(p) for p in parts)


def _measure_voice_chars(voice) -> int:
    """Measure total character count for PersonaBlock (Persona Block)."""
    parts = [
        voice.tone or "",
        ", ".join(voice.preferred_styles) if voice.preferred_styles else "",
        ", ".join(voice.avoid_topics) if voice.avoid_topics else "",
        ", ".join(voice.signature_hashtags) if voice.signature_hashtags else "",
        ", ".join(voice.content_pillars) if voice.content_pillars else "",
    ]
    return sum(len(p) for p in parts)


def _measure_domain_chars(dp) -> int:
    """Measure total character count for DomainProfileBlock."""
    parts = [
        dp.industry or "",
        dp.domain_type or "",
        dp.business_location or "",
        dp.operating_hours or "",
        dp.price_range or "",
        dp.usp or "",
        ", ".join(dp.competitors) if dp.competitors else "",
        " ".join(f"{k}={v}" for k, v in dp.domain_extra.items()) if dp.domain_extra else "",
    ]
    return sum(len(p) for p in parts)


# ─────────────────────────────────────────────────────────────────────
#  _compact_recall_to_summary — 단일 헬퍼 (DRY 원칙)
#
#  이전 설계의 핵심 문제:
#    - 압축 로직이 3곳(memory_append_recall, _inject_core_memory,
#      _auto_save_working_summary)에 중복 구현됨
#    - merged[-600:] → 뒤에서만 잘라내므로 초기 핵심 정보 손실
#    - 이전 요약 + 새 overflow 단순 문자열 연결 (의미적 통합 없음)
#
#  개선 사항:
#    - 3곳의 중복 로직을 단일 함수로 통합
#    - 이전 요약의 앞부분(_SUMMARY_PREV_KEEP 자)을 보존하여 초기 정보 유지
#    - 날짜 범위 prefix로 overflow 기간 명시
#    - merged[:_WORKING_SUMMARY_MAX] → 앞에서 잘라 초기 정보 보존
# ─────────────────────────────────────────────────────────────────────

def _compact_recall_to_summary(memory: "MemoryState", force: bool = False) -> None:
    """
    [MemGPT: Recall Memory 압축 — 단일 헬퍼]
    recall_log가 _RECALL_SUMMARISE_AT을 초과할 때만 동작.
    force=True이면 recall_log 크기에 관계없이 LLM 압축을 강제 실행.
    overflow된 항목을 working_summary에 병합하고 recall_log를 _RECALL_WINDOW로 축소.

    [LLM Compression] MemGPT/Letta 원본 방식:
    Gemini API를 사용하여 overflow 항목 + 이전 요약을 의미론적으로 압축.
    API 오류 시 단순 문자열 병합 fallback으로 동작.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    # Calculate total token usage of the recall log
    total_tokens = sum(
        _estimate_tokens(e.content) + _estimate_tokens(e.role)
        for e in memory.recall_log
    )
    if not force and total_tokens <= _RECALL_SUMMARISE_TOKEN_THRESHOLD:
        return

    # Select the keep window: newest turns that fit within _RECALL_WINDOW_TOKEN_BUDGET
    keep: list = []
    budget = _RECALL_WINDOW_TOKEN_BUDGET
    for entry in reversed(memory.recall_log):
        entry_tokens = _estimate_tokens(entry.content) + _estimate_tokens(entry.role)
        if budget - entry_tokens < 0:
            break
        keep.insert(0, entry)
        budget -= entry_tokens

    overflow = memory.recall_log[: len(memory.recall_log) - len(keep)]
    memory.recall_log = keep

    if overflow:
        start_date = overflow[0].timestamp[:10]
        end_date = overflow[-1].timestamp[:10]
        date_range = f"{start_date}~{end_date}" if start_date != end_date else start_date
    else:
        date_range = "unknown"

    overflow_lines = [
        f"[{e.role}] {e.content[:150]}"
        for e in overflow
    ]
    overflow_text = f"[{date_range}] " + "\n".join(overflow_lines) if overflow else ""

    prev = memory.working_summary or ""

    # force=True이고 overflow가 없으면 working_summary만 압축 (LLM 호출은 아래에서 처리)
    if force and not overflow and not prev:
        return

    # ── [LLM Compression] Gemini API 호출로 의미론적 요약 생성 ──────────────
    try:
        import concurrent.futures
        client = _get_embed_client()
        if prev:
            prompt = (
                "You are a memory compression assistant. "
                "Compress the following conversation history into a concise summary "
                f"within {_WORKING_SUMMARY_MAX} characters. "
                "Preserve key facts, decisions, and context. "
                "Write in a compact, information-dense style.\n\n"
                f"PREVIOUS SUMMARY:\n{prev[:_SUMMARY_PREV_KEEP]}\n\n"
                f"NEW CONVERSATION TURNS TO INTEGRATE:\n{overflow_text}\n\n"
                "Produce a single unified summary combining both."
            )
        else:
            prompt = (
                "You are a memory compression assistant. "
                "Summarize the following conversation history concisely "
                f"within {_WORKING_SUMMARY_MAX} characters. "
                "Preserve key facts, decisions, and context.\n\n"
                f"CONVERSATION TURNS:\n{overflow_text}\n\n"
                "Produce a concise summary."
            )

        def _call_compress():
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call_compress)
            response = future.result(timeout=15)  # 15초 타임아웃

        llm_summary = response.text.strip() if response.text else ""

        if llm_summary:
            memory.working_summary = llm_summary[:_WORKING_SUMMARY_MAX]
            _logger.info(
                "Recall compacted via LLM: %d entries → working_summary (%d chars)",
                len(overflow),
                len(memory.working_summary),
            )
            return

    except concurrent.futures.TimeoutError:
        _logger.warning("LLM compression timed out (15s), falling back to string-join.")
    except Exception as llm_err:
        _logger.warning(
            "LLM compression failed (%s), falling back to string-join.", llm_err
        )

    # ── Fallback: 단순 문자열 병합 ────────────────────────────────────────────
    new_text = overflow_text
    if prev:
        kept_prev = prev[:_SUMMARY_PREV_KEEP]
        merged = f"[PREV: {kept_prev}] [NEW: {new_text}]"
    else:
        merged = new_text

    memory.working_summary = merged[:_WORKING_SUMMARY_MAX]
    _logger.info(
        "Recall compacted (fallback): %d entries → working_summary (%d chars)",
        len(overflow),
        len(memory.working_summary),
    )


def _compress_session_summary(memory: "MemoryState") -> None:
    """
    [Hierarchical Summary] 세션 종료 시 L1→L2→L3 계층적 압축.
    L1 (working_summary) → L2 (session_summaries[]) → L3 (long_term_summary)
    """
    # L1 → L2: working_summary가 있으면 session_summaries에 추가
    if memory.working_summary and memory.working_summary.strip():
        logger.info(
            "[COMPRESS] 🔵 L1→L2 compression | working_summary=%d chars → session_summaries[%d]",
            len(memory.working_summary), len(memory.session_summaries),
        )
        session_entry = f"[{memory.last_updated[:10]}] {memory.working_summary[:_SESSION_SUMMARY_MAX]}"
        memory.session_summaries.append(session_entry)
        memory.working_summary = ""  # L1 리셋 (다음 세션용)

    # L2 → L3: session_summaries가 cap 초과 시 오래된 것들을 L3로 병합
    if len(memory.session_summaries) > _SESSION_SUMMARIES_CAP:
        overflow = memory.session_summaries[:-_SESSION_SUMMARIES_CAP]
        logger.info("[COMPRESS] 🔵 L2→L3 compression | %d sessions merged into long_term_summary", len(overflow))
        memory.session_summaries = memory.session_summaries[-_SESSION_SUMMARIES_CAP:]

        overflow_text = "\n".join(overflow)
        prev_l3 = memory.long_term_summary or ""

        # LLM 압축 시도
        try:
            import concurrent.futures
            client = _get_embed_client()
            prompt = (
                "You are a long-term memory compression assistant. "
                "Merge the following session summaries into the existing long-term summary. "
                f"Output must be under {_LONG_TERM_SUMMARY_MAX} characters. "
                "Preserve: user preferences, brand identity, key decisions, successful strategies, "
                "important facts. Remove: greetings, repetitive info, trivial details.\n\n"
                f"EXISTING LONG-TERM SUMMARY:\n{prev_l3[:2000]}\n\n"
                f"NEW SESSION SUMMARIES TO INTEGRATE:\n{overflow_text[:3000]}\n\n"
                "Produce a single unified long-term summary."
            )

            def _call():
                return client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(_call).result(timeout=20)

            if response.text:
                memory.long_term_summary = response.text.strip()[:_LONG_TERM_SUMMARY_MAX]
                logger.info(
                    "[COMPRESS] 🟢 Compression complete | L2=%d sessions, L3=%d chars",
                    len(memory.session_summaries), len(memory.long_term_summary),
                )
                return
        except Exception as e:
            logger.warning("[COMPRESS] 🔴 L2→L3 LLM compression failed: %s — fallback merge.", e)

        # Fallback: 단순 병합
        merged = f"{prev_l3}\n{overflow_text}" if prev_l3 else overflow_text
        memory.long_term_summary = merged[:_LONG_TERM_SUMMARY_MAX]
        logger.info(
            "[COMPRESS] 🟢 Compression complete (fallback) | L2=%d sessions, L3=%d chars",
            len(memory.session_summaries), len(memory.long_term_summary),
        )


def _embed(text: str) -> List[float]:
    """Return embedding vector for text using text-embedding-004."""
    client = _get_embed_client()
    result = client.models.embed_content(
        model=_EMBED_MODEL,
        contents=text,
    )
    # EmbedContentResponse → embeddings[0].values
    return result.embeddings[0].values


# ─── Qdrant Vector Search ────────────────────────────────────────────────────
#
# 환경변수:
#   QDRANT_URL     — Qdrant 서버 URL (기본: http://localhost:6333)
#   QDRANT_API_KEY — 선택적 API 키
#
# Qdrant 미연결 시 keyword fallback으로 자동 전환.

_qdrant_client = None
_QDRANT_HEALTHY = True

_QDRANT_CAMPAIGNS_COLLECTION = "campaigns"
_QDRANT_CONVERSATIONS_COLLECTION = "conversations"
_QDRANT_VECTOR_SIZE = 768  # text-embedding-004 output dim


def _get_qdrant_client():
    """Lazy-init Qdrant client. 컬렉션 없으면 자동 생성."""
    global _qdrant_client, _QDRANT_HEALTHY
    if _qdrant_client is not None:
        return _qdrant_client

    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY", None)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        _qdrant_client = QdrantClient(url=url, api_key=api_key, timeout=10)

        for col in [_QDRANT_CAMPAIGNS_COLLECTION, _QDRANT_CONVERSATIONS_COLLECTION]:
            if not _qdrant_client.collection_exists(col):
                _qdrant_client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(
                        size=_QDRANT_VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Qdrant collection '%s' created.", col)

        logger.info("[QDRANT] 🔵 Client init | url=%s, status=connected", url)
        _QDRANT_HEALTHY = True
        return _qdrant_client
    except Exception as e:
        logger.warning("[QDRANT] 🔴 Client init | url=%s, status=failed | %s", url, e)
        _QDRANT_HEALTHY = False
        return None


def is_qdrant_healthy() -> bool:
    """Returns whether Qdrant is currently healthy and reachable."""
    return _QDRANT_HEALTHY


def _qdrant_upsert(collection: str, point_id: str, vector: List[float], payload: dict) -> bool:
    """Qdrant에 벡터+메타데이터 upsert. 실패 시 False."""
    client = _get_qdrant_client()
    if not client:
        logger.info("[QDRANT] ⚡ Upsert | collection=%s, point_id=%s, result=fail (no client)", collection, point_id[:16])
        return False
    try:
        from qdrant_client.models import PointStruct
        client.upsert(
            collection_name=collection,
            points=[PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, point_id)),
                vector=vector,
                payload=payload,
            )],
        )
        logger.info("[QDRANT] ⚡ Upsert | collection=%s, point_id=%s, result=success", collection, point_id[:16])
        return True
    except Exception as e:
        logger.warning("[QDRANT] ⚡ Upsert | collection=%s, point_id=%s, result=fail | %s", collection, point_id[:16], e)
        return False


def _qdrant_search(
    collection: str,
    query_vec: List[float],
    top_k: int = 10,
) -> List[tuple]:
    """Qdrant ANN 검색. Returns [(original_id, score, payload), ...]."""
    global _QDRANT_HEALTHY
    client = _get_qdrant_client()
    if not client:
        return []
    try:
        results = client.query_points(
            collection_name=collection,
            query=query_vec,
            limit=top_k,
            score_threshold=0.1,
        )
        _was_healthy = _QDRANT_HEALTHY
        _QDRANT_HEALTHY = True
        if not _was_healthy:
            logger.info("[QDRANT] ⚠️ Health status changed: healthy")
        _hits = [(hit.payload.get("id", ""), hit.score, hit.payload) for hit in results.points]
        _top_score = round(_hits[0][1], 3) if _hits else 0.0
        logger.info(
            "[QDRANT] 🔍 Search | collection=%s, top_k=%d, results=%d, top_score=%s",
            collection, top_k, len(_hits), _top_score,
        )
        return _hits
    except Exception as e:
        _was_healthy = _QDRANT_HEALTHY
        _QDRANT_HEALTHY = False
        if _was_healthy:
            logger.info("[QDRANT] ⚠️ Health status changed: unhealthy")
        logger.warning("[QDRANT] 🔍 Search | collection=%s, result=fail | %s", collection, e)
        return []


_MEMORY_KEY = "memory"


# ─── Private helpers ─────────────────────────────────────────────────────────

def _load_memory(tool_context: ToolContext) -> MemoryState:
    """Load MemoryState from ADK session state. Creates a fresh one if absent."""
    raw = tool_context.state.get(_MEMORY_KEY)
    if raw is None:
        return MemoryState()
    try:
        if isinstance(raw, dict):
            return MemoryState.model_validate(raw)
        return MemoryState.model_validate_json(raw)
    except Exception:
        logger.warning("Corrupted memory state — resetting to default MemoryState.")
        return MemoryState()


def _save_memory(tool_context: ToolContext, memory: MemoryState) -> None:
    """Persist MemoryState back into ADK session state. Enforces archive caps."""
    try:
        # Archive cap 적용 — SQLite blob 비대화 방지
        if len(memory.conversation_archive) > _CONVERSATION_ARCHIVE_CAP:
            memory.conversation_archive = memory.conversation_archive[-_CONVERSATION_ARCHIVE_CAP:]
        if len(memory.campaign_archive) > _CAMPAIGN_ARCHIVE_CAP:
            memory.campaign_archive = memory.campaign_archive[-_CAMPAIGN_ARCHIVE_CAP:]
        memory.last_updated = datetime.now(timezone.utc).isoformat()
        tool_context.state[_MEMORY_KEY] = memory.model_dump(mode="json")
        logger.info(
            "[MEMORY_SAVE] ⚡ Persisting memory | campaigns=%d/%d, conversations=%d/%d, segments=%d",
            len(memory.campaign_archive), _CAMPAIGN_ARCHIVE_CAP,
            len(memory.conversation_archive), _CONVERSATION_ARCHIVE_CAP,
            len(memory.audience_block.segments),
        )
    except Exception:
        logger.error("[MEMORY_SAVE] 🔴 Failed to save memory state.", exc_info=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Core Memory Tools (Human / Persona Block) ───────────────────────────────

def memory_get_core_profile(tool_context: ToolContext) -> str:
    """
    [MemGPT: Core Memory READ]
    Retrieve all 4 Core Memory blocks: Human, Persona, Domain, and Audience.
    Always call this at the start of a session to personalize content generation.

    Returns:
        JSON string with all 4 core memory blocks.
    """
    memory = _load_memory(tool_context)
    human = memory.human_block
    persona = memory.persona_block
    domain = memory.domain_block
    audience = memory.audience_block

    logger.info(
        "[MEMORY_READ] 🔍 Core profile loaded | human=%s, persona_tone=%s, domain=%s, segments=%d",
        human.display_name or "(empty)", persona.tone or "(empty)",
        domain.industry or "(empty)", len(audience.segments),
    )

    result = {
        "human_block": {
            "display_name": human.display_name,
            "twitter_handle": human.twitter_handle,
            "instagram_handle": human.instagram_handle,
            "extra_fields": human.extra_fields,
        },
        "persona_block": {
            "tone": persona.tone,
            "preferred_styles": persona.preferred_styles,
            "avoid_topics": persona.avoid_topics,
            "signature_hashtags": persona.signature_hashtags,
            "content_pillars": persona.content_pillars,
        },
        "domain_block": {
            "industry": domain.industry,
            "domain_type": domain.domain_type,
            "business_location": domain.business_location,
            "usp": domain.usp,
            "competitors": domain.competitors,
        },
        "audience_block": {
            "target_platforms": audience.target_platforms,
            "default_age_range": audience.default_age_range,
            "segments": [s.model_dump(mode="json") for s in audience.segments],
            "seasonal_peaks": audience.seasonal_peaks,
            "offline_channels": audience.offline_channels,
        },
        "total_campaigns": memory.total_campaigns,
        "working_summary": memory.working_summary,
    }
    return json.dumps(result, ensure_ascii=False)


def memory_update_user_profile(
    tool_context: ToolContext,
    display_name: Optional[str] = None,
    twitter_handle: Optional[str] = None,
    instagram_handle: Optional[str] = None,
    industry: Optional[str] = None,
    target_platforms: Optional[List[str]] = None,
    extra_fields: Optional[dict] = None,
) -> str:
    """
    [MemGPT: Core Memory WRITE — Human Block + cross-block routing]
    Update the user's persistent identity profile.
    Call this when the user shares new information about themselves or their brand.

    - display_name, twitter_handle, instagram_handle, extra_fields → human_block
    - industry → domain_block
    - target_platforms → audience_block

    Args:
        display_name: Brand or person name (e.g., 'Acme Co').
        twitter_handle: Twitter/X handle (e.g., '@acme').
        instagram_handle: Instagram handle (e.g., '@acme_official').
        industry: Business vertical (e.g., 'SaaS', 'Fashion'). Stored in domain_block.
        target_platforms: List of active platforms (e.g., ['twitter', 'instagram']). Stored in audience_block.
        extra_fields: Dict of arbitrary key-value pairs to MERGE into human_block.extra_fields
            (e.g., {'location': 'Seoul', 'employee_count': '50', 'founded_year': '2021'}).
            New keys are added; existing keys are updated. Pass only the keys to change.

    Returns:
        Confirmation message with updated fields.
    """
    memory = _load_memory(tool_context)
    human = memory.human_block
    updated_fields = []

    if display_name is not None:
        human.display_name = display_name
        updated_fields.append("display_name")
    if twitter_handle is not None:
        human.twitter_handle = twitter_handle
        updated_fields.append("twitter_handle")
    if instagram_handle is not None:
        human.instagram_handle = instagram_handle
        updated_fields.append("instagram_handle")
    if extra_fields is not None:
        # Merge — don't replace the whole dict
        human.extra_fields = {**human.extra_fields, **{str(k): str(v) for k, v in extra_fields.items()}}
        updated_fields.append(f"extra_fields({list(extra_fields.keys())})")

    # Cross-block routing: industry → domain_block
    if industry is not None:
        memory.domain_block.industry = industry
        updated_fields.append("industry→domain_block")

    # Cross-block routing: target_platforms → audience_block
    if target_platforms is not None:
        memory.audience_block.target_platforms = target_platforms
        updated_fields.append("target_platforms→audience_block")

    # ── MemGPT: enforce Core Memory char limit (arXiv:2310.08560) ──
    char_count = _measure_profile_chars(human)
    if char_count > _CORE_CHAR_LIMIT_PROFILE:
        return (
            f"[Memory Error] Human Block update rejected: {char_count} chars "
            f"exceeds limit of {_CORE_CHAR_LIMIT_PROFILE}. "
            "Condense existing data first with core_memory_replace."
        )

    logger.info("[MEMORY_WRITE] ⚡ memory_update_user_profile | fields_updated=%s", updated_fields)
    _save_memory(tool_context, memory)

    return f"[Memory Updated] Human Block fields updated: {', '.join(updated_fields)} ({char_count}/{_CORE_CHAR_LIMIT_PROFILE} chars)"


def memory_update_brand_voice(
    tool_context: ToolContext,
    tone: Optional[str] = None,
    preferred_styles: Optional[List[str]] = None,
    avoid_topics: Optional[List[str]] = None,
    signature_hashtags: Optional[List[str]] = None,
    content_pillars: Optional[List[str]] = None,
) -> str:
    """
    [MemGPT: Core Memory WRITE — Persona Block]
    Update the brand voice profile. This is the most important personalization signal.
    Call this when the user expresses preferences about tone, style, hashtags, or content themes.

    Args:
        tone: Brand communication tone (e.g., 'casual and witty').
        preferred_styles: Visual/content style preferences (e.g., ['Minimalist', 'Dark']).
        avoid_topics: Topics to never include (e.g., ['politics', 'competitors']).
        signature_hashtags: Brand hashtags to always include (e.g., ['#BuildInPublic']).
        content_pillars: Core content categories (e.g., ['Education', 'Product demos']).

    Returns:
        Confirmation message with updated fields.
    """
    memory = _load_memory(tool_context)
    voice = memory.persona_block
    updated_fields = []

    if tone is not None:
        voice.tone = tone
        updated_fields.append(f"tone='{tone}'")
    if preferred_styles is not None:
        voice.preferred_styles = preferred_styles
        updated_fields.append(f"preferred_styles={preferred_styles}")
    if avoid_topics is not None:
        voice.avoid_topics = avoid_topics
        updated_fields.append(f"avoid_topics={avoid_topics}")
    if signature_hashtags is not None:
        voice.signature_hashtags = signature_hashtags
        updated_fields.append(f"signature_hashtags={signature_hashtags}")
    if content_pillars is not None:
        voice.content_pillars = content_pillars
        updated_fields.append(f"content_pillars={content_pillars}")

    # ── MemGPT: enforce Core Memory char limit (arXiv:2310.08560) ──
    char_count = _measure_voice_chars(voice)
    if char_count > _CORE_CHAR_LIMIT_VOICE:
        return (
            f"[Memory Error] Persona Block update rejected: {char_count} chars "
            f"exceeds limit of {_CORE_CHAR_LIMIT_VOICE}. "
            "Condense existing data first with core_memory_replace."
        )

    logger.info("[MEMORY_WRITE] ⚡ memory_update_brand_voice | fields_updated=%s", updated_fields)
    _save_memory(tool_context, memory)

    return f"[Memory Updated] Persona Block (brand voice) updated: {'; '.join(updated_fields)} ({char_count}/{_CORE_CHAR_LIMIT_VOICE} chars)"


# ─── Domain Profile Block Tools ──────────────────────────────────────────────

def memory_update_domain_profile(
    tool_context: ToolContext,
    domain_type: Optional[str] = None,
    business_location: Optional[str] = None,
    operating_hours: Optional[str] = None,
    price_range: Optional[str] = None,
    offline_channels: Optional[List[str]] = None,
    seasonal_peaks: Optional[List[str]] = None,
    usp: Optional[str] = None,
    competitors: Optional[List[str]] = None,
    target_age_range: Optional[str] = None,
    industry: Optional[str] = None,
    domain_extra: Optional[dict] = None,
) -> str:
    """
    [Domain Profile Block WRITE + cross-block routing to Audience Block]
    Update the domain-specific business profile block.
    Call this when the user reveals business details: location, price range, operating hours,
    USP, competitors, seasonal patterns, or offline channels.

    - domain_type, business_location, operating_hours, price_range, usp, competitors,
      industry, domain_extra → domain_block
    - offline_channels, seasonal_peaks, target_age_range → audience_block

    Args:
        domain_type: Business type — 'restaurant', 'cafe', 'fashion', 'fitness', 'beauty',
                     'retail', 'education', 'saas', 'other'
        business_location: Physical location for local targeting (e.g., '서울 강남구')
        operating_hours: Operating hours (e.g., '10:00-22:00 Mon-Sat')
        price_range: Consumer segment indicator (e.g., '₩₩', 'premium', 'budget-friendly')
        offline_channels: Offline channels list (e.g., ['매장', '배달앱', '팝업스토어']). Stored in audience_block.
        seasonal_peaks: Key seasons/dates (e.g., ['크리스마스', '여름 성수기']). Stored in audience_block.
        usp: Unique selling point — core differentiator
        competitors: Main competitor brands/businesses
        target_age_range: Primary target age (e.g., '20-35'). Stored in audience_block.
        industry: Business vertical (e.g., 'SaaS', 'Fashion')
        domain_extra: Any other domain-specific key-value pairs

    Returns:
        Confirmation of updated fields.
    """
    memory = _load_memory(tool_context)
    dp = memory.domain_block
    ab = memory.audience_block
    updated = []

    if domain_type is not None:
        dp.domain_type = domain_type; updated.append("domain_type")
    if business_location is not None:
        dp.business_location = business_location; updated.append("business_location")
    if operating_hours is not None:
        dp.operating_hours = operating_hours; updated.append("operating_hours")
    if price_range is not None:
        dp.price_range = price_range; updated.append("price_range")
    if usp is not None:
        dp.usp = usp; updated.append("usp")
    if competitors is not None:
        dp.competitors = competitors; updated.append("competitors")
    if industry is not None:
        dp.industry = industry; updated.append("industry")
    if domain_extra is not None:
        dp.domain_extra.update(domain_extra); updated.append("domain_extra")

    # Cross-block routing: audience-related fields → audience_block
    if offline_channels is not None:
        ab.offline_channels = offline_channels; updated.append("offline_channels→audience_block")
    if seasonal_peaks is not None:
        ab.seasonal_peaks = seasonal_peaks; updated.append("seasonal_peaks→audience_block")
    if target_age_range is not None:
        ab.default_age_range = target_age_range; updated.append("default_age_range→audience_block")

    # ── MemGPT: enforce Core Memory char limit (arXiv:2310.08560) ──
    char_count = _measure_domain_chars(dp)
    if char_count > _CORE_CHAR_LIMIT_DOMAIN:
        return (
            f"[Memory Error] Domain Profile Block update rejected: {char_count} chars "
            f"exceeds limit of {_CORE_CHAR_LIMIT_DOMAIN}. "
            "Condense existing data first with core_memory_replace."
        )

    logger.info("[MEMORY_WRITE] ⚡ memory_update_domain_profile | fields_updated=%s", updated)
    _save_memory(tool_context, memory)
    return f"[Domain Profile Updated] Fields: {', '.join(updated)} ({char_count}/{_CORE_CHAR_LIMIT_DOMAIN} chars)"


def memory_add_domain_knowledge(
    tool_context: ToolContext,
    key: str,
    value: str,
    confidence: str = "confirmed",
) -> str:
    """
    [Domain Profile Block: Domain Knowledge WRITE]
    Store any business-related information learned from conversation.
    This is a flexible key-value store — use it for ANY domain-specific info
    that doesn't fit into the fixed fields (location, USP, etc.).

    The key categorizes the information, the value contains the detail.
    If a key already exists, the value will be updated (not duplicated).

    Examples of when to call:
    - 제품/메뉴: key="flagship_product", value="시그니처 딸기라떼 - 신선한 딸기, 6,500원"
    - 서비스: key="main_service", value="퍼스널 트레이닝 - 1회 5만원, 주 3회 패키지 할인"
    - 재료/소싱: key="ingredient_source", value="국내산 유기농 딸기 직거래"
    - 인증/수상: key="certification", value="ISO 9001 인증, 2025 건강용품 대상 수상"
    - 고객 특성: key="customer_insight", value="30대 직장인 여성이 주 고객, 점심시간 방문 많음"
    - 제휴: key="partnership", value="배달의민족 입점, 카카오 선물하기 연동"
    - 시설: key="facility", value="매장 30평, 포토존 2곳, 테라스 좌석 있음"
    - 제품 라인업: key="product_line", value="손목보호대, 무릎보호대, 발목보호대 (BARUEL 브랜드)"
    - 판매 채널: key="sales_channel", value="자사몰, 쿠팡, 네이버 스마트스토어"

    Args:
        key: Information category — use descriptive snake_case keys.
        value: Detailed information content. Include specifics: prices, names, numbers.
        confidence: 'confirmed' if user directly stated it, 'inferred' if deduced from context.

    Returns:
        Confirmation of stored knowledge.
    """
    from .schemas import DomainKnowledge
    memory = _load_memory(tool_context)
    dp = memory.domain_block

    # Update existing key or add new
    existing = None
    for k in dp.knowledge:
        if k.key == key:
            existing = k
            break

    if existing:
        existing.value = value
        existing.confidence = confidence
        existing.source_turn = _now_iso()
        action = "Updated"
    else:
        dp.knowledge.append(DomainKnowledge(
            key=key,
            value=value,
            confidence=confidence,
            source_turn=_now_iso(),
        ))
        # Cap at 50 knowledge items
        if len(dp.knowledge) > 50:
            dp.knowledge = dp.knowledge[-50:]
        action = "Added"

    _save_memory(tool_context, memory)
    total = len(dp.knowledge)
    return f"[Domain Knowledge {action}] key='{key}'. Total knowledge items: {total}"


# ─── Audience Segment Management Tools ────────────────────────────────────────

_AUDIENCE_SEGMENTS_CAP = 20
_AUDIENCE_TRAITS_PER_SEGMENT_CAP = 30


def memory_update_audience_segment(
    tool_context: ToolContext,
    name: str,
    age_range: str = "",
    gender: str = "",
    location: str = "",
    products: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
    source: str = "confirmed",
    notes: str = "",
) -> str:
    """
    [MemGPT: Audience Block WRITE — Segment]
    Create or update an audience segment. If a segment with the same name exists, update it.
    Use this when the user mentions a specific target audience group.

    Args:
        name: Segment name (e.g., '시니어 재활 고객', 'IT 직장인')
        age_range: Target age range for this segment
        gender: Gender distribution
        location: Geographic target
        products: Products/services this segment is interested in
        platforms: Channels where this segment is active
        source: 'confirmed' (user stated) | 'inferred' | 'discovered'
        notes: Additional notes

    Returns:
        Confirmation of the created or updated segment.
    """
    memory = _load_memory(tool_context)
    ab = memory.audience_block

    # Find existing segment by name (case-insensitive)
    existing = None
    for seg in ab.segments:
        if seg.name.strip().lower() == name.strip().lower():
            existing = seg
            break

    if existing:
        # Update existing segment — only update non-empty fields
        if age_range:
            existing.age_range = age_range
        if gender:
            existing.gender = gender
        if location:
            existing.location = location
        if products is not None:
            existing.products = products
        if platforms is not None:
            existing.platforms = platforms
        if source:
            existing.source = source
        if notes:
            existing.notes = notes
        action = "Updated"
        seg_id = existing.segment_id
    else:
        # Create new segment
        if len(ab.segments) >= _AUDIENCE_SEGMENTS_CAP:
            return (
                f"[Memory Error] Audience segment cap reached ({_AUDIENCE_SEGMENTS_CAP}). "
                "Remove an existing segment before adding a new one."
            )
        seg_id = f"seg_{uuid.uuid4().hex[:8]}"
        new_seg = AudienceSegment(
            segment_id=seg_id,
            name=name.strip(),
            source=source,
            age_range=age_range,
            gender=gender,
            location=location,
            products=products or [],
            platforms=platforms or [],
            notes=notes,
        )
        ab.segments.append(new_seg)
        action = "Created"

    logger.info(
        "[AUDIENCE] ⚡ Segment update | name=\"%s\", source=%s, age=%s, products=%s",
        name, source, age_range, products,
    )
    logger.info("[AUDIENCE] 📝 Total segments: %d/%d", len(ab.segments), _AUDIENCE_SEGMENTS_CAP)
    _save_memory(tool_context, memory)
    return (
        f"[Audience Segment {action}] '{name}' (id={seg_id}). "
        f"Total segments: {len(ab.segments)}/{_AUDIENCE_SEGMENTS_CAP}"
    )


def memory_add_audience_trait(
    tool_context: ToolContext,
    segment_name: str,
    key: str,
    value: str,
    confidence: str = "confirmed",
) -> str:
    """
    [MemGPT: Audience Block WRITE — Trait]
    Add a trait to an audience segment. If the segment doesn't exist, create it first.
    Use this when discovering specific attributes about a target audience.

    Args:
        segment_name: Name of the audience segment to add trait to
        key: Trait category (e.g., 'occupation', 'pain_point', 'motivation', 'budget',
             'lifestyle', 'media_habit', 'purchase_behavior')
        value: Trait value in natural language
        confidence: 'confirmed' | 'inferred' | 'discovered'

    Returns:
        Confirmation of the added trait.
    """
    memory = _load_memory(tool_context)
    ab = memory.audience_block

    # Find segment by name (case-insensitive)
    target_seg = None
    for seg in ab.segments:
        if seg.name.strip().lower() == segment_name.strip().lower():
            target_seg = seg
            break

    # If segment not found, auto-create it
    if target_seg is None:
        if len(ab.segments) >= _AUDIENCE_SEGMENTS_CAP:
            return (
                f"[Memory Error] Segment '{segment_name}' not found and segment cap reached "
                f"({_AUDIENCE_SEGMENTS_CAP}). Remove an existing segment first."
            )
        seg_id = f"seg_{uuid.uuid4().hex[:8]}"
        target_seg = AudienceSegment(
            segment_id=seg_id,
            name=segment_name.strip(),
            source=confidence,
        )
        ab.segments.append(target_seg)
        logger.info("Auto-created audience segment '%s' for trait addition.", segment_name)

    # Check trait cap
    if len(target_seg.traits) >= _AUDIENCE_TRAITS_PER_SEGMENT_CAP:
        return (
            f"[Memory Error] Trait cap reached for segment '{segment_name}' "
            f"({_AUDIENCE_TRAITS_PER_SEGMENT_CAP}). Remove old traits first."
        )

    # Update existing trait with same key, or add new
    existing_trait = None
    for t in target_seg.traits:
        if t.key == key:
            existing_trait = t
            break

    if existing_trait:
        existing_trait.value = value
        existing_trait.confidence = confidence
        action = "Updated"
    else:
        target_seg.traits.append(AudienceTrait(
            key=key,
            value=value,
            confidence=confidence,
        ))
        action = "Added"

    logger.info(
        "[AUDIENCE] ⚡ Trait added | segment=\"%s\", key=%s, value=\"%s\"",
        segment_name, key, value[:50],
    )
    logger.info("[AUDIENCE] 📝 Segment traits: %d/%d", len(target_seg.traits), _AUDIENCE_TRAITS_PER_SEGMENT_CAP)
    _save_memory(tool_context, memory)
    return (
        f"[Audience Trait {action}] '{key}' on segment '{segment_name}'. "
        f"Total traits: {len(target_seg.traits)}/{_AUDIENCE_TRAITS_PER_SEGMENT_CAP}"
    )


def memory_get_audience_segments(
    tool_context: ToolContext,
    segment_name: str = "",
) -> str:
    """
    [MemGPT: Audience Block READ]
    Retrieve audience segments. If segment_name is provided, return that specific segment.
    Otherwise return all segments summary.

    Args:
        segment_name: Optional — name of a specific segment to retrieve. Empty = all segments.

    Returns:
        JSON string with segment details.
    """
    memory = _load_memory(tool_context)
    ab = memory.audience_block

    if not ab.segments:
        return json.dumps({
            "status": "empty",
            "message": "No audience segments defined yet. Use memory_update_audience_segment to create one.",
            "default_age_range": ab.default_age_range,
            "target_platforms": ab.target_platforms,
        })

    if segment_name:
        # Find specific segment
        for seg in ab.segments:
            if seg.name.strip().lower() == segment_name.strip().lower():
                return json.dumps({
                    "status": "found",
                    "segment": seg.model_dump(mode="json"),
                })
        return json.dumps({
            "status": "not_found",
            "message": f"Segment '{segment_name}' not found.",
            "available_segments": [s.name for s in ab.segments],
        })

    # Return all segments summary
    summaries = []
    for seg in ab.segments:
        summary = {
            "segment_id": seg.segment_id,
            "name": seg.name,
            "source": seg.source,
            "age_range": seg.age_range,
            "gender": seg.gender,
            "location": seg.location,
            "products": seg.products,
            "platforms": seg.platforms,
            "trait_count": len(seg.traits),
            "top_traits": [{"key": t.key, "value": t.value[:80]} for t in seg.traits[:5]],
            "notes": seg.notes[:100] if seg.notes else "",
        }
        summaries.append(summary)

    return json.dumps({
        "status": "ok",
        "total_segments": len(ab.segments),
        "default_age_range": ab.default_age_range,
        "target_platforms": ab.target_platforms,
        "segments": summaries,
    })


def memory_collect_performance(
    tool_context: ToolContext,
    campaign_id: str,
    engagement_level: str,
    reach_level: str = "",
    conversion_level: str = "",
    best_platform: str = "",
    what_worked: Optional[List[str]] = None,
    what_failed: Optional[List[str]] = None,
    notes: str = "",
) -> str:
    """
    [Performance Feedback WRITE]
    Record structured performance data for a campaign based on user feedback.
    Call this when the user reports how a campaign performed.
    Also updates the Audience Behavior Graph with the new data point.

    Args:
        campaign_id: Campaign ID to update.
        engagement_level: Overall engagement — 'low', 'medium', 'high', 'viral'
        reach_level: Reach/impressions — 'low', 'medium', 'high'
        conversion_level: Conversion/action rate — 'low', 'medium', 'high'
        best_platform: Platform that performed best
        what_worked: List of elements that worked (e.g., ['밝은 색감', '짧은 캡션'])
        what_failed: List of elements that underperformed
        notes: Free-form notes (appended to existing performance_notes)

    Returns:
        Confirmation with updated campaign and behavior graph status.
    """
    logger.info("[PERFORMANCE] 🔵 Recording performance | campaign=%s, engagement=%s", campaign_id, engagement_level)
    memory = _load_memory(tool_context)

    # ── Update CampaignRecord ─────────────────────────────────────────────
    target_record = None
    for record in memory.campaign_archive:
        if record.campaign_id == campaign_id:
            target_record = record
            break

    if target_record is None:
        logger.info("[PERFORMANCE] 🔴 Campaign '%s' not found", campaign_id)
        return f"[Memory Error] Campaign '{campaign_id}' not found."

    perf = PerformanceData(
        engagement_level=engagement_level,
        reach_level=reach_level,
        conversion_level=conversion_level,
        best_platform=best_platform,
        what_worked=what_worked or [],
        what_failed=what_failed or [],
        collected_at=_now_iso(),
    )
    target_record.performance = perf
    if notes:
        target_record.performance_notes = notes

    # ── Remove from performance_pending queue ─────────────────────────────
    memory.performance_pending = [
        p for p in memory.performance_pending if p.campaign_id != campaign_id
    ]

    # ── Match campaign target_audiences to audience segments for segment_id ──
    matched_segment_id = ""
    if target_record.target_audiences:
        ab = memory.audience_block
        for ta in target_record.target_audiences:
            for seg in ab.segments:
                if seg.name.strip().lower() == ta.strip().lower():
                    matched_segment_id = seg.segment_id
                    break
            if matched_segment_id:
                break

    # ── Update Audience Behavior Graph ────────────────────────────────────
    graph = memory.behavior_graph
    for platform in target_record.platforms_used:
        for pillar in target_record.target_audiences or [""]:
            # Find or create node
            node_id = f"{platform}_{target_record.selected_styles[0] if target_record.selected_styles else 'general'}"
            existing_node = next((n for n in graph.nodes if n.node_id == node_id), None)
            if not existing_node:
                content_type = "video" if platform in ("tiktok", "youtube") else "image"
                graph.nodes.append(ContentNode(
                    node_id=node_id,
                    platform=platform,
                    content_type=content_type,
                    topic=pillar,
                ))

            # Add edge with segment_id if matched
            graph.edges.append(PerformanceEdge(
                edge_id=f"{campaign_id}_{platform}",
                node_id=node_id,
                campaign_id=campaign_id,
                segment_id=matched_segment_id,
                engagement_level=engagement_level,
                reach_level=reach_level,
                what_worked=what_worked or [],
                what_failed=what_failed or [],
                timestamp=_now_iso(),
            ))

    # ── Recompute graph aggregates ────────────────────────────────────────
    _recompute_graph_insights(graph)
    graph.last_updated = _now_iso()
    logger.info(
        "[PERFORMANCE] 📝 Behavior graph: %d nodes, %d edges | segment_match=%s",
        len(graph.nodes), len(graph.edges), matched_segment_id or "none",
    )

    # ── Re-embed campaign with performance data → Qdrant upsert ─────
    # 성과 데이터가 추가되었으므로 임베딩을 재생성하여 검색 정확도 유지
    _reembed_ok = False
    try:
        new_embed_text = _campaign_to_embed_text(target_record)
        new_vec = _embed(new_embed_text)
        if new_vec:
            _reembed_ok = _qdrant_upsert(
                _QDRANT_CAMPAIGNS_COLLECTION,
                f"campaign_{campaign_id}",
                new_vec,
                {"id": campaign_id, "goal": target_record.goal[:200],
                 "platforms": target_record.platforms_used,
                 "timestamp": target_record.timestamp},
            )
    except Exception as e:
        logger.warning("[PERFORMANCE] 🔴 Failed to re-embed campaign '%s': %s", campaign_id, e)
    logger.info("[PERFORMANCE] ⚡ Qdrant re-embed: %s", "success" if _reembed_ok else "fail")

    _save_memory(tool_context, memory)
    logger.info(
        "[PERFORMANCE] 🟢 Performance recorded | best_platform=%s, graph_updated=true",
        best_platform or "N/A",
    )
    return (
        f"[Performance Recorded] Campaign '{campaign_id}': "
        f"engagement={engagement_level}, best_platform={best_platform or 'N/A'}. "
        f"Behavior graph updated. Embedding refreshed."
    )


def _recompute_graph_insights(graph: AudienceBehaviorGraph) -> None:
    """Recompute platform_best_content_type, topic_performance_summary, overall_best_platform."""
    _LEVEL_SCORE = {"low": 1, "medium": 2, "high": 3, "viral": 4, "": 0}

    # Platform → list of engagement scores
    platform_scores: dict[str, list[int]] = {}
    platform_types: dict[str, dict[str, int]] = {}

    for edge in graph.edges:
        node = next((n for n in graph.nodes if n.node_id == edge.node_id), None)
        if not node:
            continue
        score = _LEVEL_SCORE.get(edge.engagement_level, 0)
        platform_scores.setdefault(node.platform, []).append(score)
        platform_types.setdefault(node.platform, {}).setdefault(node.content_type, 0)
        platform_types[node.platform][node.content_type] += score

    # Best content type per platform
    graph.platform_best_content_type = {
        p: max(types, key=types.get)
        for p, types in platform_types.items()
        if types
    }

    # Overall best platform
    if platform_scores:
        graph.overall_best_platform = max(
            platform_scores, key=lambda p: sum(platform_scores[p]) / len(platform_scores[p])
        )

    # Topic performance — based on edge what_worked tags
    topic_counts: dict[str, dict[str, int]] = {}
    for edge in graph.edges:
        node = next((n for n in graph.nodes if n.node_id == edge.node_id), None)
        if not node or not node.topic:
            continue
        topic_counts.setdefault(node.topic, {"high": 0, "medium": 0, "low": 0})
        lvl = edge.engagement_level if edge.engagement_level in ("low", "medium", "high", "viral") else "low"
        if lvl == "viral":
            lvl = "high"
        topic_counts[node.topic][lvl] += 1

    graph.topic_performance_summary = {
        topic: max(counts, key=counts.get)
        for topic, counts in topic_counts.items()
        if counts
    }


def memory_get_performance_pending(tool_context: ToolContext) -> str:
    """
    [Performance Queue READ]
    Get list of campaigns that need performance data collection.
    Call this at session start to decide whether to ask the user about past campaign results.

    Returns:
        JSON list of pending performance requests (max ask_count < 2).
    """
    memory = _load_memory(tool_context)
    pending = [p for p in memory.performance_pending if p.ask_count < 2]
    return json.dumps({
        "pending_count": len(pending),
        "campaigns": [
            {
                "campaign_id": p.campaign_id,
                "goal": p.campaign_goal,
                "platforms": p.platforms,
                "created_at": p.created_at,
                "ask_count": p.ask_count,
            }
            for p in pending
        ]
    }, ensure_ascii=False)


def memory_mark_performance_asked(tool_context: ToolContext, campaign_id: str) -> str:
    """
    [Performance Queue UPDATE]
    Mark a campaign as 'already asked' to avoid repeated prompting.
    Call this after asking the user about campaign performance, even if they haven't answered yet.

    Args:
        campaign_id: Campaign ID that was asked about.
    """
    memory = _load_memory(tool_context)
    for p in memory.performance_pending:
        if p.campaign_id == campaign_id:
            p.ask_count += 1
            p.asked_at = _now_iso()
    _save_memory(tool_context, memory)
    return f"[Performance Queue] Campaign '{campaign_id}' marked as asked."


def memory_get_behavior_insights(tool_context: ToolContext) -> str:
    """
    [Behavior Graph READ]
    Get aggregated audience behavior insights from the User Behavior Graph.
    Use this to inform content strategy recommendations based on past performance patterns.

    Returns:
        JSON with platform insights, content type recommendations, and topic performance.
    """
    memory = _load_memory(tool_context)
    graph = memory.behavior_graph

    # Collect what_worked / what_failed frequency across all edges
    worked_freq: dict[str, int] = {}
    failed_freq: dict[str, int] = {}
    for edge in graph.edges:
        for tag in edge.what_worked:
            worked_freq[tag] = worked_freq.get(tag, 0) + 1
        for tag in edge.what_failed:
            failed_freq[tag] = failed_freq.get(tag, 0) + 1

    top_worked = sorted(worked_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    top_failed = sorted(failed_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    return json.dumps({
        "overall_best_platform": graph.overall_best_platform,
        "platform_best_content_type": graph.platform_best_content_type,
        "topic_performance": graph.topic_performance_summary,
        "top_what_worked": [t for t, _ in top_worked],
        "top_what_failed": [t for t, _ in top_failed],
        "total_data_points": len(graph.edges),
        "last_updated": graph.last_updated,
    }, ensure_ascii=False)


# ─── Archival Memory Tools (Campaign History) ────────────────────────────────

def _campaign_to_embed_text(record: CampaignRecord) -> str:
    """Concatenate all searchable fields of a campaign into a single string for embedding.
    Includes performance data if available — enables search by outcome (e.g., "고성과 캠페인")."""
    parts = [
        record.goal,
        record.selected_trend,
        record.guideline_summary,
        record.performance_notes,
        " ".join(record.target_audiences),
        " ".join(record.selected_styles),
        " ".join(record.platforms_used),
    ]
    # Include performance data for richer semantic search
    if record.performance:
        perf = record.performance
        if perf.engagement_level:
            parts.append(f"engagement:{perf.engagement_level}")
        if perf.best_platform:
            parts.append(f"best_platform:{perf.best_platform}")
        if perf.what_worked:
            parts.append("worked:" + " ".join(perf.what_worked))
        if perf.what_failed:
            parts.append("failed:" + " ".join(perf.what_failed))
    return " ".join(p for p in parts if p).strip()


def memory_archive_campaign(
    tool_context: ToolContext,
    goal: str,
    selected_trend: str = "",
    target_audiences: Optional[List[str]] = None,
    selected_styles: Optional[List[str]] = None,
    guideline_summary: str = "",
    platforms_used: Optional[List[str]] = None,
    performance_notes: str = "",
) -> str:
    """
    [MemGPT: Archival Memory WRITE]
    Save a completed campaign to long-term archival memory.
    Automatically generates and caches an embedding vector for future semantic search.
    Call this after every successful content generation.

    Args:
        goal: The campaign goal.
        selected_trend: Trend theme used in this campaign.
        target_audiences: List of audience group names targeted.
        selected_styles: List of style names used.
        guideline_summary: One-sentence summary of the content guideline.
        platforms_used: List of platforms generated (e.g., ['twitter', 'instagram']).
        performance_notes: Optional user feedback on engagement or results.

    Returns:
        Campaign ID of the archived record.
    """
    memory = _load_memory(tool_context)

    record = CampaignRecord(
        campaign_id=str(uuid.uuid4())[:8],
        timestamp=_now_iso(),
        goal=goal,
        selected_trend=selected_trend,
        target_audiences=target_audiences or [],
        selected_styles=selected_styles or [],
        guideline_summary=guideline_summary,
        platforms_used=platforms_used or [],
        performance_notes=performance_notes,
    )
    logger.info(
        "[CAMPAIGN] 🔵 Archiving campaign | id=%s, goal=\"%s\", platforms=%s",
        record.campaign_id, goal[:80], platforms_used,
    )

    # Generate embedding and upsert to Qdrant
    _qdrant_ok = False
    try:
        embed_text = _campaign_to_embed_text(record)
        vector = _embed(embed_text)
        if vector:
            _qdrant_ok = _qdrant_upsert(
                _QDRANT_CAMPAIGNS_COLLECTION,
                f"campaign_{record.campaign_id}",
                vector,
                {"id": record.campaign_id, "goal": record.goal[:200],
                 "platforms": record.platforms_used, "timestamp": record.timestamp},
            )
    except Exception as e:
        logger.warning("[CAMPAIGN] 🔴 Failed to embed campaign '%s': %s", record.campaign_id, e)
    logger.info("[CAMPAIGN] ⚡ Qdrant upsert: %s | vector_dims=768", "success" if _qdrant_ok else "fail")

    # Unlimited campaign archive — no cap (Qdrant handles retrieval at scale)
    memory.campaign_archive.append(record)

    # Add to performance_pending queue so agent asks user about results next session
    pending = PerformancePendingRequest(
        campaign_id=record.campaign_id,
        campaign_goal=goal[:100],
        platforms=platforms_used or [],
        created_at=_now_iso(),
    )
    memory.performance_pending.append(pending)
    # Keep pending queue to max 10 unasked items
    if len(memory.performance_pending) > 10:
        memory.performance_pending = memory.performance_pending[-10:]

    logger.info("[CAMPAIGN] 📝 Added to performance_pending queue | pending_count=%d", len(memory.performance_pending))

    memory.total_campaigns += 1
    _save_memory(tool_context, memory)

    logger.info("[CAMPAIGN] 🟢 Campaign archived | total_campaigns=%d", memory.total_campaigns)
    return f"[Memory Archived] Campaign '{record.campaign_id}' saved. Total campaigns: {memory.total_campaigns}"


def memory_search_campaigns(
    tool_context: ToolContext,
    query: str,
    limit: int = 5,
) -> str:
    """
    [MemGPT: Archival Memory READ — Semantic Similarity Search]
    Find campaigns SIMILAR TO a specific topic/keyword using vector similarity.

    USE THIS TOOL WHEN the user asks:
    - "봄 시즌 관련 캠페인 찾아줘" (topic-based search)
    - "비슷한 캠페인 있어?" (similarity search)
    - "이전에 쿠키 홍보한 적 있어?" (specific product search)

    DO NOT use this for listing ALL campaigns — use memory_get_recent_campaigns instead.

    Args:
        query: Specific topic/keyword to search for (any language).
               e.g., '두바이 쫀득 쿠키', '봄 시즌 프로모션', '인스타그램 패션 홍보'
        limit: Maximum number of results to return (default 5).

    Returns:
        JSON list of matching campaign records sorted by semantic relevance.
    """
    memory = _load_memory(tool_context)

    if not memory.campaign_archive:
        return json.dumps({"message": "No campaigns in archive yet.", "results": []})

    archive_map = {r.campaign_id: r for r in memory.campaign_archive}
    scored: List[tuple[float, CampaignRecord]] = []
    _search_method = "keyword"

    # ── Path 1: Qdrant ANN search ─────────────────────────────────────────
    try:
        query_vec = _embed(query)
        qdrant_results = _qdrant_search(
            _QDRANT_CAMPAIGNS_COLLECTION, query_vec, top_k=limit * 2
        )
        if qdrant_results:
            for cid, sim, payload in qdrant_results:
                record = archive_map.get(cid)
                if record:
                    scored.append((sim, record))
            _search_method = "qdrant"
    except Exception as e:
        logger.warning("[SEARCH] 🔴 Qdrant campaign query failed: %s", e)

    # ── Path 2: Keyword fallback ──────────────────────────────────────────
    if not scored:
        query_lower = query.lower()
        for record in reversed(memory.campaign_archive):
            searchable = _campaign_to_embed_text(record).lower()
            if any(kw in searchable for kw in query_lower.split()):
                scored.append((1.0, record))

    matches = [
        {
            "campaign_id": r.campaign_id,
            "timestamp": r.timestamp,
            "goal": r.goal,
            "trend": r.selected_trend,
            "audiences": r.target_audiences,
            "styles": r.selected_styles,
            "guideline_summary": r.guideline_summary,
            "platforms": r.platforms_used,
            "performance_notes": r.performance_notes,
            # 구조화 성과 데이터 포함 — 에이전트 리즈닝에 활용
            "performance": r.performance.model_dump() if r.performance else None,
            "relevance_score": round(score, 3),
        }
        for score, r in scored[:limit]
        if score > 0.1  # filter out near-zero similarity
    ]

    _top_score = round(scored[0][0], 3) if scored else 0.0
    _top_goal = scored[0][1].goal[:60] if scored else ""
    logger.info(
        "[SEARCH] 🔍 Campaign search | query=\"%s\" | method=%s | results=%d | top_score=%s | top_goal=\"%s\"",
        query[:60], _search_method, len(matches), _top_score, _top_goal,
    )

    if not matches:
        return json.dumps({"message": "No relevant past campaigns found.", "results": []})

    return json.dumps({"results": matches, "count": len(matches)}, ensure_ascii=False)


def memory_get_recent_campaigns(tool_context: ToolContext, limit: int) -> str:
    """
    [MemGPT: Campaign LIST — Time-ordered]
    List ALL recent campaigns in chronological order with their performance data.

    USE THIS TOOL WHEN the user asks:
    - "캠페인 보여줘", "이전 캠페인", "캠페인 목록", "성과 보여줘"
    - "어떤 캠페인 했었지?", "지난번 캠페인"
    - ANY request to VIEW, LIST, or SHOW campaigns

    DO NOT use memory_search_campaigns for listing — that is for semantic similarity search only.

    Args:
        limit: Number of recent campaigns to retrieve (default 5).

    Returns:
        JSON list of campaign records with goal, platforms, performance data.
    """
    memory = _load_memory(tool_context)
    recent = memory.campaign_archive[-limit:] if memory.campaign_archive else []
    recent_reversed = list(reversed(recent))

    results = [
        {
            "campaign_id": r.campaign_id,
            "timestamp": r.timestamp,
            "goal": r.goal,
            "platforms": r.platforms_used,
            "guideline_summary": r.guideline_summary,
        }
        for r in recent_reversed
    ]
    return json.dumps({"recent_campaigns": results}, ensure_ascii=False)


def memory_archive_conversation(
    tool_context: ToolContext,
    role: str,
    content: str,
    session_id: str,
    summary: str,
) -> str:
    """
    [MemGPT: Archival Memory WRITE — Conversation History]
    Save one conversation turn to long-term archival memory.
    Automatically generates and caches an embedding vector for future semantic search.
    Call this after each user message and agent response to maintain full conversation history.

    Args:
        role: 'user' or 'agent'.
        content: Message content (will be truncated to 1000 chars).
        session_id: ADK session ID for this turn.
        summary: Optional short annotation of this turn.

    Returns:
        Confirmation with conversation turn ID.
    """
    memory = _load_memory(tool_context)
    record = ConversationRecord(
        conversation_id=str(uuid.uuid4())[:8],
        timestamp=_now_iso(),
        role=role,
        content=content[:1000],
        session_id=session_id,
        summary=summary,
    )
    try:
        vector = _embed(content[:1000])
        if vector:
            _qdrant_upsert(
                _QDRANT_CONVERSATIONS_COLLECTION,
                f"conv_{record.conversation_id}",
                vector,
                {"id": record.conversation_id, "role": role,
                 "session_id": session_id, "timestamp": record.timestamp},
            )
        logger.info("Conversation embedding stored: %s", record.conversation_id)
    except Exception as e:
        logger.warning("Failed to embed conversation '%s': %s. Keyword fallback active.", record.conversation_id, e)
    # Unlimited conversation archive
    memory.conversation_archive.append(record)
    _save_memory(tool_context, memory)
    return f"[Memory Archived] Conversation turn '{record.conversation_id}' saved. Total archived turns: {len(memory.conversation_archive)}"


def memory_search_conversations(
    tool_context: ToolContext,
    query: str,
    top_k: int = 5,
) -> str:
    """
    [MemGPT: Archival Memory READ — Conversation Search]
    Semantically search past conversation turns using embedding similarity.
    Falls back to keyword matching if embeddings are unavailable.

    Args:
        query: Natural language query to search conversation history.
        top_k: Number of top results to return (default: 5).

    Returns:
        JSON string with matching conversation turns.
    """
    memory = _load_memory(tool_context)
    if not memory.conversation_archive:
        return json.dumps({"conversations": [], "note": "No conversation history archived yet."}, ensure_ascii=False)

    conv_map = {r.conversation_id: r for r in memory.conversation_archive}
    results: list[dict] = []
    search_type = "keyword"

    # ── Path 1: Qdrant ANN search ─────────────────────────────────────────
    try:
        query_vec = _embed(query)
        qdrant_results = _qdrant_search(
            _QDRANT_CONVERSATIONS_COLLECTION, query_vec, top_k=top_k * 2
        )
        if qdrant_results:
            for cid, sim, payload in qdrant_results:
                record = conv_map.get(cid)
                if record and sim > 0.1:
                    results.append({
                        "conversation_id": record.conversation_id,
                        "timestamp": record.timestamp,
                        "role": record.role,
                        "content": record.content,
                        "session_id": record.session_id,
                        "summary": record.summary,
                        "score": round(sim, 4),
                    })
            if results:
                search_type = "qdrant"
                logger.info("Qdrant conv query '%s': %d hits", query, len(results))
                return json.dumps({"conversations": results[:top_k], "search_type": search_type}, ensure_ascii=False)
    except Exception as e:
        logger.warning("Qdrant conversation query failed: %s", e)

    # ── Path 2: Keyword fallback ──────────────────────────────────────────
    q_lower = query.lower()
    for record in reversed(memory.conversation_archive):
        if q_lower in record.content.lower() or q_lower in record.summary.lower():
            results.append({
                "conversation_id": record.conversation_id,
                "timestamp": record.timestamp,
                "role": record.role,
                "content": record.content,
                "session_id": record.session_id,
                "summary": record.summary,
            })
            if len(results) >= top_k:
                break

    return json.dumps({"conversations": results, "search_type": "keyword"}, ensure_ascii=False)


# ─── Recall Memory Tools (Working Summary) ───────────────────────────────────

def memory_update_working_summary(
    tool_context: ToolContext,
    summary: str,
) -> str:
    """
    [MemGPT: Recall Memory WRITE]
    Update the rolling working summary that condenses recent session context.
    Call this at the END of each session to preserve key insights for next time.
    Keep it under 500 characters — focus on user preferences discovered, decisions made,
    and any unresolved items.

    Args:
        summary: Concise summary of this session's key insights and decisions.

    Returns:
        Confirmation message.
    """
    memory = _load_memory(tool_context)
    memory.working_summary = summary[:_WORKING_SUMMARY_MAX]  # Guard against oversized summaries
    _save_memory(tool_context, memory)
    return f"[Memory Updated] Working summary saved ({len(summary)} chars)."


# ─── Recall Memory Tools (Conversation History) ──────────────────────────────

def memory_append_recall(
    tool_context: ToolContext,
    role: str,
    content: str,
    summary_note: str = "",
) -> str:
    """
    [MemGPT: Recall Memory WRITE — Conversation Log]
    Append one turn to the rolling conversation history (recall_log).
    Automatically summarises the oldest entries into working_summary when the log
    exceeds the window size, matching MemGPT's sliding-window recall pattern.

    Call this ONCE after each user message and ONCE after the agent response to
    maintain a full conversation record.

    Args:
        role: 'user' or 'agent'.
        content: Message content (will be truncated to 500 chars).
        summary_note: Optional annotation (e.g., 'User confirmed platform = Instagram').

    Returns:
        Confirmation with current recall_log length.
    """
    memory = _load_memory(tool_context)

    entry = RecallEntry(
        timestamp=_now_iso(),
        role=role,
        content=content[:500],
        summary_note=summary_note,
    )
    memory.recall_log.append(entry)

    # When log exceeds the summarise threshold, condense the oldest entries
    _compact_recall_to_summary(memory)

    _save_memory(tool_context, memory)
    return f"[Recall Memory] Entry appended. Log size: {len(memory.recall_log)}"


def memory_get_recall_log(
    tool_context: ToolContext,
    limit: int,
) -> str:
    """
    [MemGPT: Recall Memory READ — Recent Conversation History]
    Retrieve the most recent conversation turns from recall_log.
    Use this to review exactly what was said in the current session.

    Args:
        limit: Number of recent turns to retrieve (default 10, max 20).

    Returns:
        JSON list of recent RecallEntry objects, oldest-first.
    """
    memory = _load_memory(tool_context)
    limit = min(limit, 20)
    recent = memory.recall_log[-limit:] if memory.recall_log else []

    results = [
        {
            "timestamp": e.timestamp,
            "role": e.role,
            "content": e.content,
            "summary_note": e.summary_note,
        }
        for e in recent
    ]

    return json.dumps({
        "recall_log": results,
        "total_turns_in_log": len(memory.recall_log),
        "working_summary": memory.working_summary or "(none)",
    }, ensure_ascii=False)


def memory_add_performance_notes(
    tool_context: ToolContext,
    campaign_id: str,
    notes: str,
) -> str:
    """
    [MemGPT: Archival Memory UPDATE]
    Add performance feedback to a previously archived campaign.
    Call this when the user reports engagement results or requests modifications based on past results.

    Args:
        campaign_id: The campaign ID to update.
        notes: User's performance feedback or engagement results.

    Returns:
        Confirmation or error message.
    """
    memory = _load_memory(tool_context)
    for record in memory.campaign_archive:
        if record.campaign_id == campaign_id:
            record.performance_notes = notes
            _save_memory(tool_context, memory)
            return f"[Memory Updated] Performance notes added to campaign '{campaign_id}'."

    return f"[Memory Error] Campaign '{campaign_id}' not found in archive."


# ─── Asset Archive Tools (Generated Images & Videos) ─────────────────────────

def memory_record_generated_asset(
    tool_context: ToolContext,
    asset_id: str,
    asset_type: str,
    gcs_url: str,
    prompt_used: str = "",
    platform: str = "",
    session_id: str = "",
    local_filename: str = "",
    caption: str = "",
    hashtags: str = "",
) -> str:
    """
    [MemGPT: Asset Archive WRITE]
    Index a newly generated image or video asset in long-term memory.
    Call this immediately after a successful GCS upload so the asset appears in the Creations tab.

    Args:
        asset_id: Unique identifier for the asset (e.g., UUID or filename stem).
        asset_type: 'image' or 'video'.
        gcs_url: Public GCS URL of the stored asset.
        prompt_used: The generation prompt used to create this asset.
        platform: Target platform (e.g., 'instagram', 'tiktok', 'youtube').
        session_id: ADK session ID in which the asset was generated.
        local_filename: Original filename used during generation (optional).
        caption: Post caption/text used with this asset (e.g., Instagram caption).
        hashtags: Comma-separated hashtags (e.g., "#건강,#손목보호대,#헬스"). Will be split into a list.

    Returns:
        Confirmation message with the recorded asset ID.
    """
    memory = _load_memory(tool_context)

    asset = GeneratedAsset(
        asset_id=asset_id,
        asset_type=asset_type,
        gcs_url=gcs_url,
        local_filename=local_filename,
        prompt_used=prompt_used,
        caption=caption,
        hashtags=[t.strip() for t in hashtags.split(",") if t.strip()] if hashtags else [],
        platform=platform,
        created_at=_now_iso(),
        session_id=session_id,
    )

    memory.asset_archive.append(asset)
    # Cap at 200 assets to prevent unbounded growth
    if len(memory.asset_archive) > 200:
        memory.asset_archive = memory.asset_archive[-200:]

    _save_memory(tool_context, memory)
    return f"[Memory Archived] Asset '{asset_id}' ({asset_type}, {platform}) recorded. Total assets: {len(memory.asset_archive)}"


def memory_get_assets(
    tool_context: ToolContext,
    asset_type: Optional[str],
    platform: Optional[str],
    limit: int,
) -> str:
    """
    [MemGPT: Asset Archive READ]
    Retrieve previously generated assets from the archive.
    Use this to show the user their past creations or to reuse assets.

    Args:
        asset_type: Filter by 'image' or 'video'. If None, returns all types.
        platform: Filter by platform (e.g., 'instagram'). If None, returns all platforms.
        limit: Maximum number of results to return (default 20, most recent first).

    Returns:
        JSON list of matching asset records.
    """
    memory = _load_memory(tool_context)
    assets = list(reversed(memory.asset_archive))  # Most recent first

    if asset_type:
        assets = [a for a in assets if a.asset_type == asset_type]
    if platform:
        assets = [a for a in assets if a.platform == platform]

    assets = assets[:limit]

    results = [
        {
            "asset_id": a.asset_id,
            "asset_type": a.asset_type,
            "gcs_url": a.gcs_url,
            "platform": a.platform,
            "prompt_used": a.prompt_used,
            "caption": getattr(a, 'caption', ''),
            "hashtags": getattr(a, 'hashtags', []),
            "created_at": a.created_at,
            "session_id": a.session_id,
            "local_filename": a.local_filename,
            "is_user_uploaded": getattr(a, 'is_user_uploaded', False),
        }
        for a in assets
    ]

    return json.dumps({"assets": results, "count": len(results)}, ensure_ascii=False)


# ─── Context Window Management ───────────────────────────────────────────────

# Gemini 2.5 Flash context window: ~1,000,000 tokens.
# We track conversation turns as a proxy (accurate token counting requires the
# actual API response metadata). Each turn is assumed ≈ 2,000 tokens average.
_TOKENS_PER_TURN_ESTIMATE = 2000
_CONTEXT_WINDOW_TOKENS = 1_000_000
_COMPRESS_THRESHOLD = 0.80          # Trigger compression at 80%
_TURNS_TO_COMPRESS = int(_CONTEXT_WINDOW_TOKENS * _COMPRESS_THRESHOLD / _TOKENS_PER_TURN_ESTIMATE)
# = ~400 turns before auto-compress. Adjust _TOKENS_PER_TURN_ESTIMATE downward
# for heavier prompts (e.g. 8000 for content generation turns → threshold = 100 turns).

_TURN_COUNTER_KEY = "_ctx_turns"


def _get_turn_count(tool_context: ToolContext) -> int:
    """Read the current conversation turn counter from session state."""
    return int(tool_context.state.get(_TURN_COUNTER_KEY, 0))


def _set_turn_count(tool_context: ToolContext, count: int) -> None:
    tool_context.state[_TURN_COUNTER_KEY] = count


def memory_tick_turn(tool_context: ToolContext) -> str:
    """
    [MemGPT: Context Window Management — TICK]
    Increment the conversation turn counter by 1.
    Call this once at the START of every agent response (before other tool calls).

    Returns:
        JSON with current turn count, estimated context usage %, and whether
        auto-compression was triggered.
    """
    count = _get_turn_count(tool_context) + 1
    _set_turn_count(tool_context, count)

    usage_pct = round(count / _TURNS_TO_COMPRESS * 100, 1)
    triggered = False

    if count >= _TURNS_TO_COMPRESS:
        # Auto-compress: summarize working_summary and reset counter
        memory = _load_memory(tool_context)
        prev_summary = memory.working_summary or ""
        recent_info = (
            f"[Auto-compressed at turn {count}] "
            f"Prior summary: {prev_summary[:300]}"
        )
        memory.working_summary = recent_info[:600]
        _save_memory(tool_context, memory)
        _set_turn_count(tool_context, 0)
        triggered = True
        usage_pct = 0.0

    return json.dumps({
        "turn": count,
        "context_usage_pct": usage_pct,
        "compress_threshold_turns": _TURNS_TO_COMPRESS,
        "auto_compressed": triggered,
    })


def memory_compress_context(
    tool_context: ToolContext,
    session_summary: str,
) -> str:
    """
    [MemGPT: Context Window Management — MANUAL COMPRESS]
    Manually compress context: update working_summary with a fresh distillation
    of the current session and reset the turn counter.
    Call this proactively when the conversation has covered many topics and
    you want to preserve key insights before context degrades.

    Args:
        session_summary: A concise (≤500 chars) summary of insights, decisions,
            and unresolved items from the current session so far.

    Returns:
        Confirmation with new context usage %.
    """
    memory = _load_memory(tool_context)
    prev = memory.working_summary or ""

    # Merge: keep a short tail of the previous summary for continuity
    if prev and len(prev) > 100:
        merged = f"[prev] {prev[:200]} | [now] {session_summary}"
    else:
        merged = session_summary

    memory.working_summary = merged[:_WORKING_SUMMARY_MAX]
    _save_memory(tool_context, memory)
    _set_turn_count(tool_context, 0)

    return json.dumps({
        "status": "compressed",
        "working_summary_length": len(memory.working_summary),
        "context_usage_pct": 0.0,
    })


def memory_get_context_status(tool_context: ToolContext) -> str:
    """
    [MemGPT: Context Window Management — STATUS]
    Returns the current context window usage estimate.
    Use this to decide whether to compress before a long generation task.

    Returns:
        JSON with turn count, estimated usage %, and threshold.
    """
    count = _get_turn_count(tool_context)
    usage_pct = round(min(count / max(_TURNS_TO_COMPRESS, 1) * 100, 100.0), 1)
    return json.dumps({
        "turn": count,
        "context_usage_pct": usage_pct,
        "compress_threshold_turns": _TURNS_TO_COMPRESS,
        "needs_compression": count >= _TURNS_TO_COMPRESS,
    })


def build_memory_context_block(memory: MemoryState, user_query: str = "") -> str:
    """
    Build the MemGPT-style memory block to inject into agent system prompts.

    Components:
      1. Core Memory    — Human Block + Domain Profile Block + Persona Block (always injected)
      2. Recall Memory  — Last 5 conversation turns (always injected)
      3. Archival hint  — Top 2 semantically similar past campaigns (if query provided)
      4. Behavior Graph — Aggregated audience performance insights (always injected if data exists)
      5. Performance Queue — Campaigns awaiting feedback collection (session-start trigger)
    """
    _t0_ctx = time.time()
    logger.info("[CONTEXT] 🔵 Building context block | user_query=\"%s\"", (user_query or "")[:60])
    human = memory.human_block
    voice = memory.persona_block
    dp = memory.domain_block
    audience = memory.audience_block

    # ── Legacy extra_fields (backward compat) ─────────────────────────
    extra_lines = [
        f"  {k.replace('_', ' ').title():<12}: {v}"
        for k, v in (human.extra_fields or {}).items()
    ]

    # ── Domain Profile Block ──────────────────────────────────────────
    domain_lines = []
    if dp.industry:
        domain_lines.append(f"  Industry     : {dp.industry}")
    if dp.domain_type:
        domain_lines.append(f"  Domain Type  : {dp.domain_type}")
    if dp.business_location:
        domain_lines.append(f"  Location     : {dp.business_location}")
    if dp.price_range:
        domain_lines.append(f"  Price Range  : {dp.price_range}")
    if dp.usp:
        domain_lines.append(f"  USP          : {dp.usp}")
    if dp.competitors:
        domain_lines.append(f"  Competitors  : {', '.join(dp.competitors)}")
    if dp.operating_hours:
        domain_lines.append(f"  Hours        : {dp.operating_hours}")
    for k, v in (dp.domain_extra or {}).items():
        domain_lines.append(f"  {k.replace('_',' ').title():<12}: {v}")
    # Domain Knowledge (flexible key-value store)
    if hasattr(dp, 'knowledge') and dp.knowledge:
        domain_lines.append("  ── Domain Knowledge ──")
        for dk in dp.knowledge[:15]:  # Show top 15
            conf = "✓" if dk.confidence == "confirmed" else "?"
            domain_lines.append(f"  {conf} {dk.key.replace('_',' ').title()}: {dk.value[:80]}")
    if not domain_lines:
        domain_lines = ["  (not configured — use memory_update_domain_profile to fill)"]

    # ── Audience Block ────────────────────────────────────────────────
    audience_lines = []
    if audience.target_platforms:
        audience_lines.append(f"  Platforms    : {', '.join(audience.target_platforms)}")
    if audience.default_age_range:
        audience_lines.append(f"  Default Age  : {audience.default_age_range}")
    if audience.segments:
        audience_lines.append(f"  Segments ({len(audience.segments)}):")
        for seg in audience.segments[:5]:  # Show first 5 to save context budget
            seg_info = f"    [{seg.name}]"
            if seg.age_range:
                seg_info += f" age={seg.age_range}"
            if seg.gender:
                seg_info += f" gender={seg.gender}"
            if seg.products:
                seg_info += f" products={', '.join(seg.products[:3])}"
            if seg.platforms:
                seg_info += f" channels={', '.join(seg.platforms[:3])}"
            audience_lines.append(seg_info)
            # Show top 3 traits per segment
            for trait in seg.traits[:3]:
                conf = "✓" if trait.confidence == "confirmed" else "?" if trait.confidence == "inferred" else "★"
                audience_lines.append(f"      {conf} {trait.key}: {trait.value[:60]}")
        if len(audience.segments) > 5:
            audience_lines.append(f"    … (+{len(audience.segments) - 5} more segments)")
    if audience.seasonal_peaks:
        audience_lines.append(f"  Seasonal     : {', '.join(audience.seasonal_peaks)}")
    if audience.offline_channels:
        audience_lines.append(f"  Offline Ch.  : {', '.join(audience.offline_channels)}")
    if not audience_lines:
        audience_lines = ["  (not configured — use memory_update_domain_profile or memory_update_audience_segment to fill)"]

    # ── Recall log: token-budget window ──────────────────────────────
    recall_lines = []
    if memory.recall_log:
        recent: list = []
        budget = _RECALL_WINDOW_TOKEN_BUDGET
        for entry in reversed(memory.recall_log):
            entry_tokens = _estimate_tokens(entry.content) + _estimate_tokens(entry.role)
            if budget - entry_tokens < 0:
                break
            recent.insert(0, entry)
            budget -= entry_tokens
        for e in recent:
            ts = e.timestamp[:16].replace("T", " ")
            recall_lines.append(f"  [{ts}] {e.role.upper()}: {e.content[:200]}")
        if not recall_lines:
            recall_lines = ["  (no conversation history yet)"]
    else:
        recall_lines = ["  (no conversation history yet)"]

    # ── Archival Memory: metadata only (MemGPT §3.2 — search-based retrieval) ─
    # Per MemGPT paper, archival data is NEVER auto-injected into context.
    # Only metadata (counts) appear here; full retrieval via tool calls only.
    n_campaigns = len(memory.campaign_archive) if memory.campaign_archive else 0
    n_conversations = len(memory.conversation_archive) if memory.conversation_archive else 0

    # ── Behavior Graph Insights ───────────────────────────────────────
    graph = memory.behavior_graph
    behavior_lines = []
    if graph.edges:
        if graph.overall_best_platform:
            behavior_lines.append(f"  Best Platform    : {graph.overall_best_platform}")
        if graph.platform_best_content_type:
            for plat, ctype in graph.platform_best_content_type.items():
                behavior_lines.append(f"  {plat:<16}: {ctype} 콘텐츠가 최고 성과")
        if graph.topic_performance_summary:
            for topic, level in graph.topic_performance_summary.items():
                behavior_lines.append(f"  주제 [{topic}]: {level} 성과")
        # Top what_worked
        worked_freq: dict[str, int] = {}
        for edge in graph.edges:
            for tag in edge.what_worked:
                worked_freq[tag] = worked_freq.get(tag, 0) + 1
        if worked_freq:
            top_worked = sorted(worked_freq, key=worked_freq.get, reverse=True)[:3]
            behavior_lines.append(f"  잘 되는 요소     : {', '.join(top_worked)}")
        failed_freq: dict[str, int] = {}
        for edge in graph.edges:
            for tag in edge.what_failed:
                failed_freq[tag] = failed_freq.get(tag, 0) + 1
        if failed_freq:
            top_failed = sorted(failed_freq, key=failed_freq.get, reverse=True)[:3]
            behavior_lines.append(f"  피해야 할 요소   : {', '.join(top_failed)}")
        # GAP-2 fix: Cross-reference Behavior Graph insights with Domain Profile
        # Alert agent when graph data suggests domain profile enrichment opportunities
        domain = memory.domain_block
        cross_hints = []
        if graph.overall_best_platform and not domain.domain_type:
            cross_hints.append(
                f"  ⚡ Behavior data shows '{graph.overall_best_platform}' is best, "
                "but domain_type is empty — ask user about their business type."
            )
        if graph.platform_best_content_type and not domain.usp:
            best_items = list(graph.platform_best_content_type.items())[:2]
            cross_hints.append(
                f"  ⚡ Content strategy emerging ({', '.join(f'{p}→{t}' for p, t in best_items)}), "
                "but USP is empty — ask user about their unique selling point."
            )
        if worked_freq and memory.audience_block.seasonal_peaks == []:
            top_tag = sorted(worked_freq, key=worked_freq.get, reverse=True)[0]
            cross_hints.append(
                f"  ⚡ Top tactic '{top_tag}' identified — consider updating seasonal_peaks "
                "if this correlates with a specific season or event."
            )
        if cross_hints:
            behavior_lines.append("  ── Domain Profile Enrichment Hints ──")
            behavior_lines.extend(cross_hints)
    else:
        behavior_lines = ["  (성과 데이터 없음 — 캠페인 성과 피드백 후 자동 업데이트)"]

    # ── Performance Trend Analysis ────────────────────────────────────
    perf_trend_lines = []
    campaigns_with_perf = [c for c in memory.campaign_archive if c.performance is not None]
    if campaigns_with_perf:
        # Per-platform CTR computation (clicks / views)
        platform_metrics: dict[str, list[float]] = {}
        platform_engagement: dict[str, list[str]] = {}
        for c in campaigns_with_perf:
            p = c.performance
            for plat in (c.platforms_used or []):
                if plat not in platform_metrics:
                    platform_metrics[plat] = []
                    platform_engagement[plat] = []
                if p.views and p.views > 0 and p.clicks is not None:
                    ctr = round(p.clicks / p.views * 100, 2)
                    platform_metrics[plat].append(ctr)
                if p.engagement_level:
                    platform_engagement[plat].append(p.engagement_level)

        # Rank platforms by avg CTR
        platform_avg_ctr: dict[str, float] = {}
        for plat, ctrs in platform_metrics.items():
            if ctrs:
                platform_avg_ctr[plat] = round(sum(ctrs) / len(ctrs), 2)

        if platform_avg_ctr:
            ranked = sorted(platform_avg_ctr.items(), key=lambda x: x[1], reverse=True)
            top_plat, top_ctr = ranked[0]
            perf_trend_lines.append(f"  Top Platform (CTR): {top_plat} — avg {top_ctr}% CTR")
            if len(ranked) > 1:
                bot_plat, bot_ctr = ranked[-1]
                perf_trend_lines.append(f"  Low Platform (CTR): {bot_plat} — avg {bot_ctr}% CTR")

        # Engagement level distribution per platform
        for plat, levels in platform_engagement.items():
            if levels:
                from collections import Counter
                most_common = Counter(levels).most_common(1)[0][0]
                perf_trend_lines.append(f"  {plat} engagement: mostly {most_common}")

        # Most frequent what_worked / what_failed across ALL campaigns
        all_worked: dict[str, int] = {}
        all_failed: dict[str, int] = {}
        for c in campaigns_with_perf:
            p = c.performance
            for tag in (p.what_worked or []):
                all_worked[tag] = all_worked.get(tag, 0) + 1
            for tag in (p.what_failed or []):
                all_failed[tag] = all_failed.get(tag, 0) + 1

        if all_worked:
            top_w = sorted(all_worked, key=all_worked.get, reverse=True)[:3]
            perf_trend_lines.append(f"  Proven tactics     : {', '.join(top_w)}")
        if all_failed:
            top_f = sorted(all_failed, key=all_failed.get, reverse=True)[:3]
            perf_trend_lines.append(f"  Avoid repeating    : {', '.join(top_f)}")

        # Recent trend: compare last 3 vs previous 3 overall engagement
        level_score = {"high": 3, "medium": 2, "low": 1}
        recent3 = campaigns_with_perf[-3:]
        prev3 = campaigns_with_perf[-6:-3]
        def avg_score(clist):
            scores = [level_score.get((c.performance.engagement_level or "").lower(), 0) for c in clist]
            return sum(scores) / len(scores) if scores else 0
        r_score = avg_score(recent3)
        p_score = avg_score(prev3)
        if p_score > 0:
            if r_score > p_score:
                perf_trend_lines.append("  Trend: ↑ improving — recent campaigns outperform earlier ones")
            elif r_score < p_score:
                perf_trend_lines.append("  Trend: ↓ declining — recent campaigns underperform vs. earlier")
            else:
                perf_trend_lines.append("  Trend: → stable performance across campaigns")

        perf_trend_lines.append(f"  Based on {len(campaigns_with_perf)} campaign(s) with performance data")
    else:
        perf_trend_lines = ["  (no performance data yet — collect via memory_collect_performance)"]

    # ── Proactive Campaign Suggestions ────────────────────────────────
    proactive_lines: list[str] = []
    if campaigns_with_perf:
        high_perf = []
        for c in campaigns_with_perf:
            p = c.performance
            is_high = False
            if p.engagement_level and p.engagement_level.lower() == "high":
                is_high = True
            elif p.views and p.clicks and p.views > 0:
                ctr = p.clicks / p.views
                if ctr >= 0.05:
                    is_high = True
            if is_high:
                high_perf.append(c)
        if high_perf:
            proactive_lines.append(f"  🎯 고성과 캠페인 기반 변형 제안 가능: {len(high_perf)}개")
            for c in high_perf[:3]:
                p = c.performance
                plats = ", ".join(c.platforms_used) if c.platforms_used else "(없음)"
                worked = p.what_worked if p.what_worked else "(미기록)"
                eng = p.engagement_level or "N/A"
                proactive_lines.append(f"    ★ [{c.campaign_id}] {c.goal[:60]}")
                proactive_lines.append(f"      플랫폼: {plats} | 참여도: {eng}")
                proactive_lines.append(f"      성공요인: {worked}")
            proactive_lines.append("  → 위 캠페인의 성공 요소를 활용한 변형 캠페인을 사용자에게 제안하세요")

    # ── Performance pending (session-start trigger) ───────────────────
    pending = [p for p in memory.performance_pending if p.ask_count < 2]
    pending_lines = []
    if pending:
        pending_lines.append(f"  ⚠ 성과 확인 대기: {len(pending)}개 캠페인")
        for p in pending[:3]:
            pending_lines.append(f"    - [{p.campaign_id}] {p.campaign_goal[:50]} ({', '.join(p.platforms)})")
        pending_lines.append("  → 세션 시작 시 memory_get_performance_pending으로 확인 후 유저에게 자연스럽게 질문")

    # ── MemGPT-style context window management (arXiv:2310.08560) ────────
    # Build each section independently, then apply priority-based trimming
    # to fit within _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET.
    # Priority: Core (always kept) > Recall > Behavior/Trend > Archival

    # --- Core sections (never trimmed) ---
    core_lines = [
        "════════════════════════════════════════",
        "  PERSISTENT USER MEMORY  [MemGPT Core — 4 Blocks]",
        "════════════════════════════════════════",
        "",
        "▶ HUMAN BLOCK (User Identity)",
        f"  Name        : {human.display_name or '(not set)'}",
        f"  Twitter     : {human.twitter_handle or '(not set)'}",
        f"  Instagram   : {human.instagram_handle or '(not set)'}",
        *extra_lines,
        "",
        "▶ PERSONA BLOCK (Brand Voice)",
        f"  Tone        : {voice.tone or '(not defined yet)'}",
        f"  Styles      : {', '.join(voice.preferred_styles) if voice.preferred_styles else '(none)'}",
        f"  Pillars     : {', '.join(voice.content_pillars) if voice.content_pillars else '(none)'}",
        f"  Hashtags    : {', '.join(voice.signature_hashtags) if voice.signature_hashtags else '(none)'}",
        f"  Avoid       : {', '.join(voice.avoid_topics) if voice.avoid_topics else '(none)'}",
        "",
        "▶ DOMAIN PROFILE BLOCK (Business Details)",
        *domain_lines,
        "",
        "▶ AUDIENCE BLOCK (Target Audience & Channels)",
        *audience_lines,
    ]

    # --- Trimmable sections (lowest priority first) ---
    sec_archival = [
        "",
        "▶ ARCHIVAL MEMORY (search-based only — use tools to retrieve)",
        f"  Campaigns stored : {n_campaigns}",
        f"  Conversations    : {n_conversations}",
        "  → Use memory_search_campaigns / memory_search_conversations tools",
    ]

    sec_behavior = [
        "",
        "▶ AUDIENCE BEHAVIOR GRAPH (Performance Insights)",
        *behavior_lines,
    ]

    sec_trend = [
        "",
        "▶ PERFORMANCE TREND ANALYSIS (Campaign-Level Insights)",
        *perf_trend_lines,
    ]

    # ── Hierarchical Recall Memory (L1/L2/L3) ──────────────────────
    l1_line = f"  [L1 Current session summary]: {memory.working_summary}" if memory.working_summary else ""
    l2_lines = []
    if memory.session_summaries:
        l2_lines.append("  [L2 Recent session summaries]:")
        for s in memory.session_summaries[-3:]:  # 최근 3개 세션만 주입
            l2_lines.append(f"    {s[:200]}")
    l3_line = ""
    if memory.long_term_summary:
        l3_line = f"  [L3 Long-term memory]: {memory.long_term_summary[:1500]}"

    sec_recall = [
        "",
        "▶ RECALL MEMORY (Hierarchical — L1 current / L2 sessions / L3 long-term)",
        *recall_lines,
        *([] if not l1_line else [l1_line]),
        *l2_lines,
        *([] if not l3_line else [l3_line]),
    ]

    sec_pending = (
        ["", "▶ PERFORMANCE COLLECTION QUEUE", *pending_lines]
        if pending_lines else []
    )

    sec_proactive = (
        ["", "▶ PROACTIVE CAMPAIGN SUGGESTIONS (Past Performance-Based)", *proactive_lines]
        if proactive_lines else []
    )

    footer = ["════════════════════════════════════════"]

    # --- Measure core (always kept) + footer ---
    def _section_chars(section: list[str]) -> int:
        return sum(len(line) + 1 for line in section)  # +1 for newline

    core_chars = _section_chars(core_lines) + _section_chars(footer)
    remaining = _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET - core_chars

    # --- Apply budget to trimmable sections (trim lowest priority first) ---
    # Order: recall (highest) → behavior → trend → pending → archival (lowest)
    # We allocate greedily: measure each section, trim if over budget.
    trimmable_sections = [
        ("recall", sec_recall),
        ("behavior", sec_behavior),
        ("trend", sec_trend),
        ("proactive", sec_proactive),
        ("pending", sec_pending),
        ("archival", sec_archival),
    ]

    # First pass: measure total needed
    total_needed = sum(_section_chars(s) for _, s in trimmable_sections)

    if total_needed <= remaining:
        # Everything fits — no trimming needed
        trimmed = {name: section for name, section in trimmable_sections}
    else:
        # Trim from lowest priority upward until budget is met
        trimmed = {}
        budget_left = remaining
        # Process highest priority first to guarantee their space
        for name, section in trimmable_sections:
            sec_size = _section_chars(section)
            if sec_size <= budget_left:
                trimmed[name] = section
                budget_left -= sec_size
            else:
                trimmed[name] = _truncate_section(section, budget_left)
                budget_left -= _section_chars(trimmed[name])
                if budget_left < 0:
                    budget_left = 0

    # --- Qdrant health warning ---
    qdrant_warning = []
    if not _QDRANT_HEALTHY:
        qdrant_warning = [
            "",
            "  \u26a0\ufe0f VECTOR SEARCH UNAVAILABLE \u2014 Semantic search degraded. Keyword fallback only.",
        ]

    # --- Assemble final output in display order ---
    lines = [
        *core_lines,
        *trimmed.get("behavior", []),
        *trimmed.get("trend", []),
        *trimmed.get("recall", []),
        *trimmed.get("archival", []),
        *trimmed.get("proactive", []),
        *trimmed.get("pending", []),
        *qdrant_warning,
        *footer,
    ]
    _result = "\n".join(lines)
    _core_len = _section_chars(core_lines)
    _recall_len = _section_chars(trimmed.get("recall", []))
    _behavior_len = _section_chars(trimmed.get("behavior", []))
    _archival_len = _section_chars(trimmed.get("archival", []))
    _n_segments = len(memory.audience_block.segments)
    _l1_len = len(memory.working_summary or "")
    _l2_count = len(memory.session_summaries)
    _l3_len = len(memory.long_term_summary or "")
    _used = len(_result)
    _pct = round(_used / _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET * 100, 1)
    logger.info(
        "[CONTEXT] 📝 Sections: core=%d, recall=%d, behavior=%d, archival=%d, audience_segments=%d",
        _core_len, _recall_len, _behavior_len, _archival_len, _n_segments,
    )
    logger.info("[CONTEXT] 📝 L1=%dchars, L2=%dsessions, L3=%dchars", _l1_len, _l2_count, _l3_len)
    logger.info("[CONTEXT] 📝 Budget: %d/%d chars (%s%%)", _used, _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET, _pct)
    logger.info(
        "[CONTEXT] 🟢 Context block ready | total=%d chars, time=%dms",
        _used, int((time.time() - _t0_ctx) * 1000),
    )
    return _result
