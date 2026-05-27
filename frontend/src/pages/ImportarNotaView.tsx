import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Archive, Bot, CheckCircle2, FilePlus2, FileText, Loader2, ReceiptText, RefreshCw, ShieldAlert, X } from 'lucide-react';
import { ApiError, apiClient, importarLoteChaves, importarPdfNfce } from '../api/client';
import {
  ArchiveImportacaoRequest,
  ArchiveImportacaoResponse,
  ImportacaoChaveRequest,
  ImportacaoHistoricoItem,
  ImportacaoLoteChavesRequest,
  ImportacaoLoteChavesResponse,
  ImportacaoLoteChaveResultado,
  ImportacoesHistoricoResponse,
  ImportacaoNotaResponse,
} from '../types/api';

interface ImportarNotaViewProps {
  onImported?: () => void;
}

const MAX_BATCH_KEYS = 5;

const qualityBadgeConfig = {
  ok: {
    label: 'Extração confiável',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800',
  },
  warning: {
    label: 'Importação com atenção',
    className: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-800',
  },
  failed: {
    label: 'Extração incompleta',
    className: 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:border-rose-800',
  },
};

const numberLabel = (value: number | string | null | undefined) => {
  if (value === null || value === undefined || value === '') return '-';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(value);
};

const countValue = (value: number | null | undefined) => value ?? 0;

const formatCurrency = (value: number | string | null | undefined) => {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed)
    ? parsed.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
    : 'R$ 0,00';
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('pt-BR');
};

const ImportQualityBadge: React.FC<{ status?: string | null }> = ({ status }) => {
  const normalized = status === 'failed' || status === 'warning' || status === 'ok' ? status : 'warning';
  const config = qualityBadgeConfig[normalized];
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold ${config.className}`}>
      {config.label}
    </span>
  );
};

const ImportQualitySummary: React.FC<{ nota: ImportacaoNotaResponse['nota_fiscal'] }> = ({ nota }) => {
  const messages = [
    nota.extraction_parser_source === 'ai_fallback' ? 'A extração usou fallback de IA.' : null,
    countValue(nota.extraction_missing_ean_count) > 0 ? 'Há produtos sem EAN.' : null,
    nota.extraction_total_mismatch ? 'Há divergência entre a soma dos itens e o total da nota.' : null,
    countValue(nota.extraction_item_count) === 0 ? 'Nenhum item foi extraído.' : null,
    countValue(nota.extraction_invalid_quantity_count) > 0 ? 'Há itens com quantidade inválida.' : null,
    countValue(nota.extraction_invalid_value_count) > 0 ? 'Há itens com valor inválido.' : null,
    countValue(nota.extraction_empty_description_count) > 0 ? 'Há itens sem descrição.' : null,
  ].filter((message): message is string => Boolean(message));

  const parserLabel = nota.extraction_parser_source === 'ai_fallback' ? 'Fallback IA' : 'Determinístico';

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-950/30 p-4 text-slate-700 dark:text-slate-200" role="status" aria-live="polite">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Qualidade da extração</p>
          <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">Origem: {parserLabel}</p>
        </div>
        <ImportQualityBadge status={nota.extraction_quality_status} />
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Itens extraídos</p>
          <p className="mt-1 text-lg font-bold text-slate-900 dark:text-white">{countValue(nota.extraction_item_count)}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Sem EAN</p>
          <p className="mt-1 text-lg font-bold text-slate-900 dark:text-white">{countValue(nota.extraction_missing_ean_count)}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Soma dos itens</p>
          <p className="mt-1 text-lg font-bold text-slate-900 dark:text-white">R$ {numberLabel(nota.extraction_total_itens)}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Total da nota</p>
          <p className="mt-1 text-lg font-bold text-slate-900 dark:text-white">R$ {numberLabel(nota.extraction_total_nota ?? nota.valor_total)}</p>
        </div>
      </div>

      {messages.length > 0 && (
        <ul className="mt-4 space-y-2">
          {messages.map((message) => (
            <li key={message} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
              <AlertCircle size={16} className="mt-0.5 shrink-0 text-amber-500" />
              <span>{message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const compactQualityConfig = {
  ok: {
    label: 'Confiavel',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800',
  },
  warning: {
    label: 'Atencao',
    className: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-800',
  },
  failed: {
    label: 'Incompleta',
    className: 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:border-rose-800',
  },
};

const CompactQualityBadge: React.FC<{ status?: string | null }> = ({ status }) => {
  const normalized = status === 'failed' || status === 'warning' || status === 'ok' ? status : 'warning';
  const config = compactQualityConfig[normalized];
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-bold ${config.className}`}>
      {config.label}
    </span>
  );
};

const batchStatusConfig: Record<ImportacaoLoteChaveResultado['status'], { label: string; className: string }> = {
  success: {
    label: 'Importada',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800',
  },
  duplicate: {
    label: 'Duplicada',
    className: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-800',
  },
  failed: {
    label: 'Falhou',
    className: 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:border-rose-800',
  },
};

