/**
 * ConversationHistoryTab — 대화 히스토리 탭
 * 세션별 블록으로 그룹핑, 클릭하면 대화 내용 펼침.
 * user_query와 agent_response만 표시.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ChatBubbleLeftRightIcon,
  UserIcon,
  CpuChipIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
  CalendarDaysIcon,
  BookOpenIcon,
  ClockIcon,
  ArchiveBoxIcon,
} from '@heroicons/react/24/outline';
import { fetchConversationHistory } from '../api';
import type { MemoryState } from '../memory';

interface ConversationTurn {
  timestamp: string;
  role: string;
  content: string;
  summary_note?: string;
  summary?: string;
  session_id?: string;
  source: 'recall' | 'archive';
}

interface SessionBlock {
  sessionId: string;
  date: string;
  turns: ConversationTurn[];
  firstUserMessage: string;
  lastAgentMessage: string;
  turnCount: number;
}

interface ConversationHistoryTabProps {
  userId: string;
  memory?: MemoryState;
}

function formatDate(ts: string): string {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  } catch {
    return ts.slice(0, 10);
  }
}

function formatTime(ts: string): string {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return '';
  }
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max) + '…' : text;
}

/** Group turns into session blocks */
function buildSessionBlocks(turns: ConversationTurn[]): SessionBlock[] {
  // Sort chronologically for grouping
  const sorted = [...turns].sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));

  // Group by session_id or by date if no session_id
  const groups: Record<string, ConversationTurn[]> = {};
  for (const turn of sorted) {
    const key = turn.session_id || turn.timestamp?.slice(0, 10) || 'unknown';
    if (!groups[key]) groups[key] = [];
    groups[key].push(turn);
  }

  const blocks: SessionBlock[] = Object.entries(groups).map(([sessionId, sessionTurns]) => {
    const userTurns = sessionTurns.filter(t => t.role === 'user');
    const agentTurns = sessionTurns.filter(t => t.role === 'agent');

    return {
      sessionId,
      date: sessionTurns[0]?.timestamp || '',
      turns: sessionTurns,
      firstUserMessage: userTurns[0]?.content || '',
      lastAgentMessage: agentTurns[agentTurns.length - 1]?.content || '',
      turnCount: sessionTurns.length,
    };
  });

  // Sort by date descending (most recent first)
  blocks.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  return blocks;
}

