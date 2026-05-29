import React, { useMemo } from "react";
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Package,
  ArrowUpRight,
  Activity,
  Calendar,
  Info,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LineChart,
  Line,
} from "recharts";
import { DashboardResumo, AlertaPreco } from "../types/api";

import { Skeleton } from "../components/Skeleton";

interface DashboardViewProps {
  data: DashboardResumo | null;
  alerts: AlertaPreco[];
  produtosCount: number;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  data,
  alerts,
  produtosCount,
}) => {
  const isDarkMode =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  const maxProductSpend = useMemo(() => {
    if (!data?.top_produtos.length) return 0;
    return Math.max(...data.top_produtos.map((p) => p.total));
  }, [data]);

  const maxSupplierSpend = useMemo(() => {
    if (!data?.top_fornecedores.length) return 0;
    return Math.max(...data.top_fornecedores.map((f) => f.total));
  }, [data]);

  if (!data) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 rounded-2xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Skeleton className="lg:col-span-2 h-[450px] rounded-3xl" />
          <Skeleton className="h-[450px] rounded-3xl" />
        </div>
      </div>
    );
  }

  const stats = [
    {
      label: "Gasto Total",
      value: `R$ ${Number(data.total_geral || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`,
      icon: BarChart3,
      color: "blue",
      trend: "Total acumulado",
    },
    {
      label: "Categorias",
      value: data.por_categoria?.length || 0,
      icon: Calendar,
      color: "indigo",
      trend: "Agrupamento",
    },
    {
      label: "Produtos Únicos",
      value: produtosCount,
      icon: Package,
      color: "emerald",
      trend: "Catálogo",
    },
    {
      label: "Alertas Ativos",
      value: alerts.length,
      icon: AlertTriangle,
      color: "amber",
      trend: "Variação de preço",
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Welcome Section */}
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight">
          Seu Painel de Compras
        </h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Acompanhe seus hábitos de consumo e economias em tempo real.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <div
            key={i}
            className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all"
          >
            <div className="flex justify-between items-start mb-4">
              <div
                className={`p-3 rounded-xl bg-${stat.color}-50 dark:bg-${stat.color}-900/20 text-${stat.color}-600 dark:text-${stat.color}-400`}
              >
                <stat.icon size={20} />
              </div>
              <span
                className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400`}
              >
                {stat.trend}
              </span>
            </div>
            <p className="text-slate-500 dark:text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">
              {stat.label}
            </p>
            <h3 className="text-2xl font-bold text-slate-800 dark:text-white">
              {stat.value}
            </h3>
          </div>
        ))}
      </div>

      {/* Alerts Sidebar - Mobile Only (Top of charts) */}
      <div className="lg:hidden">
        <AlertsSection alerts={alerts} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <section
          className="lg:col-span-2 bg-white dark:bg-slate-900 p-6 md:p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm transition-colors"
          aria-labelledby="chart-category-title"
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3
                id="chart-category-title"
                className="font-bold text-slate-800 dark:text-white text-lg"
              >
                Gastos por Categoria
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Onde você mais investiu seu dinheiro
              </p>
            </div>
            <TrendingUp
              size={20}
              className="text-slate-400 dark:text-slate-600"
            />
          </div>
          <div
            className="h-[300px] md:h-[350px] w-full"
            aria-label="Gráfico de barras mostrando gastos por categoria"
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.por_categoria}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke={isDarkMode ? "#1e293b" : "#f1f5f9"}
                />
                <XAxis
                  dataKey="categoria"
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 10,
                    fontWeight: 600,
                  }}
                  dy={10}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 10,
                  }}
                />
                <Tooltip
                  cursor={{ fill: isDarkMode ? "#1e293b" : "#f8fafc" }}
                  contentStyle={{
                    backgroundColor: isDarkMode ? "#0f172a" : "#ffffff",
                    borderRadius: "12px",
                    border: "none",
                    boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)",
                  }}
                  itemStyle={{ color: isDarkMode ? "#f8fafc" : "#0f172a" }}
                />
                <Bar dataKey="total" radius={[6, 6, 0, 0]} barSize={40}>
                  {data.por_categoria.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        ["#7c3aed", "#6366f1", "#8b5cf6", "#a855f7", "#ec4899"][
                          index % 5
                        ]
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
            <Info size={14} className="mt-0.5 shrink-0 text-indigo-500" />
            <p>
              Este gráfico agrupa seus gastos pelas categorias atribuídas aos
              produtos. Categoria "Outros" inclui itens ainda não classificados.
            </p>
          </div>
        </section>

        {/* Alerts Sidebar - Desktop Only */}
        <div className="hidden lg:block">
          <AlertsSection alerts={alerts} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Evolution Chart */}
        <section
          className="bg-white dark:bg-slate-900 p-6 md:p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm transition-colors"
          aria-labelledby="chart-evolution-title"
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3
                id="chart-evolution-title"
                className="font-bold text-slate-800 dark:text-white text-lg"
              >
                Evolução Mensal de Gastos
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Total investido mês a mês
              </p>
            </div>
            <Activity
              size={20}
              className="text-slate-400 dark:text-slate-600"
            />
          </div>
          <div
            className="h-[250px] md:h-[300px] w-full"
            aria-label="Gráfico de linha mostrando a evolução mensal de gastos"
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.evolucao_mensal}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke={isDarkMode ? "#1e293b" : "#f1f5f9"}
                />
                <XAxis
                  dataKey="mes"
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 10,
                    fontWeight: 600,
                  }}
                  dy={10}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 10,
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDarkMode ? "#0f172a" : "#ffffff",
                    borderRadius: "12px",
                    border: "none",
                    boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)",
                  }}
                  itemStyle={{ color: isDarkMode ? "#f8fafc" : "#0f172a" }}
                />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="#6366f1"
                  strokeWidth={3}
                  dot={{
                    r: 4,
                    fill: "#6366f1",
                    strokeWidth: 2,
                    stroke: isDarkMode ? "#0f172a" : "#fff",
                  }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
            <Info size={14} className="mt-0.5 shrink-0 text-indigo-500" />
            <p>
              Valores baseados na data de emissão das notas fiscais. Ideal para
              identificar meses com maior concentração de compras.
            </p>
          </div>
        </section>

        {/* Top Lists */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Top Products */}
          <section className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
            <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-6 flex items-center justify-between">
              Top 5 Produtos (Gasto)
              <Package size={14} className="text-slate-400" />
            </h4>
            <div className="space-y-6 flex-1">
              {data.top_produtos.slice(0, 5).map((p, i) => (
                <div key={i} className="group cursor-default">
                  <div className="flex justify-between items-end mb-1.5 px-0.5">
                    <span
                      className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 truncate max-w-[180px] group-hover:text-indigo-500 transition-colors"
                      title={p.produto}
                    >
                      {p.produto}
                    </span>
                    <span className="font-bold text-slate-800 dark:text-white text-[11px]">
                      R${" "}
                      {p.total.toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full transition-all duration-1000 ease-out"
                      style={{ width: `${(p.total / maxProductSpend) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
              {data.top_produtos.length === 0 && (
                <div className="h-full flex items-center justify-center">
                  <p className="text-slate-500 text-[10px] italic">
                    Sem dados suficientes
                  </p>
                </div>
              )}
            </div>
            <p className="mt-6 text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3">
              Ranking baseado no valor total acumulado para cada produto,
              independente do fornecedor.
            </p>
          </section>

          {/* Top Suppliers */}
          <section className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
            <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-6 flex items-center justify-between">
              Top 5 Fornecedores
              <Calendar size={14} className="text-slate-400" />
            </h4>
            <div className="space-y-6 flex-1">
              {data.top_fornecedores.slice(0, 5).map((f, i) => (
                <div key={i} className="group cursor-default">
                  <div className="flex justify-between items-end mb-1.5 px-0.5">
                    <span
                      className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 truncate max-w-[180px] group-hover:text-emerald-500 transition-colors"
                      title={f.fornecedor}
                    >
                      {f.fornecedor}
                    </span>
                    <span className="font-bold text-slate-800 dark:text-white text-[11px]">
                      R${" "}
                      {f.total.toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-1000 ease-out"
                      style={{
                        width: `${(f.total / maxSupplierSpend) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
              {data.top_fornecedores.length === 0 && (
                <div className="h-full flex items-center justify-center">
                  <p className="text-slate-500 text-[10px] italic">
                    Sem dados suficientes
                  </p>
                </div>
              )}
            </div>
            <p className="mt-6 text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3">
              Identifica onde você concentra a maior parte do seu orçamento de
              compras.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

const AlertsSection: React.FC<{ alerts: AlertaPreco[] }> = ({ alerts }) => (
  <section
    className="bg-slate-900 dark:bg-slate-950 rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200 dark:shadow-none border dark:border-slate-800 transition-colors"
    aria-labelledby="alerts-title"
  >
    <div className="flex items-center gap-2 mb-6">
      <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
      <h3 id="alerts-title" className="text-white font-bold">
        Alertas de Preço
      </h3>
    </div>
    <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
      {alerts.length === 0 ? (
        <div className="bg-slate-800/50 border border-slate-800 p-6 rounded-2xl text-center">
          <p className="text-slate-500 text-xs">
            Tudo certo com seus preços habituais. Nenhuma anomalia detectada.
          </p>
        </div>
      ) : (
        alerts.map((alert, i) => (
          <div
            key={i}
            className="bg-slate-800/50 dark:bg-slate-900/50 border border-slate-700/50 dark:border-slate-800 p-4 rounded-2xl group hover:bg-slate-800 transition-all cursor-pointer"
            role="alert"
          >
            <div className="flex justify-between items-start mb-2">
              <p className="text-[10px] font-bold text-amber-500 uppercase tracking-widest">
                Aumento de {alert.variacao_percentual.toFixed(1)}%
              </p>
              <ArrowUpRight
                size={14}
                className="text-slate-500 group-hover:text-white transition-colors"
              />
            </div>
            <p className="text-white text-sm font-bold line-clamp-2 mb-1 group-hover:text-indigo-300 transition-colors">
              {alert.produto}
            </p>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="whitespace-nowrap">
                De R${" "}
                {alert.preco_medio.toLocaleString("pt-BR", {
                  minimumFractionDigits: 2,
                })}
              </span>
              <span>→</span>
              <span className="text-rose-400 font-bold whitespace-nowrap">
                R${" "}
                {alert.preco_atual.toLocaleString("pt-BR", {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
            <p className="mt-2 text-[10px] text-slate-500 dark:text-slate-400 truncate">
              {alert.local}
            </p>
          </div>
        ))
      )}
    </div>
    <button className="w-full mt-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl text-xs font-bold uppercase tracking-widest transition-all border border-white/10 focus:outline-none focus:ring-2 focus:ring-indigo-500">
      Ver todos os Alertas
    </button>
  </section>
);
