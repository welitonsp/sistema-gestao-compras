import React from 'react';
import { Users, UserPlus, Globe, Trash2, Plus, Power, Shield } from 'lucide-react';
import { User, Department } from '../types/api';

interface Webhook {
  id: string;
  name: string;
  url: string;
  is_active: boolean;
}

interface GestaoViewProps {
  users: User[];
  departments: Department[];
  webhooks: Webhook[];
  onDeleteWebhook: (id: string) => void;
  onAddUser: () => void;
  onToggleUser: (user: User) => void;
}

export const GestaoView: React.FC<GestaoViewProps> = ({ users, departments, webhooks, onDeleteWebhook, onAddUser, onToggleUser }) => {
  return (
    <main className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="p-4 border-b flex justify-between items-center bg-slate-50">
            <h3 className="font-black flex items-center gap-2 text-sm text-slate-800">
              <Users size={18} className="text-blue-600" /> CONTROLE DE ACESSOS
            </h3>
            <button 
              onClick={onAddUser}
              className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider hover:bg-blue-700 transition-all flex items-center gap-1"
            >
              <UserPlus size={14} /> Novo Usuário
            </button>
          </div>
          <table className="w-full text-left text-[10px]">
            <thead className="bg-slate-100 text-slate-500 uppercase font-black border-b border-slate-200">
              <tr>
                <th className="p-4">Identidade</th>
                <th className="p-4">Perfil</th>
                <th className="p-4">Unidade</th>
                <th className="p-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-slate-50 transition-colors">
                  <td className="p-4">
                    <p className="font-black text-slate-900">{u.username}</p>
                    <p className="text-slate-500 text-[9px]">{u.email}</p>
                  </td>
                  <td className="p-4">
                    <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-black text-[9px] uppercase border border-blue-100 flex items-center gap-1 w-fit">
                      <Shield size={10} /> {u.role}
                    </span>
                  </td>
                  <td className="p-4 font-bold text-slate-600">
                    {departments.find(d => d.id === u.department_id)?.name || 'Global'}
                  </td>
                  <td className="p-4 text-right">
                    <button 
                      onClick={() => onToggleUser(u)}
                      className={`p-1.5 rounded-lg transition-all ${u.is_active ? 'text-green-600 hover:bg-green-50' : 'text-red-400 hover:bg-red-50'}`}
                      title={u.is_active ? 'Desativar usuário' : 'Ativar usuário'}
                    >
                      <Power size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl border shadow-sm p-6 border-l-4 border-indigo-500">
            <h3 className="font-black mb-4 flex items-center gap-2 text-sm text-indigo-600 uppercase">
              <Globe size={18} /> Webhooks Ativos
            </h3>
            <div className="space-y-3">
              {webhooks.length === 0 && <p className="text-[10px] text-slate-400 italic">Nenhum conector configurado.</p>}
              {webhooks.map(wh => (
                <div key={wh.id} className="p-3 bg-slate-50 rounded-xl border relative group hover:border-indigo-200 transition-all">
                  <p className="font-black text-xs text-slate-800">{wh.name}</p>
                  <p className="text-[8px] text-slate-400 truncate mt-1">{wh.url}</p>
                  <button 
                    onClick={() => onDeleteWebhook(wh.id)} 
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-red-500 hover:scale-110 transition-all"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
              <button className="w-full border-2 border-dashed border-slate-200 py-3 rounded-xl text-slate-400 flex items-center justify-center gap-2 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 transition-all text-[10px] font-black uppercase">
                <Plus size={16} /> Novo Endpoint
              </button>
            </div>
          </div>

          <div className="bg-slate-900 rounded-xl p-6 text-white shadow-xl">
             <h4 className="font-black text-[10px] uppercase text-slate-500 mb-2">Resumo da Governança</h4>
             <div className="grid grid-cols-2 gap-4">
                <div>
                   <p className="text-2xl font-black">{users.length}</p>
                   <p className="text-[9px] text-slate-400">Usuários</p>
                </div>
                <div>
                   <p className="text-2xl font-black text-blue-400">{departments.length}</p>
                   <p className="text-[9px] text-slate-400">Departamentos</p>
                </div>
             </div>
          </div>
        </div>
      </div>
    </main>
  );
};
