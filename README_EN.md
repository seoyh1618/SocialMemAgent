# SocialMemAgent — Hyper-Personalized Multi-Channel Marketing Agent with MemGPT-Style Long-Term Memory

> Extending MemGPT's 3-Tier Memory with Domain-Specific 4-Block Core Memory + Audience Behavior Graph + Performance Feedback Loop

[한국어](SocialMediaBrandingAgent/README.md) | **English**

---

## Overview

Large Language Model (LLM) agents forget everything between sessions. MemGPT (Packer et al., 2023) addressed this with an OS-inspired virtual memory hierarchy—Core, Recall, and Archival—that gives LLMs the illusion of unbounded context. However, MemGPT was designed as a general-purpose conversational memory system. It does not model domain-specific user profiles, audience behavior, or performance feedback loops.

**SocialMemAgent** extends the MemGPT architecture for the marketing domain. It is a multi-agent system that permanently accumulates user characteristics and campaign performance data, remembers them persistently across sessions, and progressively refines its strategies through a feedback loop: generate campaign, collect performance, learn, generate better campaign.

### Three Key Research Contributions

1. **Domain-Specific 4-Block Core Memory** — Extends MemGPT's 2-Block (Human + Persona) to 4-Block (Human + Persona + Domain + Audience), enabling industry-specific personalization (e.g., a cafe needs emotional content strategies, a salon needs before/after strategies, a restaurant needs menu-highlight strategies).

2. **Audience Behavior Graph with Performance Feedback Loop** — Models audience behavior data as a graph structure combined with the memory system. Tracks performance per audience segment (`PerformanceEdge.segment_id`) and feeds insights back into strategy generation.

3. **Hierarchical Summary Chain (L1/L2/L3) + Automatic Archival/Retrieval** — Replaces MemGPT's single-summary recall with a three-level pyramid (working summary, session summaries, long-term summary). Adds automatic conversation archival to Qdrant every turn via callbacks and automatic past conversation retrieval before each agent invocation.

### The Bakery Analogy

| System | Analogy |
|--------|---------|
| ChatGPT | A baker who forgets every customer the next day |
| MemGPT | A baker with a notebook (but might forget to write things down) |
| **SocialMemAgent** | A baker with a CRM system (automatic recording + automatic recall) |

---

## Key Features

1. **Persistent Long-Term Memory** — User profiles, brand voice, campaigns, and audience data survive across sessions indefinitely via SQLite + Qdrant vector storage.

2. **4-Block Core Memory** — HumanBlock (user info), PersonaBlock (brand voice), DomainBlock (industry-specific marketing strategy), AudienceBlock (structured audience segments with flexible traits).

3. **9-Channel Multi-Platform Support** — Instagram, Facebook, X (Twitter), TikTok, LinkedIn, YouTube, Pinterest, Threads, Kakao — each with a dedicated strategist agent, channel-specific tools, and optimized content formats.

4. **Audience Behavior Graph** — Graph-based audience behavior modeling with performance edges, segment-level tracking, and aggregated insights that feed back into content strategy.

5. **Hierarchical Recall Compression** — L1 working summary (2,500 chars) + L2 session summaries (max 10) + L3 long-term summary (3,000 chars), preventing context window overflow while preserving long-term context.

6. **Automatic Archival and Retrieval** — Every conversation turn is automatically archived to Qdrant (callback-based). Past conversations are automatically retrieved and injected into the prompt before each agent invocation.

7. **Multimodal Content Generation** — Text + Image (Imagen 3.0 with channel-specific aspect ratios) + Video (Veo 2.0) + Audio (TTS via Chirp3-HD). Product image consistency enforced through `product_details` and `color_palette`.

8. **Real-Time Trend Analysis** — Channel-specific trend tools (hashtags, keywords, trending topics) integrated into each strategist agent for contextually relevant content.

---

## Architecture

### Agent Tree

