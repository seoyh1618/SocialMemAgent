"""
Channel Trend Tools — 채널별 트렌드 조회 도구

각 채널 strategist에서 사용하는 트렌드 분석 도구.
구현 우선순위:
  1. YouTube Trending API (공식)
  2. X/Twitter Trends (기존 get_trends 활용)
  3. Google Trends (pytrends — 전 채널 범용)
  4. TikTok Creative Center (스크래핑)
  5. Instagram Hashtag (Graph API)
  6. Naver DataLab (한국 시장 — Kakao용)
  7. Pinterest Trends (스크래핑)
  8. LinkedIn Trending (Google Trends fallback)
  9. Threads Trending (Google Trends fallback)
"""

import json
import logging
import os
from typing import Optional
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  1. Google Trends (범용 — 모든 채널에서 fallback으로 사용)
# ─────────────────────────────────────────────────────────────────────

def get_google_trends(
    keywords: str,
    region: str = "KR",
    timeframe: str = "now 7-d",
    platform: str = "",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Google Trends에서 키워드 관심도 + 관련 검색어를 조회합니다.

    Args:
        keywords: 쉼표로 구분된 키워드 (최대 5개). 예: "카페,라떼,봄"
        region: 국가 코드 (KR, US, JP 등). 기본값: KR
        timeframe: 기간 (now 7-d, today 1-m, today 3-m). 기본값: 최근 7일
        platform: 플랫폼 필터 (youtube, images, news, ""). 비워두면 웹 전체
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540)
        kw_list = [k.strip() for k in keywords.split(",")][:5]

        gprop = platform if platform in ("youtube", "images", "news", "froogle") else ""
        pytrends.build_payload(kw_list, timeframe=timeframe, geo=region, gprop=gprop)

        # 관련 검색어 (트렌드 키워드 확장에 유용)
        related = pytrends.related_queries()
        rising_queries = {}
        for kw in kw_list:
            if kw in related and related[kw].get("rising") is not None:
                rising_df = related[kw]["rising"]
                if not rising_df.empty:
                    rising_queries[kw] = rising_df.head(10).to_dict("records")

        # 한국 실시간 인기 검색어
        trending_now = []
        try:
            trending_df = pytrends.trending_searches(pn="south_korea")
            trending_now = trending_df[0].tolist()[:20]
        except Exception:
            pass

        return {
            "status": "success",
            "keywords": kw_list,
            "region": region,
            "timeframe": timeframe,
            "platform_filter": gprop or "web",
            "rising_queries": rising_queries,
            "trending_searches_kr": trending_now,
        }
    except ImportError:
        return {"status": "error", "message": "pytrends 라이브러리가 설치되지 않았습니다. pip install pytrends"}
    except Exception as e:
        logger.warning("Google Trends failed: %s", e)
        return {"status": "error", "message": str(e)}


# ─────────────────────────────────────────────────────────────────────
#  2. YouTube Trending (공식 API)
# ─────────────────────────────────────────────────────────────────────

def get_youtube_trends(
    region: str = "KR",
    category_id: str = "",
    max_results: int = 10,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """YouTube 인기 동영상 트렌드를 조회합니다.

    Args:
        region: 국가 코드 (KR, US, JP 등). 기본값: KR
        category_id: 비디오 카테고리 ID (비워두면 전체). 예: 22=People&Blogs, 24=Entertainment
        max_results: 반환할 최대 결과 수 (1-50). 기본값: 10
    """
    try:
        import httpx

        api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {"status": "error", "message": "YOUTUBE_API_KEY 또는 GOOGLE_API_KEY 환경변수가 설정되지 않았습니다."}

        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": min(max_results, 50),
            "key": api_key,
        }
        if category_id:
            params["videoCategoryId"] = category_id

        resp = httpx.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        trends = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            trends.append({
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "category": snippet.get("categoryId"),
                "tags": snippet.get("tags", [])[:10],
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "published_at": snippet.get("publishedAt"),
            })

        return {
            "status": "success",
            "region": region,
            "count": len(trends),
            "trending_videos": trends,
        }
    except Exception as e:
        logger.warning("YouTube Trends failed: %s", e)
        return {"status": "error", "message": str(e)}


