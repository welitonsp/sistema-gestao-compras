import React, { useEffect, useState } from 'react';
import { AlertCircle, Hash, Loader2, RotateCcw, ShieldCheck, X } from 'lucide-react';
import { ApiError, apiClient } from '../api/client';
import type {
  CanonizationRevertRequest,
  CanonizationRevertResponse,
  Produto,
} from '../types/api';

interface RevertCanonizationModalProps {
  produto: Produto | null;
  onClose: () => void;
  onSuccess: () => void;
}

const resolveRevertError = (err: unknown): string => {
  if (err instanceof ApiError) {
    if (err.status === 400) return 'Nao foi possivel confirmar a reversao.';
    if (err.status === 403) return 'Voce nao tem permissao para reverter este mapeamento.';
    if (err.status === 404) return 'Mapeamento ativo nao encontrado.';
    if (err.status === 409) return 'Este mapeamento nao esta mais ativo ou ja foi revertido.';
    if (err.message) return err.message;
  }

  return 'Nao foi possivel reverter a canonizacao. Tente novamente.';
};

export const RevertCanonizationModal: React.FC<RevertCanonizationModalProps> = ({
  produto,
  onClose,
  onSuccess,
}) => {
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (produto) {
      setReason('');
      setError('');
      setLoading(false);
    }
  }, [produto]);

  if (!produto?.canonizacao) return null;

  const handleClose = () => {
    if (loading) return;
    setReason('');
    setError('');
    onClose();
  };

  const handleConfirm = async () => {
    const normalizedReason = reason.trim();
    if (!normalizedReason) {
      setError('Informe o motivo da reversao para continuar.');
      return;
    }

    setLoading(true);
    setError('');

    const payload: CanonizationRevertRequest = {
      ean_original: produto.canonizacao!.ean_original,
      reason: normalizedReason,
      confirmed: true,
    };

    try {
      await apiClient.post<CanonizationRevertResponse>(
        '/produtos/canonization/revert',
        payload,
      );
      setReason('');
      setError('');
      onSuccess();
      onClose();
    } catch (err) {
      setError(resolveRevertError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revert-canonization-title"
    >
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6 dark:border-slate-800">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl bg-amber-50 p-2.5 text-amber-600 dark:bg-amber-900/20 dark:text-amber-300">
              <RotateCcw size={22} aria-hidden="true" />
            </div>
            <div>
              <h3 id="revert-canonization-title" className="text-lg font-bold text-slate-900 dark:text-white">
                Reverter Canonização de Produto
              </h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {produto.nome_limpo}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            aria-label="Fechar reversao de canonizacao"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/60">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                EAN original
              </p>
              <p className="mt-2 flex items-center gap-1.5 break-all font-mono text-sm font-bold text-slate-700 dark:text-slate-200">
                <Hash size={13} aria-hidden="true" />
                {produto.canonizacao.ean_original}
              </p>
            </div>
            <div className="rounded-2xl border border-primary-100 bg-primary-50/60 p-4 dark:border-primary-800/50 dark:bg-primary-900/20">
              <p className="text-[10px] font-bold uppercase tracking-widest text-primary-500 dark:text-primary-300">
                EAN canônico alvo
              </p>
              <p className="mt-2 flex items-center gap-1.5 break-all font-mono text-sm font-bold text-slate-800 dark:text-slate-100">
                <Hash size={13} aria-hidden="true" />
                {produto.canonizacao.ean_canonico}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-100">
            <div className="flex items-start gap-3">
              <ShieldCheck size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div className="space-y-1.5 font-medium leading-relaxed">
                <p>Os dados fiscais originais não serão alterados.</p>
                <p>O produto original continuará no catálogo.</p>
                <p>Após a reversão, dashboards e relatórios voltarão a considerar este EAN separadamente.</p>
                <p>A ação será registrada em auditoria.</p>
              </div>
            </div>
          </div>

          <label className="block">
            <span className="text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Motivo da reversão
            </span>
            <textarea
              value={reason}
              onChange={(event) => {
                setReason(event.target.value);
                if (error && event.target.value.trim()) setError('');
              }}
              disabled={loading}
              maxLength={500}
              rows={4}
              className="mt-2 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none transition-all focus:border-primary-500 focus:bg-white focus:ring-4 focus:ring-primary-100 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:bg-slate-800 dark:focus:ring-primary-900/20"
              placeholder="Descreva por que este mapeamento deve ser revertido"
              required
            />
            <span className="mt-1 block text-right text-[11px] font-bold text-slate-400 dark:text-slate-500">
              {reason.length}/500
            </span>
          </label>

          {error && (
            <div
              className="flex items-start gap-3 rounded-2xl border border-rose-100 bg-rose-50 p-4 text-rose-700 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-300"
              role="alert"
            >
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p className="text-sm font-semibold">{error}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col justify-end gap-3 border-t border-slate-100 bg-slate-50 p-6 dark:border-slate-800 dark:bg-slate-950/40 sm:flex-row">
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-600 transition-all hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading || !reason.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-amber-600 px-5 py-3 text-sm font-bold text-white transition-all hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : <RotateCcw size={18} aria-hidden="true" />}
            {loading ? 'Revertendo...' : 'Confirmar Reversão'}
          </button>
        </div>
      </div>
    </div>
  );
};
