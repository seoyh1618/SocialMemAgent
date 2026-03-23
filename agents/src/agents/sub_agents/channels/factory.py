"""
Channel Strategist Factory

각 채널별 strategist 에이전트를 생성하는 팩토리.
모든 strategist는 동일 구조:
  - state["channel_brief"]에서 브랜드 정보 읽기 (메모리 조회 불필요)
  - state["channel_spec"]에서 채널 규칙 읽기
  - 채널별 트렌드 도구 + 공유 생성 도구(AgentTool) 사용
"""

import logging
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from ...channel_spec import (
    get_channel_spec,
    get_all_channels,
    format_channel_spec_for_prompt,
    ChannelSpec,
)
from ..image_generation import image_generation_agent
from ..video_generation import video_generation_agent
from ..audio_generation import audio_generation_agent
from ..idea_generation import idea_generation_agent
from ...twitter_tools import advanced_search, get_trends
from ...channel_trends import CHANNEL_TREND_TOOLS
from ...memory_tools import memory_get_behavior_insights

logger = logging.getLogger(__name__)


# ─── 채널별 프롬프트 생성 ──────────────────────────────────────────────

# ─── 채널별 연구 기반 전략 프롬프트 (Evidence-Based) ──────────────────
# Sources: Social Insider, Buffer, Sprout Social, HubSpot, Hootsuite 2025-2026
# Academic: Adobe Visual Search Study, TikTok Music Impact Report, LinkedIn Algorithm Study

