import React from 'react';
import { 
  FileText, ShieldCheck, User as UserIcon, Calendar, 
  ArrowRight, Search, Filter, Download, MoreHorizontal,
  Globe, RotateCcw, ShieldAlert, X
} from 'lucide-react';
import { AuditLog } from '../types/api';
import type { AuditLogFilters } from '../types/api';
import { Skeleton } from '../components/Skeleton';

interface AuditoriaViewProps {
  logs: AuditLog[] | null;
  onExport?: (filters?: AuditLogFilters) => void;
  onFiltersChange?: (filters: AuditLogFilters) => void;
  onLoadMore?: (filters: AuditLogFilters) => void;
  hasMore?: boolean;
  loadingMore?: boolean;
}

const SECURITY_OPERATION = 'AUDIT_CHAT_BLOCKED';

const operationLabel = (operation: string) => {
  if (operation === SECURITY_OPERATION) return 'CHAT BLOQUEADO';
  if (operation === 'PRODUCT_CANONIZATION_REVERTED') return 'CANONIZACAO REVERTIDA';
  if (operation === 'PRODUCT_CANONIZED') return 'CANONIZACAO';
  if (operation === 'CATEGORY_CONFIRMED') return 'CATEGORIA CONFIRMADA';
  return operation;
};

const operationClass = (operation: string) => {
  if (operation === SECURITY_OPERATION) {
    return 'bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-300';
  }
  if (operation === 'PRODUCT_CANONIZATION_REVERTED') {
    return 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300';
  }
  if (operation === 'PRODUCT_CANONIZED') {
    return 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300';
  }
  if (operation === 'LOGIN') {
    return 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400';
  }
  if (operation === 'DELETE' || operation === 'IMPORT_DELETED') {
    return 'bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-400';
  }
  if (operation === 'IMPORT' || operation.startsWith('IMPORT_')) {
    return 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400';
  }
  return 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400';
};

