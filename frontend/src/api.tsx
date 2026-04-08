import type { Base, SocialMediaAgentInput } from "./base";
import type { MemoryState } from "./memory";
import { DEFAULT_MEMORY_STATE } from "./memory";

// Configuration
// const API_BASE_URL = "https://socialmediabrandingagent-662824162875.us-west1.run.app";
const API_BASE_URL = "http://localhost:8080";

// Types for the message structure
interface MessagePart {
  text?: string;
  inlineData?: { mimeType: string; data: string };
}

interface Message {
  role: 'user' | 'model';
  parts: MessagePart[];
}

interface AgentRequestPayload {
  appName: string;
  userId: string;
  sessionId: string;
  newMessage: Message;
  streaming: boolean;
}

interface AgentResponse {
  content: {
    parts: Array<{
      text?: string;
      functionCall?: any;
      functionResponse?: any;
    }>;
    role: string;
  };
  invocation_id: string;
  author: string;
  partial: boolean;
  actions: {
    state_delta: Record<string, any>;
    artifact_delta: Record<string, any>;
    requested_auth_configs: Record<string, any>;
  };
  id: string;
  timestamp: number;
}

// Define the response type for starting a new session
interface StartSessionResponse {
  id: string;
  appName: string;
  userId: string;
  state: Record<string, any>;
  events: any[];
  lastUpdateTime: number;
}

// Callbacks interface for handling SSE events
interface SSECallbacks {
  onData: (data: AgentResponse) => void;
  onStateDelta?: (delta: Record<string, unknown>) => void;
  onMemoryToolCall?: (toolName: string) => void;
  onToolCall?: (toolName: string, author: string) => void;
  onToolResponse?: (toolName: string, response: unknown) => void;
  onFinalText?: (text: string, author: string) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

// Display names for tools — mirrors backend _TOOL_DISPLAY_NAMES
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  advanced_search: 'Twitter 검색 중',
  get_trends: '트렌드 조회 중',
  generate_image: '이미지 생성 중',
  generate_video: '동영상 생성 중',
  generate_audio: '오디오 생성 중',
  analyze_user_image: '첨부 이미지 분석 중',
  memory_get_core_profile: '브랜드 프로필 조회 중',
  memory_update_user_profile: '사용자 프로필 업데이트 중',
  memory_update_brand_voice: '브랜드 보이스 업데이트 중',
  memory_update_domain_profile: '도메인 프로파일 업데이트 중',
  memory_add_domain_knowledge: '도메인 지식 저장 중',
  memory_get_knowledge: '도메인 지식 조회 중',
  memory_add_product: '제품 등록 중',
  memory_get_product: '제품 상세 조회 중',
  memory_update_product: '제품 정보 수정 중',
  memory_update_audience_segment: '타겟 고객 업데이트 중',
  memory_add_audience_trait: '고객 특성 추가 중',
  memory_get_audience_segments: '타겟 세그먼트 조회 중',
  memory_mark_performance_asked: '성과 질문 마킹 중',
  read_skill_md: '📋 스킬 MD 참조 중',
  memory_archive_campaign: '캠페인 저장 중',
  memory_search_campaigns: '캠페인 검색 중',
  memory_get_recent_campaigns: '최근 캠페인 조회 중',
  memory_record_generated_asset: '에셋 저장 중',
  memory_get_assets: '에셋 목록 조회 중',
  memory_get_behavior_insights: '행동 인사이트 분석 중',
  memory_collect_performance: '성과 데이터 기록 중',
  memory_get_performance_pending: '성과 수집 목록 확인 중',
  memory_update_working_summary: '대화 요약 업데이트 중',
  memory_archive_conversation: '대화 기록 저장 중',
  memory_search_conversations: '대화 기록 검색 중',
  instagram_strategist: '📱 Instagram 콘텐츠 생성 중',
  facebook_strategist: '📘 Facebook 콘텐츠 생성 중',
  x_strategist: '🐦 X(Twitter) 콘텐츠 생성 중',
  tiktok_strategist: '🎵 TikTok 콘텐츠 생성 중',
  youtube_strategist: '🎬 YouTube 콘텐츠 생성 중',
  linkedin_strategist: '💼 LinkedIn 콘텐츠 생성 중',
  pinterest_strategist: '📌 Pinterest 콘텐츠 생성 중',
  threads_strategist: '🧵 Threads 콘텐츠 생성 중',
  kakao_strategist: '💬 카카오 콘텐츠 생성 중',
  idea_generation_agent: '💡 아이디어 생성 중',
  content_orchestrator: '🎯 콘텐츠 전략 수립 중',
};

