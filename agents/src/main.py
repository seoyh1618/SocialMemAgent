import asyncio
import logging

# ——— Enable ADK debug ———
# logging.basicConfig(level=logging.DEBUG)

# Suppress noisy OpenTelemetry context detach warnings (ADK async generator issue)
logging.getLogger("opentelemetry.context").setLevel(logging.ERROR)

# Load .env from agents root or src/agents/ — must run before any google SDK import
import os
from pathlib import Path
_env_candidates = [
    Path(__file__).parent.parent / ".env",           # agents/.env
    Path(__file__).parent / "agents" / ".env",       # agents/src/agents/.env
]
for _env_path in _env_candidates:
    if _env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(_env_path)
        break

import bcrypt
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.sessions import DatabaseSessionService
from google.cloud import storage as gcs_storage

# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Example session DB URL (e.g., SQLite)
SESSION_DB_URL = "sqlite+aiosqlite:///./sessions.db"
# Example allowed origins for CORS
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
# Set web=True if you intend to serve a web interface, False otherwise
SERVE_WEB_INTERFACE = True

# Call the function to get the FastAPI app instance
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_DB_URL,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)

# ─── Auth DB (SQLite — lightweight user registry) ────────────────────
AUTH_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")

def _init_auth_db():
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            avatar_url TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

_init_auth_db()

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _check_password(password: str, hashed: str) -> bool:
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return bcrypt.checkpw(password.encode(), hashed.encode())
    # Legacy SHA-256 fallback for existing users
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest() == hashed

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthUserResponse(BaseModel):
    userId: str
    username: str
    email: str
    displayName: str
    avatarUrl: Optional[str] = None
    createdAt: str


class MemoryStatePatch(BaseModel):
    model_config = {"extra": "ignore"}
    core_profile: Optional[dict] = None  # Legacy — triggers migration via model_validator
    human_block: Optional[dict] = None
    persona_block: Optional[dict] = None
    domain_block: Optional[dict] = None
    audience_block: Optional[dict] = None
    campaign_archive: Optional[list] = None
    conversation_archive: Optional[list] = None
    asset_archive: Optional[list] = None
    recall_log: Optional[list] = None
    working_summary: Optional[str] = None
    behavior_graph: Optional[dict] = None
    performance_pending: Optional[list] = None
    total_campaigns: Optional[int] = None
    last_updated: Optional[str] = None