export default function ConversationHistoryTab({ userId, memory }: ConversationHistoryTabProps) {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [workingSummary, setWorkingSummary] = useState('');
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [showSummaries, setShowSummaries] = useState(true);
  const LIMIT = 50;

  const load = useCallback(async (p: number) => {
    setIsLoading(true);
    try {
      const result = await fetchConversationHistory(userId, { limit: LIMIT, page: p });
      setTurns(result.conversations);
      setTotal(result.total);
      setWorkingSummary(result.working_summary);
    } catch {
      setTurns([]);
    }
    setIsLoading(false);
  }, [userId]);

  useEffect(() => {
    load(page);
  }, [load, page]);

  const sessionBlocks = buildSessionBlocks(turns);

  // Group session blocks by date
  const dateGroups: Record<string, SessionBlock[]> = {};
  for (const block of sessionBlocks) {
    const dateKey = block.date?.slice(0, 10) || 'unknown';
    if (!dateGroups[dateKey]) dateGroups[dateKey] = [];
    dateGroups[dateKey].push(block);
  }
  const sortedDates = Object.keys(dateGroups).sort((a, b) => b.localeCompare(a));

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 pt-4 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2 mb-1">
          <ChatBubbleLeftRightIcon className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-semibold text-white">대화 히스토리</h2>
          <span className="ml-auto text-sm text-gray-400">{total}개 대화</span>
        </div>
        {/* Collapsible Memory Summary Section (L1/L2/L3) */}
        {(workingSummary || memory?.working_summary || (memory?.session_summaries && memory.session_summaries.length > 0) || memory?.long_term_summary) && (
          <button
            onClick={() => setShowSummaries(!showSummaries)}
            className="mt-2 w-full flex items-center gap-2 text-xs font-medium text-gray-400 hover:text-gray-200 transition-colors"
          >
            <BookOpenIcon className="w-4 h-4" />
            <span>메모리 요약</span>
            {showSummaries
              ? <ChevronUpIcon className="w-3.5 h-3.5 ml-auto" />
              : <ChevronDownIcon className="w-3.5 h-3.5 ml-auto" />
            }
          </button>
        )}
        {showSummaries && (
          <div className="mt-2 space-y-2">
            {/* L1: Current Session Summary (working_summary) */}
            {(workingSummary || memory?.working_summary) && (
              <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1">
                  <ClockIcon className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-medium text-indigo-300">L1 - 현재 세션 요약</span>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">{workingSummary || memory?.working_summary}</p>
              </div>
            )}

            {/* L2: Per-Session Summaries */}
            {memory?.session_summaries && memory.session_summaries.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 px-1">
                  <DocumentTextIcon className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-medium text-purple-300">L2 - 세션별 요약</span>
                  <span className="text-[10px] text-gray-500 ml-auto">{memory.session_summaries.length}개</span>
                </div>
                <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1">
                  {memory.session_summaries.map((summary, i) => (
                    <div key={i} className="p-2.5 bg-purple-500/10 border border-purple-500/15 rounded-lg">
                      <p className="text-xs text-gray-300 leading-relaxed">{summary}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* L3: Long-Term Summary */}
            {memory?.long_term_summary && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <div className="flex items-center gap-1.5 mb-1">
                  <ArchiveBoxIcon className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-medium text-amber-300">L3 - 장기 기억</span>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">{memory.long_term_summary}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : sessionBlocks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-gray-500">
            <ChatBubbleLeftRightIcon className="w-10 h-10 mb-2 opacity-40" />
            <p className="text-sm">아직 대화 기록이 없습니다</p>
            <p className="text-xs text-gray-600 mt-1">에이전트와 대화를 시작하면 여기에 기록됩니다</p>
          </div>
        ) : (
          <div className="space-y-5">
            {sortedDates.map(dateKey => (
              <div key={dateKey}>
                {/* Date header */}
                <div className="flex items-center gap-2 mb-3">
                  <CalendarDaysIcon className="w-4 h-4 text-gray-500" />
                  <span className="text-xs font-medium text-gray-400">{formatDate(dateKey)}</span>
                  <div className="h-px flex-1 bg-white/10" />
                </div>

                {/* Session blocks for this date */}
                <div className="space-y-2">
                  {dateGroups[dateKey].map(block => {
                    const isExpanded = expandedSession === block.sessionId;
                    return (
                      <div key={block.sessionId} className="rounded-lg border border-white/10 overflow-hidden">
                        {/* Session header — clickable */}
                        <button
                          onClick={() => setExpandedSession(isExpanded ? null : block.sessionId)}
                          className="w-full flex items-start gap-3 p-3 hover:bg-white/5 transition-colors text-left"
                        >
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center mt-0.5">
                            <ChatBubbleLeftRightIcon className="w-4 h-4 text-indigo-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-white">
                                {truncate(block.firstUserMessage, 60) || '대화 세션'}
                              </span>
                              <span className="flex-shrink-0 text-[10px] text-gray-500">
                                {formatTime(block.date)}
                              </span>
                            </div>
                            <p className="text-xs text-gray-400 line-clamp-1">
                              {truncate(block.lastAgentMessage, 80)}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700/50 text-gray-400">
                                {block.turnCount}턴
                              </span>
                              {block.turns.some(t => t.source === 'archive') && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/30 text-emerald-400">
                                  아카이브
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex-shrink-0 mt-1">
                            {isExpanded
                              ? <ChevronUpIcon className="w-4 h-4 text-gray-500" />
                              : <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                            }
                          </div>
                        </button>

                        {/* Expanded conversation */}
                        {isExpanded && (
                          <div className="border-t border-white/5 bg-white/[0.02] px-4 py-3 space-y-3">
                            {block.turns
                              .filter(t => t.role === 'user' || t.role === 'agent')
                              .map((turn, idx) => (
                              <div key={idx} className="flex gap-3">
                                <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5 ${
                                  turn.role === 'user'
                                    ? 'bg-indigo-500/20 text-indigo-400'
                                    : 'bg-emerald-500/20 text-emerald-400'
                                }`}>
                                  {turn.role === 'user'
                                    ? <UserIcon className="w-3.5 h-3.5" />
                                    : <CpuChipIcon className="w-3.5 h-3.5" />
                                  }
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-0.5">
                                    <span className={`text-[11px] font-medium ${
                                      turn.role === 'user' ? 'text-indigo-300' : 'text-emerald-300'
                                    }`}>
                                      {turn.role === 'user' ? '사용자' : '에이전트'}
                                    </span>
                                    <span className="text-[10px] text-gray-600">{formatTime(turn.timestamp)}</span>
                                  </div>
                                  <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap break-words">
                                    {turn.content}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-3 border-t border-white/10 flex items-center justify-between">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeftIcon className="w-4 h-4" /> 이전
          </button>
          <span className="text-xs text-gray-500">{page + 1} / {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          >
            다음 <ChevronRightIcon className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