const MEMORY_TOOLS = new Set([
  'memory_get_core_profile',
  'memory_update_human_block',
  'memory_update_persona_block',
  'memory_update_domain_block',
  'memory_update_audience_block',
  'memory_archive_campaign',
  'memory_search_campaigns',
  'memory_get_recent_campaigns',
  'memory_update_working_summary',
  'memory_record_generated_asset',
  'memory_get_assets',
]);

// Main function to send message and handle SSE response
export const sendMessageToAgentSSE = (
  message: string,
  base: Base,
  user_id: string,
  session_id: string,
  callbacks: SSECallbacks,
  imageData?: { mimeType: string; data: string }
) => {
  const socialMediaAgentInput: SocialMediaAgentInput = {
    user_query: message,
    base: base
  };
  console.log('socialMediaAgentInput:', socialMediaAgentInput);
  const parts: MessagePart[] = [{ text: JSON.stringify(socialMediaAgentInput) }];
  if (imageData) {
    parts.push({ inlineData: { mimeType: imageData.mimeType, data: imageData.data } });
  }
  const payload: AgentRequestPayload = {
    appName: "agents",
    userId: user_id,
    sessionId: session_id,
    newMessage: {
      role: "user",
      parts,
    },
    streaming: true
  };

  // Make the POST request and handle the SSE stream
  fetch(`${API_BASE_URL}/run_sse`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(payload)
  }).then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = ''; // Buffer to hold incomplete lines

    function processLine(line: string) {
      if (line.startsWith('data: ')) {
        try {
          const jsonStr = line.slice(6); // Remove 'data: ' prefix
          const data = JSON.parse(jsonStr) as AgentResponse; // AgentResponse is defined above
          console.log('SSE events before filtering:', data);
          // Only keep the streaming data (i.e. partial data). This filter out the following data which has partial=false:
          // 1. FunctionCall events.
          // 2. FunctionResponse events.
          // 3. Final reponse that repeats all historical thoughts/text.
          // Removing this check will also require updating logics in ChatInterface because it messes up the message
          // completion logics.
          // Extract state_delta from ALL events (partial and non-partial)
          // This is critical for real-time reasoning step display
          const anyDelta = data.actions?.state_delta;
          if (anyDelta && Object.keys(anyDelta).length > 0) {
            console.log('[SSE state_delta]', JSON.stringify(anyDelta));
            // Debug: send to server for file logging
            fetch(`${API_BASE_URL}/debug/log_delta`, {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ delta: anyDelta, author: data.author, partial: data.partial, ts: Date.now() }),
            }).catch(() => {});
            if (callbacks.onStateDelta) {
              callbacks.onStateDelta(anyDelta as Record<string, unknown>);
            }
          }

          if (data.partial == true) {
            callbacks.onData(data);
          }
          if (!data.partial) {
            // Non-partial = final event. Do NOT send to onData (would duplicate streamed text).
            // Instead, store final text for onComplete to use for JSON parsing.
            const hasText = data.content?.parts?.some(p => p.text);
            const author = data.author || '';
            if (hasText) {
              // ADK 1.20+: author is always "agents", so store all final texts for JSON parsing
              const finalText = data.content.parts.map(p => p.text || '').join('');
              if (callbacks.onFinalText) {
                callbacks.onFinalText(finalText, author);
              }
            }

            // Handle tool calls — notify for reasoning display
            const fnCall = data.content?.parts?.[0]?.functionCall;
            if (fnCall) {
              if (callbacks.onMemoryToolCall && MEMORY_TOOLS.has(fnCall.name)) {
                callbacks.onMemoryToolCall(fnCall.name);
              }
              if (callbacks.onToolCall) {
                callbacks.onToolCall(fnCall.name, author || '');
              }
            }

            // Handle tool RESPONSES — extract result summaries for rich reasoning
            const fnResponse = data.content?.parts?.[0]?.functionResponse;
            if (fnResponse && callbacks.onToolResponse) {
              callbacks.onToolResponse(fnResponse.name, fnResponse.response);
            }
          }
        } catch (error) {
          console.error('[SSE PARSE ERROR]', error, 'on line:', line);
          if (callbacks.onError) {
            callbacks.onError(error as Error);
          }
        }
      }
    }

    function readStream() {
      reader.read().then(({done, value}) => {
        if (done) {
          // Process any remaining data in the buffer when the stream is closed.
          if (buffer.trim()) {
            processLine(buffer.trim());
          }
          if (callbacks.onComplete) {
            callbacks.onComplete();
          }
          return;
        }

        // Decode the current chunk and add it to the buffer.
        // Using { stream: true } is important for multi-byte characters.
        buffer += decoder.decode(value, { stream: true });

        // Process all complete lines (ending with \n) in the buffer.
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          const line = buffer.substring(0, newlineIndex).trim(); // Get the line
          buffer = buffer.substring(newlineIndex + 1); // Remove the line from the buffer

          if (line) { // Process the line if it's not empty
            processLine(line);
          }
        }
        
        // Continue reading the stream
        readStream();
      }).catch(error => {
        console.error('[SSE ERROR]', error);
        if (callbacks.onError) {
          callbacks.onError(error);
        }
      });
    }

    readStream();
  }).catch(error => {
    console.error('[FETCH ERROR]', error);
    if (callbacks.onError) {
      callbacks.onError(error);
    }
  });

  // Return cleanup function
  return () => {
    // If you had an AbortController, you could call abort() here.
    // For now, we'll just signal completion if the callback exists.
    if (callbacks.onComplete) {
      callbacks.onComplete();
    }
  };
};

