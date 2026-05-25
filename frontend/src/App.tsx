import { useState, useEffect, useMemo, useCallback } from 'react';
import { LogOut, RefreshCw, ShieldCheck, PackageOpen, Users, UserPlus, Settings2, Globe, Trash2, Plus, Bell } from 'lucide-react';
import { apiClient } from './api/client';
import { useAuth } from './api/authContext';
import Login from './Login';
import { DashboardResumo, AlertaPreco, AuditLog, Produto, ForecastInfo, AnomaliaEstatistica, User, Department } from './types/api';

// Components & Pages
import { StatusMessage } from './components/StatusMessage';
import { JobMonitor, JobStatus } from './components/JobMonitor';
import { AuditChatbot } from './components/AuditChatbot';
import { DashboardView } from './pages/DashboardView';
import { AuditoriaView } from './pages/AuditoriaView';
import { CatalogoView } from './pages/CatalogoView';
import { GestaoView } from './pages/GestaoView';
import { UserCreateModal } from './components/UserCreateModal';

type Tab = 'dashboard' | 'auditoria' | 'produtos' | 'gestao';

export default function App() {
  const { isAuthenticated, logout, user: authUser } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [data, setData] = useState<DashboardResumo | null>(null);
  const [alerts, setAlertas] = useState<AlertaPreco[]>([]);
  const [duplicatas, setDuplicatas] = useState<any[]>([]);
  const [volatilidade, setVolatilidade] = useState<any[]>([]);
  const [forecasts, setForecasts] = useState<ForecastInfo[]>([]);
  const [anomalias, setAnomalias] = useState<AnomaliaEstatistica[]>([]);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [webhooks, setWebhooks] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeJobs, setActiveJobs] = useState<JobStatus[]>([]);
  const [searchProduto, setSearchProduto] = useState('');
  const [editingEan, setEditingEan] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);

  const showStatus = (msg: string) => {
    setStatusMessage(msg);
    setTimeout(() => setStatusMessage(''), 3000);
  };

  const fetchData = useCallback(async () => {
    try {
      const promises: any[] = [
        apiClient.get<DashboardResumo>('/dashboard/resumo'),
        apiClient.get<{ alertas: AlertaPreco[] }>('/dashboard/alertas'),
        apiClient.get<AuditLog[]>('/dashboard/audit-logs'),
        apiClient.get<Produto[]>('/produtos'),
        apiClient.get<any[]>('/dashboard/alertas/duplicidade'),
        apiClient.get<any[]>('/dashboard/insights/volatilidade'),
        apiClient.get<ForecastInfo[]>('/dashboard/insights/forecast'),
        apiClient.get<AnomaliaEstatistica[]>('/dashboard/alertas/estatisticos'),
        apiClient.get<any[]>('/dashboard/insights/tendencia'),
      ];

      if (authUser?.role === 'admin') {
        promises.push(apiClient.get<User[]>('/users'));
        promises.push(apiClient.get<Department[]>('/users/departments'));
        promises.push(apiClient.get<any[]>('/webhooks'));
      }

      const results = await Promise.all(promises);
      
      setData(results[0]);
      setAlertas(results[1].alertas);
      setAuditLogs(results[2]);
      setProdutos(results[3]);
      setDuplicatas(results[4]);
      setVolatilidade(results[5]);
      setForecasts(results[6]);
      setAnomalias(results[7]);
      setTrendData(results[8]);
      
      if (authUser?.role === 'admin') {
        setUsers(results[9]);
        setDepartments(results[10]);
        setWebhooks(results[11]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [authUser]);

  useEffect(() => {
    if (isAuthenticated) fetchData();
  }, [isAuthenticated, fetchData]);

  // SSE Notifications
  useEffect(() => {
    if (!isAuthenticated) return;
    const eventSource = new EventSource(`/api/v1/dashboard/notifications`);
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'JOB_STARTED') {
        setActiveJobs(prev => [...prev, { job_id: data.payload.job_id, status: 'in_progress', success: null, file: data.payload.file }]);
      } 
      else if (data.type === 'JOB_COMPLETED' || data.type === 'JOB_FAILED') {
        setActiveJobs(prev => prev.map(job => job.job_id === data.payload.job_id ? { ...job, status: data.type === 'JOB_COMPLETED' ? 'completed' : 'failed', success: data.type === 'JOB_COMPLETED' } : job));
        if (data.type === 'JOB_COMPLETED') { 
          showStatus(`Concluído: ${data.payload.file || 'arquivo'}`); 
          fetchData(); 
        }
      }
      else if (data.type === 'ANOMALY_DETECTED') {
        showStatus(`ALERTA: Anomalia crítica detectada no produto ${data.payload.produto}!`);
        fetchData();
      }
    };
    return () => eventSource.close();
  }, [isAuthenticated, fetchData]);

  const handleProcessBatch = async () => {
    setIsProcessing(true);
    try { 
      await apiClient.post<any>('/notas/processar-lote', {}); 
      showStatus("Lote em processamento..."); 
    } catch (err) { alert("Falha no worker."); } 
    finally { setIsProcessing(false); }
  };

  const handleExport = () => {
    showStatus("Gerando relatório...");
    let endpoint = activeTab === 'auditoria' ? '/dashboard/audit-logs/export' : '/produtos/export';
    fetch(`/api/v1${endpoint}`).then(r => r.blob()).then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${activeTab}_${new Date().getTime()}.csv`;
        a.click();
    });
  };

  const handleUpdateCategory = async (ean: string) => {
    try {
      await apiClient.patch(`/produtos/${ean}`, { categoria: editValue });
      setEditingEan(null);
      showStatus("Produto atualizado!");
      fetchData();
    } catch (err) { alert("Erro na atualização."); }
  };

  const handleCreateUser = async (userData: any) => {
    try {
      await apiClient.post('/users', userData);
      showStatus("Usuário criado com sucesso!");
      fetchData();
    } catch (err) {
      throw err;
    }
  };

  const handleToggleUserStatus = async (user: User) => {
    try {
      await apiClient.patch(`/users/${user.id}`, { is_active: !user.is_active });
      showStatus(`Usuário ${user.username} ${user.is_active ? 'desativado' : 'ativado'}!`);
      fetchData();
    } catch (err) { alert("Erro ao alterar status."); }
  };

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm("Remover?")) return;
    try { await apiClient.post(`/webhooks/${id}`, {}, { method: 'DELETE' }); fetchData(); } catch(e) { alert("Erro"); }
  };

  const chartData = useMemo(() => data?.por_categoria.map(c => ({ name: c.categoria, total: Number(c.total) })) || [], [data]);
  const filteredProdutos = useMemo(() => produtos.filter(p => p.nome_limpo.toLowerCase().includes(searchProduto.toLowerCase()) || p.ean.includes(searchProduto)), [produtos, searchProduto]);

  if (!isAuthenticated) return <Login />;
  if (loading) return <div className="p-12 font-bold animate-pulse text-blue-800 uppercase tracking-widest text-center">Iniciando Portal de Auditoria Governamental...</div>;

  const isEmpty = (!data || data.total_geral === 0) && activeJobs.length === 0;

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8">
      <StatusMessage message={statusMessage} />
      
      <UserCreateModal 
        isOpen={isUserModalOpen} 
        onClose={() => setIsUserModalOpen(false)} 
        departments={departments} 
        onSave={handleCreateUser} 
      />

      <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2 tracking-tighter"><ShieldCheck className="text-blue-600" /> GESTÃO DE COMPRAS</h1>
          <p className="text-slate-500 text-[10px] font-black uppercase">
            Portal Corporativo | {authUser?.role} | {departments.find(d => d.id === users.find(u => u.username === authUser?.username)?.department_id)?.name || 'Institucional'}
          </p>
        </div>
        <div className="flex gap-2">
          <nav className="bg-slate-200/50 p-1 rounded-xl flex gap-1 mr-2" role="tablist">
            {['dashboard', 'auditoria', 'produtos', 'gestao'].map((t) => (
              (t !== 'gestao' || authUser?.role === 'admin') && (
                <button 
                  key={t} 
                  role="tab" 
                  aria-selected={activeTab === t} 
                  onClick={() => setActiveTab(t as Tab)} 
                  className={`px-4 py-1.5 rounded-lg text-[10px] font-black transition-all ${activeTab === t ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
                >
                  {t.toUpperCase()}
                </button>
              )
            ))}
          </nav>
          <button className="bg-white text-slate-600 border border-slate-200 px-3 py-1.5 rounded-lg text-[10px] font-black hover:bg-red-50 hover:text-red-600 transition-all" onClick={logout}>SAIR</button>
          <button disabled={isProcessing} onClick={handleProcessBatch} className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-[10px] font-black hover:bg-blue-700 flex items-center gap-2">
            {isProcessing ? <RefreshCw className="animate-spin" size={14} /> : <RefreshCw size={14} />} LOTE
          </button>
        </div>
      </header>

      <AuditChatbot />

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white rounded-3xl border-2 border-dashed border-slate-200">
          <PackageOpen size={64} className="text-slate-200 mb-6" />
          <h2 className="text-xl font-black text-slate-800">BASE DE DADOS VAZIA</h2>
          <p className="text-slate-500 text-sm mt-2">Clique no botão LOTE para iniciar a ingestão institucional.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-6">
            {activeTab === 'dashboard' && <DashboardView data={data} alerts={alerts} duplicatas={duplicatas} anomalias={anomalias} forecasts={forecasts} chartData={chartData} trendData={trendData} />}
            {activeTab === 'auditoria' && <AuditoriaView logs={auditLogs} onExport={handleExport} />}
            {activeTab === 'produtos' && <CatalogoView produtos={filteredProdutos} search={searchProduto} onSearchChange={setSearchProduto} onExport={handleExport} editingEan={editingEan} editValue={editValue} onEditStart={(p) => { setEditingEan(p.ean); setEditValue(p.categoria || ''); }} onEditChange={setEditValue} onEditSave={handleUpdateCategory} onEditCancel={() => setEditingEan(null)} onRefresh={fetchData} />}
            {activeTab === 'gestao' && (
              <GestaoView 
                users={users} 
                departments={departments} 
                webhooks={webhooks} 
                onDeleteWebhook={handleDeleteWebhook}
                onAddUser={() => setIsUserModalOpen(true)}
                onToggleUser={handleToggleUserStatus}
              />
            )}
          </div>
          
          <div className="lg:col-span-1 space-y-6">
            <JobMonitor jobs={activeJobs} />
            
            <div className="bg-white p-6 rounded-2xl border shadow-sm">
              <h3 className="text-[10px] font-black mb-4 text-slate-400 uppercase tracking-widest">Network Integrity</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center text-[10px]">
                  <span className="text-slate-500 font-bold">API GATEWAY</span>
                  <span className="text-green-600 flex items-center gap-1 font-black underline">ONLINE</span>
                </div>
                <div className="flex justify-between items-center text-[10px]">
                  <span className="text-slate-500 font-bold">SSE STREAM</span>
                  <span className="text-blue-600 flex items-center gap-1 font-black animate-pulse">ACTIVE</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
