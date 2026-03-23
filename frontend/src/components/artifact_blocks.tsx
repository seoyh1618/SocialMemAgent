import InstagramPostBlock from "./blocks/instagram_post_block";
import TikTokPostBlock from "./blocks/tiktok_post_block";
import TwitterPostBlock from "./blocks/twitter_post_block";
import YouTubePostBlock from "./blocks/youtube_post_block";
import FacebookPostBlock from "./blocks/facebook_post_block";
import LinkedInPostBlock from "./blocks/linkedin_post_block";
import PinterestPostBlock from "./blocks/pinterest_post_block";
import ThreadsPostBlock from "./blocks/threads_post_block";
import KakaoPostBlock from "./blocks/kakao_post_block";
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

function ChannelWrapper({ children, campaigns, platform }: { children: React.ReactNode; campaigns: CampaignRecord[]; platform: string }) {
  const perf = getLatestPerformance(campaigns, platform);
  return (
    <li className="overflow-hidden rounded-xl border border-gray-200">
      {children}
      {perf && <PerformanceMetrics performance={perf} />}
    </li>
  );
}

export default function ArtifactBlocks({ base, campaigns = [] }: ArtifactBlocksProps) {
  return (
    <>
      {base.instagram_post?.enabled && (base.instagram_post.value.post_text || base.instagram_post.value.image_url) && (
        <ChannelWrapper campaigns={campaigns} platform="instagram">
          <InstagramPostBlock
            mediaUrl={base.instagram_post.value.image_url}
            contentText={base.instagram_post.value.post_text}
          />
        </ChannelWrapper>
      )}
      {base.facebook_post?.enabled && base.facebook_post.value && typeof base.facebook_post.value === 'object' && (base.facebook_post.value as any).post_text && (
        <ChannelWrapper campaigns={campaigns} platform="facebook">
          <FacebookPostBlock
            contentText={(base.facebook_post.value as any).post_text}
            mediaUrl={(base.facebook_post.value as any).image_url}
          />
        </ChannelWrapper>
      )}
      {base.twitter_post?.enabled && base.twitter_post.value && (
        <ChannelWrapper campaigns={campaigns} platform="twitter">
          <TwitterPostBlock contentText={base.twitter_post.value} />
        </ChannelWrapper>
      )}
      {base.threads_post?.enabled && base.threads_post.value && (
        <ChannelWrapper campaigns={campaigns} platform="threads">
          <ThreadsPostBlock contentText={base.threads_post.value} />
        </ChannelWrapper>
      )}
      {base.linkedin_post?.enabled && base.linkedin_post.value && typeof base.linkedin_post.value === 'object' && (base.linkedin_post.value as any).post_text && (
        <ChannelWrapper campaigns={campaigns} platform="linkedin">
          <LinkedInPostBlock
            contentText={(base.linkedin_post.value as any).post_text}
            mediaUrl={(base.linkedin_post.value as any).image_url}
          />
        </ChannelWrapper>
      )}
      {base.youtube_post?.enabled && base.youtube_post.value?.title && (
        <ChannelWrapper campaigns={campaigns} platform="youtube">
          <YouTubePostBlock
            videoUrl={base.youtube_post.value.video_url}
            descriptionSnippet={base.youtube_post.value.description}
            videoTitle={base.youtube_post.value.title}
            channelName="Brand Channel"
          />
        </ChannelWrapper>
      )}
      {base.tiktok_post?.enabled && base.tiktok_post.value?.video_url && (
        <ChannelWrapper campaigns={campaigns} platform="tiktok">
          <TikTokPostBlock videoUrl={base.tiktok_post.value.video_url} />
        </ChannelWrapper>
      )}
      {base.pinterest_post?.enabled && base.pinterest_post.value && typeof base.pinterest_post.value === 'object' && (base.pinterest_post.value as any).image_url && (
        <ChannelWrapper campaigns={campaigns} platform="pinterest">
          <PinterestPostBlock
            mediaUrl={(base.pinterest_post.value as any).image_url}
            description={(base.pinterest_post.value as any).post_text}
          />
        </ChannelWrapper>
      )}
      {base.kakao_post?.enabled && base.kakao_post.value && typeof base.kakao_post.value === 'object' && (base.kakao_post.value as any).post_text && (
        <ChannelWrapper campaigns={campaigns} platform="kakao">
          <KakaoPostBlock
            contentText={(base.kakao_post.value as any).post_text}
            mediaUrl={(base.kakao_post.value as any).image_url}
          />
        </ChannelWrapper>
      )}
    </>
  );
}