// Function to start a new session
// [MemGPT bug-fix Oct 15 2023 — "patch save/load"]
// Uses /sessions/create/{user_id} instead of the default ADK session endpoint.
// This copies persistent memory (memory_u_{userId}) into the new session's
// initial state so that _inject_core_memory callback reads real memory,
// not an empty default — fixing the two-session mismatch.
export const startNewSession = async (userId: string): Promise<string> => {
  const requestUrl = `${API_BASE_URL}/sessions/create/${userId}`;

  try {
    const response = await fetch(requestUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[START SESSION HTTP ERROR ${response.status}]`, errorBody, 'on URL:', requestUrl);
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json() as { session_id: string; user_id: string; memory_loaded: boolean };
    if (!data.session_id) {
      console.error('[START SESSION ERROR]', 'session_id not found in response', data, 'on URL:', requestUrl);
      throw new Error('session_id not found in response.');
    }
    console.log(`[MemGPT] New session ${data.session_id} created, memory_loaded=${data.memory_loaded}`);
    return data.session_id;
  } catch (error) {
    if (error instanceof Error) {
      console.error('[START SESSION FETCH ERROR]', error.message, 'on URL:', requestUrl, error);
      throw error;
    } else {
      const errorMessage = String(error);
      console.error('[START SESSION FETCH ERROR]', errorMessage, 'on URL:', requestUrl, error);
      throw new Error(errorMessage);
    }
  }
};

// [MemGPT bug-fix Oct 15 2023 — "fix summarizer"]
// Syncs conversation session memory back to the persistent memory session.
// Must be called after each conversation turn to ensure working_summary and
// newly archived campaigns are not lost between sessions.
export const syncSessionMemory = async (userId: string, sessionId: string): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/sessions/sync/${userId}/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      console.warn(`[MemGPT] Memory sync failed: ${response.status}`);
    } else {
      const result = await response.json();
      console.log(`[MemGPT] Memory synced: ${result.status}`);
    }
  } catch (error) {
    // Non-fatal — session memory will still persist in ADK's SQLite
    console.warn('[MemGPT] Memory sync error (non-fatal):', error);
  }
};

// Helper function to extract text content from agent response
export const extractTextFromResponse = (response: AgentResponse): string | null => {
  if (response.content?.parts?.[0]?.text) {
    return response.content.parts[0].text;
  }
  return null;
};


// ─── MemGPT Memory API ────────────────────────────────────────────────────────

/**
 * Load the user's persistent MemoryState from the backend.
 * Returns DEFAULT_MEMORY_STATE if no memory exists yet.
 */
export const loadUserMemory = async (userId: string): Promise<MemoryState> => {
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}`);
    if (!response.ok) {
      console.warn(`[Memory] GET /memory/${userId} returned ${response.status}, using default.`);
      return DEFAULT_MEMORY_STATE;
    }
    const data = await response.json();
    return data.memory as MemoryState;
  } catch (error) {
    console.error('[Memory] Failed to load user memory:', error);
    return DEFAULT_MEMORY_STATE;
  }
};

