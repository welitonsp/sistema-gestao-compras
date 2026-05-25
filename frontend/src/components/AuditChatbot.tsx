import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, X, Minus, Bot, User, Loader2, Database } from 'lucide-react';
import { apiClient } from '../api/client';

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
    { role: 'assistant', content: 'Olá! Sou seu Assistente de Auditoria. Como posso ajudar com os dados de compras hoje?' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await apiClient.post<any>('/chat', { message: userMessage });
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: response.answer,
        query: response.query_used
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Desculpe, ocorreu um erro ao processar sua pergunta. Verifique sua conexão.' 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 text-white rounded-full shadow-2xl flex items-center justify-center hover:bg-blue-700 transition-all hover:scale-110 z-50 focus:ring-4 focus:ring-blue-300"
        aria-label="Abrir chat de auditoria"
      >
        <MessageSquare size={28} />
      </button>
    );
  }

  return (
    <div className={`fixed bottom-6 right-6 w-80 md:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 transition-all ${isMinimized ? 'h-14' : 'h-[500px]'}`}>
      {/* Header */}
      <div className="p-4 bg-slate-900 text-white rounded-t-2xl flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-blue-400" />
          <span className="font-bold text-sm tracking-tight">AUDITOR VIRTUAL</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setIsMinimized(!isMinimized)} className="p-1 hover:bg-white/10 rounded">
            <Minus size={16} />
          </button>
          <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-white/10 rounded">
            <X size={16} />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-3 rounded-2xl text-xs shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-none' 
                    : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
                }`}>
                  <div className="flex items-center gap-1 mb-1 opacity-70 font-bold uppercase text-[9px]">
                    {msg.role === 'user' ? <User size={10} /> : <Bot size={10} />}
                    {msg.role === 'user' ? 'Você' : 'IA Auditor'}
                  </div>
                  <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  
                  {msg.query && (
                    <details className="mt-2 pt-2 border-t border-slate-100">
                      <summary className="cursor-pointer text-[9px] text-blue-500 font-bold hover:underline flex items-center gap-1">
                        <Database size={10} /> VER SQL EXECUTADO
                      </summary>
                      <pre className="mt-2 p-2 bg-slate-900 text-green-400 rounded text-[9px] overflow-x-auto">
                        {msg.query}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white p-3 rounded-2xl border border-slate-100 rounded-tl-none flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin text-blue-600" />
                  <span className="text-[10px] text-slate-500 font-medium">Analisando base de dados...</span>
                </div>
              </div>
            )}
          </div>

          {/* Footer Input */}
          <form onSubmit={handleSendMessage} className="p-4 border-t border-slate-100 bg-white rounded-b-2xl">
            <div className="relative">
              <input 
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ex: Qual o total gasto em Maio?"
                className="w-full pl-4 pr-10 py-2.5 bg-slate-100 border-none rounded-full text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                disabled={isLoading}
              />
              <button 
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-1 top-1/2 -translate-y-1/2 p-2 text-blue-600 hover:text-blue-700 disabled:opacity-30"
              >
                <Send size={18} />
              </button>
            </div>
            <p className="text-[9px] text-slate-400 text-center mt-2 uppercase font-bold tracking-tighter">Powered by Gemini 1.5 Flash</p>
          </form>
        </>
      )}
    </div>
  );
};
