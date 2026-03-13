from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

T = TypeVar("T")


class EnabledField(BaseModel, Generic[T]):
    """A value that can be toggled on/off."""
    value: T
    enabled: bool = Field(default=True, description="Whether the field is enabled. If disabled, the value will be ignored.")


class AudienceGroup(BaseModel):
    name: str = Field(description="The name of the audience group. For example, 'Teens (13-17)'")
    targeted: bool = Field(default=False, description="Whether the audience group is targeted. If targeted, we want the generated content to be tailored to this audience group.")


class Trend(BaseModel):
    selected_trend: str = Field(description="The selected trend. For example, 'AI'")
    trending: List[str] = Field(description="The trending topics. For example, ['AI', 'Wine & Fruits Fair', 'WWDC2025']")


class Style(BaseModel):
    name: str = Field(description="The name of the style. For example, 'Vintage / Retro'")
    selected: bool = Field(default=False, description="Whether the style is selected. If selected, we want the generated content to be in this style.")


class ImagePost(BaseModel):
    image_url: HttpUrl = Field(description="The URL of the image post. Get this URL from the image generation tool.")
    post_text: str = Field(description="The content text of the image post.")

class VideoPost(BaseModel):
    video_url: HttpUrl = Field(description="The URL of the video post. Get this URL from the video generation tool.")
    title: str = Field(description="The title of the video post (e.g. YouTube video title).")
    description: str = Field(description="A short description of the video post (e.g. YouTube video description).")


class Base(BaseModel):
    # ── 1. Goal ────────────────────────────────────────────
    goal: str = Field(description="The goal of the content. For example, 'Promote a new SaaS product.'")

    # ── 2. Context ────────────────────────────────────────
    trends: EnabledField[Trend]
    audiences: EnabledField[List[AudienceGroup]]
    styles: EnabledField[List[Style]]

    # ── 3. Intermediate artifacts ─────────────────────────
    guideline: EnabledField[str]
    image_prompt: EnabledField[str]
    video_prompt: EnabledField[str]
    video_narration: EnabledField[str]

    # ── 4. Final artifacts ────────────────────────────────
    twitter_post: EnabledField[str]
    youtube_post: EnabledField[VideoPost]
    tiktok_post: EnabledField[VideoPost]
    instagram_post: EnabledField[ImagePost]

    model_config = {
        "populate_by_name": True,          # allows alias use if you add them later
        "frozen": False,                   # set True if you need immutability
        "extra": "forbid",                 # no undeclared fields ignore
    }

class SocialMediaAgentInput(BaseModel):
    user_query: str = Field(description="The user's query. The user may ask you to modify the content of the base. Or they may ask you generate the social media post content.")
    base: Base = Field(description="The base of the content. This is the content that you will be modifying or generating.")


class SocialMediaAgentOutput(BaseModel):
    agent_response: str = Field(description="This will be the response to the user's query.")
    is_updated: bool = Field(description="Whether the base is updated. If nothing was changed, this will be False.")
    updated_base: Base = Field(description="The base of the content. This is the content that you will be modifying or generating.")


# ─── MemGPT Memory Schemas ────────────────────────────────────────────────────

class BrandVoice(BaseModel):
    """MemGPT Core Memory: Persona Block — brand identity permanently loaded into context."""
    tone: str = Field(
        default="",
        description="Brand tone (e.g., 'casual and witty', 'professional and authoritative')"
    )
    preferred_styles: List[str] = Field(
        default_factory=list,
        description="User's preferred visual/content styles, e.g. ['Minimalist', 'Vibrant']"
    )
    avoid_topics: List[str] = Field(
        default_factory=list,
        description="Topics or themes the brand explicitly avoids."
    )
    signature_hashtags: List[str] = Field(
        default_factory=list,
        description="Recurring hashtags that represent the brand."
    )
    content_pillars: List[str] = Field(
        default_factory=list,
        description="Core content themes (e.g., 'Education', 'Behind-the-scenes', 'Product demos')"
    )