/**
 * Persist the user's full MemoryState to the backend.
 * Called from ProfileBlock when the user saves profile edits.
 */
export const saveUserMemory = async (userId: string, memory: MemoryState): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(memory),
    });
    if (!response.ok) {
      const err = await response.text();
      console.error(`[Memory] PUT /memory/${userId} failed:`, err);
      throw new Error(`Memory save failed: ${response.status}`);
    }
  } catch (error) {
    console.error('[Memory] Failed to save user memory:', error);
    throw error;
  }
};

/**
 * Fetch recent campaigns from Archival Memory.
 */
export const fetchRecentCampaigns = async (
  userId: string,
  limit: number = 10
): Promise<{ campaigns: any[]; total: number }> => {
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/campaigns?limit=${limit}`);
    if (!response.ok) return { campaigns: [], total: 0 };
    return await response.json();
  } catch {
    return { campaigns: [], total: 0 };
  }
};

/**
 * Upload a user image to GCS and record it in the asset_archive.
 * Returns the new GeneratedAsset record.
 */
export const uploadUserAsset = async (
  userId: string,
  file: File,
  platform: string = ''
): Promise<{ asset: any }> => {
  const formData = new FormData();
  formData.append('file', file);
  if (platform) formData.append('platform', platform);

  const response = await fetch(`${API_BASE_URL}/memory/${userId}/assets/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Upload failed: ${response.status} ${err}`);
  }

  return response.json();
};

/**
 * Update performance metrics for a specific campaign in Archival Memory.
 * Accepts partial updates — only provided fields are overwritten.
 */
export const updateCampaignPerformance = async (
  userId: string,
  campaignId: string,
  performance: Partial<{
    views: number; clicks: number; impressions: number; likes: number; shares: number; comments: number;
    engagement_level: string; reach_level: string; conversion_level: string;
    best_platform: string; what_worked: string[]; what_failed: string[];
  }>
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/memory/${userId}/campaigns/${campaignId}/performance`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(performance),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Performance update failed: ${response.status} ${err}`);
  }
};

/**
 * Update performance metrics for a specific asset in asset_gallery.
 * Accepts partial updates — only provided fields are overwritten.
 */
export const updateAssetPerformance = async (
  userId: string,
  assetId: string,
  performance: Partial<{ views: number; clicks: number; impressions: number; likes: number; shares: number; comments: number }>
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/memory/${userId}/assets/${assetId}/performance`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(performance),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Asset performance update failed: ${response.status} ${err}`);
  }
};

/**
 * Delete an asset from the user's asset_archive by asset_id.
 */
export const deleteUserAsset = async (
  userId: string,
  assetId: string,
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/memory/${userId}/assets/${assetId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Delete failed: ${response.status} ${err}`);
  }
};