_CHANNEL_STRATEGY_GUIDES: dict[str, str] = {
    "instagram": """
=== INSTAGRAM EVIDENCE-BASED STRATEGY (2025-2026) ===

[FORMAT PRIORITY — by engagement rate]
1. Carousels: 0.55% engagement (highest). 6-10 panels optimal.
   - Cover slide: plain-language hook. Final slide: saveable recap.
2. Reels: 0.52% engagement. 30-90 seconds sweet spot.
   - 94% of distribution now comes from AI recommendations.
   - 7-15 second Reels work for trending/humor content.
3. Static images: declining 17% YoY — avoid as primary format.

[CAPTION OPTIMIZATION — research-backed numbers]
- 125-150 words = 3.1% engagement (peak).
  Under 50 words = 2.2%. Over 200 words = 2.4%.
- First line is the hook — only 2 lines show before "더 보기".
- Caption SEO > Hashtags: keyword-rich captions generate ~30% more reach
  and 2x more likes than hashtag-heavy posts.
- Meta recommends 3-5 highly relevant hashtags (not 30).

[ALGORITHM SIGNALS — confirmed by Adam Mosseri, Jan 2025]
1. Watch Time — users decide within 1.7 seconds.
2. Sends Per Reach (DM shares) — #1 signal for reaching NEW audiences.
3. Likes Per Reach — matters more for existing followers.
4. First 30-60 minutes of engagement determine extended reach.

[POSTING]
- Best days: Tue-Thu (Wednesday is the winner across 8 of 9 studies).
- Best hours: 7-9 AM, 11 AM-1 PM; evening 8-10 PM Wed/Thu.
- Platform average engagement: 0.48%.
""",

    "facebook": """
=== FACEBOOK EVIDENCE-BASED STRATEGY (2025-2026) ===

[FORMAT PRIORITY]
1. Photos: 35% more engagement than text, 44% more than videos.
2. Reels: 22% more engagement than traditional video. All videos auto-Reels now.
   Reels = 50% of time spent on FB+IG combined.
3. Posts with images: 2.3x more engagement than text-only.

[TEXT OPTIMIZATION]
- 40-80 characters = highest engagement.
- Posts under 80 chars have 66% higher engagement than longer posts.
- Sharp decline after 280 characters.
- Question-type posts drive the most comments.

[ALGORITHM — 2025]
- Organic reach: 1-2% (down from 16% in 2012).
- Groups deliver 3-5x more reach than Pages.
- AI-curated content = ~30% of feed (non-follower exposure possible).
- Meaningful Social Interaction (MSI) — comments > shares > reactions.
- First 1 hour comment velocity determines reach.

[POSTING]
- Reels get highest reach; photos get highest engagement.
- Video MUST have captions (85% watch muted).
- Platform average engagement: 0.15%.
""",

    "x": """
=== X (TWITTER) EVIDENCE-BASED STRATEGY (2025-2026) ===

[FORMAT PRIORITY]
1. Threads: 3x more engagement than single tweets.
   - Optimal: 4-8 tweets (7 is the sweet spot).
   - Visual breaks every 3-4 tweets → +45% completion rates.
2. Visual tweets: Images = +150% interactions. Video = 2-4x more reach.
3. Native uploads get 40% more engagement than links.

[TEXT OPTIMIZATION]
- 280 chars maximum (standard). Premium: 25,000 chars.
- Shorter = better for single tweets. Threads for depth.
- Quote RT with commentary outperforms plain RT.

[ALGORITHM — from open-sourced code]
- Reply depth is king: a reply-to-reply is weighted +75 vs +0.5 for a like.
  Conversation replies are 150x more powerful than likes.
- Grok monitors sentiment: positive/constructive → wider distribution.
  Negative/combative → reduced visibility even with high engagement.
- First hour engagement determines For You feed pickup.

[POSTING]
- Best: Weekdays 8 AM-2 PM. Monday 6 AM particularly effective.
- Tue-Thu generally strongest.
- Platform average engagement: 0.12%.
""",

    "tiktok": """
=== TIKTOK EVIDENCE-BASED STRATEGY (2025-2026) ===

[HOOK TIMING — critical research data]
- 1.3 seconds: thumb starts scrolling again. CAPTURE HERE.
- 3-second checkpoint: THE most critical algorithmic signal.
  70-85% retention at 3s → 2.2x more total views.
  Above 85% → viral potential. Below 60% → minimal promotion.
- 84.3% of viral TikToks used psychological hooks in first 3 seconds:
  pattern interruption, curiosity gaps, social proof.

[COMPLETION RATE BY LENGTH]
- Under 15s: 92% completion, 35% of views.
- 16-30s: 84% completion, 28% of views.
- 31-60s: 68% completion, 22% of views.
- Pattern interrupts every 3-5 seconds prevent drop-offs.

[SOUND/MUSIC — TikTok Music Impact Report]
- Music is central to 90% of most-viewed TikTok videos.
- 84% of Billboard Global 200 entries in 2024 went viral on TikTok first.
- Trending audio gets disproportionate algorithmic push.

[TEXT & SEO]
- TikTok SEO: caption + on-screen text + spoken keywords ALL indexed.
- Text overlays essential — most viewers start with sound off.

[POSTING]
- Peak: 5-9 PM weekdays.
- 1-4x per day = 56% better interaction rates.
- Platform average engagement: 3.70% (highest of all platforms, +49% YoY).
""",

    "linkedin": """
=== LINKEDIN EVIDENCE-BASED STRATEGY (2025-2026) ===

[FORMAT PRIORITY — by engagement rate]
1. Carousel/PDF: 24.42% engagement. 11.2x more impressions than text-only.
   15-20s dwell time vs 8-10s for text.
2. Text posts: 6.67% base. Personal stories → +300% engagement.
3. Video: ~3.5%. Drops after 30 seconds unless captioned.

[TEXT OPTIMIZATION — research-backed numbers]
- 1,200-1,800 characters = peak engagement zone.
- 1,300-1,400 characters = absolute sweet spot.
- First 140 characters = critical hook placement.
- "...see more" cutoff at ~210-220 chars on desktop.
- Strong hook openings → +45% more engagement.
- Structure: challenge → action → result → lesson.

[ALGORITHM — 2025]
- First 30 minutes influence 75% of total reach.
- Peak window posting: +38% engagement, +44% reach vs off-peak.
- Algorithm prioritizes expertise and original insights.
- Comments weighted more than reactions.
- Respond to comments within first hour → triggers second wave.

[POSTING]
- Best: Tue-Thu, 9 AM-12 PM.
- Tech: early morning. Finance: before market open.
- Recommended mix: Carousels 2-3x/week, polls 1-2x, text 1-2x.
- Median engagement: 6.5% (highest of all platforms).
""",

    "youtube": """
=== YOUTUBE EVIDENCE-BASED STRATEGY (2025-2026) ===

[THUMBNAIL — CTR research]
- Good CTR: 4-6%. Excellent: above 6%.
- Faces with strong emotion → +20-30% CTR.
- "Thumbnail-content alignment paradox": high CTR + poor retention = algorithm stops recommending.
- Use YouTube's native A/B thumbnail testing (2025).

[TITLE OPTIMIZATION]
- Front-load target keyword in first 5 words.
- Numbers + power words + clear value proposition.
- Keep under 60 characters (truncation point).

[VIDEO LENGTH & RETENTION]
- 5-10 minutes: peak retention at 31.5%.
- Shorts: 80-90% completion for top performers. Target 90-100% for under 20s.
- 30s Short at 85% watch time > 60s Short at 50% retention.
- Shorts: 16.9 subs per 10K views (discovery funnel).
- Shorts as teasers for long-form = proven growth strategy.

[ALGORITHM]
- Average view duration and % watched = primary signals.
- Replay rate: 15%+ = strong content signal.
- First hour engagement determines long-term distribution.
- Homepage recommendation: based on viewer watch history similarity.
- Suggested videos: topic clustering based.

[POSTING]
- Include chapters/timestamps (improves retention + SEO).
- Description: first 2 lines appear in search results.
""",

    "pinterest": """
=== PINTEREST EVIDENCE-BASED STRATEGY (2025-2026) ===

[VISUAL SEARCH — Adobe Study]
- 73% say Pinterest visual search results outperform traditional search.
- 36% of users start product searches on Pinterest.
- Pinterest IS a search engine — SEO is everything.

[PIN OPTIMIZATION]
- Standard Pin: 1000x1500px (2:3 ratio) — confirmed by Pinterest.
  Other ratios "may negatively impact performance."
- Idea Pins: 1080x1920px (9:16) for full-screen mobile.
- Video Pins: taller formats (2:3 to 1:2) = stronger saves/clicks.
  Square/landscape perform poorly.

[DESCRIPTION SEO — Tailwind study, 1M+ pins]
- Ideal: 100-500 characters.
- 5 or fewer keywords — quality over quantity.
- Pins with alt text: +25% impressions, +123% outbound clicks.

[ENGAGEMENT BENCHMARKS]
- Idea Pins: 0.5-1% (up to 8-10% for high-production).
- Standard Pins: 0.15-0.25%.
- Save rate: 1-2% in niche categories (food, DIY, fashion).

[ALGORITHM — four pillars]
1. Domain quality. 2. Pin quality. 3. Pinner quality. 4. Topic relevance.
- Seasonal content: publish 60-90 days before event.
- Consistency > sporadic posting.
- New pin creation > re-pins (algorithmic preference).
- Pins can go viral MONTHS after posting (unique to Pinterest).
""",

    "threads": """
=== THREADS EVIDENCE-BASED STRATEGY (2025-2026) ===

[PLATFORM STATUS]
- 400M+ MAU (Aug 2025). Fastest-growing text platform.
- Median engagement: 6.25% (vs X's 3.6%) — Buffer study, 10.2M posts.

[CONTENT STRATEGY]
- 500 chars main text. Up to 10,000 chars via text attachments (Sep 2025).
- Shorter, punchier content performs best — 500 chars is ceiling, not target.
- Images outperform all formats — even on this "text-first" platform.
- Video: short, snappy, hook in first 3 seconds.

[UNIQUE RULES]
- NO hashtags. Use 1 topic tag per post (not #tag, but topic selection).
- Links do NOT count against character limit.
- First line = headline. It's what stops the scroll.
- Threading: split long thoughts into numbered posts (1/5, 2/5...).

[CROSS-PLATFORM]
- Instagram followers port directly — cross-posting is key strategy.
- Content originating on Threads (not cross-posted) may get slight preference.

[VIRALITY]
- Reply velocity and conversation depth drive distribution.
- Reposts/quotes function like X's RT mechanism.
- Authentic personal voice > polished brand tone.
- Memes/humor are highly effective for virality.
""",

    "kakao": """
=== KAKAO / KOREAN MARKET EVIDENCE-BASED STRATEGY (2025-2026) ===

[KOREAN DIGITAL LANDSCAPE]
- 48.9M social media users (94.7% of population, Feb 2025).
- Average: 1 hour 14 minutes/day on social, 4.4 platforms used.
- Online advertising: 10.1 trillion won (~$7.8B), 59% of total ad spend.

[KAKAOTALK PERFORMANCE]
- 50M+ MAU. 97.5% of users in their 20s use it.
- Open rates: 3-5x higher than email in Korea.
- AI-powered ad CTR: +40% vs traditional display.
- Commerce GMV: KRW 2.7 trillion in Q4 2024, +12% YoY.

[MESSAGE OPTIMIZATION]
- Card-type message: image + title + description + CTA buttons.
- Coupon/discount messages get highest open rates.
- Button text: action verbs ("쿠폰 받기", "예약하기", "자세히 보기").
- Image: 2:1 wide format recommended. Minimize text on image.
- Best send times: lunch 12-13시, after work 18-20시.

[KOREAN CONSUMER BEHAVIOR]
- KakaoTalk share = #1 viral mechanism in Korea.
- Kakao Gift integration drives organic sharing.
- Naver Blog SEO + KakaoTalk distribution = most effective combo.
- Season events: 설날, 추석, 수능, K-pop comebacks = peak timing.
- Local beauty brands outperform global brands via platform-native approach.

[CRITICAL WARNING]
- Over-messaging causes mass unsubscribes. Quality > frequency.
- 알림톡: information only, NO advertising copy allowed.
- 친구톡: advertising OK but costs per message.
- Localize beyond translation — reflect Korean values and trends.
""",
}


