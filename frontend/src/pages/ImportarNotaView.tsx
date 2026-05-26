import React, { useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, FilePlus2, Loader2, ReceiptText } from 'lucide-react';
import { apiClient } from '../api/client';
import { ImportacaoChaveRequest, ImportacaoNotaResponse } from '../types/api';

interface ImportarNotaViewProps {
  onImported?: () => void;
}

export const ImportarNotaView: React.FC<ImportarNotaViewProps> = ({ onImported }) => {
  const [chaveAcesso, setChaveAcesso] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<ImportacaoNotaResponse | null>(null);
  const [error, setError] = useState('');

  const validationMessage = useMemo(() => {
    if (!chaveAcesso) return '';
    if (!/^\d+$/.test(chaveAcesso)) return 'Use apenas numeros.';
    if (chaveAcesso.length !== 44) return 'A chave de acesso deve ter 44 digitos.';
    return '';
  }, [chaveAcesso]);

  const isValid = chaveAcesso.length === 44 && !validationMessage;

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const onlyNumbers = event.target.value.replace(/\D/g, '').slice(0, 44);
    setChaveAcesso(onlyNumbers);
    setError('');
    setSuccess(null);
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
            <div className="flex items-start gap-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300 p-4 rounded-2xl" role="status" aria-live="polite">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
              <div className="text-sm">
                <p className="font-bold">Nota importada com sucesso.</p>
                <p className="mt-1">
                  Nota {success.nota_fiscal.numero_nota} de {success.fornecedor.razao_social} com {success.total_itens} item(ns).
                </p>
              </div>
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
    </div>
  );
};
