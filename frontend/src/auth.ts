/**
 * Auth layer — 백엔드 /auth/* API 연동.
 * localStorage를 세션 캐시로 사용하여 페이지 새로고침 후에도 로그인 유지.
 * 각 사용자의 userId가 MemGPT 메모리 키로 사용되어 완전히 분리된 메모리를 가짐.
 */

const API_BASE_URL = "http://localhost:8080";
const STORAGE_KEY = "smb_auth_user";

export interface AuthUser {
  userId: string;       // "u_{username}" — MemGPT 메모리 키
  username: string;
  email: string;
  displayName: string;
  avatarUrl?: string;
  createdAt: string;
}

export interface SignupParams {
  username: string;
  email: string;
  password: string;
  displayName?: string;
}

export interface LoginParams {
  username: string;
  password: string;
}

export type AuthResult =
  | { ok: true; user: AuthUser }
  | { ok: false; error: string };

// ─── Session helpers ─────────────────────────────────────────────────

export function getCurrentUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

function persistSession(user: AuthUser) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

export function logout() {
  localStorage.removeItem(STORAGE_KEY);
}

// ─── API calls ───────────────────────────────────────────────────────

export async function signup({ username, email, password, displayName }: SignupParams): Promise<AuthResult> {
  // Client-side validation (mirrors backend)
  const trimUser = username.trim().toLowerCase();
  if (trimUser.length < 2) return { ok: false, error: "아이디는 2자 이상이어야 합니다." };
  if (!/^[a-z0-9_]+$/.test(trimUser)) return { ok: false, error: "아이디는 영문 소문자, 숫자, 언더스코어만 허용됩니다." };
  if (!email.includes("@")) return { ok: false, error: "유효한 이메일을 입력해주세요." };
  if (password.length < 6) return { ok: false, error: "비밀번호는 6자 이상이어야 합니다." };

  try {
    const res = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: trimUser, email: email.trim().toLowerCase(), password, display_name: displayName }),
    });

    if (!res.ok) {
      const err = await res.json();
      return { ok: false, error: err.detail || "회원가입에 실패했습니다." };
    }

    const data = await res.json();
    const user: AuthUser = {
      userId: data.userId,
      username: data.username,
      email: data.email,
      displayName: data.displayName,
      avatarUrl: data.avatarUrl,
      createdAt: data.createdAt,
    };
    persistSession(user);
    return { ok: true, user };
  } catch (e) {
    return { ok: false, error: "서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해주세요." };
  }
}

export async function login({ username, password }: LoginParams): Promise<AuthResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.trim().toLowerCase(), password }),
    });

    if (!res.ok) {
      const err = await res.json();
      return { ok: false, error: err.detail || "로그인에 실패했습니다." };
    }

    const data = await res.json();
    const user: AuthUser = {
      userId: data.userId,
      username: data.username,
      email: data.email,
      displayName: data.displayName,
      avatarUrl: data.avatarUrl,
      createdAt: data.createdAt,
    };
    persistSession(user);
    return { ok: true, user };
  } catch (e) {
    return { ok: false, error: "서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해주세요." };
  }
}
