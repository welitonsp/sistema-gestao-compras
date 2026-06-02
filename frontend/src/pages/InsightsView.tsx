import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, AlertTriangle, BarChart3, 
  Zap, ShieldAlert, Sparkles, RefreshCw 
} from 'lucide-react';
import { apiClient } from '../api/client';
import { Skeleton } from '../components/Skeleton';
import { formatCurrencyBRL } from '../lib/formatters';
import type {
  SavingOpportunitiesSummary,
  SavingOpportunity,
} from '../types/api';

const getConfidenceLabel = (confidence: SavingOpportunity["confidence"]) => {
  switch (confidence) {
    case "high":
      return "Confiança alta";
    case "medium":
      return "Confiança média";
    case "low":
      return "Confiança baixa";
    case "insufficient_data":
      return "Dados insuficientes";
    default:
      return "Confiança não informada";
  }
};

const buildSavingsOpportunitiesPath = () => {
  const sourceParams =
    typeof window === "undefined"
      ? new URLSearchParams()
      : new URLSearchParams(window.location.search);
  const query = new URLSearchParams();
  const startDate = sourceParams.get("start_date");
  const endDate = sourceParams.get("end_date");

  if (startDate) query.append("start_date", startDate);
  if (endDate) query.append("end_date", endDate);

  const queryString = query.toString();
  return `/dashboard/oportunidades/economia${queryString ? `?${queryString}` : ""}`;
};

