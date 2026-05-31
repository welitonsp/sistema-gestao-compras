import React from "react";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { AlertaRisco } from "../../types/api";

interface RiskAlertsSectionProps {
  alerts: AlertaRisco[];
}

export const RiskAlertsSection: React.FC<RiskAlertsSectionProps> = ({ alerts }) => {
  if (alerts.length === 0) {
    return (
      <div className="bg-emerald-50/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-800/50 p-4 rounded-2xl flex items-center gap-3">
        <CheckCircle2 size={18} className="text-emerald-500" />
        <p className="text-emerald-700 dark:text-emerald-400 text-xs font-medium">
          Nenhum risco relevante encontrado neste período.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {alerts.map((alert, i) => {
        const severityColors = {
          info: "blue",
          warning: "amber",
          danger: "rose",
        };
        const color =
          severityColors[alert.severidade as keyof typeof severityColors] ||
          "slate";

        return (
          <div
            key={i}
            className={`bg-${color}-50/50 dark:bg-${color}-900/10 border border-${color}-100 dark:border-${color}-800/50 p-4 rounded-2xl flex items-start gap-3 hover:shadow-sm transition-all`}
          >
            <ShieldAlert
              size={18}
              className={`text-${color}-500 mt-0.5 shrink-0`}
            />
            <div className="space-y-1">
              <h4
                className={`text-${color}-800 dark:text-${color}-300 text-xs font-bold uppercase tracking-tight`}
              >
                {alert.titulo}
              </h4>
              <p
                className={`text-${color}-700 dark:text-${color}-400 text-[11px] leading-relaxed`}
              >
                {alert.mensagem}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
