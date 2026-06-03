import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Hash,
  Info,
  Layers,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "../api/client";
import { formatPercentBR } from "../lib/formatters";
import type {
  CanonizationCandidateGroup,
  CanonizationCandidatesResponse,
  CanonizationMatch,
} from "../types/api";
import { Skeleton } from "./Skeleton";

const formatSimilarity = (value: number) =>
  `${formatPercentBR(Math.max(0, Math.min(1, Number(value || 0))) * 100)}%`;

const similarityLabel = (value: number) => {
  if (value >= 0.95) return "Alta confiança";
  if (value >= 0.9) return "Revisar com cautela";
  return "Abaixo do limiar";
};

const similarityClass = (value: number) => {
  if (value >= 0.95) {
    return "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800/50";
  }

  if (value >= 0.9) {
    return "bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800/50";
  }

  return "bg-rose-50 text-rose-700 border-rose-100 dark:bg-rose-900/20 dark:text-rose-300 dark:border-rose-800/50";
};

const categoryLabel = (category?: string | null) => category || "Sem categoria";

const MatchRow: React.FC<{
  match: CanonizationMatch;
  primaryEan: string;
  selected: boolean;
  onToggle: (primaryEan: string, matchEan: string) => void;
}> = ({ match, primaryEan, selected, onToggle }) => (
  <div
    className={`rounded-2xl border p-4 transition-colors ${
      selected
        ? "border-primary-200 bg-primary-50/70 dark:border-primary-800/60 dark:bg-primary-900/20"
        : "border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-800/40"
    }`}
  >
    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
      <div className="min-w-0">
        <p className="font-bold text-sm text-slate-800 dark:text-slate-100 break-words">
          {match.name}
        </p>
        <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-bold text-slate-500 dark:text-slate-400">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-white dark:bg-slate-900 px-2 py-1 font-mono">
            <Hash size={12} aria-hidden="true" />
            {match.ean}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-white dark:bg-slate-900 px-2 py-1">
            <Layers size={12} aria-hidden="true" />
            {categoryLabel(match.category)}
          </span>
        </div>
      </div>
      <span
        className={`w-fit rounded-full border px-3 py-1 text-[11px] font-bold ${similarityClass(
          match.similarity,
        )}`}
      >
        {similarityLabel(match.similarity)} - {formatSimilarity(match.similarity)}
      </span>
    </div>

    {match.reason && (
      <p className="mt-3 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
        {match.reason}
      </p>
    )}

    <label className="mt-4 inline-flex w-fit cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800">
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onToggle(primaryEan, match.ean)}
        className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
        aria-label={`${selected ? "Remover" : "Selecionar"} ${match.name} da simulação de canonização`}
      />
      {selected ? "Selecionado para simulação" : "Selecionar para simulação"}
    </label>
  </div>
);

