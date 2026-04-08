/**
 * MemoryMindMap — MemGPT 메모리를 SVG 기반 인터랙티브 그래프 노드로 시각화
 *
 * - 중심 노드: 브랜드명
 * - 위성 노드: Human Block, Persona Block, Recall Memory, Archival Memory
 * - 클릭 시 하위 노드 펼침 (2단계 방사형 배치)
 * - 마우스 휠로 줌인/아웃, 드래그로 팬
 * - 새 필드 감지 시 pulse 애니메이션
 * - isActive=true 이면 3초마다 loadUserMemory 호출
 */

import { useState, useEffect, useRef, useCallback, type WheelEvent, type PointerEvent } from 'react';
import type { MemoryState } from '../memory';
import { loadUserMemory } from '../api';
import { SparklesIcon, PencilSquareIcon } from '@heroicons/react/24/outline';

// ─── Types ────────────────────────────────────────────────────────────────────

interface MindNode {
  id: string;
  label: string;
  value?: string;
  icon?: string;
  color: NodeColor;
  children?: MindNode[];
  isNew?: boolean;
}

type NodeColor =
  | 'root'
  | 'human'
  | 'persona'
  | 'recall'
  | 'archival'
  | 'leaf'
  | 'tag'
  | 'extra'
  | 'campaign'
  | 'domain'
  | 'behavior'
  | 'performance';

interface Transform {
  x: number;
  y: number;
  scale: number;
}

interface Vec2 {
  x: number;
  y: number;
}

interface GraphNode {
  id: string;
  label: string;
  value?: string;
  icon?: string;
  color: NodeColor;
  pos: Vec2;
  radius: number;
  parentId?: string;
  isNew?: boolean;
  depth: number;
}

interface GraphEdge {
  from: Vec2;
  to: Vec2;
}

// ─── Color palette ────────────────────────────────────────────────────────────

const PALETTE: Record<NodeColor, { fill: string; stroke: string; text: string; glow: string }> = {
  root:     { fill: '#4f46e5', stroke: '#6366f1', text: '#ffffff', glow: '#818cf8' },
  human:    { fill: '#eef2ff', stroke: '#818cf8', text: '#3730a3', glow: '#a5b4fc' },
  persona:  { fill: '#f5f3ff', stroke: '#a78bfa', text: '#5b21b6', glow: '#c4b5fd' },
  recall:   { fill: '#fffbeb', stroke: '#fbbf24', text: '#92400e', glow: '#fcd34d' },
  archival: { fill: '#f0fdf4', stroke: '#34d399', text: '#065f46', glow: '#6ee7b7' },
  leaf:     { fill: '#f9fafb', stroke: '#d1d5db', text: '#374151', glow: '#e5e7eb' },
  tag:      { fill: '#f3f4f6', stroke: '#9ca3af', text: '#4b5563', glow: '#d1d5db' },
  extra:    { fill: '#eff6ff', stroke: '#93c5fd', text: '#1e40af', glow: '#bfdbfe' },
  campaign: { fill: '#ecfdf5', stroke: '#6ee7b7', text: '#064e3b', glow: '#a7f3d0' },
  domain:      { fill: '#fef3c7', stroke: '#f59e0b', text: '#78350f', glow: '#fcd34d' },
  behavior:    { fill: '#fce7f3', stroke: '#ec4899', text: '#831843', glow: '#f9a8d4' },
  performance: { fill: '#e0f2fe', stroke: '#0ea5e9', text: '#0c4a6e', glow: '#7dd3fc' },
};

// ─── Build tree from MemoryState ──────────────────────────────────────────────

