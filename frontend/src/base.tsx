export interface EnabledField<T> {
  value: T;
  enabled: boolean;
}

export interface AudienceGroup {
  name: string;
  targeted: boolean;
}

export interface Trend {
    selected_trend: string;
    trending: string[];
}

export interface Style {
    name: string;
    selected: boolean;
}

export interface ImagePost {
    image_url: string;
    post_text: string;
}

export interface VideoPost {
    video_url: string;
    title: string;
    description: string;
}

// Base interface
export interface Base {
    goal: string;

    // Context
    trends: EnabledField<Trend>;
    audiences: EnabledField<AudienceGroup[]>;
    styles: EnabledField<Style[]>;

    // Intermediate
    guideline: EnabledField<string>;
    image_prompt: EnabledField<string>;
    video_prompt: EnabledField<string>;
    video_narration: EnabledField<string>;

    // Artifacts
    twitter_post: EnabledField<string>;
    youtube_post: EnabledField<VideoPost>;
    tiktok_post: EnabledField<VideoPost>;
    instagram_post: EnabledField<ImagePost>;
    facebook_post: EnabledField<ImagePost>;
    linkedin_post: EnabledField<ImagePost>;
    pinterest_post: EnabledField<ImagePost>;
    threads_post: EnabledField<string>;
    kakao_post: EnabledField<ImagePost>;
}

// Helper method to set if the field is enabled.
export function setEnabledField(
    base: Base, 
    fieldName: keyof Pick<Base, "trends" | "audiences" | "styles" | "guideline" | "image_prompt" | "video_prompt" | "video_narration" | "twitter_post" | "youtube_post" | "tiktok_post" | "instagram_post" | "facebook_post" | "linkedin_post" | "pinterest_post" | "threads_post" | "kakao_post">,
    enabled: boolean): Base {
    const newBase = {...base};
    switch (fieldName) {
        case "trends":
            newBase.trends.enabled = enabled;
            break;
        case "styles":
            newBase.styles.enabled = enabled;
            break;
        case "audiences":
            newBase.audiences.enabled = enabled;
            break;
        case "guideline":
            newBase.guideline.enabled = enabled;
            break;
        case "image_prompt":
            newBase.image_prompt.enabled = enabled;
            break;
        case "video_prompt":
            newBase.video_prompt.enabled = enabled;
            break;
        case "video_narration":
            newBase.video_narration.enabled = enabled;
            break;
        case "twitter_post":
            newBase.twitter_post.enabled = enabled;
            break;
        case "youtube_post":
            newBase.youtube_post.enabled = enabled;
            break;
        case "tiktok_post":
            newBase.tiktok_post.enabled = enabled;
            break;
        case "instagram_post":
            newBase.instagram_post.enabled = enabled;
            break;
        case "facebook_post":
            newBase.facebook_post.enabled = enabled;
            break;
        case "linkedin_post":
            newBase.linkedin_post.enabled = enabled;
            break;
        case "pinterest_post":
            newBase.pinterest_post.enabled = enabled;
            break;
        case "threads_post":
            newBase.threads_post.enabled = enabled;
            break;
        case "kakao_post":
            newBase.kakao_post.enabled = enabled;
            break;
        default:
            throw new Error(`Invalid field name: ${fieldName}`);
    }
    return newBase;
}

// // Diff type
// export type Diff = 
// | {fieldName: "goal"; newGoal: string}
// | {fieldName: "audiences"; newAudience: AudienceGroup[]}
// | {fieldName: "guideline"; newGuideline: string}
// | {fieldName: "twitter_post"; newTwitterPost: string}
// | {fieldName: "video_url"; newVideoUrl: string}

export interface SocialMediaAgentInput {
    user_query: string;
    base: Base;
}

export interface SocialMediaAgentOutput {
    agent_response: string;
    is_updated: boolean;
    updated_base: Base;
}

// ── Orchestrator channels JSON → Base 변환 ──────────────────────────
export interface OrchestratorChannelOutput {
    agent_response: string;
    is_updated: boolean;
    channels: Record<string, {
        content_type?: string;
        caption?: string;
        hashtags?: string[];
        image_url?: string | null;
        video_url?: string | null;
        additional?: Record<string, unknown>;
    }>;
}

