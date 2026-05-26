import React, { useState } from 'react';
import { 
  Users, Shield, Building2, UserPlus, 
  Trash2, Mail, BadgeCheck, MoreVertical,
  Activity, Globe, Zap, Settings
} from 'lucide-react';
import { User, Department } from '../types/api';

interface GestaoViewProps {
  users: User[];
  departments: Department[];
  onRefresh: () => void;
}

export const GestaoView: React.FC<GestaoViewProps> = ({ users, departments, onRefresh }) => {
  const [activeSubTab, setActiveSubTab] = useState<'users' | 'departments' | 'settings'>('users');

  return (
    <div className="space-y-8">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 bg-slate-200/50 dark:bg-slate-800/50 p-1 rounded-2xl w-fit transition-colors">
        <button 
          onClick={() => setActiveSubTab('users')}
          className={`px-6 py-2 rounded-xl text-xs font-bold transition-all ${activeSubTab === 'users' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
        >
          Usuários
        </button>
        <button 
          onClick={() => setActiveSubTab('departments')}
          className={`px-6 py-2 rounded-xl text-xs font-bold transition-all ${activeSubTab === 'departments' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
        >
          Locais
        </button>
        <button 
          onClick={() => setActiveSubTab('settings')}
          className={`px-6 py-2 rounded-xl text-xs font-bold transition-all ${activeSubTab === 'settings' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
        >
          Sistema
        </button>
      </div>

      {activeSubTab === 'users' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-slate-800 dark:text-white flex items-center gap-2">
              <Users className="text-primary-500" size={24} /> Acessos e Usuários
            </h3>
            <button 
              className="flex items-center gap-2 px-6 py-2.5 bg-primary-600 text-white rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-primary-700 transition-all shadow-lg shadow-primary-200 dark:shadow-none"
              aria-label="Convidar novo usuário"
            >
              <UserPlus size={16} /> Novo Usuário
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(users || []).map((user) => (
              <div key={user.id} className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all group relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4">
                  <div className={`h-2 w-2 rounded-full ${user.is_active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-300 dark:bg-slate-700'}`} />
                </div>
                <div className="flex items-center gap-4 mb-6">
                  <div className="h-12 w-12 bg-slate-100 dark:bg-slate-800 rounded-2xl flex items-center justify-center text-primary-600 font-bold text-lg group-hover:bg-primary-600 group-hover:text-white transition-colors">
                    {user.username[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="font-bold text-slate-800 dark:text-slate-200">{user.username}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Shield size={10} className="text-slate-400 dark:text-slate-500" />
                      <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-tighter">{user.role}</span>
                    </div>
                  </div>
                </div>
                <div className="space-y-3 pt-4 border-t border-slate-50 dark:border-slate-800">
                  <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <Mail size={14} className="text-slate-300 dark:text-slate-600" />
                    <span className="truncate">{user.email || '—'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <Building2 size={14} className="text-slate-300 dark:text-slate-600" />
                    <span>{(departments || []).find(d => d.id === user.department_id)?.name || 'Pessoal'}</span>
                  </div>
                </div>
                <div className="mt-6 pt-2 flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button className="p-2 text-slate-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded-lg transition-colors" aria-label={`Configurar ${user.username}`}><Settings size={16} /></button>
                  <button className="p-2 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-900/30 rounded-lg transition-colors" aria-label={`Excluir ${user.username}`}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeSubTab === 'departments' && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden p-8 transition-colors">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-xl font-bold text-slate-800 dark:text-white">Meus Locais de Compra</h3>
            <button 
              className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-xl text-xs font-bold hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
              aria-label="Adicionar novo local de compra"
            >
              Adicionar Local
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(departments || []).map((dept) => (
              <div key={dept.id} className="p-5 border border-slate-100 dark:border-slate-800 rounded-2xl hover:border-primary-200 dark:hover:border-primary-800 transition-colors flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 p-3 rounded-xl"><Building2 size={20} /></div>
                  <div>
                    <p className="font-bold text-slate-800 dark:text-slate-200 text-sm">{dept.name}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500 font-medium">ID: {dept.id.slice(0, 8)}...</p>
                  </div>
                </div>
                <BadgeCheck className="text-emerald-500" size={20} />
              </div>
            ))}
          </div>
        </div>
      )}

      {activeSubTab === 'settings' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { label: 'Status da API', icon: Zap, value: 'Operacional', color: 'emerald' },
            { label: 'Sincronização', icon: Globe, value: 'Ativa', color: 'primary' },
            { label: 'Saúde do Sistema', icon: BadgeCheck, value: 'Otimizada', color: 'indigo' }
          ].map((item, i) => (
            <div key={i} className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 flex flex-col items-center text-center gap-4 transition-colors">
              <div className={`p-4 rounded-2xl bg-${item.color}-50 dark:bg-${item.color}-900/20 text-${item.color}-600 dark:text-${item.color}-400`}>
                <item.icon size={32} />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">{item.label}</p>
                <p className="text-xl font-bold text-slate-800 dark:text-white">{item.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
