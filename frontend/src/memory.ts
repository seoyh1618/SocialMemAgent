/**
 * MemGPT Memory Type Definitions — Frontend mirror of backend schemas.py MemoryState.
 * Provides type safety for memory API calls and ProfileBlock UI.
 *
 * 5-Block Core Memory Architecture:
 *   HumanBlock    → OwnerProfile: 매장 고유 속성 (23필드, Core 전체 주입)
 *   PersonaBlock  → BrandVoice: 톤, 스타일, 표현 규칙 (18필드, Core 전체 주입)
 *   DomainBlock   → DomainProfile + Knowledge: 사업 정보 + 운영 지식 (Core: DomainProfile 전체 + Knowledge 카탈로그)
 *   AudienceBlock → Segment: 고객 세그먼트 (Core: 카탈로그만)
 *   CampaignBlock → Campaign + Performance + BehaviorGraph (Core: BehaviorGraph 요약 + 카탈로그)
 */

// ─── HUMAN Block (OwnerProfile) ─────────────────────────────────────────────

export interface HumanBlock {
  // 기본 식별
  profile_id?: string;
  display_name: string;
  owner_name?: string;
  // 레거시 핸들
  twitter_handle: string | null;
  instagram_handle: string | null;
  // 통합 SNS
  social_handles?: Record<string, string>;
  // 사업 정보
  business_type?: string;
  industry?: string;
  industry_subcategory?: string;
  founding_date?: string;
  business_stage?: string;
  team_size?: number;
  monthly_marketing_budget?: string;
  // 위치/운영
  business_location?: string;
  service_area?: string;
  operating_hours?: string;
  // 목표
  primary_goal?: string;
  secondary_goals?: string[];
  // 추가
  website_url?: string;
  owner_role_in_content?: string;
  languages?: string[];
  payment_methods?: string[];
  reservation_system?: string;
  delivery_available?: boolean;
  online_store_url?: string;
  // 동적 확장
  extra_fields: Record<string, string>;
}

// ─── PERSONA Block (BrandVoice) ─────────────────────────────────────────────

export interface PersonaBlock {
  // 식별
  voice_id?: string;
  // 톤
  tone: string;
  tone_primary?: string;
  tone_formality?: string;
  // 성격/스타일
  personality_traits?: string[];
  writing_style?: string;
  preferred_styles: string[];
  color_palette?: string[];
  photography_style?: string;
  // 이모지
  emoji_usage?: string;
  emoji_set?: string[];
  // 콘텐츠
  content_pillars: string[];
  signature_hashtags: string[];
  // 금지
  avoid_topics: string[];
  avoid_words?: string[];
  // CTA/스토리
  preferred_cta_style?: string;
  brand_story_snippet?: string;
  slogan?: string;
  // 채널별 오버라이드
  platform_voice_overrides?: Record<string, Record<string, string>>;
  // 동적 확장
  extra?: Record<string, string>;
}

// ─── BUSINESS Block: DomainKnowledge ────────────────────────────────────────

export interface DomainKnowledge {
  knowledge_id?: string;
  key: string;
  category?: string;
  title?: string;
  value: string;
  detail?: string;
  marketing_angle?: string;
  confidence: 'confirmed' | 'inferred';
  expiry_hint?: string;
  related_products?: string[];
  priority?: string;
  source_turn: string;
}

// ─── BUSINESS Block: DomainBlock ────────────────────────────────────────────

export interface DomainBlock {
  industry: string;
  domain_type: string;
  business_location: string;
  operating_hours: string;
  price_range: string;
  usp: string;
  competitors: string[];
  knowledge: DomainKnowledge[];
  domain_extra: Record<string, string>;
}

// ─── AUDIENCE Block ─────────────────────────────────────────────────────────

export interface AudienceTrait {
  key: string;
  value: string;
  confidence: 'confirmed' | 'inferred' | 'discovered';
}

export interface AudienceSegment {
  segment_id: string;
  name: string;
  source: 'confirmed' | 'inferred' | 'discovered';
  age_range: string;
  gender: string;
  location: string;
  products: string[];
  platforms: string[];
  traits: AudienceTrait[];
  notes: string;
}

export interface AudienceBlock {
  target_platforms: string[];
  default_age_range: string;
  segments: AudienceSegment[];
  seasonal_peaks: string[];
  offline_channels: string[];
}

