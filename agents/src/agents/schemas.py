from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field, HttpUrl, model_validator
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

class PersonaBlock(BaseModel):
    """MemGPT Core Memory: Persona Block — brand voice and style identity."""
    tone: str = Field(default="", description="Brand tone")
    preferred_styles: List[str] = Field(default_factory=list)
    avoid_topics: List[str] = Field(default_factory=list)
    signature_hashtags: List[str] = Field(default_factory=list)
    content_pillars: List[str] = Field(default_factory=list)


# Backward compatibility alias
BrandVoice = PersonaBlock


class DomainKnowledge(BaseModel):
    """
    도메인 지식 항목 — LLM이 대화 중 수집한 비즈니스 정보를 자유롭게 저장.
    고정 스키마 없이 key-value로 어떤 산업이든 유연하게 대응.
    """
    key: str = Field(description="정보 카테고리 (e.g., 'flagship_product', 'menu_item', 'service', 'material', 'certification', 'partnership')")
    value: str = Field(description="정보 내용 (e.g., '시그니처 딸기라떼 - 신선한 딸기 사용, 6,500원')")
    confidence: str = Field(default="confirmed", description="정보 신뢰도: 'confirmed' (사용자 직접 언급), 'inferred' (대화에서 추론)")
    source_turn: str = Field(default="", description="수집 시점 (ISO timestamp 또는 대화 요약)")


class DomainProfileBlock(BaseModel):
    """
    Domain Profile Block — 소상공인 서비스 도메인별 특화 정보.
    MemGPT Human Block과 병합하여 사용 (extra_fields 대체/보완).
    도메인 유형(restaurant, fashion, fitness, beauty, cafe, retail 등)에 따라
    콘텐츠 전략이 달라지므로 구조화된 필드로 관리.
    """
    industry: str = Field(
        default="",
        description="User's industry or niche (e.g., 'SaaS', 'Fashion', 'Fitness')."
    )
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
    usp: str = Field(
        default="",
        description="Unique Selling Point — core differentiator from competitors"
    )
    competitors: List[str] = Field(
        default_factory=list,
        description="Main competitor brands or businesses"
    )
    knowledge: List[DomainKnowledge] = Field(
        default_factory=list,
        description=(
            "도메인 지식 — LLM이 대화에서 수집한 비즈니스 정보를 자유 형식으로 저장. "
            "제품, 서비스, 재료, 인증, 제휴, 고객 특성 등 산업에 따라 다른 정보를 유연하게 수집. "
            "key로 카테고리 구분, value에 상세 내용 저장."
        )
    )
    domain_extra: dict = Field(
        default_factory=dict,
        description="Additional domain-specific fields not covered above (snake_case keys, string values)"
    )


class HumanBlock(BaseModel):
    """MemGPT Core Memory: Human Block — user identity and contact."""
    display_name: str = Field(default="")
    twitter_handle: Optional[str] = Field(default=None)
    instagram_handle: Optional[str] = Field(default=None)
    extra_fields: dict = Field(default_factory=dict)


class AudienceTrait(BaseModel):
    """오디언스 세그먼트의 자유형 속성 — 업종에 따라 다른 정보 수집."""
    key: str = Field(description="Attribute category: 'occupation', 'pain_point', 'lifestyle', 'budget', 'motivation', 'media_habit', 'purchase_behavior', etc.")
    value: str = Field(description="Attribute value in natural language.")
    confidence: str = Field(default="confirmed", description="'confirmed' (user stated) | 'inferred' (agent deduced) | 'discovered' (unexpected finding)")


class AudienceSegment(BaseModel):
    """제품/서비스별 타겟 오디언스 세그먼트."""
    segment_id: str = Field(default="", description="Unique segment identifier (auto-generated)")
    name: str = Field(description="Segment name, e.g., '시니어 재활 고객', 'IT 직장인'")
    source: str = Field(default="confirmed", description="How this segment was identified: 'confirmed' | 'inferred' | 'discovered'")
    # Common attributes
    age_range: str = Field(default="", description="Target age range, e.g., '30-40대'")
    gender: str = Field(default="", description="Gender distribution, e.g., '여성 중심', '남녀 비율 6:4', '무관'")
    location: str = Field(default="", description="Geographic target, e.g., '서울 강남', '전국', '온라인'")
    # Connection info
    products: List[str] = Field(default_factory=list, description="Products/services this segment is interested in")
    platforms: List[str] = Field(default_factory=list, description="Channels where this segment is most active")
    # Flexible traits
    traits: List[AudienceTrait] = Field(default_factory=list, description="Industry-specific attributes collected from conversations")
    notes: str = Field(default="", description="Free-form notes about this segment")


