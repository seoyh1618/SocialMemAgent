/**
 * MemGPT Memory Type Definitions — Frontend mirror of backend schemas.py MemoryState.
 * Provides type safety for memory API calls and ProfileBlock UI.
 *
 * 4-Block Core Memory Architecture:
 *   HumanBlock    → display_name, handles, extra_fields
 *   PersonaBlock  → tone, preferred_styles, avoid_topics, signature_hashtags, content_pillars
 *   DomainBlock   → industry, domain_type, usp, competitors, knowledge, etc.
 *   AudienceBlock → target_platforms, default_age_range, segments (AudienceSegment[]), seasonal_peaks, offline_channels
 */

export interface HumanBlock {
  display_name: string;
  twitter_handle: string | null;
  instagram_handle: string | null;
  extra_fields: Record<string, string>;
}

export interface PersonaBlock {
  tone: string;
  preferred_styles: string[];
  avoid_topics: string[];
  signature_hashtags: string[];
  content_pillars: string[];
}

export interface DomainKnowledge {
  key: string;
  value: string;
  confidence: 'confirmed' | 'inferred';
  source_turn: string;
}

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
}

export interface MemoryState {
  human_block: HumanBlock;
  persona_block: PersonaBlock;
  domain_block: DomainBlock;
  audience_block: AudienceBlock;
  campaign_archive: CampaignRecord[];
  asset_archive: GeneratedAsset[];
  /** Rolling conversation history — managed by backend callbacks */
  recall_log?: RecallEntry[];
  working_summary: string;
  session_summaries?: string[];
  long_term_summary?: string;
  behavior_graph?: BehaviorGraph;
  performance_pending?: PerformancePendingRequest[];
  conversation_archive?: { conversation_id: string; timestamp: string; role: string; content: string; summary: string }[];
  total_campaigns: number;
  last_updated: string;
}

export const DEFAULT_MEMORY_STATE: MemoryState = {
  human_block: {
    display_name: "",
    twitter_handle: null,
    instagram_handle: null,
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
  asset_archive: [],
  working_summary: "",
  total_campaigns: 0,
  last_updated: "",
  // agent-managed fields — not sent on PUT (preserved by backend merge strategy)
  recall_log: undefined,
};
