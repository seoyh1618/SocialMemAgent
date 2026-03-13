/**
 * MemGPT Memory Type Definitions — Frontend mirror of backend schemas.py MemoryState.
 * Provides type safety for memory API calls and ProfileBlock UI.
 */

export interface BrandVoice {
  tone: string;
  preferred_styles: string[];
  avoid_topics: string[];
  signature_hashtags: string[];
  content_pillars: string[];
}

export interface UserProfile {
  display_name: string;
  twitter_handle: string | null;
  instagram_handle: string | null;
  industry: string;
  target_platforms: string[];
  brand_voice: BrandVoice;
  extra_fields: Record<string, string>;
}

export interface PerformanceData {
  collected_at: string;
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

export interface CampaignEmbedding {
  campaign_id: string;
  vector: number[];
}

export interface MemoryState {
  core_profile: UserProfile;
  campaign_archive: CampaignRecord[];
  /** Cached Vertex AI embedding vectors — managed by backend, not editable by frontend */
  campaign_embeddings?: CampaignEmbedding[];
  asset_archive: GeneratedAsset[];
  /** Rolling conversation history — managed by backend callbacks */
  recall_log?: RecallEntry[];
  working_summary: string;
  total_campaigns: number;
  last_updated: string;
}

export const DEFAULT_MEMORY_STATE: MemoryState = {
  core_profile: {
    display_name: "",
    twitter_handle: null,
    instagram_handle: null,
    industry: "",
    target_platforms: [],
    extra_fields: {},
    brand_voice: {
      tone: "",
      preferred_styles: [],
      avoid_topics: [],
      signature_hashtags: [],
      content_pillars: [],
    },
  },
  campaign_archive: [],
  asset_archive: [],
  working_summary: "",
  total_campaigns: 0,
  last_updated: "",
  // agent-managed fields — not sent on PUT (preserved by backend merge strategy)
  campaign_embeddings: undefined,
  recall_log: undefined,
};