def _build_strategist_prompt(spec: ChannelSpec) -> str:
    """채널별 연구 기반 strategist 프롬프트 생성."""
    channel_spec_text = format_channel_spec_for_prompt(spec)
    evidence_guide = _CHANNEL_STRATEGY_GUIDES.get(spec.channel_id, "")

    base_prompt = f"""You are a {spec.display_name} content strategist with deep expertise in {spec.display_name} marketing.
You create content that is specifically optimized for {spec.display_name}'s algorithm and user behavior.

**LANGUAGE RULE**: ALL content MUST be in the SAME LANGUAGE as the user's original query.
If the user wrote in Korean, ALL output must be in Korean. If in English, output in English.

{channel_spec_text}

{evidence_guide}

═══ BRAND CONTEXT (from orchestrator) ═══
{{_channel_brief}}
═══════════════════════════════════════════

## AUDIENCE SEGMENT PERSONALIZATION (CRITICAL)
When you see audience segments in the brand context:
1. Identify the PRIMARY target segment for this channel (highest engagement or first listed)
2. Use the segment's age_range, gender, and traits to personalize:
   - Language/tone appropriate for the age group
   - Pain points and motivations from traits → weave into caption
   - Products from the segment → feature in the content
3. If multiple segments exist, create the MAIN content for the primary segment
   and suggest 1-2 VARIANT captions for other segments
4. Reference what_worked/what_failed from behavior graph to avoid past mistakes

## BEHAVIOR GRAPH USAGE (IMPORTANT)
Before generating content:
1. Call `memory_get_behavior_insights` to check behavior graph insights (platform_best_content_type, what_worked, what_failed)
2. APPLY what_worked patterns to your content strategy
3. AVOID what_failed patterns
4. If this platform has low engagement history, suggest adjustments based on evidence-based strategy above

## PRODUCT IMAGE CONSISTENCY (CRITICAL)
When the brand context includes "PRODUCT IMAGE REFERENCE":
1. You MUST call image_generation_agent with analyze_user_image FIRST
2. From the analysis result, extract `product_details` and `color_palette`
3. Include these in the generate_image prompt: "Maintain exact product: [product_details]. Colors: [colors]"
4. This ensures ALL channels show the SAME product appearance

═══ YOUR TASK ═══
1. Read the brand context and evidence-based strategy guide carefully.
2. **Call `memory_get_behavior_insights`** to get behavior graph data for {spec.display_name}.
3. **Call your trend tool(s)** if available to get current {spec.display_name} trends.
4. Generate content that is OPTIMIZED for {spec.display_name}:
"""

    # 채널별 구체적 콘텐츠 생성 지시
    if spec.channel_id == "instagram":
        base_prompt += """
   a. CHOOSE FORMAT based on goal:
      - Brand awareness/reach → Reels (30-60s) or Carousel (6-10 panels)
      - Saves/education → Carousel with saveable recap on last panel
      - Engagement → Carousel (0.55% engagement, highest)
      DO NOT default to static images (declining 17% YoY).

   b. WRITE CAPTION following research:
      - Target 125-150 words (3.1% engagement sweet spot)
      - First line = scroll-stopping hook (only 2 lines show before "더 보기")
      - Use keyword-rich phrases for Instagram SEO (not just hashtags)
      - End with CTA: save, share, comment, or DM prompt
      - 3-5 highly relevant hashtags (Meta recommendation) + brand signature tags

   c. GENERATE IMAGE:
      - Ratio: 4:5 (takes more screen space than 1:1)
      - If carousel: design hook on panel 1, value on panels 2-9, CTA on panel 10
      - If Reels: thumbnail frame that captures attention in 1.7 seconds
      - If user has referenced an asset → analyze_user_image first
"""

    elif spec.channel_id == "facebook":
        base_prompt += """
   a. CHOOSE FORMAT:
      - Maximum reach → Reels (22% more engagement than traditional video)
      - Highest engagement → Photo post (35% more than text)
      - Community reach → Design for Group sharing (3-5x more reach than Page)
      AVOID link posts (deprioritized by algorithm).

   b. WRITE TEXT following research:
      - Target 40-80 characters (66% higher engagement than longer posts)
      - If longer content needed, keep under 280 characters
      - Question-type posts drive most comments
      - Design for shareability — "의미있는 대화" triggers MSI signal

   c. GENERATE IMAGE:
      - Ratio: 1.91:1 for link preview, 1:1 for feed post
      - If video: MUST include captions (85% watch muted)
"""

    elif spec.channel_id == "x":
        base_prompt += """
   a. CHOOSE FORMAT:
      - In-depth content → Thread (4-8 tweets, 7 optimal)
        Visual break every 3-4 tweets → +45% completion
      - Quick engagement → Single tweet with image (+150% interactions)
      - Commentary → Quote RT format

   b. WRITE TWEET following research:
      - Single tweet: concise, impactful, under 280 chars
      - Thread: each tweet must stand alone AND build on the narrative
      - Positive/constructive tone → wider distribution (Grok sentiment monitoring)
      - Design for reply depth — replies weighted 150x more than likes

   c. GENERATE IMAGE:
      - Ratio: 16:9
      - Native upload only (40% more engagement than links)
"""

    elif spec.channel_id == "tiktok":
        base_prompt += """
   a. DESIGN HOOK (most critical step):
      - First 1.3 seconds: thumb stops or scrolls. HOOK HERE.
      - Use pattern interruption, curiosity gap, or social proof.
      - 3-second retention must be 70-85%+ for algorithmic push.
      - Text overlay on screen for muted viewing.

   b. PLAN VIDEO STRUCTURE:
      - Target 15-30 seconds for maximum completion rate (84-92%)
      - Pattern interrupts every 3-5 seconds (B-roll, text change, camera switch)
      - Include trending sound/music (90% of top TikToks use music)
      - TikTok SEO: keywords in caption + on-screen text + spoken words

   c. WRITE CAPTION:
      - Keyword-rich for TikTok search
      - 3-5 hashtags (trend + niche mix)
      - Under 2,200 characters

   d. GENERATE VIDEO (9:16 vertical, full-screen):
      - video_generation_agent with hook-first structure
      - audio_generation_agent for narration if needed
"""

    elif spec.channel_id == "linkedin":
        base_prompt += """
   a. CHOOSE FORMAT:
      - Education/B2B → PDF Carousel (24.42% engagement, 11.2x impressions)
      - Personal brand → Text post with story structure (challenge→action→result→lesson)
      - Quick engagement → Poll or discussion question
      AVOID: generic corporate-tone posts (personal stories get 300% more engagement)

   b. WRITE POST following research:
      - Target 1,200-1,800 characters (peak zone). Sweet spot: 1,300-1,400.
      - First 140 characters = hook (before "...see more" at ~210 chars)
      - Use whitespace for readability (but authentic, not "broetry")
      - End with engagement prompt (question, call-to-comment)

   c. GENERATE CONTENT:
      - PDF carousel: educational slides with clear takeaways
      - Image: professional but human, 1:1 ratio
      - If video: caption required, keep under 30 seconds
"""

    elif spec.channel_id == "youtube":
        base_prompt += """
   a. DESIGN THUMBNAIL + TITLE (80% of click decision):
      - Thumbnail: 16:9, face with strong emotion (+20-30% CTR)
        3-5 words text overlay, high contrast colors
      - Title: keyword in first 5 words, under 60 chars
        Numbers + power words + clear value proposition
      - Good CTR target: 4-6%. Excellent: 6%+.

   b. WRITE DESCRIPTION:
      - First 2 lines appear in search results — put key content here
      - Include chapter timestamps for longer videos
      - Natural keyword placement throughout

   c. PLAN VIDEO:
      - Long-form: 5-10 minutes for peak retention (31.5%)
      - Shorts: target 90-100% retention for under 20 seconds
        30s Short at 85% watch > 60s Short at 50% retention
      - Shorts as teasers for long-form = proven growth strategy

   d. GENERATE: thumbnail (image_generation), video, audio/narration
"""

    elif spec.channel_id == "pinterest":
        base_prompt += """
   a. DESIGN PIN following research:
      - Standard Pin: 1000x1500px (2:3 ratio) — MUST use this ratio
        "Other ratios may negatively impact performance" — Pinterest official
      - Text overlay on image increases save rate
      - Idea Pin: 1080x1920px (9:16) for multi-page story format
      - Video Pin: taller formats (2:3 to 1:2), NOT square/landscape

   b. WRITE DESCRIPTION (SEO-critical):
      - 100-500 characters optimal
      - 5 or fewer keywords — quality and relevance over quantity
      - Include alt text (+25% impressions, +123% outbound clicks)
      - Board name should also be keyword-rich

   c. CONSIDER TIMING:
      - Seasonal content: publish 60-90 days BEFORE the event
      - Pins can go viral months later (unique long-tail distribution)
      - Consistency > sporadic posting
"""

    elif spec.channel_id == "threads":
        base_prompt += """
   a. WRITE TEXT following research:
      - First line = headline. This is what stops the scroll.
      - Short and punchy — 500 chars is ceiling, not target
      - Conversational/opinion-driven tone > polished brand voice
      - If long content: numbered threading (1/5, 2/5...)
      - Use 1 topic tag (NOT hashtag — Threads uses topic selection)

   b. CHOOSE FORMAT:
      - Text-only: works well if the writing is strong
      - Image + text: outperforms all other formats (even on "text-first" platform)
      - Video: short, hook in 3 seconds
      - Links: included freely (don't count against char limit)

   c. CROSS-PLATFORM:
      - If user has Instagram: leverage follower base
      - Authentic personal voice > branded corporate tone
      - Memes/humor = highly effective for virality
"""

    elif spec.channel_id == "kakao":
        base_prompt += """
   a. DESIGN MESSAGE following Korean market research:
      - Card-type message: image (2:1 wide) + title + description + CTA buttons
      - Button text: action verbs ("쿠폰 받기", "예약하기", "자세히 보기")
      - Coupon/discount messages get highest open rates
      - Keep text concise — value proposition immediately visible

   b. CONSIDER TIMING:
      - Best send times: 점심 12-13시, 퇴근 후 18-20시
      - Align with Korean events: 설날, 추석, 수능, K-pop 컴백
      - Kakao Gift integration drives organic sharing

   c. MESSAGE TYPE RULES:
      - 알림톡: information ONLY. NO advertising copy allowed.
      - 친구톡: advertising OK but costs per message.
      - Over-messaging causes mass unsubscribes — quality > frequency.

   d. GENERATE CARD IMAGE:
      - 2:1 wide format, minimal text on image
      - Clean, aesthetic design (Korean consumers respond to well-designed visuals)
"""

    else:
        # Generic fallback for any future channels
        base_prompt += f"""
   a. Call idea_generation_agent to generate ideas for {spec.display_name}
   b. Write content following the channel spec rules above
   c. Generate image/video if needed using the appropriate tool
"""

    base_prompt += f"""
5. Apply brand voice from context:
   - Use the exact tone specified
   - Include signature hashtags (if applicable to {spec.display_name})
   - Respect avoid_topics
   - Reference content pillars
   - Cite what you applied: "브랜드 톤 [X]와 과거 성과 데이터를 반영했습니다."

6. Return your output as JSON:
{{{{
    "channel": "{spec.channel_id}",
    "content_type": "<{spec.primary_content} or specific type chosen>",
    "caption": "<the post text/caption>",
    "hashtags": ["<list>", "<of>", "<hashtags>"],
    "image_url": "<generated image URL if any>",
    "video_url": "<generated video URL if any>",
    "image_ratio": "<ratio used>",
    "additional": {{<channel-specific extras: CTA buttons, thumbnail, thread tweets, etc.>}}
}}}}
"""

    return base_prompt


