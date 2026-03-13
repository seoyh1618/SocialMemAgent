/**
 * PerformanceChart — Recharts-based visualization for campaign performance
 *
 * Renders two charts from campaign_archive data:
 *   1. Bar chart: average CTR per platform (clicks / views * 100)
 *   2. Line chart: engagement score trend over time (high=3, medium=2, low=1)
 */

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { CampaignRecord } from '../../memory';

interface PerformanceChartProps {
  campaigns: CampaignRecord[];
}

const ENGAGEMENT_SCORE: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

const PLATFORM_COLORS = [
  '#6366f1', // indigo-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#14b8a6', // teal-500
  '#f59e0b', // amber-500
  '#10b981', // emerald-500
];

export default function PerformanceChart({ campaigns }: PerformanceChartProps) {
  // ── Compute platform CTR data ──────────────────────────────────────────
  const platformStats: Record<string, { totalClicks: number; totalViews: number }> = {};

  for (const c of campaigns) {
    if (!c.performance) continue;
    const { views, clicks } = c.performance;
    if (!views || views === 0) continue;
    for (const platform of c.platforms_used) {
      if (!platformStats[platform]) {
        platformStats[platform] = { totalClicks: 0, totalViews: 0 };
      }
      platformStats[platform].totalClicks += clicks ?? 0;
      platformStats[platform].totalViews += views;
    }
  }

  const ctrData = Object.entries(platformStats)
    .map(([platform, { totalClicks, totalViews }]) => ({
      platform,
      ctr: totalViews > 0 ? parseFloat(((totalClicks / totalViews) * 100).toFixed(2)) : 0,
    }))
    .sort((a, b) => b.ctr - a.ctr);

  // ── Compute engagement trend data ──────────────────────────────────────
  const trendData = campaigns
    .filter((c) => c.performance?.engagement_level)
    .slice(-10)
    .map((c, i) => ({
      label: `#${i + 1}`,
      campaign_id: c.campaign_id,
      score: ENGAGEMENT_SCORE[c.performance!.engagement_level!] ?? 0,
      engagement: c.performance!.engagement_level,
    }));

  const hasCtrData = ctrData.length > 0;
  const hasTrendData = trendData.length >= 2;

  if (!hasCtrData && !hasTrendData) return null;

  return (
    <div className="space-y-4 mt-3">
      {/* ── Platform CTR Bar Chart ── */}
      {hasCtrData && (
        <div>
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
            📊 Platform CTR (%)
          </p>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={ctrData} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="platform"
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                formatter={(value: number) => [`${value}%`, 'CTR']}
                labelFormatter={(label) => `Platform: ${label}`}
                contentStyle={{
                  fontSize: 11,
                  borderRadius: 6,
                  border: '1px solid #e2e8f0',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                }}
              />
              <Bar dataKey="ctr" radius={[3, 3, 0, 0]}>
                {ctrData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={PLATFORM_COLORS[index % PLATFORM_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Engagement Trend Line Chart ── */}
      {hasTrendData && (
        <div>
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
            📈 Engagement Trend
          </p>
          <ResponsiveContainer width="100%" height={100}>
            <LineChart data={trendData} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 3]}
                ticks={[1, 2, 3]}
                tick={{ fontSize: 9, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => (['', 'Low', 'Mid', 'High'] as const)[v] ?? ''}
              />
              <Tooltip
                formatter={(_: number, __: string, props: { payload?: { engagement?: string } }) => [
                  props.payload?.engagement ?? '',
                  'Engagement',
                ]}
                labelFormatter={(label) => `Campaign ${label}`}
                contentStyle={{
                  fontSize: 11,
                  borderRadius: 6,
                  border: '1px solid #e2e8f0',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
