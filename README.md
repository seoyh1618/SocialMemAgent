# SocialMemAgent — MemGPT 기반 초개인화 멀티채널 마케팅 에이전트

> MemGPT의 3-Tier 메모리를 도메인 특화 **4-Block Core Memory + Audience Behavior Graph + 피드백 루프**로 확장한 LLM 장기 메모리 기반 초개인화 마케팅 에이전트

---

## 프로젝트 개요

### 연구 목적

LLM 장기 메모리(MemGPT) 기반 **초개인화(Hyper-Personalization) 마케팅 에이전트** 아키텍처를 제안합니다.

사용자 특성과 마케팅 성과 데이터를 **영구적으로 축적**하고, 시간의 경과와 관계없이 **영구 지속적으로 기억**하며, 이를 기반으로 캠페인을 생성하고 성과를 다시 학습하는 **피드백 루프**를 통해 **점진적으로 고도화**되는 초개인화 마케팅 에이전트입니다.

### 3가지 핵심 기여

1. **도메인 기반 개인화를 위한 Domain Profile Memory 구조 확장** — MemGPT의 Core Memory를 4-Block(Human + Persona + Domain + Audience)으로 재설계하여 업종별로 다른 개인화 전략 지원
2. **User Behavior Graph + Audience Segment를 활용한 행동 기반 개인화 강화** — 고객 행동 패턴을 그래프 구조로 모델링하고, 세그먼트별 성과를 추적하여 개인화 정확도 향상
3. **LLM 장기 메모리 기반 초개인화 마케팅 에이전트 구조 제안** — 계층적 요약(L1/L2/L3) + 자동 아카이빙/검색을 통한 영구 메모리 기반 멀티채널 콘텐츠 생성

### 쉬운 비유

| | 설명 |
|---|---|
| **ChatGPT** | 기억을 잃는 빵집 주인 — 단골이 와도 매번 "무엇을 드릴까요?" |
| **MemGPT** | 메모장을 가진 주인 — 이름과 취향을 적어두지만 관리가 수동 |
| **본 시스템** | 고객 관리 시스템을 갖춘 주인 — 구매 이력, 선호도, 행동 패턴을 자동 축적하고 맞춤 추천 |

---

## 핵심 기능

### 1. 4-Block Core Memory
사용자 정보를 목적별로 분리하여 독립적으로 관리합니다.

```
Core Memory
├── Human Block    — 사용자 기본 정보, 선호도, 속성 (5,000자)
├── Persona Block  — 브랜드 보이스, 톤, 스타일 (5,000자)
├── Domain Block   — 업종별 마케팅 전략 정보 (3,000자)
└── Audience Block — 구조화된 청중 세그먼트 (20개 세그먼트, 세그먼트당 30개 특성)
```

### 2. Audience Behavior Graph + 피드백 루프
- 고객 행동 데이터를 그래프 구조(노드 + 엣지)로 모델링
- 세그먼트별 성과(PerformanceEdge)를 추적하여 전략 개선
- `행동 패턴 분석 → 전략 생성 → 성과 측정 → 전략 업데이트` 피드백 루프

### 3. L1/L2/L3 계층적 요약 + 자동 아카이빙/검색
- **L1 (Working Summary)**: 현재 대화 요약 (2,500자)
- **L2 (Session Summaries)**: 세션별 요약 (최대 10개)
- **L3 (Long-term Summary)**: 전체 상호작용 장기 요약 (3,000자)
- **Auto Archival**: 매 턴 callback 기반 Qdrant 자동 아카이빙
- **Auto Retrieval**: before_agent_callback에서 과거 대화 자동 검색 + 프롬프트 주입

### 4. 9채널 멀티 에이전트
Instagram, Facebook, X(Twitter), TikTok, YouTube, LinkedIn, Pinterest, Threads, KakaoTalk — 각 채널 특성에 맞는 전문 Strategist 에이전트가 콘텐츠 생성

