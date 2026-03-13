import { useState } from 'react';
import { useAuth } from '../AuthContext';
import { SparklesIcon, XMarkIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';

interface LoginModalProps {
  onClose: () => void;
  defaultTab?: 'login' | 'signup';
}

export default function LoginModal({ onClose, defaultTab = 'login' }: LoginModalProps) {
  const { doLogin, doSignup } = useAuth();
  const [tab, setTab] = useState<'login' | 'signup'>(defaultTab);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Login form
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });

  // Signup form
  const [signupForm, setSignupForm] = useState({
    username: '',
    email: '',
    password: '',
    displayName: '',
  });

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    const result = await doLogin(loginForm);
    setIsLoading(false);
    if (result.ok) {
      onClose();
    } else {
      setError(result.error);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    const result = await doSignup(signupForm);
    setIsLoading(false);
    if (result.ok) {
      onClose();
    } else {
      setError(result.error);
    }
  };

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="relative w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden">
        {/* Header gradient */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-8 text-white">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
          >
            <XMarkIcon className="w-4 h-4 text-white" />
          </button>

          <div className="flex items-center gap-3 mb-1">
            <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
              <SparklesIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold">Social Media Agent</span>
          </div>
          <p className="text-sm text-indigo-200 ml-12">
            {tab === 'login'
              ? '로그인하여 나만의 브랜드 메모리를 시작하세요'
              : '가입하고 개인화된 AI 브랜딩을 경험하세요'}
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-gray-100">
          <button
            onClick={() => { setTab('login'); setError(''); }}
            className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${
              tab === 'login'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            로그인
          </button>
          <button
            onClick={() => { setTab('signup'); setError(''); }}
            className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${
              tab === 'signup'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            회원가입
          </button>
        </div>

        <div className="px-6 py-6">
          {/* Error message */}
          {error && (
            <div className="mb-4 px-4 py-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
              {error}
            </div>
          )}

          {/* ─── Login Form ─── */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">아이디</label>
                <input
                  type="text"
                  value={loginForm.username}
                  onChange={e => setLoginForm(p => ({ ...p, username: e.target.value }))}
                  placeholder="아이디를 입력하세요"
                  required
                  autoFocus
                  className="w-full px-4 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">비밀번호</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={loginForm.password}
                    onChange={e => setLoginForm(p => ({ ...p, password: e.target.value }))}
                    placeholder="비밀번호를 입력하세요"
                    required
                    className="w-full px-4 py-3 pr-11 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-sm font-semibold rounded-xl hover:from-indigo-700 hover:to-purple-700 transition-all disabled:opacity-50 shadow-sm mt-2"
              >
                {isLoading ? '로그인 중...' : '로그인'}
              </button>

              <p className="text-center text-xs text-gray-400 pt-1">
                계정이 없으신가요?{' '}
                <button type="button" onClick={() => setTab('signup')} className="text-indigo-500 font-medium hover:underline">
                  회원가입
                </button>
              </p>
            </form>
          )}

          {/* ─── Signup Form ─── */}
          {tab === 'signup' && (
            <form onSubmit={handleSignup} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">아이디 *</label>
                  <input
                    type="text"
                    value={signupForm.username}
                    onChange={e => setSignupForm(p => ({ ...p, username: e.target.value }))}
                    placeholder="영문/숫자"
                    required
                    autoFocus
                    className="w-full px-3 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">표시 이름</label>
                  <input
                    type="text"
                    value={signupForm.displayName}
                    onChange={e => setSignupForm(p => ({ ...p, displayName: e.target.value }))}
                    placeholder="브랜드명 등"
                    className="w-full px-3 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">이메일 *</label>
                <input
                  type="email"
                  value={signupForm.email}
                  onChange={e => setSignupForm(p => ({ ...p, email: e.target.value }))}
                  placeholder="이메일 주소"
                  required
                  className="w-full px-4 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">비밀번호 * (6자 이상)</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={signupForm.password}
                    onChange={e => setSignupForm(p => ({ ...p, password: e.target.value }))}
                    placeholder="6자 이상"
                    required
                    className="w-full px-4 py-3 pr-11 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 bg-gray-50 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-sm font-semibold rounded-xl hover:from-indigo-700 hover:to-purple-700 transition-all disabled:opacity-50 shadow-sm mt-2"
              >
                {isLoading ? '가입 중...' : '회원가입'}
              </button>

              <p className="text-center text-xs text-gray-400 pt-1">
                이미 계정이 있으신가요?{' '}
                <button type="button" onClick={() => setTab('login')} className="text-indigo-500 font-medium hover:underline">
                  로그인
                </button>
              </p>
            </form>
          )}
        </div>

        {/* Footer note */}
        <div className="px-6 pb-5 text-center">
          <p className="text-[10px] text-gray-300">
            가입하면 브랜드 메모리가 영구적으로 저장됩니다
          </p>
        </div>
      </div>
    </div>
  );
}
