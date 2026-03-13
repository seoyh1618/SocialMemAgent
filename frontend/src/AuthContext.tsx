import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { getCurrentUser, login, logout, signup } from './auth';
import type { AuthUser, LoginParams, SignupParams, AuthResult } from './auth';

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  doLogin: (params: LoginParams) => Promise<AuthResult>;
  doSignup: (params: SignupParams) => Promise<AuthResult>;
  doLogout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => getCurrentUser());

  const doLogin = useCallback(async (params: LoginParams): Promise<AuthResult> => {
    const result = await login(params);
    if (result.ok) setUser(result.user);
    return result;
  }, []);

  const doSignup = useCallback(async (params: SignupParams): Promise<AuthResult> => {
    const result = await signup(params);
    if (result.ok) setUser(result.user);
    return result;
  }, []);

  const doLogout = useCallback(() => {
    logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, doLogin, doSignup, doLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
