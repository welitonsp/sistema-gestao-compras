import React, { useMemo, useState } from 'react';
import { AlertCircle, Archive, CheckCircle2, FilePlus2, Loader2, ReceiptText, ShieldAlert, X } from 'lucide-react';
import { ApiError, apiClient } from '../api/client';
import {
  ArchiveImportacaoRequest,
  ArchiveImportacaoResponse,
  ImportacaoChaveRequest,
  ImportacaoNotaResponse,
} from '../types/api';

interface ImportarNotaViewProps {
  onImported?: () => void;
}

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

export const ImportarNotaView: React.FC<ImportarNotaViewProps> = ({ onImported }) => {
  const [chaveAcesso, setChaveAcesso] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<ImportacaoNotaResponse | null>(null);
  const [error, setError] = useState('');
  const [archiveChave, setArchiveChave] = useState('');
  const [archiveMotivo, setArchiveMotivo] = useState('');
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveSuccess, setArchiveSuccess] = useState<ArchiveImportacaoResponse | null>(null);
  const [archiveError, setArchiveError] = useState('');
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);

  const validationMessage = useMemo(() => {
    if (!chaveAcesso) return '';
    if (!/^\d+$/.test(chaveAcesso)) return 'Use apenas numeros.';
    if (chaveAcesso.length !== 44) return 'A chave de acesso deve ter 44 digitos.';
    return '';
  }, [chaveAcesso]);

  const isValid = chaveAcesso.length === 44 && !validationMessage;

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
      onImported?.();
    } catch {
      setError('Nao foi possivel importar a nota. Confira a chave, tente novamente ou consulte a SEFAZ mais tarde.');
    } finally {
      setLoading(false);
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