```
root_agent (Router, gemini-2.5-flash)
├── content_orchestrator (16+ tools: 6 memory + 1 behavior + 9 strategist AgentTools)
│   ├── instagram_strategist   (idea + image + hashtag + trends + behavior)
│   ├── facebook_strategist    (idea + image + trends + behavior)
│   ├── x_strategist           (idea + image + trends + search + behavior)
│   ├── tiktok_strategist      (idea + video + audio + trends + behavior)
│   ├── linkedin_strategist    (idea + image + trends + behavior)
│   ├── youtube_strategist     (idea + image + video + audio + trends + keyword + behavior)
│   ├── pinterest_strategist   (idea + image + trends + behavior)
│   ├── threads_strategist     (idea + image + behavior)
│   └── kakao_strategist       (idea + image + trends + behavior)
│
└── general_chat_agent (22+ tools: memory + trends + AgentTool(memory_agent))
    └── memory_agent (25 memory tools)
```

### Memory System

```
Core Memory (always injected into context via Python callback)
├── Human Block     — user info, handles, industry, target platforms
├── Persona Block   — brand voice, tone, styles, hashtags, content pillars
├── Domain Block    — industry-specific strategy (10 fields + knowledge[])
└── Audience Block  — AudienceSegment[] (20 cap) with AudienceTrait[] (30/segment)

Archival Memory (metadata injected; full data accessed via tool calls)
├── campaign_archive      — CampaignRecord[] (SQLite 50 cap + Qdrant unlimited)
├── conversation_archive  — ConversationRecord[] (SQLite 100 cap + Qdrant unlimited)
├── asset_archive         — GeneratedAsset[] (200 cap)
└── behavior_graph        — nodes + edges + aggregated insights

Recall Memory (hierarchical summary)
├── recall_log            — auto-appended user/agent turns
├── L1: working_summary   — 2,500 chars, LLM-compressed
├── L2: session_summaries  — max 10 session-level summaries
└── L3: long_term_summary  — 3,000 chars, long-term compressed
```

### 7-Step Orchestrator Workflow

0. **Re-entry detection** — Check recall_log for pending approval
1. **Channel parsing** — Extract target channels from user request
2. **Memory retrieval** — Single query for core profile (4-Block), campaigns, behavior, assets, audience segments
3. **Channel brief generation** — Build `_channel_brief` with conversation context + NLU signals
4. **Plan presentation** — Present plan and wait for user approval (intentional 2-turn confirmation)
5. **Strategist delegation** — Parallel invocation of channel strategists
6. **Campaign archival** — Store generated campaigns
7. **Result aggregation** — Unified JSON response (`agent_response`, `is_updated`, `channels{}`)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | Google Gemini 2.5 Flash |
| Agent Framework | Google ADK (Agent Development Kit) >= 1.4.1 |
| Backend | FastAPI >= 0.115.12, Python 3.12+ |
| Frontend | React 19, TypeScript, TailwindCSS v4, Vite |
| Vector Database | Qdrant (Docker, port 6333) |
| Session Storage | SQLite (ADK `DatabaseSessionService`) |
| Auth Storage | SQLite (`auth.db`), bcrypt + SHA-256 legacy fallback |
| Image Generation | Imagen 3.0 (channel-specific configs) |
| Video Generation | Veo 2.0 |
| Audio Generation | Google Cloud TTS Chirp3-HD (en, es) |
| Media Storage | Google Cloud Storage |
| Embedding | `text-embedding-004` (768-dim) |
| Video Processing | MoviePy + FFmpeg |
| Container | Docker (Python 3.13-slim + FFmpeg), Docker Compose |

---

## Project Structure

