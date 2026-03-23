/**
 * ProfileBlock — MemGPT Core Memory UI (4-Block Architecture)
 *
 * Displays and edits the user's persistent profile across 4 blocks:
 *   Human Block    → display_name, handles, extra_fields
 *   Persona Block  → tone, preferred_styles, avoid_topics, signature_hashtags, content_pillars
 *   Domain Block   → industry, domain_type, usp, competitors, knowledge, etc.
 *   Audience Block → target_platforms, default_age_range, segments (AudienceSegment[]), seasonal_peaks, offline_channels
 *
 * Changes are saved via the /memory API and persist across sessions.
 */

import { useState } from 'react';
import type {
  MemoryState,
  HumanBlock,
  PersonaBlock,
  DomainBlock,
  AudienceBlock,
  AudienceSegment,
  AudienceTrait,
} from '../../memory';
import { useToast } from '../../contexts/ToastContext';
import {
  UserCircleIcon,
  SparklesIcon,
  CheckIcon,
  PencilIcon,
  PlusIcon,
  XMarkIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';

interface ProfileBlockProps {
  memory: MemoryState;
  onSave: (updated: MemoryState) => Promise<void>;
  userId: string;
  initialTab?: 'identity' | 'voice' | 'domain' | 'audience';
}

// ─── Tag list editor ─────────────────────────────────────────────────
function TagListEditor({
  label,
  tags,
  onChange,
  placeholder,
  color = 'indigo',
}: {
  label: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder: string;
  color?: 'indigo' | 'pink' | 'red' | 'green' | 'yellow' | 'amber' | 'teal';
}) {
  const [input, setInput] = useState('');

  const colorMap = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    pink: 'bg-pink-50 text-pink-700 border-pink-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
  };

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput('');
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</label>
      <div className="flex flex-wrap gap-1.5 min-h-[28px]">
        {tags.map((tag) => (
          <span
            key={tag}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colorMap[color]}`}
          >
            {tag}
            <button
              onClick={() => onChange(tags.filter((t) => t !== tag))}
              className="hover:opacity-70 transition-opacity"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
          placeholder={placeholder}
          className="flex-1 text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-gray-50"
        />
        <button
          onClick={addTag}
          className="px-2.5 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  );
}

// ─── Extra fields editor (dynamic key-value pairs) ───────────────────
function ExtraFieldsEditor({
  fields,
  onChange,
}: {
  fields: Record<string, string>;
  onChange: (f: Record<string, string>) => void;
}) {
  const [keyInput, setKeyInput] = useState('');
  const [valInput, setValInput] = useState('');

  const add = () => {
    const k = keyInput.trim().replace(/\s+/g, '_').toLowerCase();
    const v = valInput.trim();
    if (!k || !v) return;
    onChange({ ...fields, [k]: v });
    setKeyInput('');
    setValInput('');
  };

  const remove = (k: string) => {
    const next = { ...fields };
    delete next[k];
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider">추가 정보 (동적 필드)</label>
      {Object.entries(fields).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-[11px] bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded-lg font-medium">{k.replace(/_/g, ' ')}</span>
          <span className="text-xs text-gray-600 flex-1 truncate">{v}</span>
          <button onClick={() => remove(k)} className="text-gray-300 hover:text-red-400 transition-colors text-sm">×</button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          type="text"
          value={keyInput}
          onChange={(e) => setKeyInput(e.target.value)}
          placeholder="키 (예: location)"
          className="w-28 text-xs px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-400 bg-gray-50"
        />
        <input
          type="text"
          value={valInput}
          onChange={(e) => setValInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="값 (예: Seoul)"
          className="flex-1 text-xs px-2 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-400 bg-gray-50"
        />
        <button
          onClick={add}
          className="px-2.5 py-1.5 text-xs bg-sky-100 hover:bg-sky-200 text-sky-700 rounded-lg transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  );
}

// ─── Source badge colors ──────────────────────────────────────────────
const SOURCE_STYLE: Record<string, string> = {
  confirmed: 'bg-green-50 text-green-700 border-green-200',
  inferred: 'bg-amber-50 text-amber-700 border-amber-200',
  discovered: 'bg-purple-50 text-purple-700 border-purple-200',
};

// ─── Audience Segment Manager ────────────────────────────────────────
function AudienceTabContent({
  audience,
  isEditing,
  updateAudience,
}: {
  audience: AudienceBlock;
  isEditing: boolean;
  updateAudience: (patch: Partial<AudienceBlock>) => void;
}) {
  const [showNewSegment, setShowNewSegment] = useState(false);
  const [newSeg, setNewSeg] = useState({ name: '', age_range: '', gender: '', location: '', products: '' });
  const [addingTraitFor, setAddingTraitFor] = useState<string | null>(null);
  const [traitKey, setTraitKey] = useState('');
  const [traitVal, setTraitVal] = useState('');

  const segments = audience.segments ?? [];

  const addSegment = () => {
    if (!newSeg.name.trim()) return;
    const seg: AudienceSegment = {
      segment_id: `seg_${Date.now()}`,
      name: newSeg.name.trim(),
      source: 'confirmed',
      age_range: newSeg.age_range,
      gender: newSeg.gender,
      location: newSeg.location,
      products: newSeg.products ? newSeg.products.split(',').map(s => s.trim()).filter(Boolean) : [],
      platforms: [],
      traits: [],
      notes: '',
    };
    updateAudience({ segments: [...segments, seg] });
    setNewSeg({ name: '', age_range: '', gender: '', location: '', products: '' });
    setShowNewSegment(false);
  };

  const removeSegment = (segId: string) => {
    updateAudience({ segments: segments.filter(s => s.segment_id !== segId) });
  };

  const addTrait = (segId: string) => {
    if (!traitKey.trim() || !traitVal.trim()) return;
    const newTrait: AudienceTrait = { key: traitKey.trim(), value: traitVal.trim(), confidence: 'confirmed' };
    updateAudience({
      segments: segments.map(s =>
        s.segment_id === segId ? { ...s, traits: [...s.traits, newTrait] } : s
      ),
    });
    setTraitKey('');
    setTraitVal('');
    setAddingTraitFor(null);
  };

  const removeTrait = (segId: string, traitIdx: number) => {
    updateAudience({
      segments: segments.map(s =>
        s.segment_id === segId ? { ...s, traits: s.traits.filter((_, i) => i !== traitIdx) } : s
      ),
    });
  };

  return (
    <div className="space-y-4">
      {/* Default Age Range */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Default Age Range</label>
        {isEditing ? (
          <input
            type="text"
            value={audience.default_age_range || (audience as any).target_age_range || ""}
            onChange={(e) => updateAudience({ default_age_range: e.target.value })}
            placeholder="20-35, 18-45..."
            className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        ) : (
          <p className="text-sm text-gray-800">{audience.default_age_range || (audience as any).target_age_range || <span className="text-gray-400 italic">Not set</span>}</p>
        )}
      </div>

      <TagListEditor
        label="Target Platforms"
        tags={audience.target_platforms}
        onChange={(t) => updateAudience({ target_platforms: t })}
        placeholder="twitter, instagram, tiktok..."
        color="indigo"
      />

      {/* ── Segment Cards ── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider">Audience Segments</label>
          {isEditing && (
            <button
              onClick={() => setShowNewSegment(!showNewSegment)}
              className="flex items-center gap-1 px-2 py-1 text-xs text-teal-600 bg-teal-50 border border-teal-200 rounded-lg hover:bg-teal-100 transition-colors"
            >
              <PlusIcon className="w-3.5 h-3.5" />
              세그먼트 추가
            </button>
          )}
        </div>

        {/* New Segment Form */}
        {isEditing && showNewSegment && (
          <div className="mb-3 p-3 bg-teal-50/50 border border-teal-200 rounded-xl space-y-2">
            <input
              type="text"
              value={newSeg.name}
              onChange={(e) => setNewSeg(p => ({ ...p, name: e.target.value }))}
              placeholder="세그먼트 이름 (예: 20대 직장인)"
              className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
            />
            <div className="grid grid-cols-3 gap-2">
              <input
                type="text"
                value={newSeg.age_range}
                onChange={(e) => setNewSeg(p => ({ ...p, age_range: e.target.value }))}
                placeholder="연령대 (20-30)"
                className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
              />
              <input
                type="text"
                value={newSeg.gender}
                onChange={(e) => setNewSeg(p => ({ ...p, gender: e.target.value }))}
                placeholder="성별"
                className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
              />
              <input
                type="text"
                value={newSeg.location}
                onChange={(e) => setNewSeg(p => ({ ...p, location: e.target.value }))}
                placeholder="지역"
                className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
              />
            </div>
            <input
              type="text"
              value={newSeg.products}
              onChange={(e) => setNewSeg(p => ({ ...p, products: e.target.value }))}
              placeholder="연관 제품 (쉼표 구분)"
              className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
            />
            <div className="flex gap-2">
              <button onClick={addSegment} className="px-3 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors">추가</button>
              <button onClick={() => setShowNewSegment(false)} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors">취소</button>
            </div>
          </div>
        )}

        {/* Segment Card List */}
        {segments.length === 0 ? (
          <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100">
            <UserGroupIcon className="w-5 h-5 text-gray-300" />
            <p className="text-xs text-gray-400 italic">아직 세그먼트가 없습니다. {isEditing ? '위에서 추가하세요.' : '편집 모드에서 추가할 수 있습니다.'}</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {segments.map((seg) => (
              <div key={seg.segment_id || seg.name} className="relative p-3 bg-white border border-gray-200 rounded-xl">
                {/* Delete button */}
                {isEditing && (
                  <button
                    onClick={() => removeSegment(seg.segment_id)}
                    className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center text-gray-300 hover:text-red-500 transition-colors"
                    title="세그먼트 삭제"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                )}

                {/* Name + Source badge */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-gray-800">{seg.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${SOURCE_STYLE[seg.source] || SOURCE_STYLE.confirmed}`}>
                    {seg.source}
                  </span>
                </div>

                {/* Demographics row */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2">
                  {seg.age_range && (
                    <span className="text-xs text-gray-500"><span className="text-gray-400">Age:</span> {seg.age_range}</span>
                  )}
                  {seg.gender && (
                    <span className="text-xs text-gray-500"><span className="text-gray-400">Gender:</span> {seg.gender}</span>
                  )}
                  {seg.location && (
                    <span className="text-xs text-gray-500"><span className="text-gray-400">Location:</span> {seg.location}</span>
                  )}
                </div>

                {/* Products chips */}
                {seg.products.length > 0 && (
                  <div className="mb-2">
                    <span className="text-[10px] text-gray-400 uppercase tracking-wider mr-1.5">Products</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {seg.products.map(p => (
                        <span key={p} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 border border-indigo-200 rounded text-[10px]">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Platforms chips */}
                {seg.platforms.length > 0 && (
                  <div className="mb-2">
                    <span className="text-[10px] text-gray-400 uppercase tracking-wider mr-1.5">Platforms</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {seg.platforms.map(p => (
                        <span key={p} className="px-1.5 py-0.5 bg-sky-50 text-sky-600 border border-sky-200 rounded text-[10px]">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Traits list */}
                {seg.traits.length > 0 && (
                  <div className="mb-2">
                    <span className="text-[10px] text-gray-400 uppercase tracking-wider">Traits</span>
                    <div className="mt-1 space-y-0.5">
                      {seg.traits.map((t, ti) => (
                        <div key={ti} className="flex items-center gap-1.5">
                          <span className="text-[11px] text-gray-500">{t.key}:</span>
                          <span className="text-[11px] text-gray-700 font-medium">{t.value}</span>
                          <span className={`text-[9px] px-1 py-0.5 rounded border ${SOURCE_STYLE[t.confidence] || SOURCE_STYLE.confirmed}`}>
                            {t.confidence}
                          </span>
                          {isEditing && (
                            <button onClick={() => removeTrait(seg.segment_id, ti)} className="text-gray-300 hover:text-red-400 text-[10px] transition-colors ml-auto">x</button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Add trait inline */}
                {isEditing && (
                  <>
                    {addingTraitFor === seg.segment_id ? (
                      <div className="flex gap-1.5 mt-1">
                        <input
                          type="text"
                          value={traitKey}
                          onChange={(e) => setTraitKey(e.target.value)}
                          placeholder="Key"
                          className="w-20 text-[11px] px-2 py-1 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-gray-50"
                        />
                        <input
                          type="text"
                          value={traitVal}
                          onChange={(e) => setTraitVal(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTrait(seg.segment_id))}
                          placeholder="Value"
                          className="flex-1 text-[11px] px-2 py-1 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-400 bg-gray-50"
                        />
                        <button onClick={() => addTrait(seg.segment_id)} className="px-2 py-1 text-[11px] bg-teal-100 text-teal-700 rounded-lg hover:bg-teal-200 transition-colors">OK</button>
                        <button onClick={() => { setAddingTraitFor(null); setTraitKey(''); setTraitVal(''); }} className="px-2 py-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors">x</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setAddingTraitFor(seg.segment_id)}
                        className="flex items-center gap-1 mt-1 text-[10px] text-teal-600 hover:text-teal-700 transition-colors"
                      >
                        <PlusIcon className="w-3 h-3" />
                        Trait 추가
                      </button>
                    )}
                  </>
                )}

                {/* Notes */}
                {seg.notes && (
                  <p className="mt-1.5 text-[11px] text-gray-400 italic">{seg.notes}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <TagListEditor
        label="Seasonal Peaks"
        tags={audience.seasonal_peaks}
        onChange={(t) => updateAudience({ seasonal_peaks: t })}
        placeholder="Christmas, Summer, Black Friday..."
        color="amber"
      />

      <TagListEditor
        label="Offline Channels"
        tags={audience.offline_channels}
        onChange={(t) => updateAudience({ offline_channels: t })}
        placeholder="Pop-up store, Trade shows..."
        color="green"
      />
    </div>
  );
}

// ─── Main ProfileBlock ────────────────────────────────────────────────
export default function ProfileBlock({ memory, onSave, userId, initialTab = 'identity' }: ProfileBlockProps) {
  const { showToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draft, setDraft] = useState<MemoryState>(memory);
  const [activeTab, setActiveTab] = useState<'identity' | 'voice' | 'domain' | 'audience'>(initialTab);

  const human = draft.human_block;
  const persona = draft.persona_block;
  const domain = draft.domain_block;
  const audience = draft.audience_block;

  const updateHuman = (patch: Partial<HumanBlock>) => {
    setDraft((prev) => ({
      ...prev,
      human_block: { ...prev.human_block, ...patch },
    }));
  };

  const updatePersona = (patch: Partial<PersonaBlock>) => {
    setDraft((prev) => ({
      ...prev,
      persona_block: { ...prev.persona_block, ...patch },
    }));
  };

  const updateDomain = (patch: Partial<DomainBlock>) => {
    setDraft((prev) => ({
      ...prev,
      domain_block: { ...prev.domain_block, ...patch },
    }));
  };

  const updateAudience = (patch: Partial<AudienceBlock>) => {
    setDraft((prev) => ({
      ...prev,
      audience_block: { ...prev.audience_block, ...patch },
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(draft);
      setIsEditing(false);
      showToast('프로필 저장 완료', 'success');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(memory);
    setIsEditing(false);
  };

  const isProfileEmpty =
    !human.display_name && !domain.industry && !human.twitter_handle;

  return (
    <li className="col-span-2 overflow-hidden rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/40 to-purple-50/20 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-indigo-100/70">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <SparklesIcon className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">
              {human.display_name || 'Your Brand Profile'}
            </h3>
            <p className="text-xs text-indigo-500 font-medium">MemGPT · Persistent Memory</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {memory.total_campaigns > 0 && (
            <span className="text-xs text-gray-400">
              {memory.total_campaigns} campaign{memory.total_campaigns !== 1 ? 's' : ''}
            </span>
          )}
          {isEditing ? (
            <div className="flex gap-2">
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >
                <CheckIcon className="w-3.5 h-3.5" />
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 rounded-lg hover:bg-white/60 border border-gray-200/50 transition-colors"
            >
              <PencilIcon className="w-3.5 h-3.5" />
              Edit Profile
            </button>
          )}
        </div>
      </div>

      {/* Empty state prompt */}
      {isProfileEmpty && !isEditing && (
        <div className="px-5 py-3 bg-indigo-50/60 border-b border-indigo-100/50">
          <p className="text-xs text-indigo-600">
            💡 Tell the agent your brand name, industry, and preferred tone — it will remember them across sessions.
          </p>
        </div>
      )}

      {/* Tabs — 4 sections */}
      <div className="flex border-b border-gray-100 px-5 pt-3">
        {([
          { key: 'identity' as const, label: '👤 사용자 정보' },
          { key: 'voice' as const, label: '🎨 브랜드 보이스' },
          { key: 'domain' as const, label: '🏪 도메인 프로필' },
          { key: 'audience' as const, label: '🎯 타겟 오디언스' },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`mr-5 pb-2.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="px-5 py-4">
        {/* ── 사용자 정보 Tab (Human Block) ── */}
        {activeTab === 'identity' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Brand / Display Name</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={human.display_name}
                    onChange={(e) => updateHuman({ display_name: e.target.value })}
                    placeholder="Acme Co."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800 font-medium">{human.display_name || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Twitter / X Handle</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={human.twitter_handle || ''}
                    onChange={(e) => updateHuman({ twitter_handle: e.target.value || null })}
                    placeholder="@mybrand"
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{human.twitter_handle || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Instagram Handle</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={human.instagram_handle || ''}
                    onChange={(e) => updateHuman({ instagram_handle: e.target.value || null })}
                    placeholder="@mybrand_official"
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{human.instagram_handle || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>
            </div>

            {/* Extra fields */}
            {isEditing ? (
              <ExtraFieldsEditor
                fields={human.extra_fields ?? {}}
                onChange={(f) => updateHuman({ extra_fields: f })}
              />
            ) : Object.keys(human.extra_fields ?? {}).length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">추가 정보</label>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {Object.entries(human.extra_fields ?? {}).map(([k, v]) => (
                    <div key={k} className="flex items-baseline gap-1.5">
                      <span className="text-[10px] text-gray-400 capitalize shrink-0">{k.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-gray-700 font-medium truncate">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {memory.working_summary && (
              <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-100">
                <p className="text-xs font-medium text-gray-400 mb-1">Last Session Summary</p>
                <p className="text-xs text-gray-600">{memory.working_summary}</p>
              </div>
            )}
          </div>
        )}

        {/* ── 브랜드 보이스 Tab (Persona Block) ── */}
        {activeTab === 'voice' && (
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Brand Tone</label>
              {isEditing ? (
                <input
                  type="text"
                  value={persona.tone}
                  onChange={(e) => updatePersona({ tone: e.target.value })}
                  placeholder="casual and witty, professional, bold..."
                  className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              ) : (
                <p className="text-sm text-gray-800">
                  {persona.tone ? (
                    <span className="italic">"{persona.tone}"</span>
                  ) : (
                    <span className="text-gray-400 italic">Not defined</span>
                  )}
                </p>
              )}
            </div>

            <TagListEditor
              label="Preferred Styles"
              tags={persona.preferred_styles}
              onChange={(t) => updatePersona({ preferred_styles: t })}
              placeholder="Minimalist, Vibrant, Dark..."
              color="indigo"
            />

            <TagListEditor
              label="Content Pillars"
              tags={persona.content_pillars}
              onChange={(t) => updatePersona({ content_pillars: t })}
              placeholder="Education, Behind-the-scenes..."
              color="green"
            />

            <TagListEditor
              label="Signature Hashtags"
              tags={persona.signature_hashtags}
              onChange={(t) => updatePersona({ signature_hashtags: t })}
              placeholder="#BuildInPublic, #YourBrand..."
              color="yellow"
            />

            <TagListEditor
              label="Topics to Avoid"
              tags={persona.avoid_topics}
              onChange={(t) => updatePersona({ avoid_topics: t })}
              placeholder="politics, competitors..."
              color="red"
            />
          </div>
        )}

        {/* ── 도메인 프로필 Tab (Domain Block) ── */}
        {activeTab === 'domain' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Industry</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.industry}
                    onChange={(e) => updateDomain({ industry: e.target.value })}
                    placeholder="SaaS, Fashion, Fitness..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.industry || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Domain Type</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.domain_type}
                    onChange={(e) => updateDomain({ domain_type: e.target.value })}
                    placeholder="B2B, B2C, D2C..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.domain_type || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Business Location</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.business_location}
                    onChange={(e) => updateDomain({ business_location: e.target.value })}
                    placeholder="Seoul, New York..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.business_location || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Price Range</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.price_range}
                    onChange={(e) => updateDomain({ price_range: e.target.value })}
                    placeholder="$$, Premium, Budget..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.price_range || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Operating Hours</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.operating_hours}
                    onChange={(e) => updateDomain({ operating_hours: e.target.value })}
                    placeholder="9AM-6PM, 24/7..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.operating_hours || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">USP (Unique Selling Proposition)</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={domain.usp}
                    onChange={(e) => updateDomain({ usp: e.target.value })}
                    placeholder="What makes your brand unique..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{domain.usp || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>
            </div>

            <TagListEditor
              label="Competitors"
              tags={domain.competitors}
              onChange={(t) => updateDomain({ competitors: t })}
              placeholder="Competitor A, Competitor B..."
              color="amber"
            />

            {/* Domain extra fields */}
            {isEditing ? (
              <ExtraFieldsEditor
                fields={domain.domain_extra ?? {}}
                onChange={(f) => updateDomain({ domain_extra: f })}
              />
            ) : Object.keys(domain.domain_extra ?? {}).length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">도메인 추가 정보</label>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {Object.entries(domain.domain_extra ?? {}).map(([k, v]) => (
                    <div key={k} className="flex items-baseline gap-1.5">
                      <span className="text-[10px] text-gray-400 capitalize shrink-0">{k.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-gray-700 font-medium truncate">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 타겟 오디언스 Tab (Audience Block) ── */}
        {activeTab === 'audience' && (
          <AudienceTabContent
            audience={audience}
            isEditing={isEditing}
            updateAudience={updateAudience}
          />
        )}

      </div>
    </li>
  );
}
