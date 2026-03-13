import { useState, useEffect, useRef, useCallback } from 'react';
import type { Base, SocialMediaAgentOutput } from '../base';
import { startNewSession, sendMessageToAgentSSE, extractTextFromResponse, loadUserMemory, saveUserMemory, syncSessionMemory, fetchUserAssets } from '../api';
import {
  PaperAirplaneIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  SparklesIcon,
  Cog6ToothIcon,
  XMarkIcon,
  PhotoIcon,
} from '@heroicons/react/24/outline';

import ReactMarkdown, { type Components } from 'react-markdown';
import ArtifactBlocks from '../components/artifact_blocks';
import ContextBlocks from '../components/context_blocks';
import ToolBar from '../components/tool_bar';
import ProfileBlock from '../components/blocks/profile_block';
import AppSidebar from '../components/AppSidebar';
import MemoryMindMap from '../components/MemoryMindMap';
import CreationsTab from '../components/CreationsTab';
import LoginModal from '../components/LoginModal';
import { useAuth } from '../AuthContext';
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
}

const LandingPage = () => {
  const { user, isAuthenticated } = useAuth();
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
  const [panelView, setPanelView] = useState<'artifacts' | 'context' | 'profile' | 'memory' | 'creations'>('artifacts');
  const [sideSection, setSideSection] = useState<'chat' | 'profile' | 'history' | 'memory' | 'creations'>('chat');
  const [isToolbarOpen, setIsToolbarOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  // Context window usage (0–100), updated from SSE state_delta._ctx_usage_pct
  const [ctxUsagePct, setCtxUsagePct] = useState(0);
  // Heartbeat: current tool being executed, updated from SSE state_delta._last_tool
  const [lastTool, setLastTool] = useState<string | null>(null);
  // Asset attachment in chat input
  const [attachedAsset, setAttachedAsset] = useState<GeneratedAsset | null>(null);
  const [showAssetPicker, setShowAssetPicker] = useState(false);
  const [pickerAssets, setPickerAssets] = useState<GeneratedAsset[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const assetPickerRef = useRef<HTMLDivElement>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastChunkId = useRef<string | null>(null);
  const formattedBaseContent = useRef('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pendingBase = useRef<Base | null>(null);

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
        // Agent-initiated welcome message
        const isReturning = mem.total_campaigns > 0;
        const brandTone = mem.core_profile.brand_voice.tone;
        let welcome: string;
        if (isReturning) {
          welcome = `안녕하세요! 돌아오셨군요 😊\n\n이전에 **${mem.total_campaigns}개의 캠페인**을 함께 만들었네요.${brandTone ? ` 브랜드 톤 "${brandTone}"도 기억하고 있어요.` : ''}\n\n오늘은 어떤 콘텐츠를 만들어 볼까요? 새로운 캠페인을 시작하거나, 기존 브랜드 전략을 이어가도 좋아요.`;
        } else {
          welcome = `안녕하세요! 소셜 미디어 브랜딩 에이전트입니다 ✨\n\n저는 여러분의 브랜드에 맞는 콘텐츠를 함께 만들어드려요.\n\n**먼저 몇 가지 여쭤볼게요 —**\n어떤 브랜드나 제품을 홍보하려고 하시나요? 그리고 주로 어떤 소셜 미디어 플랫폼을 사용하시나요? (인스타그램, 유튜브, 틱톡, 트위터 등)\n\n편하게 말씀해 주시면 최적의 콘텐츠 전략을 제안해드릴게요!`;
        }
        setMessages([{ role: 'agent', content: welcome, isComplete: true }]);
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
    twitter_post: { value: '', enabled: true },
    youtube_post: { value: { video_url: '', title: '', description: '' }, enabled: true },
    tiktok_post: { value: { video_url: '', title: '', description: '' }, enabled: true },
    instagram_post: { value: { image_url: '', post_text: '' }, enabled: true },
  });

  const sendMessage = (messageText: string, currentBase: Base, addUserBubble = true) => {
    if (!messageText.trim() || isLoading || !sessionId) return;

    setMessages(prev => [
      ...prev,
      ...(addUserBubble ? [{ role: 'user' as const, content: messageText, isComplete: true }] : []),
      { role: 'reasoning' as const, content: '', isComplete: false },
    ]);
    setIsLoading(true);
    formattedBaseContent.current = '';

    sendMessageToAgentSSE(messageText, currentBase, userId, sessionId, {
      onStateDelta: (delta) => {
        const ctxPct = delta['_ctx_usage_pct'];
        if (typeof ctxPct === 'number') setCtxUsagePct(ctxPct);
        const tool = delta['_last_tool'];
        if (typeof tool === 'string') setLastTool(tool);
      },
      onData: (response) => {

        const text = extractTextFromResponse(response);
        const author = response.author;
        const chunkId = response.id;
        if (!text || lastChunkId.current === chunkId) return;
        lastChunkId.current = chunkId;

        if (author === 'social_media_branding_content_agent') {
          // Content pipeline started → open artifact panel
          setShowArtifactPanel(true);
          setPanelView('artifacts');
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'reasoning' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, content: last.content + text }];
            return prev;
          });
        } else if (author === 'format_agent') {
          formattedBaseContent.current += text;
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'reasoning' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, isComplete: true }, { role: 'base_content', content: text, isComplete: false }];
            if (last?.role === 'base_content' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, content: last.content + text }];
            return prev;
          });
        } else if (author === 'response_agent') {
          if (formattedBaseContent.current) {
            try {
              const json = formattedBaseContent.current.replace(/^```json/, '').replace(/```$/, '');
              const out: SocialMediaAgentOutput = JSON.parse(json);
              if (out.is_updated) { setBase(out.updated_base); pendingBase.current = out.updated_base; }
            } catch (e) { console.error('parse error', e); }
            formattedBaseContent.current = '';
          }
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'base_content' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, isComplete: true }, { role: 'agent', content: text, isComplete: false }];
            if (last?.role === 'agent' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, content: last.content + text }];
            return prev;
          });
        } else if (author === 'general_chat_agent') {
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'reasoning' && !last.isComplete) {
              if (!last.content.trim())
                return [...prev.slice(0, -1), { role: 'agent' as const, content: text, isComplete: false }];
              return [...prev.slice(0, -1), { ...last, isComplete: true }, { role: 'agent' as const, content: text, isComplete: false }];
            }
            if (last?.role === 'agent' && !last.isComplete)
              return [...prev.slice(0, -1), { ...last, content: last.content + text }];
            return prev;
          });
        }
      },
      onError: (err) => {
        console.error('Agent error:', err);
        setMessages(prev => [...prev, { role: 'agent', content: '오류가 발생했습니다. 다시 시도해주세요.', isComplete: true }]);
        setIsLoading(false);
      },
      onComplete: () => {
        setMessages(prev => {
          const msgs = [...prev];
          const last = msgs[msgs.length - 1];
          if (last?.role === 'agent') last.isComplete = true;
          else if (last?.role === 'reasoning' && !last.isComplete) {
            if (!last.content.trim()) return msgs.slice(0, -1);
            last.isComplete = true;
          }
          return msgs;
        });
        setIsLoading(false);
        setLastTool(null);
        // Sync memory to persistent store, then reload so UI reflects any updates
        if (sessionId) {
          syncSessionMemory(userId, sessionId).then(() => {
            loadUserMemory(userId).then(fresh => setMemory(fresh));
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
    const collapsed = reasoningCollapsed[idx] ?? msg.isComplete;
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
              ? (lastTool && idx === messages.findIndex(m => m.role === 'reasoning' && !m.isComplete)
                  ? lastTool
                  : '생각하는 중...')
              : '사고 과정'}
          </span>
          {!msg.isComplete && (
            <span className="flex space-x-1 ml-1">
              {[0, 150, 300].map(d => <span key={d} className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />)}
            </span>
          )}
        </button>
        <div className={`reasoning-content ${collapsed ? 'reasoning-collapsed' : 'reasoning-expanded'}`}>
          <div className="mt-2 ml-7 p-3 text-sm text-gray-600 border-l-2 border-indigo-200 bg-gradient-to-r from-indigo-50/50 to-transparent rounded-r-lg">
            <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
            {!msg.isComplete && <span className="inline-block w-2 h-4 bg-indigo-400 animate-pulse ml-0.5" />}
          </div>
        </div>
      </div>
    );
  };

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
          if (s === 'profile') { setShowArtifactPanel(true); setPanelView('profile'); }
          if (s === 'memory') { setShowArtifactPanel(true); setPanelView('memory'); }
          if (s === 'creations') { setShowArtifactPanel(true); setPanelView('creations'); }
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
                <div className="flex items-center bg-gray-100 rounded-lg p-1">
                  {(['artifacts', 'context', 'profile', 'memory', 'creations'] as const).map(v => (
                    <button key={v} onClick={() => setPanelView(v)}
                      className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-all ${
                        panelView === v ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'
                      }`}>
                      {v === 'artifacts' ? '아티팩트' : v === 'context' ? '컨텍스트' : v === 'profile' ? '✦ 프로필' : v === 'memory' ? '🧠 메모리' : '🎨 크리에이션'}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  {base && (
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
                  <button onClick={() => setShowArtifactPanel(false)}
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 transition-all">
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {/* Panel content */}
              <div className={`flex-1 overflow-hidden flex flex-col ${panelView === 'memory' ? '' : 'overflow-y-auto px-6 pb-6 pt-4'}`}>
                {panelView === 'creations' ? (
                  <CreationsTab userId={userId} />
                ) : panelView === 'memory' ? (
                  <MemoryMindMap
                    initialMemory={memory}
                    userId={userId}
                    isActive={isLoading}
                    onEditClick={() => { setPanelView('profile'); }}
                  />
                ) : panelView === 'profile' ? (
                  <ul role="list" className="grid grid-cols-1 gap-x-6 gap-y-6 lg:grid-cols-2">
                    <ProfileBlock memory={memory} onSave={handleMemorySave} userId={userId} />
                  </ul>
                ) : base ? (
                  <ul role="list" className="grid grid-cols-1 gap-x-6 gap-y-6 lg:grid-cols-2">
                    {panelView === 'artifacts' ? <ArtifactBlocks base={base} campaigns={memory.campaign_archive} /> : <ContextBlocks base={base} setBase={setBase as any} />}
                  </ul>
                ) : (
                  <div className="h-full flex items-center justify-center">
                    <div className="text-center text-gray-400">
                      <SparklesIcon className="w-10 h-10 mx-auto mb-3 animate-pulse text-indigo-300" />
                      <p className="text-sm">콘텐츠 생성 중...</p>
                    </div>
                  </div>
                )}
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
                      <div key={idx} className="flex justify-end my-4">
                        <div className="max-w-[85%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3 text-sm">
                          <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={idx} className="my-4">
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mt-0.5">
                          <SparklesIcon className="w-4 h-4 text-white" />
                        </div>
                        <div className="flex-1 min-w-0 prose prose-sm max-w-none text-gray-800">
                          <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                          {!msg.isComplete && <span className="inline-block w-2 h-5 bg-indigo-500 animate-pulse ml-0.5" />}
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

      {showLoginModal && <LoginModal onClose={() => setShowLoginModal(false)} />}
    </div>
  );
};

export default LandingPage;
