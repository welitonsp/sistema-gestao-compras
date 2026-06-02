import React, { useEffect, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Hash,
  Info,
  Layers,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { apiClient } from "../api/client";
import type {
  CategorySuggestionCandidate,
  CategorySuggestionCandidatesResponse,
} from "../types/api";
import { Skeleton } from "./Skeleton";

const confidenceLabels: Record<
  CategorySuggestionCandidate["confidence_level"],
  string
> = {
  high: "Alta confiança",
  medium: "Confiança média",
  low: "Baixa confiança",
  insufficient_data: "Dados insuficientes",
};

const sourceLabels: Record<CategorySuggestionCandidate["source"], string> = {
  item_suggestion: "Sugestão de itens",
  classification_cache: "Histórico confirmado",
  rules: "Regra determinística",
  none: "Sem origem suficiente",
};

const confidenceClasses: Record<
  CategorySuggestionCandidate["confidence_level"],
  string
> = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800/50",
  medium:
    "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800/50",
  low: "bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800/50",
  insufficient_data:
    "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
};

const formatPercent = (value: number) =>
  `${Math.max(0, Math.min(100, Number(value || 0) * 100)).toLocaleString(
    "pt-BR",
    {
      maximumFractionDigits: 1,
    },
  )}%`;

const formatDate = (value: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("pt-BR");
};

export const CategoryReviewTab: React.FC = () => {
  const [data, setData] =
    useState<CategorySuggestionCandidatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [confirmingByEan, setConfirmingByEan] = useState<
    Record<string, boolean>
  >({});
  const [errorByEan, setErrorByEan] = useState<Record<string, boolean>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchCandidates = async () => {
    setLoading(true);
    setError(false);
    try {
      const response =
        await apiClient.get<CategorySuggestionCandidatesResponse>(
          "/produtos/categorization/candidates?limit=25",
        );
      setData(response);
    } catch {
      setData(null);
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, []);

  const handleConfirmSuggestion = async (
    candidate: CategorySuggestionCandidate,
  ) => {
    if (
      !candidate.can_confirm ||
      !candidate.suggested_category ||
      confirmingByEan[candidate.ean]
    ) {
      return;
    }

    setConfirmingByEan((current) => ({ ...current, [candidate.ean]: true }));
    setErrorByEan((current) => ({ ...current, [candidate.ean]: false }));
    setSuccessMessage(null);

    try {
      await apiClient.patch(`/produtos/${encodeURIComponent(candidate.ean)}`, {
        categoria: candidate.suggested_category,
      });

      setData((current) => {
        if (!current) return current;

        const nextCandidates = current.candidates.filter(
          (item) => item.ean !== candidate.ean,
        );

        return {
          ...current,
          total_candidates: Math.max(0, current.total_candidates - 1),
          returned_count: nextCandidates.length,
          candidates: nextCandidates,
        };
      });
      setSuccessMessage("Categoria confirmada.");
    } catch {
      setErrorByEan((current) => ({ ...current, [candidate.ean]: true }));
    } finally {
      setConfirmingByEan((current) => ({ ...current, [candidate.ean]: false }));
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-44 rounded-3xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-8 text-center">
        <Info
          size={40}
          className="mx-auto mb-4 text-amber-500"
          aria-hidden="true"
        />
        <h3 className="font-bold text-slate-800 dark:text-white">
          Não foi possível carregar a revisão agora
        </h3>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Tente novamente em alguns instantes.
        </p>
        <button
          onClick={fetchCandidates}
          className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-600 text-white text-xs font-bold uppercase tracking-widest hover:bg-primary-700 transition-colors"
        >
          <RefreshCw size={14} aria-hidden="true" />
          Tentar novamente
        </button>
      </div>
    );
  }

  const candidates = data?.candidates || [];

  if (candidates.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-8 text-center">
        <CheckCircle2
          size={42}
          className="mx-auto mb-4 text-emerald-500"
          aria-hidden="true"
        />
        <h3 className="font-bold text-slate-800 dark:text-white">
          Catálogo saudável
        </h3>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Catálogo saudável. Nenhum produto pendente de revisão no momento.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400">
              <Sparkles size={20} aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 dark:text-white">
                Revisar Categorias
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Sugestões read-only para apoiar a revisão humana do catálogo.
              </p>
            </div>
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">
            {data?.returned_count || candidates.length} de{" "}
            {data?.total_candidates || candidates.length} candidato(s)
          </div>
        </div>
        {successMessage && (
          <div className="mt-4 rounded-2xl border border-emerald-100 dark:border-emerald-800/50 bg-emerald-50 dark:bg-emerald-900/20 px-4 py-3 text-sm font-medium text-emerald-700 dark:text-emerald-300">
            {successMessage}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {candidates.map((candidate) => {
          const lastSeen = formatDate(candidate.last_seen);
          const isConfirming = Boolean(confirmingByEan[candidate.ean]);
          const canConfirm =
            candidate.can_confirm &&
            Boolean(candidate.suggested_category) &&
            !isConfirming;
          const actionLabel = !candidate.can_confirm
            ? "Sem sugestão confirmável"
            : isConfirming
              ? "Confirmando..."
              : "Confirmar sugestão";

          return (
            <article
              key={candidate.ean}
              className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm flex flex-col gap-5"
            >
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="font-bold text-slate-800 dark:text-white break-words">
                    {candidate.product_name}
                  </h4>
                  <span className="mt-2 inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 dark:text-slate-500 bg-slate-100/70 dark:bg-slate-800/70 px-2 py-1 rounded-lg">
                    <Hash size={12} aria-hidden="true" />
                    {candidate.ean}
                  </span>
                </div>
                <span
                  className={`w-fit rounded-full border px-3 py-1 text-[11px] font-bold ${confidenceClasses[candidate.confidence_level]}`}
                >
                  {confidenceLabels[candidate.confidence_level]} ·{" "}
                  {formatPercent(candidate.confidence)}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 p-4">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-1">
                    Categoria atual
                  </p>
                  <p className="text-sm font-bold text-slate-700 dark:text-slate-200">
                    {candidate.current_category || "Sem categoria"}
                  </p>
                </div>
                <div className="rounded-2xl bg-primary-50/60 dark:bg-primary-900/10 border border-primary-100 dark:border-primary-800/40 p-4">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-primary-500 dark:text-primary-300 mb-1">
                    Sugestão
                  </p>
                  <p className="text-sm font-bold text-slate-800 dark:text-slate-100">
                    {candidate.suggested_category || "Sem sugestão"}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-[11px] font-bold">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-3 py-1">
                  <Layers size={12} aria-hidden="true" />
                  {sourceLabels[candidate.source]}
                </span>
                <span className="rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-3 py-1">
                  {candidate.occurrence_count} ocorrência(s)
                </span>
                {lastSeen && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-3 py-1">
                    <CalendarDays size={12} aria-hidden="true" />
                    Visto em {lastSeen}
                  </span>
                )}
              </div>

              <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                {candidate.reason}
              </p>

              <button
                type="button"
                onClick={() => handleConfirmSuggestion(candidate)}
                disabled={!canConfirm}
                className={`mt-auto w-full rounded-xl border px-4 py-2.5 text-xs font-bold uppercase tracking-widest transition-colors ${
                  canConfirm
                    ? "border-primary-600 bg-primary-600 text-white hover:bg-primary-700"
                    : "border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
                }`}
              >
                {actionLabel}
              </button>
              {errorByEan[candidate.ean] && (
                <p className="text-xs font-medium text-rose-600 dark:text-rose-400">
                  Não foi possível confirmar a categoria. Tente novamente.
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
};
