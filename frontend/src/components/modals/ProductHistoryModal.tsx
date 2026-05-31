import React, { useMemo, useState, useEffect } from "react";
import {
  History,
  X,
  AlertTriangle,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ProductPriceHistoryResponse } from "../../types/api";
import { apiClient } from "../../api/client";
import { Skeleton } from "../Skeleton";

interface ProductHistoryModalProps {
  ean: string;
  onClose: () => void;
  isDarkMode: boolean;
}

export const ProductHistoryModal: React.FC<ProductHistoryModalProps> = ({
  ean,
  onClose,
  isDarkMode,
}) => {
  const [historyData, setHistoryData] =
    useState<ProductPriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const response = await apiClient.get<ProductPriceHistoryResponse>(
          `/dashboard/produtos/${ean}/historico`,
        );
        setHistoryData(response);
      } catch (err) {
        console.error("Erro ao buscar histórico:", err);
        setError("Não foi possível carregar o histórico de preços.");
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [ean]);

  const chartData = useMemo(() => {
    if (!historyData?.historico) return [];
    return [...historyData.historico].reverse().map((h) => ({
      data: new Date(h.data_compra).toLocaleDateString("pt-BR"),
      preco: h.preco_unitario,
    }));
  }, [historyData]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-white dark:bg-slate-900 w-full max-w-4xl max-h-[90vh] rounded-3xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800 animate-in zoom-in-95 duration-200">
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-xl">
              <History size={20} aria-hidden="true" />
            </div>
            <div>
              <h3
                id="modal-title"
                className="font-bold text-slate-800 dark:text-white"
              >
                Histórico de Preço
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                EAN: {ean}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors text-slate-400"
            aria-label="Fechar modal"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {loading ? (
            <div className="space-y-8">
              <Skeleton className="h-64 w-full rounded-2xl" />
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-500">
              <AlertTriangle size={48} className="mb-4 opacity-20" />
              <p className="font-medium">{error}</p>
              <button
                onClick={onClose}
                className="mt-4 px-6 py-2 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-xl text-xs font-bold"
              >
                Voltar ao Dashboard
              </button>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-1">
                <h4 className="text-lg font-bold text-slate-800 dark:text-white truncate">
                  {historyData?.nome_produto}
                </h4>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Total de compras registradas: {historyData?.historico.length}
                </p>
              </div>

              {/* Chart */}
              <div className="bg-slate-50 dark:bg-slate-950/50 p-6 rounded-2xl border border-slate-100 dark:border-slate-800">
                <h5 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-6">
                  Variação do Preço Unitário (R$)
                </h5>
                <div className="h-[200px] w-full">
                  {chartData.length < 2 ? (
                    <div className="h-full flex items-center justify-center text-slate-400 italic text-xs">
                      Dados insuficientes para gerar gráfico de tendência.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke={isDarkMode ? "#1e293b" : "#e2e8f0"}
                        />
                        <XAxis
                          dataKey="data"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#94a3b8", fontSize: 10 }}
                          dy={10}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#94a3b8", fontSize: 10 }}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: isDarkMode ? "#0f172a" : "#fff",
                            borderRadius: "12px",
                            border: "none",
                            boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)",
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="preco"
                          stroke="#6366f1"
                          strokeWidth={3}
                          dot={{ r: 4, fill: "#6366f1" }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-bold tracking-widest border-b border-slate-100 dark:border-slate-800">
                      <th className="pb-3 px-2">Data</th>
                      <th className="pb-3 px-2">Fornecedor</th>
                      <th className="pb-3 px-2">Preço Un.</th>
                      <th className="pb-3 px-2 text-center">Qtd.</th>
                      <th className="pb-3 px-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                    {historyData?.historico.map((h, i) => (
                      <tr
                        key={i}
                        className="text-xs hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors"
                      >
                        <td className="py-4 px-2 font-medium text-slate-600 dark:text-slate-400">
                          {new Date(h.data_compra).toLocaleDateString("pt-BR")}
                        </td>
                        <td className="py-4 px-2 font-bold text-slate-700 dark:text-slate-200">
                          {h.fornecedor}
                        </td>
                        <td className="py-4 px-2 font-bold text-indigo-600 dark:text-indigo-400">
                          R${" "}
                          {h.preco_unitario.toLocaleString("pt-BR", {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                        <td className="py-4 px-2 text-center text-slate-500">
                          {h.quantidade}
                        </td>
                        <td className="py-4 px-2 text-right font-bold text-slate-700 dark:text-slate-200">
                          R${" "}
                          {h.valor_total.toLocaleString("pt-BR", {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                      </tr>
                    ))}
                    {historyData?.historico.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="py-8 text-center text-slate-400 italic"
                        >
                          Nenhuma compra encontrada.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
