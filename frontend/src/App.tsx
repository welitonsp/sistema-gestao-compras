import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';
import { 
  LogOut, RefreshCw, ShieldCheck, PackageOpen, Users, 
  Settings2, Globe, Trash2, Plus, Bell, LayoutDashboard, 
  ClipboardCheck, Package, Shield, User as UserIcon, TrendingUp
} from 'lucide-react';
import { apiClient } from './api/client';
import { useAuth } from './api/authContext';
import Login from './Login';
import { 
  DashboardResumo, AlertaPreco, AuditLog, Produto, 
  ForecastInfo, AnomaliaEstatistica, User, Department 
} from './types/api';

import { StatusMessage } from './components/StatusMessage';
import { JobMonitor, JobStatus } from './components/JobMonitor';
import { AuditChatbot } from './components/AuditChatbot';
import { Skeleton } from './components/Skeleton';

// Lazy load views for better performance (Code Splitting)
const DashboardView = lazy(() => import('./pages/DashboardView').then(m => ({ default: m.DashboardView })));
const AuditoriaView = lazy(() => import('./pages/AuditoriaView').then(m => ({ default: m.AuditoriaView })));
const CatalogoView = lazy(() => import('./pages/CatalogoView').then(m => ({ default: m.CatalogoView })));
const GestaoView = lazy(() => import('./pages/GestaoView').then(m => ({ default: m.GestaoView })));
const InsightsView = lazy(() => import('./pages/InsightsView').then(m => ({ default: m.InsightsView })));

type Tab = 'dashboard' | 'auditoria' | 'produtos' | 'gestao' | 'insights';