function buildTree(memory: MemoryState, prevMemory: MemoryState | null): MindNode {
  const human = memory.human_block;
  const persona = memory.persona_block;
  const domain = memory.domain_block;
  const audience = memory.audience_block;
  const prevHuman = prevMemory?.human_block;
  const prevPersona = prevMemory?.persona_block;
  const prevDomain = prevMemory?.domain_block;
  const prevAudience = prevMemory?.audience_block;

  const isNew = (cur: string | null | undefined, prev: string | null | undefined) =>
    !!cur && cur !== prev;

  const isNewTag = (tag: string, prevList: string[] | undefined) =>
    !prevList?.includes(tag);

  // Human Block (Owner Profile — 드릴다운)
  const humanChildren: MindNode[] = [];
  if (human.display_name)
    humanChildren.push({ id: 'h-name', label: '브랜드명', value: human.display_name, color: 'leaf', isNew: isNew(human.display_name, prevHuman?.display_name) });
  if ((human as any).owner_name)
    humanChildren.push({ id: 'h-owner', label: '대표자', value: (human as any).owner_name, color: 'leaf' });
  if ((human as any).business_location)
    humanChildren.push({ id: 'h-loc', label: '위치', value: (human as any).business_location, color: 'leaf' });
  if ((human as any).industry)
    humanChildren.push({ id: 'h-ind', label: '업종', value: (human as any).industry, color: 'leaf' });
  if ((human as any).primary_goal)
    humanChildren.push({ id: 'h-goal', label: '목표', value: (human as any).primary_goal, color: 'leaf' });
  if ((human as any).business_stage)
    humanChildren.push({ id: 'h-stage', label: '단계', value: (human as any).business_stage, color: 'leaf' });
  // SNS 핸들 (social_handles 또는 레거시)
  const handles = (human as any).social_handles || {};
  const handleEntries = Object.entries(handles);
  if (handleEntries.length > 0) {
    humanChildren.push({
      id: 'h-sns', label: `SNS (${handleEntries.length})`, color: 'extra',
      children: handleEntries.map(([k, v]) => ({
        id: `h-sns-${k}`, label: k, value: String(v), color: 'leaf' as NodeColor,
      })),
    });
  } else {
    if (human.twitter_handle)
      humanChildren.push({ id: 'h-tw', label: '𝕏 Twitter', value: `@${human.twitter_handle}`, color: 'leaf' });
    if (human.instagram_handle)
      humanChildren.push({ id: 'h-ig', label: '📸 Instagram', value: `@${human.instagram_handle}`, color: 'leaf' });
  }
  const extraEntries = Object.entries(human.extra_fields || {});
  if (extraEntries.length > 0) {
    humanChildren.push({
      id: 'h-extra', label: `추가 정보 (${extraEntries.length})`, color: 'extra',
      children: extraEntries.map(([k, v]) => ({
        id: `h-extra-${k}`, label: k.replace(/_/g, ' '), value: v, color: 'leaf' as NodeColor,
      })),
    });
  }

  // Persona Block (Brand Voice — 드릴다운)
  const personaChildren: MindNode[] = [];
  const tonePrimary = (persona as any).tone_primary || persona.tone;
  if (tonePrimary)
    personaChildren.push({ id: 'p-tone', label: '톤앤매너', value: `"${tonePrimary}"`, color: 'leaf', isNew: isNew(tonePrimary, (prevPersona as any)?.tone_primary || prevPersona?.tone) });
  if ((persona as any).tone_formality)
    personaChildren.push({ id: 'p-formal', label: '격식', value: (persona as any).tone_formality, color: 'leaf' });
  if ((persona as any).slogan)
    personaChildren.push({ id: 'p-slogan', label: '슬로건', value: (persona as any).slogan, color: 'leaf' });
  if ((persona as any).emoji_usage)
    personaChildren.push({ id: 'p-emoji', label: '이모지', value: (persona as any).emoji_usage, color: 'leaf' });
  if (persona.content_pillars.length > 0)
    personaChildren.push({
      id: 'p-pillars', label: `콘텐츠 기둥 (${persona.content_pillars.length})`, color: 'leaf',
      children: persona.content_pillars.map((p, i) => ({
        id: `p-pillar-${i}`, label: p, color: 'tag' as NodeColor,
        isNew: isNewTag(p, prevPersona?.content_pillars),
      })),
    });
  if (persona.preferred_styles.length > 0)
    personaChildren.push({
      id: 'p-styles', label: `스타일 (${persona.preferred_styles.length})`, color: 'leaf',
      children: persona.preferred_styles.map((s, i) => ({
        id: `p-style-${i}`, label: s, color: 'tag' as NodeColor,
        isNew: isNewTag(s, prevPersona?.preferred_styles),
      })),
    });
  if (persona.signature_hashtags.length > 0)
    personaChildren.push({
      id: 'p-hashtags', label: `해시태그 (${persona.signature_hashtags.length})`, color: 'leaf',
      children: persona.signature_hashtags.map((h, i) => ({
        id: `p-hash-${i}`, label: h.startsWith('#') ? h : `#${h}`, color: 'tag' as NodeColor,
        isNew: isNewTag(h, prevPersona?.signature_hashtags),
      })),
    });
  if (persona.avoid_topics.length > 0)
    personaChildren.push({
      id: 'p-avoid', label: `금지 주제 (${persona.avoid_topics.length})`, color: 'leaf',
      children: persona.avoid_topics.map((t, i) => ({
        id: `p-avoid-${i}`, label: t, color: 'tag' as NodeColor,
        isNew: isNewTag(t, prevPersona?.avoid_topics),
      })),
    });

  // Domain Block
  const domainChildren: MindNode[] = [];
  if (domain.industry)
    domainChildren.push({ id: 'd-ind', label: '업종', value: domain.industry, color: 'leaf', isNew: isNew(domain.industry, prevDomain?.industry) });
  if (domain.domain_type)
    domainChildren.push({ id: 'd-type', label: '업종 유형', value: domain.domain_type, color: 'leaf', isNew: isNew(domain.domain_type, prevDomain?.domain_type) });
  if (domain.business_location)
    domainChildren.push({ id: 'd-loc', label: '위치', value: domain.business_location, color: 'leaf', isNew: isNew(domain.business_location, prevDomain?.business_location) });
  if (domain.price_range)
    domainChildren.push({ id: 'd-price', label: '가격대', value: domain.price_range, color: 'leaf', isNew: isNew(domain.price_range, prevDomain?.price_range) });
  if (domain.usp)
    domainChildren.push({ id: 'd-usp', label: 'USP', value: domain.usp.length > 25 ? domain.usp.slice(0, 25) + '…' : domain.usp, color: 'leaf', isNew: isNew(domain.usp, prevDomain?.usp) });
  if (domain.competitors?.length)
    domainChildren.push({
      id: 'd-comp', label: `경쟁사 (${domain.competitors.length})`, color: 'leaf',
      children: domain.competitors.map((c, i) => ({
        id: `d-comp-${i}`, label: c, color: 'tag' as NodeColor,
        isNew: !prevDomain?.competitors?.includes(c),
      })),
    });
  if (domain.operating_hours)
    domainChildren.push({ id: 'd-hours', label: '영업시간', value: domain.operating_hours, color: 'leaf' });
  // Domain Knowledge (flexible key-value entries)
  const knowledge = domain.knowledge || [];
  if (knowledge.length > 0) {
    domainChildren.push({
      id: 'd-knowledge', label: `도메인 지식 (${knowledge.length})`, color: 'leaf',
      children: knowledge.slice(0, 10).map((k, i) => ({
        id: `d-know-${i}`,
        label: `${k.key?.replace(/_/g, ' ')}: ${(k.value || '').slice(0, 30)}${(k.value || '').length > 30 ? '…' : ''}`,
        color: 'tag' as NodeColor,
        isNew: !prevDomain || !prevDomain.knowledge?.some((pk) => pk.key === k.key && pk.value === k.value),
      })),
    });
  }

  // Audience Block
  const audienceChildren: MindNode[] = [];
  if (audience.target_platforms.length > 0)
    audienceChildren.push({
      id: 'a-plat', label: '활성 플랫폼', color: 'leaf',
      children: audience.target_platforms.map((p, i) => ({
        id: `a-plat-${i}`, label: p, color: 'tag' as NodeColor,
        isNew: isNewTag(p, prevAudience?.target_platforms),
      })),
    });
  const ageRange = audience.default_age_range || (audience as any).target_age_range;
  const prevAgeRange = prevAudience?.default_age_range || (prevAudience as any)?.target_age_range;
  if (ageRange)
    audienceChildren.push({ id: 'a-age', label: '기본 연령대', value: ageRange, color: 'leaf', isNew: isNew(ageRange, prevAgeRange) });
  const segments = audience.segments || [];
  const prevSegments = prevAudience?.segments || [];
  if (segments.length)
    audienceChildren.push({
      id: 'a-seg', label: `세그먼트 (${segments.length})`, color: 'leaf',
      children: segments.map((s, i) => ({
        id: `a-seg-${i}`, label: s.name, color: 'tag' as NodeColor,
        isNew: !prevSegments.some(ps => ps.name === s.name),
      })),
    });
  if (audience.seasonal_peaks?.length)
    audienceChildren.push({
      id: 'a-season', label: `성수기 (${audience.seasonal_peaks.length})`, color: 'leaf',
      children: audience.seasonal_peaks.map((s, i) => ({
        id: `a-season-${i}`, label: s, color: 'tag' as NodeColor,
        isNew: !prevAudience?.seasonal_peaks?.includes(s),
      })),
    });
  if (audience.offline_channels?.length)
    audienceChildren.push({
      id: 'a-offline', label: `오프라인 (${audience.offline_channels.length})`, color: 'leaf',
      children: audience.offline_channels.map((ch, i) => ({
        id: `a-offline-${i}`, label: ch, color: 'tag' as NodeColor,
        isNew: !prevAudience?.offline_channels?.includes(ch),
      })),
    });

  // Behavior Graph
  const bg = memory.behavior_graph;
  const prevBg = prevMemory?.behavior_graph;
  const behaviorChildren: MindNode[] = [];
  if (bg) {
    if (bg.overall_best_platform)
      behaviorChildren.push({ id: 'bg-best', label: '최고 플랫폼', value: bg.overall_best_platform, color: 'leaf', isNew: isNew(bg.overall_best_platform, prevBg?.overall_best_platform) });
    const pbc = Object.entries(bg.platform_best_content_type || {});
    if (pbc.length)
      behaviorChildren.push({
        id: 'bg-pbc', label: `플랫폼별 최적 (${pbc.length})`, color: 'leaf',
        children: pbc.map(([plat, ctype]) => ({
          id: `bg-pbc-${plat}`, label: `${plat}: ${ctype}`, color: 'tag' as NodeColor,
        })),
      });
    const tps = Object.entries(bg.topic_performance_summary || {});
    if (tps.length)
      behaviorChildren.push({
        id: 'bg-topic', label: `주제별 성과 (${tps.length})`, color: 'leaf',
        children: tps.map(([topic, level]) => ({
          id: `bg-topic-${topic}`, label: `${topic}: ${level}`, color: 'tag' as NodeColor,
        })),
      });
    // Aggregate what_worked / what_failed
    const workedFreq: Record<string, number> = {};
    const failedFreq: Record<string, number> = {};
    for (const edge of (bg.edges || [])) {
      for (const w of (edge.what_worked || [])) workedFreq[w] = (workedFreq[w] || 0) + 1;
      for (const f of (edge.what_failed || [])) failedFreq[f] = (failedFreq[f] || 0) + 1;
    }
    const topWorked = Object.entries(workedFreq).sort((a, b) => b[1] - a[1]).slice(0, 4);
    const topFailed = Object.entries(failedFreq).sort((a, b) => b[1] - a[1]).slice(0, 3);
    if (topWorked.length)
      behaviorChildren.push({
        id: 'bg-worked', label: `잘 되는 요소 (${topWorked.length})`, color: 'leaf',
        children: topWorked.map(([tag]) => ({ id: `bg-w-${tag}`, label: tag, color: 'tag' as NodeColor })),
      });
    if (topFailed.length)
      behaviorChildren.push({
        id: 'bg-failed', label: `피해야 할 요소 (${topFailed.length})`, color: 'leaf',
        children: topFailed.map(([tag]) => ({ id: `bg-f-${tag}`, label: `⚠ ${tag}`, color: 'tag' as NodeColor })),
      });
  }

  // Performance Summary (from campaigns with performance data)
  const perfCampaigns = (memory.campaign_archive ?? []).filter(c => c.performance);
  const perfChildren: MindNode[] = [];
  if (perfCampaigns.length) {
    // Platform CTR
    const platCtrs: Record<string, number[]> = {};
    for (const c of perfCampaigns) {
      const p = c.performance!;
      for (const plat of (c.platforms_used || [])) {
        if (!platCtrs[plat]) platCtrs[plat] = [];
        if (p.views && p.views > 0 && p.clicks) {
          platCtrs[plat].push(Math.round(p.clicks / p.views * 10000) / 100);
        }
      }
    }
    const platAvgs = Object.entries(platCtrs)
      .filter(([, ctrs]) => ctrs.length > 0)
      .map(([plat, ctrs]) => ({ plat, avg: Math.round(ctrs.reduce((a, b) => a + b, 0) / ctrs.length * 100) / 100 }))
      .sort((a, b) => b.avg - a.avg);
    if (platAvgs.length)
      perfChildren.push({
        id: 'perf-ctr', label: '플랫폼별 CTR', color: 'leaf',
        children: platAvgs.map(({ plat, avg }) => ({
          id: `perf-ctr-${plat}`, label: `${plat}: ${avg}%`, color: 'tag' as NodeColor,
        })),
      });

    // Trend direction
    const levelScore: Record<string, number> = { high: 3, medium: 2, low: 1 };
    const recent3 = perfCampaigns.slice(-3);
    const prev3 = perfCampaigns.slice(-6, -3);
    const avgScore = (list: typeof recent3) => {
      const scores = list.map(c => levelScore[(c.performance?.engagement_level || '').toLowerCase()] || 0);
      return scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    };
    const rScore = avgScore(recent3);
    const pScore = avgScore(prev3);
    let trend = '→ 안정';
    if (pScore > 0 && rScore > pScore) trend = '↑ 개선 중';
    else if (pScore > 0 && rScore < pScore) trend = '↓ 하락 중';
    perfChildren.push({ id: 'perf-trend', label: '성과 추이', value: trend, color: 'leaf' });
    perfChildren.push({ id: 'perf-count', label: '성과 데이터', value: `${perfCampaigns.length}개 캠페인`, color: 'leaf' });
  }

  // Archival Memory
  const campaigns = [...(memory.campaign_archive ?? [])].reverse().slice(0, 5);
  const archivalChildren: MindNode[] = campaigns.map((c) => ({
    id: `camp-${c.campaign_id}`,
    label: c.goal.length > 22 ? c.goal.slice(0, 22) + '…' : c.goal,
    color: 'campaign' as NodeColor,
    isNew: !prevMemory?.campaign_archive.some(pc => pc.campaign_id === c.campaign_id),
    children: [
      c.selected_trend ? { id: `camp-${c.campaign_id}-trend`, label: `트렌드: ${c.selected_trend}`, color: 'leaf' as NodeColor } : null,
      c.platforms_used.length ? { id: `camp-${c.campaign_id}-plat`, label: c.platforms_used.join(', '), color: 'tag' as NodeColor } : null,
      c.guideline_summary ? { id: `camp-${c.campaign_id}-guide`, label: c.guideline_summary.slice(0, 30) + (c.guideline_summary.length > 30 ? '…' : ''), color: 'leaf' as NodeColor } : null,
      c.performance ? { id: `camp-${c.campaign_id}-perf`, label: `성과: ${c.performance.engagement_level || 'N/A'}`, color: 'performance' as NodeColor } : null,
    ].filter(Boolean) as MindNode[],
  }));

  // Recall Memory — recent turns count + summary
  const recallLog = memory.recall_log || [];
  const recallChildren: MindNode[] = [];
  if (recallLog.length > 0) {
    recallChildren.push({ id: 'recall-count', label: '최근 대화', value: `${recallLog.length}턴`, color: 'leaf' });
  }
  if (memory.working_summary) {
    recallChildren.push({
      id: 'recall-summary',
      label: memory.working_summary.length > 50 ? memory.working_summary.slice(0, 50) + '…' : memory.working_summary,
      color: 'leaf' as NodeColor,
      isNew: memory.working_summary !== prevMemory?.working_summary,
    });
  }

  return {
    id: 'root',
    label: human.display_name || '내 브랜드',
    color: 'root',
    children: [
      { id: 'human', label: 'Owner Profile', icon: '👤', color: 'human', children: humanChildren },
      { id: 'persona', label: 'Brand Voice', icon: '🎨', color: 'persona', children: personaChildren },
      ...(domainChildren.length ? [{
        id: 'domain', label: 'Business Block', icon: '🏪', color: 'domain' as NodeColor, children: domainChildren,
      }] : []),
      ...(audienceChildren.length ? [{
        id: 'audience', label: 'Audience Block', icon: '🎯', color: 'extra' as NodeColor, children: audienceChildren,
      }] : []),
      ...(behaviorChildren.length ? [{
        id: 'behavior', label: 'Campaign Block', icon: '📊', color: 'behavior' as NodeColor, children: behaviorChildren,
      }] : []),
      ...(perfChildren.length ? [{
        id: 'performance', label: 'Performance', icon: '📈', color: 'performance' as NodeColor, children: perfChildren,
      }] : []),
      ...(recallChildren.length ? [{
        id: 'recall', label: 'Recall Memory', icon: '💭', color: 'recall' as NodeColor,
        children: recallChildren,
      }] : []),
      ...(archivalChildren.length ? [{
        id: 'archival',
        label: `Archival (${memory.total_campaigns ?? campaigns.length})`,
        icon: '🗄',
        color: 'archival' as NodeColor,
        children: archivalChildren,
      }] : []),
    ],
  };
}

