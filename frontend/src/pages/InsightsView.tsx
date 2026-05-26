import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, AlertTriangle, BarChart3, 
  Zap, ShieldAlert, Sparkles, RefreshCw 
} from 'lucide-react';
import { apiClient } from '../api/client';
import { Skeleton } from '../components/Skeleton';

export const InsightsView: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  const fetchInsights = async () => {
    setLoading(true);
    try {
      const [duplicatas, estatisticos, tendencia, forecast, volatilidade] = await Promise.all([
        apiClient.get<any[]>('/dashboard/alertas/duplicidade'),
        apiClient.get<any[]>('/dashboard/alertas/estatisticos'),
        apiClient.get<any[]>('/dashboard/insights/tendencia'),
        apiClient.get<any[]>('/dashboard/insights/forecast'),
        apiClient.get<any[]>('/dashboard/insights/volatilidade'),
      ]);

      setData({
        duplicatas,
        estatisticos,
        tendencia,
        forecast,
        volatilidade
      });
    } catch (err) {
      console.error("Erro ao buscar insights", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="h-8 w-64 bg-slate-200 dark:bg-slate-800 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-3xl" />
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-3xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Insights Avançados</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">Análises estatísticas e previsões geradas pela IA.</p>
        </div>
        <button 
          onClick={fetchInsights}
          className="p-2 text-slate-400 hover:text-primary-600 transition-colors"
        >
          <RefreshCw size={20} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Forecast */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 rounded-xl"><Sparkles size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Previsão de Gastos</h3>
          </div>
          <div className="space-y-4">
            {data?.forecast?.map((item: any, i: number) => (
              <div key={i} className="flex justify-between items-center text-sm">
                <span className="text-slate-500 dark:text-slate-400">{item.categoria}</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">R$ {Number(item.projeção_proximo_mes).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Duplicidade */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-rose-50 dark:bg-rose-900/20 text-rose-600 rounded-xl"><ShieldAlert size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Possíveis Duplicidades</h3>
          </div>
          {data?.duplicatas?.length === 0 ? (
            <p className="text-xs text-slate-400 italic">Nenhuma nota suspeita detectada.</p>
          ) : (
            <div className="space-y-3">
              {data?.duplicatas?.slice(0, 3).map((item: any, i: number) => (
                <div key={i} className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl text-xs">
                  <p className="font-bold text-slate-700 dark:text-slate-300">Nota {item.numero_nota}</p>
                  <p className="text-slate-500 mt-1">Valor: R$ {item.valor_total}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Volatilidade */}
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-amber-50 dark:bg-amber-900/20 text-amber-600 rounded-xl"><Zap size={18} /></div>
            <h3 className="font-bold text-slate-800 dark:text-white">Alta Volatilidade</h3>
          </div>
          <div className="space-y-3">
            {data?.volatilidade?.slice(0, 5).map((item: any, i: number) => (
              <div key={i} className="flex justify-between items-center text-xs">
                <span className="text-slate-500 truncate max-w-[150px]">{item.produto}</span>
                <span className="font-bold text-amber-600">{item.variacao_maxima}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="bg-indigo-600 rounded-3xl p-8 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 p-12 opacity-10"><TrendingUp size={120} /></div>
        <div className="relative z-10">
          <h3 className="text-xl font-bold mb-2">Tendência de Preços</h3>
          <p className="text-indigo-100 text-sm mb-6 max-w-xl">
            Acompanhe a evolução dos preços médios em todas as categorias. 
            Este módulo utiliza regressão linear para identificar padrões sazonais.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {data?.tendencia?.slice(0, 4).map((item: any, i: number) => (
              <div key={i} className="bg-white/10 backdrop-blur-md p-4 rounded-2xl border border-white/10">
                <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-200 mb-1">{item.mes}</p>
                <p className="text-lg font-bold">R$ {Number(item.preco_medio).toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
