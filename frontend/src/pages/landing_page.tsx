import { useState, useEffect, useRef, useCallback } from 'react';
import type { Base, SocialMediaAgentOutput, OrchestratorChannelOutput } from '../base';
import { channelsToBase } from '../base';
import { startNewSession, sendMessageToAgentSSE, extractTextFromResponse, loadUserMemory, saveUserMemory, syncSessionMemory, fetchUserAssets, TOOL_DISPLAY_NAMES } from '../api';
import {
  PaperAirplaneIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  SparklesIcon,
  Cog6ToothIcon,
  XMarkIcon,
  PhotoIcon,
  ArrowPathIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

import ReactMarkdown, { type Components } from 'react-markdown';
import ArtifactBlocks from '../components/artifact_blocks';
import ContextBlocks from '../components/context_blocks';
import ToolBar from '../components/tool_bar';
import ProfileBlock from '../components/blocks/profile_block';
import CampaignHistoryBlock from '../components/blocks/CampaignHistoryBlock';
import BehaviorGraphBlock from '../components/blocks/BehaviorGraphBlock';
import AppSidebar from '../components/AppSidebar';
import MemoryMindMap from '../components/MemoryMindMap';
import CreationsTab from '../components/CreationsTab';
import ConversationHistoryTab from '../components/ConversationHistoryTab';
import { useAuth } from '../AuthContext';
import { useToast } from '../contexts/ToastContext';
import type { MemoryState, GeneratedAsset } from '../memory';
import { DEFAULT_MEMORY_STATE } from '../memory';

const markdownComponents: Components = {
  a: ({ children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props} className="text-indigo-500 underline hover:text-indigo-700" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

interface Message {
  role: 'user' | 'reasoning' | 'base_content' | 'agent';
  content: string;
  isComplete?: boolean;
  timestamp?: string;
}

const LandingPage = () => {
  const { user, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const userId = user?.userId ?? 'u_guest';

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [memory, setMemory] = useState<MemoryState>(DEFAULT_MEMORY_STATE);

  // Chat
  const [messages, setMessages] = useState<Message[]>([]);
  const [reasoningCollapsed, setReasoningCollapsed] = useState<Record<number, boolean>>({});
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [base, setBase] = useState<Base | null>(null);

  // Artifact panel
  const [showArtifactPanel, setShowArtifactPanel] = useState(false);
  const [panelView, setPanelView] = useState<'artifacts' | 'context' | 'profile' | 'history' | 'conversations' | 'memory' | 'creations' | 'behavior'>('artifacts');
  const [sideSection, setSideSection] = useState<'chat' | 'profile' | 'history' | 'conversations' | 'memory' | 'creations' | 'behavior'>('chat');
  const [isToolbarOpen, setIsToolbarOpen] = useState(false);
  // Context window usage (0–100), updated from SSE state_delta._ctx_usage_pct
  const [ctxUsagePct, setCtxUsagePct] = useState(0);
  // Heartbeat: current tool being executed, updated from SSE state_delta._last_tool
  const [lastTool, setLastTool] = useState<string | null>(null);
  // Track whether tools are actively being called (reasoning phase vs response phase)
  const isToolActiveRef = useRef(false);

  // Asset attachment in chat input
  const [attachedAsset, setAttachedAsset] = useState<GeneratedAsset | null>(null);
  const [showAssetPicker, setShowAssetPicker] = useState(false);
  const [pickerAssets, setPickerAssets] = useState<GeneratedAsset[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const assetPickerRef = useRef<HTMLDivElement>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastChunkId = useRef<string | null>(null);
  const finalTextRef = useRef<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pendingBase = useRef<Base | null>(null);
  const lastSentMessage = useRef<string>('');
  const lastSentBase = useRef<Base | null>(null);

  useEffect(() => {
    setIsInitializing(true);
    setSessionId(null);
    setMemory(DEFAULT_MEMORY_STATE);
    setMessages([]);
    setBase(null);
    setShowArtifactPanel(false);

    const init = async () => {
      try {
        const [sid, mem] = await Promise.all([startNewSession(userId), loadUserMemory(userId)]);
        setSessionId(sid);
        setMemory(mem);
        // Agent-initiated welcome message — personalized based on memory state
        const brandName = mem.human_block.display_name;
        const brandTone = mem.persona_block.tone;
        const industry = mem.domain_block.industry;
        const platforms = mem.audience_block.target_platforms;
        const dp = mem.domain_block;
        const hasCampaigns = mem.total_campaigns > 0;
        const hasProfile = !!(brandName || industry);
        const pendingCount = (mem.performance_pending || []).filter(p => p.ask_count < 2).length;

        // Build domain insight snippets
        const domainSnippets: string[] = [];
        if (dp?.usp) domainSnippets.push(`USP "${dp.usp}"`);
        if (dp?.business_location) domainSnippets.push(`${dp.business_location} 기반`);
        if (dp?.knowledge?.length) {
          const products = dp.knowledge.filter(k => k.key.includes('product') || k.key.includes('service'));
          if (products.length > 0) domainSnippets.push(`제품 ${products.length}개 등록됨`);
        }

        let welcome: string;
        if (hasCampaigns) {
          // 재방문 + 캠페인 이력 있음
          const domainLine = domainSnippets.length > 0 ? `\n${domainSnippets.join(' · ')}` : '';
          const pendingLine = pendingCount > 0 ? `\n\n📊 참고로, 이전 캠페인 **${pendingCount}개**의 성과를 아직 확인하지 못했어요. 결과가 있으시면 알려주세요!` : '';
          welcome = `${brandName ? `**${brandName}**님, ` : ''}안녕하세요! 돌아오셨군요 😊\n\n이전에 **${mem.total_campaigns}개의 캠페인**을 함께 만들었네요.${brandTone ? ` 브랜드 톤 "${brandTone}"도 기억하고 있어요.` : ''}${domainLine}${pendingLine}\n\n오늘은 어떤 이야기를 나눠볼까요? 새로운 캠페인, 전략 논의, 아이디어 브레인스토밍 뭐든 좋아요.`;
        } else if (hasProfile) {
          // 프로필은 있지만 캠페인은 아직 없음
          const profileParts: string[] = [];
          if (industry) profileParts.push(`**${industry}** 업종`);
          if (platforms && platforms.length > 0) profileParts.push(`**${platforms.join(', ')}** 플랫폼`);
          if (brandTone) profileParts.push(`"${brandTone}" 톤`);
          if (dp?.business_location) profileParts.push(`📍 ${dp.business_location}`);
          const profileSummary = profileParts.length > 0 ? `\n\n기억하고 있는 정보: ${profileParts.join(' · ')}` : '';
          welcome = `${brandName ? `**${brandName}**님, ` : ''}안녕하세요! 반갑습니다 ✨${profileSummary}\n\n아직 캠페인을 만들어보지 않으셨네요. 어떤 제품이나 서비스를 홍보하고 싶으신지, 또는 마케팅 전략에 대해 이야기 나눠볼까요?`;
        } else {
          // 완전 신규 사용자
          welcome = `안녕하세요! 소셜 미디어 브랜딩 에이전트입니다 ✨\n\n저는 여러분의 브랜드에 맞는 콘텐츠를 함께 만들어드려요.\n브랜드 전략 논의, 콘텐츠 기획, 포스팅 생성까지 함께할 수 있어요.\n\n편하게 어떤 브랜드나 사업을 하고 계신지 알려주세요. 거기서부터 시작해볼게요!`;
        }
        setMessages([{ role: 'agent', content: welcome, isComplete: true, timestamp: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) }]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setIsInitializing(false);
      }
    };
    init();
  }, [userId]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setIsToolbarOpen(false);
      if (assetPickerRef.current && !assetPickerRef.current.contains(e.target as Node)) setShowAssetPicker(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const openAssetPicker = useCallback(async () => {
    setShowAssetPicker(prev => {
      if (prev) return false;
      return true;
    });
    setPickerLoading(true);
    try {
      const result = await fetchUserAssets(userId, { limit: 20, page: 0, asset_type: 'image' });
      setPickerAssets(result.assets as GeneratedAsset[]);
    } finally {
      setPickerLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleMemorySave = async (updated: MemoryState) => {
    await saveUserMemory(userId, updated);
    setMemory(updated);
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
  };

  const createInitialBase = (goal: string): Base => ({
    goal: goal.trim(),
    trends: { value: { selected_trend: '', trending: [] }, enabled: true },
    audiences: { value: [], enabled: true },
    styles: { value: [], enabled: true },
    guideline: { value: '', enabled: true },
    image_prompt: { value: '', enabled: true },
    video_prompt: { value: '', enabled: true },
    video_narration: { value: '', enabled: true },
    twitter_post: { value: '', enabled: false },
    youtube_post: { value: { video_url: '', title: '', description: '' }, enabled: false },
    tiktok_post: { value: { video_url: '', title: '', description: '' }, enabled: false },
    instagram_post: { value: { image_url: '', post_text: '' }, enabled: false },
    facebook_post: { value: { image_url: '', post_text: '' }, enabled: false },
    linkedin_post: { value: { image_url: '', post_text: '' }, enabled: false },
    pinterest_post: { value: { image_url: '', post_text: '' }, enabled: false },
    threads_post: { value: '', enabled: false },
    kakao_post: { value: { image_url: '', post_text: '' }, enabled: false },
  });

  const makeTimestamp = () =>
    new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

  // ── Summarize tool response for rich reasoning display ──
  const summarizeToolResponse = (toolName: string, response: unknown): string | null => {
    try {
      // response can be a string (JSON) or object
      const resp = typeof response === 'string' ? JSON.parse(response) : response;
      if (!resp || typeof resp !== 'object') return null;
      const r = resp as Record<string, unknown>;

      switch (toolName) {
        case 'memory_get_core_profile': {
          const parts: string[] = [];
          if (r.display_name) parts.push(`브랜드: ${r.display_name}`);
          if (r.industry) parts.push(`업종: ${r.industry}`);
          if (r.tone) parts.push(`톤: ${r.tone}`);
          const domain = r.domain_block as Record<string, unknown> | undefined;
          if (domain?.usp) parts.push(`USP: ${String(domain.usp).slice(0, 50)}`);
          if (domain?.business_location) parts.push(`위치: ${domain.business_location}`);
          return parts.length > 0 ? parts.join(' | ') : '프로필 정보를 확인했습니다.';
        }
        case 'memory_search_campaigns': {
          const results = r.results as Array<Record<string, unknown>> | undefined;
          if (!results || !Array.isArray(results)) return '검색 결과 없음';
          if (results.length === 0) return '유사 캠페인 없음 → 새로운 전략으로 접근합니다.';
          const summaries = results.slice(0, 2).map((c, i) => {
            const goal = String(c.goal || '').slice(0, 40);
            const perf = c.performance as Record<string, unknown> | undefined;
            const worked = (perf?.what_worked as string[])?.slice(0, 2)?.join(', ') || '';
            const failed = (perf?.what_failed as string[])?.slice(0, 2)?.join(', ') || '';
            let s = `[${i + 1}] ${goal}`;
            if (worked) s += ` ✓ ${worked}`;
            if (failed) s += ` ✗ ${failed}`;
            return s;
          });
          return `${results.length}건 검색됨\n    ${summaries.join('\n    ')}`;
        }
        case 'memory_get_behavior_insights': {
          const parts: string[] = [];
          if (r.overall_best_platform) parts.push(`최고 플랫폼: ${r.overall_best_platform}`);
          const worked = r.top_what_worked as string[] | undefined;
          const failed = r.top_what_failed as string[] | undefined;
          if (worked?.length) parts.push(`효과적: ${worked.slice(0, 3).join(', ')}`);
          if (failed?.length) parts.push(`개선필요: ${failed.slice(0, 3).join(', ')}`);
          if (parts.length === 0) return '성과 데이터 축적 중 — 첫 캠페인 이후 분석됩니다.';
          return parts.join(' | ') + '\n  → 이 인사이트를 콘텐츠에 반영합니다.';
        }
        case 'memory_get_assets': {
          const assets = r.assets as Array<Record<string, unknown>> | undefined;
          if (!assets?.length) return '등록된 에셋 없음';
          const userUploaded = assets.filter(a => a.is_user_uploaded).length;
          return `에셋 ${assets.length}개 (사용자 업로드: ${userUploaded}개)`;
        }
        case 'memory_archive_campaign': {
          const cid = r.campaign_id || '';
          return `캠페인이 Archival Memory에 저장됨 (ID: ${String(cid).slice(0, 8)})`;
        }
        case 'memory_record_generated_asset': {
          const atype = r.asset_type || 'image';
          const platform = r.platform || '';
          return `${atype} 에셋 저장 완료${platform ? ` (${platform})` : ''}`;
        }
        case 'memory_collect_performance': {
          return 'Behavior Graph 자동 갱신 완료';
        }
        default: {
          // Strategist results
          if (toolName.endsWith('_strategist')) {
            const channel = toolName.replace('_strategist', '').replace(/_/g, ' ');
            // response is usually a string for AgentTool
            if (typeof response === 'string' && response.length > 20) {
              const preview = response.slice(0, 120).replace(/\n/g, ' ');
              return `${channel} 채널 콘텐츠 생성 완료: ${preview}...`;
            }
            return `${channel} 채널 콘텐츠 생성 완료`;
          }
          return null;
        }
      }
    } catch {
      return null;
    }
  };

  const sendMessage = (messageText: string, currentBase: Base, addUserBubble = true) => {
    if (!messageText.trim() || isLoading || !sessionId) return;

    lastSentMessage.current = messageText;
    lastSentBase.current = currentBase;
    const ts = makeTimestamp();

    setMessages(prev => [
      ...prev,
      ...(addUserBubble ? [{ role: 'user' as const, content: messageText, isComplete: true, timestamp: ts }] : []),
      { role: 'agent' as const, content: '__TYPING__', isComplete: false },
    ]);
    setIsLoading(true);

    finalTextRef.current = null;

    // Track tools seen in this turn to avoid duplicates
    const seenToolsRef = new Set<string>();

    sendMessageToAgentSSE(messageText, currentBase, userId, sessionId, {
      onStateDelta: (delta) => {
        const ctxPct = delta['_ctx_usage_pct'];
        if (typeof ctxPct === 'number') setCtxUsagePct(ctxPct);
        // _last_tool from real state_delta (if ADK sends it)
        const tool = delta['_last_tool'];
        if (typeof tool === 'string') {
          setLastTool(tool);
        }
      },
      onToolCall: (toolName: string) => {
        if (toolName === 'transfer_to_agent') return;
        if (seenToolsRef.has(toolName)) return;
        seenToolsRef.add(toolName);

        const displayName = TOOL_DISPLAY_NAMES[toolName] || toolName.replace(/_/g, ' ');
        setLastTool(displayName);
        isToolActiveRef.current = true;

        setMessages(prev => {
          const last = prev[prev.length - 1];

          // Replace __TYPING__ with reasoning
          if (last?.role === 'agent' && last.content === '__TYPING__') {
            return [...prev.slice(0, -1),
                    { role: 'reasoning' as const, content: `[Step 1]: ${displayName}`, isComplete: false }];
          }

          if (last?.role === 'reasoning' && !last.isComplete) {
            const updated = [...prev];
            const msg = { ...updated[updated.length - 1] };
            const stepNum = (msg.content.match(/\[Step \d+\]/g) || []).length + 1;
            msg.content += (msg.content ? '\n\n' : '') + `[Step ${stepNum}]: ${displayName}`;
            updated[updated.length - 1] = msg;
            return updated;
          }
          if (last?.role === 'agent' && !last.isComplete) return prev;
          return [...prev, { role: 'reasoning' as const, content: `[Step 1]: ${displayName}`, isComplete: false }];
        });
      },
      onToolResponse: (toolName: string, response: unknown) => {
        // Append tool result summary to the last reasoning step
        if (toolName === 'transfer_to_agent' || toolName === 'memory_append_recall') return;
        const summary = summarizeToolResponse(toolName, response);
        if (!summary) return;

        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'reasoning' && !last.isComplete) {
            const updated = [...prev];
            const msg = { ...updated[updated.length - 1] };
            msg.content += `\n  → ${summary}`;
            updated[updated.length - 1] = msg;
            return updated;
          }
          return prev;
        });
      },
      onFinalText: (text, _author) => {
        finalTextRef.current = text;
      },
      onData: (response) => {
        const text = extractTextFromResponse(response);
        const chunkId = response.id;
        if (!text || lastChunkId.current === chunkId) return;
        lastChunkId.current = chunkId;

        // ADK 1.20+: author is always "agents" (app name).
        // Use isToolActiveRef to distinguish reasoning (tool phase) vs agent response.
        // When text arrives, tools are no longer actively being called → close reasoning.
        setMessages(prev => {
          const last = prev[prev.length - 1];

          // If reasoning is active → close reasoning, start agent message
          if (last?.role === 'reasoning' && !last.isComplete) {
            isToolActiveRef.current = false;
            return [...prev.slice(0, -1), { ...last, isComplete: true },
                    { role: 'agent' as const, content: text, isComplete: false }];
          }

          // Replace typing indicator with actual text
          if (last?.role === 'agent' && last.content === '__TYPING__') {
            return [...prev.slice(0, -1), { ...last, content: text }];
          }

          // Append to existing agent message
          if (last?.role === 'agent' && !last.isComplete) {
            return [...prev.slice(0, -1), { ...last, content: last.content + text }];
          }

          return [...prev, { role: 'agent' as const, content: text, isComplete: false }];
        });
      },
      onError: (err) => {
        console.error('Agent error:', err);
        setMessages(prev => [...prev, { role: 'agent', content: '__ERROR__오류가 발생했습니다. 다시 시도해주세요.', isComplete: true, timestamp: makeTimestamp() }]);
        setIsLoading(false);
      },
      onComplete: () => {
        const completeTs = makeTimestamp();
        setMessages(prev => {
          const msgs = [...prev];
          const last = msgs[msgs.length - 1];

          // Mark reasoning as complete
          for (const m of msgs) {
            if (m.role === 'reasoning' && !m.isComplete) {
              if (!m.content.trim()) { /* will be cleaned below */ }
              else m.isComplete = true;
            }
          }

          if (last?.role === 'agent') {
            last.isComplete = true;
            if (!last.timestamp) last.timestamp = completeTs;

            // ── Parse orchestrator channels JSON → update Base for previews ──
            // Use finalTextRef (complete non-partial text) if available, fallback to streamed content
            const candidateTexts = [finalTextRef.current, last.content.trim()].filter(Boolean) as string[];
            let parsed: OrchestratorChannelOutput | null = null;

            for (const raw of candidateTexts) {
              if (parsed) break;
              try {
                let content = raw;
                // Strip markdown code fences
                if (content.startsWith('```json')) {
                  content = content.replace(/^```json\s*/, '').replace(/\s*```$/, '');
                } else if (content.startsWith('```')) {
                  content = content.replace(/^```\s*/, '').replace(/\s*```$/, '');
                }

                // Try parsing whole content as JSON
                try {
                  const obj = JSON.parse(content);
                  if (obj.channels && typeof obj.channels === 'object') parsed = obj;
                } catch {
                  // Try extracting JSON from mixed content
                  const braceStart = content.indexOf('{');
                  const braceEnd = content.lastIndexOf('}');
                  if (braceStart >= 0 && braceEnd > braceStart) {
                    try {
                      const obj = JSON.parse(content.substring(braceStart, braceEnd + 1));
                      if (obj.channels && typeof obj.channels === 'object') parsed = obj;
                    } catch { /* not valid JSON */ }
                  }
                }
              } catch { /* skip */ }
            }

            if (parsed) {
              // Update base state with channel data → triggers ArtifactBlocks re-render
              setTimeout(() => {
                setBase(prevBase => {
                  const fallback: Base = prevBase || ({} as Base);
                  return channelsToBase(parsed!, fallback);
                });
                // Open artifact panel to show previews
                setShowArtifactPanel(true);
                setPanelView('artifacts');
              }, 0);
              // Replace raw JSON in chat with human-readable agent_response
              if (parsed.agent_response) {
                last.content = parsed.agent_response;
              }
            }

            // Reset finalTextRef for next turn
            finalTextRef.current = null;
          } else if (last?.role === 'reasoning' && !last.isComplete) {
            if (!last.content.trim()) return msgs.slice(0, -1);
            last.isComplete = true;
          }

          // Remove empty reasoning messages
          return msgs.filter(m => !(m.role === 'reasoning' && !m.content.trim()));
        });
        setIsLoading(false);
        setLastTool(null);
        // Sync memory to persistent store, then reload so UI reflects any updates
        if (sessionId) {
          syncSessionMemory(userId, sessionId).then(() => {
            loadUserMemory(userId).then(fresh => {
              setMemory(fresh);
              showToast('메모리 동기화 완료', 'success');
            });
          });
        }
      },
    });
  };

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() || isLoading || !sessionId) return;
    const msg = inputMessage;
    setInputMessage('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    // If an asset is attached, prepend a reference note so the agent can use it
    const asset = attachedAsset;
    setAttachedAsset(null);
    setShowAssetPicker(false);

    const fullMsg = asset
      ? `[참조 에셋: ${asset.local_filename || asset.asset_id} — URL: ${asset.gcs_url}]\n\n${msg}`
      : msg;

    sendMessage(fullMsg, base || pendingBase.current || createInitialBase(msg));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  // ─── Reasoning block ─────────────────────────────────────────────────
  const renderReasoningBlock = (msg: Message, idx: number) => {
    const collapsed = reasoningCollapsed[idx] ?? msg.isComplete; // 완료 시 접힘
    return (
      <div key={idx} className="w-full my-3">
        <button
          onClick={() => setReasoningCollapsed(p => ({ ...p, [idx]: !collapsed }))}
          className="group flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors"
        >
          <div className={`flex items-center justify-center w-5 h-5 rounded ${!msg.isComplete ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-500'}`}>
            {collapsed ? <ChevronRightIcon className="h-3.5 w-3.5" /> : <ChevronDownIcon className="h-3.5 w-3.5" />}
          </div>
          <SparklesIcon className={`h-4 w-4 ${!msg.isComplete ? 'text-indigo-500 animate-pulse' : 'text-gray-400'}`} />
          <span className={!msg.isComplete ? 'text-indigo-600' : 'text-gray-500'}>
            {!msg.isComplete
              ? (lastTool ? lastTool : '생각하는 중...')
              : '사고 과정'}
          </span>
          {!msg.isComplete && (
            <span className="flex space-x-1 ml-1">
              {[0, 150, 300].map(d => <span key={d} className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />)}
            </span>
          )}
        </button>
        {!collapsed && (
          <div className="mt-2 ml-7 p-3 text-sm text-gray-600 border-l-2 border-indigo-200 bg-gradient-to-r from-indigo-50/50 to-transparent rounded-r-lg">
            <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
            {!msg.isComplete && <span className="inline-block w-2 h-4 bg-indigo-400 animate-pulse" />}
          </div>
        )}
      </div>
    );
  };

  // ─── Onboarding checklist for new users ──────────────────────────────
  const onboardingSteps = [
    {
      label: '브랜드명 입력',
      done: !!memory.human_block.display_name,
      suggestion: '안녕하세요! 저희 브랜드 이름은 ',
    },
    {
      label: '업종 설정',
      done: !!memory.domain_block.industry,
      suggestion: '저희 업종은 ',
    },
    {
      label: '톤 설정',
      done: !!memory.persona_block.tone,
      suggestion: '브랜드 톤은 친근하고 전문적인 느낌으로 해주세요',
    },
    {
      label: '첫 캠페인 생성',
      done: memory.total_campaigns > 0,
      suggestion: '인스타그램에 올릴 신제품 홍보 캠페인을 만들어주세요',
    },
  ];
  const allOnboardingDone = onboardingSteps.every(s => s.done);
  const showOnboarding = !isInitializing && !allOnboardingDone && memory.total_campaigns === 0;

  const renderOnboardingChecklist = () => {
    if (!showOnboarding) return null;
    return (
      <div className="mx-5 mt-4 mb-2 bg-indigo-50 border border-indigo-100 rounded-xl p-4">
        <p className="text-sm font-semibold text-indigo-700 mb-3">시작 가이드</p>
        <div className="space-y-2">
          {onboardingSteps.map((step, i) => (
            <button
              key={i}
              disabled={step.done || isLoading}
              onClick={() => {
                if (!step.done && !isLoading) {
                  setInputMessage(step.suggestion);
                  textareaRef.current?.focus();
                }
              }}
              className={`flex items-center gap-2.5 w-full text-left px-2 py-1.5 rounded-lg transition-colors ${
                step.done
                  ? 'cursor-default'
                  : 'hover:bg-indigo-100/60 cursor-pointer'
              }`}
            >
              {step.done ? (
                <CheckCircleIcon className="w-5 h-5 text-green-500 shrink-0" />
              ) : (
                <span className="flex items-center justify-center w-5 h-5 rounded-full border-2 border-gray-300 text-gray-300 text-xs shrink-0">
                  {i + 1}
                </span>
              )}
              <span className={`text-sm ${step.done ? 'text-gray-400 line-through' : 'text-gray-700'}`}>
                {step.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    );
  };

  // ─── Skeleton loading for artifact panel ────────────────────────────
  const renderArtifactSkeleton = () => (
    <ul role="list" className="grid grid-cols-1 gap-x-6 gap-y-6 lg:grid-cols-2">
      {[0, 1, 2].map(i => (
        <li key={i} className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-gray-200" />
            <div className="h-4 w-24 bg-gray-200 rounded" />
          </div>
          <div className="w-full h-36 bg-gray-100 rounded-lg mb-4" />
          <div className="space-y-2">
            <div className="h-3 bg-gray-200 rounded w-full" />
            <div className="h-3 bg-gray-200 rounded w-4/5" />
            <div className="h-3 bg-gray-100 rounded w-3/5" />
          </div>
          <div className="flex gap-2 mt-4">
            <div className="h-5 w-16 bg-gray-100 rounded-full" />
            <div className="h-5 w-20 bg-gray-100 rounded-full" />
            <div className="h-5 w-14 bg-gray-100 rounded-full" />
          </div>
        </li>
      ))}
    </ul>
  );

  // ─── Context window progress bar ─────────────────────────────────────
  const renderContextBar = () => {
    // Only show when there's meaningful usage (> 5%)
    if (ctxUsagePct <= 5) return null;
    const pct = Math.min(ctxUsagePct, 100);
    const isWarning = pct >= 70 && pct < 90;
    const isCritical = pct >= 90;
    const barColor = isCritical
      ? 'bg-red-500'
      : isWarning
      ? 'bg-amber-400'
      : 'bg-indigo-400';
    const textColor = isCritical
      ? 'text-red-500'
      : isWarning
      ? 'text-amber-500'
      : 'text-gray-400';
    const label = isCritical
      ? '컨텍스트 한계 근접 — 자동 압축 예정'
      : isWarning
      ? '컨텍스트 70% 이상 — 곧 압축됩니다'
      : '컨텍스트 사용 중';

    return (
      <div className="px-1 pb-2">
        <div className="flex items-center justify-between mb-1">
          <span className={`text-[10px] font-medium ${textColor}`}>{label}</span>
          <span className={`text-[10px] tabular-nums ${textColor}`}>{pct.toFixed(0)}%</span>
        </div>
        <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  };

  // ─── Input bar ───────────────────────────────────────────────────────
  const renderInput = (placeholder = '메시지를 입력하세요...') => (
    <div className="shrink-0 border-t border-gray-100 bg-white px-4 pt-3 pb-4">
      {renderContextBar()}

      {/* Attached asset preview */}
      {attachedAsset && (
        <div className="flex items-center gap-2 mb-2 px-1">
          <img
            src={attachedAsset.gcs_url}
            alt={attachedAsset.local_filename || 'asset'}
            className="w-10 h-10 rounded-lg object-cover border border-gray-200"
          />
          <span className="text-xs text-gray-500 truncate max-w-[60%]">{attachedAsset.local_filename || attachedAsset.asset_id.slice(0, 8)}</span>
          <button
            type="button"
            onClick={() => setAttachedAsset(null)}
            className="ml-auto text-gray-400 hover:text-gray-600 transition-colors"
            title="첨부 해제"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Asset picker popover */}
      {showAssetPicker && (
        <div ref={assetPickerRef} className="mb-2 p-3 bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
          {pickerLoading ? (
            <div className="flex items-center justify-center py-4 text-xs text-gray-400">로딩 중...</div>
          ) : pickerAssets.length === 0 ? (
            <div className="flex items-center justify-center py-4 text-xs text-gray-400">에셋이 없습니다</div>
          ) : (
            <div className="grid grid-cols-4 gap-2">
              {pickerAssets.map(a => (
                <button
                  key={a.asset_id}
                  type="button"
                  onClick={() => { setAttachedAsset(a); setShowAssetPicker(false); }}
                  className={`relative rounded-lg overflow-hidden aspect-square border-2 transition-all hover:opacity-90 ${
                    attachedAsset?.asset_id === a.asset_id ? 'border-indigo-500' : 'border-transparent'
                  }`}
                  title={a.local_filename || a.asset_id}
                >
                  <img src={a.gcs_url} alt={a.local_filename || ''} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="flex flex-col bg-gray-50 border border-gray-200 rounded-2xl focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
          <textarea
            ref={textareaRef}
            value={inputMessage}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            placeholder={isLoading ? '에이전트가 생각 중...' : placeholder}
            rows={1}
            className="w-full p-4 pb-2 text-sm bg-transparent border-none outline-none resize-none text-gray-900 placeholder-gray-400"
            disabled={isLoading || isInitializing || !!error}
          />
          <div className="flex items-center justify-between px-4 pb-3">
            {/* Asset picker button */}
            <button
              type="button"
              onClick={openAssetPicker}
              disabled={isLoading || isInitializing || !!error}
              className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all ${
                showAssetPicker
                  ? 'bg-indigo-100 text-indigo-600'
                  : attachedAsset
                  ? 'bg-indigo-50 text-indigo-500'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              } disabled:opacity-40`}
              title="에셋 참조"
            >
              <PhotoIcon className="w-4 h-4" />
              <span>에셋 참조</span>
            </button>

            <button type="submit"
              disabled={isLoading || isInitializing || !!error || !inputMessage.trim()}
              className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all ${
                isLoading || isInitializing || !!error || !inputMessage.trim()
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm'
              }`}>
              <PaperAirplaneIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
        {isInitializing && <p className="mt-2 text-center text-xs text-gray-400">세션 초기화 중...</p>}
        {error && (
          <button onClick={() => window.location.reload()} className="mt-2 text-xs text-red-500 w-full text-center">
            연결 오류 — 클릭하여 재시도
          </button>
        )}
      </form>
    </div>
  );

  // ─── RENDER ──────────────────────────────────────────────────────────
  return (
    <div className="h-screen bg-white flex overflow-hidden">
      <AppSidebar
        memory={memory}
        activeSection={sideSection}
        onSectionChange={(s) => {
          setSideSection(s);
          if (s === 'chat') {
            // Keep artifact panel open if content was generated, restore to artifacts view
            if (base) {
              setShowArtifactPanel(true);
              setPanelView('artifacts');
            } else {
              setShowArtifactPanel(false);
            }
          }
          if (s === 'profile') { setShowArtifactPanel(true); setPanelView('profile'); loadUserMemory(userId).then(setMemory); }
          if (s === 'history') { setShowArtifactPanel(true); setPanelView('history'); loadUserMemory(userId).then(setMemory); }
          if (s === 'conversations') { setShowArtifactPanel(true); setPanelView('conversations'); }
          if (s === 'memory') { setShowArtifactPanel(true); setPanelView('memory'); }
          if (s === 'creations') { setShowArtifactPanel(true); setPanelView('creations'); }
          if (s === 'behavior') { setShowArtifactPanel(true); setPanelView('behavior'); loadUserMemory(userId).then(setMemory); }
        }}
      />

      <div className="flex flex-1 overflow-hidden">

        {/* ── Artifact panel — slides in when content generation starts ── */}
        <div className={`
          overflow-hidden flex flex-col border-r border-gray-200 bg-gray-50
          transition-all duration-300 ease-in-out
          ${showArtifactPanel ? 'w-[60%]' : 'w-0'}
        `}>
          {showArtifactPanel && (
            <>
              {/* Panel header */}
              <div className="shrink-0 flex items-center justify-between px-6 py-3 border-b border-gray-100 bg-white">
                <span className="text-sm font-semibold text-gray-700">
                  {panelView === 'artifacts' ? '아티팩트' : panelView === 'context' ? '컨텍스트' : panelView === 'profile' ? '브랜드 프로필' : panelView === 'history' ? '캠페인 히스토리' : panelView === 'conversations' ? '대화 히스토리' : panelView === 'memory' ? '메모리 맵' : panelView === 'behavior' ? 'Behavior Graph' : 'Assets'}
                </span>
                <div className="flex items-center gap-2">
                  {(panelView === 'artifacts' || panelView === 'context') && base && (
                    <div className="relative" ref={dropdownRef}>
                      <button onClick={() => setIsToolbarOpen(!isToolbarOpen)}
                        className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all ${
                          isToolbarOpen ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                        }`}>
                        <Cog6ToothIcon className="w-4 h-4" />
                      </button>
                      {isToolbarOpen && (
                        <div className="absolute right-0 top-full mt-2 w-60 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                          <div className="p-4"><ToolBar base={base} setBase={setBase as any} /></div>
                        </div>
                      )}
                    </div>
                  )}
                  <button onClick={() => { setShowArtifactPanel(false); setSideSection('chat'); }}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 transition-all">
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {/* Panel content */}
              <div className={`flex-1 overflow-hidden flex flex-col ${panelView === 'memory' || panelView === 'creations' || panelView === 'conversations' || panelView === 'behavior' ? '' : 'overflow-y-auto px-6 pb-6 pt-4'}`}>
                {panelView === 'behavior' ? (
                  <div className="overflow-y-auto px-6 pb-6 pt-4 flex-1">
                    <BehaviorGraphBlock
                      behaviorGraph={memory.behavior_graph ?? { nodes: [], edges: [], platform_best_content_type: {}, topic_performance_summary: {}, overall_best_platform: '' }}
                      campaigns={memory.campaign_archive}
                    />
                  </div>
                ) : panelView === 'conversations' ? (
                  <ConversationHistoryTab userId={userId} memory={memory} />
                ) : panelView === 'creations' ? (
                  <CreationsTab userId={userId} />
                ) : panelView === 'memory' ? (
                  <MemoryMindMap
                    initialMemory={memory}
                    userId={userId}
                    isActive={isLoading}
                    onEditClick={() => { setSideSection('profile'); setPanelView('profile'); }}
                  />
                ) : panelView === 'profile' ? (
                  <div className="w-full">
                    <ProfileBlock memory={memory} onSave={handleMemorySave} userId={userId} initialTab="identity" />
                  </div>
                ) : panelView === 'history' ? (
                  <CampaignHistoryBlock
                    memory={memory}
                    userId={userId}
                    onMemoryRefresh={() => loadUserMemory(userId).then(setMemory)}
                  />
                ) : panelView === 'artifacts' ? (
                  base ? (
                    <ul role="list" className="grid grid-cols-1 gap-x-6 gap-y-6 lg:grid-cols-2">
                      <ArtifactBlocks base={base} campaigns={memory.campaign_archive} />
                    </ul>
                  ) : isLoading ? (
                    renderArtifactSkeleton()
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center text-gray-400">
                        <SparklesIcon className="w-10 h-10 mx-auto mb-3 text-indigo-200" />
                        <p className="text-sm font-medium text-gray-500 mb-1">아직 생성된 콘텐츠가 없습니다</p>
                        <p className="text-xs text-gray-400">채팅으로 소셜 미디어 콘텐츠를 생성해보세요</p>
                      </div>
                    </div>
                  )
                ) : panelView === 'context' ? (
                  base ? (
                    <ul role="list" className="grid grid-cols-1 gap-x-6 gap-y-6 lg:grid-cols-2">
                      <ContextBlocks base={base} setBase={setBase as any} />
                    </ul>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center text-gray-400">
                        <SparklesIcon className="w-10 h-10 mx-auto mb-3 text-indigo-200" />
                        <p className="text-sm font-medium text-gray-500 mb-1">컨텍스트 정보가 없습니다</p>
                        <p className="text-xs text-gray-400">콘텐츠를 생성하면 목표, 타겟 오디언스 등 컨텍스트 정보가 표시됩니다</p>
                      </div>
                    </div>
                  )
                ) : null}
              </div>
            </>
          )}
        </div>

        {/* ── Chat panel — always visible ── */}
        <div className={`flex flex-col bg-white overflow-hidden transition-all duration-300 ease-in-out ${
          showArtifactPanel ? 'w-[40%]' : 'w-full'
        }`}>
          {/* Header */}
          <div className="shrink-0 px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
            <SparklesIcon className="w-4 h-4 text-indigo-500" />
            <span className="text-sm font-semibold text-gray-700">AI 에이전트</span>
            {isAuthenticated && memory.total_campaigns > 0 && (
              <span className="ml-2 text-[10px] text-indigo-400 bg-indigo-50 px-2 py-0.5 rounded-full">메모리 활성</span>
            )}
            {!showArtifactPanel && base && (
              <button onClick={() => setShowArtifactPanel(true)}
                className="ml-auto flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors">
                <SparklesIcon className="w-3.5 h-3.5" />
                아티팩트 보기
              </button>
            )}
          </div>

          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto">
            {isInitializing ? (
              <div className="h-full flex items-center justify-center">
                <div className="flex items-center gap-2 text-gray-400 text-sm">
                  <span className="flex space-x-1">
                    {[0, 150, 300].map(d => <span key={d} className="w-2 h-2 bg-indigo-300 rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />)}
                  </span>
                  <span>준비 중...</span>
                </div>
              </div>
            ) : (
              <div className="px-5 py-6 space-y-1">
                {/* Onboarding checklist for new users */}
                {renderOnboardingChecklist()}
                {messages.map((msg, idx) => {
                  if (msg.role === 'reasoning') return renderReasoningBlock(msg, idx);

                  if (msg.role === 'base_content') {
                    if (!msg.isComplete) return null;
                    return (
                      <div key={idx} className="w-full my-2 ml-7">
                        <button onClick={() => {
                          try {
                            const json = msg.content.replace(/^```json/, '').replace(/```$/, '');
                            const out: SocialMediaAgentOutput = JSON.parse(json);
                            if (out.is_updated) { setBase(out.updated_base); setShowArtifactPanel(true); }
                          } catch (e) { console.error(e); }
                        }} className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 text-xs font-medium transition-colors">
                          체크포인트 복원
                        </button>
                      </div>
                    );
                  }

                  if (msg.role === 'user') {
                    return (
                      <div key={idx} className="flex flex-col items-end my-4">
                        <div className="max-w-[85%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3 text-sm">
                          <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.timestamp && <span className="text-[10px] text-gray-400 mt-1">{msg.timestamp}</span>}
                      </div>
                    );
                  }

                  // Typing indicator
                  if (msg.content === '__TYPING__') {
                    return (
                      <div key={idx} className="my-4">
                        <div className="flex items-start gap-3">
                          <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mt-0.5">
                            <SparklesIcon className="w-4 h-4 text-white" />
                          </div>
                          <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
                            <span className="flex space-x-1">
                              {[0, 150, 300].map(d => <span key={d} className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />)}
                            </span>
                            <span>에이전트가 응답을 준비하고 있습니다...</span>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  const isErrorMsg = msg.content.startsWith('__ERROR__');
                  const displayContent = isErrorMsg ? msg.content.replace('__ERROR__', '') : msg.content;

                  return (
                    <div key={idx} className="my-4">
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mt-0.5">
                          <SparklesIcon className="w-4 h-4 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="prose prose-sm max-w-none text-gray-800">
                            <ReactMarkdown components={markdownComponents}>{displayContent}</ReactMarkdown>
                            {!msg.isComplete && <span className="inline-block w-2 h-5 bg-indigo-500 animate-pulse ml-0.5" />}
                          </div>
                          {isErrorMsg && lastSentMessage.current && (
                            <button
                              onClick={() => {
                                if (lastSentMessage.current && lastSentBase.current) {
                                  sendMessage(lastSentMessage.current, lastSentBase.current, false);
                                }
                              }}
                              disabled={isLoading}
                              className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50"
                            >
                              <ArrowPathIcon className="w-3.5 h-3.5" />
                              다시 시도
                            </button>
                          )}
                          {msg.timestamp && msg.isComplete && <span className="text-[10px] text-gray-400 mt-1 block">{msg.timestamp}</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {renderInput('메시지를 입력하세요...')}
        </div>
      </div>

    </div>
  );
};

export default LandingPage;
