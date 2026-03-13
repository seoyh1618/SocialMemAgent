import InstagramPostBlock from "./blocks/instagram_post_block";
import TikTokPostBlock from "./blocks/tiktok_post_block";
import TwitterPostBlock from "./blocks/twitter_post_block";
import YouTubePostBlock from "./blocks/youtube_post_block";
import type { Base } from "../base";
import type { CampaignRecord, PerformanceData } from "../memory";

interface ArtifactBlocksProps {
  base: Base;
  campaigns?: CampaignRecord[];
}

function PerformanceMetrics({ performance }: { performance: PerformanceData }) {
  const metrics = [
    { label: "Views", value: performance.views },
    { label: "Clicks", value: performance.clicks },
    { label: "Impressions", value: performance.impressions },
    { label: "Likes", value: performance.likes },
    { label: "Shares", value: performance.shares },
    { label: "Comments", value: performance.comments },
  ].filter(m => m.value > 0);

  if (metrics.length === 0) return null;

  return (
    <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
      <p className="text-xs font-medium text-gray-500 mb-2">Performance</p>
      <div className="flex flex-wrap gap-3">
        {metrics.map(m => (
          <div key={m.label} className="text-center">
            <p className="text-sm font-semibold text-gray-800">{m.value.toLocaleString()}</p>
            <p className="text-xs text-gray-400">{m.label}</p>
          </div>
        ))}
      </div>
      {performance.collected_at && (
        <p className="text-xs text-gray-400 mt-2">
          Updated {new Date(performance.collected_at).toLocaleDateString()}
        </p>
      )}
    </div>
  );
}

function getLatestPerformance(campaigns: CampaignRecord[], platform: string): PerformanceData | null {
  const relevant = campaigns
    .filter(c => c.platforms_used?.includes(platform) && c.performance)
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return relevant[0]?.performance ?? null;
}

export default function ArtifactBlocks({ base, campaigns = [] }: ArtifactBlocksProps) {
  return (
    <>
      {base.twitter_post.enabled && (
        <li className="overflow-hidden rounded-xl border border-gray-200">
          <TwitterPostBlock
            contentText={base.twitter_post.value}
            username="BrandDesigner"
            profilePicUrl="https://randomuser.me/api/portraits/men/32.jpg"
          />
          {(() => {
            const perf = getLatestPerformance(campaigns, "twitter");
            return perf ? <PerformanceMetrics performance={perf} /> : null;
          })()}
        </li>
      )}
      {base.instagram_post.enabled && (
        <li className="overflow-hidden rounded-xl border border-gray-200">
          <InstagramPostBlock
            mediaUrl={base.instagram_post.value.image_url}
            contentText={base.instagram_post.value.post_text}
            username="BrandDesigner"
            profilePicUrl="https://randomuser.me/api/portraits/men/32.jpg"
          />
          {(() => {
            const perf = getLatestPerformance(campaigns, "instagram");
            return perf ? <PerformanceMetrics performance={perf} /> : null;
          })()}
        </li>
      )}
      {base.youtube_post.enabled && (
        <li className="overflow-hidden rounded-xl border border-gray-200">
          <YouTubePostBlock
            videoUrl={base.youtube_post.value.video_url}
            descriptionSnippet={base.youtube_post.value.description}
            thumbnailUrl="https://randomuser.me/api/portraits/men/32.jpg"
            videoTitle={base.youtube_post.value.title}
            channelName="branding_channel"
          />
          {(() => {
            const perf = getLatestPerformance(campaigns, "youtube");
            return perf ? <PerformanceMetrics performance={perf} /> : null;
          })()}
        </li>
      )}
      {base.tiktok_post.enabled && (
        <li className="overflow-hidden rounded-xl border border-gray-200">
          <TikTokPostBlock
            videoUrl={base.tiktok_post.value.video_url}
            profilePicUrl="https://randomuser.me/api/portraits/men/32.jpg"
          />
          {(() => {
            const perf = getLatestPerformance(campaigns, "tiktok");
            return perf ? <PerformanceMetrics performance={perf} /> : null;
          })()}
        </li>
      )}
    </>
  );
}