### 5. AudienceSegment + Traits
구조화된 타겟 청중 관리 — 세그먼트별 인구통계, 관심사, 행동 패턴을 독립적으로 추적

### 6. Qdrant 벡터 검색
- 2-path 검색: Qdrant ANN(근사 최근접 이웃) + keyword fallback
- campaigns/conversations 2개 컬렉션
- Qdrant 건강 모니터링(`_QDRANT_HEALTHY` 플래그)

### 7. Imagen 3.0 채널별 이미지 최적화
채널별 최적 이미지 비율(aspect_ratio) + 스타일 설정, Imagen 3.0 프롬프트 최적화

### 8. NLU Signal Detection
대화에서 도메인 정보(업종, 타겟 고객, 브랜드 특성)를 자동 감지하여 Core Memory 업데이트 제안

---

## 시스템 아키텍처

### 에이전트 트리

```
root_agent (라우터, Gemini 2.5 Flash)
│
├── content_orchestrator (16+ tools)
│   │   메모리 도구 6개 + 행동 분석 1개 + 9개 채널 Strategist AgentTool
│   │
│   ├── instagram_strategist (4 tools + behavior)
│   ├── facebook_strategist  (3 tools + behavior)
│   ├── tiktok_strategist    (5 tools + behavior)
│   ├── x_strategist         (4 tools + behavior)
│   ├── linkedin_strategist  (3 tools + behavior)
│   ├── youtube_strategist   (6 tools + behavior)
│   ├── pinterest_strategist (3 tools + behavior)
│   ├── threads_strategist   (2 tools + behavior)
│   └── kakao_strategist     (3 tools + behavior)
│
└── general_chat_agent (22+ tools)
    │   메모리 도구 + 트렌드 도구 + memory_agent AgentTool
    │
    └── memory_agent (25 tools)
            Core Memory CRUD, Recall, Archival, Behavior Graph, Summary 등
```

### 메모리 시스템

```
┌─────────────────────────────────────────────────────┐
│                   Context Window                     │
│  ┌───────────┐ ┌───────────┐ ┌────────┐ ┌────────┐ │
│  │  Human    │ │  Persona  │ │ Domain │ │Audience│ │
│  │  Block    │ │  Block    │ │ Block  │ │ Block  │ │
│  └───────────┘ └───────────┘ └────────┘ └────────┘ │
│  ┌──────────────────────────────────────────────┐   │
│  │  Recall Memory (최근 대화, 40K tokens)        │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Hierarchical Summary (L1 + L2 + L3)         │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Behavior Graph (nodes + edges + insights)   │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐   ┌───────────┐   ┌───────────┐
    │ SQLite  │   │  Qdrant   │   │   GCS     │
    │Core/Recall│  │ Campaigns │   │  Assets   │
    │Behavior │   │ Convos    │   │  Media    │
    └─────────┘   └───────────┘   └───────────┘
```

### 7-Step 사이클

1. **사용자 입력** → 2. **메모리 로드** (Core + Recall + Summary + Archival 검색) → 3. **NLU Signal 추출** → 4. **채널 라우팅** (orchestrator → strategist) → 5. **콘텐츠 생성** (채널별 최적화) → 6. **성과 수집** (Behavior Graph 업데이트) → 7. **메모리 업데이트** (자동 아카이빙)

---

## 기술 스택

| Category | Technology |
|----------|-----------|
| **Backend** | FastAPI + Google ADK (Agent Development Kit) + Python 3.12+ |
| **Frontend** | React 19 + TypeScript + TailwindCSS v4 |
| **LLM** | Gemini 2.5 Flash |
| **Embedding** | text-embedding-004 (768-dim) |
| **Vector DB** | Qdrant |
| **Image Generation** | Imagen 3.0 |
| **TTS** | Google Cloud TTS (Chirp3-HD) |
| **Video** | MoviePy + FFmpeg |
| **Session Storage** | SQLite (ADK DatabaseSessionService) |
| **Auth** | SQLite + bcrypt |
| **Media Storage** | Google Cloud Storage |
| **Package Manager** | Poetry (Backend) / npm (Frontend) |
| **Container** | Docker (Python 3.13-slim + FFmpeg) |

