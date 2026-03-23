/**
 * CreationsTab — Asset Archive gallery (images & videos)
 * Fetches from GET /memory/{userId}/assets with pagination.
 * Shows image thumbnails and video previews with download buttons.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  PhotoIcon,
  FilmIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  FunnelIcon,
  SparklesIcon,
  ArrowUpTrayIcon,
  CheckCircleIcon,
  PaperAirplaneIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { fetchUserAssets, uploadUserAsset, deleteUserAsset, updateAssetPerformance } from '../api';
import type { GeneratedAsset } from '../memory';

interface CreationsTabProps {
  userId: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  instagram:  'bg-pink-100 text-pink-700',
  youtube:    'bg-red-100 text-red-700',
  tiktok:     'bg-gray-900 text-white',
  twitter:    'bg-sky-100 text-sky-700',
  x:          'bg-sky-100 text-sky-700',
  facebook:   'bg-blue-100 text-blue-700',
  linkedin:   'bg-blue-200 text-blue-800',
  pinterest:  'bg-red-50 text-red-600',
  threads:    'bg-gray-100 text-gray-700',
  kakao:      'bg-yellow-100 text-yellow-700',
};

function AssetCard({
  asset,
  isSelected,
  onSelect,
  onDelete,
}: {
  asset: GeneratedAsset;
  isSelected: boolean;
  onSelect: (asset: GeneratedAsset) => void;
  onDelete: (asset: GeneratedAsset) => void;
}) {
  const [videoError, setVideoError] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const isImage = asset.asset_type === 'image';
  const platformColor = PLATFORM_COLORS[asset.platform] ?? 'bg-gray-100 text-gray-600';
  const date = asset.created_at
    ? new Date(asset.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const a = document.createElement('a');
    a.href = asset.gcs_url;
    a.download = asset.local_filename || (isImage ? 'image.png' : 'video.mp4');
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.click();
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('이 에셋을 삭제하시겠습니까?')) return;
    setIsDeleting(true);
    try {
      await onDelete(asset);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      onClick={() => onSelect(asset)}
      className={`rounded-2xl border bg-white shadow-sm overflow-hidden hover:shadow-md transition-all cursor-pointer ${
        isSelected ? 'border-indigo-500 ring-2 ring-indigo-300' : 'border-gray-100'
      }`}
    >
      {/* Media preview */}
      <div className="relative bg-gray-50 aspect-square overflow-hidden">
        {isImage ? (
          <img
            src={asset.gcs_url}
            alt={asset.prompt_used || 'Generated image'}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : videoError ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-400">
            <FilmIcon className="w-10 h-10" />
            <p className="text-xs">미리보기 불가</p>
          </div>
        ) : (
          <video
            src={asset.gcs_url}
            className="w-full h-full object-cover"
            preload="metadata"
            onError={() => setVideoError(true)}
            muted
            playsInline
            onMouseEnter={e => (e.currentTarget as HTMLVideoElement).play().catch(() => {})}
            onMouseLeave={e => { (e.currentTarget as HTMLVideoElement).pause(); (e.currentTarget as HTMLVideoElement).currentTime = 0; }}
          />
        )}

        {/* Type badge */}
        <div className="absolute top-2 left-2">
          <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${isImage ? 'bg-indigo-100 text-indigo-700' : 'bg-purple-100 text-purple-700'}`}>
            {isImage ? <PhotoIcon className="w-3 h-3" /> : <FilmIcon className="w-3 h-3" />}
            {isImage ? 'IMAGE' : 'VIDEO'}
          </span>
        </div>

        {/* Selected indicator */}
        {isSelected && (
          <div className="absolute top-2 right-8">
            <CheckCircleIcon className="w-5 h-5 text-indigo-600 bg-white rounded-full" />
          </div>
        )}

        {/* Download + Delete button overlay */}
        <div className="absolute top-2 right-2 flex flex-col gap-1">
          <button
            onClick={handleDownload}
            className="w-7 h-7 flex items-center justify-center rounded-full bg-white/80 hover:bg-white text-gray-600 hover:text-indigo-600 shadow transition-all"
            title="다운로드"
          >
            <ArrowDownTrayIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="w-7 h-7 flex items-center justify-center rounded-full bg-white/80 hover:bg-white text-gray-400 hover:text-red-500 shadow transition-all disabled:opacity-40"
            title="삭제"
          >
            <TrashIcon className={`w-3.5 h-3.5 ${isDeleting ? 'animate-pulse' : ''}`} />
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="px-3 py-2.5 space-y-1.5">
        {asset.platform && (
          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${platformColor}`}>
            {asset.platform}
          </span>
        )}
        {(asset as any).caption && (
          <p className="text-[11px] text-gray-700 line-clamp-3 leading-relaxed font-medium">{(asset as any).caption}</p>
        )}
        {(asset as any).hashtags && (asset as any).hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {(asset as any).hashtags.slice(0, 6).map((tag: string, i: number) => (
              <span key={i} className="text-[10px] text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded-full">
                {tag.startsWith('#') ? tag : `#${tag}`}
              </span>
            ))}
            {(asset as any).hashtags.length > 6 && (
              <span className="text-[10px] text-gray-400">+{(asset as any).hashtags.length - 6}</span>
            )}
          </div>
        )}
        {!((asset as any).caption) && asset.prompt_used && (
          <p className="text-[11px] text-gray-500 line-clamp-2 leading-relaxed">{asset.prompt_used}</p>
        )}
        {date && <p className="text-[10px] text-gray-400">{date}</p>}
      </div>
    </div>
  );
}