```
SocialMediaBrandingAgent/
├── agents/
│   ├── src/
│   │   ├── main.py                          # FastAPI entry point, ADK integration, Auth/Memory/Session APIs
│   │   └── agents/
│   │       ├── agent.py                     # Root agent, callbacks (auto archival/retrieval), NLU
│   │       ├── prompt.py                    # Prompt templates (Router, General Chat, etc.)
│   │       ├── schemas.py                   # Pydantic models (4-Block Core, AudienceSegment, etc.)
│   │       ├── memory_tools.py              # 25+ memory tools, context block builder, embedding/vector search
│   │       ├── channel_spec.py              # 9-channel ChannelSpec definitions
│   │       ├── channel_trends.py            # 10 trend tool functions
│   │       ├── twitter_tools.py             # X/Twitter API tools
│   │       ├── video_editing_tools.py       # MoviePy video+audio assembly, GCS upload
│   │       ├── utils/
│   │       │   └── gcs_url_converters.py    # GCS URL conversion utilities
│   │       └── sub_agents/
│   │           ├── orchestrator/agent.py    # Content orchestrator (9 strategist delegation)
│   │           ├── channels/factory.py      # Channel strategist factory (STRATEGIST_REGISTRY)
│   │           ├── image_generation/agent.py  # Imagen 3.0 + image analysis
│   │           ├── video_generation/agent.py  # Veo 2.0 + video assembly
│   │           ├── audio_generation/agent.py  # TTS (Chirp3-HD)
│   │           ├── idea_generation/agent.py   # Idea generation + search
│   │           └── memory/agent.py            # Memory management agent (25 tools)
│   ├── tests/
│   │   └── test_context_block.py            # Context block builder tests
│   ├── pyproject.toml                       # Poetry config, dependencies
│   ├── Dockerfile                           # Python 3.13-slim + FFmpeg
│   └── docker-compose.yml                   # App + Qdrant services
│
└── frontend/
    ├── src/
    │   ├── App.tsx                           # Main application component
    │   ├── main.tsx                          # Entry point
    │   ├── api.tsx                           # Backend API client
    │   ├── auth.ts                           # Authentication utilities
    │   ├── memory.ts                         # Memory state management
    │   ├── base.tsx                          # Base types and interfaces
    │   ├── AuthContext.tsx                   # Auth context provider
    │   ├── pages/
    │   │   ├── landing_page.tsx             # Landing page
    │   │   ├── login_page.tsx               # Login page
    │   │   └── main_page.tsx                # Main chat + artifact view
    │   └── components/
    │       ├── ChatInterface.tsx             # Chat with SSE streaming
    │       ├── AppSidebar.tsx                # Session sidebar
    │       ├── artifact_blocks.tsx           # SSE artifact parser (9 channels)
    │       ├── context_blocks.tsx            # Memory context display
    │       ├── tool_bar.tsx                  # Tool execution indicator
    │       ├── MemoryMapView.tsx             # 4-tab memory profile viewer
    │       ├── MemoryMindMap.tsx             # Memory mind map visualization
    │       ├── ConversationHistoryTab.tsx    # Conversation history browser
    │       ├── CreationsTab.tsx              # Asset gallery
    │       └── blocks/
    │           ├── profile_block.tsx         # User profile display
    │           ├── audience_block.tsx        # Audience segment manager
    │           ├── BehaviorGraphBlock.tsx    # Behavior graph visualization
    │           ├── CampaignHistoryBlock.tsx  # Campaign history with performance
    │           ├── performance_chart.tsx     # Performance charts (Recharts)
    │           ├── instagram_post_block.tsx  # Instagram preview
    │           ├── facebook_post_block.tsx   # Facebook preview
    │           ├── twitter_post_block.tsx    # X/Twitter preview
    │           ├── tiktok_post_block.tsx     # TikTok preview
    │           ├── linkedin_post_block.tsx   # LinkedIn preview
    │           ├── youtube_post_block.tsx    # YouTube preview
    │           ├── pinterest_post_block.tsx  # Pinterest preview
    │           ├── threads_post_block.tsx    # Threads preview
    │           ├── kakao_post_block.tsx      # Kakao preview
    │           └── ...                      # Additional content blocks
    ├── package.json
    └── vite.config.ts
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose (for Qdrant vector database)
- Google Cloud Project with the following enabled:
  - Generative AI API (Gemini)
  - Cloud Storage
  - Cloud Text-to-Speech
  - Imagen API

### Environment Variables

Create an `.env` file in the `agents/` directory:

```env
# Google AI
GOOGLE_API_KEY=your-google-api-key-here
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Google Cloud Storage
GCS_BUCKET_NAME=your-gcs-bucket-name

# Qdrant (default for Docker Compose)
QDRANT_URL=http://localhost:6333

# X/Twitter API (optional, for X strategist)
X_BEARER_TOKEN=your-x-bearer-token-here
```

> **Warning:** Never commit actual API keys to version control. All values above are placeholders.

### Running

#### Option 1: Docker Compose (Recommended)

```bash
cd SocialMediaBrandingAgent/agents