class AudienceBlock(BaseModel):
    """MemGPT Core Memory: Audience Block — target audience and channel strategy."""
    target_platforms: List[str] = Field(default_factory=list, description="Brand's primary target platforms")
    default_age_range: str = Field(default="", description="Brand-wide default target age range")
    segments: List[AudienceSegment] = Field(default_factory=list, description="Product/service-specific audience segments (max 20)")
    seasonal_peaks: List[str] = Field(default_factory=list)
    offline_channels: List[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """DEPRECATED — kept for backward compatibility with old serialized sessions.
    New code should use HumanBlock, PersonaBlock, DomainProfileBlock, AudienceBlock directly."""
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
    segment_id: str = Field(default="", description="References AudienceSegment.segment_id — links performance to a specific audience segment")
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
    access_count: int = Field(
        default=0,
        description="MemGPT Usage Frequency — how many times this campaign was retrieved via search. Higher = more relevant to user's brand."
    )
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
    caption: str = Field(default="", description="Post caption/text used with this asset (e.g., Instagram caption with hashtags).")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags used with this asset.")
    platform: str = Field(default="", description="Target platform (e.g., 'instagram', 'tiktok', 'youtube').")
    created_at: str = Field(description="ISO-8601 timestamp when the asset was generated.")
    session_id: str = Field(default="", description="ADK session ID in which the asset was generated.")
    is_user_uploaded: bool = Field(default=False, description="True if uploaded by user, False if AI-generated.")
    performance: Optional[PerformanceData] = Field(
        default=None,
        description="Structured performance data for this asset."
    )


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
    access_count: int = Field(
        default=0,
        description="MemGPT Usage Frequency — how many times this entry was retrieved/referenced. Higher = more important, preserved during compression."
    )


class ConversationRecord(BaseModel):
    """MemGPT Archival Memory unit — one conversation turn stored for long-term recall."""
    conversation_id: str = Field(description="Unique conversation turn identifier.")
    timestamp: str = Field(description="ISO-8601 creation timestamp.")
    role: str = Field(description="'user' or 'agent'.")
    access_count: int = Field(
        default=0,
        description="MemGPT Usage Frequency — retrieval count via semantic search."
    )
    content: str = Field(description="Message content (up to 1000 chars).")
    session_id: str = Field(default="", description="ADK session ID in which this turn occurred.")
    summary: str = Field(default="", description="Optional short summary annotation of this turn.")


class MemoryState(BaseModel):
    """
    MemGPT-style memory container stored in ADK session.state['memory'].
    Extended with 4 independent Core Memory blocks, Audience Behavior Graph,
    and structured performance tracking.

    Core Memory Blocks:
      - human_block             → Human Block (user identity & contact)
      - persona_block           → Persona Block (brand voice & style)
      - domain_block            → Domain Profile Block (business details)
      - audience_block          → Audience Block (target audience & channels)
    Other Layers:
      - campaign_archive        → Archival Memory (Qdrant vector search — unlimited)
      - conversation_archive    → Archival Memory (Qdrant vector search — unlimited)
      - recall_log              → Recall Memory (rolling conversation history, token-budget based)
      - working_summary         → Recall Memory summary (condensed older turns)
      - asset_archive           → Generated asset index (images & videos)
      - behavior_graph          → Audience-level User Behavior Graph
      - performance_pending     → Queue of campaigns awaiting performance data collection
    """

    @model_validator(mode='before')
    @classmethod
    def _migrate_core_profile(cls, data):
        """Backward compatibility: migrate old nested core_profile to 4 independent blocks."""
        if isinstance(data, dict) and 'core_profile' in data:
            cp = data.pop('core_profile')
            if isinstance(cp, dict):
                # Migrate to new blocks
                if 'human_block' not in data:
                    data['human_block'] = {
                        'display_name': cp.get('display_name', ''),
                        'twitter_handle': cp.get('twitter_handle'),
                        'instagram_handle': cp.get('instagram_handle'),
                        'extra_fields': cp.get('extra_fields', {}),
                    }
                if 'persona_block' not in data:
                    bv = cp.get('brand_voice', {})
                    data['persona_block'] = bv if isinstance(bv, dict) else {}
                if 'domain_block' not in data:
                    dp = cp.get('domain_profile', {})
                    if isinstance(dp, dict):
                        dp = dict(dp)  # shallow copy to avoid mutating original
                        dp['industry'] = cp.get('industry', dp.get('industry', ''))
                        # Remove fields that moved to audience_block
                        dp.pop('target_age_range', None)
                        dp.pop('seasonal_peaks', None)
                        dp.pop('offline_channels', None)
                    else:
                        dp = {'industry': cp.get('industry', '')}
                    data['domain_block'] = dp
                if 'audience_block' not in data:
                    dp = cp.get('domain_profile', {})
                    data['audience_block'] = {
                        'target_platforms': cp.get('target_platforms', []),
                        'default_age_range': dp.get('target_age_range', '') if isinstance(dp, dict) else '',
                        'segments': [],
                        'seasonal_peaks': dp.get('seasonal_peaks', []) if isinstance(dp, dict) else [],
                        'offline_channels': dp.get('offline_channels', []) if isinstance(dp, dict) else [],
                    }
        # ── Migrate old audience_block field names ────────────────────────
        if isinstance(data, dict) and 'audience_block' in data:
            ab = data['audience_block']
            if isinstance(ab, dict):
                # Rename target_age_range → default_age_range
                if 'target_age_range' in ab and 'default_age_range' not in ab:
                    ab['default_age_range'] = ab.pop('target_age_range')
                # Convert old audience_segments: List[str] → segments: List[AudienceSegment]
                if 'audience_segments' in ab and 'segments' not in ab:
                    old_segs = ab.pop('audience_segments')
                    if isinstance(old_segs, list):
                        ab['segments'] = [
                            {'name': s, 'segment_id': f'migrated_{i}'}
                            if isinstance(s, str)
                            else s
                            for i, s in enumerate(old_segs)
                        ]
                    else:
                        ab['segments'] = []

        return data

    human_block: HumanBlock = Field(
        default_factory=HumanBlock,
        description="[Core Memory / Human Block] Permanent user identity and contact info."
    )
    persona_block: PersonaBlock = Field(
        default_factory=PersonaBlock,
        description="[Core Memory / Persona Block] Brand voice and style identity."
    )
    domain_block: DomainProfileBlock = Field(
        default_factory=DomainProfileBlock,
        description="[Core Memory / Domain Block] Domain-specific business profile."
    )
    audience_block: AudienceBlock = Field(
        default_factory=AudienceBlock,
        description="[Core Memory / Audience Block] Target audience and channel strategy."
    )
    campaign_archive: List[CampaignRecord] = Field(
        default_factory=list,
        description="[Archival Memory] Past campaigns. Semantic search via Qdrant; local list as metadata store."
    )
    conversation_archive: List[ConversationRecord] = Field(
        default_factory=list,
        description="[Archival Memory] Full conversation history. Semantic search via Qdrant."
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
        description="[Recall Memory L1] Condensed summary of older turns beyond the recall_log token window."
    )
    session_summaries: List[str] = Field(
        default_factory=list,
        description="[Recall Memory L2] Per-session summaries (each ~500 chars). Max 10 kept."
    )
    long_term_summary: str = Field(
        default="",
        description="[Recall Memory L3] Long-term cumulative summary across all sessions (~3000 chars)."
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
    field: str = Field(description="Dot-path to the field to update, e.g. 'persona_block.tone'")
    value: str = Field(description="New value as a string or JSON string for lists.")


class MemoryResponse(BaseModel):
    """Response schema for memory read endpoint."""
    user_id: str
    memory: MemoryState