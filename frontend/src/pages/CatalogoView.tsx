import React, { useState, useEffect } from 'react';
import { 
  Package, Search, Download, Edit2, Check, X, 
  Sparkles, Wand2, Filter, ChevronRight, Hash,
  Tag, Layers, Info
} from 'lucide-react';
import { Produto } from '../types/api';
import { apiClient } from '../api/client';
import { Skeleton } from '../components/Skeleton';
import { CanonizationReviewTab } from '../components/CanonizationReviewTab';
import { CategoryReviewTab } from '../components/CategoryReviewTab';

interface Suggestion {
  type: string;
  primary: any;
  suggestion: any;
  reason: string;
}

interface CatalogoViewProps {
  produtos: Produto[] | null;
  onRefresh: () => void;
  onExport?: () => void;
}

type CatalogTab = 'products' | 'category-review' | 'canonization-review';

export const CatalogoView: React.FC<CatalogoViewProps> = ({ produtos, onRefresh, onExport }) => {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [search, setSearch] = useState('');
  const [editingEan, setEditingEan] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [filterCategory, setFilterCategory] = useState('Todas');
  const [activeTab, setActiveTab] = useState<CatalogTab>('products');

  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        const data = await apiClient.get<Suggestion[]>('/produtos/maintenance');
        setSuggestions(data || []);
      } catch (e) { console.error(e); }
    };
    fetchSuggestions();
  }, []);

  const handleUpdateCategory = async (ean: string) => {
    try {
      await apiClient.patch(`/produtos/${ean}`, { categoria: editValue });
      setEditingEan(null);
      onRefresh();
    } catch (err) {
      alert('Erro ao atualizar categoria');
    }
  };

  const handleApplyHeal = async (ean: string, targetData: any) => {
    try {
      await apiClient.post(`/produtos/${ean}/heal`, targetData);
      setSuggestions(prev => prev.filter(s => s.primary.ean !== ean));
      onRefresh();
    } catch (e) { alert("Erro ao aplicar autocura."); }
  };

  const categories = ['Todas', ...Array.from(new Set((produtos || []).map(p => p.categoria)))];

  const filtered = (produtos || []).filter(p => {
    const matchesSearch = p.nome_limpo.toLowerCase().includes(search.toLowerCase()) || p.ean.includes(search);
    const matchesCat = filterCategory === 'Todas' || p.categoria === filterCategory;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-1 w-fit shadow-sm">
        <button
          onClick={() => setActiveTab('products')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'products'
              ? 'bg-primary-600 text-white shadow-md shadow-primary-200'
              : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
          aria-pressed={activeTab === 'products'}
        >
          Meus Produtos
        </button>
        <button
          onClick={() => setActiveTab('category-review')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'category-review'
              ? 'bg-primary-600 text-white shadow-md shadow-primary-200'
              : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
          aria-pressed={activeTab === 'category-review'}
        >
          Revisar Categorias
        </button>
        <button
          onClick={() => setActiveTab('canonization-review')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'canonization-review'
              ? 'bg-primary-600 text-white shadow-md shadow-primary-200'
              : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
          aria-pressed={activeTab === 'canonization-review'}
        >
          Canonização (Beta)
        </button>
      </div>

      {activeTab === 'products' ? (
        <>
      {/* Suggestions Section */}
      {suggestions.length > 0 && (
        <div className="bg-primary-600 rounded-3xl p-6 shadow-xl shadow-primary-200 overflow-hidden relative transition-all">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none text-white">
            <Sparkles size={120} />
          </div>
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="bg-white/20 p-3 rounded-2xl backdrop-blur-md">
                <Wand2 className="text-white" size={24} />
              </div>
              <div>
                <h3 className="text-white font-bold text-lg">Inteligência de Catálogo</h3>
                <p className="text-primary-100 text-sm">Encontramos {suggestions.length} oportunidades de unificação e correção.</p>
              </div>
            </div>
            <button 
              onClick={() => setShowSuggestions(!showSuggestions)}
              className="px-6 py-2 bg-white text-primary-600 rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-primary-50 transition-all shadow-lg"
              aria-expanded={showSuggestions}
              aria-label={showSuggestions ? "Esconder sugestões" : "Ver sugestões de unificação"}
            >
              {showSuggestions ? 'Recolher' : 'Analisar Sugestões'}
            </button>
          </div>
          
          {showSuggestions && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8 animate-in slide-in-from-top duration-500">
              {suggestions.map((s, i) => (
                <div key={i} className="bg-white dark:bg-slate-900 p-5 rounded-2xl flex flex-col gap-4 border border-primary-100 dark:border-slate-800 shadow-sm">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <span className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-tighter">Inconsistência Detectada</span>
                      <p className="font-bold text-slate-800 dark:text-slate-200 text-sm leading-tight">{s.primary.nome}</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1"><Tag size={10} /> {s.primary.categoria}</p>
                    </div>
                    <div className="bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 p-1.5 rounded-lg"><Info size={14} /></div>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800 p-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-700">
                    <p className="text-[11px] font-bold text-primary-600 dark:text-primary-400 uppercase mb-2">Sugestão de Alinhamento</p>
                    <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{s.suggestion.nome}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-500 font-medium">{s.suggestion.categoria} • {s.suggestion.marca}</p>
                  </div>
                  <button 
                    onClick={() => handleApplyHeal(s.primary.ean, { categoria: s.suggestion.categoria, marca: s.suggestion.marca, nome_limpo: s.suggestion.nome })}
                    className="w-full bg-primary-600 text-white py-2.5 rounded-xl text-[11px] font-bold uppercase tracking-widest hover:bg-primary-700 transition-all flex items-center justify-center gap-2"
                  >
                    Unificar Produtos
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Table Section */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden transition-colors">
        <div className="p-8 border-b border-slate-100 dark:border-slate-800 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <h3 className="text-xl font-bold text-slate-800 dark:text-white flex items-center gap-3">
              <div className="bg-slate-100 dark:bg-slate-800 p-2 rounded-xl text-slate-500 dark:text-slate-400"><Layers size={20} /></div>
              Meus Produtos
            </h3>
            <div className="flex items-center gap-3">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary-500 transition-colors" size={18} />
                <input 
                  type="text" 
                  placeholder="Buscar por nome ou EAN..." 
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full md:w-80 pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-sm dark:text-white focus:ring-4 focus:ring-primary-100 dark:focus:ring-primary-900/20 focus:bg-white dark:focus:bg-slate-800 focus:border-primary-500 outline-none transition-all"
                  aria-label="Buscar produtos no catálogo"
                />
              </div>
              <button 
                onClick={onExport}
                className="p-2.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-2xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                aria-label="Exportar catálogo em CSV"
              >
                <Download size={18} />
              </button>
              <button 
                className="p-2.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-2xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                aria-label="Abrir filtros avançados"
              >
                <Filter size={18} />
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {categories.length <= 8 ? (
              categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setFilterCategory(cat)}
                  className={`px-4 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${filterCategory === cat ? 'bg-primary-600 text-white shadow-md shadow-primary-200' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'}`}
                  aria-pressed={filterCategory === cat}
                >
                  {cat}
                </button>
              ))
            ) : (
              <div className="flex items-center gap-3 w-full md:w-auto">
                <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest whitespace-nowrap">Filtrar por:</span>
                <select 
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="flex-1 md:w-64 px-4 py-2 bg-slate-100 dark:bg-slate-800 border-none rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 outline-none focus:ring-2 focus:ring-primary-500 transition-all cursor-pointer"
                  aria-label="Selecionar categoria de produto"
                >
                  {categories.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 text-xs uppercase font-bold tracking-widest">
                <th className="px-8 py-4">Produto</th>
                <th className="px-8 py-4">Código EAN</th>
                <th className="px-8 py-4">Marca</th>
                <th className="px-8 py-4">Categoria</th>
                <th className="px-8 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {!produtos ? (
                [1, 2, 3, 4, 5].map((i) => (
                  <tr key={i}>
                    <td className="px-8 py-5"><Skeleton className="h-4 w-64" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-6 w-32 rounded-lg" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-8 py-5"><Skeleton className="h-8 w-32 rounded-xl" /></td>
                    <td className="px-8 py-5 text-right"><Skeleton className="h-8 w-8 rounded-lg ml-auto" /></td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-8 py-20 text-center text-slate-400 dark:text-slate-600">
                    <Package size={40} className="mx-auto mb-4 opacity-20" />
                    <p className="text-sm font-medium">Nenhum item encontrado</p>
                  </td>
                </tr>
              ) : (
                filtered.map((p) => (
                  <tr key={p.ean} className="group hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-8 py-5">
                      <p className="text-sm font-bold text-slate-700 dark:text-slate-200">{p.nome_limpo}</p>
                    </td>
                    <td className="px-8 py-5">
                      <span className="flex items-center gap-1.5 text-xs font-mono text-slate-400 dark:text-slate-500 bg-slate-100/50 dark:bg-slate-800/50 px-2 py-1 rounded-lg w-fit">
                        <Hash size={12} /> {p.ean}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-sm text-slate-500 dark:text-slate-400">{p.marca || '—'}</td>
                    <td className="px-8 py-5">
                      {editingEan === p.ean ? (
                        <div className="flex items-center gap-2 animate-in fade-in zoom-in duration-200">
                          <input 
                            autoFocus
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="bg-white dark:bg-slate-800 border-2 border-primary-500 px-3 py-1.5 rounded-xl text-sm dark:text-white outline-none w-full shadow-lg"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleUpdateCategory(p.ean);
                              if (e.key === 'Escape') setEditingEan(null);
                            }}
                            aria-label={`Editar categoria de ${p.nome_limpo}`}
                          />
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 group-hover:bg-primary-50 dark:group-hover:bg-primary-900/30 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors uppercase">
                          {p.categoria}
                        </span>
                      )}
                    </td>
                    <td className="px-8 py-5 text-right">
                      {editingEan === p.ean ? (
                        <div className="flex justify-end gap-1">
                          <button onClick={() => handleUpdateCategory(p.ean)} className="p-2 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded-lg transition-colors" aria-label="Confirmar alteração"><Check size={18} /></button>
                          <button onClick={() => setEditingEan(null)} className="p-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-900/30 rounded-lg transition-colors" aria-label="Cancelar alteração"><X size={18} /></button>
                        </div>
                      ) : (
                        <button 
                          onClick={() => { setEditingEan(p.ean); setEditValue(p.categoria); }}
                          className="p-2 text-slate-300 dark:text-slate-600 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded-xl transition-all opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0"
                          aria-label={`Editar ${p.nome_limpo}`}
                        >
                          <Edit2 size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
        </>
      ) : activeTab === 'category-review' ? (
        <CategoryReviewTab />
      ) : (
        <CanonizationReviewTab />
      )}
    </div>
  );
};