@app.post("/auth/signup")
async def auth_signup(req: SignupRequest):
    """Register a new user. Returns the user profile on success."""
    username = req.username.strip().lower()
    email = req.email.strip().lower()
    display_name = (req.display_name or username).strip()

    if len(username) < 2:
        raise HTTPException(status_code=400, detail="아이디는 2자 이상이어야 합니다.")
    if not all(c.isalnum() or c == '_' for c in username):
        raise HTTPException(status_code=400, detail="아이디는 영문 소문자, 숫자, 언더스코어만 허용됩니다.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="유효한 이메일을 입력해주세요.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")

    user_id = f"u_{username}"
    avatar_url = f"https://api.dicebear.com/7.x/initials/svg?seed={display_name}&backgroundColor=6366f1"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        conn = sqlite3.connect(AUTH_DB_PATH)
        conn.execute(
            "INSERT INTO users (user_id, username, email, password_hash, display_name, avatar_url, created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, username, email, _hash_password(req.password), display_name, avatar_url, created_at),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디 또는 이메일입니다.")

    return JSONResponse(content={
        "userId": user_id, "username": username, "email": email,
        "displayName": display_name, "avatarUrl": avatar_url, "createdAt": created_at,
    })

@app.post("/auth/login")
async def auth_login(req: LoginRequest):
    """Authenticate a user. Returns the user profile on success."""
    username = req.username.strip().lower()
    conn = sqlite3.connect(AUTH_DB_PATH)
    row = conn.execute(
        "SELECT user_id, username, email, password_hash, display_name, avatar_url, created_at FROM users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="존재하지 않는 아이디입니다.")
    if not _check_password(req.password, row[3]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    return JSONResponse(content={
        "userId": row[0], "username": row[1], "email": row[2],
        "displayName": row[4], "avatarUrl": row[5], "createdAt": row[6],
    })

@app.get("/auth/me/{user_id}")
async def auth_me(user_id: str):
    """Get user profile by user_id."""
    conn = sqlite3.connect(AUTH_DB_PATH)
    row = conn.execute(
        "SELECT user_id, username, email, display_name, avatar_url, created_at FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return JSONResponse(content={
        "userId": row[0], "username": row[1], "email": row[2],
        "displayName": row[3], "avatarUrl": row[4], "createdAt": row[5],
    })

# ─── MemGPT Memory API Endpoints ─────────────────────────────────────
# These endpoints provide direct access to the MemoryState stored in
# ADK session.state['memory'] for a given user, keyed by a dedicated
# "memory" session (session_id = "memory_{user_id}").

_APP_NAME = "agents"
_MEMORY_SESSION_PREFIX = "memory_"
_MEMORY_KEY = "memory"


logger = logging.getLogger(__name__)

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in _SESSION_LOCKS:
        _SESSION_LOCKS[user_id] = asyncio.Lock()
    return _SESSION_LOCKS[user_id]


def _get_session_service() -> DatabaseSessionService:
    return DatabaseSessionService(db_url=SESSION_DB_URL)


def _memory_session_id(user_id: str) -> str:
    return f"{_MEMORY_SESSION_PREFIX}{user_id}"


@app.get("/memory/{user_id}")
async def get_memory(user_id: str):
    """
    [MemGPT API] Read the full MemoryState for a user.
    Returns the Core Memory (profile + brand voice), Archival Memory (campaigns),
    and Recall Memory (working summary).
    """
    try:
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            # Return default empty memory
            from agents.schemas import MemoryState
            return JSONResponse(content={"user_id": user_id, "memory": MemoryState().model_dump(mode="json")})

        raw_memory = session.state.get(_MEMORY_KEY, {})
        return JSONResponse(content={"user_id": user_id, "memory": raw_memory})
    except Exception:
        logger.exception("get_memory failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/memory/{user_id}")
async def update_memory(user_id: str, memory_data: dict):
    """
    [MemGPT API] Merge-update the MemoryState for a user.
    Used by the frontend ProfileBlock to persist profile edits.

    MERGE strategy (not overwrite):
    - Loads existing memory from the persistent session
    - Deep-merges the incoming fields ONLY for fields present in memory_data
    - Preserves agent-managed fields (recall_log, behavior_graph) that the
      frontend MemoryState type does not include — preventing data loss on save.
    """
    try:
        from agents.schemas import MemoryState

        svc = _get_session_service()
        session_id = _memory_session_id(user_id)

        async with _get_user_lock(user_id):
            # Load existing memory to merge into
            session = await svc.get_session(
                app_name=_APP_NAME, user_id=user_id, session_id=session_id
            )
            if session is not None:
                existing_raw = session.state.get(_MEMORY_KEY, {})
                if isinstance(existing_raw, dict):
                    # Merge: incoming fields override, agent-managed fields preserved
                    merged_raw = {**existing_raw, **memory_data}
                else:
                    merged_raw = memory_data
            else:
                merged_raw = memory_data

            # Validate merged result against schema
            validated = MemoryState.model_validate(merged_raw)
            new_state = {_MEMORY_KEY: validated.model_dump(mode="json")}

            if session is None:
                await svc.create_session(
                    app_name=_APP_NAME,
                    user_id=user_id,
                    session_id=session_id,
                    state=new_state,
                )
            else:
                await svc.delete_session(
                    app_name=_APP_NAME, user_id=user_id, session_id=session_id
                )
                await svc.create_session(
                    app_name=_APP_NAME,
                    user_id=user_id,
                    session_id=session_id,
                    state=new_state,
                )

        return JSONResponse(content={"status": "ok", "user_id": user_id})
    except Exception:
        logger.exception("update_memory failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.patch("/memory/{user_id}")
async def patch_memory(user_id: str, patch: MemoryStatePatch):
    async with _get_user_lock(user_id):
        try:
            from agents.schemas import MemoryState
            svc = _get_session_service()
            session_id = _memory_session_id(user_id)
            session = await svc.get_session(
                app_name=_APP_NAME, user_id=user_id, session_id=session_id
            )
            existing_raw = session.state.get(_MEMORY_KEY, {}) if session and isinstance(session.state.get(_MEMORY_KEY), dict) else {}
            patch_data = patch.model_dump(exclude_none=True)
            merged_raw = {**existing_raw, **patch_data}
            validated = MemoryState.model_validate(merged_raw)
            new_state = {_MEMORY_KEY: validated.model_dump(mode="json")}
            if session is None:
                await svc.create_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id, state=new_state)
            else:
                await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id)
                await svc.create_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id, state=new_state)
            return JSONResponse(content={"status": "ok", "user_id": user_id})
        except Exception:
            logger.exception("patch_memory failed for user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/sessions/create/{user_id}")