# Start both the application and Qdrant
docker compose up --build
```

This starts:
- **App** on `http://localhost:8080`
- **Qdrant** on `http://localhost:6333`

#### Option 2: Manual Setup

**1. Start Qdrant**

```bash
docker run -d -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

**2. Backend**

```bash
cd SocialMediaBrandingAgent/agents

# Install dependencies
pip install poetry
poetry install

# Run the server
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8080
```

**3. Frontend**

```bash
cd SocialMediaBrandingAgent/frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

### Access URLs

| Service | URL |
|---------|-----|
| Frontend (dev) | `http://localhost:5173` |
| Backend API | `http://localhost:8080` |
| ADK Web UI | `http://localhost:8080/dev-ui` |
| Qdrant Dashboard | `http://localhost:6333/dashboard` |

---

## How It Differs from MemGPT

| Aspect | MemGPT | SocialMemAgent |
|--------|--------|----------------|
| Core Memory | 2-Block (Human + Persona) | **4-Block** (+ Domain + Audience) |
| Archival Save | Agent decides when to save | **Automatic** every turn (callback-based) |
| Archival Search | Agent decides when to search | **Automatic** every turn + on-demand agent search |
| Recall Compression | Single summary | **L1/L2/L3** hierarchical pyramid |
| Performance Learning | None | **Behavior Graph** with feedback loop |
| Audience Modeling | None | **AudienceSegment** with flexible Traits (20 segments, 30 traits each) |
| Multi-Agent | Single agent | **1 router + 1 orchestrator + 9 channel strategists + 4 generators + 1 memory agent** |
| Content Generation | None | Text + Image (Imagen 3.0) + Video (Veo 2.0) + Audio (Chirp3-HD TTS) |
| Vector Search | Agent-initiated | **2-path**: Qdrant ANN + keyword fallback, with health monitoring |
| Domain Awareness | General-purpose | **Industry-specific** strategies (cafe, salon, restaurant, etc.) |

---

## Agent Structure

```
root_agent (Router — routes to content creation or general chat)
│   Model: gemini-2.5-flash
│   Callbacks: _inject_core_memory, _tool_heartbeat, _auto_save_working_summary
│
├── content_orchestrator
│   Role: Retrieves memory once, builds channel brief with NLU signals,
│         presents plan for user approval, delegates to channel strategists
│   Tools: 6 memory tools + 1 behavior tool + 9 strategist AgentTools
│   │
│   ├── instagram_strategist  → output_key: "instagram_output"
│   ├── facebook_strategist   → output_key: "facebook_output"
│   ├── x_strategist          → output_key: "x_output"
│   ├── tiktok_strategist     → output_key: "tiktok_output"
│   ├── linkedin_strategist   → output_key: "linkedin_output"
│   ├── youtube_strategist    → output_key: "youtube_output"
│   ├── pinterest_strategist  → output_key: "pinterest_output"
│   ├── threads_strategist    → output_key: "threads_output"
│   └── kakao_strategist      → output_key: "kakao_output"
│
└── general_chat_agent
    Role: Handles non-content requests (memory queries, profile updates, general Q&A)
    Tools: 22+ tools (memory + trends + AgentTool(memory_agent))
    │
    └── memory_agent
        Role: Dedicated memory management (25 tools for CRUD on all memory blocks)
        output_key: "memory_agent_output"
```

---

## Memory Architecture

### 4-Block Core Memory (Always in Context)

| Block | Contents | Char Limit |
|-------|----------|------------|
| **Human Block** | `display_name`, `handles`, `industry`, `target_platforms`, user preferences | 5,000 |
| **Persona Block** | `tone`, `preferred_styles`, `avoid_topics`, `signature_hashtags`, `content_pillars` | 5,000 |
| **Domain Block** | Industry-specific strategy (10 fields), `knowledge[]` (max 50), `domain_extra` | 3,000 |
| **Audience Block** | `AudienceSegment[]` (20 cap), each with `AudienceTrait[]` (30 cap) | Dynamic |

### Hierarchical Recall (L1/L2/L3)

