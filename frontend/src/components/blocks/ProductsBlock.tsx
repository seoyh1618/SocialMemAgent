/**
 * ProductsBlock — 제품 카탈로그 뷰
 * Core에는 ID+이름만 주입, 이 컴포넌트에서 상세 표시.
 * API: GET /memory/{userId}/products
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  CubeIcon,
  ChevronRightIcon,
  XMarkIcon,
  TagIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { fetchProducts } from '../../api';
import type { ProductRecord } from '../../memory';

interface ProductsBlockProps {
  userId: string;
}

export default function ProductsBlock({ userId }: ProductsBlockProps) {
  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProduct, setSelectedProduct] = useState<ProductRecord | null>(null);

  useEffect(() => {
    loadProducts();
  }, [userId]);

  const loadProducts = async () => {
    setLoading(true);
    const result = await fetchProducts(userId);
    setProducts(result.products as ProductRecord[]);
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <CubeIcon className="w-12 h-12 mb-3 text-gray-300" />
        <p className="text-sm font-medium">등록된 제품이 없습니다</p>
        <p className="text-xs mt-1">대화에서 제품 정보를 알려주시면 자동으로 등록됩니다</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CubeIcon className="w-5 h-5 text-amber-500" />
          <h2 className="text-sm font-semibold text-gray-700">제품 카탈로그</h2>
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{products.length}개</span>
        </div>
      </div>

      {/* 제품 그리드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {products.map((product, idx) => (
          <motion.button
            key={product.product_id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.06, duration: 0.35, ease: [0.25, 0.1, 0.25, 1] }}
            whileHover={{ y: -3, boxShadow: '0 8px 24px rgba(0,0,0,0.06)' }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setSelectedProduct(product)}
            className="text-left p-4 bg-white rounded-xl border border-gray-100 transition-colors group"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{product.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{product.product_id}</p>
              </div>
              <ChevronRightIcon className="w-4 h-4 text-gray-300 group-hover:text-indigo-400 transition-colors mt-0.5" />
            </div>

            {/* 메타 정보 */}
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {product.price && (
                <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded border border-amber-100">
                  {product.price}
                </span>
              )}
              {product.category && (
                <span className="text-[10px] px-1.5 py-0.5 bg-gray-50 text-gray-500 rounded border border-gray-100">
                  {product.category}
                </span>
              )}
              {product.best_platform && (
                <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded border border-indigo-100">
                  {product.best_platform}
                </span>
              )}
              {product.avg_engagement && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                  product.avg_engagement === 'high' ? 'bg-green-50 text-green-700 border-green-100' :
                  product.avg_engagement === 'medium' ? 'bg-yellow-50 text-yellow-700 border-yellow-100' :
                  'bg-gray-50 text-gray-500 border-gray-100'
                }`}>
                  {product.avg_engagement}
                </span>
              )}
            </div>
          </motion.button>
        ))}
      </div>

      {/* 상세 모달 */}
      {selectedProduct && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setSelectedProduct(null)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            className="bg-white rounded-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between p-5 border-b border-gray-100">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">{selectedProduct.name}</h3>
                <p className="text-xs text-gray-400 mt-0.5">{selectedProduct.product_id}</p>
              </div>
              <button onClick={() => setSelectedProduct(null)} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
                <XMarkIcon className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* 모달 본문 */}
            <div className="p-5 space-y-4">
              {/* 기본 정보 */}
              <div className="grid grid-cols-2 gap-3">
                <DetailField label="가격" value={selectedProduct.price} />
                <DetailField label="카테고리" value={selectedProduct.category} />
                <DetailField label="유형" value={selectedProduct.product_type} />
                <DetailField label="가용성" value={selectedProduct.availability} />
              </div>

              {/* 설명 */}
              {selectedProduct.description && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1">설명</p>
                  <p className="text-sm text-gray-700">{selectedProduct.description}</p>
                </div>
              )}

              {/* USP */}
              {selectedProduct.unique_selling_point && (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                  <div className="flex items-center gap-1.5 mb-1">
                    <StarIcon className="w-3.5 h-3.5 text-amber-500" />
                    <p className="text-xs font-medium text-amber-700">차별점</p>
                  </div>
                  <p className="text-sm text-amber-800">{selectedProduct.unique_selling_point}</p>
                </div>
              )}

              {/* 핵심 특성 */}
              {selectedProduct.key_features && selectedProduct.key_features.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1.5">핵심 특성</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedProduct.key_features.map((f, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded-full border border-indigo-100">{f}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 마케팅 문구 */}
              {selectedProduct.messaging_hooks && selectedProduct.messaging_hooks.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1.5">마케팅 문구</p>
                  <div className="space-y-1">
                    {selectedProduct.messaging_hooks.map((h, i) => (
                      <p key={i} className="text-xs text-gray-600 pl-2 border-l-2 border-indigo-200">"{h}"</p>
                    ))}
                  </div>
                </div>
              )}

              {/* 성과 */}
              <div className="grid grid-cols-3 gap-2 pt-3 border-t border-gray-100">
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <p className="text-[10px] text-gray-400">최적 채널</p>
                  <p className="text-xs font-medium text-gray-700 mt-0.5">{selectedProduct.best_platform || '—'}</p>
                </div>
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <p className="text-[10px] text-gray-400">참여도</p>
                  <p className="text-xs font-medium text-gray-700 mt-0.5">{selectedProduct.avg_engagement || '—'}</p>
                </div>
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <p className="text-[10px] text-gray-400">캠페인</p>
                  <p className="text-xs font-medium text-gray-700 mt-0.5">{selectedProduct.total_campaigns || 0}건</p>
                </div>
              </div>

              {/* 타겟 세그먼트 */}
              {selectedProduct.target_segments && selectedProduct.target_segments.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-1.5">타겟 세그먼트</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedProduct.target_segments.map((s) => (
                      <span key={s} className="text-xs px-2 py-0.5 bg-teal-50 text-teal-700 rounded-full border border-teal-100">
                        <TagIcon className="w-3 h-3 inline mr-0.5" />{s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

function DetailField({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <p className="text-[10px] text-gray-400 uppercase tracking-wider">{label}</p>
      <p className="text-sm text-gray-700 mt-0.5">{value || '—'}</p>
    </div>
  );
}
