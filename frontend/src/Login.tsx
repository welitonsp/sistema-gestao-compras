import { useState } from 'react';
import { useAuth } from './api/authContext';
import { Lock, User, Loader2 } from 'lucide-react';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Falha ao autenticar');
      }

      // Agora buscamos o perfil para atualizar o contexto
      const meResponse = await fetch('/api/v1/users/me');
      const userData = await meResponse.json();
      
      login({ username: userData.username, role: userData.role });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock size={32} />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Acesso Restrito</h1>
          <p className="text-slate-500 mt-2">Sistema de Gestão de Compras</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          <div aria-live="polite" aria-atomic="true">
            {error && (
              <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm border border-red-100" role="alert">
                {error}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-2">Usuário</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} aria-hidden="true" />
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-offset-2 focus:ring-blue-600 focus:border-blue-600 transition-all outline-none"
                placeholder="admin"
                required
                aria-required="true"
                aria-invalid={!!error}
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">Senha</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} aria-hidden="true" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-offset-2 focus:ring-blue-600 focus:border-blue-600 transition-all outline-none"
                placeholder="••••••••"
                required
                aria-required="true"
                aria-invalid={!!error}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-semibold hover:bg-blue-700 focus:ring-2 focus:ring-offset-2 focus:ring-blue-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            aria-busy={isLoading}
          >
            {isLoading ? <Loader2 className="animate-spin" size={20} aria-hidden="true" /> : 'Entrar no Sistema'}
          </button>
        </form>

        <p className="mt-8 text-center text-xs text-slate-400 uppercase tracking-widest font-medium">
          Uso Institucional e Monitorado
        </p>
      </div>
    </div>
  );
}