class DomainProfileBlock(BaseModel):
    """
    Domain Profile Block — 소상공인 서비스 도메인별 특화 정보.
    MemGPT Human Block과 병합하여 사용 (extra_fields 대체/보완).
    도메인 유형(restaurant, fashion, fitness, beauty, cafe, retail 등)에 따라
    콘텐츠 전략이 달라지므로 구조화된 필드로 관리.
    """
    domain_type: str = Field(
        default="",
        description="Service domain type: 'restaurant', 'cafe', 'fashion', 'fitness', 'beauty', 'retail', 'education', 'saas', 'other'"
    )
    business_location: str = Field(
        default="",
        description="Business location for local targeting (e.g., '서울 강남구', 'Seoul Gangnam')"
    )
    operating_hours: str = Field(
        default="",
        description="Operating hours — relevant for restaurants, cafes, retail (e.g., '10:00-22:00 Mon-Sat')"
    )
    price_range: str = Field(
        default="",
        description="Price range indicating consumer segment (e.g., '₩₩', 'premium', 'budget-friendly')"
    )
    offline_channels: List[str] = Field(
        default_factory=list,
        description="Offline sales/presence channels (e.g., ['매장', '배달', '팝업스토어'])"
    )
    seasonal_peaks: List[str] = Field(
        default_factory=list,
        description="Peak seasons or key dates (e.g., ['크리스마스', '발렌타인데이', '여름 성수기'])"
    )
    usp: str = Field(
        default="",
        description="Unique Selling Point — core differentiator from competitors"
    )
    competitors: List[str] = Field(
        default_factory=list,
        description="Main competitor brands or businesses"
    )
    target_age_range: str = Field(
        default="",
        description="Primary target age range (e.g., '20-35', '30-50')"
    )
    domain_extra: dict = Field(
        default_factory=dict,
        description="Additional domain-specific fields not covered above (snake_case keys, string values)"
    )


class UserProfile(BaseModel):
    """MemGPT Core Memory: Human Block + Domain Profile Block — merged persistent user identity."""
    display_name: str = Field(default="", description="User's display name or brand name.")
    twitter_handle: Optional[str] = Field(default=None, description="Twitter/X handle (e.g., '@mybrand')")
    instagram_handle: Optional[str] = Field(default=None, description="Instagram handle.")
    industry: str = Field(default="", description="User's industry or niche (e.g., 'SaaS', 'Fashion', 'Fitness').")
    target_platforms: List[str] = Field(
        default_factory=list,
        description="Platforms user primarily posts on. e.g. ['twitter', 'instagram']"
    )
    brand_voice: BrandVoice = Field(
        default_factory=BrandVoice,
        description="Persistent brand voice profile (Persona Block)."
    )
    domain_profile: DomainProfileBlock = Field(
        default_factory=DomainProfileBlock,
        description="Domain-specific business profile block — replaces unstructured extra_fields."
    )
    extra_fields: dict = Field(
        default_factory=dict,
        description=(
            "Legacy dynamic key-value store. Preserved for backward compatibility. "
            "New data should use domain_profile fields instead. "
            "Keys are short snake_case labels; values are always strings."
        )
    )


# ─── Performance & Behavior Graph Schemas ─────────────────────────────────────

class PerformanceData(BaseModel):
    """
    구조화된 캠페인 성과 데이터 — 자유형 텍스트(performance_notes) 보완.
    사용자 입력 기반으로 업데이트 (정량 지표 수집 주기 트리거).
    """
    engagement_level: str = Field(
        default="",
        description="Overall engagement level: 'low', 'medium', 'high', 'viral'"
    )
    reach_level: str = Field(
        default="",
        description="Reach/impression level: 'low', 'medium', 'high'"
    )
    conversion_level: str = Field(
        default="",
        description="Conversion/action rate: 'low', 'medium', 'high'"
    )
    best_platform: str = Field(
        default="",
        description="Platform that performed best in this campaign"
    )
    what_worked: List[str] = Field(
        default_factory=list,
        description="Content elements that worked well (e.g., ['짧은 영상', '밝은 색감', '유머'])"
    )
    what_failed: List[str] = Field(
        default_factory=list,
        description="Elements that underperformed (e.g., ['긴 텍스트', '전문 용어'])"
    )
    collected_at: str = Field(
        default="",
        description="ISO-8601 timestamp when performance data was collected"
    )
    # Numeric performance metrics (user-input raw counts)
    views: int = Field(default=0, description="Total view count")
    clicks: int = Field(default=0, description="Total click count")
    impressions: int = Field(default=0, description="Total impression count")
    likes: int = Field(default=0, description="Total likes/reactions count")
    shares: int = Field(default=0, description="Total shares/reposts count")
    comments: int = Field(default=0, description="Total comments count")


class PerformancePendingRequest(BaseModel):
    """
    성과 수집 대기 요청 — 에이전트가 다음 세션 시작 시 또는 주기적으로 유저에게 물어볼 캠페인 목록.
    """
    campaign_id: str = Field(description="Campaign ID to ask performance about")
    campaign_goal: str = Field(default="", description="Short goal description for context in the question")
    platforms: List[str] = Field(default_factory=list, description="Platforms used in this campaign")
    created_at: str = Field(description="When this request was created")
    asked_at: str = Field(default="", description="When the agent last asked — empty if not yet asked")
    ask_count: int = Field(default=0, description="How many times we've asked (stop after 2)")


