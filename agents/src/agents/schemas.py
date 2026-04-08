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
    """
    MemGPT Core Memory: Persona Block (BrandVoice) — 브랜드 톤, 스타일, 표현 규칙.
    Core에 전체 주입 (1매장=1레코드, 고정). 채널별 톤 오버라이드 지원.
    """
    # 식별
    voice_id: str = Field(default="", description="식별 ID")
    # 톤
    tone: str = Field(default="", description="[레거시] Brand tone — tone_primary 사용 권장")
    tone_primary: str = Field(default="", description="기본 톤 (e.g., '따뜻하고 친근한')")
    tone_formality: str = Field(default="", description="formal / semi-formal / casual / playful")
    # 성격/스타일
    personality_traits: List[str] = Field(default_factory=list, description="브랜드 성격 (e.g., ['caring', 'approachable'])")
    writing_style: str = Field(default="", description="short_punchy / narrative / informative")
    preferred_styles: List[str] = Field(default_factory=list, description="비주얼 스타일")
    color_palette: List[str] = Field(default_factory=list, description="브랜드 컬러")
    photography_style: str = Field(default="", description="overhead / lifestyle / product_closeup")
    # 이모지
    emoji_usage: str = Field(default="", description="none / minimal / moderate / heavy")
    emoji_set: List[str] = Field(default_factory=list, description="브랜드 이모지 (e.g., ['☕', '🍞'])")
    # 콘텐츠
    content_pillars: List[str] = Field(default_factory=list, description="콘텐츠 핵심 주제 (3~5개)")
    signature_hashtags: List[str] = Field(default_factory=list, description="매 포스트에 자동 추가")
    # 금지
    avoid_topics: List[str] = Field(default_factory=list, description="절대 언급 금지")
    avoid_words: List[str] = Field(default_factory=list, description="사용 금지 단어")
    # CTA/스토리
    preferred_cta_style: str = Field(default="", description="direct / soft_invitation / question")
    brand_story_snippet: str = Field(default="", description="브랜드 스토리 (2~3문장)")
    slogan: str = Field(default="", description="슬로건")
    # 채널별 오버라이드
    platform_voice_overrides: dict = Field(default_factory=dict, description="채널별 톤 오버라이드 (e.g., {'tiktok': {'tone': 'playful'}})")
    # 동적 확장
    extra: dict = Field(default_factory=dict, description="기존 스키마에 없는 추가 속성")


# Backward compatibility alias
BrandVoice = PersonaBlock


