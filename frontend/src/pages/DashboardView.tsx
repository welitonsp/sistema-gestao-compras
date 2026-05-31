import React, { useMemo, useState, useEffect, useRef } from "react";
import {
  BarChart3,
  TrendingUp,
  Package,
  Activity,
  Calendar,
  Filter,
  ShieldAlert,
  Info,
  AlertTriangle,
  X,
  CheckCircle2,
  ChevronDown,
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
import {
  DashboardResumo,
  AlertaPreco,
} from "../types/api";
import { apiClient } from "../api/client";

import { Skeleton } from "../components/Skeleton";

// Modular Components
import { DataHealthCard } from "../components/dashboard/DataHealthCard";
import { RiskAlertsSection } from "../components/dashboard/RiskAlertsSection";
import { AlertsSection } from "../components/dashboard/AlertsSection";
import { StatsGrid } from "../components/dashboard/StatsGrid";
import { ExportMenu } from "../components/dashboard/ExportMenu";
import { SupplierHistoryModal } from "../components/modals/SupplierHistoryModal";
import { ProductHistoryModal } from "../components/modals/ProductHistoryModal";

interface DashboardViewProps {
  data: DashboardResumo | null;
  alerts: AlertaPreco[];
  produtosCount: number;
}

type PeriodPreset = "30d" | "month" | "year" | "all";

export const DashboardView: React.FC<DashboardViewProps> = ({
  data: initialData,
  alerts,
  produtosCount,
}) => {
  const [data, setData] = useState<DashboardResumo | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState<PeriodPreset>("all");
  const [selectedEan, setSelectedEan] = useState<string | null>(null);
  const [selectedSupplierId, setSelectedSupplierId] = useState<string | null>(
    null,
  );
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        exportMenuRef.current &&
        !exportMenuRef.current.contains(event.target as Node)
      ) {
        setExportMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExportMenuOpen(false);
      }
    };

    if (exportMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEscape);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [exportMenuOpen]);

  const handleExport = async (dataset: string) => {
    setExporting(dataset);
    try {
      const { start_date, end_date } = getDateParams();
      const query = new URLSearchParams({ dataset });
      if (start_date) query.append("start_date", start_date);
      if (end_date) query.append("end_date", end_date);

      const response = await fetch(`/api/v1/dashboard/export?${query.toString()}`, {
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Falha ao exportar");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      const disposition = response.headers.get("Content-Disposition");
      let filename = `dashboard_${dataset}.csv`;
      if (disposition && disposition.includes("filename=")) {
        filename = disposition.split("filename=")[1].replace(/"/g, "");
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Erro ao exportar CSV:", error);
      alert("Não foi possível exportar o arquivo. Tente novamente.");
    } finally {
      setExporting(null);
    }
  };

  const isDarkMode =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  const getDatesForPreset = (preset: PeriodPreset) => {
    let start_date: string | undefined;
    let end_date: string | undefined;
    const now = new Date();
    const today = now.toISOString().split("T")[0];
    if (preset === "30d") {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      start_date = d.toISOString().split("T")[0];
      end_date = today;
    } else if (preset === "month") {
      const d = new Date(now.getFullYear(), now.getMonth(), 1);
      start_date = d.toISOString().split("T")[0];
      end_date = today;
    } else if (preset === "year") {
      const d = new Date(now.getFullYear(), 0, 1);
      start_date = d.toISOString().split("T")[0];
      end_date = today;
    }
    return { start_date, end_date };
  };

  const fetchFilteredData = async (preset: PeriodPreset) => {
    setLoading(true);
    try {
      const { start_date, end_date } = getDatesForPreset(preset);

      const query = new URLSearchParams();
      if (start_date) query.append("start_date", start_date);
      if (end_date) query.append("end_date", end_date);

      const response = await apiClient.get<DashboardResumo>(
        `/dashboard/resumo?${query.toString()}`,
      );
      setData(response);
    } catch (error) {
      console.error("Erro ao carregar dados filtrados:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (period !== "all") {
      fetchFilteredData(period);
    } else {
      setData(initialData);
    }
  }, [period, initialData]);

  const maxProductSpend = useMemo(() => {
    if (!data?.top_produtos.length) return 0;
    return Math.max(...data.top_produtos.map((p) => p.total));
  }, [data]);

  const maxSupplierSpend = useMemo(() => {
    if (!data?.top_fornecedores.length) return 0;
    return Math.max(...data.top_fornecedores.map((f) => f.total));
  }, [data]);

  const getDateParams = () => {
    return getDatesForPreset(period);
  };

  if (!data && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-500">
        <Info size={48} className="mb-4 opacity-20" />
        <p>Nenhum dado disponível.</p>
      </div>
    );
  }

  const stats = [
    {
      label: "Gasto Total",
      value: `R$ ${Number(data?.total_geral || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`,
      icon: BarChart3,
      color: "blue",
      trend: "Total acumulado",
    },
    {
      label: "Categorias",
      value: data?.por_categoria?.length || 0,
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

  const presets = [
    { id: "all", label: "Tudo" },
    { id: "year", label: "Ano Atual" },
    { id: "month", label: "Mês Atual" },
    { id: "30d", label: "Últimos 30 dias" },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Welcome & Filter Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight">
            Seu Painel de Compras
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Acompanhe seus hábitos de consumo e economias em tempo real.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <ExportMenu 
            exportMenuOpen={exportMenuOpen}
            setExportMenuOpen={setExportMenuOpen}
            exportMenuRef={exportMenuRef}
            exporting={exporting}
            onExport={handleExport}
          />

          <div className="flex items-center gap-2 bg-white dark:bg-slate-900 p-1 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <div className="px-3 text-slate-400 dark:text-slate-500">
              <Filter size={16} />
            </div>
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => setPeriod(p.id as PeriodPreset)}
                className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  period === p.id
                    ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/20"
                    : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-8">
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
      ) : (
        <>
          <StatsGrid stats={stats} />

          <RiskAlertsSection alerts={data?.alertas_risco || []} />

          {/* Data Health Section */}
          {data?.saude_dados && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1">
                <DataHealthCard metrics={data.saude_dados} />
              </div>
              <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-center">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 rounded-2xl bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400">
                    <ShieldAlert size={24} />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-800 dark:text-white">Análise de Integridade</h4>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Detalhamento da qualidade dos dados importados</p>
                  </div>
                </div>
                <div className="space-y-3">
                  {data.saude_dados.total_mismatches > 0 && (
                    <div className="flex items-center gap-2 text-xs text-rose-600 dark:text-rose-400 font-medium">
                      <AlertTriangle size={14} />
                      <span>{data.saude_dados.total_mismatches} nota(s) apresentam divergência entre o total da nota e a soma dos itens.</span>
                    </div>
                  )}
                  {data.saude_dados.itens_sem_ean > 0 && (
                    <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 font-medium">
                      <Info size={14} />
                      <span>{data.saude_dados.itens_sem_ean} item(ns) foram extraídos sem código EAN válido, dificultando o rastreio de preços.</span>
                    </div>
                  )}
                  {data.saude_dados.notas_failed > 0 && (
                    <div className="flex items-center gap-2 text-xs text-rose-600 dark:text-rose-400 font-medium">
                      <X size={14} />
                      <span>{data.saude_dados.notas_failed} importação(ões) falharam criticamente na extração de dados estruturados.</span>
                    </div>
                  )}
                  {(data.saude_dados.quantidades_invalidas > 0 || data.saude_dados.valores_invalidos > 0) && (
                    <div className="flex items-center gap-2 text-xs text-rose-600 dark:text-rose-400 font-medium">
                      <AlertTriangle size={14} />
                      <span>Detectados {data.saude_dados.quantidades_invalidas + data.saude_dados.valores_invalidos} campo(s) numérico(s) inválidos nos itens das notas.</span>
                    </div>
                  )}
                  {data.saude_dados.descricoes_vazias > 0 && (
                    <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 font-medium">
                      <Info size={14} />
                      <span>{data.saude_dados.descricoes_vazias} item(ns) possuem descrição vazia ou ilegível.</span>
                    </div>
                  )}
                  {data.saude_dados.total_mismatches === 0 && data.saude_dados.itens_sem_ean === 0 && data.saude_dados.notas_failed === 0 && data.saude_dados.descricoes_vazias === 0 && (
                    <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      <CheckCircle2 size={14} />
                      <span>Todos os dados importados no período possuem alta integridade técnica.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

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
                {data && data.por_categoria.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-600 border-2 border-dashed border-slate-100 dark:border-slate-800 rounded-2xl">
                    <BarChart3 size={32} className="mb-2 opacity-20" />
                    <p className="text-xs">
                      Sem dados de categoria para este período
                    </p>
                  </div>
                ) : (
                  data && (
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
                          itemStyle={{
                            color: isDarkMode ? "#f8fafc" : "#0f172a",
                          }}
                        />
                        <Bar dataKey="total" radius={[6, 6, 0, 0]} barSize={40}>
                          {data.por_categoria.map((_, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={
                                [
                                  "#7c3aed",
                                  "#6366f1",
                                  "#8b5cf6",
                                  "#a855f7",
                                  "#ec4899",
                                ][index % 5]
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )
                )}
              </div>
              <div className="mt-4 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
                <Info size={14} className="mt-0.5 shrink-0 text-indigo-500" />
                <p>
                  Este gráfico agrupa seus gastos pelas categorias atribuídas
                  aos produtos. Categoria "Outros" inclui itens ainda não
                  classificados.
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
                {data && data.evolucao_mensal.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-600 border-2 border-dashed border-slate-100 dark:border-slate-800 rounded-2xl">
                    <Activity size={32} className="mb-2 opacity-20" />
                    <p className="text-xs">Sem histórico para este período</p>
                  </div>
                ) : (
                  data && (
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
                          itemStyle={{
                            color: isDarkMode ? "#f8fafc" : "#0f172a",
                          }}
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
                  )
                )}
              </div>
              <div className="mt-4 flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
                <Info size={14} className="mt-0.5 shrink-0 text-indigo-500" />
                <p>
                  Valores baseados na data de emissão das notas fiscais. Ideal
                  para identificar meses com maior concentração de compras.
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
                  {data &&
                    data.top_produtos.slice(0, 5).map((p, i) => (
                      <div
                        key={i}
                        className="group cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 -mx-2 px-2 py-1 rounded-xl transition-all"
                        onClick={() => setSelectedEan(p.ean)}
                      >
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
                            style={{
                              width: `${(p.total / maxProductSpend) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  {data && data.top_produtos.length === 0 && (
                    <div className="h-full flex items-center justify-center text-slate-400 dark:text-slate-600">
                      <p className="text-[10px] italic">
                        Sem dados para este período
                      </p>
                    </div>
                  )}
                </div>
                <p className="mt-6 text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3">
                  Ranking baseado no valor total acumulado para cada produto.
                  Clique para ver o histórico.
                </p>
              </section>

              {/* Top Suppliers */}
              <section className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
                <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-6 flex items-center justify-between">
                  Top 5 Fornecedores
                  <ChevronDown size={14} className="text-slate-400" />
                </h4>
                <div className="space-y-6 flex-1">
                  {data &&
                    data.top_fornecedores.slice(0, 5).map((f, i) => (
                      <div
                        key={i}
                        className="group cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 -mx-2 px-2 py-1 rounded-xl transition-all"
                        onClick={() => setSelectedSupplierId(f.fornecedor_id)}
                      >
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
                  {data && data.top_fornecedores.length === 0 && (
                    <div className="h-full flex items-center justify-center text-slate-400 dark:text-slate-600">
                      <p className="text-[10px] italic">
                        Sem dados para este período
                      </p>
                    </div>
                  )}
                </div>
                <p className="mt-6 text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3">
                  Ranking baseado no valor total acumulado para cada fornecedor.
                  Clique para detalhes.
                </p>
              </section>
            </div>
          </div>
        </>
      )}

      {selectedEan && (
        <ProductHistoryModal
          ean={selectedEan}
          onClose={() => setSelectedEan(null)}
          isDarkMode={isDarkMode}
        />
      )}

      {selectedSupplierId && (
        <SupplierHistoryModal
          supplierId={selectedSupplierId}
          onClose={() => setSelectedSupplierId(null)}
          dateParams={getDateParams()}
        />
      )}
    </div>
  );
};
