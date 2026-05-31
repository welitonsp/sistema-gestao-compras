import React, { useMemo, useState, useEffect } from "react";
import {
  AlertTriangle,
  Building2,
  Download,
  Package,
  ShieldAlert,
  X,
} from "lucide-react";
import { SupplierDrilldownResponse } from "../../types/api";
import { apiClient } from "../../api/client";
import { Skeleton } from "../Skeleton";

interface SupplierHistoryModalProps {
  supplierId: string;
  onClose: () => void;
  dateParams: { start_date?: string; end_date?: string };
}

export const SupplierHistoryModal: React.FC<SupplierHistoryModalProps> = ({
  supplierId,
  onClose,
  dateParams,
}) => {
  const [data, setData] = useState<SupplierDrilldownResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleExportProducts = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const query = new URLSearchParams();
      if (dateParams.start_date)
        query.append("start_date", dateParams.start_date);
      if (dateParams.end_date) query.append("end_date", dateParams.end_date);

      const response = await fetch(
        `/api/v1/dashboard/fornecedores/${supplierId}/export?${query.toString()}`,
        {
          credentials: "include",
        },
      );

      if (!response.ok) {
        throw new Error("Falha ao exportar");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      const disposition = response.headers.get("Content-Disposition");
      let filename = `fornecedor_produtos.csv`;
      if (disposition && disposition.includes("filename=")) {
        filename = disposition.split("filename=")[1].replace(/"/g, "");
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Erro ao exportar CSV do fornecedor:", error);
      alert("Não foi possível exportar os produtos do fornecedor. Tente novamente.");
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const query = new URLSearchParams();
        if (dateParams.start_date)
          query.append("start_date", dateParams.start_date);
        if (dateParams.end_date) query.append("end_date", dateParams.end_date);
        const response = await apiClient.get<SupplierDrilldownResponse>(
          `/dashboard/fornecedores/${supplierId}/detalhes?${query.toString()}`,
        );
        setData(response);
      } catch (err) {
        console.error("Erro ao buscar detalhes do fornecedor:", err);
        setError("Não foi possível carregar os detalhes do fornecedor.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [supplierId, dateParams]);

  const maxProductSpend = useMemo(() => {
    if (!data?.top_produtos.length) return 0;
    return Math.max(...data.top_produtos.map((p) => p.total_gasto));
  }, [data]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="supplier-modal-title"
    >
      <div className="bg-white dark:bg-slate-900 w-full max-w-5xl max-h-[90vh] rounded-3xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800 animate-in zoom-in-95 duration-200">
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-xl">
              <Building2 size={20} aria-hidden="true" />
            </div>
            <div>
              <h3
                id="supplier-modal-title"
                className="font-bold text-slate-800 dark:text-white"
              >
                Detalhes do Fornecedor
              </h3>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            aria-label="Fechar modal"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {loading ? (
            <div className="space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-24 w-full rounded-2xl" />
                ))}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-xl" />
                  ))}
                </div>
                <div className="space-y-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-xl" />
                  ))}
                </div>
              </div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-500">
              <AlertTriangle size={48} className="mb-4 opacity-20" aria-hidden="true" />
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
                <h4
                  className="text-xl font-bold text-slate-800 dark:text-white truncate"
                  title={data?.nome_exibicao}
                >
                  {data?.nome_exibicao}
                </h4>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {data?.resumo.quantidade_notas} nota(s) no período
                  selecionado.
                </p>
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">
                    Gasto Total
                  </p>
                  <p className="text-lg font-bold text-slate-800 dark:text-white">
                    R${" "}
                    {Number(data?.resumo.total_gasto || 0).toLocaleString(
                      "pt-BR",
                      { minimumFractionDigits: 2 },
                    )}
                  </p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">
                    Qtd de Notas
                  </p>
                  <p className="text-lg font-bold text-slate-800 dark:text-white">
                    {data?.resumo.quantidade_notas}
                  </p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 p-4 rounded-2xl">
                  <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">
                    Ticket Médio
                  </p>
                  <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400">
                    R${" "}
                    {Number(data?.resumo.ticket_medio || 0).toLocaleString(
                      "pt-BR",
                      { minimumFractionDigits: 2 },
                    )}
                  </p>
                </div>
              </div>

              {/* Concentration Alert */}
              {data?.concentracao && (
                <div
                  className={`p-4 rounded-2xl flex items-start gap-3 border transition-all ${
                    data.concentracao.nivel === "danger"
                      ? "bg-rose-50/50 dark:bg-rose-900/10 border-rose-100 dark:border-rose-800/50"
                      : data.concentracao.nivel === "warning"
                        ? "bg-amber-50/50 dark:bg-amber-900/10 border-amber-100 dark:border-amber-800/50"
                        : "bg-blue-50/50 dark:bg-blue-900/10 border-blue-100 dark:border-blue-800/50"
                  }`}
                >
                  <ShieldAlert
                    size={18}
                    aria-hidden="true"
                    className={`mt-0.5 shrink-0 ${
                      data.concentracao.nivel === "danger"
                        ? "text-rose-500"
                        : data.concentracao.nivel === "warning"
                          ? "text-amber-500"
                          : "text-blue-500"
                    }`}
                  />
                  <div>
                    <p
                      className={`text-xs font-bold uppercase tracking-tight ${
                        data.concentracao.nivel === "danger"
                          ? "text-rose-800 dark:text-rose-300"
                          : data.concentracao.nivel === "warning"
                            ? "text-amber-800 dark:text-amber-300"
                            : "text-blue-800 dark:text-blue-300"
                      }`}
                    >
                      {data.concentracao.nivel === "danger"
                        ? "Alta Concentração"
                        : data.concentracao.nivel === "warning"
                          ? "Atenção"
                          : "Insight de Gastos"}
                    </p>
                    <p
                      className={`text-[11px] leading-relaxed ${
                        data.concentracao.nivel === "danger"
                          ? "text-rose-700 dark:text-rose-400"
                          : data.concentracao.nivel === "warning"
                            ? "text-amber-700 dark:text-amber-400"
                            : "text-blue-700 dark:text-blue-400"
                      }`}
                    >
                      {data.concentracao.mensagem}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Top Products in Supplier */}
                <section className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
                  <h4 className="font-bold text-slate-800 dark:text-white text-sm mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span>Top Produtos Comprados Aqui</span>
                      <Package size={14} className="text-slate-400" aria-hidden="true" />
                    </div>
                    <button
                      onClick={handleExportProducts}
                      disabled={exporting || loading}
                      className="flex items-center gap-1.5 px-3 py-1 text-[10px] font-bold bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                    >
                      {exporting ? (
                        <div className="animate-spin h-3 w-3 border-2 border-indigo-500 border-t-transparent rounded-full" />
                      ) : (
                        <Download size={12} className="text-indigo-500" />
                      )}
                      <span>Exportar produtos</span>
                    </button>
                  </h4>
                  <div className="space-y-6 flex-1">
                    {data?.top_produtos.map((p, i) => (
                      <div key={i} className="group cursor-default">
                        <div className="flex justify-between items-end mb-1.5 px-0.5">
                          <span
                            className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 truncate max-w-[150px] md:max-w-[250px]"
                            title={p.nome_produto}
                          >
                            {p.nome_produto}
                          </span>
                          <div className="text-right">
                            <span className="font-bold text-slate-800 dark:text-white text-[11px] block">
                              R${" "}
                              {p.total_gasto.toLocaleString("pt-BR", {
                                minimumFractionDigits: 2,
                              })}
                            </span>
                            <span className="text-[9px] text-slate-400 block">
                              {p.quantidade_total} un · R${" "}
                              {p.preco_medio.toLocaleString("pt-BR", {
                                minimumFractionDigits: 2,
                              })}
                              /un
                            </span>
                          </div>
                        </div>
                        <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full transition-all duration-1000 ease-out"
                            style={{
                              width: `${(p.total_gasto / maxProductSpend) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                    {data?.top_produtos.length === 0 && (
                      <div className="h-full flex items-center justify-center text-slate-400 italic">
                        <p className="text-xs">Nenhum produto encontrado.</p>
                      </div>
                    )}
                  </div>
                </section>

                {/* Table */}
                <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
                  <h5 className="text-sm font-bold text-slate-800 dark:text-white mb-6">
                    Últimas Notas
                  </h5>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-bold tracking-widest border-b border-slate-100 dark:border-slate-800">
                          <th className="pb-3 px-2">Data</th>
                          <th className="pb-3 px-2 text-center">Nº Nota</th>
                          <th className="pb-3 px-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                        {data?.notas.map((n, i) => (
                          <tr
                            key={i}
                            className="text-xs hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors"
                          >
                            <td className="py-4 px-2 font-medium text-slate-600 dark:text-slate-400">
                              {new Date(n.data_emissao).toLocaleDateString(
                                "pt-BR",
                              )}
                            </td>
                            <td className="py-4 px-2 text-center text-slate-500">
                              {n.numero_nota}
                            </td>
                            <td className="py-4 px-2 text-right font-bold text-slate-700 dark:text-slate-200">
                              R${" "}
                              {n.valor_total.toLocaleString("pt-BR", {
                                minimumFractionDigits: 2,
                              })}
                            </td>
                          </tr>
                        ))}
                        {data?.notas.length === 0 && (
                          <tr>
                            <td
                              colSpan={3}
                              className="py-8 text-center text-slate-400 italic"
                            >
                              Nenhuma nota encontrada.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
