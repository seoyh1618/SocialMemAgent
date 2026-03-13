"""
MemGPT-style memory tools for SocialMediaBrandingAgent.

Architecture mirrors MemGPT's three-tier memory system:
  ┌──────────────────────────────────────────────────────────┐
  │  CORE MEMORY  (always in-context)                        │
  │   • UserProfile   → "Human Block"                        │
  │   • BrandVoice    → "Persona Block" (brand identity)     │
  ├──────────────────────────────────────────────────────────┤
  │  ARCHIVAL MEMORY  (vector semantic search)               │
  │   • CampaignRecord list → past campaigns, lessons        │
  │   • CampaignEmbedding  → cached Vertex AI embedding      │
  │   Retrieval: cosine similarity via text-embedding-004    │
  ├──────────────────────────────────────────────────────────┤
  │  RECALL MEMORY  (rolling conversation history)           │
  │   • recall_log      → last 20 turns verbatim             │
  │   • working_summary → condensed older turns              │
  └──────────────────────────────────────────────────────────┘

Storage layer: ADK ToolContext / session state (SQLite via ADK).
All tools are pure Python callables compatible with google.adk.tools.
"""

import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from google.adk.tools import ToolContext

from .schemas import (
    AudienceBehaviorGraph,
    BrandVoice,
    CampaignEmbedding,
    CampaignRecord,
    ContentNode,
    ConversationEmbedding,
    ConversationRecord,
    DomainProfileBlock,
    GeneratedAsset,
    MemoryState,
    PerformanceData,
    PerformanceEdge,
    PerformancePendingRequest,
    RecallEntry,
    UserProfile,
)

logger = logging.getLogger(__name__)

# ─── Embedding client (lazy init) ────────────────────────────────────────────
# Uses Vertex AI text-embedding-004 — already available via google-adk dependency.
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
_WORKING_SUMMARY_MAX = 800  # Max chars for working_summary (increased from 600 for better retention)
_SUMMARY_PREV_KEEP = 300    # How many chars of previous summary to retain when merging


