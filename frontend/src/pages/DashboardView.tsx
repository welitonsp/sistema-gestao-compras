import React from "react";
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Package,
  ArrowUpRight,
  Activity,
  Calendar,
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
      trend: "+12%",
    },
    {
      label: "Categorias",
      value: data.por_categoria?.length || 0,
      icon: Calendar,
      color: "indigo",
      trend: "Em uso",
    },
    {
      label: "Produtos Únicos",
      value: produtosCount,
      icon: Package,
      color: "emerald",
      trend: "Em catálogo",
    },
    {
      label: "Alertas Ativos",
      value: alerts.length,
      icon: AlertTriangle,
      color: "amber",
      trend: "Ação requerida",
    },
  ];

  const isDarkMode =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  return (
    <div className="space-y-8">
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
                className={`text-[11px] font-bold uppercase px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400`}
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm transition-colors">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="font-bold text-slate-800 dark:text-white text-lg">
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
          <div className="h-[350px] w-full">
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
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                  dy={10}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 11,
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
        </div>

        {/* Alerts Sidebar */}
        <div className="bg-slate-900 dark:bg-slate-950 rounded-3xl p-8 shadow-xl shadow-slate-200 dark:shadow-none border dark:border-slate-800 transition-colors">
          <div className="flex items-center gap-2 mb-6">
            <div className="h-2 w-2 rounded-full bg-amber-500" />
            <h3 className="text-white font-bold">Alertas de Preço</h3>
          </div>
          <div className="space-y-4">
            {alerts.length === 0 ? (
              <div className="bg-slate-800/50 border border-slate-800 p-4 rounded-2xl text-center">
                <p className="text-slate-500 text-xs">
                  Tudo certo com seus preços habituais
                </p>
              </div>
            ) : (
              alerts.map((alert, i) => (
                <div
                  key={i}
                  className="bg-slate-800/50 dark:bg-slate-900/50 border border-slate-700/50 dark:border-slate-800 p-4 rounded-2xl group hover:bg-slate-800 transition-all cursor-pointer"
                >
                  <div className="flex justify-between items-start mb-2">
                    <p className="text-[11px] font-bold text-amber-500 uppercase tracking-widest">
                      Aumento de {alert.variacao_percentual.toFixed(1)}%
                    </p>
                    <ArrowUpRight
                      size={14}
                      className="text-slate-500 group-hover:text-white transition-colors"
                    />
                  </div>
                  <p className="text-white text-sm font-bold truncate mb-1">
                    {alert.produto}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span>
                      De R${" "}
                      {alert.preco_medio.toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                    <span>→</span>
                    <span className="text-white font-bold text-xs text-rose-400">
                      R${" "}
                      {alert.preco_atual.toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
          <button className="w-full mt-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl text-xs font-bold uppercase tracking-widest transition-all border border-white/10">
            Relatório de Economia
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Evolution Chart */}
        <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm transition-colors">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="font-bold text-slate-800 dark:text-white text-lg">
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
          <div className="h-[300px] w-full">
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
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                  dy={10}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{
                    fill: isDarkMode ? "#64748b" : "#94a3b8",
                    fontSize: 11,
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
        </div>

        {/* Top Lists */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Top Products */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-4">
              Top 5 Produtos (Gasto)
            </h4>
            <div className="space-y-3">
              {data.top_produtos.slice(0, 5).map((p, i) => (
                <div
                  key={i}
                  className="flex justify-between items-center text-xs"
                >
                  <span
                    className="text-slate-500 dark:text-slate-400 truncate max-w-[120px]"
                    title={p.produto}
                  >
                    {p.produto}
                  </span>
                  <span className="font-bold text-slate-700 dark:text-slate-200">
                    R${" "}
                    {p.total.toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              ))}
              {data.top_produtos.length === 0 && (
                <p className="text-slate-500 text-[10px] italic">
                  Sem dados suficientes
                </p>
              )}
            </div>
          </div>
          {/* Top Suppliers */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-4">
              Top 5 Fornecedores
            </h4>
            <div className="space-y-3">
              {data.top_fornecedores.slice(0, 5).map((f, i) => (
                <div
                  key={i}
                  className="flex justify-between items-center text-xs"
                >
                  <span
                    className="text-slate-500 dark:text-slate-400 truncate max-w-[120px]"
                    title={f.fornecedor}
                  >
                    {f.fornecedor}
                  </span>
                  <span className="font-bold text-slate-700 dark:text-slate-200">
                    R${" "}
                    {f.total.toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              ))}
              {data.top_fornecedores.length === 0 && (
                <p className="text-slate-500 text-[10px] italic">
                  Sem dados suficientes
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
