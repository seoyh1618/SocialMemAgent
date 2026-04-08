/**
 * AppSidebar — 왼쪽 고정 사이드바
 * - 로그인 전: 로그인/회원가입 CTA
 * - 로그인 후: 사용자 프로필, MemGPT 메모리 요약, 메뉴
 */

import { useState } from 'react';
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

  const navItems = [
    { id: 'chat' as const, icon: Squares2X2Icon, label: '콘텐츠 생성' },
    { id: 'profile' as const, icon: UserCircleIcon, label: '브랜드 프로필' },
    { id: 'products' as const, icon: CubeIcon, label: '제품 카탈로그' },
    { id: 'knowledge' as const, icon: BookOpenIcon, label: '도메인 지식' },
    { id: 'history' as const, icon: ClockIcon, label: '캠페인 히스토리' },
    { id: 'conversations' as const, icon: ChatBubbleLeftRightIcon, label: '대화 히스토리' },
    { id: 'memory' as const, icon: CpuChipIcon, label: '메모리 맵' },
    { id: 'behavior' as const, icon: PresentationChartLineIcon, label: 'Behavior Graph' },
    { id: 'creations' as const, icon: PhotoIcon, label: 'Assets' },
  ];

  return (
    <>
      {/* ─── Sidebar ─── */}
      <aside className="flex h-full w-64 flex-col bg-gray-950 text-white">

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/10">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0">
            <SparklesIcon className="w-4.5 h-4.5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-white truncate">Social Agent</p>
            <p className="text-[10px] text-indigo-400 font-medium">MemGPT Powered</p>
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

        {/* ─── Navigation ─── */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <p className="px-2 mb-2 text-[10px] font-semibold text-gray-600 uppercase tracking-widest">메뉴</p>
          {navItems.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => onSectionChange(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                activeSection === id
                  ? 'bg-indigo-600 text-white font-medium shadow-lg shadow-indigo-900/30'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Icon className="w-4.5 h-4.5 shrink-0" />
              <span className="flex-1 text-left">{label}</span>
              {activeSection === id && (
                <ChevronRightIcon className="w-3.5 h-3.5" />
              )}
            </button>
          ))}
        </nav>

        {/* ─── Memory snapshot ─── */}
        {user && (
          <div className="px-4 py-4 border-t border-white/10">
            <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2.5">
              브랜드 메모리 스냅샷
            </p>
            <div className="space-y-2">
              {voice.tone ? (
                <div className="flex items-start gap-2">
                  <span className="text-[10px] text-gray-600 w-10 shrink-0 pt-0.5">톤</span>
                  <span className="text-[11px] text-gray-300 italic truncate">"{voice.tone}"</span>
                </div>
              ) : (
                <p className="text-[11px] text-gray-600 italic">톤이 아직 설정되지 않았습니다</p>
              )}

              {voice.preferred_styles.length > 0 && (
                <div className="flex items-start gap-2">
                  <span className="text-[10px] text-gray-600 w-10 shrink-0 pt-0.5">스타일</span>
                  <div className="flex flex-wrap gap-1">
                    {voice.preferred_styles.slice(0, 3).map(s => (
                      <span key={s} className="text-[10px] bg-indigo-900/50 text-indigo-300 px-1.5 py-0.5 rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {voice.signature_hashtags.length > 0 && (
                <div className="flex items-start gap-2">
                  <span className="text-[10px] text-gray-600 w-10 shrink-0 pt-0.5"># </span>
                  <p className="text-[11px] text-indigo-400 truncate">
                    {voice.signature_hashtags.slice(0, 3).join(' ')}
                  </p>
                </div>
              )}

              {memory.working_summary && (
                <div className="mt-2 p-2.5 bg-white/5 rounded-lg">
                  <p className="text-[10px] text-gray-500 mb-1">최근 세션 요약</p>
                  <p className="text-[11px] text-gray-400 leading-relaxed line-clamp-2">
                    {memory.working_summary}
                  </p>
                </div>
              )}
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
