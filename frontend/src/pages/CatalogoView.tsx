import React, { useState, useEffect } from 'react';
import { Package, Search, Download, Edit2, Check, X, Sparkles, AlertCircle, Wand2 } from 'lucide-react';
import { Produto } from '../types/api';
import { apiClient } from '../api/client';

interface Suggestion {
  type: string;
  primary: any;
  suggestion: any;
  reason: string;
}

interface CatalogoViewProps {
  produtos: Produto[];
  search: string;
  onSearchChange: (val: string) => void;
  onExport: () => void;
  editingEan: string | null;
  editValue: string;
  onEditStart: (p: Produto) => void;
  onEditChange: (val: string) => void;
  onEditSave: (ean: string) => void;
  onEditCancel: () => void;
  onRefresh: () => void;
}

export const CatalogoView: React.FC<CatalogoViewProps> = ({ 
  produtos, search, onSearchChange, onExport, 
  editingEan, editValue, onEditStart, onEditChange, onEditSave, onEditCancel, onRefresh
}) => {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        const data = await apiClient.get<Suggestion[]>('/produtos/maintenance');
        setSuggestions(data);
      } catch (e) { console.error(e); }
    };
    fetchSuggestions();
  }, []);

  const handleApplyHeal = async (ean: string, targetData: any) => {
    try {
      await apiClient.post(`/produtos/${ean}/heal`, targetData);
      setSuggestions(prev => prev.filter(s => s.primary.ean !== ean));
      onRefresh();
    } catch (e) { alert("Erro ao aplicar autocura."); }
  };

  return (
    <div className="space-y-6">
      {suggestions.length > 0 && (
        <div className="bg-indigo-50 border-l-4 border-indigo-500 p-6 rounded-r-2xl shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="text-indigo-600" size={20} />
              <h3 className="font-black text-indigo-900 text-sm uppercase tracking-wider">Sugestões de Autocura de IA</h3>
            </div>
            <button 
              onClick={() => setShowSuggestions(!showSuggestions)}
              className="text-[10px] font-black text-indigo-600 bg-white px-3 py-1 rounded-full border border-indigo-200 hover:bg-indigo-600 hover:text-white transition-all"
            >
              {showSuggestions ? 'OCULTAR' : `VER ${suggestions.length} ALERTAS`}
            </button>
          </div>
          
          {showSuggestions && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in slide-in-from-top duration-300">
              {suggestions.map((s, i) => (
                <div key={i} className="bg-white/80 p-4 rounded-xl border border-indigo-100 flex flex-col gap-3">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <p className="text-[10px] font-black text-slate-400 uppercase">Item Inconsistente</p>
                      <p className="font-bold text-slate-800 text-xs">{s.primary.nome}</p>
                      <p className="text-[9px] text-slate-500">Cat: {s.primary.categoria} | Marca: {s.primary.marca || '-'}</p>
                    </div>
                    <Wand2 size={16} className="text-indigo-400" />
                  </div>
                  <div className="bg-indigo-50/50 p-2 rounded-lg border border-dashed border-indigo-200">
                    <p className="text-[9px] font-black text-indigo-600 uppercase mb-1">IA sugere unificar com:</p>
                    <p className="text-xs font-bold text-slate-700">{s.suggestion.nome}</p>
                    <p className="text-[9px] text-slate-500">Novo Alinhamento: <b>{s.suggestion.categoria} / {s.suggestion.marca}</b></p>
                  </div>
                  <button 
                    onClick={() => handleApplyHeal(s.primary.ean, { categoria: s.suggestion.categoria, marca: s.suggestion.marca, nome_limpo: s.suggestion.nome })}
                    className="mt-2 w-full bg-indigo-600 text-white py-2 rounded-lg text-[10px] font-black uppercase tracking-widest hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
                  >
                    <Sparkles size={14} /> Aplicar Unificação
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <main className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Package className="text-slate-400" aria-hidden="true" />
            Catálogo de Produtos
          </h3>
          <div className="flex items-center gap-4 w-full md:w-auto">
            <div className="relative w-full md:w-64">
              <label htmlFor="busca-produto" className="sr-only">Buscar produto por nome ou EAN</label>
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} aria-hidden="true" />
              <input 
                id="busca-produto"
                type="text" 
                placeholder="Buscar EAN ou Nome..." 
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                className="w-full pl-10 pr-4 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
            <button 
              type="button" 
              onClick={onExport}
              className="text-xs flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-md font-medium transition-colors focus:ring-2 focus:ring-offset-1 focus:ring-slate-300 outline-none shrink-0"
            >
              <Download size={14} aria-hidden="true" /> Exportar CSV
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" aria-label="Catálogo de produtos">
            <thead className="bg-slate-50 text-slate-500 text-[10px] uppercase tracking-wider font-semibold">
              <tr>
                <th className="px-6 py-3 border-b border-slate-100">EAN / Código</th>
                <th className="px-6 py-3 border-b border-slate-100">Descrição Canônica</th>
                <th className="px-6 py-3 border-b border-slate-100">Marca</th>
                <th className="px-6 py-3 border-b border-slate-100">Categoria (IA)</th>
                <th className="px-6 py-3 border-b border-slate-100 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="text-[13px] text-slate-700">
              {produtos.map((p) => (
                <tr key={p.ean} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-6 py-3 border-b border-slate-100 font-mono text-[10px] text-slate-600">{p.ean}</td>
                  <td className="px-6 py-3 border-b border-slate-100 font-medium">{p.nome_limpo}</td>
                  <td className="px-6 py-3 border-b border-slate-100">{p.marca || '-'}</td>
                  <td className="px-6 py-3 border-b border-slate-100">
                    {editingEan === p.ean ? (
                      <input 
                        autoFocus
                        aria-label={`Editar categoria de ${p.nome_limpo}`}
                        value={editValue}
                        onChange={(e) => onEditChange(e.target.value)}
                        className="bg-white border border-blue-400 px-2 py-0.5 rounded outline-none w-full"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') onEditSave(p.ean);
                          if (e.key === 'Escape') onEditCancel();
                        }}
                      />
                    ) : (
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${p.categoria === 'Não Classificado' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                        {p.categoria}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3 border-b border-slate-100 text-right">
                    {editingEan === p.ean ? (
                      <div className="flex justify-end gap-2">
                        <button onClick={() => onEditSave(p.ean)} className="text-green-600 hover:text-green-800" aria-label="Salvar categoria"><Check size={16} aria-hidden="true" /></button>
                        <button onClick={onEditCancel} className="text-red-600 hover:text-red-800" aria-label="Cancelar edição"><X size={16} aria-hidden="true" /></button>
                      </div>
                    ) : (
                      <button 
                        onClick={() => onEditStart(p)}
                        className="text-slate-400 hover:text-blue-600 transition-colors"
                        aria-label="Editar categoria"
                      >
                        <Edit2 size={14} aria-hidden="true" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
};