// ─── CAMPAIGN Block: Performance ────────────────────────────────────────────

export interface PerformancePendingRequest {
  campaign_id: string;
  campaign_goal: string;
  platforms: string[];
  created_at: string;
  asked_at: string;
  ask_count: number;
}

export interface PerformanceEdge {
  edge_id: string;
  node_id: string;
  campaign_id: string;
  segment_id: string;
  engagement_level: string;
  reach_level: string;
  what_worked: string[];
  what_failed: string[];
  timestamp: string;
}

export interface BehaviorGraph {
  nodes: { node_id: string; platform: string; content_type: string; topic: string }[];
  edges: PerformanceEdge[];
  platform_best_content_type: Record<string, string>;
  topic_performance_summary: Record<string, string>;
  overall_best_platform: string;
}

export interface PerformanceData {
  collected_at: string;
  engagement_level: string;
  reach_level: string;
  conversion_level: string;
  best_platform: string;
  what_worked: string[];
  what_failed: string[];
  views: number;
  clicks: number;
  impressions: number;
  likes: number;
  shares: number;
  comments: number;
}

export interface CampaignRecord {
  campaign_id: string;
  timestamp: string;
  goal: string;
  selected_trend: string;
  target_audiences: string[];
  selected_styles: string[];
  guideline_summary: string;
  platforms_used: string[];
  performance_notes: string;
  performance?: PerformanceData;
}

// ─── Product Record ─────────────────────────────────────────────────────────

export interface ProductRecord {
  product_id: string;
  name: string;
  price?: string;
  category?: string;
  product_type?: string;
  description?: string;
  key_features?: string[];
  unique_selling_point?: string;
  target_segments?: string[];
  seasonal_relevance?: string[];
  availability?: string;
  visual_description?: string;
  messaging_hooks?: string[];
  customer_objections?: string[];
  best_platform?: string;
  best_content_type?: string;
  total_campaigns?: number;
  avg_engagement?: string;
}

// ─── Assets & Recall ────────────────────────────────────────────────────────

export interface GeneratedAsset {
  asset_id: string;
  asset_type: 'image' | 'video';
  gcs_url: string;
  local_filename: string;
  prompt_used: string;
  caption: string;
  hashtags: string[];
  platform: string;
  created_at: string;
  session_id: string;
  is_user_uploaded?: boolean;
}

export interface RecallEntry {
  timestamp: string;
  role: 'user' | 'agent';
  content: string;
  summary_note: string;
  access_count?: number;
}

// ─── MemoryState ────────────────────────────────────────────────────────────

export interface MemoryState {
  // 5-Block Core Memory
  human_block: HumanBlock;
  persona_block: PersonaBlock;
  domain_block: DomainBlock;
  audience_block: AudienceBlock;
  // Archival
  campaign_archive: CampaignRecord[];
  product_archive?: ProductRecord[];
  asset_archive: GeneratedAsset[];
  // Recall Memory (3-Level)
  recall_log?: RecallEntry[];
  working_summary: string;
  session_summaries?: string[];
  long_term_summary?: string;
  // Campaign Block (BehaviorGraph)
  behavior_graph?: BehaviorGraph;
  performance_pending?: PerformancePendingRequest[];
  // Conversation Archive
  conversation_archive?: { conversation_id: string; timestamp: string; role: string; content: string; summary: string }[];
  // Meta
  total_campaigns: number;
  last_updated: string;
}

// ─── Default State ──────────────────────────────────────────────────────────

export const DEFAULT_MEMORY_STATE: MemoryState = {
  human_block: {
    display_name: "",
    twitter_handle: null,
    instagram_handle: null,
    social_handles: {},
    extra_fields: {},
  },
  persona_block: {
    tone: "",
    preferred_styles: [],
    avoid_topics: [],
    signature_hashtags: [],
    content_pillars: [],
  },
  domain_block: {
    industry: "",
    domain_type: "",
    business_location: "",
    operating_hours: "",
    price_range: "",
    usp: "",
    competitors: [],
    knowledge: [],
    domain_extra: {},
  },
  audience_block: {
    target_platforms: [],
    default_age_range: "",
    segments: [],
    seasonal_peaks: [],
    offline_channels: [],
  },
  campaign_archive: [],
  product_archive: [],
  asset_archive: [],
  working_summary: "",
  total_campaigns: 0,
  last_updated: "",
  recall_log: undefined,
};
