import logging

# ——— Enable ADK debug ———
# logging.basicConfig(level=logging.DEBUG)

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
SESSION_DB_URL = "sqlite:///./sessions.db"
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memory/{user_id}")
async def update_memory(user_id: str, memory_data: dict):
    """
    [MemGPT API] Merge-update the MemoryState for a user.
    Used by the frontend ProfileBlock to persist profile edits.

    MERGE strategy (not overwrite):
    - Loads existing memory from the persistent session
    - Deep-merges the incoming fields ONLY for fields present in memory_data
    - Preserves agent-managed fields (recall_log, campaign_embeddings) that the
      frontend MemoryState type does not include — preventing data loss on save.
    """
    try:
        from agents.schemas import MemoryState

        svc = _get_session_service()
        session_id = _memory_session_id(user_id)

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/sync/{user_id}/{session_id}")
async def sync_session_memory_to_persistent(user_id: str, session_id: str):
    """
    [MemGPT API] 대화 세션에서 변경된 메모리를 전용 메모리 세션으로 역동기화.
    대화가 끝나거나 메모리 변경이 감지될 때 호출합니다.
    """
    try:
        svc = _get_session_service()

        # 1. 현재 대화 세션의 메모리 읽기
        conv_session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )
        if not conv_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        raw_memory = conv_session.state.get(_MEMORY_KEY)
        if not raw_memory:
            return JSONResponse(content={"status": "no_memory_to_sync"})

        # 2. 전용 메모리 세션에 업데이트
        memory_session_id = _memory_session_id(user_id)
        memory_session = await svc.get_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
        )
        if memory_session is None:
            await svc.create_session(
                app_name=_APP_NAME,
                user_id=user_id,
                session_id=memory_session_id,
                state={_MEMORY_KEY: raw_memory},
            )
        else:
            await svc.delete_session(
                app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id
            )
            await svc.create_session(
                app_name=_APP_NAME,
                user_id=user_id,
                session_id=memory_session_id,
                state={_MEMORY_KEY: raw_memory},
            )

        return JSONResponse(content={"status": "ok", "synced": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        if session is not None:
            await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id)
        await svc.create_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id, state=new_state
        )

        return JSONResponse(content={"asset": new_asset.model_dump(mode="json")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id)
        await svc.create_session(
            app_name=_APP_NAME, user_id=user_id, session_id=memory_session_id, state=new_state
        )
        return JSONResponse(content={"deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memory/{user_id}/campaigns/{campaign_id}/performance")
async def update_campaign_performance(user_id: str, campaign_id: str, request: Request):
    """
    Update performance data for a specific campaign in Archival Memory.
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

        memory.last_updated = datetime.now(timezone.utc).isoformat()
        new_state = {_MEMORY_KEY: memory.model_dump(mode="json")}
        await svc.delete_session(app_name=_APP_NAME, user_id=user_id, session_id=session_id)
        await svc.create_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id, state=new_state
        )
        return JSONResponse(content={"updated": True, "campaign_id": campaign_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def start():
    """Launched with `poetry run start` at root level"""
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)