const batchQualityConfig = {
  ok: {
    label: 'Confiável',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800',
  },
  warning: {
    label: 'Atenção',
    className: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-800',
  },
  failed: {
    label: 'Incompleta',
    className: 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:border-rose-800',
  },
};

const BatchStatusBadge: React.FC<{ status: ImportacaoLoteChaveResultado['status'] }> = ({ status }) => {
  const config = batchStatusConfig[status];
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-bold ${config.className}`}>
      {config.label}
    </span>
  );
};

const BatchQualityBadge: React.FC<{ status?: string | null }> = ({ status }) => {
  const normalized = status === 'failed' || status === 'warning' || status === 'ok' ? status : 'warning';
  const config = batchQualityConfig[normalized];
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-bold ${config.className}`}>
      {config.label}
    </span>
  );
};

const parseBatchKeys = (value: string) => (
  value
    .split(/[\s,;]+/)
    .map((part) => part.replace(/\D/g, ''))
    .filter(Boolean)
);

const hasDuplicateBatchKeys = (keys: string[]) => new Set(keys).size !== keys.length;

const maskKeyPreview = (key: string) => {
  if (key.includes('...')) return key;
  const onlyNumbers = key.replace(/\D/g, '');
  if (onlyNumbers.length < 8) return 'chave nao informada';
  return `${onlyNumbers.slice(0, 4)}...${onlyNumbers.slice(-4)}`;
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const archived = status === 'archived';
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-bold ${
      archived
        ? 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
        : 'bg-indigo-100 text-indigo-800 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-200 dark:border-indigo-800'
    }`}>
      {archived ? 'Arquivada' : 'Ativa'}
    </span>
  );
};

const readQualityDetails = (details: ImportacaoHistoricoItem['extraction_quality_details']) => {
  if (!details) return {};
  if (typeof details === 'object') return details as Record<string, unknown>;
  try {
    return JSON.parse(details) as Record<string, unknown>;
  } catch {
    return {};
  }
};

const importAlerts = (item: ImportacaoHistoricoItem) => {
  const details = readQualityDetails(item.extraction_quality_details);
  const nestedDetails = typeof details.details === 'object' && details.details !== null
    ? details.details as Record<string, unknown>
    : {};

  return [
    countValue(item.extraction_missing_ean_count) > 0 ? `${item.extraction_missing_ean_count} sem EAN` : null,
    item.extraction_total_mismatch ? 'Total divergente' : null,
    item.extraction_parser_source === 'ai_fallback' ? 'Fallback IA' : null,
    nestedDetails.html_truncated === true ? 'HTML truncado' : null,
  ].filter((message): message is string => Boolean(message));
};

const ImportHistorySection: React.FC<{ refreshKey: number }> = ({ refreshKey }) => {
  const [items, setItems] = useState<ImportacaoHistoricoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'active' | 'archived' | 'all'>('active');
  const [qualityFilter, setQualityFilter] = useState<'all' | 'ok' | 'warning' | 'failed'>('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadImports = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        limit: '20',
        offset: '0',
        status: statusFilter,
        quality_status: qualityFilter,
      });
      const response = await apiClient.get<ImportacoesHistoricoResponse>(`/notas/importacoes?${params.toString()}`);
      setItems(response.items);
      setTotal(response.total);
    } catch {
      setError('Nao foi possivel carregar o historico de importacoes.');
    } finally {
      setLoading(false);
    }
  }, [qualityFilter, statusFilter]);

  useEffect(() => {
    loadImports();
  }, [loadImports, refreshKey]);

  const summary = useMemo(() => ({
    loaded: items.length,
    warning: items.filter((item) => item.extraction_quality_status === 'warning').length,
    failed: items.filter((item) => item.extraction_quality_status === 'failed').length,
    fallback: items.filter((item) => item.extraction_parser_source === 'ai_fallback').length,
  }), [items]);

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
      <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-2xl">
            <ReceiptText size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">Historico de importacoes</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {summary.loaded} de {total} importacao(oes) carregada(s), {summary.warning} com atencao, {summary.failed} incompleta(s), {summary.fallback} via fallback IA.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-sm font-semibold text-slate-700 dark:text-slate-200"
            aria-label="Filtrar por status"
          >
            <option value="active">Ativas</option>
            <option value="archived">Arquivadas</option>
            <option value="all">Todas</option>
          </select>
          <select
            value={qualityFilter}
            onChange={(event) => setQualityFilter(event.target.value as typeof qualityFilter)}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-sm font-semibold text-slate-700 dark:text-slate-200"
            aria-label="Filtrar por qualidade"
          >
            <option value="all">Todas qualidades</option>
            <option value="ok">Confiavel</option>
            <option value="warning">Atencao</option>
            <option value="failed">Incompleta</option>
          </select>
          <button
            type="button"
            onClick={loadImports}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-2xl text-sm font-bold disabled:opacity-50 transition-all"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Atualizar lista
          </button>
        </div>
      </div>

      <div className="p-8">
        {error && (
          <div className="flex items-start gap-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 p-4 rounded-2xl" role="alert">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <p className="text-sm font-semibold">{error}</p>
          </div>
        )}

        {!error && loading && (
          <div className="flex items-center gap-3 text-sm font-semibold text-slate-500 dark:text-slate-400" role="status" aria-live="polite">
            <Loader2 size={18} className="animate-spin" />
            Carregando historico...
          </div>
        )}

        {!error && !loading && items.length === 0 && (
          <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">Nenhuma importacao registrada ainda.</p>
        )}

        {!error && items.length > 0 && (
          <>
            <div className="hidden xl:block overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-slate-950/40 text-[11px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Nota</th>
                    <th className="px-4 py-3">Fornecedor</th>
                    <th className="px-4 py-3">Data</th>
                    <th className="px-4 py-3">Valor</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Qualidade</th>
                    <th className="px-4 py-3">Origem</th>
                    <th className="px-4 py-3">Alertas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {items.map((item) => (
                    <tr key={item.id} className="text-slate-700 dark:text-slate-200">
                      <td className="px-4 py-4">
                        <p className="font-bold">{item.numero_nota}</p>
                        <p className="font-mono text-xs text-slate-400">{maskKeyPreview(item.chave_acesso)}</p>
                      </td>
                      <td className="px-4 py-4 max-w-[240px] truncate">{item.fornecedor}</td>
                      <td className="px-4 py-4">{formatDate(item.data_emissao)}</td>
                      <td className="px-4 py-4 font-semibold">{formatCurrency(item.valor_total)}</td>
                      <td className="px-4 py-4"><StatusBadge status={item.status} /></td>
                      <td className="px-4 py-4"><CompactQualityBadge status={item.extraction_quality_status} /></td>
                      <td className="px-4 py-4">
                        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 dark:text-slate-400">
                          {item.extraction_parser_source === 'ai_fallback' && <Bot size={14} />}
                          {item.extraction_parser_source === 'ai_fallback' ? 'Fallback IA' : 'Deterministico'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-1.5">
                          {importAlerts(item).length > 0 ? importAlerts(item).map((alert) => (
                            <span key={alert} className="rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-200 px-2 py-1 text-[11px] font-bold">
                              {alert}
                            </span>
                          )) : <span className="text-xs text-slate-400">Sem alertas</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="xl:hidden space-y-3">
              {items.map((item) => {
                const alerts = importAlerts(item);
                return (
                  <div key={item.id} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/30 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-slate-900 dark:text-white">Nota {item.numero_nota}</p>
                        <p className="font-mono text-xs text-slate-400 mt-1">{maskKeyPreview(item.chave_acesso)}</p>
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200 truncate">{item.fornecedor}</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-[11px] uppercase tracking-widest text-slate-400 font-bold">Data</p>
                        <p className="font-semibold text-slate-700 dark:text-slate-200">{formatDate(item.data_emissao)}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-widest text-slate-400 font-bold">Valor</p>
                        <p className="font-semibold text-slate-700 dark:text-slate-200">{formatCurrency(item.valor_total)}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-widest text-slate-400 font-bold">Itens</p>
                        <p className="font-semibold text-slate-700 dark:text-slate-200">{countValue(item.extraction_item_count)}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-widest text-slate-400 font-bold">Origem</p>
                        <p className="font-semibold text-slate-700 dark:text-slate-200">{item.extraction_parser_source === 'ai_fallback' ? 'Fallback IA' : 'Deterministico'}</p>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <CompactQualityBadge status={item.extraction_quality_status} />
                      {alerts.length > 0 ? alerts.map((alert) => (
                        <span key={alert} className="rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-200 px-2 py-1 text-[11px] font-bold">
                          {alert}
                        </span>
                      )) : <span className="text-xs font-semibold text-slate-400">Sem alertas</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const resolvePdfError = (err: unknown): string => {
  if (err instanceof ApiError) {
    const msg = (err.message || '').toLowerCase();
    if (msg.includes('ja cadastrada') || msg.includes('já cadastrada') || msg.includes('duplicada') || err.status === 409) {
      return 'Nota fiscal já cadastrada.';
    }
    if (msg.includes('texto') || msg.includes('escaneado') || msg.includes('imagem') || msg.includes('extraível')) {
      return 'Este PDF não possui texto extraível. Use o PDF detalhado baixado da SEFAZ.';
    }
    if (msg.includes('inválido') || msg.includes('invalido') || msg.includes('reconhecido') || msg.includes('não parece ser') || msg.includes('nao parece ser') || msg.includes('tabela ausente') || msg.includes('fiscal') || msg.includes('estrutura') || msg.includes('produtos') || msg.includes('chave') || msg.includes('emissão') || msg.includes('cnpj')) {
      return 'O arquivo enviado não parece ser uma NFC-e detalhada da SEFAZ.';
    }
  }
  return 'Não foi possível importar a nota fiscal. Verifique o arquivo e tente novamente.';
};

export const ImportarNotaView: React.FC<ImportarNotaViewProps> = ({ onImported }) => {
  const [chaveAcesso, setChaveAcesso] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<ImportacaoNotaResponse | null>(null);
  const [error, setError] = useState('');

  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfSuccess, setPdfSuccess] = useState<ImportacaoNotaResponse | null>(null);
  const [pdfError, setPdfError] = useState('');

  const [batchKeysInput, setBatchKeysInput] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchResult, setBatchResult] = useState<ImportacaoLoteChavesResponse | null>(null);
  const [batchError, setBatchError] = useState('');
  const [archiveChave, setArchiveChave] = useState('');
  const [archiveMotivo, setArchiveMotivo] = useState('');
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveSuccess, setArchiveSuccess] = useState<ArchiveImportacaoResponse | null>(null);
  const [archiveError, setArchiveError] = useState('');
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const validationMessage = useMemo(() => {
    if (!chaveAcesso) return '';
    if (!/^\d+$/.test(chaveAcesso)) return 'Use apenas numeros.';
    if (chaveAcesso.length !== 44) return 'A chave de acesso deve ter 44 digitos.';
    return '';
  }, [chaveAcesso]);

  const isValid = chaveAcesso.length === 44 && !validationMessage;

  const batchKeys = useMemo(() => parseBatchKeys(batchKeysInput), [batchKeysInput]);

  const batchValidationMessage = useMemo(() => {
    if (!batchKeysInput.trim()) return '';
    if (batchKeys.length === 0) return 'Informe pelo menos uma chave de acesso.';
    if (batchKeys.length > MAX_BATCH_KEYS) return `Informe no maximo ${MAX_BATCH_KEYS} chaves por lote.`;
    if (hasDuplicateBatchKeys(batchKeys)) return 'Remova chaves duplicadas antes de importar.';
    const invalidIndex = batchKeys.findIndex((key) => key.length !== 44);
    if (invalidIndex >= 0) return `A chave ${invalidIndex + 1} deve ter 44 digitos.`;
    return '';
  }, [batchKeys, batchKeysInput]);

  const isBatchValid = batchKeys.length >= 1 && batchKeys.length <= MAX_BATCH_KEYS && !batchValidationMessage;

  const archiveChaveValidation = useMemo(() => {
    if (!archiveChave) return '';
    if (!/^\d+$/.test(archiveChave)) return 'Use apenas numeros.';
    if (archiveChave.length !== 44) return 'A chave de acesso deve ter 44 digitos.';
    return '';
  }, [archiveChave]);

  const archiveMotivoTrimmed = archiveMotivo.trim();
  const archiveMotivoValidation = useMemo(() => {
    if (!archiveMotivo) return '';
    if (archiveMotivoTrimmed.length < 5) return 'Informe um motivo com pelo menos 5 caracteres.';
    if (archiveMotivoTrimmed.length > 500) return 'O motivo deve ter no maximo 500 caracteres.';
    return '';
  }, [archiveMotivo, archiveMotivoTrimmed]);

  const isArchiveValid = archiveChave.length === 44 && !archiveChaveValidation && archiveMotivoTrimmed.length >= 5 && archiveMotivoTrimmed.length <= 500;

  const maskKey = (key: string) => {
    if (key.length < 8) return 'chave nao informada';
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const onlyNumbers = event.target.value.replace(/\D/g, '').slice(0, 44);
    setChaveAcesso(onlyNumbers);
    setError('');
    setSuccess(null);
  };

  const handleBatchKeysChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setBatchKeysInput(event.target.value);
    setBatchError('');
    setBatchResult(null);
  };

  const handleArchiveChaveChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const onlyNumbers = event.target.value.replace(/\D/g, '').slice(0, 44);
    setArchiveChave(onlyNumbers);
    setArchiveError('');
    setArchiveSuccess(null);
  };

  const handleArchiveMotivoChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setArchiveMotivo(event.target.value.slice(0, 500));
    setArchiveError('');
    setArchiveSuccess(null);
  };

  const handlePdfChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setPdfFile(file);
    setPdfError('');
    setPdfSuccess(null);
  };

  const handlePdfSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setPdfError('');
    setPdfSuccess(null);

    if (!pdfFile) {
      setPdfError('Selecione um arquivo PDF.');
      return;
    }

    setPdfLoading(true);
    try {
      const response = await importarPdfNfce(pdfFile);
      setPdfSuccess(response);
      setPdfFile(null);
      setHistoryRefreshKey((value) => value + 1);
      onImported?.();
    } catch (err) {
      setPdfError(resolvePdfError(err));
    } finally {
      setPdfLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setSuccess(null);

    if (!chaveAcesso) {
      setError('Informe a chave de acesso da nota fiscal.');
      return;
    }

    if (!isValid) {
      setError(validationMessage || 'Verifique a chave de acesso informada.');
      return;
    }

    setLoading(true);
    try {
      const payload: ImportacaoChaveRequest = { chave_acesso: chaveAcesso };
      const response = await apiClient.post<ImportacaoNotaResponse>('/notas/importacao-por-chave', payload);
      setSuccess(response);
      setChaveAcesso('');
      setHistoryRefreshKey((value) => value + 1);
      onImported?.();
    } catch {
      setError('Nao foi possivel importar a nota. Confira a chave, tente novamente ou consulte a SEFAZ mais tarde.');
    } finally {
      setLoading(false);
    }
  };

  const handleBatchSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBatchError('');
    setBatchResult(null);

    if (!batchKeysInput.trim() || batchKeys.length === 0) {
      setBatchError('Informe pelo menos uma chave de acesso.');
      return;
    }

    if (!isBatchValid) {
      setBatchError(batchValidationMessage || 'Verifique as chaves informadas.');
      return;
    }

    setBatchLoading(true);
    try {
      const payload: ImportacaoLoteChavesRequest = { chaves_acesso: batchKeys };
      const response = await importarLoteChaves(payload);
      setBatchResult(response);
      setBatchKeysInput('');
      setHistoryRefreshKey((value) => value + 1);
      onImported?.();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
        setBatchError('Verifique as chaves informadas. Cada chave deve ter 44 digitos validos e nao pode estar duplicada.');
      } else {
        setBatchError('Nao foi possivel importar o lote. Tente novamente ou consulte a SEFAZ mais tarde.');
      }
    } finally {
      setBatchLoading(false);
    }
  };

  const resolveArchiveError = (err: unknown) => {
    if (err instanceof ApiError) {
      if (err.status === 403) return 'Usuario sem permissao para arquivar importacoes.';
      if (err.status === 404) return 'Importacao nao encontrada.';
      if (err.status === 409) return 'Esta importacao ja esta arquivada.';
      if (err.status === 400 || err.status === 422) return 'Verifique a chave e o motivo informado.';
    }
    return 'Nao foi possivel arquivar a importacao. Tente novamente mais tarde.';
  };

  const handleArchiveSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setArchiveError('');
    setArchiveSuccess(null);

    if (!archiveChave) {
      setArchiveError('Informe a chave de acesso da nota fiscal.');
      return;
    }

    if (archiveChaveValidation) {
      setArchiveError(archiveChaveValidation);
      return;
    }

    if (!archiveMotivoTrimmed) {
      setArchiveError('Informe o motivo do archive.');
      return;
    }

    if (archiveMotivoValidation) {
      setArchiveError(archiveMotivoValidation);
      return;
    }

    setShowArchiveConfirm(true);
  };

  const confirmArchive = async () => {
    if (archiveLoading || !isArchiveValid) return;

    setArchiveLoading(true);
    setArchiveError('');
    setArchiveSuccess(null);
    try {
      const payload: ArchiveImportacaoRequest = { motivo: archiveMotivoTrimmed };
      const response = await apiClient.post<ArchiveImportacaoResponse>(`/notas/${archiveChave}/archive`, payload);
      setArchiveSuccess(response);
      setArchiveChave('');
      setArchiveMotivo('');
      setShowArchiveConfirm(false);
      setHistoryRefreshKey((value) => value + 1);
      onImported?.();
    } catch (err) {
      setArchiveError(resolveArchiveError(err));
      setShowArchiveConfirm(false);
    } finally {
      setArchiveLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight">Importar Nota</h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Informe a chave de acesso da NF-e ou NFC-e para incluir a nota no dashboard e no catalogo.
        </p>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex items-start gap-4">
          <div className="p-3 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-2xl">
            <FilePlus2 size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">Nova importacao por chave</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              A chave possui 44 digitos e fica no DANFE ou no QR Code da nota.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6" noValidate>
          <div className="space-y-2">
            <label htmlFor="chave-acesso" className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Chave de acesso
            </label>
            <div className="relative">
              <ReceiptText className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 dark:text-slate-600" size={20} />
              <input
                id="chave-acesso"
                type="text"
                inputMode="numeric"
                pattern="\d{44}"
                maxLength={44}
                value={chaveAcesso}
                onChange={handleChange}
                aria-describedby="chave-acesso-help"
                aria-invalid={Boolean(error || validationMessage)}
                placeholder="Digite os 44 digitos da chave"
                className="w-full pl-12 pr-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-2xl outline-none focus:border-indigo-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm font-mono tracking-wider text-slate-900 dark:text-white"
              />
            </div>
            <div id="chave-acesso-help" className="flex items-center justify-between gap-3 text-xs">
              <span className={validationMessage ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-slate-400 dark:text-slate-500'}>
                {validationMessage || 'Somente numeros. Nenhum dado real e exibido antes da confirmacao.'}
              </span>
              <span className="font-mono text-slate-400 dark:text-slate-500">{chaveAcesso.length}/44</span>
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 p-4 rounded-2xl" role="alert">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm font-semibold">{error}</p>
            </div>
          )}

          {success && (
            <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300 p-4 rounded-2xl" role="status" aria-live="polite">
              <div className="flex items-start gap-3">
                <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
                <div className="text-sm">
                  <p className="font-bold">Nota importada com sucesso.</p>
                  <p className="mt-1">
                    Nota {success.nota_fiscal.numero_nota} de {success.fornecedor.razao_social} com {success.total_itens} item(ns).
                  </p>
                </div>
              </div>
              <ImportQualitySummary nota={success.nota_fiscal} />
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              type="submit"
              disabled={loading || !isValid}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-900/10"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <FilePlus2 size={18} />}
              {loading ? 'Importando...' : 'Importar'}
            </button>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Apos a importacao, os dados do painel e catalogo serao atualizados automaticamente.
            </p>
          </div>
        </form>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex items-start gap-4">
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-2xl">
            <FileText size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">Importar PDF da NFC-e</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Envie o PDF detalhado da NFC-e (com produtos) baixado da SEFAZ.
            </p>
          </div>
        </div>

        <form onSubmit={handlePdfSubmit} className="p-8 space-y-6" noValidate>
          <div className="space-y-2">
            <label htmlFor="arquivo-pdf" className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Arquivo PDF
            </label>
            <input
              id="arquivo-pdf"
              type="file"
              accept="application/pdf"
              onChange={handlePdfChange}
              className="block w-full text-sm text-slate-500 dark:text-slate-400
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                dark:file:bg-blue-900/20 dark:file:text-blue-400
                hover:file:bg-blue-100 dark:hover:file:bg-blue-900/30"
            />
          </div>

          {pdfError && (
            <div className="flex items-start gap-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 p-4 rounded-2xl" role="alert">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm font-semibold">{pdfError}</p>
            </div>
          )}

          {pdfSuccess && (
            <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300 p-4 rounded-2xl" role="status" aria-live="polite">
              <div className="flex items-start gap-3">
                <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
                <div className="text-sm">
                  <p className="font-bold">Nota fiscal importada com sucesso.</p>
                  <p className="mt-1">
                    Fornecedor: {pdfSuccess.fornecedor.razao_social}<br/>
                    Número: {pdfSuccess.nota_fiscal.numero_nota || 'Não informado'}<br/>
                    Data de emissão: {formatDate(pdfSuccess.nota_fiscal.data_emissao)}<br/>
                    Valor total: {formatCurrency(pdfSuccess.nota_fiscal.valor_total)}<br/>
                    Itens extraídos: {countValue(pdfSuccess.total_itens)}<br/>
                    Total dos itens: {formatCurrency(pdfSuccess.nota_fiscal.extraction_total_itens)}<br/>
                    Qualidade da extração: {pdfSuccess.nota_fiscal.extraction_quality_status || 'Não informado'}
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              type="submit"
              disabled={pdfLoading || !pdfFile}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-2xl text-sm font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-900/10"
            >
              {pdfLoading ? <Loader2 size={18} className="animate-spin" /> : <FileText size={18} />}
              {pdfLoading ? 'Importando PDF...' : 'Importar PDF'}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex items-start gap-4">
          <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-2xl">
            <ReceiptText size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">Importar várias chaves</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Cole ate 5 chaves NF-e ou NFC-e separadas por linha, espaco, virgula ou ponto e virgula.
            </p>
          </div>
        </div>

        <form onSubmit={handleBatchSubmit} className="p-8 space-y-6" noValidate>
          <div className="space-y-2">
            <label htmlFor="batch-chaves-acesso" className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Chaves de acesso
            </label>
            <textarea
              id="batch-chaves-acesso"
              value={batchKeysInput}
              onChange={handleBatchKeysChange}
              rows={6}
              aria-describedby="batch-chaves-help"
              aria-invalid={Boolean(batchError || batchValidationMessage)}
              placeholder="Cole uma chave por linha ou separe por espaco, virgula ou ponto e virgula"
              className="w-full px-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-2xl outline-none focus:border-emerald-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm font-mono tracking-wider text-slate-900 dark:text-white resize-y min-h-[160px]"
            />
            <div id="batch-chaves-help" className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-xs">
              <span className={batchValidationMessage ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-slate-400 dark:text-slate-500'}>
                {batchValidationMessage || 'Caracteres nao numericos sao removidos de cada chave antes do envio.'}
              </span>
              <span className={`font-mono ${batchKeys.length > MAX_BATCH_KEYS ? 'text-amber-600 dark:text-amber-400 font-bold' : 'text-slate-400 dark:text-slate-500'}`}>
                {batchKeys.length} de {MAX_BATCH_KEYS} chaves
              </span>
            </div>
          </div>

          {batchKeys.length > 0 && (
            <div className="flex flex-wrap gap-2" aria-label="Previa mascarada das chaves normalizadas">
              {batchKeys.slice(0, MAX_BATCH_KEYS).map((key, index) => (
                <span key={`${key}-${index}`} className="inline-flex max-w-full items-center rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs font-mono font-semibold text-slate-500 dark:text-slate-300">
                  {maskKeyPreview(key)}
                </span>
              ))}
              {batchKeys.length > MAX_BATCH_KEYS && (
                <span className="inline-flex items-center rounded-full bg-amber-50 dark:bg-amber-900/20 px-3 py-1 text-xs font-bold text-amber-700 dark:text-amber-200">
                  +{batchKeys.length - MAX_BATCH_KEYS} acima do limite
                </span>
              )}
            </div>
          )}

          {batchError && (
            <div className="flex items-start gap-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 p-4 rounded-2xl" role="alert">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm font-semibold">{batchError}</p>
            </div>
          )}

          {batchLoading && (
            <div className="flex items-center gap-3 text-sm font-semibold text-slate-500 dark:text-slate-400" role="status" aria-live="polite">
              <Loader2 size={18} className="animate-spin" />
              Processando lote...
            </div>
          )}

          {batchResult && (
            <div className="space-y-5" role="status" aria-live="polite">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-2xl bg-slate-50 dark:bg-slate-950/30 border border-slate-100 dark:border-slate-800 p-4">
                  <p className="text-[11px] uppercase tracking-widest text-slate-400 dark:text-slate-500 font-bold">Total</p>
                  <p className="mt-1 text-xl font-bold text-slate-900 dark:text-white">{batchResult.total}</p>
                </div>
                <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/40 p-4">
                  <p className="text-[11px] uppercase tracking-widest text-emerald-700 dark:text-emerald-200 font-bold">Importadas</p>
                  <p className="mt-1 text-xl font-bold text-emerald-800 dark:text-emerald-100">{batchResult.success_count}</p>
                </div>
                <div className="rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-900/40 p-4">
                  <p className="text-[11px] uppercase tracking-widest text-amber-700 dark:text-amber-200 font-bold">Duplicadas</p>
                  <p className="mt-1 text-xl font-bold text-amber-800 dark:text-amber-100">{batchResult.duplicate_count}</p>
                </div>
                <div className="rounded-2xl bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 p-4">
                  <p className="text-[11px] uppercase tracking-widest text-rose-700 dark:text-rose-200 font-bold">Falhas</p>
                  <p className="mt-1 text-xl font-bold text-rose-800 dark:text-rose-100">{batchResult.failed_count}</p>
                </div>
              </div>

              <div className="hidden md:block overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-950/40 text-[11px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Chave</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Qualidade</th>
                      <th className="px-4 py-3">Mensagem</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {batchResult.results.map((result, index) => (
                      <tr key={`${result.chave_acesso}-${index}`} className="text-slate-700 dark:text-slate-200">
                        <td className="px-4 py-4 font-mono text-xs text-slate-500 dark:text-slate-400">{maskKeyPreview(result.chave_acesso)}</td>
                        <td className="px-4 py-4"><BatchStatusBadge status={result.status} /></td>
                        <td className="px-4 py-4">
                          {result.status === 'success' && result.nota_fiscal
                            ? <BatchQualityBadge status={result.nota_fiscal.extraction_quality_status} />
                            : <span className="text-xs font-semibold text-slate-400">Nao aplicavel</span>}
                        </td>
                        <td className="px-4 py-4 max-w-[360px] text-sm text-slate-600 dark:text-slate-300 break-words">{result.mensagem}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="md:hidden space-y-3">
                {batchResult.results.map((result, index) => (
                  <div key={`${result.chave_acesso}-${index}`} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/30 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[11px] uppercase tracking-widest text-slate-400 font-bold">Chave</p>
                        <p className="mt-1 font-mono text-xs text-slate-500 dark:text-slate-400 break-words">{maskKeyPreview(result.chave_acesso)}</p>
                      </div>
                      <BatchStatusBadge status={result.status} />
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200 break-words">{result.mensagem}</p>
                    {result.status === 'success' && result.nota_fiscal && (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Qualidade</span>
                        <BatchQualityBadge status={result.nota_fiscal.extraction_quality_status} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              type="submit"
              disabled={batchLoading || !isBatchValid}
              className="inline-flex min-h-11 items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-2xl text-sm font-bold hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-900/10"
            >
              {batchLoading ? <Loader2 size={18} className="animate-spin" /> : <FilePlus2 size={18} />}
              {batchLoading ? 'Importando lote...' : 'Importar lote'}
            </button>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Ao concluir, o historico, dashboard e catalogo sao atualizados automaticamente.
            </p>
          </div>
        </form>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden transition-colors">
        <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex items-start gap-4">
          <div className="p-3 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 rounded-2xl">
            <Archive size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white">Arquivar importacao por chave</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Arquive uma importacao sem excluir fisicamente a nota, itens, historico ou auditoria.
            </p>
          </div>
        </div>

        <form onSubmit={handleArchiveSubmit} className="p-8 space-y-6" noValidate>
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-6">
            <div className="space-y-2">
              <label htmlFor="archive-chave-acesso" className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Chave de acesso
              </label>
              <div className="relative">
                <ReceiptText className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 dark:text-slate-600" size={20} />
                <input
                  id="archive-chave-acesso"
                  type="text"
                  inputMode="numeric"
                  pattern="\d{44}"
                  maxLength={44}
                  value={archiveChave}
                  onChange={handleArchiveChaveChange}
                  aria-describedby="archive-chave-help"
                  aria-invalid={Boolean(archiveError || archiveChaveValidation)}
                  placeholder="Digite os 44 digitos da chave"
                  className="w-full pl-12 pr-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-2xl outline-none focus:border-amber-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm font-mono tracking-wider text-slate-900 dark:text-white"
                />
              </div>
              <div id="archive-chave-help" className="flex items-center justify-between gap-3 text-xs">
                <span className={archiveChaveValidation ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-slate-400 dark:text-slate-500'}>
                  {archiveChaveValidation || 'A chave completa nao sera exibida apos o envio.'}
                </span>
                <span className="font-mono text-slate-400 dark:text-slate-500">{archiveChave.length}/44</span>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="archive-motivo" className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Motivo obrigatorio
              </label>
              <textarea
                id="archive-motivo"
                value={archiveMotivo}
                onChange={handleArchiveMotivoChange}
                minLength={5}
                maxLength={500}
                rows={4}
                aria-describedby="archive-motivo-help"
                aria-invalid={Boolean(archiveError || archiveMotivoValidation)}
                placeholder="Descreva o motivo operacional do archive"
                className="w-full px-4 py-4 bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-100 dark:border-slate-800 rounded-2xl outline-none focus:border-amber-500 focus:bg-white dark:focus:bg-slate-800 transition-all text-sm text-slate-900 dark:text-white resize-none"
              />
              <div id="archive-motivo-help" className="flex items-center justify-between gap-3 text-xs">
                <span className={archiveMotivoValidation ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-slate-400 dark:text-slate-500'}>
                  {archiveMotivoValidation || 'Use de 5 a 500 caracteres.'}
                </span>
                <span className="font-mono text-slate-400 dark:text-slate-500">{archiveMotivo.length}/500</span>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-900/40 text-amber-800 dark:text-amber-200 p-4 rounded-2xl">
            <ShieldAlert size={18} className="mt-0.5 shrink-0" />
            <p className="text-sm font-semibold">
              A nota arquivada deixa de compor dashboard, alertas, insights e catalogo operacional. Nada e excluido fisicamente.
            </p>
          </div>

          {archiveError && (
            <div className="flex items-start gap-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300 p-4 rounded-2xl" role="alert">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm font-semibold">{archiveError}</p>
            </div>
          )}

          {archiveSuccess && (
            <div className="flex items-start gap-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300 p-4 rounded-2xl" role="status" aria-live="polite">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
              <div className="text-sm">
                <p className="font-bold">Importacao arquivada com sucesso.</p>
                <p className="mt-1">
                  Chave {archiveSuccess.chave_acesso}. Status {archiveSuccess.status}. Motivo: {archiveSuccess.archive_reason}
                </p>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              type="submit"
              disabled={archiveLoading || !isArchiveValid}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-amber-600 text-white rounded-2xl text-sm font-bold hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-amber-900/10"
            >
              {archiveLoading ? <Loader2 size={18} className="animate-spin" /> : <Archive size={18} />}
              {archiveLoading ? 'Arquivando...' : 'Arquivar importacao'}
            </button>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Uma confirmacao sera solicitada antes de enviar a operacao.
            </p>
          </div>
        </form>
      </div>

      <ImportHistorySection refreshKey={historyRefreshKey} />

      {showArchiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="archive-confirm-title">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2.5 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 rounded-2xl">
                  <ShieldAlert size={22} />
                </div>
                <div>
                  <h3 id="archive-confirm-title" className="text-lg font-bold text-slate-900 dark:text-white">Confirmar archive</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Chave {maskKey(archiveChave)}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowArchiveConfirm(false)}
                disabled={archiveLoading}
                className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50"
                aria-label="Fechar confirmacao"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                A nota sera arquivada e deixara de compor dashboard, alertas, insights e catalogo operacional. Nada sera excluido fisicamente.
              </p>
              <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 rounded-2xl p-4">
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">Motivo</p>
                <p className="text-sm text-slate-700 dark:text-slate-200 mt-1 whitespace-pre-wrap">{archiveMotivoTrimmed}</p>
              </div>
            </div>
            <div className="p-6 bg-slate-50 dark:bg-slate-950/40 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowArchiveConfirm(false)}
                disabled={archiveLoading}
                className="px-5 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 rounded-2xl text-sm font-bold hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-all"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmArchive}
                disabled={archiveLoading}
                className="inline-flex items-center justify-center gap-2 px-5 py-3 bg-amber-600 text-white rounded-2xl text-sm font-bold hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {archiveLoading ? <Loader2 size={18} className="animate-spin" /> : <Archive size={18} />}
                {archiveLoading ? 'Arquivando...' : 'Confirmar archive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
