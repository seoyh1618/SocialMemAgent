/**
 * ProfileBlock — MemGPT Core Memory UI
 *
 * Displays and edits the user's persistent profile (Human Block) and
 * brand voice (Persona Block). Changes are saved via the /memory API
 * and persist across sessions.
 *
 * Architecture:
 *   Human Block   → display_name, handles, industry, target_platforms
 *   Persona Block → tone, preferred_styles, avoid_topics, signature_hashtags, content_pillars
 */

import { useState } from 'react';
import type { MemoryState, BrandVoice, UserProfile, CampaignRecord, PerformanceData } from '../../memory';
import { updateCampaignPerformance } from '../../api';
import {
  UserCircleIcon,
  SparklesIcon,
  CheckIcon,
  PencilIcon,
  ClockIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import PerformanceChart from './performance_chart';

interface ProfileBlockProps {
  memory: MemoryState;
  onSave: (updated: MemoryState) => Promise<void>;
  userId: string;
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
  color?: 'indigo' | 'pink' | 'red' | 'green' | 'yellow';
}) {
  const [input, setInput] = useState('');

  const colorMap = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    pink: 'bg-pink-50 text-pink-700 border-pink-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
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

// ─── Main ProfileBlock ────────────────────────────────────────────────
export default function ProfileBlock({ memory, onSave, userId }: ProfileBlockProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draft, setDraft] = useState<MemoryState>(memory);
  const [activeTab, setActiveTab] = useState<'identity' | 'voice' | 'history'>('identity');
  const [editingCampaignId, setEditingCampaignId] = useState<string | null>(null);
  const [perfDraft, setPerfDraft] = useState<Record<string, number>>({});

  const profile = draft.core_profile;
  const voice = profile.brand_voice;

  const updateProfile = (patch: Partial<UserProfile>) => {
    setDraft((prev) => ({
      ...prev,
      core_profile: { ...prev.core_profile, ...patch },
    }));
  };

  const updateVoice = (patch: Partial<BrandVoice>) => {
    setDraft((prev) => ({
      ...prev,
      core_profile: {
        ...prev.core_profile,
        brand_voice: { ...prev.core_profile.brand_voice, ...patch },
      },
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(draft);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(memory);
    setIsEditing(false);
  };

  const isProfileEmpty =
    !profile.display_name && !profile.industry && !profile.twitter_handle;

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
              {profile.display_name || 'Your Brand Profile'}
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

      {/* Tabs */}
      <div className="flex border-b border-gray-100 px-5 pt-3">
        {(['identity', 'voice', 'history'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`mr-5 pb-2.5 text-xs font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            {tab === 'identity' ? '👤 Identity' : tab === 'voice' ? '🎨 Brand Voice' : '📋 History'}
          </button>
        ))}
      </div>

      <div className="px-5 py-4">
        {/* ── Identity Tab ── */}
        {activeTab === 'identity' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Brand / Display Name</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={profile.display_name}
                    onChange={(e) => updateProfile({ display_name: e.target.value })}
                    placeholder="Acme Co."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800 font-medium">{profile.display_name || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Industry</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={profile.industry}
                    onChange={(e) => updateProfile({ industry: e.target.value })}
                    placeholder="SaaS, Fashion, Fitness..."
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{profile.industry || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Twitter / X Handle</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={profile.twitter_handle || ''}
                    onChange={(e) => updateProfile({ twitter_handle: e.target.value || null })}
                    placeholder="@mybrand"
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{profile.twitter_handle || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Instagram Handle</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={profile.instagram_handle || ''}
                    onChange={(e) => updateProfile({ instagram_handle: e.target.value || null })}
                    placeholder="@mybrand_official"
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  />
                ) : (
                  <p className="text-sm text-gray-800">{profile.instagram_handle || <span className="text-gray-400 italic">Not set</span>}</p>
                )}
              </div>
            </div>

            {isEditing && (
              <TagListEditor
                label="Target Platforms"
                tags={profile.target_platforms}
                onChange={(t) => updateProfile({ target_platforms: t })}
                placeholder="twitter, instagram, tiktok..."
                color="indigo"
              />
            )}

            {!isEditing && profile.target_platforms.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Target Platforms</label>
                <div className="flex flex-wrap gap-1.5">
                  {profile.target_platforms.map((p) => (
                    <span key={p} className="px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full text-xs font-medium">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Extra fields */}
            {isEditing ? (
              <ExtraFieldsEditor
                fields={profile.extra_fields ?? {}}
                onChange={(f) => updateProfile({ extra_fields: f })}
              />
            ) : Object.keys(profile.extra_fields ?? {}).length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">추가 정보</label>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {Object.entries(profile.extra_fields ?? {}).map(([k, v]) => (
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

        {/* ── Brand Voice Tab ── */}
        {activeTab === 'voice' && (
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Brand Tone</label>
              {isEditing ? (
                <input
                  type="text"
                  value={voice.tone}
                  onChange={(e) => updateVoice({ tone: e.target.value })}
                  placeholder="casual and witty, professional, bold..."
                  className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              ) : (
                <p className="text-sm text-gray-800">
                  {voice.tone ? (
                    <span className="italic">"{voice.tone}"</span>
                  ) : (
                    <span className="text-gray-400 italic">Not defined</span>
                  )}
                </p>
              )}
            </div>

            <TagListEditor
              label="Preferred Styles"
              tags={voice.preferred_styles}
              onChange={(t) => updateVoice({ preferred_styles: t })}
              placeholder="Minimalist, Vibrant, Dark..."
              color="indigo"
            />

            <TagListEditor
              label="Content Pillars"
              tags={voice.content_pillars}
              onChange={(t) => updateVoice({ content_pillars: t })}
              placeholder="Education, Behind-the-scenes..."
              color="green"
            />

            <TagListEditor
              label="Signature Hashtags"
              tags={voice.signature_hashtags}
              onChange={(t) => updateVoice({ signature_hashtags: t })}
              placeholder="#BuildInPublic, #YourBrand..."
              color="yellow"
            />

            <TagListEditor
              label="Topics to Avoid"
              tags={voice.avoid_topics}
              onChange={(t) => updateVoice({ avoid_topics: t })}
              placeholder="politics, competitors..."
              color="red"
            />
          </div>
        )}

        {/* ── History Tab ── */}
        {activeTab === 'history' && (
          <div className="space-y-3">
            {memory.campaign_archive.length === 0 ? (
              <p className="text-sm text-gray-400 italic text-center py-4">
                No campaigns archived yet. Generate content to build history.
              </p>
            ) : (
              <>
                <PerformanceChart campaigns={memory.campaign_archive} />
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {[...memory.campaign_archive].reverse().slice(0, 10).map((campaign) => (
                  <div
                    key={campaign.campaign_id}
                    className="p-3 bg-white rounded-lg border border-gray-100 hover:border-indigo-100 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-medium text-gray-700 line-clamp-2">{campaign.goal}</p>
                      <span className="shrink-0 text-xs text-gray-300 font-mono">#{campaign.campaign_id}</span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {campaign.platforms_used.map((p) => (
                        <span key={p} className="px-1.5 py-0.5 bg-gray-50 text-gray-500 border border-gray-100 rounded text-[10px]">
                          {p}
                        </span>
                      ))}
                      {campaign.selected_trend && (
                        <span className="px-1.5 py-0.5 bg-blue-50 text-blue-500 border border-blue-100 rounded text-[10px]">
                          #{campaign.selected_trend}
                        </span>
                      )}
                    </div>
                    {campaign.guideline_summary && (
                      <p className="mt-1 text-[10px] text-gray-400 line-clamp-1">{campaign.guideline_summary}</p>
                    )}
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-gray-300">
                      <ClockIcon className="w-3 h-3" />
                      {new Date(campaign.timestamp).toLocaleDateString()}
                    </div>
                    {/* Performance stats display */}
                    {campaign.performance && (
                      <div className="mt-1.5 grid grid-cols-3 gap-1">
                        {(['views','clicks','impressions','likes','shares','comments'] as const).map((k) => (
                          <div key={k} className="text-center">
                            <p className="text-[10px] font-semibold text-gray-600">{campaign.performance![k].toLocaleString()}</p>
                            <p className="text-[9px] text-gray-300">{k}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Performance edit toggle */}
                    <button
                      onClick={() => {
                        if (editingCampaignId === campaign.campaign_id) {
                          setEditingCampaignId(null);
                        } else {
                          setEditingCampaignId(campaign.campaign_id);
                          setPerfDraft({
                            views: campaign.performance?.views ?? 0,
                            clicks: campaign.performance?.clicks ?? 0,
                            impressions: campaign.performance?.impressions ?? 0,
                            likes: campaign.performance?.likes ?? 0,
                            shares: campaign.performance?.shares ?? 0,
                            comments: campaign.performance?.comments ?? 0,
                          });
                        }
                      }}
                      className="mt-1.5 flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-600"
                    >
                      <ChartBarIcon className="w-3 h-3" />
                      {editingCampaignId === campaign.campaign_id ? 'Cancel' : (campaign.performance ? 'Update Performance' : 'Add Performance')}
                    </button>
                    {editingCampaignId === campaign.campaign_id && (
                      <div className="mt-2 space-y-1.5">
                        <div className="grid grid-cols-2 gap-1">
                          {(['views','clicks','impressions','likes','shares','comments'] as const).map((k) => (
                            <div key={k} className="flex flex-col">
                              <label className="text-[9px] text-gray-400">{k}</label>
                              <input
                                type="number"
                                min={0}
                                value={perfDraft[k] ?? 0}
                                onChange={(e) => setPerfDraft((prev) => ({ ...prev, [k]: Number(e.target.value) }))}
                                className="text-xs px-1.5 py-1 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-400"
                              />
                            </div>
                          ))}
                        </div>
                        <button
                          onClick={async () => {
                            await updateCampaignPerformance(userId, campaign.campaign_id, perfDraft as any);
                            setEditingCampaignId(null);
                          }}
                          className="w-full text-xs py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700"
                        >
                          Save Performance
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              </>
            )}

            <p className="text-[10px] text-gray-300 text-center">
              Showing last 10 of {memory.campaign_archive.length} campaigns
            </p>
          </div>
        )}
      </div>
    </li>
  );
}