def _estimate_tokens(text: str) -> int:
    """Estimate token count using ~4 chars per token heuristic."""
    return max(1, len(text) // 4)


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

def _compact_recall_to_summary(memory: "MemoryState") -> None:
    """
    [MemGPT: Recall Memory 압축 — 단일 헬퍼]
    recall_log가 _RECALL_SUMMARISE_AT을 초과할 때만 동작.
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
    if total_tokens <= _RECALL_SUMMARISE_TOKEN_THRESHOLD:
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
    overflow_text = f"[{date_range}] " + "\n".join(overflow_lines)

    prev = memory.working_summary or ""

    # ── [LLM Compression] Gemini API 호출로 의미론적 요약 생성 ──────────────
    try:
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

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        llm_summary = response.text.strip() if response.text else ""

        if llm_summary:
            memory.working_summary = llm_summary[:_WORKING_SUMMARY_MAX]
            _logger.info(
                "Recall compacted via LLM: %d entries → working_summary (%d chars)",
                len(overflow),
                len(memory.working_summary),
            )
            return

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


def _embed(text: str) -> List[float]:
    """Return embedding vector for text using Vertex AI text-embedding-004."""
    client = _get_embed_client()
    result = client.models.embed_content(
        model=_EMBED_MODEL,
        contents=text,
    )
    # EmbedContentResponse → embeddings[0].values
    return result.embeddings[0].values


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── Vertex AI Vector Search (Matching Engine) ───────────────────────────────
#
# 환경변수:
#   VECTOR_SEARCH_INDEX_ENDPOINT  — 인덱스 엔드포인트 리소스 이름
#   VECTOR_SEARCH_DEPLOYED_INDEX  — 배포된 인덱스 ID
#   GOOGLE_CLOUD_PROJECT          — GCP 프로젝트 ID
#   GOOGLE_CLOUD_LOCATION         — 리전 (기본: us-central1)
#
# 미설정 시 로컬 SQLite 임베딩 캐시(기존 방식)로 자동 폴백.
# 이를 통해 로컬 개발과 프로덕션 모두 동일한 코드로 동작.

_vs_client = None
_VS_ENDPOINT = None
_VS_DEPLOYED_INDEX = None
_VS_AVAILABLE = None  # None = 아직 확인 안 함, True/False = 확인 완료


def _check_vector_search_available() -> bool:
    """Vector Search 사용 가능 여부를 캐시해 반환."""
    global _VS_AVAILABLE, _VS_ENDPOINT, _VS_DEPLOYED_INDEX, _vs_client
    if _VS_AVAILABLE is not None:
        return _VS_AVAILABLE

    endpoint = os.getenv("VECTOR_SEARCH_INDEX_ENDPOINT", "")
    deployed = os.getenv("VECTOR_SEARCH_DEPLOYED_INDEX", "")
    if not endpoint or not deployed:
        logger.info("Vertex AI Vector Search not configured — using local embedding cache.")
        _VS_AVAILABLE = False
        return False

    try:
        from google.cloud import aiplatform
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        aiplatform.init(project=project, location=location)
        _vs_client = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=endpoint)
        _VS_ENDPOINT = endpoint
        _VS_DEPLOYED_INDEX = deployed
        _VS_AVAILABLE = True
        logger.info("Vertex AI Vector Search connected: endpoint=%s, index=%s", endpoint, deployed)
    except Exception as e:
        logger.warning("Vertex AI Vector Search init failed: %s — using local cache.", e)
        _VS_AVAILABLE = False

    return _VS_AVAILABLE


def _vs_upsert(datapoint_id: str, embedding: List[float]) -> bool:
    """
    Vector Search 인덱스에 임베딩을 upsert.
    실패 시 False 반환 (호출자가 로컬 캐시로 폴백).
    """
    if not _check_vector_search_available():
        return False
    try:
        from google.cloud.aiplatform_v1.types import index as index_v1
        datapoint = index_v1.IndexDatapoint(
            datapoint_id=datapoint_id,
            feature_vector=embedding,
        )
        _vs_client._index.upsert_datapoints(datapoints=[datapoint])
        return True
    except Exception as e:
        logger.warning("Vector Search upsert failed for '%s': %s", datapoint_id, e)
        return False


def _vs_query(
    query_vec: List[float],
    top_k: int = 10,
    namespace: str = "",
) -> List[tuple[str, float]]:
    """
    Vector Search에서 ANN 검색 수행.
    Returns list of (datapoint_id, distance) sorted by relevance.
    실패 시 빈 리스트 반환 → 호출자가 로컬 폴백 사용.
    namespace 접두사로 campaign_ / conv_ 구분.
    """
    if not _check_vector_search_available():
        return []
    try:
        response = _vs_client.find_neighbors(
            deployed_index_id=_VS_DEPLOYED_INDEX,
            queries=[query_vec],
            num_neighbors=top_k,
        )
        results = []
        for neighbor in response[0]:
            dp_id = neighbor.id
            # namespace 필터 (접두사 기반)
            if namespace and not dp_id.startswith(namespace):
                continue
            # distance → similarity (cosine index의 경우 distance = 1 - cosine_sim)
            similarity = 1.0 - neighbor.distance
            results.append((dp_id, similarity))
        return results
    except Exception as e:
        logger.warning("Vector Search query failed: %s — using local fallback.", e)
        return []


_MEMORY_KEY = "memory"


# ─── Private helpers ─────────────────────────────────────────────────────────

def _load_memory(tool_context: ToolContext) -> MemoryState:
    """Load MemoryState from ADK session state. Creates a fresh one if absent."""
    raw = tool_context.state.get(_MEMORY_KEY)
    if raw is None:
        return MemoryState()
    if isinstance(raw, dict):
        return MemoryState.model_validate(raw)
    return MemoryState.model_validate_json(raw)


def _save_memory(tool_context: ToolContext, memory: MemoryState) -> None:
    """Persist MemoryState back into ADK session state."""
    memory.last_updated = datetime.now(timezone.utc).isoformat()
    tool_context.state[_MEMORY_KEY] = memory.model_dump(mode="json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Core Memory Tools (Human / Persona Block) ───────────────────────────────

def memory_get_core_profile(tool_context: ToolContext) -> str:
    """
    [MemGPT: Core Memory READ]
    Retrieve the user's persistent profile (Human Block) and brand voice (Persona Block).
    Always call this at the start of a session to personalize content generation.

    Returns:
        JSON string with UserProfile and BrandVoice data.
    """
    memory = _load_memory(tool_context)
    profile = memory.core_profile

    result = {
        "display_name": profile.display_name,
        "twitter_handle": profile.twitter_handle,
        "instagram_handle": profile.instagram_handle,
        "industry": profile.industry,
        "target_platforms": profile.target_platforms,
        "brand_voice": {
            "tone": profile.brand_voice.tone,
            "preferred_styles": profile.brand_voice.preferred_styles,
            "avoid_topics": profile.brand_voice.avoid_topics,
            "signature_hashtags": profile.brand_voice.signature_hashtags,
            "content_pillars": profile.brand_voice.content_pillars,
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
    [MemGPT: Core Memory WRITE — Human Block]
    Update the user's persistent identity profile.
    Call this when the user shares new information about themselves or their brand.

    Args:
        display_name: Brand or person name (e.g., 'Acme Co').
        twitter_handle: Twitter/X handle (e.g., '@acme').
        instagram_handle: Instagram handle (e.g., '@acme_official').
        industry: Business vertical (e.g., 'SaaS', 'Fashion').
        target_platforms: List of active platforms (e.g., ['twitter', 'instagram']).
        extra_fields: Dict of arbitrary key-value pairs to MERGE into extra_fields
            (e.g., {'location': 'Seoul', 'employee_count': '50', 'founded_year': '2021'}).
            New keys are added; existing keys are updated. Pass only the keys to change.

    Returns:
        Confirmation message with updated fields.
    """
    memory = _load_memory(tool_context)
    profile = memory.core_profile
    updated_fields = []

    if display_name is not None:
        profile.display_name = display_name
        updated_fields.append("display_name")
    if twitter_handle is not None:
        profile.twitter_handle = twitter_handle
        updated_fields.append("twitter_handle")
    if instagram_handle is not None:
        profile.instagram_handle = instagram_handle
        updated_fields.append("instagram_handle")
    if industry is not None:
        profile.industry = industry
        updated_fields.append("industry")
    if target_platforms is not None:
        profile.target_platforms = target_platforms
        updated_fields.append("target_platforms")
    if extra_fields is not None:
        # Merge — don't replace the whole dict
        profile.extra_fields = {**profile.extra_fields, **{str(k): str(v) for k, v in extra_fields.items()}}
        updated_fields.append(f"extra_fields({list(extra_fields.keys())})")

    memory.core_profile = profile
    _save_memory(tool_context, memory)

    return f"[Memory Updated] Human Block fields updated: {', '.join(updated_fields)}"


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
    voice = memory.core_profile.brand_voice
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

    memory.core_profile.brand_voice = voice
    _save_memory(tool_context, memory)

    return f"[Memory Updated] Persona Block (brand voice) updated: {'; '.join(updated_fields)}"


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
    domain_extra: Optional[dict] = None,
) -> str:
    """
    [Domain Profile Block WRITE]
    Update the domain-specific business profile block.
    Call this when the user reveals business details: location, price range, operating hours,
    USP, competitors, seasonal patterns, or offline channels.

    Args:
        domain_type: Business type — 'restaurant', 'cafe', 'fashion', 'fitness', 'beauty',
                     'retail', 'education', 'saas', 'other'
        business_location: Physical location for local targeting (e.g., '서울 강남구')
        operating_hours: Operating hours (e.g., '10:00-22:00 Mon-Sat')
        price_range: Consumer segment indicator (e.g., '₩₩', 'premium', 'budget-friendly')
        offline_channels: Offline channels list (e.g., ['매장', '배달앱', '팝업스토어'])
        seasonal_peaks: Key seasons/dates (e.g., ['크리스마스', '여름 성수기'])
        usp: Unique selling point — core differentiator
        competitors: Main competitor brands/businesses
        target_age_range: Primary target age (e.g., '20-35')
        domain_extra: Any other domain-specific key-value pairs

    Returns:
        Confirmation of updated fields.
    """
    memory = _load_memory(tool_context)
    dp = memory.core_profile.domain_profile
    updated = []

    if domain_type is not None:
        dp.domain_type = domain_type; updated.append("domain_type")
    if business_location is not None:
        dp.business_location = business_location; updated.append("business_location")
    if operating_hours is not None:
        dp.operating_hours = operating_hours; updated.append("operating_hours")
    if price_range is not None:
        dp.price_range = price_range; updated.append("price_range")
    if offline_channels is not None:
        dp.offline_channels = offline_channels; updated.append("offline_channels")
    if seasonal_peaks is not None:
        dp.seasonal_peaks = seasonal_peaks; updated.append("seasonal_peaks")
    if usp is not None:
        dp.usp = usp; updated.append("usp")
    if competitors is not None:
        dp.competitors = competitors; updated.append("competitors")
    if target_age_range is not None:
        dp.target_age_range = target_age_range; updated.append("target_age_range")
    if domain_extra is not None:
        dp.domain_extra.update(domain_extra); updated.append("domain_extra")

    _save_memory(tool_context, memory)
    return f"[Domain Profile Updated] Fields: {', '.join(updated)}"


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
    memory = _load_memory(tool_context)

    # ── Update CampaignRecord ─────────────────────────────────────────────
    target_record = None
    for record in memory.campaign_archive:
        if record.campaign_id == campaign_id:
            target_record = record
            break

    if target_record is None:
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

            # Add edge
            graph.edges.append(PerformanceEdge(
                edge_id=f"{campaign_id}_{platform}",
                node_id=node_id,
                campaign_id=campaign_id,
                engagement_level=engagement_level,
                reach_level=reach_level,
                what_worked=what_worked or [],
                what_failed=what_failed or [],
                timestamp=_now_iso(),
            ))

    # ── Recompute graph aggregates ────────────────────────────────────────
    _recompute_graph_insights(graph)
    graph.last_updated = _now_iso()

    _save_memory(tool_context, memory)
    return (
        f"[Performance Recorded] Campaign '{campaign_id}': "
        f"engagement={engagement_level}, best_platform={best_platform or 'N/A'}. "
        f"Behavior graph updated."
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
    """Concatenate all searchable fields of a campaign into a single string for embedding."""
    parts = [
        record.goal,
        record.selected_trend,
        record.guideline_summary,
        record.performance_notes,
        " ".join(record.target_audiences),
        " ".join(record.selected_styles),
        " ".join(record.platforms_used),
    ]
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

    # Generate embedding and upsert to Vector Search (fallback: local cache)
    try:
        embed_text = _campaign_to_embed_text(record)
        vector = _embed(embed_text)
        if vector:
            vs_id = f"campaign_{record.campaign_id}"
            if not _vs_upsert(vs_id, vector):
                # Vector Search unavailable → local cache fallback (cap at 200)
                memory.campaign_embeddings.append(
                    CampaignEmbedding(campaign_id=record.campaign_id, vector=vector)
                )
                if len(memory.campaign_embeddings) > 200:
                    memory.campaign_embeddings = memory.campaign_embeddings[-200:]
            logger.info("Campaign embedding stored: %s (%d dims)", record.campaign_id, len(vector))
    except Exception as e:
        logger.warning("Failed to embed campaign '%s': %s. Keyword fallback active.", record.campaign_id, e)

    # Unlimited campaign archive — no cap (Vector Search handles retrieval at scale)
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

    memory.total_campaigns += 1
    _save_memory(tool_context, memory)

    return f"[Memory Archived] Campaign '{record.campaign_id}' saved. Total campaigns: {memory.total_campaigns}"


def memory_search_campaigns(
    tool_context: ToolContext,
    query: str,
    limit: int = 5,
) -> str:
    """
    [MemGPT: Archival Memory READ — Semantic Search]
    Search past campaigns using Vertex AI embedding similarity (text-embedding-004).
    Language-agnostic: Korean query finds English-stored campaigns and vice versa.
    Falls back to keyword search if embeddings are unavailable.

    Use this to leverage past successes, avoid repeated mistakes, and maintain brand consistency.

    Args:
        query: Natural language search query (any language).
               e.g., 'SaaS 제품 런칭', 'fitness video campaign', '인스타그램 패션 홍보'
        limit: Maximum number of results to return (default 5).

    Returns:
        JSON list of matching campaign records sorted by semantic relevance.
    """
    memory = _load_memory(tool_context)

    if not memory.campaign_archive:
        return json.dumps({"message": "No campaigns in archive yet.", "results": []})

    archive_map = {r.campaign_id: r for r in memory.campaign_archive}
    scored: List[tuple[float, CampaignRecord]] = []

    # ── Path 1: Vertex AI Vector Search (ANN, unlimited scale) ────────────
    try:
        query_vec = _embed(query)
        vs_results = _vs_query(query_vec, top_k=limit * 2, namespace="campaign_")
        if vs_results:
            for vs_id, sim in vs_results:
                cid = vs_id.replace("campaign_", "", 1)
                record = archive_map.get(cid)
                if record:
                    scored.append((sim, record))
            logger.info("Vector Search campaign query '%s': %d hits", query, len(scored))
    except Exception as e:
        logger.warning("Vector Search campaign query failed: %s", e)

    # ── Path 2: Local embedding cache (cosine similarity) ─────────────────
    if not scored:
        embed_map = {e.campaign_id: e.vector for e in memory.campaign_embeddings}
        if embed_map:
            try:
                if 'query_vec' not in dir():
                    query_vec = _embed(query)
                for record in memory.campaign_archive:
                    vec = embed_map.get(record.campaign_id)
                    if vec:
                        score = _cosine_similarity(query_vec, vec)
                    else:
                        try:
                            vec = _embed(_campaign_to_embed_text(record))
                            score = _cosine_similarity(query_vec, vec)
                        except Exception:
                            score = 0.0
                    scored.append((score, record))
                scored.sort(key=lambda x: x[0], reverse=True)
                logger.info("Local cosine search for '%s': top score=%.3f", query, scored[0][0] if scored else 0)
            except Exception as e:
                logger.warning("Local embedding search failed: %s. Keyword fallback.", e)
                scored = []

    # ── Path 3: Keyword fallback ───────────────────────────────────────────
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

    if not matches:
        return json.dumps({"message": "No relevant past campaigns found.", "results": []})

    return json.dumps({"results": matches, "count": len(matches)}, ensure_ascii=False)


def memory_get_recent_campaigns(tool_context: ToolContext, limit: int) -> str:
    """
    [MemGPT: Recall Memory READ]
    Retrieve the most recent campaigns to understand recent content patterns.
    Use this at session start to provide continuity from the last interaction.

    Args:
        limit: Number of recent campaigns to retrieve (default 3).

    Returns:
        JSON list of the most recent campaign records.
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
            vs_id = f"conv_{record.conversation_id}"
            if not _vs_upsert(vs_id, vector):
                # Fallback: local cache (cap at 200)
                memory.conversation_embeddings.append(
                    ConversationEmbedding(conversation_id=record.conversation_id, vector=vector)
                )
                if len(memory.conversation_embeddings) > 200:
                    memory.conversation_embeddings = memory.conversation_embeddings[-200:]
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

    # ── Path 1: Vertex AI Vector Search ───────────────────────────────────
    try:
        query_vec = _embed(query)
        vs_results = _vs_query(query_vec, top_k=top_k * 2, namespace="conv_")
        if vs_results:
            for vs_id, sim in vs_results:
                cid = vs_id.replace("conv_", "", 1)
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
                search_type = "vector_search"
                logger.info("Vector Search conv query '%s': %d hits", query, len(results))
                return json.dumps({"conversations": results[:top_k], "search_type": search_type}, ensure_ascii=False)
    except Exception as e:
        logger.warning("Vector Search conversation query failed: %s", e)

    # ── Path 2: Local embedding cosine similarity ──────────────────────────
    if not results and memory.conversation_embeddings:
        try:
            if 'query_vec' not in locals():
                query_vec = _embed(query)
            emb_map = {e.conversation_id: e.vector for e in memory.conversation_embeddings}
            scored = []
            for record in memory.conversation_archive:
                vec = emb_map.get(record.conversation_id)
                if vec:
                    scored.append((_cosine_similarity(query_vec, vec), record))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [
                {
                    "conversation_id": r.conversation_id,
                    "timestamp": r.timestamp,
                    "role": r.role,
                    "content": r.content,
                    "session_id": r.session_id,
                    "summary": r.summary,
                    "score": round(score, 4),
                }
                for score, r in scored[:top_k]
                if score > 0.1
            ]
            if results:
                search_type = "local_cosine"
                logger.info("Local cosine conv search '%s': %d hits", query, len(results))
                return json.dumps({"conversations": results, "search_type": search_type}, ensure_ascii=False)
        except Exception as e:
            logger.warning("Local conv embedding search failed: %s.", e)

    # ── Path 3: Keyword fallback ───────────────────────────────────────────
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
            "created_at": a.created_at,
            "session_id": a.session_id,
            "local_filename": a.local_filename,
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


# ─── Context Injection Helper (used by prompt.py) ────────────────────────────

def semantic_search_campaigns_inline(
    memory: MemoryState,
    query: str,
    limit: int = 3,
) -> List[dict]:
    """
    Internal semantic search used by before_agent_callback (no ToolContext needed).
    Returns a list of dicts sorted by cosine similarity. Falls back to keyword search.
    """
    if not memory.campaign_archive:
        return []

    embed_map = {e.campaign_id: e.vector for e in memory.campaign_embeddings}
    scored: List[tuple[float, CampaignRecord]] = []

    if embed_map:
        try:
            query_vec = _embed(query)
            for record in memory.campaign_archive:
                vec = embed_map.get(record.campaign_id, [])
                score = _cosine_similarity(query_vec, vec) if vec else 0.0
                scored.append((score, record))
            scored.sort(key=lambda x: x[0], reverse=True)
        except Exception as e:
            logger.warning("Inline semantic search failed: %s — using keyword fallback", e)
            scored = []

    if not scored:
        query_lower = query.lower()
        for record in reversed(memory.campaign_archive):
            searchable = _campaign_to_embed_text(record).lower()
            if any(kw in searchable for kw in query_lower.split()):
                scored.append((1.0, record))

    return [
        {
            "campaign_id": r.campaign_id,
            "goal": r.goal,
            "trend": r.selected_trend,
            "guideline_summary": r.guideline_summary,
            "platforms": r.platforms_used,
            "performance_notes": r.performance_notes,
            "relevance_score": round(score, 3),
        }
        for score, r in scored[:limit]
        if score > 0.1
    ]


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
    profile = memory.core_profile
    voice = profile.brand_voice
    dp = profile.domain_profile

    # ── Legacy extra_fields (backward compat) ─────────────────────────
    extra_lines = [
        f"  {k.replace('_', ' ').title():<12}: {v}"
        for k, v in (profile.extra_fields or {}).items()
    ]

    # ── Domain Profile Block ──────────────────────────────────────────
    domain_lines = []
    if dp.domain_type:
        domain_lines.append(f"  Domain Type  : {dp.domain_type}")
    if dp.business_location:
        domain_lines.append(f"  Location     : {dp.business_location}")
    if dp.target_age_range:
        domain_lines.append(f"  Target Age   : {dp.target_age_range}")
    if dp.price_range:
        domain_lines.append(f"  Price Range  : {dp.price_range}")
    if dp.usp:
        domain_lines.append(f"  USP          : {dp.usp}")
    if dp.competitors:
        domain_lines.append(f"  Competitors  : {', '.join(dp.competitors)}")
    if dp.offline_channels:
        domain_lines.append(f"  Offline Ch.  : {', '.join(dp.offline_channels)}")
    if dp.seasonal_peaks:
        domain_lines.append(f"  Seasonal     : {', '.join(dp.seasonal_peaks)}")
    if dp.operating_hours:
        domain_lines.append(f"  Hours        : {dp.operating_hours}")
    for k, v in (dp.domain_extra or {}).items():
        domain_lines.append(f"  {k.replace('_',' ').title():<12}: {v}")
    if not domain_lines:
        domain_lines = ["  (not configured — use memory_update_domain_profile to fill)"]

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

    # ── Archival hint: top relevant campaigns with performance ────────
    archival_lines = []
    if user_query and memory.campaign_archive:
        try:
            top = semantic_search_campaigns_inline(memory, user_query, limit=3)
            for c in top:
                perf_str = ""
                if c.get("performance"):
                    p = c["performance"]
                    perf_str = f" | 성과: {p.get('engagement_level','?')} | 잘된점: {', '.join(p.get('what_worked',[])[:2])}"
                archival_lines.append(
                    f"  [{c['campaign_id']}] {c['goal'][:70]} "
                    f"(score:{c['relevance_score']}){perf_str}"
                )
        except Exception:
            pass
    if not archival_lines:
        archival_lines = ["  (use memory_search_campaigns tool for deeper search)"]

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

    # ── Performance pending (session-start trigger) ───────────────────
    pending = [p for p in memory.performance_pending if p.ask_count < 2]
    pending_lines = []
    if pending:
        pending_lines.append(f"  ⚠ 성과 확인 대기: {len(pending)}개 캠페인")
        for p in pending[:3]:
            pending_lines.append(f"    - [{p.campaign_id}] {p.campaign_goal[:50]} ({', '.join(p.platforms)})")
        pending_lines.append("  → 세션 시작 시 memory_get_performance_pending으로 확인 후 유저에게 자연스럽게 질문")

    lines = [
        "════════════════════════════════════════",
        "  PERSISTENT USER MEMORY  [MemGPT Core]",
        "════════════════════════════════════════",
        "",
        "▶ HUMAN BLOCK (User Identity)",
        f"  Name        : {profile.display_name or '(not set)'}",
        f"  Industry    : {profile.industry or '(not set)'}",
        f"  Twitter     : {profile.twitter_handle or '(not set)'}",
        f"  Instagram   : {profile.instagram_handle or '(not set)'}",
        f"  Platforms   : {', '.join(profile.target_platforms) if profile.target_platforms else '(not set)'}",
        *extra_lines,
        "",
        "▶ DOMAIN PROFILE BLOCK (Business Details)",
        *domain_lines,
        "",
        "▶ PERSONA BLOCK (Brand Voice)",
        f"  Tone        : {voice.tone or '(not defined yet)'}",
        f"  Styles      : {', '.join(voice.preferred_styles) if voice.preferred_styles else '(none)'}",
        f"  Pillars     : {', '.join(voice.content_pillars) if voice.content_pillars else '(none)'}",
        f"  Hashtags    : {', '.join(voice.signature_hashtags) if voice.signature_hashtags else '(none)'}",
        f"  Avoid       : {', '.join(voice.avoid_topics) if voice.avoid_topics else '(none)'}",
        "",
        "▶ AUDIENCE BEHAVIOR GRAPH (Performance Insights)",
        *behavior_lines,
        "",
        "▶ PERFORMANCE TREND ANALYSIS (Campaign-Level Insights)",
        *perf_trend_lines,
        "",
        "▶ RECALL MEMORY (Recent Conversation — last 5 turns)",
        *recall_lines,
        f"  [Older turns summary]: {memory.working_summary if memory.working_summary else '(none)'}",
        "",
        "▶ ARCHIVAL HINT (Semantically similar past campaigns + performance)",
        *archival_lines,
        "",
        f"  Total campaigns: {memory.total_campaigns}",
        *(["", "▶ PERFORMANCE COLLECTION QUEUE", *pending_lines] if pending_lines else []),
        "════════════════════════════════════════",
    ]
    return "\n".join(lines)
