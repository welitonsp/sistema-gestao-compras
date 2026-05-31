import React from "react";
import { ArrowUpRight } from "lucide-react";
import { AlertaPreco } from "../../types/api";

interface AlertsSectionProps {
  alerts: AlertaPreco[];
}

export const AlertsSection: React.FC<AlertsSectionProps> = ({ alerts }) => (
  <section
    className="bg-slate-900 dark:bg-slate-950 rounded-3xl p-6 md:p-8 shadow-xl shadow-slate-200 dark:shadow-none border dark:border-slate-800 transition-colors h-full flex flex-col"
    aria-labelledby="alerts-title"
  >
    <div className="flex items-center gap-2 mb-6">
      <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" aria-hidden="true" />
      <h3 id="alerts-title" className="text-white font-bold">
        Alertas de Preço
      </h3>
    </div>
    <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar flex-1">
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