---

## 프로젝트 구조

```
SocialMediaBrandingAgent/
├── agents/                              # 백엔드
│   ├── src/
│   │   ├── main.py                      # FastAPI 엔트리포인트 + API 라우트
│   │   └── agents/
│   │       ├── agent.py                 # 에이전트 정의 + 콜백 (root_agent)
│   │       ├── schemas.py               # Pydantic 스키마 (Memory, Behavior 등)
│   │       ├── memory_tools.py          # 30+ 메모리 도구 (Core/Recall/Archival/Summary)
│   │       ├── prompt.py                # 에이전트 프롬프트
│   │       ├── channel_spec.py          # 채널별 사양 정의
│   │       ├── channel_trends.py        # 채널 트렌드 도구
│   │       ├── twitter_tools.py         # X(Twitter) API 도구
│   │       ├── video_editing_tools.py   # 비디오 편집 도구
│   │       ├── utils/
│   │       │   └── gcs_url_converters.py # GCS URL 변환 유틸리티
│   │       └── sub_agents/
│   │           ├── orchestrator/        # content_orchestrator
│   │           │   └── agent.py
│   │           ├── channels/            # 9채널 strategist 팩토리
│   │           │   └── factory.py
│   │           ├── memory/              # memory_agent
│   │           │   ├── agent.py
│   │           │   └── prompt.py
│   │           ├── image_generation/    # Imagen 3.0 이미지 생성
│   │           │   ├── agent.py
│   │           │   └── prompt.py
│   │           ├── video_generation/    # 비디오 생성
│   │           │   ├── agent.py
│   │           │   └── prompt.py
│   │           ├── audio_generation/    # TTS 오디오 생성
│   │           │   ├── agent.py
│   │           │   └── prompt.py
│   │           └── idea_generation/     # 아이디어 생성
│   │               ├── agent.py
│   │               └── prompt.py
│   ├── pyproject.toml                   # Poetry 의존성
│   ├── Dockerfile                       # Python 3.13-slim + FFmpeg
│   └── docker-compose.yml              # app + Qdrant 서비스
│
└── frontend/                            # 프론트엔드
    ├── src/
    │   ├── main.tsx                     # React 엔트리포인트
    │   ├── App.tsx                      # 라우터 설정
    │   ├── api.tsx                      # SSE 스트리밍 API 클라이언트
    │   ├── memory.ts                    # 메모리 타입 + API
    │   ├── auth.ts                      # 인증 API
    │   ├── AuthContext.tsx              # 인증 컨텍스트
    │   ├── pages/
    │   │   ├── landing_page.tsx         # 랜딩 페이지
    │   │   ├── login_page.tsx           # 로그인 페이지
    │   │   └── main_page.tsx            # 메인 채팅 페이지
    │   └── components/
    │       ├── ChatInterface.tsx         # 채팅 인터페이스
    │       ├── AppSidebar.tsx            # 사이드바
    │       ├── MemoryMapView.tsx         # 메모리 시각화
    │       ├── MemoryMindMap.tsx         # 메모리 마인드맵
    │       ├── ConversationHistoryTab.tsx # 대화 히스토리
    │       ├── CreationsTab.tsx          # 생성물 탭
    │       ├── LoginModal.tsx            # 로그인 모달
    │       └── blocks/                   # UI 블록 컴포넌트
    │           ├── profile_block.tsx      # 4-Tab 프로필 (Human/Persona/Domain/Audience)
    │           ├── audience_block.tsx     # 청중 세그먼트 관리
    │           ├── BehaviorGraphBlock.tsx # Behavior Graph 시각화
    │           ├── CampaignHistoryBlock.tsx # 캠페인 히스토리
    │           ├── performance_chart.tsx  # 성과 차트
    │           ├── instagram_post_block.tsx  # Instagram 프리뷰
    │           ├── facebook_post_block.tsx   # Facebook 프리뷰
    │           ├── twitter_post_block.tsx    # X 프리뷰
    │           ├── tiktok_post_block.tsx     # TikTok 프리뷰
    │           ├── youtube_post_block.tsx    # YouTube 프리뷰
    │           ├── linkedin_post_block.tsx   # LinkedIn 프리뷰
    │           ├── pinterest_post_block.tsx  # Pinterest 프리뷰
    │           ├── threads_post_block.tsx    # Threads 프리뷰
    │           ├── kakao_post_block.tsx      # KakaoTalk 프리뷰
    │           └── ...                       # 기타 블록
    └── package.json
```