const GroupCard: React.FC<{
  group: CanonizationCandidateGroup;
  selectedMatchEans: string[];
  onToggleMatch: (primaryEan: string, matchEan: string) => void;
}> = ({ group, selectedMatchEans, onToggleMatch }) => {
  const selectedMatches = group.matches.filter((match) =>
    selectedMatchEans.includes(match.ean),
  );

  return (
    <article className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-5">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-xl bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400">
          <ShieldCheck size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            Produto principal
          </p>
          <h4 className="mt-1 font-bold text-slate-800 dark:text-white break-words">
            {group.primary.name}
          </h4>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-bold text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 px-2 py-1 font-mono">
              <Hash size={12} aria-hidden="true" />
              {group.primary.ean}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 px-2 py-1">
              <Layers size={12} aria-hidden="true" />
              {categoryLabel(group.primary.category)}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
          Candidatos similares
        </p>
        {group.matches.map((match) => (
          <MatchRow
            key={match.ean}
            match={match}
            primaryEan={group.primary.ean}
            selected={selectedMatchEans.includes(match.ean)}
            onToggle={onToggleMatch}
          />
        ))}
      </div>

      {selectedMatches.length > 0 && (
        <div className="rounded-2xl border border-primary-100 bg-primary-50/70 p-4 dark:border-primary-800/50 dark:bg-primary-900/20">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-xl bg-white p-2 text-primary-600 dark:bg-slate-900 dark:text-primary-300">
              <Eye size={16} aria-hidden="true" />
            </div>
            <div className="min-w-0 space-y-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-primary-600 dark:text-primary-300">
                  Plano de Canonização - Simulação local
                </p>
                <p className="mt-1 text-sm font-bold text-slate-800 dark:text-white break-words">
                  {group.primary.name}
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {selectedMatches.length} candidato(s) selecionado(s)
                </p>
              </div>

              <ul className="space-y-2">
                {selectedMatches.slice(0, 4).map((match) => (
                  <li
                    key={match.ean}
                    className="rounded-xl bg-white px-3 py-2 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-300"
                  >
                    <span className="font-bold">{match.name}</span>
                    <span className="ml-2 font-mono text-slate-400">
                      {match.ean}
                    </span>
                  </li>
                ))}
              </ul>

              {selectedMatches.length > 4 && (
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  +{selectedMatches.length - 4} candidato(s) adicional(is)
                </p>
              )}

              <div className="space-y-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                <p>Nenhuma alteração será salva nesta fase.</p>
                <p>
                  A efetivação no banco será tratada em fase futura com
                  auditoria e confirmação explícita.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </article>
  );
};

export const CanonizationReviewTab: React.FC = () => {
  const [data, setData] = useState<CanonizationCandidatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedMatches, setSelectedMatches] = useState<Record<string, string[]>>(
    {},
  );

  const fetchCandidates = async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await apiClient.get<CanonizationCandidatesResponse>(
        "/produtos/canonization/candidates",
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

  const toggleMatchSelection = (primaryEan: string, matchEan: string) => {
    setSelectedMatches((current) => {
      const currentGroup = current[primaryEan] || [];
      let nextGroup: string[];

      if (currentGroup.includes(matchEan)) {
        nextGroup = currentGroup.filter((ean) => ean !== matchEan);
      } else {
        nextGroup = [...currentGroup, matchEan];
      }

      if (nextGroup.length === 0) {
        const { [primaryEan]: removed, ...rest } = current;
        void removed;
        return rest;
      }

      return {
        ...current,
        [primaryEan]: nextGroup,
      };
    });
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-48 rounded-3xl" />
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
          Não foi possível carregar a canonização agora
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

  const groups = data?.groups || [];

  return (
    <div className="space-y-6">
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400">
              <Eye size={20} aria-hidden="true" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-bold text-slate-800 dark:text-white">
                  Canonização (Beta)
                </h3>
                <span className="rounded-full border border-amber-100 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-900/20 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-300">
                  Preview read-only
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                Esta tela é apenas uma prévia. Nenhuma unificação será feita automaticamente.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-[11px] font-bold text-slate-500 dark:text-slate-400">
            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1">
              {data?.total_groups || 0} grupo(s)
            </span>
            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1">
              Threshold {formatSimilarity(data?.threshold || 0)}
            </span>
            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1">
              Limite {data?.limit || 0}
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2 rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
          <AlertTriangle
            size={16}
            className="mt-0.5 shrink-0 text-amber-500"
            aria-hidden="true"
          />
          <p>
            Revise manualmente os candidatos antes de qualquer decisão operacional. Esta etapa não consolida produtos.
          </p>
        </div>
      </div>

      {groups.length === 0 ? (
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
            Catálogo saudável: nenhum candidato de canonização encontrado.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {groups.map((group) => (
            <GroupCard
              key={`${group.primary.ean}-${group.matches
                .map((match) => match.ean)
                .join("-")}`}
              group={group}
              selectedMatchEans={selectedMatches[group.primary.ean] || []}
              onToggleMatch={toggleMatchSelection}
            />
          ))}
        </div>
      )}
    </div>
  );
};