/**
 * Fetch generated assets (images & videos) from Asset Archive with pagination.
 * asset_type: optional 'image' | 'video' filter.
 */
/**
 * Fetch conversation history (recall_log + conversation_archive merged).
 */
export const fetchConversationHistory = async (
  userId: string,
  options: { limit?: number; page?: number } = {}
): Promise<{ conversations: any[]; total: number; page: number; limit: number; working_summary: string }> => {
  const { limit = 30, page = 0 } = options;
  const params = new URLSearchParams({ limit: String(limit), page: String(page) });
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/conversations?${params}`);
    if (!response.ok) return { conversations: [], total: 0, page, limit, working_summary: '' };
    return await response.json();
  } catch {
    return { conversations: [], total: 0, page, limit, working_summary: '' };
  }
};


/**
 * Fetch generated assets (images & videos) from Asset Archive with pagination.
 * asset_type: optional 'image' | 'video' filter.
 */
export const fetchUserAssets = async (
  userId: string,
  options: { limit?: number; page?: number; asset_type?: 'image' | 'video' } = {}
): Promise<{ assets: any[]; total: number; page: number; limit: number }> => {
  const { limit = 20, page = 0, asset_type } = options;
  const params = new URLSearchParams({ limit: String(limit), page: String(page) });
  if (asset_type) params.set('asset_type', asset_type);
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/assets?${params}`);
    if (!response.ok) return { assets: [], total: 0, page, limit };
    return await response.json();
  } catch {
    return { assets: [], total: 0, page, limit };
  }
};


/**
 * Fetch all products from product_archive.
 */
export const fetchProducts = async (
  userId: string
): Promise<{ products: any[]; total: number }> => {
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/products`);
    if (!response.ok) return { products: [], total: 0 };
    return await response.json();
  } catch {
    return { products: [], total: 0 };
  }
};

/**
 * Fetch a single product by ID.
 */
export const fetchProductDetail = async (
  userId: string,
  productId: string
): Promise<any | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/products/${productId}`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
};

/**
 * Fetch knowledge items, optionally filtered by category.
 */
export const fetchKnowledge = async (
  userId: string,
  category?: string
): Promise<{ knowledge: any[]; total: number }> => {
  try {
    const params = category ? `?category=${encodeURIComponent(category)}` : '';
    const response = await fetch(`${API_BASE_URL}/memory/${userId}/knowledge${params}`);
    if (!response.ok) return { knowledge: [], total: 0 };
    return await response.json();
  } catch {
    return { knowledge: [], total: 0 };
  }
};

// interface ParsedChatResponse {
//     text?: string;
//     imageUrl?: string;
//     videoUrl?: string;
// }

// export function parseChatResponse(responseString: string): ParsedChatResponse {
//     try {
//         console.log('responseString:', responseString);

//         const parsed: ParsedChatResponse = {};

//         // Regex to find Text content (anything after "Text: " and before "Image: " or "Video: " or end of string)
//         const textMatch = responseString.match(/\*\*text:\*\* "(.*?)"/s);
//         if (textMatch && textMatch[1]) {
//             parsed.text = textMatch[1].trim();
//         }

//         // Looks for "URL: " followed by http(s)://... any characters ... .png
//         const imageMatch = responseString.match(/(https?:\/\/[^\s"]+\.png)/i);
//         if (imageMatch && imageMatch[1]) {
//             parsed.imageUrl = imageMatch[1];
//         }

//         // Looks for "URL: " followed by http(s)://... any characters ... .mp4
//         const videoMatch = responseString.match(/(https?:\/\/[^\s"]+\.mp4)/i);
//         if (videoMatch && videoMatch[1]) {
//             parsed.videoUrl = videoMatch[1];
//         }

//         return parsed;
//     } catch (error) {
//         return null;
//     }
// }