const safeJsonDetails = (detailsText: string | null): Record<string, unknown> | null => {
  try {
    const details = JSON.parse(detailsText || '{}');
    return details && typeof details === 'object' && !Array.isArray(details)
      ? details as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
};

const detailString = (details: Record<string, unknown>, key: string): string | null => {
  const value = details[key];
  return typeof value === 'string' && value.trim() ? value : null;
};

const auditChatBlockedSummary = (log: AuditLog): string | null => {
  if (log.operacao !== SECURITY_OPERATION) return null;

  const details = safeJsonDetails(log.detalhes);
  const reason = details ? detailString(details, 'reason') : null;
  return reason ? `Bloqueio de segurança: ${reason}` : 'Bloqueio de segurança do chat de auditoria';
};

const canonicalDetailsSummary = (log: AuditLog): string | null => {
  if (
    log.operacao !== 'PRODUCT_CANONIZATION_REVERTED'
    && log.operacao !== 'PRODUCT_CANONIZED'
  ) {
    return null;
  }

  const details = safeJsonDetails(log.detalhes) as {
    ean_original?: string;
    ean_canonico?: string;
    reason?: string | null;
  } | null;
  if (details) {
    if (!details.ean_original || !details.ean_canonico) return null;

    const base = `EAN ${details.ean_original} -> ${details.ean_canonico}`;
    return details.reason ? `${base} · ${details.reason}` : base;
  }

  return null;
};

const detailsSummary = (log: AuditLog): string | null => (
  auditChatBlockedSummary(log) || canonicalDetailsSummary(log)
);

const normalizeSearch = (value: string): string => value.trim().toLocaleLowerCase('pt-BR');

const auditSearchText = (log: AuditLog): string => (
  [
    log.usuario,
    log.operacao,
    operationLabel(log.operacao),
    log.entidade,
    log.entidade_id,
    log.ip_origem,
    detailsSummary(log),
  ]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('pt-BR')
);

const serverOperationFilter = (operationFilter: string): string | undefined => {
  if (operationFilter === 'all') return undefined;
  if (operationFilter === 'security') return SECURITY_OPERATION;
  return operationFilter;
};

export const AuditoriaView: React.FC<AuditoriaViewProps> = ({
  logs,
  onExport,
  onFiltersChange,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
}) => {
  const [searchTerm, setSearchTerm] = React.useState('');
  const [operationFilter, setOperationFilter] = React.useState('all');
  const [selectedLog, setSelectedLog] = React.useState<AuditLog | null>(null);
  const didMountFilters = React.useRef(false);

  const operationOptions = React.useMemo(() => (
    Array.from(new Set((logs || []).map((log) => log.operacao)))
      .filter((operation) => operation !== SECURITY_OPERATION)
      .sort()
  ), [logs]);

  const normalizedSearch = React.useMemo(() => normalizeSearch(searchTerm), [searchTerm]);
  const filteredLogs = React.useMemo(() => {
    if (!logs) return null;

    return logs.filter((log) => {
      const matchesOperation = operationFilter === 'all'
        || (operationFilter === 'security' && log.operacao === SECURITY_OPERATION)
        || log.operacao === operationFilter;
      const matchesSearch = !normalizedSearch || auditSearchText(log).includes(normalizedSearch);
      return matchesOperation && matchesSearch;
    });
  }, [logs, normalizedSearch, operationFilter]);
  const hasActiveFilters = Boolean(normalizedSearch) || operationFilter !== 'all';
  const serverFilters = React.useMemo<AuditLogFilters>(() => ({
    q: searchTerm,
    operation: serverOperationFilter(operationFilter),
  }), [operationFilter, searchTerm]);
  const selectedLogSummary = selectedLog ? detailsSummary(selectedLog) : null;
  const selectedLogIsBlocked = selectedLog?.operacao === SECURITY_OPERATION;

  React.useEffect(() => {
    if (!onFiltersChange) return;
    if (!didMountFilters.current) {
      didMountFilters.current = true;
      return;
    }

    const timeout = window.setTimeout(() => {
      onFiltersChange(serverFilters);
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [onFiltersChange, serverFilters]);

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
          {/* Share Button (Chromium/Mobile optimized) */}
          <button 
            onClick={handleShare}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded-xl text-xs font-bold hover:bg-indigo-100 transition-all shadow-sm"
            aria-label="Compartilhar histórico"
          >
            <Globe size={16} /> Compartilhar
          </button>

          <button 
            onClick={() => onExport?.(serverFilters)}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 rounded-xl text-xs font-bold text-white hover:bg-slate-800 transition-all shadow-lg shadow-slate-200"
            aria-label="Exportar histórico em formato CSV"
          >
            <Download size={16} /> Exportar
          </button>
        </div>
      </div>

      {/* Activity Timeline / Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="flex flex-col gap-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_220px] lg:min-w-[560px]">
            <label className="relative block">
              <span className="sr-only">Buscar no histórico de auditoria</span>
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
              <input
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm font-medium text-slate-700 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-indigo-700 dark:focus:ring-indigo-900/30"
                placeholder="Buscar por usuário, operação ou item"
                type="search"
              />
            </label>

            <label className="relative block">
              <span className="sr-only">Filtrar por operação</span>
              <Filter size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
              <select
                value={operationFilter}
                onChange={(event) => setOperationFilter(event.target.value)}
                className="h-11 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm font-bold text-slate-600 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-indigo-700 dark:focus:ring-indigo-900/30"
              >
                <option value="all">Todas as operações</option>
                <option value="security">Bloqueios do chat</option>
                {operationOptions.map((operation) => (
                  <option key={operation} value={operation}>{operationLabel(operation)}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex items-center justify-between gap-3 lg:justify-end">
            <span className="text-xs font-bold text-slate-400 dark:text-slate-500">
              {logs && filteredLogs ? `${filteredLogs.length} registros carregados` : 'Carregando registros'}
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={() => {
                  setSearchTerm('');
                  setOperationFilter('all');
                }}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
              >
                Limpar
              </button>
            )}
          </div>
        </div>
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
              ) : filteredLogs?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-8 py-20 text-center text-slate-400 dark:text-slate-600">
                    <ShieldCheck size={40} className="mx-auto mb-4 opacity-20" />
                    <p className="text-sm font-medium">
                      {logs.length === 0 ? 'Nenhum registro encontrado' : 'Nenhum registro corresponde aos filtros'}
                    </p>
                  </td>
                </tr>
              ) : (
                filteredLogs?.map((log, i) => {
                  const summary = detailsSummary(log);
                  const isCanonizationRevert = log.operacao === 'PRODUCT_CANONIZATION_REVERTED';
                  const isAuditChatBlocked = log.operacao === SECURITY_OPERATION;

                  return (
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
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-tight ${operationClass(log.operacao)}`}>
                        {isCanonizationRevert && <RotateCcw size={12} aria-hidden="true" />}
                        {isAuditChatBlocked && <ShieldAlert size={12} aria-hidden="true" />}
                        {operationLabel(log.operacao)}
                      </span>
                    </td>
                    <td className="px-8 py-5">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{log.entidade}</span>
                          <ArrowRight size={12} className="text-slate-300 dark:text-slate-700" />
                          <span className="text-xs font-mono text-slate-400 dark:text-slate-500 truncate max-w-[120px] bg-slate-50 dark:bg-slate-800/50 px-1.5 py-0.5 rounded border border-slate-100 dark:border-slate-800">
                            {log.entidade_id}
                          </span>
                        </div>
                        {summary && (
                          <p className="max-w-md text-[11px] font-medium text-slate-500 dark:text-slate-400">
                            {summary}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-8 py-5">
                      <div className="flex items-center gap-2">
                        <div className={`h-1.5 w-1.5 rounded-full shadow-sm dark:shadow-none ${
                          isAuditChatBlocked
                            ? 'bg-rose-500 shadow-rose-200'
                            : 'bg-emerald-500 shadow-emerald-200'
                        }`} />
                        <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase">
                          {isAuditChatBlocked ? 'Bloqueado' : 'Sucesso'}
                        </span>
                      </div>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <button 
                        type="button"
                        onClick={() => setSelectedLog(log)}
                        className="p-2 text-slate-300 dark:text-slate-600 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                        aria-label="Ver detalhes do log"
                      >
                        <MoreHorizontal size={18} />
                      </button>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        {logs && hasMore && (
          <div className="flex justify-center border-t border-slate-100 px-6 py-4 dark:border-slate-800">
            <button
              type="button"
              onClick={() => onLoadMore?.(serverFilters)}
              disabled={loadingMore}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {loadingMore ? 'Carregando...' : 'Carregar mais registros'}
            </button>
          </div>
        )}
      </div>

      {selectedLog && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/40 px-4 py-6 backdrop-blur-sm sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="audit-log-detail-title"
        >
          <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5 dark:border-slate-800">
              <div className="space-y-2">
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-tight ${operationClass(selectedLog.operacao)}`}>
                  {selectedLog.operacao === 'PRODUCT_CANONIZATION_REVERTED' && <RotateCcw size={12} aria-hidden="true" />}
                  {selectedLogIsBlocked && <ShieldAlert size={12} aria-hidden="true" />}
                  {operationLabel(selectedLog.operacao)}
                </span>
                <h3 id="audit-log-detail-title" className="text-lg font-bold text-slate-800 dark:text-slate-100">
                  Detalhes do registro
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                aria-label="Fechar detalhes do log"
              >
                <X size={18} />
              </button>
            </div>

            <div className="grid gap-4 px-6 py-5 sm:grid-cols-2">
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Data e Hora</p>
                <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {new Date(selectedLog.criado_em || Date.now()).toLocaleString('pt-BR')}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Status</p>
                <p className={`mt-1 text-sm font-bold ${selectedLogIsBlocked ? 'text-rose-600 dark:text-rose-300' : 'text-emerald-600 dark:text-emerald-300'}`}>
                  {selectedLogIsBlocked ? 'Bloqueado' : 'Sucesso'}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Usuário</p>
                <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">{selectedLog.usuario}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Origem</p>
                <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">{selectedLog.ip_origem || 'Pessoal'}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Entidade</p>
                <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">{selectedLog.entidade}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Item</p>
                <p className="mt-1 break-all font-mono text-xs font-semibold text-slate-500 dark:text-slate-400">{selectedLog.entidade_id}</p>
              </div>
            </div>

            <div className="border-t border-slate-100 px-6 py-5 dark:border-slate-800">
              <p className="text-[11px] font-bold uppercase text-slate-400 dark:text-slate-500">Resumo seguro</p>
              <p className="mt-2 rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-600 dark:bg-slate-950 dark:text-slate-300">
                {selectedLogSummary || 'Sem resumo adicional para este registro.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