// ─── Build flat graph node/edge list from tree ────────────────────────────────

function buildGraph(
  tree: MindNode,
  expandedIds: Set<string>,
  newIds: Set<string>,
  svgW: number,
  svgH: number
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  const cx = svgW / 2;
  const cy = svgH / 2;

  // Root node
  const rootNode: GraphNode = {
    id: tree.id,
    label: tree.label,
    icon: tree.icon,
    color: tree.color,
    pos: { x: cx, y: cy },
    radius: 44,
    depth: 0,
    isNew: newIds.has(tree.id),
  };
  nodes.push(rootNode);

  const satelliteNodes = tree.children ?? [];
  const L1_RADIUS = 155; // distance from root to L1 nodes

  satelliteNodes.forEach((sat, si) => {
    const angle = (2 * Math.PI * si) / satelliteNodes.length - Math.PI / 2;
    const px = cx + L1_RADIUS * Math.cos(angle);
    const py = cy + L1_RADIUS * Math.sin(angle);

    const satNode: GraphNode = {
      id: sat.id,
      label: sat.label,
      icon: sat.icon,
      color: sat.color,
      pos: { x: px, y: py },
      radius: 36,
      parentId: 'root',
      depth: 1,
      isNew: newIds.has(sat.id),
    };
    nodes.push(satNode);
    edges.push({ from: { x: cx, y: cy }, to: { x: px, y: py } });

    if (!expandedIds.has(sat.id)) return;

    const children = sat.children ?? [];
    const L2_RADIUS = 110;

    children.forEach((child, ci) => {
      // spread child nodes in a fan around the satellite direction
      const totalSpread = Math.min(children.length * 0.32, Math.PI * 0.9);
      const startAngle = angle - totalSpread / 2;
      const childAngle = children.length === 1
        ? angle
        : startAngle + (totalSpread / (children.length - 1)) * ci;

      const cpx = px + L2_RADIUS * Math.cos(childAngle);
      const cpy = py + L2_RADIUS * Math.sin(childAngle);

      const childNode: GraphNode = {
        id: child.id,
        label: child.label,
        value: child.value,
        icon: child.icon,
        color: child.color,
        pos: { x: cpx, y: cpy },
        radius: 28,
        parentId: sat.id,
        depth: 2,
        isNew: newIds.has(child.id),
      };
      nodes.push(childNode);
      edges.push({ from: { x: px, y: py }, to: { x: cpx, y: cpy } });
    });
  });

  return { nodes, edges };
}

