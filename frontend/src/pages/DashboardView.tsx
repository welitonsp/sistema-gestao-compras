import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LineChart, Line } from 'recharts';
import { ShoppingCart, BrainCircuit, BarChart3, TrendingUp, TrendingDown, History } from 'lucide-react';
import { DashboardResumo, AlertaPreco, AnomaliaEstatistica, ForecastInfo } from '../types/api';

const COLORS = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'];

interface DashboardViewProps {
  data: DashboardResumo | null;
  alerts: AlertaPreco[];
  duplicatas: any[];
  anomalias: AnomaliaEstatistica[];
  forecasts: ForecastInfo[];
  chartData: any[];
  trendData: any[];
}

export const DashboardView: React.FC<DashboardViewProps> = ({ data, alerts, duplicatas, anomalias, forecasts, chartData, trendData }) => {
  return (
    <main className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {duplicatas.length > 0 && (
          <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-xl">
            <h3 className="font-bold text-amber-900 text-xs mb-2 uppercase tracking-widest">⚠️ Possíveis Duplicidades ({duplicatas.length})</h3>
            {duplicatas.slice(0, 1).map((dup, i) => (
              <div key={i} className="text-[10px] text-amber-800">
                <b>{dup.fornecedor}</b> - R$ {dup.valor.toLocaleString('pt-BR')}
              </div>
            ))}
          </div>
        )}
        {anomalias.length > 0 && (
          <div className="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-xl">
            <div className="flex items-center gap-2 mb-2">
              <BrainCircuit size={16} className="text-rose-600" />
              <h3 className="font-bold text-rose-900 text-xs uppercase tracking-widest">🔍 Anomalias Z-Score</h3>
            </div>
            {anomalias.slice(0, 1).map((anom, i) => (
              <div key={i} className="flex justify-between items-center text-[10px] text-rose-800">
                <span className="font-bold truncate max-w-[200px]">{anom.produto}</span>
                <span className="font-black text-rose-600 bg-white/50 px-1.5 py-0.5 rounded">{anom.z_score.toFixed(1)}σ</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-2xl border shadow-sm flex flex-col">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-3 bg-blue-100 rounded-xl text-blue-600">
              <ShoppingCart size={24} aria-hidden="true" />
            </div>
            <div>
              <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest">Total Liquidado</p>
              <p className="text-3xl font-black text-slate-900">
                R$ {data?.total_geral.toLocaleString('pt-BR')}
              </p>
            </div>
          </div>
          <div className="h-48 mt-auto">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" hide />
                <YAxis fontSize={10} axisLine={false} tickLine={false} />
                <Tooltip cursor={{fill: '#f8fafc'}} contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'}} />
                <Bar dataKey="total" radius={[6, 6, 0, 0]}>
                  {chartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl border shadow-sm flex flex-col">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-3 bg-indigo-100 rounded-xl text-indigo-600">
              <History size={24} aria-hidden="true" />
            </div>
            <div>
              <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest">Tendência de Preços</p>
              <p className="text-sm font-bold text-slate-600 italic">Oscilação Média Mensal</p>
            </div>
          </div>
          <div className="h-48 mt-auto">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="mes" fontSize={10} axisLine={false} tickLine={false} />
                <YAxis fontSize={10} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'}} />
                <Line type="monotone" dataKey="valor" stroke="#4f46e5" strokeWidth={4} dot={{ r: 4, fill: '#4f46e5', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white p-6 rounded-2xl border shadow-sm">
        <h3 className="text-[10px] font-black mb-6 text-blue-600 uppercase tracking-widest flex items-center gap-2">
          <BarChart3 size={14} /> Forecast e Projecção Financeira
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {forecasts.slice(0, 6).map((f, i) => (
            <div key={i} className="p-4 bg-slate-50 rounded-xl border border-slate-100 relative overflow-hidden group hover:border-blue-200 transition-all">
              <div className="flex justify-between items-start mb-2">
                <p className="font-black text-slate-800 text-[11px] uppercase truncate max-w-[70%]">{f.categoria}</p>
                <span className={`text-[9px] px-2 py-0.5 rounded-full font-black flex items-center gap-1 ${
                  f.tendencia === 'Alta' ? 'bg-red-100 text-red-700' : 
                  f.tendencia === 'Queda' ? 'bg-green-100 text-green-700' : 
                  'bg-blue-100 text-blue-700'
                }`}>
                  {f.tendencia === 'Alta' ? <TrendingUp size={10} /> : f.tendencia === 'Queda' ? <TrendingDown size={10} /> : null}
                  {f.tendencia.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between items-end mt-4">
                <div>
                  <p className="text-[9px] text-slate-400 font-bold uppercase">Média Atual</p>
                  <p className="text-sm font-bold text-slate-600">R$ {f.media_atual.toFixed(0)}</p>
                </div>
                <div className="text-right">
                  <p className="text-[9px] text-blue-400 font-bold uppercase">Projetado</p>
                  <p className="text-lg font-black text-blue-600">R$ {f.projeção_proximo_mes.toFixed(0)}</p>
                </div>
              </div>
              <div className="w-full bg-slate-200 h-1.5 rounded-full mt-3 overflow-hidden">
                <div 
                  className={`h-full transition-all duration-1000 ${f.tendencia === 'Alta' ? 'bg-red-500' : 'bg-blue-500'}`} 
                  style={{ width: `${Math.min((f.media_atual / f.projeção_proximo_mes) * 100, 100)}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
};