class ContentNode(BaseModel):
    """
    Audience Behavior Graph — 콘텐츠 노드.
    플랫폼 × 콘텐츠 타입 × 주제(content_pillar) 조합을 노드로 표현.
    """
    node_id: str = Field(description="Unique node identifier")
    platform: str = Field(description="Platform: 'instagram', 'tiktok', 'twitter', 'youtube'")
    content_type: str = Field(description="Content type: 'image', 'video', 'text', 'carousel'")
    topic: str = Field(description="Content topic / pillar (maps to brand_voice.content_pillars)")


class PerformanceEdge(BaseModel):
    """
    Audience Behavior Graph — 집계 성과 엣지.
    ContentNode → 집계된 사용자 반응 데이터 연결.
    소상공인 환경 특성상 개별 유저 식별 불가 → Audience-level 집계.
    """
    edge_id: str = Field(description="Unique edge identifier")
    node_id: str = Field(description="References ContentNode.node_id")
    campaign_id: str = Field(description="References CampaignRecord.campaign_id")
    engagement_level: str = Field(default="", description="'low'/'medium'/'high'/'viral'")
    reach_level: str = Field(default="", description="'low'/'medium'/'high'")
    what_worked: List[str] = Field(default_factory=list)
    what_failed: List[str] = Field(default_factory=list)
    timestamp: str = Field(description="ISO-8601 timestamp of this observation")


class AudienceBehaviorGraph(BaseModel):
    """
    Audience-level User Behavior Graph.
    콘텐츠-채널-주제 간 관계와 집계된 사용자 행동 데이터 기반.
    전체 사용자 집단의 선호 패턴 분석에 사용.
    """
    nodes: List[ContentNode] = Field(default_factory=list)
    edges: List[PerformanceEdge] = Field(default_factory=list)
    # 집계 인사이트 — build_memory_context_block에서 직접 주입
    platform_best_content_type: dict = Field(
        default_factory=dict,
        description="Per-platform best content type: {'instagram': 'image', 'tiktok': 'video'}"
    )
    topic_performance_summary: dict = Field(
        default_factory=dict,
        description="Per-topic average performance: {'Education': 'high', 'Product demos': 'medium'}"
    )
    overall_best_platform: str = Field(
        default="",
        description="Platform with highest average engagement across all campaigns"
    )
    last_updated: str = Field(default="")


class CampaignRecord(BaseModel):
    """MemGPT Archival Memory unit — one completed campaign stored for long-term recall."""
    campaign_id: str = Field(description="Unique campaign identifier.")
    timestamp: str = Field(description="ISO-8601 creation timestamp.")
    goal: str = Field(description="The campaign goal.")
    selected_trend: str = Field(default="", description="Trend used in this campaign.")
    target_audiences: List[str] = Field(default_factory=list, description="Audience group names that were targeted.")
    selected_styles: List[str] = Field(default_factory=list, description="Style names used.")
    guideline_summary: str = Field(default="", description="Short summary of the content guideline used.")
    platforms_used: List[str] = Field(default_factory=list, description="Which platforms were generated (twitter, instagram, etc.)")
    performance_notes: str = Field(
        default="",
        description="User-provided free-form notes on engagement, success, or lessons learned."
    )
    # 구조화 성과 데이터 (PerformancePendingRequest를 통해 수집)
    performance: Optional[PerformanceData] = Field(
        default=None,
        description="Structured performance data collected via periodic user prompts."
    )


class GeneratedAsset(BaseModel):
    """A single generated image or video asset stored in GCS and indexed in memory."""
    asset_id: str = Field(description="Unique identifier for the asset (e.g., UUID).")
    asset_type: str = Field(description="Type of asset: 'image' or 'video'.")
    gcs_url: str = Field(description="Public GCS URL of the stored asset.")
    local_filename: str = Field(default="", description="Original filename used during generation.")
    prompt_used: str = Field(default="", description="The prompt that produced this asset.")
    platform: str = Field(default="", description="Target platform (e.g., 'instagram', 'tiktok', 'youtube').")
    created_at: str = Field(description="ISO-8601 timestamp when the asset was generated.")
    session_id: str = Field(default="", description="ADK session ID in which the asset was generated.")
    is_user_uploaded: bool = Field(default=False, description="True if uploaded by user, False if AI-generated.")


class RecallEntry(BaseModel):
    """
    MemGPT Recall Memory unit — one turn of conversation history.
    Mirrors MemGPT's message store: each agent turn is appended as a timestamped entry.
    The most recent N entries are injected into context; older entries are summarised.
    """
    timestamp: str = Field(description="ISO-8601 timestamp of this turn.")
    role: str = Field(description="'user' or 'agent'.")
    content: str = Field(description="Message content (truncated to 500 chars).")
    summary_note: str = Field(
        default="",
        description="Optional short annotation (e.g., 'User confirmed brand voice update')."
    )