// ─── Detail popup component ───────────────────────────────────────────────────

interface DetailPopupProps {
  node: GraphNode;
  treeNode: MindNode | null;
  onClose: () => void;
}

function DetailPopup({ node, treeNode, onClose }: DetailPopupProps) {
  const p = PALETTE[node.color];

  return (
    <div
      className="absolute top-4 right-4 z-10 w-64 rounded-2xl shadow-xl border overflow-hidden"
      style={{ background: p.fill, borderColor: p.stroke }}
    >
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${p.stroke}` }}>
        <div className="flex items-center gap-2">
          {node.icon && <span className="text-base">{node.icon}</span>}
          <span className="text-xs font-bold" style={{ color: p.text }}>{node.label}</span>
        </div>
        <button onClick={onClose} className="text-xs opacity-40 hover:opacity-80 transition-opacity" style={{ color: p.text }}>✕</button>
      </div>
      <div className="px-4 py-3 space-y-2 max-h-56 overflow-y-auto">
        {node.value && (
          <p className="text-xs" style={{ color: p.text }}>{node.value}</p>
        )}
        {treeNode?.children && treeNode.children.length > 0 && (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold opacity-60" style={{ color: p.text }}>하위 항목</p>
            {treeNode.children.map(c => (
              <div key={c.id} className="flex items-start gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: PALETTE[c.color].stroke }} />
                <div>
                  <span className="text-[11px] font-medium" style={{ color: p.text }}>{c.label}</span>
                  {c.value && <span className="ml-1 text-[10px] opacity-70" style={{ color: p.text }}>{c.value}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
        {node.isNew && (
          <div className="mt-1">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-indigo-500 text-white">
              ✨ NEW
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── SVG graph component ──────────────────────────────────────────────────────

const SVG_W = 700;
const SVG_H = 500;

interface GraphViewProps {
  tree: MindNode;
  expandedIds: Set<string>;
  newIds: Set<string>;
  onToggle: (id: string) => void;
}

function GraphView({ tree, expandedIds, newIds, onToggle }: GraphViewProps) {
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, scale: 1 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState<Vec2>({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const { nodes, edges } = buildGraph(tree, expandedIds, newIds, SVG_W, SVG_H);

  const findTreeNode = (id: string, node: MindNode): MindNode | null => {
    if (node.id === id) return node;
    for (const c of node.children ?? []) {
      const found = findTreeNode(id, c);
      if (found) return found;
    }
    return null;
  };

  const handleWheel = (e: WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    setTransform(prev => ({
      ...prev,
      scale: Math.min(3, Math.max(0.3, prev.scale * factor)),
    }));
  };

  const handlePointerDown = (e: PointerEvent<SVGSVGElement>) => {
    if ((e.target as SVGElement).closest('.graph-node')) return;
    setDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    (e.target as SVGElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: PointerEvent<SVGSVGElement>) => {
    if (!dragging) return;
    setTransform(prev => ({
      ...prev,
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    }));
  };

  const handlePointerUp = () => setDragging(false);

  const handleNodeClick = (gn: GraphNode) => {
    // If it has children in the tree, toggle expand
    const treeNode = findTreeNode(gn.id, tree);
    if (treeNode?.children && treeNode.children.length > 0) {
      onToggle(gn.id);
    }
    setSelectedNode(prev => prev?.id === gn.id ? null : gn);
  };

  const resetView = () => setTransform({ x: 0, y: 0, scale: 1 });

  const selTreeNode = selectedNode ? findTreeNode(selectedNode.id, tree) : null;

  return (
    <div className="relative w-full h-full overflow-hidden bg-gradient-to-br from-slate-50 to-indigo-50/30">
      {/* Controls */}
      <div className="absolute bottom-3 left-3 z-10 flex gap-1.5">
        <button
          onClick={() => setTransform(p => ({ ...p, scale: Math.min(3, p.scale * 1.2) }))}
          className="w-7 h-7 rounded-lg bg-white shadow border border-gray-200 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600 transition-colors text-sm font-bold"
        >+</button>
        <button
          onClick={() => setTransform(p => ({ ...p, scale: Math.max(0.3, p.scale * 0.83) }))}
          className="w-7 h-7 rounded-lg bg-white shadow border border-gray-200 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600 transition-colors text-sm font-bold"
        >−</button>
        <button
          onClick={resetView}
          className="px-2 h-7 rounded-lg bg-white shadow border border-gray-200 text-[10px] text-gray-500 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
        >초기화</button>
      </div>

      {/* Hint */}
      <div className="absolute bottom-3 right-3 z-10 text-[9px] text-gray-300 select-none">
        드래그·휠로 이동/줌 · 노드 클릭으로 펼치기
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className={`w-full h-full select-none ${dragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <defs>
          {(Object.keys(PALETTE) as NodeColor[]).map(c => (
            <filter key={c} id={`glow-${c}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          ))}
          <filter id="glow-new" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
          {/* Edges */}
          {edges.map((e, i) => (
            <line
              key={i}
              x1={e.from.x} y1={e.from.y}
              x2={e.to.x} y2={e.to.y}
              stroke="#c7d2fe"
              strokeWidth="1.5"
              strokeDasharray="4 3"
              opacity="0.7"
            />
          ))}

          {/* Nodes */}
          {nodes.map(gn => {
            const p = PALETTE[gn.color];
            const isSelected = selectedNode?.id === gn.id;
            const hasChildren = (findTreeNode(gn.id, tree)?.children?.length ?? 0) > 0;
            const isExpanded = expandedIds.has(gn.id);

            return (
              <g
                key={gn.id}
                className="graph-node"
                transform={`translate(${gn.pos.x},${gn.pos.y})`}
                onClick={() => handleNodeClick(gn)}
                style={{ cursor: hasChildren ? 'pointer' : 'default' }}
              >
                {/* Outer glow ring for new nodes */}
                {gn.isNew && (
                  <circle
                    r={gn.radius + 6}
                    fill="none"
                    stroke="#818cf8"
                    strokeWidth="2"
                    opacity="0.6"
                    filter="url(#glow-new)"
                  >
                    <animate attributeName="opacity" values="0.6;0.15;0.6" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="r" values={`${gn.radius + 4};${gn.radius + 9};${gn.radius + 4}`} dur="1.8s" repeatCount="indefinite" />
                  </circle>
                )}

                {/* Selection ring */}
                {isSelected && (
                  <circle r={gn.radius + 5} fill="none" stroke="#6366f1" strokeWidth="2.5" opacity="0.7" />
                )}

                {/* Main circle */}
                <circle
                  r={gn.radius}
                  fill={gn.depth === 0 ? 'url(#rootGrad)' : p.fill}
                  stroke={isSelected ? '#6366f1' : p.stroke}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  filter={gn.isNew ? 'url(#glow-new)' : undefined}
                />

                {/* Icon */}
                {gn.icon && (
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={gn.radius * 0.55}
                    dy={gn.label ? -gn.radius * 0.22 : 0}
                  >
                    {gn.icon}
                  </text>
                )}

                {/* Label */}
                <text
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={gn.depth === 0 ? 10 : gn.depth === 1 ? 8.5 : 7.5}
                  fontWeight={gn.depth <= 1 ? '700' : '500'}
                  fill={gn.depth === 0 ? '#ffffff' : p.text}
                  dy={gn.icon ? gn.radius * 0.28 : 0}
                  style={{ userSelect: 'none', pointerEvents: 'none' }}
                >
                  {gn.label.length > (gn.depth === 0 ? 10 : gn.depth === 1 ? 12 : 14)
                    ? gn.label.slice(0, gn.depth === 0 ? 10 : gn.depth === 1 ? 12 : 14) + '…'
                    : gn.label}
                </text>

                {/* Expand indicator */}
                {hasChildren && gn.depth < 2 && (
                  <text
                    x={gn.radius - 4}
                    y={-gn.radius + 4}
                    fontSize="8"
                    fill={p.stroke}
                    fontWeight="bold"
                    style={{ userSelect: 'none', pointerEvents: 'none' }}
                  >
                    {isExpanded ? '−' : '+'}
                  </text>
                )}

                {/* NEW badge */}
                {gn.isNew && (
                  <g transform={`translate(${gn.radius - 6},${-gn.radius + 6})`}>
                    <circle r="7" fill="#6366f1" />
                    <text textAnchor="middle" dominantBaseline="middle" fontSize="5" fill="white" fontWeight="bold" style={{ userSelect: 'none', pointerEvents: 'none' }}>N</text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Root gradient */}
          <defs>
            <radialGradient id="rootGrad" cx="40%" cy="35%">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#4f46e5" />
            </radialGradient>
          </defs>
        </g>
      </svg>

      {/* Detail popup */}
      {selectedNode && (
        <DetailPopup
          node={selectedNode}
          treeNode={selTreeNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface MemoryMindMapProps {
  initialMemory: MemoryState;
  userId: string;
  isActive: boolean;
  onEditClick?: () => void;
}

export default function MemoryMindMap({ initialMemory, userId, isActive, onEditClick }: MemoryMindMapProps) {
  const [memory, setMemory] = useState<MemoryState>(initialMemory);
  const prevMemoryRef = useRef<MemoryState | null>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(['human', 'persona', 'domain']));
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { setMemory(initialMemory); }, [initialMemory]);

  const refresh = useCallback(async () => {
    const fresh = await loadUserMemory(userId);
    setMemory(prev => {
      prevMemoryRef.current = prev;
      return fresh;
    });
    setLastUpdated(new Date());
  }, [userId]);

  // Detect new nodes
  useEffect(() => {
    const tree = buildTree(memory, prevMemoryRef.current);
    const freshIds = new Set<string>();
    const walk = (node: MindNode) => {
      if (node.isNew) freshIds.add(node.id);
      node.children?.forEach(walk);
    };
    walk(tree);

    if (freshIds.size > 0) {
      setNewIds(freshIds);
      setExpandedIds(prev => {
        const next = new Set(prev);
        const expandParents = (node: MindNode) => {
          if (node.children?.some(c => freshIds.has(c.id) || c.children?.some(gc => freshIds.has(gc.id)))) {
            next.add(node.id);
          }
          node.children?.forEach(expandParents);
        };
        expandParents(tree);
        return next;
      });
      const timer = setTimeout(() => setNewIds(new Set()), 4000);
      return () => clearTimeout(timer);
    }
  }, [memory]);

  // Polling
  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (isActive) pollingRef.current = setInterval(refresh, 3000);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [isActive, refresh]);

  const toggle = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const tree = buildTree(memory, prevMemoryRef.current);

  const isEmpty =
    !memory.human_block.display_name &&
    !memory.domain_block.industry &&
    !memory.persona_block.tone &&
    memory.persona_block.content_pillars.length === 0 &&
    memory.campaign_archive.length === 0 &&
    Object.keys(memory.human_block.extra_fields ?? {}).length === 0;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white/80">
        <div>
          <h2 className="text-sm font-bold text-gray-900">브랜드 메모리 맵</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-[10px] text-gray-400">MemGPT 지식 그래프</p>
            {isActive && (
              <span className="flex items-center gap-1 text-[10px] text-indigo-500">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
                실시간 동기화 중
              </span>
            )}
            {lastUpdated && !isActive && (
              <span className="text-[10px] text-gray-300">
                {lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })} 업데이트
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            className="text-[10px] text-gray-400 hover:text-indigo-600 transition-colors px-2 py-1 rounded-lg hover:bg-indigo-50"
          >새로고침</button>
          {onEditClick && (
            <button
              onClick={onEditClick}
              className="flex items-center gap-1 text-[11px] font-medium text-indigo-600 border border-indigo-200 rounded-lg px-2.5 py-1 hover:bg-indigo-50 transition-colors"
            >
              <PencilSquareIcon className="w-3 h-3" />
              편집
            </button>
          )}
        </div>
      </div>

      {/* Graph / Empty state */}
      <div className="flex-1 overflow-hidden">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-16 px-6">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-3">
              <SparklesIcon className="w-6 h-6 text-indigo-500" />
            </div>
            <h3 className="text-sm font-semibold text-gray-600 mb-1">메모리가 비어 있습니다</h3>
            <p className="text-xs text-gray-400 leading-relaxed max-w-xs">
              에이전트와 대화하면 브랜드 정보가 자동으로 노드로 추가됩니다.
            </p>
            {onEditClick && (
              <button
                onClick={onEditClick}
                className="mt-4 px-4 py-2 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >직접 입력하기</button>
            )}
          </div>
        ) : (
          <GraphView
            tree={tree}
            expandedIds={expandedIds}
            newIds={newIds}
            onToggle={toggle}
          />
        )}
      </div>

      {/* Stats footer */}
      {!isEmpty && (
        <div className="shrink-0 border-t border-gray-100 px-4 py-2 flex items-center gap-4 bg-gray-50/60">
          {[
            { label: '캠페인', val: memory.total_campaigns },
            { label: '해시태그', val: memory.persona_block.signature_hashtags.length },
            { label: '기둥', val: memory.persona_block.content_pillars.length },
            { label: '추가 정보', val: Object.keys(memory.human_block.extra_fields ?? {}).length },
          ].map(({ label, val }) => (
            <div key={label} className="text-center">
              <p className="text-xs font-bold text-indigo-600">{val}</p>
              <p className="text-[9px] text-gray-400">{label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
