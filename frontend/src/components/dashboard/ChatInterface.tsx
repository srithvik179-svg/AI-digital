import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage } from '@/types';
import { Send, Bot, User, CornerDownLeft, Sparkles, RefreshCw } from 'lucide-react';

interface ChatInterfaceProps {
  deviceId: string;
}

const SUGGESTIONS = [
  "How is my battery health?",
  "Why is my laptop running hot?",
  "Check CPU and RAM usage bottlenecks",
  "Summarize my laptop twin state"
];

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ deviceId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'twin',
      text: "Hello! I am your AI Laptop Twin. Ask me anything about your device telemetry, thermals, processes, or battery state.",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/twin/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          query: textToSend
        })
      });

      if (!response.ok) {
        throw new Error('Network error connecting to Digital Twin agent');
      }

      const result = await response.json();
      
      const twinMsg: ChatMessage = {
        id: Math.random().toString(),
        sender: 'twin',
        text: result.response,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, twinMsg]);
    } catch (e: any) {
      const errorMsg: ChatMessage = {
        id: Math.random().toString(),
        sender: 'twin',
        text: `Error communicating with Twin: ${e.message || 'Server did not respond.'} Please make sure the backend is active.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 flex flex-col h-[520px] overflow-hidden">
      {/* Chat Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
              Digital Twin AI Consultant
              <Sparkles className="h-3.5 w-3.5 text-amber-400 fill-amber-400/20" />
            </h2>
            <p className="text-slate-400 text-xs">RAG Agent connected to telemetry store</p>
          </div>
        </div>
        <div className="flex items-center space-x-1.5 bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full text-[10px] font-semibold border border-emerald-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot-green inline-block" />
          <span>Twin Online</span>
        </div>
      </div>

      {/* Messages Box */}
      <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-slate-950/20">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} w-full`}
          >
            <div className={`flex items-start space-x-2.5 max-w-[85%] ${msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
              <div className={`p-2 rounded-xl border flex-shrink-0 ${
                msg.sender === 'user' 
                  ? 'bg-indigo-600/10 border-indigo-500/20 text-indigo-300' 
                  : 'bg-slate-900/60 border-white/5 text-slate-300'
              }`}>
                {msg.sender === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              
              <div className={`px-4 py-3 rounded-2xl border text-sm leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white border-indigo-500/30'
                  : 'bg-slate-900/40 text-slate-200 border-white/5'
              }`}>
                {msg.text}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start w-full">
            <div className="flex items-start space-x-2.5 max-w-[85%]">
              <div className="p-2 rounded-xl border flex-shrink-0 bg-slate-900/60 border-white/5 text-slate-300">
                <Bot className="h-4 w-4" />
              </div>
              <div className="px-4 py-3 rounded-2xl border text-sm leading-relaxed bg-slate-900/40 text-slate-400 border-white/5 flex items-center space-x-2">
                <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
                <span>AI twin is examining logs...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested prompts */}
      {messages.length === 1 && (
        <div className="px-5 py-2.5 border-t border-white/5 bg-slate-950/40 flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion, i) => (
            <button
              key={i}
              onClick={() => sendMessage(suggestion)}
              className="text-xs px-2.5 py-1.5 rounded-lg bg-slate-900/80 border border-white/5 text-slate-400 hover:text-white hover:bg-slate-800 hover:border-white/10 transition duration-200"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-white/5 bg-slate-900/30 flex items-center space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
          placeholder="Ask a question about the laptop twin..."
          className="flex-1 bg-slate-950/80 border border-white/5 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 transition duration-200 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition duration-200 disabled:opacity-40 flex items-center justify-center shrink-0"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
};
export default ChatInterface;