async def create_session_with_memory(user_id: str):
    """
    [MemGPT API] 사용자별 영구 메모리를 새 대화 세션 state에 복사하여 세션 생성.
    프론트엔드는 ADK 기본 /apps/.../sessions 대신 이 엔드포인트를 사용해야 합니다.
    이렇게 해야 _inject_core_memory callback이 올바른 메모리를 읽습니다.
    """
    try:
        from agents.schemas import MemoryState
        svc = _get_session_service()

        # 1. 전용 메모리 세션에서 영구 메모리 로드
        memory_session_id = _memory_session_id(user_id)
        memory_session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
        )
        raw_memory = memory_session.state.get(_MEMORY_KEY, {}) if memory_session else {}

        # 2. 새 대화 세션에 메모리를 initial state로 주입하여 생성
        import uuid
        new_session_id = f"s_{uuid.uuid4().hex[:16]}"
        new_session = await svc.create_session(
            app_name=_APP_NAME,
            user_id=user_id,
            session_id=new_session_id,
            state={_MEMORY_KEY: raw_memory},
        )

        return JSONResponse(content={
            "session_id": new_session_id,
            "user_id": user_id,
            "memory_loaded": bool(raw_memory),
        })
    except Exception:
        logger.exception("create_session_with_memory failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/sessions/sync/{user_id}/{session_id}")