def get_youtube_keyword_trends(
    keyword: str,
    region: str = "KR",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Google Trends의 YouTube 검색 트렌드를 조회합니다.

    Args:
        keyword: 검색할 키워드. 예: "카페 브이로그"
        region: 국가 코드. 기본값: KR
    """
    return get_google_trends(
        keywords=keyword,
        region=region,
        timeframe="today 1-m",
        platform="youtube",
    )


# ─────────────────────────────────────────────────────────────────────
#  3. Instagram Hashtag Trends
# ─────────────────────────────────────────────────────────────────────

def get_instagram_hashtag_trends(
    hashtags: str,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Instagram 해시태그 관련 트렌드를 조회합니다.
    Google Trends 기반 + 해시태그 추천.

    Args:
        hashtags: 쉼표로 구분된 해시태그 키워드. 예: "카페,봄,라떼"
    """
    # Google Trends로 관심도 조회
    trends_data = get_google_trends(keywords=hashtags, region="KR", timeframe="now 7-d")

    # Instagram 특화 해시태그 전략 생성
    kw_list = [k.strip() for k in hashtags.split(",")][:5]
    hashtag_strategy = {
        "input_keywords": kw_list,
        "recommended_mix": {
            "high_volume": [f"#{kw}" for kw in kw_list],
            "medium_niche": [f"#{kw}그램" for kw in kw_list] + [f"#{kw}스타그램" for kw in kw_list],
            "branded": "시그니처 해시태그는 Core Memory에서 가져오세요",
        },
        "tips": [
            "해시태그 8-15개가 최적 (30개 한도이지만 과하면 스팸 인식)",
            "첫 번째 댓글에 해시태그 배치도 효과적",
            "릴스에는 해시태그 3-5개만 사용 권장",
        ],
    }

    return {
        "status": "success",
        "google_trends": trends_data,
        "hashtag_strategy": hashtag_strategy,
        "content_format_trends_2025": {
            "top_formats": ["릴스 (30-60초)", "캐러셀 (최대 20장)", "협업 포스트"],
            "engagement_drivers": ["DM 공유가 릴스 배포의 #1 신호", "저장(Save)이 참여율에 가장 큰 영향"],
            "caption_seo": "인스타 검색이 키워드 기반으로 전환 — 캡션에 검색 가능한 문구 포함 필수",
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  4. TikTok Trends
# ─────────────────────────────────────────────────────────────────────

def get_tiktok_trends(
    country: str = "KR",
    category: str = "hashtag",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """TikTok 트렌드 해시태그/사운드를 조회합니다.
    TikTok Creative Center 내부 API 활용.

    Args:
        country: 국가 코드 (KR, US, JP 등). 기본값: KR
        category: 조회 유형 (hashtag 또는 sound). 기본값: hashtag
    """
    try:
        import httpx

        # TikTok Creative Center 내부 API
        if category == "sound":
            url = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/sound/list"
        else:
            url = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"

        params = {
            "page": 1,
            "limit": 20,
            "period": 7,  # 최근 7일
            "country_code": country,
        }

        resp = httpx.get(url, params=params, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 0:
            items = data.get("data", {}).get("list", [])
            trends = []
            for item in items[:20]:
                if category == "sound":
                    trends.append({
                        "title": item.get("sound_title", ""),
                        "artist": item.get("artist_name", ""),
                        "usage_count": item.get("usage_count", 0),
                    })
                else:
                    trends.append({
                        "hashtag": item.get("hashtag_name", ""),
                        "video_count": item.get("video_count", 0),
                        "view_count": item.get("view_count", 0),
                    })
            return {
                "status": "success",
                "country": country,
                "category": category,
                "count": len(trends),
                "trends": trends,
            }
        else:
            raise Exception(f"TikTok API returned code: {data.get('code')}")

    except Exception as e:
        logger.warning("TikTok Creative Center failed, falling back to Google Trends: %s", e)
        # Fallback: Google Trends
        fallback = get_google_trends(keywords="틱톡,TikTok", region="KR", timeframe="now 7-d")
        return {
            "status": "partial",
            "message": f"TikTok Creative Center 접근 불가 — Google Trends fallback 사용: {e}",
            "google_trends_fallback": fallback,
            "content_format_trends_2025": {
                "top_formats": ["15-60초 숏폼", "포토 캐러셀", "듀엣/스티치"],
                "virality_keys": ["완주율이 #1 신호", "트렌드 사운드 48시간 내 사용", "훅 1초"],
                "tiktok_seo": "캡션 + 화면 텍스트 + 음성 모두 검색 대상 (TikTok SEO)",
            },
        }


# ─────────────────────────────────────────────────────────────────────
#  5. Facebook Trends
# ─────────────────────────────────────────────────────────────────────

def get_facebook_trends(
    keywords: str,
    region: str = "KR",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Facebook 관련 트렌드를 조회합니다.
    공식 Trending API 없음 — Google Trends + 포맷 트렌드 제공.

    Args:
        keywords: 쉼표로 구분된 키워드. 예: "카페,프로모션"
        region: 국가 코드. 기본값: KR
    """
    trends_data = get_google_trends(keywords=keywords, region=region, timeframe="now 7-d")

    return {
        "status": "success",
        "google_trends": trends_data,
        "content_format_trends_2025": {
            "algorithm_priority": [
                "숏폼 영상 (Reels) — 인스타와 동일하게 우선 배포",
                "네이티브 이미지 포스트 > 링크 포스트 (도달률 차이)",
                "AI 추천 콘텐츠가 피드의 ~30% (비팔로워에게도 노출 가능)",
            ],
            "top_formats": ["릴스", "그룹 포스트", "이미지 포스트", "라이브"],
            "engagement_drivers": [
                "첫 1시간 댓글 속도가 도달률 결정",
                "공유/리액션 비율 (공유 > 좋아요)",
                "의미있는 대화(Meaningful Social Interaction) 유도",
            ],
            "tips": [
                "영상은 자막 필수 (85% 무음 시청)",
                "질문형 포스트로 댓글 유도",
                "그룹 내 포스트가 일반 페이지 포스트보다 3-5배 도달",
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  6. LinkedIn Trends
# ─────────────────────────────────────────────────────────────────────

def get_linkedin_trends(
    keywords: str,
    region: str = "KR",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """LinkedIn 관련 트렌드를 조회합니다.
    공식 Trending API 없음 — Google Trends + 포맷 트렌드 제공.

    Args:
        keywords: 쉼표로 구분된 키워드. 예: "마케팅,브랜딩,스타트업"
        region: 국가 코드. 기본값: KR
    """
    trends_data = get_google_trends(keywords=keywords, region=region, timeframe="now 7-d")

    return {
        "status": "success",
        "google_trends": trends_data,
        "content_format_trends_2025": {
            "top_formats": [
                "PDF 캐러셀 (문서 슬라이드) — 텍스트 대비 2-3배 도달",
                "숏폼 비디오 (LinkedIn 비디오 탭 신설 2025)",
                "뉴스레터 (구독자에게 푸시 알림)",
                "개인 경험 기반 스토리텔링 포스트",
            ],
            "algorithm_signals": [
                "체류 시간(Dwell Time)이 핵심 신호",
                "첫 90분 내 댓글 속도 → 1차 네트워크 확산 후 2차 확산",
                "댓글이 리액션보다 가중치 높음",
                "첫 1시간 내 본인이 댓글에 답글 달면 2차 확산 트리거",
            ],
            "posting_tips": [
                "화-목, 오전 7-9시가 최적 게시 시간",
                "첫 2-3줄이 '더 보기' 전에 노출 — 강한 훅 필수",
                "이모지 적절히 사용 (가독성 향상, 과하면 역효과)",
                "전문적이되 개인적인 톤 — 법인 톤보다 개인 스토리가 효과적",
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  7. Pinterest Trends
# ─────────────────────────────────────────────────────────────────────

def get_pinterest_trends(
    keywords: str,
    country: str = "KR",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Pinterest 검색 트렌드를 조회합니다.

    Args:
        keywords: 쉼표로 구분된 키워드. 예: "봄 인테리어,카페 디자인"
        country: 국가 코드. 기본값: KR
    """
    # Pinterest Trends 페이지 내부 API 시도
    trends_result = []
    try:
        import httpx
        kw_list = [k.strip() for k in keywords.split(",")][:3]
        for kw in kw_list:
            resp = httpx.get(
                f"https://trends.pinterest.com/api/v1/trends",
                params={"country": country, "keyword": kw},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                trends_result.append({"keyword": kw, "data": data})
    except Exception as e:
        logger.debug("Pinterest Trends API failed: %s", e)

    # Google Trends fallback
    google_fallback = get_google_trends(keywords=keywords, region=country, timeframe="today 3-m", platform="images")

    return {
        "status": "success" if trends_result else "partial",
        "pinterest_trends": trends_result if trends_result else "Pinterest Trends API 접근 불가 — Google Trends 사용",
        "google_trends_images": google_fallback,
        "content_format_trends_2025": {
            "top_formats": [
                "아이디어 핀 (멀티 페이지, 영상 우선) — 알고리즘 우대",
                "쇼핑 핀 (제품 직접 연동) — 커머스 부스트",
                "비디오 핀 — 정적 이미지 대비 6배 참여율",
            ],
            "seo_critical": [
                "Pinterest는 비주얼 검색 엔진 — SEO가 핵심",
                "핀 제목 + 설명에 검색 키워드 자연스럽게 포함",
                "보드 이름도 키워드 기반으로 작성",
                "시즌 콘텐츠는 45-90일 전에 게시해야 검색에 노출",
            ],
            "virality_keys": [
                "저장률(Save Rate)이 #1 신호",
                "장기 배포: 핀은 수개월 후에도 바이럴 가능 (다른 플랫폼과 차별점)",
                "새로운 핀 생성이 리핀보다 알고리즘에서 우대",
            ],
            "image_style": "세로형 2:3 비율 권장. 텍스트 오버레이 있는 이미지가 저장률 높음",
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  8. Threads Trends
# ─────────────────────────────────────────────────────────────────────

def get_threads_trends(
    keywords: str,
    region: str = "KR",
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Threads 관련 트렌드를 조회합니다.
    공식 Trending API 없음 — Google Trends + X/Twitter 크로스 레퍼런스.

    Args:
        keywords: 쉼표로 구분된 키워드.
        region: 국가 코드. 기본값: KR
    """
    trends_data = get_google_trends(keywords=keywords, region=region, timeframe="now 7-d")

    return {
        "status": "success",
        "google_trends": trends_data,
        "cross_reference": "Threads 트렌드는 X/Twitter 트렌드와 높은 상관관계 — X 트렌드 참조 권장",
        "content_format_trends_2025": {
            "platform_character": "텍스트 중심 플랫폼. 이미지 없이도 OK",
            "top_formats": [
                "의견/질문형 텍스트 포스트 (대화 유도)",
                "캐러셀 (이미지 + 텍스트)",
                "인스타 릴스 크로스 포스팅",
            ],
            "unique_features": [
                "해시태그 없음 → '토픽 태그' 1개만 사용 (포스트당 1개)",
                "인스타그램 팔로워 기반 시작 — 크로스 포스팅이 핵심",
                "밈/유머 콘텐츠가 바이럴에 매우 효과적",
            ],
            "engagement_drivers": [
                "답글 속도와 대화 깊이",
                "리포스트/인용이 X와 유사한 역할",
                "진정성 있는 개인적 목소리 > 브랜드 톤",
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  9. Kakao / Korean Market Trends
# ─────────────────────────────────────────────────────────────────────

def get_kakao_trends(
    keywords: str,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """한국 시장 트렌드를 조회합니다.
    Naver DataLab API + Google Trends KR.

    Args:
        keywords: 쉼표로 구분된 키워드. 예: "손목보호대,건강용품"
    """
    # Naver DataLab API 시도
    naver_result = None
    try:
        import httpx
        naver_client_id = os.getenv("NAVER_CLIENT_ID")
        naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
        if naver_client_id and naver_client_secret:
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            kw_list = [k.strip() for k in keywords.split(",")][:5]

            body = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "week",
                "keywordGroups": [
                    {"groupName": kw, "keywords": [kw]} for kw in kw_list
                ],
            }
            resp = httpx.post(
                "https://openapi.naver.com/v1/datalab/search",
                json=body,
                headers={
                    "X-Naver-Client-Id": naver_client_id,
                    "X-Naver-Client-Secret": naver_client_secret,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                naver_result = resp.json()
    except Exception as e:
        logger.debug("Naver DataLab failed: %s", e)

    # Google Trends KR fallback
    google_trends = get_google_trends(keywords=keywords, region="KR", timeframe="today 1-m")

    return {
        "status": "success",
        "naver_datalab": naver_result if naver_result else "NAVER_CLIENT_ID/SECRET 미설정 또는 API 오류",
        "google_trends_kr": google_trends,
        "content_format_trends_2025": {
            "kakao_specific": [
                "카드형 메시지 — 이미지 + 제목 + 설명 + CTA 버튼",
                "쿠폰/할인 메시지가 가장 높은 열람률",
                "친구톡 (광고) vs 알림톡 (정보) 구분 필수",
            ],
            "korean_market_trends": [
                "카카오톡 내 공유가 한국에서 #1 바이럴 메커니즘",
                "카카오 선물하기 연동 콘텐츠는 자연 공유 유도",
                "시즌 이벤트 (설날, 추석, 수능, K-pop 컴백)에 맞춘 타이밍이 핵심",
                "네이버 블로그 SEO + 카카오톡 배포 콤보가 가장 효과적",
            ],
            "messaging_best_practices": [
                "메시지 제목: 한눈에 혜택 보이게",
                "버튼 텍스트: 행동 동사 (쿠폰 받기, 예약하기)",
                "이미지 2:1 와이드 권장",
                "발송 시간: 점심 (12-13시), 퇴근 후 (18-20시) 최적",
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────
#  채널별 도구 매핑
# ─────────────────────────────────────────────────────────────────────

CHANNEL_TREND_TOOLS = {
    "instagram": [get_instagram_hashtag_trends, get_google_trends],
    "facebook": [get_facebook_trends],
    "x": [],  # 기존 twitter_tools.get_trends 사용
    "tiktok": [get_tiktok_trends, get_google_trends],
    "linkedin": [get_linkedin_trends],
    "youtube": [get_youtube_trends, get_youtube_keyword_trends],
    "pinterest": [get_pinterest_trends],
    "threads": [get_threads_trends],
    "kakao": [get_kakao_trends],
}
