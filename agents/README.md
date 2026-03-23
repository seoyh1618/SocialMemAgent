# Backend — MemGPT 기반 마케팅 에이전트 API

[English](#english) | 한국어

Google ADK + FastAPI 기반의 멀티 에이전트 백엔드입니다.

## 에이전트 구조

```
root_agent (라우터, Gemini 2.5 Flash)
├── content_orchestrator (16+ tools)
│   ├── instagram_strategist (4t + behavior)
│   ├── facebook_strategist (3t + behavior)
│   ├── x_strategist (4t + behavior)
│   ├── tiktok_strategist (5t + behavior)
│   ├── youtube_strategist (6t + behavior)
│   ├── linkedin_strategist (3t + behavior)
│   ├── pinterest_strategist (3t + behavior)
│   ├── threads_strategist (2t + behavior)
│   └── kakao_strategist (3t + behavior)
└── general_chat_agent (25+ tools)
    └── memory_agent (25 tools)
```

## 메모리 시스템 (MemGPT 확장)

| 계층 | 저장소 | 설명 |
|------|--------|------|
| **Core Memory** | SQLite | 4-Block (Human/Persona/Domain/Audience), 항상 컨텍스트 주입 |
| **Archival Memory** | Qdrant + SQLite | 캠페인/대화 벡터 검색 (ANN + keyword fallback) |
| **Recall Memory** | SQLite | L1(working_summary) + L2(session_summaries) + L3(long_term_summary) |
| **Behavior Graph** | SQLite | 채널×콘텐츠×토픽 성과 추적 + 피드백 루프 |

## 설치

### 사전 요구사항
- Python 3.12+
- Docker (Qdrant용)
- Google Cloud 프로젝트 (API Key + Service Account)

### 1. 의존성 설치

```bash
cd agents
pip install poetry
poetry install
```

### 2. 환경 변수 설정

`src/agents/.env` 파일 생성:

```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
X_API_KEY=your-x-api-key
QDRANT_URL=http://localhost:6333
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### 3. Qdrant 실행

```bash
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

### 4. 서버 실행

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8080
```

또는 직접:

```bash
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

## Docker 실행

```bash
# Docker Compose (Qdrant + App)
docker compose up --build

# 또는 개별 빌드
docker build -t agent-backend .
docker run -p 8080:8080 --env-file src/agents/.env agent-backend
```

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/signup` | 회원가입 |
| POST | `/auth/login` | 로그인 |
| GET | `/memory/{user_id}` | 메모리 조회 |
| PUT | `/memory/{user_id}` | 메모리 업데이트 (병합) |
| POST | `/sessions/create/{user_id}` | 대화 세션 생성 |
| POST | `/run_sse` | 메시지 전송 (SSE 스트리밍) |
| POST | `/sessions/sync/{user_id}/{session_id}` | 세션 → 영구 메모리 동기화 |
| PUT | `/memory/{user_id}/campaigns/{id}/performance` | 캠페인 성과 업데이트 |

## 주요 파일

```
agents/
├── src/
│   ├── main.py                    # FastAPI 엔트리포인트 + API 라우터
│   └── agents/
│       ├── agent.py               # 에이전트 정의 + MemGPT 콜백
│       ├── schemas.py             # Pydantic 스키마 (4-Block, AudienceSegment 등)
│       ├── memory_tools.py        # 30+ 메모리 도구 (Core/Archival/Recall/BG)
│       ├── prompt.py              # 프롬프트 텍스트
│       ├── channel_spec.py        # 9채널 사양 데이터베이스
│       ├── channel_trends.py      # 채널별 트렌드 API
│       └── sub_agents/
│           ├── orchestrator/      # 콘텐츠 오케스트레이터
│           ├── channels/          # 9채널 strategist 팩토리
│           ├── memory/            # 메모리 전용 에이전트 (25 tools)
│           ├── image_generation/   # Imagen 3.0 이미지 생성
│           ├── video_generation/   # Veo 비디오 생성
│           └── audio_generation/   # Google Cloud TTS
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

## 주요 상수

| 상수 | 값 | 설명 |
|------|-----|------|
| RECALL_WINDOW | 40,000 tokens | 리콜 메모리 윈도우 |
| CONTEXT_BUDGET | 50,000 chars | 컨텍스트 블록 총 예산 |
| CORE_CHAR_LIMIT | 5K/5K/3K | Human/Persona/Domain 한도 |
| L2 max | 10 entries | 세션별 요약 최대 보관 |
| L3 max | 3,000 chars | 장기 요약 최대 |
| Archive Cap | 50/100 | 캠페인/대화 SQLite 보관 한도 |
| Segment Cap | 20 | 오디언스 세그먼트 최대 |
| Traits Cap | 30 per segment | 세그먼트당 특성 최대 |

---

<a name="english"></a>

# Backend — MemGPT-based Marketing Agent API

Korean | [English](#english)

Multi-agent backend built with Google ADK + FastAPI.

## Agent Structure

```
root_agent (router, Gemini 2.5 Flash)
├── content_orchestrator (16+ tools)
│   ├── instagram_strategist (4t + behavior)
│   ├── facebook_strategist (3t + behavior)
│   ├── x_strategist (4t + behavior)
│   ├── tiktok_strategist (5t + behavior)
│   ├── youtube_strategist (6t + behavior)
│   ├── linkedin_strategist (3t + behavior)
│   ├── pinterest_strategist (3t + behavior)
│   ├── threads_strategist (2t + behavior)
│   └── kakao_strategist (3t + behavior)
└── general_chat_agent (25+ tools)
    └── memory_agent (25 tools)
```

## Memory System (MemGPT Extension)

| Layer | Storage | Description |
|-------|---------|-------------|
| **Core Memory** | SQLite | 4-Block (Human/Persona/Domain/Audience), always injected into context |
| **Archival Memory** | Qdrant + SQLite | Campaign/conversation vector search (ANN + keyword fallback) |
| **Recall Memory** | SQLite | L1(working_summary) + L2(session_summaries) + L3(long_term_summary) |
| **Behavior Graph** | SQLite | Channel×Content×Topic performance tracking + feedback loop |

## Installation

### Prerequisites
- Python 3.12+
- Docker (for Qdrant)
- Google Cloud Project (API Key + Service Account)

### 1. Install Dependencies

```bash
cd agents
pip install poetry
poetry install
```

### 2. Configure Environment

Create `src/agents/.env`:

```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
X_API_KEY=your-x-api-key
QDRANT_URL=http://localhost:6333
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### 3. Start Qdrant

```bash
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

### 4. Run Server

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8080
```

## Docker

```bash
docker compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register |
| POST | `/auth/login` | Login |
| GET | `/memory/{user_id}` | Get memory state |
| PUT | `/memory/{user_id}` | Update memory (merge) |
| POST | `/sessions/create/{user_id}` | Create session |
| POST | `/run_sse` | Send message (SSE streaming) |
| POST | `/sessions/sync/{user_id}/{session_id}` | Sync session to persistent memory |
| PUT | `/memory/{user_id}/campaigns/{id}/performance` | Update campaign performance |
