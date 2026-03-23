"""
Channel Specifications — 채널별 규칙 데이터

각 채널 strategist가 state["channel_spec"]에서 읽어 프롬프트에 주입.
새 채널 추가 시 여기에 spec만 추가하면 됨.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChannelSpec:
    """채널별 콘텐츠 생성 규칙"""
    channel_id: str
    display_name: str
    platform_type: str                  # "feed" | "video" | "messaging"

    # 텍스트 제한
    caption_limit: Optional[int]
    hashtag_limit: Optional[int]
    hashtag_recommendation: str

    # 이미지/영상 규격
    image_ratios: List[str]
    video_ratios: List[str]
    primary_ratio: str

    # 콘텐츠 유형
    content_types: List[str]
    primary_content: str

    # 채널 고유 특성
    special_features: List[str]
    tone_guidance: str
    best_practices: List[str]

    # 2025-2026 콘텐츠 트렌드
    trending_formats: List[str] = field(default_factory=list)
    virality_signals: List[str] = field(default_factory=list)
    algorithm_tips: List[str] = field(default_factory=list)

    # 생성 에이전트 필요 여부
    needs_image: bool = True
    needs_video: bool = False
    needs_audio: bool = False


# ─── Instagram ────────────────────────────────────────────────────────
INSTAGRAM = ChannelSpec(
    channel_id="instagram",
    display_name="Instagram",
    platform_type="feed",
    caption_limit=2200,
    hashtag_limit=30,
    hashtag_recommendation="8-15개 권장. 시그니처 태그 + 콘텐츠 관련 + 트렌드 태그 혼합",
    image_ratios=["1:1", "4:5", "1.91:1"],
    video_ratios=["9:16", "1:1", "4:5"],
    primary_ratio="1:1",
    content_types=["피드 포스트", "릴스", "스토리", "캐러셀"],
    primary_content="피드 포스트",
    special_features=[
        "위치 태그",
        "협찬 표시 (Paid Partnership)",
        "캐러셀 최대 10장",
        "릴스 최대 90초",
        "스토리 링크 스티커",
    ],
    tone_guidance="비주얼 중심. 감성적/라이프스타일 톤. 첫 줄이 핵심 — 피드에서 '더 보기' 전에 보이는 부분",
    best_practices=[
        "첫 문장으로 관심 끌기 (피드에서 2줄만 보임)",
        "CTA 포함 (댓글, 저장, 공유 유도)",
        "해시태그는 캡션 하단 또는 첫 번째 댓글에 배치",
        "캐러셀은 첫 장이 가장 중요 — 스와이프 유도 문구",
        "릴스는 처음 3초가 승부 — 훅 필수",
    ],
    trending_formats=[
        "릴스 (30-60초) — 도달의 90%+가 릴스에서 발생",
        "캐러셀 (최대 20장) — 저장/공유율 2배",
        "협업 포스트 (Collab) — 양쪽 팔로워에게 노출",
    ],
    virality_signals=[
        "DM 공유가 릴스 배포의 #1 신호",
        "저장(Save)이 참여율에 가장 큰 영향",
        "트렌드 오디오 48시간 내 사용",
    ],
    algorithm_tips=[
        "인스타 검색이 키워드 기반 — 캡션 SEO 중요",
        "릴스 훅 1-3초가 승부",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)

# ─── Facebook ─────────────────────────────────────────────────────────
FACEBOOK = ChannelSpec(
    channel_id="facebook",
    display_name="Facebook",
    platform_type="feed",
    caption_limit=63206,
    hashtag_limit=10,
    hashtag_recommendation="3-5개 권장. 과도한 해시태그는 역효과",
    image_ratios=["1.91:1", "1:1", "4:5"],
    video_ratios=["16:9", "1:1", "9:16"],
    primary_ratio="1.91:1",
    content_types=["포스트", "릴스", "스토리", "이벤트", "라이브"],
    primary_content="포스트",
    special_features=[
        "링크 프리뷰 (OG 이미지)",
        "이벤트 생성 연동",
        "그룹 공유 최적화",
        "페이스북 숍 연동",
        "Advantage+ 광고 연동",
    ],
    tone_guidance="커뮤니티 중심. 대화형/정보 공유 톤. 링크 포스트는 짧고 궁금증 유발",
    best_practices=[
        "링크 포스트는 설명 텍스트를 짧게 (1-2문장)",
        "이미지 포스트가 링크 포스트보다 도달률 높음",
        "질문형 포스트로 댓글 유도",
        "페이스북 그룹 공유를 고려한 콘텐츠",
        "영상은 자막 필수 (85% 무음 시청)",
    ],
    trending_formats=[
        "릴스 — 인스타와 동일하게 우선 배포",
        "네이티브 이미지 포스트 > 링크 포스트",
        "AI 추천 콘텐츠가 피드 ~30% (비팔로워 노출 증가)",
    ],
    virality_signals=[
        "첫 1시간 댓글 속도가 도달률 결정",
        "공유 > 좋아요 (공유/리액션 비율)",
        "의미있는 대화(Meaningful Social Interaction) 유도",
    ],
    algorithm_tips=[
        "그룹 내 포스트가 페이지 포스트보다 3-5배 도달",
        "질문형 포스트로 댓글 유도",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)

# ─── X (Twitter) ──────────────────────────────────────────────────────
X_TWITTER = ChannelSpec(
    channel_id="x",
    display_name="X (Twitter)",
    platform_type="feed",
    caption_limit=280,
    hashtag_limit=5,
    hashtag_recommendation="2-3개 권장. 트윗 본문에 자연스럽게 삽입",
    image_ratios=["16:9", "1:1"],
    video_ratios=["16:9", "1:1"],
    primary_ratio="16:9",
    content_types=["트윗", "쓰레드", "인용 RT", "폴"],
    primary_content="트윗",
    special_features=[
        "쓰레드 (최대 25개 트윗 연결)",
        "인용 리트윗",
        "폴 (투표)",
        "스페이스 (오디오)",
        "커뮤니티 노트",
    ],
    tone_guidance="간결하고 임팩트 있는 문구. 위트/유머가 바이럴에 효과적. 280자 안에 핵심 전달",
    best_practices=[
        "280자 제한 — 핵심만 간결하게",
        "긴 내용은 쓰레드로 분할 (각 트윗이 독립적으로도 의미 있게)",
        "이미지 첨부 시 참여율 150% 증가",
        "트렌드 해시태그 활용으로 노출 확대",
        "리플라이/인용 RT 유도하는 의견 제시형 톤",
    ],
    trending_formats=[
        "롱폼 포스트 (프리미엄 25,000자) — 배포 증가 추세",
        "커뮤니티 (그룹형) — 중요도 상승",
        "스페이스 클립 — 피드에서 높은 노출",
        "인용 RT가 단순 리트윗보다 효과적",
    ],
    virality_signals=[
        "인용/리플라이 속도 (첫 30분)",
        "고팔로워 계정의 참여가 도달 증폭",
        "쓰레드형 교육 콘텐츠가 저장/공유 높음",
    ],
    algorithm_tips=[
        "이미지 첨부 시 참여율 150% 증가",
        "타겟 시간대 피크 시간에 게시",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)

# ─── TikTok ───────────────────────────────────────────────────────────
TIKTOK = ChannelSpec(
    channel_id="tiktok",
    display_name="TikTok",
    platform_type="video",
    caption_limit=2200,
    hashtag_limit=10,
    hashtag_recommendation="3-5개. 디스커버리 최적화용 트렌드 태그 + 니치 태그",
    image_ratios=["9:16"],
    video_ratios=["9:16"],
    primary_ratio="9:16",
    content_types=["숏폼 영상", "포토 슬라이드", "라이브", "듀엣", "스티치"],
    primary_content="숏폼 영상",
    special_features=[
        "트렌드 사운드/음악",
        "듀엣 (화면 분할 반응)",
        "스티치 (영상 이어 붙이기)",
        "그린스크린 효과",
        "숍 기능 (커머스 연동)",
    ],
    tone_guidance="젊고 캐주얼한 톤. 처음 1-3초가 승부 — 강한 훅 필수. 트렌드 사운드 활용이 핵심",
    best_practices=[
        "처음 1-3초 훅이 생명 — 스크롤 멈추게 하는 시작",
        "세로 풀스크린 (9:16) 필수",
        "트렌드 사운드 사용 시 도달률 대폭 상승",
        "텍스트 오버레이로 핵심 메시지 전달 (음소거 시청 대비)",
        "15-60초가 최적 길이",
    ],
    trending_formats=[
        "2-5분 롱폼 영상 — 유튜브 경쟁용 배포 증가",
        "포토 캐러셀 — 교육/리스트 콘텐츠에 급성장",
        "TikTok Shop 연동 영상 — 알고리즘 부스트",
    ],
    virality_signals=[
        "완주율(Completion Rate)이 #1 신호",
        "DM/외부 공유율이 대규모 배포 트리거",
        "트렌드 사운드 24-72시간 내 사용",
    ],
    algorithm_tips=[
        "TikTok SEO: 캡션+화면텍스트+음성 모두 검색 대상",
        "훅 1초가 생명",
    ],
    needs_image=False,
    needs_video=True,
    needs_audio=True,
)

# ─── LinkedIn ─────────────────────────────────────────────────────────
LINKEDIN = ChannelSpec(
    channel_id="linkedin",
    display_name="LinkedIn",
    platform_type="feed",
    caption_limit=3000,
    hashtag_limit=10,
    hashtag_recommendation="3-5개. 업계/직무 관련 해시태그. 과도한 사용 지양",
    image_ratios=["1.91:1", "1:1", "4:5"],
    video_ratios=["16:9", "1:1", "9:16"],
    primary_ratio="1:1",
    content_types=["포스트", "아티클", "뉴스레터", "폴", "캐러셀 (PDF)", "라이브"],
    primary_content="포스트",
    special_features=[
        "아티클 (장문 블로그형)",
        "PDF 캐러셀 (문서 슬라이드)",
        "뉴스레터 발행",
        "폴 (투표)",
        "추천/리포스트",
        "회사 페이지 연동",
    ],
    tone_guidance="전문적이고 신뢰감 있는 톤. 개인 경험 기반 스토리텔링이 효과적. B2B/커리어 콘텐츠 중심",
    best_practices=[
        "첫 2-3줄이 '더 보기' 전에 노출 — 강한 훅 필수",
        "개인 경험/인사이트 기반 스토리텔링이 가장 높은 참여율",
        "PDF 캐러셀은 교육/인사이트 콘텐츠에 매우 효과적",
        "이모지 적절히 사용하되 과하지 않게 (가독성 향상용)",
        "댓글 달기를 유도하는 질문으로 마무리",
    ],
    trending_formats=[
        "PDF 캐러셀 (문서 슬라이드) — 텍스트 대비 2-3배 도달",
        "숏폼 비디오 — LinkedIn 비디오 탭 신설 2025",
        "뉴스레터 — 구독자에게 푸시 알림 자동 발송",
        "개인 경험 스토리텔링 포스트",
    ],
    virality_signals=[
        "체류 시간(Dwell Time)이 핵심 신호",
        "첫 90분 댓글 속도 → 2차 확산 여부 결정",
        "댓글이 리액션보다 가중치 높음",
    ],
    algorithm_tips=[
        "화-목 오전 7-9시 최적 게시",
        "첫 1시간 내 본인이 댓글 답글 → 2차 확산 트리거",
        "전문적이되 개인적 톤 — 법인 톤보다 개인 스토리가 효과적",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)

# ─── YouTube ──────────────────────────────────────────────────────────
YOUTUBE = ChannelSpec(
    channel_id="youtube",
    display_name="YouTube",
    platform_type="video",
    caption_limit=5000,
    hashtag_limit=15,
    hashtag_recommendation="태그란에 최대 500자. 설명에 3-5개 해시태그 포함",
    image_ratios=["16:9"],
    video_ratios=["16:9", "9:16"],
    primary_ratio="16:9",
    content_types=["롱폼 영상", "쇼츠", "라이브", "커뮤니티 포스트"],
    primary_content="롱폼 영상",
    special_features=[
        "썸네일 (CTR 결정 핵심 — 1280x720)",
        "챕터 타임스탬프",
        "엔드스크린 + 카드",
        "자막 (CC)",
        "쇼츠 (60초 이하 세로 영상)",
        "커뮤니티 포스트 (텍스트/이미지/폴)",
    ],
    tone_guidance="제목 SEO가 핵심. 썸네일 + 제목 조합이 클릭률 결정. 설명에 키워드 자연 삽입",
    best_practices=[
        "제목: 60자 이내, 핵심 키워드 앞에 배치",
        "썸네일: 텍스트 3-5단어, 고대비 색상, 얼굴 클로즈업 효과적",
        "설명: 처음 2줄이 검색 결과에 노출 — 핵심 내용 앞에",
        "챕터 타임스탬프로 시청 시간 증가",
        "쇼츠는 틱톡과 유사하지만 유튜브 SEO에 맞는 제목/설명 필요",
    ],
    trending_formats=[
        "쇼츠 — 구독자 획득의 핵심 채널",
        "팟캐스트형 롱폼 (1-3시간) — 유튜브가 #1 팟캐스트 플랫폼",
        "커뮤니티 포스트 — 영상 업로드 사이 참여 유지",
        "A/B 썸네일 테스트 — 유튜브 내장 기능",
    ],
    virality_signals=[
        "클릭률(CTR)이 #1 성장 신호",
        "평균 시청 시간 / 시청 비율",
        "첫 24-48시간 참여가 장기 배포 결정",
    ],
    algorithm_tips=[
        "홈피드 추천은 시청 이력 유사도 기반",
        "추천 영상(사이드바)은 토픽 클러스터링 기반",
    ],
    needs_image=True,
    needs_video=True,
    needs_audio=True,
)

# ─── Pinterest ────────────────────────────────────────────────────────
PINTEREST = ChannelSpec(
    channel_id="pinterest",
    display_name="Pinterest",
    platform_type="feed",
    caption_limit=500,
    hashtag_limit=20,
    hashtag_recommendation="자연어 키워드 중심. 해시태그보다 설명 텍스트의 키워드가 검색에 중요",
    image_ratios=["2:3", "1:1"],
    video_ratios=["2:3", "9:16", "1:1"],
    primary_ratio="2:3",
    content_types=["핀", "아이디어 핀", "영상 핀", "보드"],
    primary_content="핀",
    special_features=[
        "보드 분류 (카테고리 큐레이션)",
        "리치 핀 (제품 가격/재고 자동 연동)",
        "아이디어 핀 (다중 페이지 스토리)",
        "쇼핑 핀 (커머스 직접 연동)",
        "핀 스케줄링",
    ],
    tone_guidance="영감/발견 중심. 검색 기반 플랫폼 — SEO 키워드가 핵심. 시각적으로 아름답고 실용적인 콘텐츠",
    best_practices=[
        "세로형 이미지 (2:3) 권장 — 피드에서 더 넓은 영역 차지",
        "핀 제목에 검색 키워드 자연스럽게 포함",
        "설명에 관련 키워드 2-3회 반복 (SEO)",
        "텍스트 오버레이가 있는 이미지가 저장률 높음",
        "시즌/이벤트 콘텐츠는 45일 전에 올려야 검색에 노출",
    ],
    trending_formats=[
        "아이디어 핀 (멀티 페이지, 영상 우선) — 알고리즘 우대",
        "쇼핑 핀 (커머스 직접 연동) — 부스트",
        "비디오 핀 — 정적 이미지 대비 6배 참여율",
    ],
    virality_signals=[
        "저장률(Save Rate)이 #1 신호",
        "장기 배포: 수개월 후에도 바이럴 가능",
        "새 핀 생성이 리핀보다 알고리즘 우대",
    ],
    algorithm_tips=[
        "Pinterest는 비주얼 검색 엔진 — SEO 최우선",
        "시즌 콘텐츠 45-90일 전 게시",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)

# ─── Threads ──────────────────────────────────────────────────────────
THREADS = ChannelSpec(
    channel_id="threads",
    display_name="Threads",
    platform_type="feed",
    caption_limit=500,
    hashtag_limit=5,
    hashtag_recommendation="1-3개. 토픽 태그 형태로 사용 (#태그가 아닌 토픽 기반 분류)",
    image_ratios=["1:1", "4:5", "16:9"],
    video_ratios=["9:16", "1:1"],
    primary_ratio="1:1",
    content_types=["텍스트 포스트", "이미지 포스트", "캐러셀", "영상"],
    primary_content="텍스트 포스트",
    special_features=[
        "Instagram 계정 연동",
        "토픽 태그 (해시태그 대체)",
        "인용 리포스트",
        "Fediverse 연동 예정",
        "크로스 포스팅 (Instagram → Threads)",
    ],
    tone_guidance="대화형/캐주얼. X와 유사하지만 더 친근하고 커뮤니티 중심. 짧고 공감가는 글이 효과적",
    best_practices=[
        "500자 제한 — 핵심 메시지 간결하게",
        "대화를 유도하는 의견/질문형 포스트가 효과적",
        "인스타그램 팔로워와 시너지 — 크로스 포스팅 활용",
        "밈/유머 콘텐츠가 바이럴에 효과적",
        "텍스트 위주 플랫폼 — 이미지 없어도 OK",
    ],
    trending_formats=[
        "의견/질문형 텍스트 포스트 — 대화 유도",
        "캐러셀 (이미지 + 텍스트)",
        "인스타 릴스 크로스 포스팅",
    ],
    virality_signals=[
        "답글 속도와 대화 깊이",
        "리포스트/인용이 X와 유사한 역할",
        "진정성 > 브랜드 톤",
    ],
    algorithm_tips=[
        "해시태그 없음 → 토픽 태그 1개만 사용",
        "밈/유머가 바이럴에 매우 효과적",
    ],
    needs_image=False,
    needs_video=False,
    needs_audio=False,
)

# ─── 카카오톡 비즈니스 ─────────────────────────────────────────────────
KAKAO_BIZ = ChannelSpec(
    channel_id="kakao",
    display_name="카카오톡 비즈니스",
    platform_type="messaging",
    caption_limit=1000,
    hashtag_limit=0,
    hashtag_recommendation="해시태그 미사용. CTA 버튼 텍스트가 핵심",
    image_ratios=["2:1", "1:1"],
    video_ratios=["16:9", "1:1"],
    primary_ratio="2:1",
    content_types=["텍스트 메시지", "이미지 메시지", "카드형", "리스트형", "커머스형"],
    primary_content="카드형",
    special_features=[
        "버튼 CTA (최대 5개)",
        "쿠폰 발급",
        "예약 버튼",
        "채널 추가 CTA",
        "카카오 커머스 연동",
        "친구톡 (광고 메시지)",
        "알림톡 (정보성 메시지)",
    ],
    tone_guidance="간결하고 실용적. 혜택/가치 제안 중심. 버튼 텍스트가 행동 유도의 핵심",
    best_practices=[
        "메시지 제목: 한눈에 혜택이 보이게",
        "버튼 텍스트: 행동 동사 사용 (쿠폰 받기, 예약하기, 자세히 보기)",
        "이미지: 2:1 와이드 권장, 텍스트 최소화",
        "알림톡은 정보성만 가능 — 광고 문구 불가",
        "친구톡은 광고 가능하지만 발송 비용 고려",
    ],
    trending_formats=[
        "카드형 메시지 — 이미지 + 제목 + 설명 + CTA 버튼",
        "쿠폰/할인 메시지 — 가장 높은 열람률",
        "카카오 선물하기 연동 콘텐츠",
    ],
    virality_signals=[
        "카카오톡 내 공유가 한국 #1 바이럴 메커니즘",
        "선물하기 연동 시 자연 공유 유도",
        "시즌 이벤트(설날/추석/수능) 타이밍이 핵심",
    ],
    algorithm_tips=[
        "발송 시간: 점심 12-13시, 퇴근 후 18-20시 최적",
        "네이버 블로그 SEO + 카카오톡 배포 콤보가 가장 효과적",
    ],
    needs_image=True,
    needs_video=False,
    needs_audio=False,
)


# ─── Registry ─────────────────────────────────────────────────────────
CHANNEL_REGISTRY: dict[str, ChannelSpec] = {
    "instagram": INSTAGRAM,
    "facebook": FACEBOOK,
    "x": X_TWITTER,
    "twitter": X_TWITTER,
    "tiktok": TIKTOK,
    "linkedin": LINKEDIN,
    "youtube": YOUTUBE,
    "pinterest": PINTEREST,
    "threads": THREADS,
    "kakao": KAKAO_BIZ,
    "kakaotalk": KAKAO_BIZ,
}


def get_channel_spec(channel_id: str) -> ChannelSpec | None:
    """채널 ID로 spec 조회. 없으면 None."""
    return CHANNEL_REGISTRY.get(channel_id.lower().strip())


def get_all_channels() -> list[str]:
    """등록된 고유 채널 ID 목록 (alias 제외)."""
    return ["instagram", "facebook", "x", "tiktok", "linkedin", "youtube", "pinterest", "threads", "kakao"]


def format_channel_spec_for_prompt(spec: ChannelSpec) -> str:
    """채널 spec을 strategist 프롬프트에 주입할 텍스트로 포맷."""
    lines = [
        f"=== {spec.display_name} Channel Spec ===",
        f"Platform Type: {spec.platform_type}",
        f"Caption Limit: {spec.caption_limit or 'unlimited'}",
        f"Hashtag: {spec.hashtag_recommendation}",
        f"Image Ratios: {', '.join(spec.image_ratios)}  (default: {spec.primary_ratio})",
    ]
    if spec.video_ratios:
        lines.append(f"Video Ratios: {', '.join(spec.video_ratios)}")
    lines.append(f"Content Types: {', '.join(spec.content_types)}  (primary: {spec.primary_content})")
    lines.append(f"Tone: {spec.tone_guidance}")
    lines.append("Best Practices:")
    for bp in spec.best_practices:
        lines.append(f"  - {bp}")
    lines.append("Special Features:")
    for sf in spec.special_features:
        lines.append(f"  - {sf}")
    if spec.trending_formats:
        lines.append("2025-2026 Trending Formats:")
        for tf in spec.trending_formats:
            lines.append(f"  * {tf}")
    if spec.virality_signals:
        lines.append("Virality Signals:")
        for vs in spec.virality_signals:
            lines.append(f"  * {vs}")
    if spec.algorithm_tips:
        lines.append("Algorithm Tips:")
        for at in spec.algorithm_tips:
            lines.append(f"  * {at}")
    return "\n".join(lines)
