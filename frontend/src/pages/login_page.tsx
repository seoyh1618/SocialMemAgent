import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';

const SocialIcon = ({ d }: { d: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="#3b82f6">
    <path d={d} />
  </svg>
);

const SOCIAL_ICONS = [
  // Facebook
  "M22.675 0h-21.35c-.732 0-1.325.593-1.325 1.325v21.351c0 .731.593 1.324 1.325 1.324h11.495v-9.294h-3.128v-3.622h3.128v-2.671c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.313h3.587l-.467 3.622h-3.12v9.293h6.116c.73 0 1.323-.593 1.323-1.325v-21.35c0-.732-.593-1.325-1.325-1.325z",
  // Twitter
  "M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z",
  // Instagram
  "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z",
  // YouTube
  "M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z",
  // LinkedIn
  "M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z",
];

export default function LoginPage() {
  const { doLogin, doSignup } = useAuth();
  const navigate = useNavigate();

  const [tab, setTab] = useState<'login' | 'signup'>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showOrbitals, setShowOrbitals] = useState(false);

  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [signupForm, setSignupForm] = useState({
    username: '',
    email: '',
    password: '',
    displayName: '',
  });

  useEffect(() => {
    const timer = setTimeout(() => setShowOrbitals(true), 1500);
    return () => clearTimeout(timer);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    const result = await doLogin(loginForm);
    setIsLoading(false);
    if (result.ok) {
      navigate('/');
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
      navigate('/');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4" style={{ backgroundColor: '#f5f7fa', fontFamily: "'Inter', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Condensed:wght@400;500;600;700&display=swap');
        .heading { font-family: 'IBM Plex Condensed', sans-serif; letter-spacing: -0.03em; }
        .orbit { position: relative; width: 220px; height: 220px; }
        .orbit-circle { position: absolute; border-radius: 50%; top: 0; left: 0; right: 0; bottom: 0; margin: auto; border: 1px solid rgba(59,130,246,0.2); }
        .orbit-1 { width: 220px; height: 220px; }
        .orbit-2 { width: 160px; height: 160px; }
        .orbit-3 { width: 100px; height: 100px; }
        .main-btn { position: absolute; width: 70px; height: 70px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: #3b82f6; color: white; box-shadow: 0 10px 15px -3px rgba(59,130,246,0.3); top: 50%; left: 50%; transform: translate(-50%,-50%); z-index: 10; }
        .main-btn:hover { transform: translate(-50%,-50%) scale(1.1); }
        @keyframes orbit { from { transform: rotate(0deg) translateX(80px) rotate(0deg); } to { transform: rotate(360deg) translateX(80px) rotate(-360deg); } }
        .orbital-element { position: absolute; top: 50%; left: 50%; transform-origin: 0 0; transition: opacity 0.5s ease-in-out; }
        .orbital-item { position: absolute; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); transform: translate(-50%,-50%); background: white; transition: all 0.3s; }
        .orbital-item:hover { transform: translate(-50%,-50%) scale(1.2); }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(59,130,246,0.4); } 70% { box-shadow: 0 0 0 10px rgba(59,130,246,0); } 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0); } }
        .pulse { animation: pulse 2s infinite; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .fade-in { animation: fadeInUp 0.5s ease-out forwards; opacity: 0; }
      `}</style>

      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden fade-in" style={{ animationDelay: '0.2s' }}>
        <div className="p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="heading text-4xl md:text-5xl font-semibold text-gray-900 mb-2 fade-in" style={{ animationDelay: '0.4s' }}>
              {tab === 'login' ? 'SIGN IN' : 'SIGN UP'}
            </h1>
            <p className="text-gray-600 text-lg fade-in" style={{ animationDelay: '0.6s' }}>
              {tab === 'login' ? 'Access Your Multi-Channel Social Agent' : 'Create your account'}
            </p>
          </div>

          {/* Orbit Component */}
          <div className="flex justify-center mb-10">
            <div className="orbit">
              <div className="orbit-circle orbit-1 fade-in" style={{ animationDelay: '0.8s' }} />
              <div className="orbit-circle orbit-2 fade-in" style={{ animationDelay: '0.9s' }} />
              <div className="orbit-circle orbit-3 fade-in" style={{ animationDelay: '1s' }} />

              {/* Main Button */}
              <div className="main-btn fade-in pulse" style={{ animationDelay: '1.1s' }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4" />
                </svg>
              </div>

              {/* Orbital Elements */}
              {SOCIAL_ICONS.map((iconPath, i) => (
                <div
                  key={i}
                  className="orbital-element"
                  style={{
                    animation: 'orbit 20s linear infinite',
                    animationDelay: `${-i * 4}s`,
                    opacity: showOrbitals ? 1 : 0,
                  }}
                >
                  <div className="orbital-item">
                    <SocialIcon d={iconPath} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 px-4 py-3 bg-red-50 border border-red-100 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Login Form */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-6">
              <div className="fade-in" style={{ animationDelay: '1.2s' }}>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  id="username"
                  value={loginForm.username}
                  onChange={e => setLoginForm(p => ({ ...p, username: e.target.value }))}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  placeholder="your username"
                  required
                  autoFocus
                />
              </div>

              <div className="fade-in" style={{ animationDelay: '1.3s' }}>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    value={loginForm.password}
                    onChange={e => setLoginForm(p => ({ ...p, password: e.target.value }))}
                    className="w-full px-4 py-3 pr-11 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="••••••••"
                    required
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

              <div className="flex items-center justify-between fade-in" style={{ animationDelay: '1.4s' }}>
                <div className="flex items-center">
                  <input id="remember" type="checkbox" className="h-4 w-4 border-gray-300 rounded text-blue-600 focus:ring-blue-500" />
                  <label htmlFor="remember" className="ml-2 block text-sm text-gray-700">Remember me</label>
                </div>
              </div>

              <div className="fade-in" style={{ animationDelay: '1.5s' }}>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50"
                >
                  {isLoading ? 'Signing in...' : 'Sign in'}
                </button>
              </div>
            </form>
          )}

          {/* Signup Form */}
          {tab === 'signup' && (
            <form onSubmit={handleSignup} className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <div className="fade-in" style={{ animationDelay: '1.2s' }}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
                  <input
                    type="text"
                    value={signupForm.username}
                    onChange={e => setSignupForm(p => ({ ...p, username: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="username"
                    required
                    autoFocus
                  />
                </div>
                <div className="fade-in" style={{ animationDelay: '1.25s' }}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={signupForm.displayName}
                    onChange={e => setSignupForm(p => ({ ...p, displayName: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="Brand name"
                  />
                </div>
              </div>

              <div className="fade-in" style={{ animationDelay: '1.3s' }}>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                <input
                  type="email"
                  value={signupForm.email}
                  onChange={e => setSignupForm(p => ({ ...p, email: e.target.value }))}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  placeholder="your@email.com"
                  required
                />
              </div>

              <div className="fade-in" style={{ animationDelay: '1.35s' }}>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password * (6+ chars)</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={signupForm.password}
                    onChange={e => setSignupForm(p => ({ ...p, password: e.target.value }))}
                    className="w-full px-4 py-3 pr-11 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="••••••••"
                    required
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

              <div className="fade-in" style={{ animationDelay: '1.4s' }}>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50"
                >
                  {isLoading ? 'Creating account...' : 'Sign up'}
                </button>
              </div>
            </form>
          )}

          {/* Footer */}
          <div className="mt-8 text-center fade-in" style={{ animationDelay: '1.6s' }}>
            <p className="text-sm text-gray-600">
              {tab === 'login' ? (
                <>Don't have an account? <button type="button" onClick={() => { setTab('signup'); setError(''); }} className="font-medium text-blue-600 hover:text-blue-500">Sign up</button></>
              ) : (
                <>Already have an account? <button type="button" onClick={() => { setTab('login'); setError(''); }} className="font-medium text-blue-600 hover:text-blue-500">Sign in</button></>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
