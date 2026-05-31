import React from "react";
import { Activity } from "lucide-react";
import { DataHealthMetrics } from "../../types/api";

interface DataHealthCardProps {
  metrics: DataHealthMetrics;
}

export const DataHealthCard: React.FC<DataHealthCardProps> = ({ metrics }) => {
  const getStatusColor = (nivel: string) => {
    switch (nivel) {
      case "ok":
        return "text-emerald-500 bg-emerald-500/10";
      case "warning":
        return "text-amber-500 bg-amber-500/10";
      case "danger":
        return "text-rose-500 bg-rose-500/10";
      default:
        return "text-slate-500 bg-slate-500/10";
    }
  };

  const statusColor = getStatusColor(metrics.nivel);

  return (
    <section className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full">
      <h3 className="font-bold text-slate-800 dark:text-white text-sm mb-6 flex items-center justify-between">
        Integridade de Extração
        <Activity size={16} className="text-slate-400" />
      </h3>

      <div className="flex flex-col items-center justify-center py-4">
        <div
          className={`text-4xl font-black mb-2 ${statusColor.split(" ")[0]}`}
        >
          {metrics.percentual_saude}%
        </div>
        <div
          className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${statusColor}`}
        >
          Saúde dos Dados: {metrics.nivel === "ok" ? "Excelente" : metrics.nivel === "warning" ? "Atenção" : "Crítica"}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Total Notas
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.total_notas}
          </div>
        </div>
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Divergências
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.total_mismatches}
          </div>
        </div>
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Itens S/ EAN
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.itens_sem_ean}
          </div>
        </div>
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Notas Falhas
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.notas_failed}
          </div>
        </div>
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Dados Inválidos
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.quantidades_invalidas + metrics.valores_invalidos}
          </div>
        </div>
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
            Desc. Vazias
          </div>
          <div className="text-lg font-bold text-slate-700 dark:text-slate-200">
            {metrics.descricoes_vazias}
          </div>
        </div>
      </div>

      <p className="mt-6 text-[10px] text-slate-400 leading-relaxed italic">
        * Esta métrica avalia a qualidade técnica da importação e extração de dados, não representa conformidade tributária ou fiscal legal.
      </p>
    </section>
  );
};