type PerfDraft = Partial<{ views: number; clicks: number; impressions: number; likes: number; shares: number; comments: number }>;

export default function CreationsTab({ userId }: CreationsTabProps) {
  const [assets, setAssets] = useState<GeneratedAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<'all' | 'image' | 'video'>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<GeneratedAsset | null>(null);
  const [showPerfForm, setShowPerfForm] = useState(false);
  const [perfDraft, setPerfDraft] = useState<PerfDraft>({});
  const [isSavingPerf, setIsSavingPerf] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const LIMIT = 12;

  const load = useCallback(async (p: number, f: 'all' | 'image' | 'video') => {
    setIsLoading(true);
    const result = await fetchUserAssets(userId, {
      limit: LIMIT,
      page: p,
      asset_type: f === 'all' ? undefined : f,
    });
    setAssets(result.assets as GeneratedAsset[]);
    setTotal(result.total);
    setIsLoading(false);
  }, [userId]);

  useEffect(() => {
    load(page, filter);
  }, [load, page, filter]);

  const handleFilterChange = (f: 'all' | 'image' | 'video') => {
    setFilter(f);
    setPage(0);
  };

  const handleSelectAsset = (asset: GeneratedAsset) => {
    setSelectedAsset(prev => {
      if (prev?.asset_id === asset.asset_id) return null;
      setShowPerfForm(false);
      setPerfDraft({});
      return asset;
    });
  };

  const handleDeleteAsset = async (asset: GeneratedAsset) => {
    await deleteUserAsset(userId, asset.asset_id);
    if (selectedAsset?.asset_id === asset.asset_id) setSelectedAsset(null);
    await load(page, filter);
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      await uploadUserAsset(userId, file);
      await load(0, filter);
      setPage(0);
    } catch (err) {
      console.error('[Upload error]', err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const totalPages = Math.ceil(total / LIMIT);

  if (!isLoading && assets.length === 0 && page === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-24 text-center px-6">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-4">
          <SparklesIcon className="w-7 h-7 text-indigo-500" />
        </div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">생성된 에셋이 없습니다</h3>
        <p className="text-sm text-gray-400 max-w-xs leading-relaxed mb-5">
          콘텐츠 생성 파이프라인을 실행하면 이미지와 영상이 여기에 저장됩니다.
        </p>
        <button
          onClick={handleUploadClick}
          disabled={isUploading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          <ArrowUpTrayIcon className="w-4 h-4" />
          {isUploading ? '업로드 중...' : '이미지 업로드'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-gray-900">Assets</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">총 {total}개의 에셋</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleUploadClick}
            disabled={isUploading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            title="이미지 업로드"
          >
            <ArrowUpTrayIcon className="w-3.5 h-3.5" />
            {isUploading ? '업로드 중...' : '업로드'}
          </button>
          <button
            onClick={() => load(page, filter)}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        </div>
      </div>

      {/* Publish bar — shown when an asset is selected */}
      {selectedAsset && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5">
            <p className="text-xs font-medium text-indigo-700 truncate max-w-[50%]">
              선택됨: {selectedAsset.local_filename || selectedAsset.asset_id.slice(0, 8)}
            </p>
            <div className="flex items-center gap-2">
              <button
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  showPerfForm
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-white text-green-700 border border-green-300 hover:bg-green-50'
                }`}
                onClick={() => {
                  if (!showPerfForm && selectedAsset?.performance) {
                    const p = selectedAsset.performance;
                    setPerfDraft({
                      views: p.views ?? undefined,
                      clicks: p.clicks ?? undefined,
                      likes: p.likes ?? undefined,
                      impressions: p.impressions ?? undefined,
                      shares: p.shares ?? undefined,
                      comments: p.comments ?? undefined,
                    });
                  }
                  setShowPerfForm(v => !v);
                }}
              >
                <span>{showPerfForm ? '닫기' : '성과 업데이트'}</span>
              </button>
              <button
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                onClick={() => {/* UI only — no backend */}}
              >
                <PaperAirplaneIcon className="w-3.5 h-3.5" />
                게시하기
              </button>
            </div>
          </div>

          {/* Performance input form */}
          {showPerfForm && (
            <div className="border-t border-indigo-200 bg-white px-4 py-3 space-y-3">
              <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">성과 지표 입력</p>
              <div className="grid grid-cols-3 gap-2">
                {(['views', 'clicks', 'likes', 'impressions', 'shares', 'comments'] as const).map(field => (
                  <div key={field} className="flex flex-col gap-1">
                    <label className="text-[10px] text-gray-400 capitalize">{field}</label>
                    <input
                      type="number"
                      min={0}
                      placeholder="0"
                      value={perfDraft[field] ?? ''}
                      onChange={e => {
                        const val = e.target.value === '' ? undefined : Number(e.target.value);
                        setPerfDraft(prev => ({ ...prev, [field]: val }));
                      }}
                      className="w-full rounded-lg border border-gray-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </div>
                ))}
              </div>
              <button
                disabled={isSavingPerf || Object.keys(perfDraft).length === 0}
                onClick={async () => {
                  if (!selectedAsset) return;
                  setIsSavingPerf(true);
                  try {
                    await updateAssetPerformance(userId, selectedAsset.asset_id, perfDraft);
                    setShowPerfForm(false);
                    setPerfDraft({});
                  } catch (err) {
                    console.error('[Performance update error]', err);
                  } finally {
                    setIsSavingPerf(false);
                  }
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isSavingPerf ? '저장 중...' : '저장'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex items-center gap-2">
        <FunnelIcon className="w-4 h-4 text-gray-400 shrink-0" />
        {(['all', 'image', 'video'] as const).map(f => (
          <button
            key={f}
            onClick={() => handleFilterChange(f)}
            className={`flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full transition-all ${
              filter === f ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {f === 'image' && <PhotoIcon className="w-3 h-3" />}
            {f === 'video' && <FilmIcon className="w-3 h-3" />}
            {f === 'all' ? '전체' : f === 'image' ? '이미지' : '영상'}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl bg-gray-100 aspect-square animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {assets.map(asset => (
            <AssetCard
              key={asset.asset_id}
              asset={asset}
              isSelected={selectedAsset?.asset_id === asset.asset_id}
              onSelect={handleSelectAsset}
              onDelete={handleDeleteAsset}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0 || isLoading}
            className="px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            이전
          </button>
          <span className="text-xs text-gray-400">{page + 1} / {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1 || isLoading}
            className="px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