async def sync_session_memory_to_persistent(user_id: str, session_id: str):
    """
    [MemGPT API] 대화 세션에서 변경된 메모리를 전용 메모리 세션으로 역동기화.
    대화가 끝나거나 메모리 변경이 감지될 때 호출합니다.
    """
    try:
        logger.info("[SYNC] 🔵 Session sync | user=%s, session=%s", user_id, session_id)
        svc = _get_session_service()

        # 1. 현재 대화 세션의 메모리 읽기
        conv_session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if not conv_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        raw_memory = conv_session.state.get(_MEMORY_KEY)
        if not raw_memory:
            logger.warning("[SYNC] 🔴 No memory in conv session %s for user %s", session_id, user_id)
            return JSONResponse(content={"status": "no_memory_to_sync"})

        campaign_count = len(raw_memory.get("campaign_archive", [])) if isinstance(raw_memory, dict) else "?"
        logger.info("[SYNC] 📝 Memory loaded | campaigns=%s", campaign_count)

        # 1.5 Auto-archive recall_log entries to conversation_archive
        # This ensures no conversation data is lost when recall_log is compressed
        if isinstance(raw_memory, dict):
            recall_log = raw_memory.get("recall_log", [])
            conv_archive = raw_memory.get("conversation_archive", [])
            existing_contents = {(e.get("timestamp", ""), e.get("content", "")[:100]) for e in conv_archive}
            new_archived = 0
            for entry in recall_log:
                key = (entry.get("timestamp", ""), entry.get("content", "")[:100])
                if key not in existing_contents:
                    conv_archive.append({
                        "conversation_id": str(uuid.uuid4())[:8],
                        "timestamp": entry.get("timestamp", ""),
                        "role": entry.get("role", ""),
                        "content": entry.get("content", ""),
                        "session_id": session_id,
                        "summary": entry.get("summary_note", ""),
                    })
                    new_archived += 1
            if new_archived > 0:
                raw_memory["conversation_archive"] = conv_archive
                logger.info("[SYNC] 📝 Auto-archived %d recall entries to conversation_archive", new_archived)

        # 1.7 Hierarchical summary compression (L1→L2→L3) + Archive cap
        if isinstance(raw_memory, dict):
            try:
                from agents.schemas import MemoryState
                from agents.memory_tools import (
                    _compress_session_summary,
                    _CONVERSATION_ARCHIVE_CAP,
                    _CAMPAIGN_ARCHIVE_CAP,
                    _SESSION_SUMMARIES_CAP,
                )
                memory_obj = MemoryState.model_validate(raw_memory)

                # L1→L2→L3 계층적 요약 압축
                _compress_session_summary(memory_obj)

                # Archive cap 적용
                if len(memory_obj.conversation_archive) > _CONVERSATION_ARCHIVE_CAP:
                    memory_obj.conversation_archive = memory_obj.conversation_archive[-_CONVERSATION_ARCHIVE_CAP:]
                if len(memory_obj.campaign_archive) > _CAMPAIGN_ARCHIVE_CAP:
                    memory_obj.campaign_archive = memory_obj.campaign_archive[-_CAMPAIGN_ARCHIVE_CAP:]

                _l1_triggered = bool(memory_obj.session_summaries)
                _l2_triggered = len(memory_obj.session_summaries) > _SESSION_SUMMARIES_CAP if hasattr(memory_obj, 'session_summaries') else False
                raw_memory = memory_obj.model_dump(mode="json")
                logger.info(
                    "[SYNC] ⚡ Hierarchical compression triggered: L1→L2=%s, L2→L3=%s",
                    "yes" if _l1_triggered else "no", "yes" if _l2_triggered else "no",
                )
                _conv_cap = len(memory_obj.conversation_archive)
                _camp_cap = len(memory_obj.campaign_archive)
                logger.info(
                    "[SYNC] 📝 Archive caps applied: campaigns=%d/%d, conversations=%d/%d",
                    _camp_cap, _CAMPAIGN_ARCHIVE_CAP, _conv_cap, _CONVERSATION_ARCHIVE_CAP,
                )
            except Exception as e:
                logger.warning("[SYNC] 🔴 Hierarchical compression failed: %s — skipping.", e)

        # 2. 전용 메모리 세션에 업데이트 (asset_archive는 merge)
        memory_session_id = _memory_session_id(user_id)
        memory_session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
        )

        # Merge asset_archive: 영속 세션에 직접 업로드된 에셋이 대화 세션 sync로 사라지지 않도록
        if memory_session and isinstance(raw_memory, dict):
            persistent_memory = memory_session.state.get(_MEMORY_KEY, {})
            if isinstance(persistent_memory, dict):
                persistent_assets = persistent_memory.get("asset_archive", [])
                conv_assets = raw_memory.get("asset_archive", [])
                # Merge: 양쪽의 asset_id를 합집합으로
                conv_asset_ids = {a.get("asset_id") for a in conv_assets if isinstance(a, dict)}
                for pa in persistent_assets:
                    if isinstance(pa, dict) and pa.get("asset_id") not in conv_asset_ids:
                        conv_assets.append(pa)
                raw_memory["asset_archive"] = conv_assets

        if memory_session is not None:
            await svc.delete_session(
                app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
            )
        await svc.create_session(
            app_name=_APP_NAME,
            user_id=user_id,
            session_id=memory_session_id,
            state={_MEMORY_KEY: raw_memory},
        )

        logger.info("[SYNC] 🟢 Sync complete")
        return JSONResponse(content={"status": "ok", "synced": True})
    except HTTPException:
        raise
    except Exception:
        logger.exception("[SYNC] 🔴 sync_session_memory_to_persistent failed for user_id=%s session_id=%s", user_id, session_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/memory/{user_id}/conversations")
async def get_conversations(user_id: str, limit: int = 30, page: int = 0):
    """
    [MemGPT API] List conversation history combining recall_log (recent) and
    conversation_archive (older/archived). Returns turns in reverse-chronological order.
    Includes working_summary as context.
    """
    try:
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            return JSONResponse(content={
                "conversations": [], "total": 0, "page": page, "limit": limit,
                "working_summary": "",
            })

        raw_memory = session.state.get(_MEMORY_KEY, {})

        # Combine recall_log (recent) + conversation_archive (older)
        recall_log = raw_memory.get("recall_log", [])
        conversation_archive = raw_memory.get("conversation_archive", [])
        working_summary = raw_memory.get("working_summary", "")

        # Merge and deduplicate by content+timestamp
        all_turns = []
        seen = set()

        for entry in recall_log:
            key = (entry.get("timestamp", ""), entry.get("role", ""), entry.get("content", "")[:100])
            if key not in seen:
                seen.add(key)
                all_turns.append({
                    "timestamp": entry.get("timestamp", ""),
                    "role": entry.get("role", ""),
                    "content": entry.get("content", ""),
                    "summary_note": entry.get("summary_note", ""),
                    "source": "recall",
                })

        for entry in conversation_archive:
            key = (entry.get("timestamp", ""), entry.get("role", ""), entry.get("content", "")[:100])
            if key not in seen:
                seen.add(key)
                all_turns.append({
                    "timestamp": entry.get("timestamp", ""),
                    "role": entry.get("role", ""),
                    "content": entry.get("content", ""),
                    "summary": entry.get("summary", ""),
                    "session_id": entry.get("session_id", ""),
                    "source": "archive",
                })

        # Sort by timestamp descending (most recent first)
        all_turns.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        total = len(all_turns)
        offset = page * limit
        paged = all_turns[offset : offset + limit]

        return JSONResponse(content={
            "conversations": paged,
            "total": total,
            "page": page,
            "limit": limit,
            "working_summary": working_summary,
        })
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_conversations failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/memory/{user_id}/assets")
async def get_assets(user_id: str, limit: int = 20, page: int = 0, asset_type: str = None):
    """
    [MemGPT API] List generated assets (images & videos) from Asset Archive with pagination.
    page: 0-indexed page number. Returns assets in reverse-chronological order (most recent first).
    asset_type: optional filter — 'image' or 'video'.
    """
    try:
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            return JSONResponse(content={"assets": [], "total": 0, "page": page, "limit": limit})

        raw_memory = session.state.get(_MEMORY_KEY, {})
        assets = raw_memory.get("asset_archive", [])
        # Optional type filter
        if asset_type:
            assets = [a for a in assets if a.get("asset_type") == asset_type]
        # Most recent first
        reversed_assets = list(reversed(assets))
        offset = page * limit
        paged = reversed_assets[offset : offset + limit]
        return JSONResponse(content={
            "assets": paged,
            "total": len(assets),
            "page": page,
            "limit": limit,
        })
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_assets failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/memory/{user_id}/assets/upload")
async def upload_user_asset(
    user_id: str,
    file: UploadFile = File(...),
    platform: str = "",
):
    """
    Upload a user image to GCS and record it in the user's asset_archive.
    Returns the new GeneratedAsset record.
    """
    from agents.schemas import GeneratedAsset, MemoryState
    svc = _get_session_service()
    try:
        # Read file content
        content = await file.read()
        asset_id = str(uuid.uuid4())
        filename = file.filename or f"upload_{asset_id}.png"
        gcs_path = f"images/{asset_id}_{filename}"

        # Upload to GCS (fallback to local URL if credentials unavailable)
        try:
            gcs_client = gcs_storage.Client()
            bucket = gcs_client.bucket("social-media-agent-assets")
            blob = bucket.blob(gcs_path)
            blob.upload_from_string(content, content_type=file.content_type or "image/png")
            blob.make_public()
            gcs_url = blob.public_url
        except Exception:
            # Local dev fallback: store as base64 data URL
            import base64
            mime = file.content_type or "image/png"
            gcs_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"

        # Build new asset record
        from datetime import timezone
        new_asset = GeneratedAsset(
            asset_id=asset_id,
            asset_type="image",
            gcs_url=gcs_url,
            local_filename=filename,
            prompt_used="",
            platform=platform,
            created_at=datetime.now(timezone.utc).isoformat(),
            session_id="",
            is_user_uploaded=True,
        )

        # Load current memory and append asset
        memory_session_id = f"{_MEMORY_SESSION_PREFIX}{user_id}"
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
        )
        if session is None:
            raw_memory: dict = {}
        else:
            raw_memory = dict(session.state.get(_MEMORY_KEY, {}))

        memory = MemoryState.model_validate(raw_memory) if raw_memory else MemoryState()
        memory.asset_archive.append(new_asset)
        memory.last_updated = datetime.now(timezone.utc).isoformat()

        new_state = {_MEMORY_KEY: memory.model_dump(mode="json")}
        async with _get_user_lock(user_id):
            if session is not None:
                await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id)
            await svc.create_session(
                app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id, state=new_state
            )

        return JSONResponse(content={"asset": new_asset.model_dump(mode="json")})
    except HTTPException:
        raise
    except Exception:
        logger.exception("upload_user_asset failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/memory/{user_id}/assets/{asset_id}")