export default function App() {
  const { isAuthenticated, logout, user: authUser } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [data, setData] = useState<DashboardResumo | null>(null);
  const [alerts, setAlertas] = useState<AlertaPreco[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [resumo, alertas, logs, prods] = await Promise.all([
        apiClient.get<DashboardResumo>('/dashboard/resumo'),
        apiClient.get<{ alertas: AlertaPreco[] }>('/dashboard/alertas'),
        apiClient.get<AuditLog[]>('/dashboard/audit-logs'),
        apiClient.get<Produto[]>('/produtos'),
      ]);
      
      setData(resumo);
      setAlertas(alertas.alertas);
      setAuditLogs(logs);
      setProdutos(prods);
      
      if (authUser?.role === 'admin') {
        const [userList, depts] = await Promise.all([
          apiClient.get<User[]>('/users'),
          apiClient.get<Department[]>('/users/departments'),
        ]);
        setUsers(userList);
        setDepartments(depts);
      }
    } catch (err) {
      console.error(err);
      setStatusMessage('Falha ao sincronizar dados. Verifique sua conexão.');
      setTimeout(() => setStatusMessage(''), 5000);
    } finally {
      setLoading(false);
    }
  }, [authUser]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchData();

      // SSE para notificações em tempo real
      const eventSource = new EventSource('/api/v1/dashboard/notifications');
      
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setStatusMessage(payload.message || 'Nova notificação do sistema');
          
          // Se for um evento de conclusão, recarrega dados para refletir mudanças
          if (payload.status === 'completed' || payload.type?.includes('finished')) {
            fetchData();
          }
          
          setTimeout(() => setStatusMessage(''), 8000);
        } catch (e) {
          console.error("Erro ao processar mensagem SSE", e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
      };

      return () => eventSource.close();
    }
  }, [isAuthenticated, fetchData]);

  const handleExportAudit = () => {
    window.location.href = '/api/v1/dashboard/audit-logs/export';
  };

  const handleExportProdutos = () => {
    window.location.href = '/api/v1/produtos/export';
  };

  if (!isAuthenticated) return <Login />;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex transition-colors duration-300">
      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside className={`w-64 bg-slate-900 dark:bg-slate-900 text-slate-300 flex flex-col fixed inset-y-0 z-50 transition-transform duration-300 ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 border-r dark:border-slate-800`}>
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="bg-indigo-600 p-2 rounded-xl">
            <ShieldCheck className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-white font-bold text-sm tracking-tight uppercase">Meu Gestor</h1>
            <p className="text-[11px] text-slate-500 font-medium">Análise de Compras</p>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2">
          <button 
            onClick={() => { setActiveTab('dashboard'); setIsSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${activeTab === 'dashboard' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' : 'hover:bg-slate-800 dark:hover:bg-slate-800/50 hover:text-white'}`}
          >
            <LayoutDashboard size={18} /> Dashboard
          </button>
          <button 
            onClick={() => { setActiveTab('insights'); setIsSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${activeTab === 'insights' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' : 'hover:bg-slate-800 dark:hover:bg-slate-800/50 hover:text-white'}`}
          >
            <TrendingUp size={18} /> Insights IA
          </button>
          <button 
            onClick={() => { setActiveTab('auditoria'); setIsSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${activeTab === 'auditoria' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' : 'hover:bg-slate-800 dark:hover:bg-slate-800/50 hover:text-white'}`}
          >
            <ClipboardCheck size={18} /> Histórico
          </button>
          <button 
            onClick={() => { setActiveTab('produtos'); setIsSidebarOpen(false); }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${activeTab === 'produtos' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' : 'hover:bg-slate-800 dark:hover:bg-slate-800/50 hover:text-white'}`}
          >
            <Package size={18} /> Meus Itens
          </button>
          {authUser?.role === 'admin' && (
            <button 
              onClick={() => { setActiveTab('gestao'); setIsSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${activeTab === 'gestao' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' : 'hover:bg-slate-800 dark:hover:bg-slate-800/50 hover:text-white'}`}
            >
              <Shield size={18} /> Configurações
            </button>
          )}
        </nav>

        <div className="p-4 border-t border-slate-800 mt-auto">
          <div className="bg-slate-800/50 p-4 rounded-2xl flex items-center gap-3">
            <div className="bg-slate-700 h-10 w-10 rounded-full flex items-center justify-center text-indigo-400 font-bold">
              {authUser?.username?.[0].toUpperCase()}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-white text-xs font-bold truncate">{authUser?.username}</p>
              <p className="text-[11px] text-slate-500 uppercase font-bold">{authUser?.role}</p>
            </div>
            <button 
              onClick={logout}
              className="text-slate-500 hover:text-red-400 transition-colors"
              title="Sair"
              aria-label="Sair do sistema"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 md:ml-64 min-h-screen transition-all duration-300">
        {/* Top Header */}
        <header className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 h-16 sticky top-0 z-40 flex items-center justify-between px-4 md:px-8 transition-colors">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setIsSidebarOpen(true)}
              className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl md:hidden"
              aria-label="Abrir menu"
            >
              <Settings2 size={20} />
            </button>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest">System Online</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={fetchData} 
              className="p-2 text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors" 
              title="Atualizar dados"
              aria-label="Atualizar dados do dashboard"
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            </button>
            <div className="h-6 w-[1px] bg-slate-200 dark:bg-slate-800 hidden sm:block mx-2" />
            <div className="hidden sm:flex items-center gap-3">
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-tighter">{new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
            </div>
          </div>
        </header>

        {/* View Content */}
        <div className="p-8 pb-24 overflow-x-hidden">
          <Suspense fallback={
            <div className="space-y-8 animate-in fade-in duration-500">
              <div className="flex flex-col gap-2">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-96" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}
              </div>
              <Skeleton className="h-[400px] rounded-3xl" />
            </div>
          }>
            <div key={activeTab} className="max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              {activeTab === 'dashboard' && <DashboardView data={data} alerts={alerts} produtosCount={produtos.length} />}
              {activeTab === 'insights' && <InsightsView />}
              {activeTab === 'auditoria' && <AuditoriaView logs={auditLogs} onExport={handleExportAudit} />}
              {activeTab === 'produtos' && <CatalogoView produtos={produtos} onRefresh={fetchData} onExport={handleExportProdutos} />}
              {activeTab === 'gestao' && <GestaoView users={users} departments={departments} onRefresh={fetchData} />}
            </div>
          </Suspense>
        </div>

        {/* AI Chatbot Overlay */}
        <AuditChatbot />
      </main>

      {statusMessage && <StatusMessage message={statusMessage} />}
    </div>
  );
}