def _get_tools_for_channel(spec: ChannelSpec) -> list:
    """채널 spec에 따라 필요한 도구 목록 반환."""
    tools = [
        AgentTool(agent=idea_generation_agent),
        memory_get_behavior_insights,
    ]

    if spec.needs_image:
        tools.append(AgentTool(agent=image_generation_agent))

    if spec.needs_video:
        tools.append(AgentTool(agent=video_generation_agent))

    if spec.needs_audio:
        tools.append(AgentTool(agent=audio_generation_agent))

    # X/Twitter strategist는 기존 트렌드 도구 포함
    if spec.channel_id in ("x", "twitter"):
        tools.extend([get_trends, advanced_search])

    # 채널별 트렌드 도구 추가
    trend_tools = CHANNEL_TREND_TOOLS.get(spec.channel_id, [])
    tools.extend(trend_tools)

    return tools


def create_strategist(channel_id: str) -> Agent | None:
    """단일 채널 strategist 에이전트 생성."""
    spec = get_channel_spec(channel_id)
    if spec is None:
        logger.warning("Unknown channel: %s", channel_id)
        return None

    prompt_text = _build_strategist_prompt(spec)
    tools = _get_tools_for_channel(spec)

    return Agent(
        name=f"{spec.channel_id}_strategist",
        model="gemini-2.5-flash",
        description=f"Creates optimized content for {spec.display_name}. "
                    f"Platform type: {spec.platform_type}. "
                    f"Primary content: {spec.primary_content}.",
        instruction=prompt_text,
        tools=tools,
        output_key=f"{spec.channel_id}_output",
    )


def create_all_strategists() -> dict[str, Agent]:
    """모든 채널의 strategist 에이전트 생성."""
    result = {}
    for channel_id in get_all_channels():
        agent = create_strategist(channel_id)
        if agent:
            result[channel_id] = agent
    return result


# 모듈 로드 시 생성
STRATEGIST_REGISTRY: dict[str, Agent] = create_all_strategists()
