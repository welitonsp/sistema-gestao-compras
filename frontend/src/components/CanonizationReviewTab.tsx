import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  Hash,
  Info,
  Layers,
  ListChecks,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "../api/client";
import { formatPercentBR } from "../lib/formatters";
import type {
  CanonizationCandidateGroup,
  CanonizationCandidatesResponse,
  CanonizationMappingItem,
  CanonizationMappingsResponse,
  CanonizationMappingStatus,
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

const mappingStatusOptions: { value: CanonizationMappingStatus; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Ativos" },
  { value: "reverted", label: "Revertidos" },
  { value: "inactive", label: "Inativos" },
];

const mappingSortOptions = [
  { value: "updated_at", label: "Atualização" },
  { value: "original_name", label: "Produto original" },
  { value: "canonical_name", label: "Produto canônico" },
  { value: "ean_original", label: "EAN original" },
  { value: "ean_canonico", label: "EAN canônico" },
  { value: "status", label: "Status" },
  { value: "department", label: "Departamento" },
  { value: "confirmed_at", label: "Confirmação" },
  { value: "reverted_at", label: "Reversão" },
];

const mappingPageSize = 25;

const mappingStatusLabel = (status: string) => {
  if (status === "active") return "Ativo";
  if (status === "reverted") return "Revertido";
  if (status === "inactive") return "Inativo";
  return status;
};

const mappingStatusClass = (status: string) => {
  if (status === "active") {
    return "border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-800/50 dark:bg-emerald-900/20 dark:text-emerald-300";
  }

  if (status === "reverted") {
    return "border-amber-100 bg-amber-50 text-amber-700 dark:border-amber-800/50 dark:bg-amber-900/20 dark:text-amber-300";
  }

  return "border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300";
};

const formatDateTime = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

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

const MappingRow: React.FC<{ mapping: CanonizationMappingItem }> = ({ mapping }) => {
  const confirmedAt = formatDateTime(mapping.confirmado_em);
  const revertedAt = formatDateTime(mapping.revertido_em);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 text-[11px] font-bold ${mappingStatusClass(
                mapping.status,
              )}`}
            >
              {mappingStatusLabel(mapping.status)}
            </span>
            {mapping.department_name && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {mapping.department_name}
              </span>
            )}
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="min-w-0 rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                EAN original
              </p>
              <p className="mt-1 break-words text-sm font-bold text-slate-800 dark:text-slate-100">
                {mapping.original_name || "Produto sem nome"}
              </p>
              <p className="mt-1 font-mono text-xs font-bold text-slate-500 dark:text-slate-400">
                {mapping.ean_original}
              </p>
            </div>

            <div className="hidden text-slate-400 md:block">
              <ArrowRight size={18} aria-hidden="true" />
            </div>

            <div className="min-w-0 rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-800/60">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Produto canônico
              </p>
              <p className="mt-1 break-words text-sm font-bold text-slate-800 dark:text-slate-100">
                {mapping.canonical_name || "Produto sem nome"}
              </p>
              <p className="mt-1 font-mono text-xs font-bold text-slate-500 dark:text-slate-400">
                {mapping.ean_canonico}
              </p>
            </div>
          </div>
        </div>

        <div className="min-w-[220px] space-y-2 text-xs text-slate-500 dark:text-slate-400">
          {mapping.confidence_score !== null && (
            <p>
              Confiança{" "}
              <span className="font-bold text-slate-700 dark:text-slate-200">
                {formatSimilarity(mapping.confidence_score)}
              </span>
            </p>
          )}
          {mapping.confirmado_por && (
            <p>
              Confirmado por{" "}
              <span className="font-bold text-slate-700 dark:text-slate-200">
                {mapping.confirmado_por}
              </span>
            </p>
          )}
          {confirmedAt && (
            <p className="inline-flex items-center gap-1.5">
              <Clock size={13} aria-hidden="true" />
              {confirmedAt}
            </p>
          )}
          {mapping.status === "reverted" && mapping.revertido_por && (
            <p>
              Revertido por{" "}
              <span className="font-bold text-slate-700 dark:text-slate-200">
                {mapping.revertido_por}
              </span>
            </p>
          )}
          {mapping.status === "reverted" && revertedAt && (
            <p className="inline-flex items-center gap-1.5">
              <Clock size={13} aria-hidden="true" />
              {revertedAt}
            </p>
          )}
        </div>
      </div>

      {(mapping.reason || mapping.revert_reason) && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {mapping.reason && (
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <span className="font-bold text-slate-700 dark:text-slate-200">
                Motivo:
              </span>{" "}
              {mapping.reason}
            </p>
          )}
          {mapping.revert_reason && (
            <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
              <span className="font-bold">Reversão:</span>{" "}
              {mapping.revert_reason}
            </p>
          )}
        </div>
      )}
    </article>
  );
};

const CanonizationMappingsPanel: React.FC<{
  data: CanonizationMappingsResponse | null;
  statusFilter: CanonizationMappingStatus;
  searchTerm: string;
  sortBy: string;
  sortDir: "asc" | "desc";
  page: number;
  loading: boolean;
  error: boolean;
  onStatusChange: (status: CanonizationMappingStatus) => void;
  onSearchTermChange: (value: string) => void;
  onSearchSubmit: () => void;
  onSortByChange: (value: string) => void;
  onSortDirChange: (value: "asc" | "desc") => void;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  onExport: () => void;
}> = ({
  data,
  statusFilter,
  searchTerm,
  sortBy,
  sortDir,
  page,
  loading,
  error,
  onStatusChange,
  onSearchTermChange,
  onSearchSubmit,
  onSortByChange,
  onSortDirChange,
  onPageChange,
  onRefresh,
  onExport,
}) => {
  const mappings = data?.items || [];
  const counts = data?.counts || {
    all: 0,
    active: 0,
    inactive: 0,
    reverted: 0,
  };
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / mappingPageSize));
  const canGoBack = page > 0;
  const canGoForward = page + 1 < totalPages;

  return (
    <section className="space-y-4">
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-300">
              <ListChecks size={20} aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 dark:text-white">
                Mapeamentos de canonização
              </h3>
              <p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
                Mapeamentos ativos consolidam a leitura dos dashboards. Mapeamentos revertidos deixam o EAN original voltar a ser considerado separadamente, sem alterar dados fiscais.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onExport}
              disabled={loading || total === 0}
              className="inline-flex w-fit items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold uppercase tracking-widest text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <Download size={14} aria-hidden="true" />
              Exportar
            </button>
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="inline-flex w-fit items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold uppercase tracking-widest text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <RefreshCw size={14} aria-hidden="true" />
              Atualizar
            </button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4">
          {mappingStatusOptions.map((option) => (
            <button
              key={`count-${option.value}`}
              type="button"
              onClick={() => onStatusChange(option.value)}
              className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                statusFilter === option.value
                  ? "border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-800/60 dark:bg-primary-900/20 dark:text-primary-300"
                  : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-300 dark:hover:bg-slate-800"
              }`}
              aria-pressed={statusFilter === option.value}
            >
              <span className="block text-[10px] font-bold uppercase tracking-widest">
                {option.label}
              </span>
              <span className="mt-1 block text-lg font-black">
                {counts[option.value]}
              </span>
            </button>
          ))}
        </div>

        <form
          className="mt-5 grid gap-3 lg:grid-cols-[1fr_220px_150px_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            onSearchSubmit();
          }}
        >
          <label className="relative block">
            <span className="sr-only">Buscar mapeamentos</span>
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              value={searchTerm}
              onChange={(event) => onSearchTermChange(event.target.value)}
              placeholder="Buscar por EAN, produto, usuário ou departamento"
              className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-primary-300 focus:ring-2 focus:ring-primary-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-primary-700 dark:focus:ring-primary-900/40"
            />
          </label>

          <label className="block">
            <span className="sr-only">Ordenar por</span>
            <select
              value={sortBy}
              onChange={(event) => onSortByChange(event.target.value)}
              className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-600 outline-none focus:border-primary-300 focus:ring-2 focus:ring-primary-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              {mappingSortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="sr-only">Direção</span>
            <select
              value={sortDir}
              onChange={(event) => onSortDirChange(event.target.value as "asc" | "desc")}
              className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-600 outline-none focus:border-primary-300 focus:ring-2 focus:ring-primary-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              <option value="desc">Descendente</option>
              <option value="asc">Ascendente</option>
            </select>
          </label>

          <button
            type="submit"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-xs font-bold uppercase tracking-widest text-white transition-colors hover:bg-primary-700"
          >
            <Search size={14} aria-hidden="true" />
            Buscar
          </button>
        </form>

        <div className="mt-4 flex flex-wrap gap-2">
          {mappingStatusOptions.map((option) => (
            <button
              key={`filter-${option.value}`}
              type="button"
              onClick={() => onStatusChange(option.value)}
              className={`rounded-xl px-3 py-2 text-xs font-bold transition-colors ${
                statusFilter === option.value
                  ? "bg-primary-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              }`}
              aria-pressed={statusFilter === option.value}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="mt-4 flex items-start gap-2 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-400">
          <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>
            Esta visão é somente consulta. Confirmações e reversões permanecem registradas em auditoria.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((item) => (
            <Skeleton key={item} className="h-36 rounded-3xl" />
          ))}
        </div>
      ) : error ? (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 text-center">
          <Info size={34} className="mx-auto mb-3 text-amber-500" aria-hidden="true" />
          <h3 className="font-bold text-slate-800 dark:text-white">
            Não foi possível carregar os mapeamentos
          </h3>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            A revisão de candidatos continua disponível.
          </p>
        </div>
      ) : mappings.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 text-center">
          <CheckCircle2 size={36} className="mx-auto mb-3 text-emerald-500" aria-hidden="true" />
          <h3 className="font-bold text-slate-800 dark:text-white">
            Nenhum mapeamento encontrado
          </h3>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Ajuste o filtro para consultar outro status.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              {total} mapeamento(s)
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onPageChange(page - 1)}
                disabled={!canGoBack || loading}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                aria-label="Página anterior"
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <span className="min-w-[92px] text-center text-xs font-bold text-slate-500 dark:text-slate-400">
                {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => onPageChange(page + 1)}
                disabled={!canGoForward || loading}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                aria-label="Próxima página"
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
          {mappings.map((mapping) => (
            <MappingRow
              key={`${mapping.department_id}-${mapping.ean_original}-${mapping.status}`}
              mapping={mapping}
            />
          ))}
        </div>
      )}
    </section>
  );
};

