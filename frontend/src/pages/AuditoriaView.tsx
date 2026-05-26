import React from 'react';
import { 
  FileText, ShieldCheck, User as UserIcon, Calendar, 
  ArrowRight, Search, Filter, Download, MoreHorizontal,
  Globe
} from 'lucide-react';
import { AuditLog } from '../types/api';
import { Skeleton } from '../components/Skeleton';

interface AuditoriaViewProps {
  logs: AuditLog[] | null;
  onExport?: () => void;
}

export const AuditoriaView: React.FC<AuditoriaViewProps> = ({ logs, onExport }) => {
  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Relatório de Compras - Meu Gestor',
          text: `Confira meu histórico de atividades do sistema Meu Gestor. Total de ${logs?.length || 0} operações registradas.`,
          url: window.location.href
        });
      } catch (err) {
        console.log('Erro ao compartilhar:', err);
      }
    } else {
      alert('Compartilhamento nativo não suportado neste navegador. Use a exportação CSV.');
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Histórico de Atividades</h2>
          <p className="text-slate-500 text-sm">Registro de todas as operações realizadas na sua conta.</p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all shadow-sm"
            aria-label="Filtrar histórico por período"
          >
            <Filter size={16} /> Filtrar
          </button>
          
          {/* Share Button (Chromium/Mobile optimized) */}
          <button 
            onClick={handleShare}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded-xl text-xs font-bold hover:bg-indigo-100 transition-all shadow-sm"
            aria-label="Compartilhar histórico"
          >
            <Globe size={16} /> Compartilhar
          </button>

          <button 
            onClick={onExport}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 rounded-xl text-xs font-bold text-white hover:bg-slate-800 transition-all shadow-lg shadow-slate-200"
            aria-label="Exportar histórico em formato CSV"
          >
            <Download size={16} /> Exportar
          </button>
        </div>
      </div>

      {/* Activity Timeline / Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 text-xs uppercase font-bold tracking-widest">
                <th className="px-8 py-5">Data e Hora</th>
                <th className="px-8 py-5">Usuário</th>
                <th className="px-8 py-5">Operação</th>
                <th className="px-8 py-5">Item Afetado</th>
                <th className="px-8 py-5">Status</th>
                <th className="px-8 py-5 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {!logs ? (
                [1, 2, 3, 4, 5].map((i) => (
                  <tr key={i}>
                    <td className="px-8 py-5"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-10 w-40 rounded-full" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-6 w-20 rounded-full" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-4 w-48" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-8 py-5 text-right"><Skeleton className="h-8 w-8 rounded-lg ml-auto" /></td>
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-8 py-20 text-center text-slate-400 dark:text-slate-600">
                    <ShieldCheck size={40} className="mx-auto mb-4 opacity-20" />
                    <p className="text-sm font-medium">Nenhum registro encontrado</p>
                  </td>
                </tr>
              ) : (
                logs.map((log, i) => (
                  <tr key={i} className="group hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-slate-400">
                        <Calendar size={14} className="text-slate-400 dark:text-slate-500" />
                        {new Date(log.criado_em || Date.now()).toLocaleString('pt-BR')}
                      </div>
                    </td>
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-3">
                        <div className="bg-slate-100 dark:bg-slate-800 p-2 rounded-full text-slate-500 dark:text-slate-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/30 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                          <UserIcon size={14} />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-slate-700 dark:text-slate-200">{log.usuario}</p>
                          <p className="text-[11px] text-slate-400 dark:text-slate-500 uppercase font-bold tracking-tighter">ID: {log.ip_origem || 'Pessoal'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-8 py-5">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-tight ${
                        log.operacao === 'LOGIN' ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' :
                        log.operacao === 'DELETE' ? 'bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-400' :
                        log.operacao === 'IMPORT' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400' :
                        'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                      }`}>
                        {log.operacao}
                      </span>
                    </td>
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{log.entidade}</span>
                        <ArrowRight size={12} className="text-slate-300 dark:text-slate-700" />
                        <span className="text-xs font-mono text-slate-400 dark:text-slate-500 truncate max-w-[120px] bg-slate-50 dark:bg-slate-800/50 px-1.5 py-0.5 rounded border border-slate-100 dark:border-slate-800">
                          {log.entidade_id}
                        </span>
                      </div>
                    </td>
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-200 dark:shadow-none" />
                        <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase">Sucesso</span>
                      </div>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <button 
                        className="p-2 text-slate-300 dark:text-slate-600 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                        aria-label="Ver detalhes do log"
                      >
                        <MoreHorizontal size={18} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