class CampaignEmbedding(BaseModel):
    """
    Cached embedding vector for a campaign record.
    Stored alongside campaign_archive to avoid re-embedding on every search.
    campaign_id references CampaignRecord.campaign_id.
    """
    campaign_id: str
    vector: List[float] = Field(default_factory=list)


class ConversationRecord(BaseModel):
    """MemGPT Archival Memory unit — one conversation turn stored for long-term recall."""
    conversation_id: str = Field(description="Unique conversation turn identifier.")
    timestamp: str = Field(description="ISO-8601 creation timestamp.")
    role: str = Field(description="'user' or 'agent'.")
    content: str = Field(description="Message content (up to 1000 chars).")
    session_id: str = Field(default="", description="ADK session ID in which this turn occurred.")
    summary: str = Field(default="", description="Optional short summary annotation of this turn.")


class ConversationEmbedding(BaseModel):
    """
    Cached embedding vector for a conversation record.
    conversation_id references ConversationRecord.conversation_id.
    """
    conversation_id: str
    vector: List[float] = Field(default_factory=list)


class MemoryState(BaseModel):
    """
    MemGPT-style memory container stored in ADK session.state['memory'].
    Extended with Domain Profile Block, Audience Behavior Graph, and structured performance tracking.

    Layers:
      - core_profile            → Human Block + Domain Profile Block (always in context)
      - campaign_archive        → Archival Memory (Vertex AI Vector Search — unlimited)
      - conversation_archive    → Archival Memory (Vertex AI Vector Search — unlimited)
      - recall_log              → Recall Memory (rolling conversation history, token-budget based)
      - working_summary         → Recall Memory summary (condensed older turns)
      - asset_archive           → Generated asset index (images & videos)
      - behavior_graph          → Audience-level User Behavior Graph
      - performance_pending     → Queue of campaigns awaiting performance data collection
      - campaign_embeddings     → Local embedding cache (fallback when Vector Search unavailable)
      - conversation_embeddings → Local embedding cache (fallback when Vector Search unavailable)
    """
    core_profile: UserProfile = Field(
        default_factory=UserProfile,
        description="[Core Memory / Human Block + Domain Block] Permanent user identity. Always injected into agent context."
    )
    campaign_archive: List[CampaignRecord] = Field(
        default_factory=list,
        description="[Archival Memory] Past campaigns. Primary search via Vertex AI Vector Search; local list as metadata store."
    )
    campaign_embeddings: List[CampaignEmbedding] = Field(
        default_factory=list,
        description="[Archival Memory] Local embedding cache — used as fallback when Vertex AI Vector Search is unavailable."
    )
    conversation_archive: List[ConversationRecord] = Field(
        default_factory=list,
        description="[Archival Memory] Full conversation history. Primary search via Vertex AI Vector Search."
    )
    conversation_embeddings: List[ConversationEmbedding] = Field(
        default_factory=list,
        description="[Archival Memory] Local embedding cache — fallback for conversation search."
    )
    asset_archive: List[GeneratedAsset] = Field(
        default_factory=list,
        description="[Asset Archive] Index of all generated images and videos. Used by the Creations tab."
    )
    recall_log: List[RecallEntry] = Field(
        default_factory=list,
        description="[Recall Memory] Rolling conversation history. Token-budget based window; older turns summarised into working_summary."
    )
    working_summary: str = Field(
        default="",
        description="[Recall Memory] Condensed summary of older turns beyond the recall_log token window."
    )
    behavior_graph: AudienceBehaviorGraph = Field(
        default_factory=AudienceBehaviorGraph,
        description="[Behavior Graph] Audience-level content-channel-topic performance graph. Updated via user feedback."
    )
    performance_pending: List[PerformancePendingRequest] = Field(
        default_factory=list,
        description="[Performance Queue] Campaigns awaiting performance data collection. Agent asks user at session start or periodically."
    )
    total_campaigns: int = Field(default=0, description="Total number of campaigns generated.")
    last_updated: str = Field(
        default="",
        description="ISO-8601 timestamp of last memory write."
    )


class MemoryUpdateRequest(BaseModel):
    """Input schema for the memory update endpoint."""
    user_id: str
    field: str = Field(description="Dot-path to the field to update, e.g. 'core_profile.brand_voice.tone'")
    value: str = Field(description="New value as a string or JSON string for lists.")


class MemoryResponse(BaseModel):
    """Response schema for memory read endpoint."""
    user_id: str
    memory: MemoryState