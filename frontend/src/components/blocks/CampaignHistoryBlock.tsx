/**
 * CampaignHistoryBlock — 캠페인 히스토리 목록 + 상세 분석 뷰
 *
 * 목록: 캠페인 카드 리스트 (썸네일, 플랫폼, 날짜, 성과 요약)
 * 상세: 캠페인 클릭 시 상세 분석 뷰 (매출/트렌드/타겟/가이드라인/퍼포먼스)
 */

import { useState, useMemo } from 'react';
import type { MemoryState, CampaignRecord } from '../../memory';
import { updateCampaignPerformance } from '../../api';
import { useToast } from '../../contexts/ToastContext';
import {
  ChevronLeftIcon,
  PhotoIcon,
  ClockIcon,
  ChartBarIcon,
  EyeIcon,
  HandThumbUpIcon,
  CursorArrowRaysIcon,
  ShareIcon,
  ChatBubbleLeftIcon,
  ArrowTrendingUpIcon,
  UserGroupIcon,
  SparklesIcon,
  PencilSquareIcon,
  CheckIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

// ─── 색상 맵 ──────────────────────────────────────────────────────────────────
const PLATFORM_COLORS: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  instagram: { bg: 'bg-pink-50', text: 'text-pink-600', border: 'border-pink-200', dot: 'bg-pink-400' },
  twitter:   { bg: 'bg-sky-50',  text: 'text-sky-600',  border: 'border-sky-200',  dot: 'bg-sky-400'  },
  x:         { bg: 'bg-sky-50',  text: 'text-sky-600',  border: 'border-sky-200',  dot: 'bg-sky-400'  },
  linkedin:  { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', dot: 'bg-blue-500' },
  facebook:  { bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-200', dot: 'bg-indigo-400' },
  tiktok:    { bg: 'bg-rose-50', text: 'text-rose-600', border: 'border-rose-200', dot: 'bg-rose-400' },
  youtube:   { bg: 'bg-red-50',  text: 'text-red-600',  border: 'border-red-200',  dot: 'bg-red-500'  },
};
const DEFAULT_PLATFORM = { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200', dot: 'bg-gray-400' };

function platformColor(p: string) {
  return PLATFORM_COLORS[p.toLowerCase()] ?? DEFAULT_PLATFORM;
}

// ─── 성과 지표 상태 뱃지 ─────────────────────────────────────────────────────
function ctr(views: number, clicks: number) {
  if (!views) return null;
  return ((clicks / views) * 100).toFixed(1);
}

// ─── 목록 카드 ───────────────────────────────────────────────────────────────
interface CardProps {
  campaign: CampaignRecord;
  thumbnail?: string;
  onClick: () => void;
}

function CampaignCard({ campaign, thumbnail, onClick }: CardProps) {
  const hasPerf = !!campaign.performance;
  const dateStr = new Date(campaign.timestamp).toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white rounded-xl border border-gray-100 hover:border-indigo-200 hover:shadow-md transition-all overflow-hidden group"
    >
      <div className="flex gap-3 p-4">
        {/* Thumbnail */}
        <div className="shrink-0 w-[72px] h-[72px] rounded-lg overflow-hidden bg-gray-50 border border-gray-100 flex items-center justify-center">
          {thumbnail ? (
            <img src={thumbnail} alt="campaign" className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          ) : (
            <PhotoIcon className="w-7 h-7 text-gray-300" />
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 line-clamp-2 leading-snug group-hover:text-indigo-700 transition-colors">
            {campaign.goal}
          </p>

          {/* Platform badges */}
          <div className="mt-2 flex flex-wrap gap-1">
            {campaign.platforms_used.map((p) => {
              const c = platformColor(p);
              return (
                <span key={p} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${c.bg} ${c.text} ${c.border}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
                  {p}
                </span>
              );
            })}
            {campaign.selected_trend && (
              <span className="px-2 py-0.5 bg-violet-50 text-violet-600 border border-violet-200 rounded-full text-[11px] font-medium">
                #{campaign.selected_trend}
              </span>
            )}
          </div>

          {/* Date + perf hint */}
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-1 text-[11px] text-gray-400">
              <ClockIcon className="w-3.5 h-3.5" />
              {dateStr}
            </div>
            {hasPerf ? (
              <span className="text-[11px] text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full font-medium">
                성과 입력됨
              </span>
            ) : (
              <span className="text-[11px] text-gray-400 bg-gray-50 border border-gray-200 px-2 py-0.5 rounded-full">
                성과 미입력
              </span>
            )}
          </div>
        </div>

        {/* Arrow */}
        <div className="shrink-0 flex items-center text-gray-300 group-hover:text-indigo-400 transition-colors">
          <ChevronLeftIcon className="w-4 h-4 rotate-180" />
        </div>
      </div>

      {/* Performance mini row */}
      {hasPerf && (
        <div className="border-t border-gray-50 px-4 py-2 grid grid-cols-4 gap-2 bg-gray-50/60">
          {[
            { icon: EyeIcon, label: '조회', value: campaign.performance!.views },
            { icon: HandThumbUpIcon, label: '좋아요', value: campaign.performance!.likes },
            { icon: CursorArrowRaysIcon, label: '클릭', value: campaign.performance!.clicks },
            { icon: ShareIcon, label: '공유', value: campaign.performance!.shares },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-center gap-1.5">
              <Icon className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-gray-700">{value.toLocaleString()}</p>
                <p className="text-[10px] text-gray-400">{label}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}

// ─── 상세 분석 뷰 ────────────────────────────────────────────────────────────
interface DetailProps {
  campaign: CampaignRecord;
  thumbnail?: string;
  userId: string;
  onBack: () => void;
  onPerfSaved: () => void;
}

function CampaignDetail({ campaign, thumbnail, userId, onBack, onPerfSaved }: DetailProps) {
  const { showToast } = useToast();
  const [editingPerf, setEditingPerf] = useState(false);
  const [perfDraft, setPerfDraft] = useState({
    views: campaign.performance?.views ?? 0,
    clicks: campaign.performance?.clicks ?? 0,
    impressions: campaign.performance?.impressions ?? 0,
    likes: campaign.performance?.likes ?? 0,
    shares: campaign.performance?.shares ?? 0,
    comments: campaign.performance?.comments ?? 0,
    engagement_level: campaign.performance?.engagement_level ?? '',
    reach_level: campaign.performance?.reach_level ?? '',
    conversion_level: campaign.performance?.conversion_level ?? '',
    best_platform: campaign.performance?.best_platform ?? '',
    what_worked: (campaign.performance?.what_worked ?? []).join(', '),
    what_failed: (campaign.performance?.what_failed ?? []).join(', '),
  });
  const [saving, setSaving] = useState(false);

  const dateStr = new Date(campaign.timestamp).toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const perf = campaign.performance;
  const ctrVal = perf ? ctr(perf.views, perf.clicks) : null;

  const savePerf = async () => {
    setSaving(true);
    try {
      await updateCampaignPerformance(userId, campaign.campaign_id, {
        ...perfDraft,
        what_worked: perfDraft.what_worked ? perfDraft.what_worked.split(',').map(s => s.trim()).filter(Boolean) : [],
        what_failed: perfDraft.what_failed ? perfDraft.what_failed.split(',').map(s => s.trim()).filter(Boolean) : [],
      });
      onPerfSaved();
      setEditingPerf(false);
      showToast('성과 데이터 저장 완료', 'success');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
      >
        <ChevronLeftIcon className="w-4 h-4" />
        캠페인 목록으로
      </button>

      {/* Hero card */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {thumbnail && (
          <div className="h-40 overflow-hidden bg-gray-100">
            <img src={thumbnail} alt="campaign" className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          </div>
        )}
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <p className="text-base font-bold text-gray-900 leading-snug">{campaign.goal}</p>
            <div className="flex flex-col items-end gap-1 shrink-0">
              {campaign.platforms_used.map((p) => {
                const c = platformColor(p);
                return (
                  <span key={p} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${c.bg} ${c.text} ${c.border}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
                    {p}
                  </span>
                );
              })}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
            <ClockIcon className="w-3.5 h-3.5" />
            {dateStr}
            {campaign.selected_trend && (
              <>
                <span className="text-gray-200">·</span>
                <span className="text-violet-500 font-medium">#{campaign.selected_trend}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── 성과 지표 섹션 ── */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-50">
          <div className="flex items-center gap-2">
            <ChartBarIcon className="w-4 h-4 text-indigo-500" />
            <span className="text-sm font-semibold text-gray-800">성과 분석</span>
          </div>
          <button
            onClick={() => setEditingPerf(!editingPerf)}
            className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700"
          >
            <PencilSquareIcon className="w-3.5 h-3.5" />
            {editingPerf ? '취소' : (perf ? '수정' : '성과 입력')}
          </button>
        </div>

        {!editingPerf ? (
          perf ? (
            <div className="p-5">
              {/* 주요 지표 그리드 */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { icon: EyeIcon,              label: '조회수',   value: perf.views,       color: 'text-blue-600',   bg: 'bg-blue-50'   },
                  { icon: HandThumbUpIcon,       label: '좋아요',   value: perf.likes,       color: 'text-pink-600',   bg: 'bg-pink-50'   },
                  { icon: CursorArrowRaysIcon,   label: '클릭수',   value: perf.clicks,      color: 'text-indigo-600', bg: 'bg-indigo-50' },
                  { icon: ShareIcon,             label: '공유',     value: perf.shares,      color: 'text-violet-600', bg: 'bg-violet-50' },
                  { icon: ChatBubbleLeftIcon,    label: '댓글',     value: perf.comments,    color: 'text-emerald-600',bg: 'bg-emerald-50'},
                  { icon: ArrowTrendingUpIcon,   label: '노출수',   value: perf.impressions, color: 'text-amber-600',  bg: 'bg-amber-50'  },
                ].map(({ icon: Icon, label, value, color, bg }) => (
                  <div key={label} className={`flex items-center gap-3 p-3 rounded-xl ${bg}`}>
                    <div className={`w-8 h-8 rounded-lg bg-white flex items-center justify-center shadow-sm`}>
                      <Icon className={`w-4 h-4 ${color}`} />
                    </div>
                    <div>
                      <p className={`text-base font-bold ${color}`}>{value.toLocaleString()}</p>
                      <p className="text-[11px] text-gray-500">{label}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* CTR 요약 바 */}
              {ctrVal && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">CTR (클릭률)</span>
                      <span className="text-sm font-bold text-indigo-600">{ctrVal}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full transition-all"
                        style={{ width: `${Math.min(Number(ctrVal) * 10, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* 시맨틱 성과 지표 */}
              {(perf.engagement_level || perf.best_platform) && (
                <div className="space-y-2 mt-3 p-3 bg-indigo-50/50 rounded-xl">
                  <p className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">정성 평가</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {perf.engagement_level && (
                      <div><span className="text-gray-500">참여도:</span> <span className="font-medium text-indigo-600">{perf.engagement_level}</span></div>
                    )}
                    {perf.reach_level && (
                      <div><span className="text-gray-500">도달:</span> <span className="font-medium text-indigo-600">{perf.reach_level}</span></div>
                    )}
                    {perf.conversion_level && (
                      <div><span className="text-gray-500">전환:</span> <span className="font-medium text-indigo-600">{perf.conversion_level}</span></div>
                    )}
                    {perf.best_platform && (
                      <div><span className="text-gray-500">최고 채널:</span> <span className="font-medium text-indigo-600">{perf.best_platform}</span></div>
                    )}
                  </div>
                  {perf.what_worked && perf.what_worked.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {perf.what_worked.map((w, i) => (
                        <span key={i} className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] rounded-full">✓ {w}</span>
                      ))}
                    </div>
                  )}
                  {perf.what_failed && perf.what_failed.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {perf.what_failed.map((w, i) => (
                        <span key={i} className="px-2 py-0.5 bg-red-100 text-red-600 text-[10px] rounded-full">✗ {w}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="py-8 text-center text-gray-400">
              <ChartBarIcon className="w-8 h-8 mx-auto mb-2 text-gray-200" />
              <p className="text-sm">성과 데이터가 없습니다</p>
              <p className="text-xs mt-1">상단 버튼으로 성과를 입력하세요</p>
            </div>
          )
        ) : (
          <div className="p-5 space-y-3">
            {/* 숫자 지표 */}
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">정량 지표</p>
            <div className="grid grid-cols-2 gap-3">
              {(['views','clicks','impressions','likes','shares','comments'] as const).map((k) => (
                <div key={k}>
                  <label className="text-xs text-gray-500 mb-1 block">
                    {{ views: '조회수', clicks: '클릭수', impressions: '노출수', likes: '좋아요', shares: '공유', comments: '댓글' }[k]}
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={perfDraft[k]}
                    onChange={(e) => setPerfDraft((p) => ({ ...p, [k]: Number(e.target.value) }))}
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                  />
                </div>
              ))}
            </div>
            {/* 정성 평가 */}
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mt-3">정성 평가</p>
            <div className="grid grid-cols-2 gap-3">
              {([
                { key: 'engagement_level', label: '참여도', options: ['low','medium','high','viral'] },
                { key: 'reach_level', label: '도달', options: ['low','medium','high'] },
                { key: 'conversion_level', label: '전환', options: ['low','medium','high'] },
              ] as const).map(({ key, label, options }) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 mb-1 block">{label}</label>
                  <select
                    value={perfDraft[key]}
                    onChange={(e) => setPerfDraft((p) => ({ ...p, [key]: e.target.value }))}
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  >
                    <option value="">선택</option>
                    {options.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              ))}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">최고 채널</label>
                <input
                  type="text"
                  value={perfDraft.best_platform}
                  onChange={(e) => setPerfDraft((p) => ({ ...p, best_platform: e.target.value }))}
                  placeholder="예: instagram"
                  className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">잘된 점 (쉼표 구분)</label>
                <input
                  type="text"
                  value={perfDraft.what_worked}
                  onChange={(e) => setPerfDraft((p) => ({ ...p, what_worked: e.target.value }))}
                  placeholder="예: 밝은 색감, 짧은 캡션"
                  className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">아쉬운 점 (쉼표 구분)</label>
                <input
                  type="text"
                  value={perfDraft.what_failed}
                  onChange={(e) => setPerfDraft((p) => ({ ...p, what_failed: e.target.value }))}
                  placeholder="예: 긴 텍스트, 어두운 이미지"
                  className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
            </div>
            <button
              onClick={savePerf}
              disabled={saving}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors"
            >
              <CheckIcon className="w-4 h-4" />
              {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        )}
      </div>

      {/* ── 캠페인 상세 정보 ── */}
      <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-50">

        {/* 트렌드 */}
        {campaign.selected_trend && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowTrendingUpIcon className="w-4 h-4 text-violet-500" />
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">선택 트렌드</span>
            </div>
            <span className="inline-block px-3 py-1.5 bg-violet-50 text-violet-700 border border-violet-200 rounded-lg text-sm font-medium">
              #{campaign.selected_trend}
            </span>
          </div>
        )}

        {/* 타겟 오디언스 */}
        {campaign.target_audiences.length > 0 && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-2">
              <UserGroupIcon className="w-4 h-4 text-blue-500" />
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">타겟 오디언스</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {campaign.target_audiences.map((a) => (
                <span key={a} className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-xs font-medium">
                  {a}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 스타일 */}
        {campaign.selected_styles.length > 0 && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-2">
              <SparklesIcon className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">적용 스타일</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {campaign.selected_styles.map((s) => (
                <span key={s} className="px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg text-xs font-medium">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 가이드라인 */}
        {campaign.guideline_summary && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-2">
              <PencilSquareIcon className="w-4 h-4 text-emerald-500" />
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">콘텐츠 가이드라인</span>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{campaign.guideline_summary}</p>
          </div>
        )}

        {/* 성과 메모 */}
        {campaign.performance_notes && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-2">
              <ChatBubbleLeftIcon className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">성과 메모</span>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed italic">{campaign.performance_notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────
interface Props {
  memory: MemoryState;
  userId: string;
  onMemoryRefresh: () => void;
}

const PLATFORM_CHIPS = ['instagram', 'facebook', 'twitter', 'x', 'youtube', 'tiktok', 'linkedin', 'pinterest', 'threads', 'kakao'] as const;
type PerfFilter = 'all' | 'has_perf' | 'no_perf';

export default function CampaignHistoryBlock({ memory, userId, onMemoryRefresh }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [platformFilter, setPlatformFilter] = useState<Set<string>>(new Set());
  const [perfFilter, setPerfFilter] = useState<PerfFilter>('all');

  const campaigns = [...memory.campaign_archive].reverse();
  const selected = campaigns.find((c) => c.campaign_id === selectedId) ?? null;

  // Collect all platforms that actually appear in campaigns
  const availablePlatforms = useMemo(() => {
    const s = new Set<string>();
    campaigns.forEach((c) => c.platforms_used.forEach((p) => s.add(p.toLowerCase())));
    return PLATFORM_CHIPS.filter((p) => s.has(p));
  }, [campaigns]);

  // Filtered campaigns
  const filtered = useMemo(() => {
    return campaigns.filter((c) => {
      // Search by goal text
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        if (!c.goal.toLowerCase().includes(q)) return false;
      }
      // Platform filter
      if (platformFilter.size > 0) {
        const hasPlatform = c.platforms_used.some((p) => platformFilter.has(p.toLowerCase()));
        if (!hasPlatform) return false;
      }
      // Performance status filter
      if (perfFilter === 'has_perf' && !c.performance) return false;
      if (perfFilter === 'no_perf' && !!c.performance) return false;
      return true;
    });
  }, [campaigns, searchQuery, platformFilter, perfFilter]);

  function getThumbnail(campaign: CampaignRecord) {
    const campaignTime = new Date(campaign.timestamp).getTime();
    const img = memory.asset_archive
      .filter((a) => a.asset_type === 'image' && !a.is_user_uploaded)
      .sort((a, b) =>
        Math.abs(new Date(a.created_at).getTime() - campaignTime) -
        Math.abs(new Date(b.created_at).getTime() - campaignTime)
      )[0];
    return img?.gcs_url;
  }

  const togglePlatform = (p: string) => {
    setPlatformFilter((prev) => {
      const next = new Set(prev);
      if (next.has(p)) next.delete(p);
      else next.add(p);
      return next;
    });
  };

  const hasActiveFilters = searchQuery.trim() || platformFilter.size > 0 || perfFilter !== 'all';
  const clearFilters = () => {
    setSearchQuery('');
    setPlatformFilter(new Set());
    setPerfFilter('all');
  };

  if (campaigns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <ChartBarIcon className="w-12 h-12 mb-3 text-gray-200" />
        <p className="text-sm font-medium text-gray-500">아직 생성된 캠페인이 없습니다</p>
        <p className="text-xs mt-1">콘텐츠를 생성하면 여기에 히스토리가 쌓입니다</p>
      </div>
    );
  }

  if (selected) {
    return (
      <CampaignDetail
        campaign={selected}
        thumbnail={getThumbnail(selected)}
        userId={userId}
        onBack={() => setSelectedId(null)}
        onPerfSaved={() => { setSelectedId(null); onMemoryRefresh(); }}
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="캠페인 목표로 검색..."
          className="w-full pl-9 pr-9 py-2.5 text-sm border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder-gray-400"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Platform filter chips */}
      {availablePlatforms.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {availablePlatforms.map((p) => {
            const active = platformFilter.has(p);
            const c = platformColor(p);
            return (
              <button
                key={p}
                onClick={() => togglePlatform(p)}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all ${
                  active
                    ? `${c.bg} ${c.text} ${c.border} ring-2 ring-offset-1 ring-indigo-300`
                    : 'bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${active ? c.dot : 'bg-gray-300'}`} />
                {p}
              </button>
            );
          })}
        </div>
      )}

      {/* Performance status filter */}
      <div className="flex items-center gap-2">
        {([
          { key: 'all' as PerfFilter, label: '전체' },
          { key: 'has_perf' as PerfFilter, label: '성과 입력됨' },
          { key: 'no_perf' as PerfFilter, label: '성과 미입력' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setPerfFilter(key)}
            className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all ${
              perfFilter === key
                ? 'bg-indigo-50 text-indigo-600 border-indigo-200'
                : 'bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="ml-auto text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
          >
            필터 초기화
          </button>
        )}
      </div>

      {/* Campaign count */}
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-gray-400">
          {hasActiveFilters
            ? `${filtered.length} / ${campaigns.length}개의 캠페인`
            : `총 ${campaigns.length}개의 캠페인`}
        </p>
      </div>

      {/* Campaign list */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400">
          <MagnifyingGlassIcon className="w-8 h-8 mb-2 text-gray-200" />
          <p className="text-sm text-gray-500">검색 결과가 없습니다</p>
          <button onClick={clearFilters} className="mt-2 text-xs text-indigo-500 hover:text-indigo-700">
            필터 초기화
          </button>
        </div>
      ) : (
        filtered.map((c) => (
          <CampaignCard
            key={c.campaign_id}
            campaign={c}
            thumbnail={getThumbnail(c)}
            onClick={() => setSelectedId(c.campaign_id)}
          />
        ))
      )}
    </div>
  );
}