class DomainKnowledge(BaseModel):
    """
    도메인 지식 항목 — LLM이 대화 중 수집한 비즈니스 정보를 구조화하여 저장.
    17종 category + marketing_angle로 마케팅 활용 가능한 형태로 관리.
    Core에는 카탈로그(ID+category+title)만 주입, 상세는 도구 호출로 조회.
    """
    knowledge_id: str = Field(default="", description="고유 식별 ID (자동 생성, e.g., 'dk_001')")
    key: str = Field(default="", description="[레거시] 정보 카테고리 — category 사용 권장")
    category: str = Field(default="", description="지식 카테고리 (17종: sourcing, certification, partnership, facility, process, policy, event, competitive_advantage, local_context, customer_insight, sales_channel, regulation, review_highlight, seasonal_pattern, pricing_strategy, community, competitor_intel)")
    title: str = Field(default="", description="제목 (1줄 요약, Core 카탈로그에 표시)")
    value: str = Field(default="", description="[레거시] 정보 내용 — detail 사용 권장")
    detail: str = Field(default="", description="상세 내용 (도구 호출 시 반환)")
    marketing_angle: str = Field(default="", description="콘텐츠에서 어떻게 활용할지 (e.g., '신선함+안심 강조')")
    confidence: str = Field(default="confirmed", description="정보 신뢰도: 'confirmed' / 'inferred'")
    expiry_hint: str = Field(default="permanent", description="유효 기간: 'permanent' / 'seasonal' / 'needs_refresh'")
    related_products: List[str] = Field(default_factory=list, description="관련 제품 ID (e.g., ['prod_001'])")
    priority: str = Field(default="medium", description="우선순위: 'high' / 'medium' / 'low'")
    source_turn: str = Field(default="", description="수집 시점 (ISO timestamp)")


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
    """
    MemGPT Core Memory: Human Block (OwnerProfile) — 매장 고유 속성.
    다른 매장은 이 값을 가질 수 없는 것들. Core에 전체 주입 (1매장=1레코드, 고정).
    """
    # 기본 식별
    profile_id: str = Field(default="", description="내부 식별 ID")
    display_name: str = Field(default="", description="브랜드명 (콘텐츠에 삽입)")
    owner_name: str = Field(default="", description="대표자명")
    # 레거시 핸들 (social_handles로 이전 권장)
    twitter_handle: Optional[str] = Field(default=None, description="[레거시] Twitter 핸들")
    instagram_handle: Optional[str] = Field(default=None, description="[레거시] Instagram 핸들")
    social_handles: dict = Field(default_factory=dict, description="SNS 계정 통합 (e.g., {'instagram': '@cafe_bom'})")
    # 사업 정보
    business_type: str = Field(default="", description="B2C_retail / B2C_service / B2B")
    industry: str = Field(default="", description="업종 (e.g., 'cafe', 'bakery')")
    industry_subcategory: str = Field(default="", description="세부 업종 (e.g., 'specialty_coffee')")
    founding_date: str = Field(default="", description="설립일 (N년 경력 메시지용)")
    business_stage: str = Field(default="", description="startup / growth / established")
    team_size: int = Field(default=0, description="인원 (콘텐츠 제작 역량 판단)")
    monthly_marketing_budget: str = Field(default="", description="마케팅 예산 (유료/무료 전략 결정)")
    # 위치/운영
    business_location: str = Field(default="", description="사업 위치 (지역 타겟팅)")
    service_area: str = Field(default="", description="서비스 범위")
    operating_hours: str = Field(default="", description="영업시간 (포스팅 타이밍)")
    # 목표
    primary_goal: str = Field(default="", description="핵심 마케팅 목표 (e.g., 'increase_foot_traffic')")
    secondary_goals: List[str] = Field(default_factory=list, description="보조 목표")
    # 추가 정보
    website_url: str = Field(default="", description="웹사이트 URL")
    owner_role_in_content: str = Field(default="", description="face_of_brand / behind_scenes / not_visible")
    languages: List[str] = Field(default_factory=list, description="콘텐츠 언어")
    payment_methods: List[str] = Field(default_factory=list, description="결제 수단")
    reservation_system: str = Field(default="", description="예약 시스템 유무")
    delivery_available: bool = Field(default=False, description="배달 가능 여부")
    online_store_url: str = Field(default="", description="온라인 판매 URL")
    # 동적 확장
    extra_fields: dict = Field(default_factory=dict, description="기존 스키마에 없는 추가 속성")


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
    extra: dict = Field(
        default_factory=dict,
        description="Flexible key-value store for audience attributes not covered by fixed fields (e.g., purchase_cycle, loyalty_program, referral_pattern)."
    )


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
    Core에는 요약(proven/failed/best_platform)만 주입, 상세는 도구 호출.
    """
    nodes: List[ContentNode] = Field(default_factory=list)
    edges: List[PerformanceEdge] = Field(default_factory=list)
    # ── 집계 인사이트 (Core에 요약 주입) ──
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
    proven_tactics: List[str] = Field(
        default_factory=list,
        description="일관적으로 효과적인 전략 (e.g., ['감성사진', '12시포스팅'])"
    )
    failed_tactics: List[str] = Field(
        default_factory=list,
        description="일관적으로 실패하는 전략 (e.g., ['가격비교', '긴캡션'])"
    )
    confidence_level: str = Field(
        default="insufficient",
        description="데이터 신뢰도: insufficient(<5) / moderate(5-15) / reliable(>15)"
    )
    total_data_points: int = Field(
        default=0,
        description="총 성과 관측 수"
    )
    # ── 시계열 추적 (Phase 3 — 주도적 파트너 기능) ──
    segment_channel_trend: dict = Field(
        default_factory=dict,
        description="세그먼트별 채널 성과 추이: {'seg_001': {'instagram': [{'month': '2026-03', 'engagement': 'high', 'count': 5}]}}"
    )
    seasonal_patterns: dict = Field(
        default_factory=dict,
        description="시즌별 성과 패턴: {'spring': {'best_topics': ['봄카페'], 'avg_engagement': 'high'}}"
    )
    trend_performance: dict = Field(
        default_factory=dict,
        description="트렌드별 성과: {'봄카페': [{'month': '2026-03', 'campaigns': 2, 'avg_engagement': 'high'}]}"
    )
    segment_channel_matrix: dict = Field(
        default_factory=dict,
        description="세그먼트별 최적 채널: {'seg_001': 'instagram', 'seg_002': 'kakao'}"
    )
    # ── 메타 ──
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
    # [Phase 2] Performance Impact Score — 이 캠페인 생성 시 참조된 메모리 ID 목록
    referenced_memories: List[str] = Field(
        default_factory=list,
        description="IDs of campaigns/conversations referenced when creating this campaign. Used to compute impact_score."
    )
    impact_score: float = Field(
        default=0.0,
        description="Performance Impact Score — how much this campaign's referenced memories contributed to high performance. Auto-computed from feedback."
    )
    # [Phase 2] Temporal Relevance — 캠페인의 월/시즌 정보
    month: int = Field(
        default=0,
        description="Month (1-12) when this campaign was created. Auto-extracted from timestamp."
    )
    season: str = Field(
        default="",
        description="Season tag: 'spring'/'summer'/'fall'/'winter'. Auto-set from month."
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


class ProductRecord(BaseModel):
    """
    Product Intelligence — 제품/서비스별 마케팅 정보 + 성과 축적.
    Core에는 ID+이름만 주입, 상세는 memory_get_product(id)로 조회.
    """
    product_id: str = Field(description="Unique product identifier (auto-generated, e.g., 'prod_001').")
    name: str = Field(description="Product name (e.g., '소세지빵').")
    category: str = Field(default="", description="Product category (e.g., '빵', '라떼').")
    product_type: str = Field(default="product", description="product / service / package / subscription")
    price: str = Field(default="", description="Price (e.g., '3,000원').")
    description: str = Field(default="", description="마케팅용 설명.")
    price_positioning: str = Field(default="", description="budget / value / premium_justified / luxury")
    features: List[str] = Field(default_factory=list, description="핵심 특성.")
    unique_selling_point: str = Field(default="", description="차별점.")
    target_segments: List[str] = Field(default_factory=list, description="타겟 세그먼트 ID (e.g., ['seg_001']).")
    seasonal_relevance: List[str] = Field(default_factory=list, description="시즌 (e.g., ['spring', 'summer']).")
    availability: str = Field(default="available", description="available / seasonal_only / limited_edition")
    visual_description: str = Field(default="", description="이미지 생성 가이드.")
    messaging_hooks: List[str] = Field(default_factory=list, description="사전 승인된 마케팅 문구.")
    customer_objections: List[str] = Field(default_factory=list, description="예상 반론 + 대응.")
    # 성과 (학습됨)
    related_campaigns: List[str] = Field(default_factory=list, description="Campaign IDs that promoted this product.")
    best_platform: str = Field(default="", description="성과 기반 최적 채널.")
    best_content_type: str = Field(default="", description="성과 기반 최적 포맷.")
    total_campaigns: int = Field(default=0, description="총 캠페인 수.")
    avg_engagement: str = Field(default="", description="평균 참여도.")
    seasonal_peak: str = Field(default="", description="Best performing season.")
    # 가격 이력 (Phase 3)
    price_history: List[dict] = Field(
        default_factory=list,
        description="가격 변경 이력: [{'date': '2026-03-01', 'price': '3000원', 'avg_engagement': 'high'}]"
    )
    # 메타
    created_at: str = Field(default="", description="ISO-8601 first mention timestamp.")
    last_updated: str = Field(default="", description="ISO-8601 last update timestamp.")


class RecallEntry(BaseModel):
    """
    MemGPT Recall Memory unit — one turn of conversation history.
    entry_id로 conversation_archive와 연결하여 access_count를 동기화.
    """
    entry_id: str = Field(
        default="",
        description="Unique ID linking to ConversationRecord.conversation_id for access_count sync."
    )
    timestamp: str = Field(description="ISO-8601 timestamp of this turn.")
    role: str = Field(description="'user' or 'agent'.")
    content: str = Field(description="Message content (truncated to 500 chars).")
    summary_note: str = Field(
        default="",
        description="Optional short annotation (e.g., 'User confirmed brand voice update')."
    )
    access_count: int = Field(
        default=0,
        description="MemGPT Usage Frequency — synced with ConversationRecord.access_count via entry_id."
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

        # ── Migrate HumanBlock: twitter/instagram handles → social_handles ──
        if isinstance(data, dict) and 'human_block' in data:
            hb = data['human_block']
            if isinstance(hb, dict):
                sh = hb.setdefault('social_handles', {})
                if hb.get('twitter_handle') and 'twitter' not in sh:
                    sh['twitter'] = hb['twitter_handle']
                if hb.get('instagram_handle') and 'instagram' not in sh:
                    sh['instagram'] = hb['instagram_handle']
                # Promote extra_fields to first-class fields
                ef = hb.get('extra_fields', {})
                if isinstance(ef, dict):
                    for key_map in [('location', 'business_location'), ('industry', 'industry'),
                                    ('goal', 'primary_goal'), ('budget', 'monthly_marketing_budget')]:
                        old_key, new_key = key_map
                        if old_key in ef and not hb.get(new_key):
                            hb[new_key] = ef.pop(old_key)

        # ── Migrate PersonaBlock: tone → tone_primary ──
        if isinstance(data, dict) and 'persona_block' in data:
            pb = data['persona_block']
            if isinstance(pb, dict):
                if pb.get('tone') and not pb.get('tone_primary'):
                    pb['tone_primary'] = pb['tone']
                # Promote extra to first-class fields
                ex = pb.get('extra', {})
                if isinstance(ex, dict):
                    for key_map in [('slogan', 'slogan'), ('brand_story', 'brand_story_snippet')]:
                        old_key, new_key = key_map
                        if old_key in ex and not pb.get(new_key):
                            pb[new_key] = ex.pop(old_key)

        # ── Migrate DomainKnowledge: auto-assign knowledge_id ──
        if isinstance(data, dict) and 'domain_block' in data:
            db = data['domain_block']
            if isinstance(db, dict) and 'knowledge' in db:
                kl = db['knowledge']
                if isinstance(kl, list):
                    for i, k in enumerate(kl):
                        if isinstance(k, dict):
                            if not k.get('knowledge_id'):
                                k['knowledge_id'] = f"dk_{i+1:03d}"
                            if k.get('key') and not k.get('category'):
                                k['category'] = k['key']
                            if k.get('value') and not k.get('title'):
                                k['title'] = k['value'][:80]
                            if k.get('value') and not k.get('detail'):
                                k['detail'] = k['value']

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
    product_archive: List[ProductRecord] = Field(
        default_factory=list,
        description="[Phase 2 / Product Intelligence] Product/service catalog with per-product marketing performance."
    )
    # [Phase 2] Temporal Intelligence — 월별 성과 집계
    monthly_performance: dict = Field(
        default_factory=dict,
        description="Monthly campaign performance aggregates: {'3': {'count': 5, 'avg_engagement': 'high', 'top_product': '쿠키'}}."
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