| Level | Description | Limit |
|-------|-------------|-------|
| **L1** | Working summary — compressed from recent turns by Gemini 2.5 Flash | 2,500 chars |
| **L2** | Session summaries — carried over from completed sessions | Max 10 entries |
| **L3** | Long-term summary — compressed from L2 overflow | 3,000 chars |

### Vector Storage (Qdrant)

| Collection | Dimensions | Distance | Purpose |
|------------|-----------|----------|---------|
| `campaigns` | 768 | Cosine | Semantic campaign search (goal + guideline + performance) |
| `conversations` | 768 | Cosine | Past conversation retrieval (content + summary) |

- **Embedding model:** `text-embedding-004` (Google)
- **Point IDs:** Deterministic `uuid5(NAMESPACE_DNS, "campaign_{id}")`
- **Re-embedding:** Triggered on performance data collection
- **Health monitoring:** `_QDRANT_HEALTHY` flag with automatic keyword fallback on failure

### Context Window Budget

- **Total budget:** 50,000 characters
- **Assembly order:** Core (4-Block, never trimmed) -> Audience -> Behavior -> Trend -> Recall (L1/L2/L3) -> Archival -> Proactive Suggestions -> Pending
- **Compression trigger:** 400 turns

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/signup` | Register a new user |
| `POST` | `/auth/login` | Login (returns userId) |
| `GET` | `/auth/me/{user_id}` | Get user profile |
| `GET` | `/memory/{user_id}` | Get full memory state (4-Block Core + Archival + Recall + Behavior) |
| `PUT` | `/memory/{user_id}` | Update memory (merge), with behavior graph update + Qdrant re-embed |
| `PATCH` | `/memory/{user_id}` | Partial memory update |
| `GET` | `/memory/{user_id}/conversations` | Get conversation archive |
| `GET` | `/memory/{user_id}/assets/*` | Get generated assets |
| `POST` | `/memory/{user_id}/assets/*` | Add generated asset |
| `DELETE` | `/memory/{user_id}/assets/*` | Delete generated asset |
| `PUT` | `/memory/{user_id}/performance` | Submit performance data (behavior graph + Qdrant re-embed + pending removal) |
| `GET` | `/memory/{user_id}/campaigns` | Get campaign archive |
| `POST` | `/sessions/create/{user_id}` | Create a new conversation session (copies memory from persistent session) |
| `POST` | `/sessions/sync/{user_id}/{session_id}` | Sync conversation session back to persistent memory |
| `POST` | `/run_sse` | Send message and receive response via SSE streaming |

---

## Research Context

This project is a **master's thesis research project** exploring how MemGPT-style long-term memory can be extended for domain-specific hyper-personalization in marketing.

### Research Motivation

Existing marketing AI tools operate within single sessions, losing all context about the user, their brand, and past campaign performance once the conversation ends. MemGPT demonstrated that LLMs can maintain persistent memory through an OS-inspired virtual memory hierarchy, but its general-purpose design lacks the domain-specific structures needed for effective marketing personalization.

### Approach

- **Base architecture:** MemGPT's 3-tier memory (Core, Recall, Archival)
- **Extensions:** 4-Block Core Memory, Audience Behavior Graph, Hierarchical Summary, Auto Archival/Retrieval
- **Implementation:** Google ADK multi-agent system with 9 channel-specific strategist agents
- **Evaluation dimensions:** Personalization accuracy, memory utilization rate, campaign quality improvement over time

---

## License

MIT

---

## References

- **MemGPT: Towards LLMs as Operating Systems** — Packer, C., Fang, V., Patil, S. G., Lin, K., Wooders, S., & Gonzalez, J. E. (2023). *arXiv preprint arXiv:2310.08560.*
- **Letta** — Production platform extending MemGPT. [https://github.com/letta-ai/letta](https://github.com/letta-ai/letta)
- **Google Agent Development Kit (ADK)** — [https://google.github.io/adk-docs/](https://google.github.io/adk-docs/)
- **Qdrant Vector Database** — [https://qdrant.tech/](https://qdrant.tech/)
- **Google Imagen 3.0** — Image generation model
- **Google Veo 2.0** — Video generation model
- **Google Chirp3-HD** — Text-to-Speech model
