/**
 * KnowledgeBlock — 도메인 지식 카탈로그 뷰
 * Core에는 ID+category+title만 주입, 이 컴포넌트에서 상세 표시.
 * API: GET /memory/{userId}/knowledge?category=sourcing
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BookOpenIcon,
  FunnelIcon,
  XMarkIcon,
  LightBulbIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';
import { fetchKnowledge } from '../../api';
import type { DomainKnowledge } from '../../memory';

interface KnowledgeBlockProps {
  userId: string;
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  sourcing: { label: '소싱', color: 'bg-green-50 text-green-700 border-green-100' },
  certification: { label: '인증', color: 'bg-blue-50 text-blue-700 border-blue-100' },
  partnership: { label: '제휴', color: 'bg-purple-50 text-purple-700 border-purple-100' },
  facility: { label: '시설', color: 'bg-amber-50 text-amber-700 border-amber-100' },
  process: { label: '공정', color: 'bg-orange-50 text-orange-700 border-orange-100' },
  policy: { label: '정책', color: 'bg-slate-50 text-slate-700 border-slate-100' },
  event: { label: '이벤트', color: 'bg-pink-50 text-pink-700 border-pink-100' },
  competitive_advantage: { label: '경쟁우위', color: 'bg-indigo-50 text-indigo-700 border-indigo-100' },
  competitor_intel: { label: '경쟁사', color: 'bg-red-50 text-red-700 border-red-100' },
  local_context: { label: '지역', color: 'bg-teal-50 text-teal-700 border-teal-100' },
  customer_insight: { label: '고객', color: 'bg-cyan-50 text-cyan-700 border-cyan-100' },
  sales_channel: { label: '채널', color: 'bg-violet-50 text-violet-700 border-violet-100' },
  regulation: { label: '규제', color: 'bg-gray-50 text-gray-700 border-gray-100' },
  review_highlight: { label: '리뷰', color: 'bg-yellow-50 text-yellow-700 border-yellow-100' },
  seasonal_pattern: { label: '시즌', color: 'bg-lime-50 text-lime-700 border-lime-100' },
  pricing_strategy: { label: '가격', color: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
  community: { label: '커뮤니티', color: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-100' },
  trend: { label: '트렌드', color: 'bg-rose-50 text-rose-700 border-rose-100' },
};

export default function KnowledgeBlock({ userId }: KnowledgeBlockProps) {
  const [items, setItems] = useState<DomainKnowledge[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>('');
  const [selectedItem, setSelectedItem] = useState<DomainKnowledge | null>(null);

  useEffect(() => {
    loadKnowledge();
  }, [userId, activeCategory]);

  const loadKnowledge = async () => {
    setLoading(true);
    const result = await fetchKnowledge(userId, activeCategory || undefined);
    setItems(result.knowledge as DomainKnowledge[]);
    setLoading(false);
  };

  // 카테고리별 카운트
  const categoryCounts: Record<string, number> = {};
  items.forEach((k) => {
    const cat = k.category || k.key || 'other';
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  });

  const categories = Object.keys(categoryCounts).sort();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (items.length === 0 && !activeCategory) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <BookOpenIcon className="w-12 h-12 mb-3 text-gray-300" />
        <p className="text-sm font-medium">도메인 지식이 없습니다</p>
        <p className="text-xs mt-1">대화에서 비즈니스 정보를 알려주시면 자동으로 수집됩니다</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpenIcon className="w-5 h-5 text-amber-500" />
          <h2 className="text-sm font-semibold text-gray-700">도메인 지식</h2>
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{items.length}건</span>
        </div>
      </div>

      {/* 카테고리 필터 */}
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setActiveCategory('')}
            className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${
              !activeCategory ? 'bg-indigo-500 text-white border-indigo-500' : 'bg-white text-gray-500 border-gray-200 hover:border-indigo-200'
            }`}
          >
            <FunnelIcon className="w-3 h-3 inline mr-0.5" />전체
          </button>
          {categories.map((cat) => {
            const info = CATEGORY_LABELS[cat] || { label: cat, color: 'bg-gray-50 text-gray-700 border-gray-100' };
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat === activeCategory ? '' : cat)}
                className={`text-[10px] px-2 py-1 rounded-full border transition-colors ${
                  activeCategory === cat ? 'bg-indigo-500 text-white border-indigo-500' : `${info.color}`
                }`}
              >
                {info.label} ({categoryCounts[cat]})
              </button>
            );
          })}
        </div>
      )}

      {/* Knowledge 목록 */}
      <div className="space-y-2">
        {items.map((item, idx) => {
          const cat = item.category || item.key || 'other';
          const info = CATEGORY_LABELS[cat] || { label: cat, color: 'bg-gray-50 text-gray-700 border-gray-100' };
          return (
            <motion.button
              key={item.knowledge_id || idx}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.3 }}
              whileHover={{ y: -2 }}
              onClick={() => setSelectedItem(item)}
              className="w-full text-left p-3 bg-white rounded-xl border border-gray-100 transition-colors"
            >
              <div className="flex items-start gap-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded border shrink-0 mt-0.5 ${info.color}`}>
                  {info.label}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700 truncate">{item.title || item.value?.slice(0, 60)}</p>
                  {item.marketing_angle && (
                    <p className="text-[10px] text-indigo-500 mt-0.5 truncate">
                      <LightBulbIcon className="w-3 h-3 inline mr-0.5" />{item.marketing_angle}
                    </p>
                  )}
                </div>
                <span className="text-[10px] text-gray-300 shrink-0">{item.knowledge_id}</span>
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* 상세 모달 */}
      {selectedItem && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-2xl max-w-md w-full max-h-[70vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-gray-100">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                    CATEGORY_LABELS[selectedItem.category || selectedItem.key || '']?.color || 'bg-gray-50 text-gray-700 border-gray-100'
                  }`}>
                    {CATEGORY_LABELS[selectedItem.category || selectedItem.key || '']?.label || selectedItem.category || selectedItem.key}
                  </span>
                  <span className="text-xs text-gray-400">{selectedItem.knowledge_id}</span>
                </div>
                <h3 className="text-base font-semibold text-gray-800 mt-1">{selectedItem.title || selectedItem.value?.slice(0, 60)}</h3>
              </div>
              <button onClick={() => setSelectedItem(null)} className="p-1.5 hover:bg-gray-100 rounded-lg">
                <XMarkIcon className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* 상세 내용 */}
              {(selectedItem.detail || selectedItem.value) && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1">상세 내용</p>
                  <p className="text-sm text-gray-700">{selectedItem.detail || selectedItem.value}</p>
                </div>
              )}

              {/* 마케팅 각도 */}
              {selectedItem.marketing_angle && (
                <div className="p-3 bg-indigo-50 rounded-lg border border-indigo-100">
                  <div className="flex items-center gap-1.5 mb-1">
                    <LightBulbIcon className="w-3.5 h-3.5 text-indigo-500" />
                    <p className="text-xs font-medium text-indigo-700">마케팅 활용</p>
                  </div>
                  <p className="text-sm text-indigo-800">{selectedItem.marketing_angle}</p>
                </div>
              )}

              {/* 메타 */}
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-100">
                <div>
                  <p className="text-[10px] text-gray-400">신뢰도</p>
                  <p className="text-xs text-gray-700 mt-0.5">
                    {selectedItem.confidence === 'confirmed' ? '✓ 확인됨' : '? 추론'}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400">유효기간</p>
                  <p className="text-xs text-gray-700 mt-0.5">{selectedItem.expiry_hint || 'permanent'}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400">우선순위</p>
                  <p className="text-xs text-gray-700 mt-0.5">{selectedItem.priority || 'medium'}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400">수집 시점</p>
                  <p className="text-xs text-gray-700 mt-0.5">{selectedItem.source_turn?.slice(0, 10) || '—'}</p>
                </div>
              </div>

              {/* 관련 제품 */}
              {selectedItem.related_products && selectedItem.related_products.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1.5">관련 제품</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedItem.related_products.map((p) => (
                      <span key={p} className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full border border-amber-100">
                        <LinkIcon className="w-3 h-3 inline mr-0.5" />{p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
