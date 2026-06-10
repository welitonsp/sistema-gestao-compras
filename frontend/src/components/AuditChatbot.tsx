import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, X, Minus, Bot, User, Loader2, Database, Sparkles } from 'lucide-react';
import { ApiError, apiClient } from '../api/client';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  query?: string;
}

export const AuditChatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Olá! Sou seu Auditor Assistente. Como posso ajudar com suas compras hoje?' }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const data = await apiClient.post<any>('/chat', { message: userMsg });
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: data.answer,
        query: data.query_used
      }]);
    } catch (err) {
      const content = err instanceof ApiError && err.status === 403
        ? err.message
        : 'Desculpe, tive um problema ao processar sua pergunta.';
      setMessages(prev => [...prev, { role: 'assistant', content }]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-8 right-8 bg-primary-600 text-white p-4 rounded-2xl shadow-2xl shadow-primary-900/40 hover:bg-primary-700 hover:scale-110 active:scale-95 transition-all z-[60] flex items-center gap-3 group"
      >
        <div className="relative">
          <MessageSquare size={24} />
          <span className="absolute -top-1 -right-1 h-3 w-3 bg-emerald-400 border-2 border-primary-600 rounded-full animate-pulse" />
        </div>
        <span className="font-bold text-sm pr-2 hidden group-hover:block animate-in slide-in-from-right duration-300">Auditor AI</span>
      </button>
    );
  }

  return (
    <div className={`fixed right-8 bottom-8 z-[60] flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl transition-all duration-300 overflow-hidden ${isMinimized ? 'h-16 w-64' : 'h-[600px] w-[400px]'}`}>
      {/* Header */}
      <header className="bg-slate-900 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-xl">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <p className="text-white text-xs font-bold uppercase tracking-widest">Meu Auditor</p>
            <div className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[9px] text-slate-400 font-bold uppercase">Online</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setIsMinimized(!isMinimized)} className="p-2 text-slate-400 hover:text-white transition-colors" aria-label={isMinimized ? "Maximizar chat" : "Minimizar chat"}>
            <Minus size={16} />
          </button>
          <button onClick={() => setIsOpen(false)} className="p-2 text-slate-400 hover:text-white transition-colors" aria-label="Fechar chat">
            <X size={16} />
          </button>
        </div>
      </header>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50 dark:bg-slate-950/50">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                <div className={`max-w-[85%] flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`p-4 rounded-2xl text-sm shadow-sm ${
                    msg.role === 'user' 
                      ? 'bg-indigo-600 text-white rounded-tr-none' 
                      : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-100 dark:border-slate-700 rounded-tl-none'
                  }`}>
                    {msg.content}
                  </div>
                  {msg.query && (
                    <details className="w-full bg-slate-900 dark:bg-slate-950 rounded-xl p-3 mt-1 overflow-hidden group/debug">
                      <summary className="flex items-center gap-2 cursor-pointer list-none">
                        <Database size={10} className="text-indigo-400" />
                        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter group-hover/debug:text-slate-400 transition-colors">Dados Técnicos</span>
                      </summary>
                      <div className="mt-2">
                        <code className="text-[10px] text-indigo-300/80 font-mono break-all whitespace-pre-wrap">
                          {msg.query}
                        </code>
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin text-indigo-600" />
                  <span className="text-xs text-slate-400 dark:text-slate-500 font-medium italic">Analisando seus dados...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input */}
          <div className="p-4 bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800">
            <form onSubmit={handleSubmit} className="relative">
              <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Pergunte sobre suas compras..."
                className="w-full pl-4 pr-12 py-3 bg-slate-100 dark:bg-slate-800 border-none rounded-xl text-sm dark:text-white focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                aria-label="Mensagem para o assistente"
              />
              <button 
                type="submit"
                disabled={!input.trim() || loading}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:grayscale transition-all"
                aria-label="Enviar mensagem"
              >
                <Send size={16} />
              </button>
            </form>
            <div className="mt-3 flex items-center justify-center gap-2 opacity-30 grayscale contrast-200">
              <Sparkles size={10} className="text-indigo-600" />
              <p className="text-[9px] font-bold text-slate-900 dark:text-slate-400 uppercase tracking-tighter">Inteligência Artificial Llama 3.3</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