async def delete_user_asset(user_id: str, asset_id: str):
    """
    Delete an asset from the user's asset_archive by asset_id.
    Returns {"deleted": true} on success or 404 if not found.
    """
    from agents.schemas import MemoryState
    svc = _get_session_service()
    try:
        memory_session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Asset not found")

        raw_memory = dict(session.state.get(_MEMORY_KEY, {}))
        memory = MemoryState.model_validate(raw_memory) if raw_memory else MemoryState()

        original_len = len(memory.asset_archive)
        memory.asset_archive = [a for a in memory.asset_archive if a.asset_id != asset_id]
        if len(memory.asset_archive) == original_len:
            raise HTTPException(status_code=404, detail="Asset not found")

        from datetime import timezone
        memory.last_updated = datetime.now(timezone.utc).isoformat()
        new_state = {_MEMORY_KEY: memory.model_dump(mode="json")}
        async with _get_user_lock(user_id):
            await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id)
            await svc.create_session(
                app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id, state=new_state
            )
        return JSONResponse(content={"deleted": True})
    except HTTPException:
        raise
    except Exception:
        logger.exception("delete_user_asset failed for user_id=%s, asset_id=%s", user_id, asset_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/memory/{user_id}/campaigns")
async def get_campaigns(user_id: str, limit: int = 10, page: int = 0):
    """
    [MemGPT API] List campaigns from Archival Memory with pagination.
    page: 0-indexed page number. Returns campaigns[page*limit : (page+1)*limit]
    in reverse-chronological order (most recent first).

    [MemGPT bug-fix Oct 15 2023 — commit 15540c2 "fix paging bug"]
    The original MemGPT paper had a pagination bug where start=page instead of
    start=page*count. Fixed here: offset = page * limit (not just page).
    """
    try:
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            return JSONResponse(content={"campaigns": [], "total": 0, "page": page, "limit": limit})

        raw_memory = session.state.get(_MEMORY_KEY, {})
        campaigns = raw_memory.get("campaign_archive", [])
        # Most recent first — then apply page*limit offset (not raw page number)
        reversed_campaigns = list(reversed(campaigns))
        offset = page * limit  # Bug fix: was 'page', must be 'page * limit'
        paged = reversed_campaigns[offset : offset + limit]
        return JSONResponse(content={
            "campaigns": paged,
            "total": len(campaigns),
            "page": page,
            "limit": limit,
        })
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_campaigns failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/memory/{user_id}/assets/{asset_id}/performance")
async def update_asset_performance(user_id: str, asset_id: str, request: Request):
    """
    Update performance data for a specific asset in memory (asset_archive).
    Accepts partial updates — only provided fields are overwritten.
    """
    try:
        body = await request.json()
        from agents.schemas import MemoryState
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Memory session not found")

        raw_memory = session.state.get(_MEMORY_KEY, {})
        try:
            memory = MemoryState.model_validate(raw_memory)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to parse memory state")

        # Find the asset
        asset = next(
            (a for a in memory.asset_archive if a.asset_id == asset_id), None
        )
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

        # Merge performance data
        from agents.schemas import PerformanceData
        from datetime import timezone
        existing = asset.performance.model_dump() if asset.performance else {}
        existing.update({k: v for k, v in body.items() if v is not None})
        if "collected_at" not in body:
            existing["collected_at"] = datetime.now(timezone.utc).isoformat()
        asset.performance = PerformanceData.model_validate(existing)

        memory.last_updated = datetime.now(timezone.utc).isoformat()
        new_state = {_MEMORY_KEY: memory.model_dump(mode="json")}
        async with _get_user_lock(user_id):
            await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id)
            await svc.create_session(
                app_name=_APP_NAME, user_id=user_id, session_id=session_id, state=new_state
            )
        return JSONResponse(content={"updated": True, "asset_id": asset_id})
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_asset_performance failed for user_id=%s, asset_id=%s", user_id, asset_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/memory/{user_id}/campaigns/{campaign_id}/performance")
async def update_campaign_performance(user_id: str, campaign_id: str, request: Request):
    """
    Update performance data for a specific campaign in Archival Memory.
    Accepts partial updates — only provided fields are overwritten.
    """
    try:
        body = await request.json()
        _engagement = body.get("engagement_level", "")
        logger.info("[PERF_API] 🔵 Performance update | campaign=%s, engagement=%s", campaign_id, _engagement)
        from agents.schemas import MemoryState
        svc = _get_session_service()
        session_id = _memory_session_id(user_id)
        session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Memory session not found")

        raw_memory = session.state.get(_MEMORY_KEY, {})
        try:
            memory = MemoryState.model_validate(raw_memory)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to parse memory state")

        # Find the campaign
        campaign = next(
            (c for c in memory.campaign_archive if c.campaign_id == campaign_id), None
        )
        if campaign is None:
            raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

        # Merge performance data
        from agents.schemas import PerformanceData
        existing = campaign.performance.model_dump() if campaign.performance else {}
        existing.update({k: v for k, v in body.items() if v is not None})
        from datetime import timezone
        if "collected_at" not in body:
            existing["collected_at"] = datetime.now(timezone.utc).isoformat()
        campaign.performance = PerformanceData.model_validate(existing)

        # Also update performance_notes summary if numeric fields provided
        numeric_fields = ["views", "clicks", "impressions", "likes", "shares", "comments"]
        numeric_summary = ", ".join(
            f"{k}={body[k]}" for k in numeric_fields if k in body
        )
        if numeric_summary:
            campaign.performance_notes = (
                f"{campaign.performance_notes} | {numeric_summary}".strip(" |")
            )

        # ── Behavior Graph 업데이트 (시맨틱 필드가 있을 때) ──────────
        engagement = body.get("engagement_level", existing.get("engagement_level", ""))
        if engagement:
            from agents.schemas import PerformanceEdge, ContentNode
            graph = memory.behavior_graph
            for platform in campaign.platforms_used:
                style_name = campaign.selected_styles[0] if campaign.selected_styles else "general"
                node_id = f"{platform}_{style_name}"
                if not any(n.node_id == node_id for n in graph.nodes):
                    content_type = "video" if platform in ("tiktok", "youtube") else "image"
                    graph.nodes.append(ContentNode(
                        node_id=node_id, platform=platform,
                        content_type=content_type,
                        topic=campaign.target_audiences[0] if campaign.target_audiences else "",
                    ))
                # Match segment_id from campaign target_audiences
                seg_id = ""
                if campaign.target_audiences and hasattr(memory, 'audience_block'):
                    for ta in campaign.target_audiences:
                        for seg in memory.audience_block.segments:
                            if ta.lower() in seg.name.lower() or seg.name.lower() in ta.lower():
                                seg_id = seg.segment_id or seg.name
                                break
                        if seg_id:
                            break

                graph.edges.append(PerformanceEdge(
                    edge_id=f"{campaign_id}_{platform}",
                    node_id=node_id, campaign_id=campaign_id,
                    segment_id=seg_id,
                    engagement_level=engagement,
                    reach_level=body.get("reach_level", existing.get("reach_level", "")),
                    what_worked=body.get("what_worked", existing.get("what_worked", [])),
                    what_failed=body.get("what_failed", existing.get("what_failed", [])),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))
            # Recompute aggregates
            from agents.memory_tools import _recompute_graph_insights
            _recompute_graph_insights(graph)
            graph.last_updated = datetime.now(timezone.utc).isoformat()
            _new_edges = len([e for e in graph.edges if e.campaign_id == campaign_id])
            logger.info(
                "[PERF_API] ⚡ Behavior graph: %d new edges, segment_id=%s",
                _new_edges, seg_id or "none",
            )

        # ── Qdrant re-embed ──────────────────────────────────────────
        _qdrant_ok = False
        try:
            from agents.memory_tools import _embed, _qdrant_upsert, _campaign_to_embed_text, _QDRANT_CAMPAIGNS_COLLECTION
            embed_text = _campaign_to_embed_text(campaign)
            vec = _embed(embed_text)
            if vec:
                _qdrant_ok = _qdrant_upsert(
                    _QDRANT_CAMPAIGNS_COLLECTION,
                    f"campaign_{campaign_id}",
                    vec,
                    {"id": campaign_id, "goal": campaign.goal[:200],
                     "platforms": campaign.platforms_used,
                     "timestamp": campaign.timestamp},
                )
        except Exception as e:
            logger.warning("[PERF_API] 🔴 Qdrant re-embed failed for campaign %s: %s", campaign_id, e)
        logger.info("[PERF_API] ⚡ Qdrant re-embed: %s", "success" if _qdrant_ok else "fail")

        # Remove from performance_pending if present
        memory.performance_pending = [
            p for p in memory.performance_pending if p.campaign_id != campaign_id
        ]

        memory.last_updated = datetime.now(timezone.utc).isoformat()
        new_state = {_MEMORY_KEY: memory.model_dump(mode="json")}
        async with _get_user_lock(user_id):
            await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id)
            await svc.create_session(
                app_name=_APP_NAME, user_id=user_id, session_id=session_id, state=new_state
            )
        logger.info("[PERF_API] 🟢 Performance saved")
        return JSONResponse(content={"updated": True, "campaign_id": campaign_id})
    except HTTPException:
        raise
    except Exception:
        logger.exception("[PERF_API] 🔴 update_campaign_performance failed for user_id=%s, campaign_id=%s", user_id, campaign_id)
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def start():
    """Launched with `poetry run start` at root level"""
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)