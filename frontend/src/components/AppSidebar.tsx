/**
 * AppSidebar — 왼쪽 고정 사이드바
 * - 로그인 전: 로그인/회원가입 CTA
 * - 로그인 후: 사용자 프로필, MemGPT 메모리 요약, 메뉴
 */

import { useState } from 'react';
// framer-motion 제거 — React 19 호환성 문제로 CSS 애니메이션 사용
import { useAuth } from '../AuthContext';
import {
  SparklesIcon,
  UserCircleIcon,
  Squares2X2Icon,
  ClockIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  ChevronRightIcon,
  CpuChipIcon,
  PhotoIcon,
  ChatBubbleLeftRightIcon,
  PresentationChartLineIcon,
  CubeIcon,
  BookOpenIcon,
} from '@heroicons/react/24/outline';
import type { MemoryState } from '../memory';

type SidebarSection = 'chat' | 'profile' | 'products' | 'knowledge' | 'history' | 'conversations' | 'memory' | 'creations' | 'behavior';

interface AppSidebarProps {
  memory: MemoryState;
  activeSection: SidebarSection;
  onSectionChange: (s: SidebarSection) => void;
  totalCampaigns?: number;
}

export default function AppSidebar({
  memory,
  activeSection,
  onSectionChange,
  totalCampaigns = 0,
}: AppSidebarProps) {
  const { user, doLogout } = useAuth();
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const voice = memory.persona_block;
  const profile = memory.human_block;

  // 그룹화된 네비게이션
  const navGroups = [
    {
      title: '콘텐츠',
      items: [
        { id: 'chat' as const, icon: Squares2X2Icon, label: '콘텐츠 생성', accent: 'indigo' },
      ],
    },
    {
      title: '5-Block 메모리',
      items: [
        { id: 'profile' as const, icon: UserCircleIcon, label: 'Owner · Voice', accent: 'indigo' },
        { id: 'products' as const, icon: CubeIcon, label: '제품 카탈로그', accent: 'amber' },
        { id: 'knowledge' as const, icon: BookOpenIcon, label: '도메인 지식', accent: 'amber' },
      ],
    },
    {
      title: '성과 · 학습',
      items: [
        { id: 'history' as const, icon: ClockIcon, label: '캠페인', accent: 'rose' },
        { id: 'behavior' as const, icon: PresentationChartLineIcon, label: 'Behavior Graph', accent: 'rose' },
      ],
    },
    {
      title: '기록',
      items: [
        { id: 'conversations' as const, icon: ChatBubbleLeftRightIcon, label: '대화 히스토리', accent: 'teal' },
        { id: 'memory' as const, icon: CpuChipIcon, label: '메모리 맵', accent: 'purple' },
        { id: 'creations' as const, icon: PhotoIcon, label: 'Assets', accent: 'purple' },
      ],
    },
  ];

  const accentColors: Record<string, string> = {
    indigo: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    rose: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    teal: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  };

  return (
    <>
      {/* ─── Sidebar ─── */}
      <aside className="flex h-full w-64 flex-col bg-gray-950 text-white">

        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-white/[0.06]">
          <div
            className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20 hover:scale-105 hover:rotate-6 transition-transform duration-200"
          >
            <SparklesIcon className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-bold text-white tracking-tight">Social Agent</p>
            <p className="text-[10px] text-gray-500 font-medium tracking-wider">5-BLOCK MEMORY</p>
          </div>
        </div>

        {/* ─── User card ─── */}
        {user && (
          <div className="px-4 py-4 border-b border-white/10">
            <div className="flex items-center gap-3">
              {user.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt={user.displayName}
                  className="w-9 h-9 rounded-full shrink-0 border border-white/20"
                />
              ) : (
                <div className="w-9 h-9 rounded-full bg-indigo-600/50 flex items-center justify-center shrink-0">
                  <span className="text-sm font-bold text-indigo-200">
                    {user.displayName.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate">{user.displayName}</p>
                <p className="text-[10px] text-gray-400 truncate">@{user.username}</p>
              </div>
            </div>

            {/* Memory stats */}
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="bg-white/5 rounded-lg px-2.5 py-2 text-center">
                <p className="text-base font-bold text-indigo-400">{memory.total_campaigns}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">캠페인</p>
              </div>
              <div className="bg-white/5 rounded-lg px-2.5 py-2 text-center">
                <p className="text-base font-bold text-purple-400">
                  {voice.preferred_styles.length + voice.content_pillars.length}
                </p>
                <p className="text-[10px] text-gray-500 mt-0.5">메모리 항목</p>
              </div>
            </div>
          </div>
        )}

        {/* ─── Navigation (그룹화) ─── */}
        <nav className="flex-1 px-3 py-3 space-y-4 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.title}>
              <p className="px-2 mb-1.5 text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em]">{group.title}</p>
              <div className="space-y-0.5">
                {group.items.map(({ id, icon: Icon, label, accent }) => (
                  <button
                    key={id}
                    onClick={() => onSectionChange(id)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-all duration-150 relative hover:translate-x-0.5 active:scale-[0.98] ${
                      activeSection === id
                        ? `${accentColors[accent]} font-medium`
                        : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.03]'
                    }`}
                  >
                    {activeSection === id && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-full bg-current opacity-60" />
                    )}
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1 text-left truncate">{label}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* ─── 5-Block 메모리 상태 ─── */}
        {user && (
          <div className="px-3 py-3 border-t border-white/[0.06]">
            <p className="px-2 mb-2 text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em]">메모리 상태</p>
            <div className="space-y-0.5">
              {[
                { label: 'Owner', value: human.display_name || '미설정', color: 'text-indigo-400', dot: 'bg-indigo-500' },
                { label: 'Voice', value: (voice as any).tone_primary || voice.tone || '미설정', color: 'text-purple-400', dot: 'bg-purple-500' },
                { label: 'Product', value: `${(memory as any).product_archive?.length || 0}개`, color: 'text-amber-400', dot: 'bg-amber-500' },
                { label: 'Audience', value: `${memory.audience_block?.segments?.length || 0}개`, color: 'text-teal-400', dot: 'bg-teal-500' },
                { label: 'Campaign', value: `${memory.total_campaigns || 0}건`, color: 'text-rose-400', dot: 'bg-rose-500' },
              ].map(({ label, value, color, dot }, i) => (
                <div
                  key={label}
                  className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-white/[0.02] transition-all duration-200 animate-fade-in"
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${dot} shrink-0 ${value !== '미설정' && value !== '0개' && value !== '0건' ? 'animate-pulse' : 'opacity-30'}`} />
                  <span className="text-[10px] text-gray-600 w-14 shrink-0">{label}</span>
                  <span className={`text-[11px] ${color} truncate`}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ─── Bottom: logout ─── */}
        <div className="px-3 py-3 border-t border-white/10">
          {showLogoutConfirm ? (
            <div className="bg-red-950/50 border border-red-500/20 rounded-xl p-3">
              <p className="text-xs text-red-300 mb-2">로그아웃 하시겠습니까?</p>
              <div className="flex gap-2">
                <button
                  onClick={() => { doLogout(); setShowLogoutConfirm(false); }}
                  className="flex-1 py-1.5 text-xs bg-red-600 hover:bg-red-500 rounded-lg transition-colors"
                >
                  로그아웃
                </button>
                <button
                  onClick={() => setShowLogoutConfirm(false)}
                  className="flex-1 py-1.5 text-xs text-gray-400 hover:text-white border border-white/10 rounded-lg transition-colors"
                >
                  취소
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowLogoutConfirm(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-gray-500 hover:text-red-400 hover:bg-red-950/30 transition-all"
            >
              <ArrowRightOnRectangleIcon className="w-4.5 h-4.5" />
              <span>로그아웃</span>
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
