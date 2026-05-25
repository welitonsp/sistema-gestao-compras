import React, { useState } from 'react';
import { X, UserPlus, Shield, Mail, User } from 'lucide-react';
import { Department } from '../types/api';

interface UserCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  departments: Department[];
  onSave: (data: any) => Promise<void>;
}

export const UserCreateModal: React.FC<UserCreateModalProps> = ({ isOpen, onClose, departments, onSave }) => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'operator',
    department_id: '',
  });
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSave(formData);
      onClose();
    } catch (err) {
      alert("Erro ao criar usuário.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50">
          <h3 className="font-black text-slate-800 flex items-center gap-2">
            <UserPlus size={20} className="text-blue-600" /> NOVO USUÁRIO INSTITUCIONAL
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-8 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">Username</label>
              <input 
                required
                className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                value={formData.username}
                onChange={e => setFormData({...formData, username: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">Senha</label>
              <input 
                type="password" required
                className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                value={formData.password}
                onChange={e => setFormData({...formData, password: e.target.value})}
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">Nome Completo</label>
            <input 
              required
              className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
              value={formData.full_name}
              onChange={e => setFormData({...formData, full_name: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">E-mail Corporativo</label>
            <input 
              type="email" required
              className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">Perfil (Role)</label>
              <select 
                className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                value={formData.role}
                onChange={e => setFormData({...formData, role: e.target.value})}
              >
                <option value="operator">Operador</option>
                <option value="auditor">Auditor</option>
                <option value="manager">Gestor</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-black text-slate-500 uppercase mb-1">Departamento</label>
              <select 
                required
                className="w-full bg-slate-100 border-none rounded-lg p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                value={formData.department_id}
                onChange={e => setFormData({...formData, department_id: e.target.value})}
              >
                <option value="">Selecione...</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          </div>

          <button 
            disabled={loading}
            className="w-full bg-slate-900 text-white py-3 rounded-xl font-black text-xs uppercase tracking-widest hover:bg-blue-600 transition-all disabled:opacity-50 mt-4"
          >
            {loading ? 'PROCESSANDO...' : 'CADASTRAR USUÁRIO'}
          </button>
        </form>
      </div>
    </div>
  );
};