export const CanonizationReviewTab: React.FC = () => {
  const [data, setData] = useState<CanonizationCandidatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mappingsData, setMappingsData] =
    useState<CanonizationMappingsResponse | null>(null);
  const [loadingMappings, setLoadingMappings] = useState(true);
  const [mappingsError, setMappingsError] = useState(false);
  const [mappingStatus, setMappingStatus] =
    useState<CanonizationMappingStatus>("all");
  const [mappingSearchInput, setMappingSearchInput] = useState("");
  const [mappingQuery, setMappingQuery] = useState("");
  const [mappingSortBy, setMappingSortBy] = useState("updated_at");
  const [mappingSortDir, setMappingSortDir] = useState<"asc" | "desc">("desc");
  const [mappingPage, setMappingPage] = useState(0);
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

  const fetchMappings = async () => {
    setLoadingMappings(true);
    setMappingsError(false);
    try {
      const params = new URLSearchParams({
        status: mappingStatus,
        sort_by: mappingSortBy,
        sort_dir: mappingSortDir,
        limit: String(mappingPageSize),
        offset: String(mappingPage * mappingPageSize),
      });
      if (mappingQuery.trim()) {
        params.set("q", mappingQuery.trim());
      }
      const response = await apiClient.get<CanonizationMappingsResponse>(
        `/produtos/canonization/mappings?${params.toString()}`,
      );
      setMappingsData(response);
    } catch {
      setMappingsData(null);
      setMappingsError(true);
    } finally {
      setLoadingMappings(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, []);

  useEffect(() => {
    fetchMappings();
  }, [mappingStatus, mappingQuery, mappingSortBy, mappingSortDir, mappingPage]);

  const handleMappingStatusChange = (status: CanonizationMappingStatus) => {
    setMappingStatus(status);
    setMappingPage(0);
  };

  const handleMappingSearchSubmit = () => {
    setMappingQuery(mappingSearchInput.trim());
    setMappingPage(0);
  };

  const handleMappingSortByChange = (value: string) => {
    setMappingSortBy(value);
    setMappingPage(0);
  };

  const handleMappingSortDirChange = (value: "asc" | "desc") => {
    setMappingSortDir(value);
    setMappingPage(0);
  };

  const exportMappings = () => {
    const params = new URLSearchParams({
      status: mappingStatus,
      sort_by: mappingSortBy,
      sort_dir: mappingSortDir,
    });
    if (mappingQuery.trim()) {
      params.set("q", mappingQuery.trim());
    }
    window.location.href = `/api/v1/produtos/canonization/mappings/export?${params.toString()}`;
  };

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

      <CanonizationMappingsPanel
        data={mappingsData}
        statusFilter={mappingStatus}
        searchTerm={mappingSearchInput}
        sortBy={mappingSortBy}
        sortDir={mappingSortDir}
        page={mappingPage}
        loading={loadingMappings}
        error={mappingsError}
        onStatusChange={handleMappingStatusChange}
        onSearchTermChange={setMappingSearchInput}
        onSearchSubmit={handleMappingSearchSubmit}
        onSortByChange={handleMappingSortByChange}
        onSortDirChange={handleMappingSortDirChange}
        onPageChange={setMappingPage}
        onRefresh={fetchMappings}
        onExport={exportMappings}
      />
    </div>
  );
};
