import React, { useState } from 'react';
import { useAuth } from './api/authContext';
import { 
  ShieldCheck, Lock, User as UserIcon, 
  ArrowRight, Shield, Globe, Activity 
} from 'lucide-react';
import { apiClient } from './api/client';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) throw new Error('Credenciais inválidas');
      
      const data = await response.json();
      login(data.access_token);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-6 relative overflow-hidden transition-colors duration-300">
      {/* Background Decorative Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none opacity-20">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-200 dark:bg-primary-900 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-200 dark:bg-indigo-900 rounded-full blur-[120px]" />
      </div>

      <div className="w-full max-w-[1100px] grid grid-cols-1 lg:grid-cols-2 bg-white dark:bg-slate-900 rounded-[40px] shadow-2xl shadow-slate-200 dark:shadow-none overflow-hidden relative z-10 border border-white dark:border-slate-800 transition-colors">
        {/* Left Side: Branding/Visual */}
        <div className="hidden lg:flex flex-col justify-between p-12 bg-slate-900 dark:bg-slate-950 text-white relative">
          <div className="flex items-center gap-3">
            <div className="bg-primary-600 p-2.5 rounded-2xl">
              <ShieldCheck size={28} />
            </div>
            <h1 className="text-xl font-bold uppercase tracking-tighter">Meu Gestor</h1>
          </div>

          <div className="space-y-6">
            <h2 className="text-4xl font-bold leading-tight">
              Análise inteligente <br />
              <span className="text-primary-400">das suas compras.</span>
            </h2>
            <p className="text-slate-400 text-lg leading-relaxed">
              Monitore seus gastos, descubra padrões e economize com o seu assistente pessoal.
            </p>
            <div className="grid grid-cols-2 gap-4 pt-4">
              <div className="bg-white/5 border border-white/10 p-4 rounded-2xl">
                <Activity className="text-primary-400 mb-2" size={20} />
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Tempo Real</p>
                <p className="font-bold text-sm">Dashboard</p>
              </div>
              <div className="bg-white/5 border border-white/10 p-4 rounded-2xl">
                <Globe className="text-emerald-400 mb-2" size={20} />
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Automático</p>
                <p className="font-bold text-sm">Catálogo</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-bold text-slate-500 uppercase tracking-widest">
            <Shield size={12} /> Sua privacidade é nossa prioridade
          </div>
        </div>

        {/* Right Side: Login Form */}
        <div className="p-12 lg:p-20 flex flex-col justify-center">
          <div className="mb-10 text-center lg:text-left">
            <h3 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">Bem-vindo</h3>
            <p className="text-slate-500 dark:text-slate-400 font-medium">Acesse sua conta para gerenciar suas compras.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 ml-1">Usuário</label>
              <div className="relative group">
                <UserIcon className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 dark:text-slate-600 group-focus-within:text-primary-500 transition-colors" size={20} />
                <input 
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Seu nome de usuário"
                  className="w-full pl-12 pr-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-xl outline-none focus:border-primary-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm font-bold text-slate-900 dark:text-white"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 ml-1">Senha</label>
              <div className="relative group">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 dark:text-slate-600 group-focus-within:text-primary-500 transition-colors" size={20} />
                <input 
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-12 pr-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-xl outline-none focus:border-primary-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm font-bold text-slate-900 dark:text-white"
                  required
                />
              </div>
            </div>

            {error && (
              <div className="bg-rose-50 dark:bg-rose-900/20 border-l-4 border-rose-500 p-4 rounded-r-xl text-rose-700 dark:text-rose-400 text-xs font-bold animate-in shake duration-300">
                {error}
              </div>
            )}

            <button 
              type="submit" 
              disabled={loading}
              className="w-full py-4 bg-primary-600 text-white rounded-xl font-bold uppercase tracking-widest text-sm hover:bg-primary-700 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-primary-900/20 flex items-center justify-center gap-3 disabled:opacity-50 disabled:grayscale"
            >
              {loading ? 'Autenticando...' : 'Acessar Meu Painel'}
              {!loading && <ArrowRight size={18} />}
            </button>
          </form>

          <p className="mt-12 text-center text-xs font-bold text-slate-400 dark:text-slate-600 uppercase tracking-tighter">
            Smart Shopping v3.2 — Seu assistente pessoal
          </p>
        </div>
      </div>
    </div>
  );
}
