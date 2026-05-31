import React from "react";
import { Download, ChevronDown } from "lucide-react";

interface ExportMenuProps {
  exportMenuOpen: boolean;
  setExportMenuOpen: (open: boolean) => void;
  exportMenuRef: React.RefObject<HTMLDivElement>;
  exporting: string | null;
  onExport: (dataset: string) => void;
}

export const ExportMenu: React.FC<ExportMenuProps> = ({
  exportMenuOpen,
  setExportMenuOpen,
  exportMenuRef,
  exporting,
  onExport,
}) => {
  return (
    <div className="relative" ref={exportMenuRef}>
      <button
        onClick={() => setExportMenuOpen(!exportMenuOpen)}
        disabled={!!exporting}
        aria-label="Exportar dados do dashboard"
        aria-haspopup="menu"
        aria-expanded={exportMenuOpen}
        className="flex items-center gap-2 px-4 py-1.5 text-xs font-bold bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-all disabled:opacity-50"
      >
        {exporting ? (
          <div className="animate-spin h-3 w-3 border-2 border-indigo-500 border-t-transparent rounded-full" />
        ) : (
          <Download size={14} className="text-indigo-500" />
        )}
        <span>Exportar</span>
        <ChevronDown
          size={12}
          className={`text-slate-400 transition-transform ${exportMenuOpen ? "rotate-180" : ""}`}
        />
      </button>

      {exportMenuOpen && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="py-1">
            {[
              { id: "top_produtos", label: "Top Produtos" },
              { id: "top_fornecedores", label: "Top Fornecedores" },
              { id: "evolucao_mensal", label: "Evolução Mensal" },
              { id: "alertas", label: "Alertas de Risco" },
            ].map((item) => (
              <button
                key={item.id}
                role="menuitem"
                onClick={() => {
                  setExportMenuOpen(false);
                  onExport(item.id);
                }}
                className="w-full text-left px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
