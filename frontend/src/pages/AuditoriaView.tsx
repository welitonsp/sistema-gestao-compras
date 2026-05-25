import React from 'react';
import { History, Info, Download } from 'lucide-react';
import { AuditLog } from '../types/api';

interface AuditoriaViewProps {
  logs: AuditLog[];
  onExport: () => void;
}

export const AuditoriaView: React.FC<AuditoriaViewProps> = ({ logs, onExport }) => {
  return (
    <main className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <History className="text-slate-400" aria-hidden="true" />
          Trilha de Auditoria (Audit Trail)
        </h3>
        <div className="flex items-center gap-4">
          <div className="text-xs text-slate-600 flex items-center gap-1">
            <Info size={14} aria-hidden="true" /> Exibindo os últimos 50 eventos
          </div>
          <button 
            type="button" 
            onClick={onExport}
            className="text-xs flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-md font-medium transition-colors focus:ring-2 focus:ring-offset-1 focus:ring-slate-300 outline-none"
          >
            <Download size={14} aria-hidden="true" /> Exportar CSV
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" aria-label="Tabela de logs de auditoria">
          <thead className="bg-slate-50 text-slate-500 text-[10px] uppercase tracking-wider font-semibold">
            <tr>
              <th className="px-6 py-3 border-b border-slate-100">Data/Hora</th>
              <th className="px-6 py-3 border-b border-slate-100">Usuário</th>
              <th className="px-6 py-3 border-b border-slate-100">Operação</th>
              <th className="px-6 py-3 border-b border-slate-100">Detalhes</th>
              <th className="px-6 py-3 border-b border-slate-100 text-right">IP</th>
            </tr>
          </thead>
          <tbody className="text-[13px] text-slate-700">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-6 py-3 border-b border-slate-100 whitespace-nowrap text-slate-500 text-xs">
                  {new Date(log.criado_em).toLocaleString('pt-BR')}
                </td>
                <td className="px-6 py-3 border-b border-slate-100">
                  <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase">{log.usuario}</span>
                </td>
                <td className="px-6 py-3 border-b border-slate-100 font-mono text-[10px] font-bold">
                  {log.operacao}
                </td>
                <td className="px-6 py-3 border-b border-slate-100 max-w-xs truncate" title={log.detalhes || ''}>
                  {log.detalhes}
                </td>
                <td className="px-6 py-3 border-b border-slate-100 text-right font-mono text-[10px] text-slate-500">
                  {log.ip_origem}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
};