---

## 시작하기

### 사전 요구사항

- **Python 3.12+** (백엔드)
- **Node.js 18+** (프론트엔드)
- **Docker** (Qdrant 벡터 DB용)
- **Poetry** (Python 패키지 관리)
- **Google Cloud 프로젝트**
  - Google AI API Key (Gemini 2.5 Flash)
  - Service Account JSON (Cloud Storage, TTS 등)
  - Cloud Storage 버킷

### 환경 변수 설정

`agents/src/agents/.env` 파일을 생성합니다:

```env
# Google AI
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-google-api-key

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# X(Twitter) API (선택)
X_API_KEY=your-x-api-key

# Qdrant
QDRANT_URL=http://localhost:6333
```

### 실행 방법

#### 방법 1: Docker Compose (권장)

```bash
cd SocialMediaBrandingAgent/agents
docker compose up --build
```

이 명령으로 백엔드(port 8080)와 Qdrant(port 6333)가 함께 실행됩니다.

프론트엔드는 별도로 실행합니다:

```bash
cd SocialMediaBrandingAgent/frontend
npm install
npm run dev
```

#### 방법 2: 개별 실행

```bash
# 1. Qdrant 벡터 DB 실행
docker run -d --name qdrant \
  -p 6333:6333 \
  -v qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest

# 2. 백엔드 실행
cd SocialMediaBrandingAgent/agents
pip install poetry
poetry install
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8080

# 3. 프론트엔드 실행
cd SocialMediaBrandingAgent/frontend
npm install
npm run dev
```

### 접속

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| 백엔드 API | http://localhost:8080 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

---

## MemGPT 대비 차이점

| 구분 | MemGPT (원본) | 본 시스템 (SocialMemAgent) |
|------|-------------|--------------------------|
| **Core Memory** | 2-Block (Human + Persona) | **4-Block** (Human + Persona + Domain + Audience) |
| **Archival Memory** | 외부 벡터 DB (수동 검색) | Qdrant ANN + **자동 아카이빙/검색** (callback 기반) |
| **Recall Memory** | 최근 대화 FIFO | Rolling Recall + **계층적 요약 (L1/L2/L3)** |
| **Behavior Graph** | 없음 | **Audience Behavior Graph** (노드 + 엣지 + 세그먼트별 성과) |
| **자동화 수준** | 수동 메모리 관리 | **NLU Signal 자동 감지** + 자동 아카이빙 + 자동 검색 |
| **도메인 특화** | 범용 | **업종별 마케팅 전략** (카페, 미용실, 식당 등) |
| **멀티채널** | 없음 | **9개 채널** 전문 Strategist 에이전트 |
| **피드백 루프** | 없음 | 성과 데이터 → Behavior Graph → 전략 개선 **자동 루프** |

---

## API 엔드포인트

