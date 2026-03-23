# Frontend — 초개인화 마케팅 에이전트 UI

[English](#english) | 한국어

React 19 + TypeScript + TailwindCSS v4 기반의 SPA 프론트엔드입니다.

## 주요 기능

- **9채널 콘텐츠 프리뷰** — Instagram, Facebook, X, TikTok, YouTube, LinkedIn, Pinterest, Threads, Kakao
- **4-Tab 프로필 편집기** — 사용자 정보 / 브랜드 보이스 / 도메인 프로필 / 타겟 오디언스
- **오디언스 세그먼트 관리** — 세그먼트 카드 + 자유형 Traits 추가/삭제
- **Behavior Graph 시각화** — 채널별 성과, 토픽 성과, what_worked/failed 태그
- **L1/L2/L3 메모리 요약** — 세션별/장기 요약 접기/펴기 카드
- **캠페인 히스토리** — 검색/필터 + 성과 입력 폼 (시맨틱 필드 포함)
- **메모리 맵** — 인터랙티브 마인드맵 시각화
- **SSE 스트리밍** — 실시간 에이전트 응답 + 리즈닝 단계 표시
- **UX** — 토스트 알림, 복사/다운로드, 타임스탬프, 에러 재시도, 온보딩 체크리스트, 스켈레톤 로딩

## 설치 및 실행

### 사전 요구사항
- Node.js 18+
- 백엔드 서버 실행 중 (http://localhost:8080)

### 설치

```bash
cd frontend
npm install
```

### 개발 서버 실행

```bash
npm run dev
```

http://localhost:5173 에서 접속

### 프로덕션 빌드

```bash
npm run build
npm run preview
```

## 프로젝트 구조

```
frontend/src/
├── main.tsx                          # 엔트리포인트
├── App.tsx                           # 라우터 + 프로바이더
├── memory.ts                         # 4-Block 메모리 타입 정의
├── base.tsx                          # 콘텐츠 생성 타입 정의
├── api.tsx                           # SSE + 세션 + 메모리 API
├── auth.ts                           # 인증 (로그인/회원가입)
│
├── pages/
│   ├── landing_page.tsx              # 메인 허브 (채팅 + 사이드패널)
│   ├── login_page.tsx                # 로그인/회원가입 페이지
│   └── main_page.tsx                 # 레거시 생성기 UI
│
├── components/
│   ├── AppSidebar.tsx                # 좌측 사이드바 (내비게이션 + 메모리 스냅샷)
│   ├── ChatInterface.tsx             # 채팅 스트리밍 컴포넌트
│   ├── LoginModal.tsx                # 로그인 모달
│   ├── MemoryMindMap.tsx             # 인터랙티브 메모리 그래프
│   ├── MemoryMapView.tsx             # 4-Block 메모리 카드 뷰
│   ├── ConversationHistoryTab.tsx    # 대화 히스토리 + L1/L2/L3 요약
│   ├── CreationsTab.tsx              # 에셋 갤러리 + 업로드
│   ├── artifact_blocks.tsx           # 9채널 아티팩트 렌더링
│   │
│   └── blocks/
│       ├── profile_block.tsx         # 4-Tab 프로필 편집기
│       ├── CampaignHistoryBlock.tsx  # 캠페인 히스토리 + 검색/필터
│       ├── BehaviorGraphBlock.tsx    # Behavior Graph 시각화
│       ├── performance_chart.tsx     # 성과 차트 (Recharts)
│       ├── instagram_post_block.tsx  # 인스타그램 프리뷰
│       ├── facebook_post_block.tsx   # 페이스북 프리뷰
│       ├── twitter_post_block.tsx    # X(트위터) 프리뷰
│       ├── youtube_post_block.tsx    # 유튜브 프리뷰
│       ├── tiktok_post_block.tsx     # 틱톡 프리뷰
│       ├── linkedin_post_block.tsx   # 링크드인 프리뷰
│       ├── pinterest_post_block.tsx  # 핀터레스트 프리뷰
│       ├── threads_post_block.tsx    # 스레드 프리뷰
│       └── kakao_post_block.tsx      # 카카오 프리뷰
│
├── contexts/
│   └── ToastContext.tsx              # 토스트 알림 시스템
│
└── index.css                         # TailwindCSS v4 + 커스텀 애니메이션
```

## 메모리 타입 구조 (memory.ts)

```typescript
MemoryState {
  human_block:    HumanBlock         // 사용자 정보 (이름, 핸들)
  persona_block:  PersonaBlock       // 브랜드 보이스 (톤, 스타일)
  domain_block:   DomainBlock        // 도메인 정보 (업종, USP, 경쟁사)
  audience_block: AudienceBlock      // 타겟 오디언스 (세그먼트 + Traits)
  campaign_archive: CampaignRecord[] // 과거 캠페인
  behavior_graph: BehaviorGraph      // 성과 학습 그래프
  recall_log: RecallEntry[]          // 최근 대화 이력
  working_summary: string            // L1 요약
  session_summaries: string[]        // L2 세션별 요약
  long_term_summary: string          // L3 장기 요약
}
```

## 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| React | 19 | UI 프레임워크 |
| TypeScript | 5.8 | 타입 안전성 |
| TailwindCSS | v4 | 스타일링 |
| Vite | 6 | 번들러/개발 서버 |
| Recharts | 3 | 성과 차트 |
| Heroicons | 2 | UI 아이콘 |
| FontAwesome | 6 | 브랜드 아이콘 |
| React Router | 7 | 라우팅 |

## 백엔드 연결

API Base URL은 `api.tsx`와 `auth.ts`에서 `http://localhost:8080`으로 설정되어 있습니다.
프로덕션 배포 시 환경변수로 변경하세요.

---

<a name="english"></a>

# Frontend — Hyper-Personalized Marketing Agent UI

Korean | [English](#english)

SPA frontend built with React 19 + TypeScript + TailwindCSS v4.

## Key Features

- **9-Channel Content Preview** — Instagram, Facebook, X, TikTok, YouTube, LinkedIn, Pinterest, Threads, Kakao
- **4-Tab Profile Editor** — User Info / Brand Voice / Domain Profile / Target Audience
- **Audience Segment Manager** — Segment cards + flexible Traits add/delete
- **Behavior Graph Visualization** — Platform performance, topic performance, what_worked/failed tags
- **L1/L2/L3 Memory Summary** — Session/long-term summary with collapsible cards
- **Campaign History** — Search/filter + performance input form (semantic fields)
- **Memory Mind Map** — Interactive knowledge graph visualization
- **SSE Streaming** — Real-time agent responses + reasoning step display
- **UX** — Toast notifications, copy/download, timestamps, error retry, onboarding checklist, skeleton loading

## Setup

### Prerequisites
- Node.js 18+
- Backend server running at http://localhost:8080

### Install

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Access at http://localhost:5173

### Production Build

```bash
npm run build
npm run preview
```

## Project Structure

```
frontend/src/
├── main.tsx                          # Entry point
├── App.tsx                           # Router + Providers
├── memory.ts                         # 4-Block memory type definitions
├── api.tsx                           # SSE + Session + Memory APIs
├── auth.ts                           # Authentication
├── pages/                           # Page components
├── components/                      # UI components
│   ├── blocks/                      # Channel previews + editors
│   └── ...                          # Sidebar, chat, memory visualization
└── contexts/                        # React contexts (Toast)
```

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19 | UI Framework |
| TypeScript | 5.8 | Type Safety |
| TailwindCSS | v4 | Styling |
| Vite | 6 | Bundler/Dev Server |
| Recharts | 3 | Performance Charts |
| Heroicons | 2 | UI Icons |
| React Router | 7 | Routing |

## Backend Connection

API Base URL is set to `http://localhost:8080` in `api.tsx` and `auth.ts`.
Update for production deployment.