/** Safely convert caption to string — LLM may return object instead of string */
function safeCaption(caption: unknown): string {
    if (!caption) return '';
    if (typeof caption === 'string') return caption;
    if (typeof caption === 'object') {
        // Try common fields: title, description, text, post_text
        const obj = caption as Record<string, unknown>;
        const parts = [obj.title, obj.description, obj.text, obj.post_text].filter(v => typeof v === 'string');
        if (parts.length > 0) return (parts as string[]).join('\n\n');
        return JSON.stringify(caption);
    }
    return String(caption);
}

/**
 * orchestrator의 channels 응답을 기존 Base 스키마로 변환
 */
export function channelsToBase(output: OrchestratorChannelOutput, currentBase: Base): Base {
    const newBase = { ...currentBase };
    const ch = output.channels;

    // Instagram
    if (ch.instagram) {
        newBase.instagram_post = {
            enabled: true,
            value: {
                image_url: ch.instagram.image_url || '',
                post_text: safeCaption(ch.instagram.caption) +
                    (ch.instagram.hashtags?.length ? '\n\n' + ch.instagram.hashtags.join(' ') : ''),
            },
        };
    }

    // Facebook
    if (ch.facebook) {
        newBase.facebook_post = {
            enabled: true,
            value: {
                image_url: ch.facebook.image_url || '',
                post_text: safeCaption(ch.facebook.caption) +
                    (ch.facebook.hashtags?.length ? '\n\n' + ch.facebook.hashtags.join(' ') : ''),
            },
        };
    }

    // X (Twitter)
    if (ch.x) {
        const xText = safeCaption(ch.x.caption) +
            (ch.x.hashtags?.length ? '\n\n' + ch.x.hashtags.join(' ') : '');
        newBase.twitter_post = { enabled: true, value: xText };
    }

    // Threads
    if (ch.threads) {
        const threadsText = safeCaption(ch.threads.caption) +
            (ch.threads.hashtags?.length ? '\n\n' + ch.threads.hashtags.join(' ') : '');
        newBase.threads_post = { enabled: true, value: threadsText };
    }

    // LinkedIn
    if (ch.linkedin) {
        newBase.linkedin_post = {
            enabled: true,
            value: {
                image_url: ch.linkedin.image_url || '',
                post_text: safeCaption(ch.linkedin.caption) +
                    (ch.linkedin.hashtags?.length ? '\n\n' + ch.linkedin.hashtags.join(' ') : ''),
            },
        };
    }

    // YouTube
    if (ch.youtube) {
        newBase.youtube_post = {
            enabled: true,
            value: {
                video_url: ch.youtube.video_url || '',
                title: safeCaption(ch.youtube.caption),
                description: ch.youtube.hashtags?.join(' ') || '',
            },
        };
    }

    // TikTok
    if (ch.tiktok) {
        newBase.tiktok_post = {
            enabled: true,
            value: {
                video_url: ch.tiktok.video_url || '',
                title: safeCaption(ch.tiktok.caption),
                description: ch.tiktok.hashtags?.join(' ') || '',
            },
        };
    }

    // Pinterest
    if (ch.pinterest) {
        newBase.pinterest_post = {
            enabled: true,
            value: {
                image_url: ch.pinterest.image_url || '',
                post_text: safeCaption(ch.pinterest.caption) +
                    (ch.pinterest.hashtags?.length ? '\n\n' + ch.pinterest.hashtags.join(' ') : ''),
            },
        };
    }

    // Kakao
    if (ch.kakao) {
        newBase.kakao_post = {
            enabled: true,
            value: {
                image_url: ch.kakao.image_url || '',
                post_text: safeCaption(ch.kakao.caption) +
                    (ch.kakao.hashtags?.length ? '\n\n' + ch.kakao.hashtags.join(' ') : ''),
            },
        };
    }

    // goal 업데이트
    if (output.agent_response) {
        newBase.goal = output.agent_response;
    }

    return newBase;
}