### 인증

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/signup` | 회원가입 |
| POST | `/auth/login` | 로그인 |
| GET | `/auth/me/{user_id}` | 사용자 정보 조회 |

### 세션

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/sessions/create/{user_id}` | 새 대화 세션 생성 |
| POST | `/sessions/sync/{user_id}/{session_id}` | SSE 스트리밍 대화 |

### 메모리

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/memory/{user_id}` | 전체 메모리 조회 |
| PUT | `/memory/{user_id}` | 메모리 업데이트 |
| PATCH | `/memory/{user_id}` | 메모리 부분 업데이트 |
| GET | `/memory/{user_id}/conversations` | 대화 히스토리 조회 |

### 에셋 / 캠페인

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/memory/{user_id}/assets` | 에셋 목록 조회 |
| POST | `/memory/{user_id}/assets/upload` | 에셋 업로드 |
| DELETE | `/memory/{user_id}/assets/{asset_id}` | 에셋 삭제 |
| GET | `/memory/{user_id}/campaigns` | 캠페인 목록 조회 |
| PUT | `/memory/{user_id}/assets/{asset_id}/performance` | 에셋 성과 데이터 입력 |
| PUT | `/memory/{user_id}/campaigns/{campaign_id}/performance` | 캠페인 성과 데이터 입력 |

---

## 메모리 상수

| 상수 | 값 | 설명 |
|------|---|------|
| `RECALL_WINDOW` | 40,000 tokens | Recall Memory 윈도우 크기 |
| `CONTEXT_BUDGET` | 50,000 tokens | 전체 컨텍스트 예산 |
| `WORKING_SUMMARY` | 2,500 chars | L1 요약 최대 길이 |
| `L3 Summary` | 3,000 chars | 장기 요약 최대 길이 |
| `L2 Sessions` | 최대 10개 | 세션 요약 보관 수 |
| `TURNS_TO_COMPRESS` | 400 | 압축 트리거 턴 수 |
| `Core Char (Human/Persona)` | 각 5,000 chars | Human/Persona 블록 용량 |
| `Core Char (Domain)` | 3,000 chars | Domain 블록 용량 |
| `Audience Segments` | 최대 20개 | 청중 세그먼트 수 |
| `Traits per Segment` | 최대 30개 | 세그먼트당 특성 수 |
| `Asset Cap` | 200 | 에셋 최대 보관 수 |
| `Archive Cap (Campaign)` | 50 | SQLite 캠페인 아카이브 상한 |
| `Archive Cap (Conversation)` | 100 | SQLite 대화 아카이브 상한 |

---

## 주요 의존성

### 백엔드 (Python)

```
google-adk >= 1.4.1          # Google Agent Development Kit
fastapi >= 0.115.12           # 웹 프레임워크
google-generativeai >= 0.8.5  # Gemini API
google-cloud-storage >= 2.18  # Cloud Storage
google-cloud-texttospeech >= 2.27  # TTS
moviepy >= 2.2.1              # 비디오 편집
bcrypt >= 5.0.0               # 비밀번호 해싱
qdrant-client >= 1.12.0       # 벡터 DB 클라이언트
```

### 프론트엔드 (JavaScript/TypeScript)

```
react 19 + react-dom 19       # UI 프레임워크
tailwindcss v4                 # CSS 프레임워크
react-router-dom v7            # 라우팅
recharts v3                    # 차트 시각화
react-markdown                 # Markdown 렌더링
@headlessui/react              # UI 컴포넌트
@heroicons/react               # 아이콘
@fortawesome/*                 # Font Awesome 아이콘
```

---

## 참고 문헌

- **MemGPT**: Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as Operating Systems.* arXiv:2310.08560
- **Letta**: MemGPT의 확장 프로젝트 (https://github.com/letta-ai/letta)
- **Google ADK**: Google Agent Development Kit (https://google.github.io/adk-docs/)
- **Qdrant**: 벡터 검색 엔진 (https://qdrant.tech/)

---

## 저자

- **서연호** (syh2916@gmail.com)