const SavingsOpportunitiesSection: React.FC<{
  summary: SavingOpportunitiesSummary | null;
  loading: boolean;
  error: boolean;
}> = ({ summary, loading, error }) => {
  const opportunities =
    summary?.opportunities.filter(
      (item) => item.confidence !== "insufficient_data",
    ) || [];
  const insufficientCount =
    summary?.insufficient_data_count ||
    summary?.opportunities.filter(
      (item) => item.confidence === "insufficient_data",
    ).length ||
    0;

  return (
    <section
      className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm"
      aria-labelledby="savings-opportunities-title"
    >
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
        <div>
          <h3
            id="savings-opportunities-title"
            className="text-lg font-bold text-slate-800 dark:text-white"
          >
            Oportunidades de Economia
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Potencial estimado com base no histórico disponível.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-left md:text-right">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Total estimado
            </p>
            <p className="text-xl font-black text-emerald-600 dark:text-emerald-400">
              {formatCurrencyBRL(summary?.total_estimated_savings || 0)}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Oportunidades
            </p>
            <p className="text-xl font-black text-slate-800 dark:text-white">
              {summary?.opportunity_count || 0}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((item) => (
            <Skeleton key={item} className="h-32 w-full rounded-2xl" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-amber-100 dark:border-amber-800/50 bg-amber-50/60 dark:bg-amber-900/10 p-4 text-sm text-amber-800 dark:text-amber-300">
          Não foi possível carregar as oportunidades neste momento.
        </div>
      ) : opportunities.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 p-6 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Sem oportunidades detectadas no momento. Continue importando notas
            para desbloquear insights de economia.
          </p>
          {insufficientCount > 0 && (
            <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
              {insufficientCount} item(ns) ficaram com dados insuficientes para
              recomendação financeira.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {opportunities.map((item) => (
            <article
              key={item.id}
              className="rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 p-4 md:p-5"
            >
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="font-bold text-slate-800 dark:text-white">
                    {item.product_name || item.title}
                  </h4>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                    {item.description}
                  </p>
                </div>
                <div className="md:text-right shrink-0">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    Potencial estimado
                  </p>
                  <p className="text-lg font-black text-emerald-600 dark:text-emerald-400">
                    {formatCurrencyBRL(item.estimated_savings)}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-bold">
                <span className="rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-1 text-slate-600 dark:text-slate-300">
                  {getConfidenceLabel(item.confidence)}
                </span>
                <span className="rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-1 text-slate-600 dark:text-slate-300">
                  Score {item.score.total_score}/100
                </span>
              </div>

              {item.reasons.length > 0 && (
                <div className="mt-4">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-2">
                    Motivos
                  </p>
                  <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                    {item.reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

              {item.warnings.length > 0 && (
                <div className="mt-4 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-800/50 p-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-300 mb-2">
                    Avisos
                  </p>
                  <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-300">
                    {item.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          ))}

          {insufficientCount > 0 && (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {insufficientCount} oportunidade(s) com dados insuficientes não
              foram destacadas como economia.
            </p>
          )}
        </div>
      )}
    </section>
  );
};

export const InsightsView: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [savingsSummary, setSavingsSummary] =
    useState<SavingOpportunitiesSummary | null>(null);
  const [savingsLoading, setSavingsLoading] = useState(true);
  const [savingsError, setSavingsError] = useState(false);

  const fetchInsights = async () => {
    setLoading(true);
    setSavingsLoading(true);
    setSavingsError(false);
    try {
      const [coreResult, savingsResult] = await Promise.allSettled([
        Promise.all([
          apiClient.get<any[]>('/dashboard/alertas/duplicidade'),
          apiClient.get<any[]>('/dashboard/alertas/estatisticos'),
          apiClient.get<any[]>('/dashboard/insights/tendencia'),
          apiClient.get<any[]>('/dashboard/insights/forecast'),
          apiClient.get<any[]>('/dashboard/insights/volatilidade'),
        ]),
        apiClient.get<SavingOpportunitiesSummary>(
          buildSavingsOpportunitiesPath(),
        ),
      ]);

      if (coreResult.status === "fulfilled") {
        const [duplicatas, estatisticos, tendencia, forecast, volatilidade] =
          coreResult.value;

        setData({
          duplicatas,
          estatisticos,
          tendencia,
          forecast,
          volatilidade
        });
      } else {
        throw coreResult.reason;
      }

      if (savingsResult.status === "fulfilled") {
        setSavingsSummary(savingsResult.value);
      } else {
        setSavingsSummary(null);
        setSavingsError(true);
      }
    } catch (err) {
      console.error("Erro ao buscar insights", err);
    } finally {
      setLoading(false);
      setSavingsLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="h-8 w-64 bg-slate-200 dark:bg-slate-800 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-3xl" />
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-3xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Insights Avançados</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">Análises estatísticas, previsões e estimativas baseadas no histórico disponível.</p>
        </div>
        <button 
          onClick={fetchInsights}
          className="p-2 text-slate-400 hover:text-primary-600 transition-colors"
          aria-label="Atualizar insights"
        >
          <RefreshCw size={20} />
        </button>
      </div>

      <SavingsOpportunitiesSection
        summary={savingsSummary}
        loading={savingsLoading}
        error={savingsError}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Forecast */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 rounded-xl"><Sparkles size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Previsão de Gastos</h3>
          </div>
          <div className="space-y-4">
            {data?.forecast?.map((item: any, i: number) => (
              <div key={i} className="flex justify-between items-center text-sm">
                <span className="text-slate-500 dark:text-slate-400">{item.categoria}</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">R$ {Number(item.projeção_proximo_mes).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Duplicidade */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-rose-50 dark:bg-rose-900/20 text-rose-600 rounded-xl"><ShieldAlert size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Possíveis Duplicidades</h3>
          </div>
          {data?.duplicatas?.length === 0 ? (
            <p className="text-xs text-slate-400 italic">Nenhuma nota suspeita detectada.</p>
          ) : (
            <div className="space-y-3">
              {data?.duplicatas?.slice(0, 3).map((item: any, i: number) => (
                <div key={i} className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl text-xs">
                  <p className="font-bold text-slate-700 dark:text-slate-300">{item.fornecedor}</p>
                  <p className="text-slate-500 mt-1">
                    {item.data} • R$ {Number(item.valor).toFixed(2)} • {item.quantidade_notas} notas
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Volatilidade */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-amber-50 dark:bg-amber-900/20 text-amber-600 rounded-xl"><Zap size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Alta Volatilidade</h3>
          </div>
          <div className="space-y-3">
            {data?.volatilidade?.slice(0, 5).map((item: any, i: number) => (
              <div key={i} className="flex justify-between items-center text-xs">
                <span className="text-slate-500 truncate max-w-[150px]">{item.produto}</span>
                <span className="font-bold text-amber-600">{Number(item.variacao).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="bg-indigo-600 rounded-3xl p-8 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 p-12 opacity-10"><TrendingUp size={120} /></div>
        <div className="relative z-10">
          <h3 className="text-xl font-bold mb-2">Tendência de Preços</h3>
          <p className="text-indigo-100 text-sm mb-6 max-w-xl">
            Acompanhe a evolução dos preços médios em todas as categorias. 
            Este módulo utiliza regressão linear para identificar padrões sazonais.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {data?.tendencia?.slice(0, 4).map((item: any, i: number) => (
              <div key={i} className="bg-white/10 backdrop-blur-md p-4 rounded-2xl border border-white/10">
                <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-200 mb-1">{item.mes}</p>
                <p className="text-lg font-bold">R$ {Number(item.valor).toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
