/**
 * MemoryMapView — MemGPT 메모리 구조를 시각화하는 마인드맵 스타일 뷰
 * 4-Block Core Memory: Human Block + Persona Block + Domain Block + Audience Block
 * + Archival + Recall Memory
 */

import { motion } from 'framer-motion';
import type { MemoryState } from '../memory';
import {
  UserCircleIcon,
  SparklesIcon,
  ArchiveBoxIcon,
  ClockIcon,
  PencilSquareIcon,
  HashtagIcon,
  MegaphoneIcon,
  NoSymbolIcon,
  StarIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline';

interface MemoryMapViewProps {
  memory: MemoryState;
  onEditClick?: () => void;
}

/* ─── 작은 태그 컴포넌트 ─── */
function Tag({ label, color = 'indigo' }: { label: string; color?: string }) {
  const colorMap: Record<string, string> = {
    indigo: 'bg-indigo-100 text-indigo-700',
    purple: 'bg-purple-100 text-purple-700',
    rose: 'bg-rose-100 text-rose-700',
    amber: 'bg-amber-100 text-amber-700',
    teal: 'bg-teal-100 text-teal-700',
    slate: 'bg-slate-100 text-slate-600',
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${colorMap[color] ?? colorMap.indigo}`}>
      {label}
    </span>
  );
}

/* ─── 메모리 블록 카드 ─── */
function MemoryCard({
  title,
  icon: Icon,
  accentColor,
  children,
}: {
  title: string;
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
  accentColor: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-2xl border border-gray-100 bg-white overflow-hidden shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className={`flex items-center gap-2 px-4 py-2.5 ${accentColor}`}>
        <Icon className="w-4 h-4 text-white/90" />
        <span className="text-[13px] font-semibold text-white tracking-tight">{title}</span>
      </div>
      <div className="px-4 py-3 space-y-2 text-sm">{children}</div>
    </motion.div>
  );
}

/* ─── 라벨+값 행 ─── */
function FieldRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-2">
      <span className="text-[11px] text-gray-400 w-16 shrink-0 pt-0.5">{label}</span>
      <span className="text-gray-800 font-medium text-[13px]">{value}</span>
    </div>
  );
}

/* ─── 태그 목록 행 ─── */
function TagRow({ label, tags, color }: { label: string; tags: string[]; color?: string }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="flex items-start gap-2">
      <span className="text-[11px] text-gray-400 w-16 shrink-0 pt-1">{label}</span>
      <div className="flex flex-wrap gap-1">
        {tags.map((t) => (
          <Tag key={t} label={t} color={color} />
        ))}
      </div>
    </div>
  );
}

/* ─── 캠페인 카드 ─── */
function CampaignCard({ campaign }: { campaign: MemoryState['campaign_archive'][0] }) {
  const date = campaign.timestamp
    ? new Date(campaign.timestamp).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-2 space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-semibold text-gray-700 truncate">{campaign.goal || '목표 없음'}</span>
        {date && <span className="text-[10px] text-gray-400 shrink-0">{date}</span>}
      </div>
      {campaign.selected_trend && (
        <p className="text-[11px] text-gray-500 truncate">트렌드: {campaign.selected_trend}</p>
      )}
      {campaign.platforms_used?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {campaign.platforms_used.map((p) => (
            <Tag key={p} label={p} color="slate" />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── 메인 컴포넌트 ─── */
export default function MemoryMapView({ memory, onEditClick }: MemoryMapViewProps) {
  const human = memory.human_block;
  const persona = memory.persona_block;
  const domain = memory.domain_block;
  const audience = memory.audience_block;
  const campaigns = memory.campaign_archive ?? [];

  const isEmpty =
    !human.display_name &&
    !domain.industry &&
    !persona.tone &&
    persona.content_pillars.length === 0 &&
    persona.signature_hashtags.length === 0 &&
    campaigns.length === 0 &&
    !memory.working_summary;

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-24 text-center px-6">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-4">
          <SparklesIcon className="w-7 h-7 text-indigo-500" />
        </div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">메모리가 비어 있습니다</h3>
        <p className="text-sm text-gray-400 mb-6 max-w-xs leading-relaxed">
          챗봇과 대화하거나 브랜드 프로필을 설정하면 메모리가 채워집니다.
        </p>
        {onEditClick && (
          <button
            onClick={onEditClick}
            className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            프로필 설정하기
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4 max-w-2xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-gray-900">브랜드 메모리 맵</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">MemGPT 아키텍처 기반 메모리 현황</p>
        </div>
        {onEditClick && (
          <button
            onClick={onEditClick}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
          >
            <PencilSquareIcon className="w-3.5 h-3.5" />
            편집
          </button>
        )}
      </div>

      {/* 중앙 브랜드 카드 */}
      {(human.display_name || domain.industry) && (
        <div className="rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 p-4 text-white shadow-md">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center shrink-0">
              <span className="text-lg font-bold">
                {human.display_name?.charAt(0)?.toUpperCase() ?? '?'}
              </span>
            </div>
            <div className="min-w-0">
              <p className="font-bold text-base truncate">{human.display_name || '브랜드명 미설정'}</p>
              {domain.industry && (
                <p className="text-indigo-200 text-[12px]">{domain.industry}</p>
              )}
            </div>
          </div>
          {(human.twitter_handle || human.instagram_handle || audience.target_platforms?.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {human.twitter_handle && (
                <span className="bg-white/15 text-white text-[11px] px-2 py-0.5 rounded-full">
                  𝕏 @{human.twitter_handle}
                </span>
              )}
              {human.instagram_handle && (
                <span className="bg-white/15 text-white text-[11px] px-2 py-0.5 rounded-full">
                  📸 @{human.instagram_handle}
                </span>
              )}
              {audience.target_platforms?.map((p) => (
                <span key={p} className="bg-white/15 text-white text-[11px] px-2 py-0.5 rounded-full capitalize">
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 5-Block Core Memory */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Human Block (OwnerProfile) */}
        <MemoryCard title="Owner Profile" icon={UserCircleIcon} accentColor="bg-indigo-500">
          <FieldRow label="브랜드명" value={human.display_name} />
          <FieldRow label="대표자" value={(human as any).owner_name} />
          <FieldRow label="위치" value={(human as any).business_location} />
          <FieldRow label="업종" value={(human as any).industry} />
          <FieldRow label="목표" value={(human as any).primary_goal} />
          <FieldRow label="단계" value={(human as any).business_stage} />
          {Object.entries((human as any).social_handles || {}).map(([k, v]) => (
            <FieldRow key={k} label={k} value={String(v)} />
          ))}
          {!human.display_name && (
            <p className="text-[12px] text-gray-400 italic">설정된 프로필 정보가 없습니다</p>
          )}
        </MemoryCard>

        {/* Persona Block (BrandVoice) */}
        <MemoryCard title="Brand Voice" icon={SparklesIcon} accentColor="bg-purple-500">
          <FieldRow label="톤앤매너" value={(persona as any).tone_primary || persona.tone} />
          <FieldRow label="격식" value={(persona as any).tone_formality} />
          <FieldRow label="글쓰기" value={(persona as any).writing_style} />
          <FieldRow label="이모지" value={(persona as any).emoji_usage} />
          <FieldRow label="슬로건" value={(persona as any).slogan} />
          {persona.content_pillars?.length > 0 && (
            <TagRow label="콘텐츠" tags={persona.content_pillars} color="purple" />
          )}
          {persona.preferred_styles?.length > 0 && (
            <TagRow label="스타일" tags={persona.preferred_styles} color="teal" />
          )}
          {persona.signature_hashtags?.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-[11px] text-gray-400 w-16 shrink-0 pt-1">해시태그</span>
              <div className="flex flex-wrap gap-1">
                {persona.signature_hashtags.map((h) => (
                  <span key={h} className="text-[11px] text-indigo-500 font-medium">
                    {h.startsWith('#') ? h : `#${h}`}
                  </span>
                ))}
              </div>
            </div>
          )}
          {persona.avoid_topics?.length > 0 && (
            <TagRow label="금지어" tags={persona.avoid_topics} color="rose" />
          )}
          {!persona.tone && persona.content_pillars?.length === 0 && (
            <p className="text-[12px] text-gray-400 italic">브랜드 보이스가 설정되지 않았습니다</p>
          )}
        </MemoryCard>

        {/* Domain Block */}
        {(domain.industry || domain.domain_type || domain.usp) && (
          <MemoryCard title="Domain Block" icon={ArchiveBoxIcon} accentColor="bg-amber-500">
            <FieldRow label="업종" value={domain.industry} />
            <FieldRow label="유형" value={domain.domain_type} />
            <FieldRow label="위치" value={domain.business_location} />
            <FieldRow label="가격대" value={domain.price_range} />
            <FieldRow label="USP" value={domain.usp} />
            {domain.competitors?.length > 0 && (
              <TagRow label="경쟁사" tags={domain.competitors} color="amber" />
            )}
          </MemoryCard>
        )}

        {/* Audience Block */}
        {(audience.target_platforms?.length > 0 || audience.default_age_range || (audience as any).target_age_range || audience.segments?.length > 0 || (audience as any).audience_segments?.length > 0) && (
          <MemoryCard title="Audience Block" icon={MegaphoneIcon} accentColor="bg-teal-500">
            <FieldRow label="기본 연령대" value={audience.default_age_range || (audience as any).target_age_range} />
            {audience.target_platforms?.length > 0 && (
              <TagRow label="플랫폼" tags={audience.target_platforms} color="indigo" />
            )}
            {audience.segments?.length > 0 && (
              <TagRow label="세그먼트" tags={audience.segments.map(s => s.name)} color="teal" />
            )}
            {/* Backward compat: old audience_segments as string[] */}
            {!(audience.segments?.length > 0) && (audience as any).audience_segments?.length > 0 && (
              <TagRow label="세그먼트" tags={(audience as any).audience_segments} color="teal" />
            )}
            {audience.seasonal_peaks?.length > 0 && (
              <TagRow label="성수기" tags={audience.seasonal_peaks} color="amber" />
            )}
            {audience.offline_channels?.length > 0 && (
              <TagRow label="오프라인" tags={audience.offline_channels} color="slate" />
            )}
          </MemoryCard>
        )}
      </div>

      {/* Recall Memory (3-Level) */}
      {(memory.working_summary || memory.long_term_summary) && (
        <MemoryCard title="Recall Memory (3-Level)" icon={ClockIcon} accentColor="bg-amber-500">
          {memory.working_summary && (
            <div className="mb-3">
              <p className="text-[10px] font-medium text-amber-600 mb-1">L1 — 현재 세션 요약</p>
              <p className="text-[12px] text-gray-700 leading-relaxed whitespace-pre-wrap">{memory.working_summary}</p>
            </div>
          )}
          {memory.session_summaries && memory.session_summaries.length > 0 && (
            <div className="mb-3 pt-2 border-t border-gray-100">
              <p className="text-[10px] font-medium text-amber-600 mb-1">L2 — 최근 세션 ({memory.session_summaries.length}개)</p>
              {memory.session_summaries.slice(-3).map((s, i) => (
                <p key={i} className="text-[11px] text-gray-500 mb-1 pl-2 border-l-2 border-amber-200">{s.slice(0, 120)}...</p>
              ))}
            </div>
          )}
          {memory.long_term_summary && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-[10px] font-medium text-amber-600 mb-1">L3 — 장기 누적 요약</p>
              <p className="text-[12px] text-gray-600 leading-relaxed whitespace-pre-wrap">{memory.long_term_summary.slice(0, 300)}{memory.long_term_summary.length > 300 ? '...' : ''}</p>
            </div>
          )}
        </MemoryCard>
      )}

      {/* Archival Memory */}
      {campaigns.length > 0 && (
        <MemoryCard title="Archival Memory (캠페인 아카이브)" icon={ArchiveBoxIcon} accentColor="bg-teal-500">
          <div className="space-y-2">
            {campaigns.slice(0, 5).map((c) => (
              <CampaignCard key={c.campaign_id} campaign={c} />
            ))}
            {campaigns.length > 5 && (
              <p className="text-[11px] text-gray-400 text-center pt-1">
                +{campaigns.length - 5}개 더 있습니다
              </p>
            )}
          </div>
        </MemoryCard>
      )}

      {/* Campaign Block (BehaviorGraph 요약) — 5번째 블록 */}
      {memory.behavior_graph && (memory.behavior_graph.edges?.length > 0 || (memory.behavior_graph as any).proven_tactics?.length > 0) && (
        <MemoryCard title="Campaign Block (학습된 전략)" icon={CalendarDaysIcon} accentColor="bg-rose-500">
          {(memory.behavior_graph as any).proven_tactics?.length > 0 && (
            <TagRow label="효과적" tags={(memory.behavior_graph as any).proven_tactics} color="green" />
          )}
          {(memory.behavior_graph as any).failed_tactics?.length > 0 && (
            <TagRow label="피해야 할" tags={(memory.behavior_graph as any).failed_tactics} color="rose" />
          )}
          <FieldRow label="최적 채널" value={memory.behavior_graph.overall_best_platform} />
          <FieldRow label="신뢰도" value={(memory.behavior_graph as any).confidence_level} />
          <FieldRow label="데이터" value={`${(memory.behavior_graph as any).total_data_points || memory.behavior_graph.edges?.length || 0}건`} />
        </MemoryCard>
      )}

      {/* 메모리 통계 */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: '총 캠페인', value: memory.total_campaigns ?? campaigns.length, icon: CalendarDaysIcon, color: 'text-indigo-600' },
          { label: '콘텐츠 기둥', value: persona.content_pillars?.length ?? 0, icon: StarIcon, color: 'text-purple-600' },
          { label: '해시태그', value: persona.signature_hashtags?.length ?? 0, icon: HashtagIcon, color: 'text-teal-600' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border bg-white p-3 text-center">
            <Icon className={`w-5 h-5 mx-auto mb-1 ${color}`} />
            <p className={`text-xl font-bold ${color}`}>{value}</p>
            <p className="text-[10px] text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* 마지막 업데이트 */}
      {memory.last_updated && (
        <p className="text-[10px] text-gray-400 text-center">
          마지막 업데이트: {new Date(memory.last_updated).toLocaleString('ko-KR')}
        </p>
      )}
    </div>
  );
}
