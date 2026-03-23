/**
 * BehaviorGraphBlock — Behavior Graph Visualization
 *
 * Displays:
 *  1. Overall Best Platform badge
 *  2. Platform Performance Cards (best content type + avg engagement)
 *  3. Topic Performance Summary (horizontal bars / tags)
 *  4. What Worked / What Failed (aggregated tags from edges)
 *  5. Segment Performance (edges grouped by segment_id)
 */

import { useMemo } from 'react';
import type { BehaviorGraph, CampaignRecord, PerformanceEdge } from '../../memory';
import {
  TrophyIcon,
  ChartBarIcon,
  TagIcon,
  CheckCircleIcon,
  XCircleIcon,
  UserGroupIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';

interface BehaviorGraphBlockProps {
  behaviorGraph: BehaviorGraph;
  campaigns: CampaignRecord[];
}

// ─── Platform icons / colors ────────────────────────────────────────────────
const PLATFORM_META: Record<string, { emoji: string; color: string; bg: string; border: string }> = {
  instagram:  { emoji: '\uD83D\uDCF7', color: 'text-pink-600',   bg: 'bg-pink-50',   border: 'border-pink-200' },
  twitter:    { emoji: '\uD83D\uDC26', color: 'text-sky-600',    bg: 'bg-sky-50',    border: 'border-sky-200' },
  x:          { emoji: '\u2715',       color: 'text-gray-700',   bg: 'bg-gray-50',   border: 'border-gray-200' },
  facebook:   { emoji: '\uD83D\uDC4D', color: 'text-blue-600',   bg: 'bg-blue-50',   border: 'border-blue-200' },
  linkedin:   { emoji: '\uD83D\uDCBC', color: 'text-blue-700',   bg: 'bg-blue-50',   border: 'border-blue-200' },
  tiktok:     { emoji: '\uD83C\uDFB5', color: 'text-rose-600',   bg: 'bg-rose-50',   border: 'border-rose-200' },
  youtube:    { emoji: '\u25B6\uFE0F',  color: 'text-red-600',    bg: 'bg-red-50',    border: 'border-red-200' },
  pinterest:  { emoji: '\uD83D\uDCCC', color: 'text-red-500',    bg: 'bg-red-50',    border: 'border-red-200' },
  threads:    { emoji: '\uD83E\uDDF5', color: 'text-gray-700',   bg: 'bg-gray-50',   border: 'border-gray-200' },
  kakao:      { emoji: '\uD83D\uDCAC', color: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200' },
};
const DEFAULT_META = { emoji: '\uD83C\uDF10', color: 'text-gray-600', bg: 'bg-gray-50', border: 'border-gray-200' };

function meta(platform: string) {
  return PLATFORM_META[platform.toLowerCase()] ?? DEFAULT_META;
}

// ─── Engagement level to numeric score for bar widths ───────────────────────
const ENGAGEMENT_SCORE: Record<string, number> = {
  very_high: 100, high: 80, medium: 60, low: 40, very_low: 20,
};
function engScore(level: string): number {
  return ENGAGEMENT_SCORE[level?.toLowerCase()] ?? 50;
}

const ENGAGEMENT_COLOR: Record<string, string> = {
  very_high: 'bg-emerald-500', high: 'bg-green-400', medium: 'bg-amber-400', low: 'bg-orange-400', very_low: 'bg-red-400',
};
function engColor(level: string): string {
  return ENGAGEMENT_COLOR[level?.toLowerCase()] ?? 'bg-gray-300';
}

// ─── Aggregate helper ───────────────────────────────────────────────────────
function countTags(edges: PerformanceEdge[], field: 'what_worked' | 'what_failed'): [string, number][] {
  const counts: Record<string, number> = {};
  for (const e of edges) {
    for (const tag of e[field] ?? []) {
      counts[tag] = (counts[tag] || 0) + 1;
    }
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}

// Average engagement for a platform from edges
function avgEngagement(edges: PerformanceEdge[], platform: string, nodes: BehaviorGraph['nodes']): string {
  const nodeIds = new Set(nodes.filter(n => n.platform.toLowerCase() === platform.toLowerCase()).map(n => n.node_id));
  const relevant = edges.filter(e => nodeIds.has(e.node_id));
  if (relevant.length === 0) return 'N/A';
  const sum = relevant.reduce((acc, e) => acc + engScore(e.engagement_level), 0);
  const avg = sum / relevant.length;
  if (avg >= 90) return 'very_high';
  if (avg >= 70) return 'high';
  if (avg >= 50) return 'medium';
  if (avg >= 30) return 'low';
  return 'very_low';
}

export default function BehaviorGraphBlock({ behaviorGraph, campaigns }: BehaviorGraphBlockProps) {
  const bg = behaviorGraph;

  const platformEntries = useMemo(
    () => Object.entries(bg.platform_best_content_type ?? {}),
    [bg.platform_best_content_type],
  );

  const topicEntries = useMemo(
    () => Object.entries(bg.topic_performance_summary ?? {}),
    [bg.topic_performance_summary],
  );

  const workedTags = useMemo(() => countTags(bg.edges, 'what_worked').slice(0, 10), [bg.edges]);
  const failedTags = useMemo(() => countTags(bg.edges, 'what_failed').slice(0, 10), [bg.edges]);

  // Segment performance
  const segmentPerf = useMemo(() => {
    const groups: Record<string, PerformanceEdge[]> = {};
    for (const e of bg.edges) {
      if (e.segment_id) {
        if (!groups[e.segment_id]) groups[e.segment_id] = [];
        groups[e.segment_id].push(e);
      }
    }
    return Object.entries(groups).map(([segId, edges]) => {
      const sum = edges.reduce((a, e) => a + engScore(e.engagement_level), 0);
      const avg = sum / edges.length;
      return { segId, count: edges.length, avgScore: avg };
    }).sort((a, b) => b.avgScore - a.avgScore);
  }, [bg.edges]);

  const isEmpty = !bg.overall_best_platform && platformEntries.length === 0 && bg.edges.length === 0;

  if (isEmpty) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
        <ChartBarIcon className="w-10 h-10 mx-auto mb-3 text-gray-300" />
        <p className="text-sm font-medium text-gray-500">Behavior Graph 데이터가 아직 없습니다</p>
        <p className="text-xs text-gray-400 mt-1">캠페인 성과를 입력하면 분석 결과가 여기에 표시됩니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* 1. Overall Best Platform */}
      {bg.overall_best_platform && (
        <div className="rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-purple-50/30 p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-200">
              <TrophyIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Best Platform</p>
              <p className="text-lg font-bold text-gray-800 capitalize">{bg.overall_best_platform}</p>
            </div>
            <span className={`ml-auto text-2xl`}>
              {meta(bg.overall_best_platform).emoji}
            </span>
          </div>
        </div>
      )}

      {/* 2. Platform Performance Cards */}
      {platformEntries.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <GlobeAltIcon className="w-4 h-4 text-gray-400" />
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Platform Performance</h4>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {platformEntries.map(([platform, contentType]) => {
              const m = meta(platform);
              const avgEng = avgEngagement(bg.edges, platform, bg.nodes);
              return (
                <div key={platform} className={`rounded-xl border ${m.border} ${m.bg} p-4`}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-xl">{m.emoji}</span>
                    <span className={`text-sm font-semibold capitalize ${m.color}`}>{platform}</span>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider">Best Content</p>
                      <p className="text-sm font-medium text-gray-700 capitalize">{contentType}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider">Avg Engagement</p>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-2 bg-white/80 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${engColor(avgEng)}`}
                            style={{ width: `${engScore(avgEng)}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-medium text-gray-500 capitalize w-16 text-right">
                          {avgEng.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Topic Performance Summary */}
      {topicEntries.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-2 mb-4">
            <TagIcon className="w-4 h-4 text-gray-400" />
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Topic Performance</h4>
          </div>
          <div className="space-y-2.5">
            {topicEntries.map(([topic, level]) => (
              <div key={topic} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 font-medium w-28 truncate shrink-0" title={topic}>
                  {topic}
                </span>
                <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${engColor(level)}`}
                    style={{ width: `${engScore(level)}%` }}
                  />
                </div>
                <span className="text-[10px] text-gray-400 capitalize w-16 text-right shrink-0">
                  {level.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. What Worked / What Failed */}
      {(workedTags.length > 0 || failedTags.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {workedTags.length > 0 && (
            <div className="rounded-xl border border-green-200 bg-green-50/50 p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
                <h4 className="text-xs font-semibold text-green-700 uppercase tracking-wider">What Worked</h4>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {workedTags.map(([tag, count]) => (
                  <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 border border-green-200 rounded-full text-xs">
                    {tag}
                    {count > 1 && <span className="text-[10px] text-green-500">x{count}</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
          {failedTags.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50/50 p-5">
              <div className="flex items-center gap-2 mb-3">
                <XCircleIcon className="w-4 h-4 text-red-500" />
                <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wider">What Failed</h4>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {failedTags.map(([tag, count]) => (
                  <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 border border-red-200 rounded-full text-xs">
                    {tag}
                    {count > 1 && <span className="text-[10px] text-red-500">x{count}</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 5. Segment Performance */}
      {segmentPerf.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-2 mb-4">
            <UserGroupIcon className="w-4 h-4 text-gray-400" />
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Segment Performance</h4>
          </div>
          <div className="space-y-3">
            {segmentPerf.map(({ segId, count, avgScore }) => {
              const level = avgScore >= 90 ? 'very_high' : avgScore >= 70 ? 'high' : avgScore >= 50 ? 'medium' : avgScore >= 30 ? 'low' : 'very_low';
              return (
                <div key={segId} className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                    <UserGroupIcon className="w-3.5 h-3.5 text-indigo-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-700 truncate">{segId}</span>
                      <span className="text-[10px] text-gray-400">{count} edges</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${engColor(level)}`}
                        style={{ width: `${avgScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-[10px] text-gray-400 capitalize w-16 text-right shrink-0">
                    {level.replace('_', ' ')}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
