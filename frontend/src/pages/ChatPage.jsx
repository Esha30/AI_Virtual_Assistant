import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import ReactMarkdown from 'react-markdown';
import {
  Send, Mic, MicOff, Plus, LogOut, User, Trash2, Bot,
  Calendar, CheckCircle, X, MessageSquare,
  PencilLine, Copy, RefreshCw
} from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';


const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [completingTaskIds, setCompletingTaskIds] = useState(new Set());
  const [toast, setToast] = useState(null); // { message, icon }
  const [confirmDialog, setConfirmDialog] = useState(null); // { title, message, onConfirm }
  const { user, logout, authenticatedFetch } = useAuth();

  const bottomRef = useRef(null);
  const recognitionRef = useRef(null);
  const textareaRef = useRef(null);

  // ── Data Fetching ────────────────────────────────────────────────────────────

  const fetchUnifiedData = useCallback(async (sessionId = null) => {
    if (!authenticatedFetch) return;
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const sid = sessionId || activeSessionId;
      const url = sid 
        ? `${baseUrl}/unified-context?session_id=${sid}`
        : `${baseUrl}/unified-context`;
        
      const res = await authenticatedFetch(url);
      const data = await res.json();
      
      if (data) {
        console.log('DEBUG: Unified data received:', data);
        if (data.engines) {
          console.log('DEBUG: Engine Status:', data.engines);
        }
        if (data.sessions) setSessions(data.sessions);
        if (data.tasks) {
          console.log('DEBUG: Setting tasks:', data.tasks);
          setTasks(data.tasks);
        }
        if (data.reminders) {
          console.log('DEBUG: Setting reminders:', data.reminders);
          setReminders(data.reminders);
        }
        if (data.history && (sid || !activeSessionId)) {
          const loaded = [];
          data.history.forEach(doc => {
            if (doc.user_message) loaded.push({ role: 'user', text: doc.user_message, id: doc._id });
            if (doc.bot_response) loaded.push({ role: 'bot', text: doc.bot_response, id: doc._id });
          });
          setMessages(loaded);
        }
      }
    } catch (e) { console.error('Unified fetch error', e); }
  }, [authenticatedFetch, activeSessionId]);

  useEffect(() => {
    if (authenticatedFetch) {
      fetchUnifiedData();
    }
  }, [authenticatedFetch, fetchUnifiedData]);

  useEffect(() => {
    if (activeSessionId) {
      fetchUnifiedData(activeSessionId);
    }
  }, [activeSessionId, fetchUnifiedData]);

  // ── Auto-expire reminders ─────────────────────────────────────────────────────

  useEffect(() => {
    if (!authenticatedFetch || reminders.length === 0) return;

    /* 
    const checkExpired = async () => {
      const now = new Date();
      const expired = reminders.filter(r => {
        if (!r.scheduled_time) return false;
        return new Date(r.scheduled_time) <= now;
      });

      for (const r of expired) {
        try {
          await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/reminders/${r._id}`, { method: 'DELETE' });
        } catch (e) { console.error('Auto-expire error', e); }
      }

      if (expired.length > 0) {
        fetchUnifiedData();
        showToast(`⏰ Reminder expired: "${expired[0].task}"`, 'amber');
      }
    };

    checkExpired();
    const interval = setInterval(checkExpired, 60000);
    return () => clearInterval(interval);
    */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reminders, authenticatedFetch]);

  // ── Speech Recognition ───────────────────────────────────────────────────────

  useEffect(() => {
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';
      recognition.onresult = (event) => setInput(event.results[0][0].transcript);
      recognition.onend = () => setIsRecording(false);
      recognitionRef.current = recognition;
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // ── Actions ──────────────────────────────────────────────────────────────────

  const showToast = (message, type = 'emerald') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const toggleRecording = () => {
    if (isRecording) {
      recognitionRef.current?.stop();
    } else {
      if (recognitionRef.current) {
        recognitionRef.current.start();
        setIsRecording(true);
      } else {
        showToast('Speech Recognition not supported in this browser.', 'amber');
      }
    }
  };

  const startNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setInput('');
  };

  const switchSession = (sessionId) => {
    if (sessionId === activeSessionId) return;
    setMessages([]);
    setActiveSessionId(sessionId);
  };

  const deleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s._id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (e) { console.error('Delete session error', e); }
  };

  const startRenameSession = (e, session) => {
    e.stopPropagation();
    setEditingSessionId(session._id);
    setEditingTitle(session.title);
  };

  const saveRenameSession = async (sessionId) => {
    if (!editingTitle.trim()) return;
    try {
      await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editingTitle.trim() })
      });
      setSessions(prev => prev.map(s => s._id === sessionId ? { ...s, title: editingTitle.trim() } : s));
    } catch (e) { console.error('Rename session error', e); }
    setEditingSessionId(null);
  };

  const clearAllSessions = async () => {
    setConfirmDialog({
      title: 'Clear All History',
      message: 'This will permanently delete ALL conversations and data streams. This action cannot be undone.',
      onConfirm: async () => {
        try {
          await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/sessions`, { method: 'DELETE' });
          setSessions([]);
          setActiveSessionId(null);
          setMessages([]);
          showToast('History cleared successfully', 'emerald');
        } catch (e) { 
          console.error('Clear sessions error', e);
          showToast('Failed to clear history', 'amber');
        }
      }
    });
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const regenerateResponse = async () => {
    if (messages.length < 2 || isTyping) return;
    
    // Find last user message
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (!lastUserMsg) return;

    // Get the interaction ID from the last bot response
    const lastBotMsg = messages[messages.length - 1];
    
    // Check if it was a bot response (failed or otherwise)
    if (lastBotMsg.role === 'bot') {
      const interactionId = lastBotMsg.id;
      if (interactionId) {
        try {
          await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/history/${interactionId}`, {
            method: 'DELETE'
          });
        } catch (e) {
          console.error('Failed to cleanup old interaction', e);
        }
      }
      setMessages(prev => prev.slice(0, -1));
    }

    // Also remove the user message from the UI (since handleSend will re-add it)
    setMessages(prev => prev.slice(0, -1));

    setInput(lastUserMsg.text);
    // We'll call handleSend manually with the text
    setTimeout(() => handleSend(), 10);
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || isTyping) return;

    const userText = input;
    setInput('');
    const userMsg = { role: 'user', text: userText };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      const res = await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          local_time: new Date().toISOString(),
          session_id: activeSessionId
        })
      });
      const data = await res.json();
      const botResponse = data.response;
      const returnedSessionId = data.session_id;

      if (botResponse) {
        setMessages(prev => [...prev, { role: 'bot', text: botResponse, id: data.interaction_id }]);
        speakText(botResponse);
      }

      // If this was a new session, activate it and refresh session list
      if (!activeSessionId && returnedSessionId) {
        setActiveSessionId(returnedSessionId);
        await fetchUnifiedData(returnedSessionId);
      } else {
        await fetchUnifiedData(returnedSessionId || activeSessionId); // Refresh everything with correct ID
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'bot',
        text: 'My neural link is currently fluctuating. Please ensure the backend is operational and try again in a moment.'
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const speakText = (text) => {
    if ('speechSynthesis' in window && text) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(
        text.replace(/\[PLAY_VIDEO:[^\]]+\]/g, '')
      );
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    }
  };

  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  };

  const handleToggleTask = async (taskId, completed) => {
    if (!completed) {
      // Marking as DONE: show strikethrough briefly, then auto-delete
      setCompletingTaskIds(prev => new Set([...prev, taskId]));
      try {
        await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/tasks/${taskId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed: true })
        });
        setTimeout(async () => {
          try {
            await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/tasks/${taskId}`, { method: 'DELETE' });
            setTasks(prev => prev.filter(t => t._id !== taskId));
            setCompletingTaskIds(prev => { const s = new Set(prev); s.delete(taskId); return s; });
          } catch (e) { console.error('Auto-delete completed task error', e); }
        }, 1500);
      } catch (e) {
        console.error('Toggle task error', e);
        setCompletingTaskIds(prev => { const s = new Set(prev); s.delete(taskId); return s; });
      }
    } else {
      // Un-marking (already completed but not yet deleted) — just uncheck
      try {
        await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/tasks/${taskId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed: false })
        });
        fetchUnifiedData();
      } catch (e) { console.error('Toggle task error', e); }
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/tasks/${taskId}`, { method: 'DELETE' });
      setTasks(prev => prev.filter(t => t._id !== taskId));
    } catch (e) { console.error('Delete task error', e); }
  };

  const handleDeleteReminder = async (reminderId) => {
    try {
      await authenticatedFetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/reminders/${reminderId}`, { method: 'DELETE' });
      setReminders(prev => prev.filter(r => r._id !== reminderId));
    } catch (e) { console.error('Delete reminder error', e); }
  };

  // ── Render Content ───────────────────────────────────────────────────────────

  const renderContent = (text = '', id) => {
    if (!text) return null;

    const videoRegex = /\[PLAY_VIDEO:(https:\/\/[^\]]+)\]/;
    const match = text.match(videoRegex);

    if (match) {
      const url = match[1];
      const videoToken = match[0];
      const parts = text.split(videoToken);
      return (
        <div className="flex flex-col gap-8 my-4">
          {parts[0] && <div className="markdown-body"><ReactMarkdown>{parts[0]}</ReactMarkdown></div>}
          <div className="w-full max-w-2xl aspect-video rounded-3xl overflow-hidden glass-card premium-glow transition-all duration-700 hover:scale-[1.02]">
            <iframe width="100%" height="100%" src={url} title="Aura" frameBorder="0" allowFullScreen className="opacity-90 hover:opacity-100 transition-opacity"></iframe>
          </div>
          {parts[1] && <div className="markdown-body"><ReactMarkdown>{parts[1]}</ReactMarkdown></div>}
        </div>
      );
    }

    return (
      <div className="markdown-body relative group">
        <ReactMarkdown
          components={{
            code({ inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              return !inline && match ? (
                <div className="rounded-2xl overflow-hidden my-6 border border-white/10 shadow-2xl bg-[#050505]">
                  <div className="px-5 py-2.5 bg-white/5 flex items-center justify-between border-b border-white/5">
                    <span className="text-[10px] uppercase tracking-widest font-bold text-[#525252]">{match[1]}</span>
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-500/30"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/30"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-green-500/30"></div>
                    </div>
                  </div>
                  <pre className="p-6 overflow-x-auto text-[14px]">
                    <code className={`${className} !text-[#ececec]`} {...props}>{children}</code>
                  </pre>
                </div>
              ) : (
                <code className="bg-emerald-500/10 text-emerald-300 px-1.5 py-0.5 rounded text-[0.9em] font-mono" {...props}>{children}</code>
              );
            }
          }}
        >
          {text}
        </ReactMarkdown>
        <div className="absolute top-1 right-1 flex items-center gap-1">
          {copiedId === id ? (
            <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-[10px] font-bold animate-in fade-in slide-in-from-right-1 duration-200">
              <CheckCircle size={10} /> Copied
            </span>
          ) : (
            <button 
              onClick={() => copyToClipboard(text, id)}
              className="p-2 opacity-0 group-hover:opacity-100 transition-opacity text-slate-500 hover:text-emerald-400"
              title="Copy to clipboard"
            >
              <Copy size={13} />
            </button>
          )}
        </div>
      </div>
    );
  };

  // ── Session Grouping ──────────────────────────────────────────────────────────

  const groupSessions = (sessions) => {
    const groups = {
      Today: [],
      Yesterday: [],
      'Last 7 Days': [],
      'Previous': []
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);

    sessions.forEach(s => {
      const date = new Date(s.last_updated);
      if (date >= today) groups.Today.push(s);
      else if (date >= yesterday) groups.Yesterday.push(s);
      else if (date >= lastWeek) groups['Last 7 Days'].push(s);
      else groups.Previous.push(s);
    });

    return Object.entries(groups).filter(([, items]) => items.length > 0);
  };

  // ── UI ───────────────────────────────────────────────────────────────────────

  const activeSession = sessions.find(s => s._id === activeSessionId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0a0a0b] text-[#f8fafc] font-inter">

      {/* ── SIDEBAR ──────────────────────────────────────────────────────────── */}
      <aside className="w-[280px] flex-shrink-0 flex flex-col bg-[#0f0f12] border-r border-white/[0.06]">

        {/* Logo */}
        <div className="p-5 pt-7">
          <div className="flex items-center gap-2.5 mb-6 px-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#10a37f] to-[#ab68ff] flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
            <h1 className="text-lg font-bold tracking-tight text-white">Aura <span className="text-emerald-400">Pro</span></h1>
          </div>

          {/* New Chat Button */}
          <button
            onClick={startNewSession}
            className="w-full flex items-center gap-3 py-3 px-4 rounded-xl bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08] hover:border-emerald-500/30 transition-all duration-200 text-sm font-semibold"
          >
            <Plus size={16} className="text-emerald-400" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Sessions List — scrollable */}
        <div className="flex-1 overflow-y-auto px-3 pb-2 custom-scrollbar min-h-0">
          <div className="flex items-center justify-between px-2 mb-4">
            <p className="text-[10px] font-black uppercase tracking-widest text-[#3f3f46]">Conversations</p>
            <button 
              onClick={clearAllSessions}
              className="p-1 rounded hover:bg-red-500/10 text-[#3f3f46] hover:text-red-400 transition-colors"
              title="Clear all"
            >
              <Trash2 size={12} />
            </button>
          </div>

          <div className="space-y-6">
            <AnimatePresence>
              {groupSessions(sessions).map(([group, items]) => (
                <div key={group} className="space-y-1">
                  <h3 className="session-group-header">{group}</h3>
                  {items.map((session) => (
                    <motion.div
                      key={session._id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      className={`group relative flex items-center rounded-xl cursor-pointer transition-all duration-300 ${
                        activeSessionId === session._id
                          ? 'session-item-active'
                          : 'hover:bg-white/[0.04]'
                      }`}
                      onClick={() => switchSession(session._id)}
                    >
                      {editingSessionId === session._id ? (
                        <input
                          autoFocus
                          className="flex-1 px-3 py-2.5 bg-transparent text-sm text-white outline-none"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onBlur={() => saveRenameSession(session._id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveRenameSession(session._id);
                            if (e.key === 'Escape') setEditingSessionId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className={`flex-1 px-3 py-2.5 text-sm truncate transition-colors ${
                          activeSessionId === session._id ? 'text-white font-medium' : 'text-slate-400 group-hover:text-slate-200'
                        }`}>
                          {session.title}
                        </span>
                      )}
                      <div className="flex items-center gap-0.5 pr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => startRenameSession(e, session)}
                          className="p-1.5 rounded-lg hover:bg-white/10 text-slate-500 hover:text-white transition-colors"
                          title="Rename"
                        >
                          <PencilLine size={12} />
                        </button>
                        <button
                          onClick={(e) => deleteSession(e, session._id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/15 text-slate-500 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ))}
              {sessions.length === 0 && (
                <div className="px-3 py-8 text-center bg-white/[0.02] rounded-2xl border border-dashed border-white/5 mx-2">
                  <MessageSquare size={24} className="mx-auto text-[#2a2a2e] mb-3" />
                  <p className="text-[11px] text-slate-600 font-medium">No active streams</p>
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ── INTELLIGENCE PANEL — always visible, pinned above user footer ── */}
        <div className="shrink-0 border-t border-white/[0.05] px-3 py-3 space-y-3">
          {/* Header */}
          <div className="flex items-center justify-between px-1">
            <p className="text-[10px] font-black uppercase tracking-widest text-[#3f3f46]">Intelligence</p>
            <div className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider">
              <span className="text-emerald-500">{tasks.length} tasks</span>
              <span className="text-slate-700">·</span>
              <span className="text-amber-500">{reminders.length} reminders</span>
            </div>
          </div>

          {/* Tasks section */}
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-400 uppercase tracking-widest px-1 mb-1.5">
              <CheckCircle size={10} /> Tasks
            </div>
            {tasks.length === 0 ? (
              <p className="text-[10px] text-slate-700 px-2 py-1 italic">Ask Aura to add a task</p>
            ) : (
              <div className="space-y-1 max-h-[90px] overflow-y-auto custom-scrollbar pr-0.5">
                {Array.isArray(tasks) && tasks.map((t) => {
                  const isCompleting = completingTaskIds.has(t._id);
                  const isDone = t.completed || isCompleting;
                  return (
                    <div
                      key={t._id || Math.random()}
                      className={`group flex items-center justify-between px-2 py-1.5 rounded-lg border transition-all duration-300 ${
                        isDone
                          ? 'bg-emerald-500/5 border-emerald-500/20 opacity-60'
                          : 'bg-white/[0.02] border-white/[0.04] hover:border-emerald-500/20'
                      }`}
                    >
                      <div className="flex items-center gap-2 overflow-hidden">
                        <button
                          onClick={() => handleToggleTask(t._id, t.completed)}
                          disabled={isCompleting}
                          className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-all shrink-0 ${
                            isDone
                              ? 'bg-emerald-500 border-emerald-500 text-white scale-110'
                              : 'border-white/10 hover:border-emerald-500/50'
                          }`}
                        >
                          {isDone && <CheckCircle size={8} strokeWidth={3} />}
                        </button>
                        <span className={`text-[10px] truncate transition-all duration-300 ${
                          isDone ? 'text-slate-600 line-through' : 'text-slate-300'
                        }`}>
                          {t.task || 'Unnamed Task'}
                        </span>
                      </div>
                      {!isCompleting && (
                        <button
                          onClick={() => handleDeleteTask(t._id)}
                          className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-500/10 text-slate-600 hover:text-red-400 rounded transition-all shrink-0"
                        >
                          <X size={9} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Reminders section */}
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-500 uppercase tracking-widest px-1 mb-1.5">
              <Calendar size={10} /> Reminders
            </div>
            {reminders.length === 0 ? (
              <p className="text-[10px] text-slate-700 px-2 py-1 italic">Ask Aura to set a reminder</p>
            ) : (
              <div className="space-y-1 max-h-[90px] overflow-y-auto custom-scrollbar pr-0.5">
                {Array.isArray(reminders) && reminders.map((r) => (
                  <div key={r._id || Math.random()} className="group flex items-center justify-between px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-amber-500/20 transition-all">
                    <div className="flex items-center gap-2 overflow-hidden min-w-0">
                      <div className="w-1 h-1 rounded-full bg-amber-500 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[10px] text-slate-300 truncate">{r.task || 'Unnamed Reminder'}</p>
                        {r.time && <p className="text-[9px] text-amber-500/60 truncate">{r.time}</p>}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteReminder(r._id)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-500/10 text-slate-600 hover:text-red-400 rounded transition-all shrink-0"
                    >
                      <X size={9} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* User Footer */}
        <div className="p-4 border-t border-white/[0.05]">
          <div
            className="flex items-center justify-between group cursor-pointer px-3 py-2.5 rounded-xl hover:bg-white/[0.04] transition-all"
            onClick={logout}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-500/20 to-purple-500/20 flex items-center justify-center border border-white/10">
                <User size={15} className="text-slate-300" />
              </div>
              <div>
                <p className="text-[13px] font-semibold leading-tight group-hover:text-emerald-300 transition-colors truncate max-w-[130px]">
                  {user?.email?.split('@')[0] || 'User'}
                </p>
                <p className="text-[9px] text-slate-600 uppercase tracking-widest">Secure Session</p>
              </div>
            </div>
            <LogOut size={14} className="text-slate-600 group-hover:text-red-400 transition-colors" />
          </div>
        </div>
      </aside>

      {/* ── MAIN AREA ────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col relative bg-[#0a0a0b] overflow-hidden">

        {/* Ambient glows */}
        <div className="absolute inset-0 z-0 pointer-events-none opacity-40">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-emerald-500/8 blur-[120px] rounded-full"></div>
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/8 blur-[120px] rounded-full"></div>
        </div>

        {/* Header */}
        <header className="h-16 flex items-center justify-between px-8 border-b border-white/[0.04] z-10 bg-[#0a0a0b]/70 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-base tracking-tight text-white">
              {activeSession ? activeSession.title : 'Aura AI Assistant'}
            </span>
            {activeSession && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400 font-bold uppercase tracking-widest">Active</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <AnimatePresence>
              {isSpeaking && (
                <motion.button
                  key="stop-aura-button"
                  initial={{ opacity: 0, scale: 0.9, x: 10 }}
                  animate={{ opacity: 1, scale: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.9, x: 10 }}
                  onClick={stopSpeaking}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all font-bold text-[10px] uppercase tracking-widest"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
                  Stop Aura
                </motion.button>
              )}
            </AnimatePresence>
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
              <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Online</span>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <section className="flex-1 overflow-y-auto px-6 scroll-smooth custom-scrollbar relative z-10">
          <div className="max-w-[760px] mx-auto w-full pt-10 pb-48">
            {messages.length === 0 ? (
              /* ── WELCOME SCREEN ── */
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-8"
              >
                <div className="w-20 h-20 rounded-[2.5rem] bg-gradient-to-br from-emerald-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-emerald-500/25">
                  <Bot size={40} strokeWidth={1.2} className="text-white" />
                </div>
                <div>
                  <h2 className="font-bold text-4xl tracking-tight mb-3 text-white">How can I help?</h2>
                  <p className="text-slate-500 text-lg max-w-md leading-relaxed">
                    Ask me anything — I can manage tasks, set reminders, search the web, play videos, or just converse.
                  </p>
                </div>

                {/* Suggestion chips */}
                <div className="grid grid-cols-2 gap-3 w-full max-w-lg">
                  {[
                    { icon: '📋', text: 'Add to my task list: Review project specs' },
                    { icon: '⏰', text: 'Remind me to call the client at 3pm' },
                    { icon: '🎵', text: 'Play some lo-fi study music' },
                    { icon: '💡', text: 'What are the latest trends in AI?' },
                  ].map((s, i) => (
                    <button
                      key={i}
                      onClick={() => { setInput(s.text); textareaRef.current?.focus(); }}
                      className="flex items-start gap-2.5 p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.07] hover:border-white/[0.1] transition-all duration-200 text-left"
                    >
                      <span className="text-xl shrink-0">{s.icon}</span>
                      <span className="text-sm text-slate-400 leading-snug">{s.text}</span>
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              /* ── MESSAGES ── */
              <div className="space-y-8">
                {messages.map((msg, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start items-start gap-4'}`}
                  >
                    {/* Bot Avatar */}
                    {msg.role === 'bot' && (
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500/80 to-purple-600/80 flex items-center justify-center shrink-0 mt-1 shadow-lg">
                        <Bot size={16} className="text-white" />
                      </div>
                    )}

                    {/* Message Bubble */}
                    <div className={
                      msg.role === 'user'
                        ? 'bg-[#1c1c20] border border-white/[0.06] px-5 py-3.5 rounded-[1.75rem] max-w-[80%] text-[15px] text-white leading-relaxed shadow-lg'
                        : 'flex-1 text-[15px] text-slate-200 leading-relaxed'
                    }>
                      {renderContent(msg.text, idx)}
                    </div>
                  </motion.div>
                ))}

                {/* Typing Indicator */}
                {isTyping && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-start gap-4"
                  >
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500/80 to-purple-600/80 flex items-center justify-center shrink-0">
                      <Bot size={16} className="text-white" />
                    </div>
                    <div className="flex gap-1.5 items-center h-8 px-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-400/60 animate-bounce"></span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400/80 animate-bounce [animation-delay:0.15s]"></span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:0.3s]"></span>
                    </div>
                  </motion.div>
                )}

                {/* Regenerate Button Logic */}
                {!isTyping && messages.length > 0 && messages[messages.length - 1].role === 'bot' && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-center mt-6"
                  >
                    <button 
                      onClick={regenerateResponse}
                      className="regenerate-btn group"
                    >
                      <RefreshCw size={12} className="group-hover:rotate-180 transition-transform duration-500" />
                      Regenerate Response
                    </button>
                  </motion.div>
                )}

                <div ref={bottomRef} className="h-4" />
              </div>
            )}
          </div>
        </section>

        {/* ── INPUT BAR ── */}
        <div className="absolute bottom-0 left-0 right-0 p-6 z-20 bg-gradient-to-t from-[#0a0a0b] via-[#0a0a0b]/95 to-transparent pt-20 pointer-events-none">
          <div className="max-w-[760px] mx-auto pointer-events-auto">
            <form
              className="bg-[#131316]/90 backdrop-blur-2xl border border-white/[0.09] rounded-2xl shadow-2xl focus-within:border-emerald-500/40 transition-all duration-300"
              onSubmit={handleSend}
            >
              <div className="flex items-end gap-3 px-4 py-3">
                <textarea
                  ref={textareaRef}
                  className="flex-1 bg-transparent border-none outline-none text-[15px] text-white py-1.5 placeholder:text-slate-600 resize-none max-h-[200px] custom-scrollbar leading-relaxed"
                  placeholder="Message Aura..."
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <div className="flex items-center gap-2 pb-0.5">
                  <button
                    type="button"
                    onClick={toggleRecording}
                    className={`p-2 rounded-xl transition-all duration-300 ${
                      isRecording
                        ? 'bg-red-500/20 text-red-400'
                        : 'text-slate-500 hover:text-white hover:bg-white/[0.06]'
                    }`}
                  >
                    {isRecording ? <MicOff size={18} className="animate-pulse" /> : <Mic size={18} />}
                  </button>
                  <button
                    type="submit"
                    disabled={!input.trim() || isTyping}
                    className={`p-2 rounded-xl transition-all duration-300 ${
                      input.trim() && !isTyping
                        ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-lg shadow-emerald-500/25 hover:scale-105 active:scale-95'
                        : 'bg-white/[0.03] text-slate-700'
                    }`}
                  >
                    <Send size={18} strokeWidth={2.5} />
                  </button>
                </div>
              </div>
            </form>
            <p className="text-center mt-3 text-[10px] text-slate-700 tracking-widest uppercase">
              Aura may make mistakes · Review important information
            </p>
          </div>
        </div>

      </main>

      {/* ── TOAST NOTIFICATION ── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            key="toast"
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className={`fixed bottom-24 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-2xl backdrop-blur-xl border shadow-2xl text-sm font-medium ${
              toast.type === 'amber'
                ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            }`}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="text-white/30 hover:text-white/70 transition-colors ml-1"
            >
              <X size={12} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── CONFIRMATION MODAL ── */}
      <AnimatePresence>
        {confirmDialog && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
              onClick={() => setConfirmDialog(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative w-full max-w-sm bg-[#131316] border border-white/10 rounded-3xl p-8 shadow-2xl overflow-hidden"
            >
              {/* Background accent */}
              <div className="absolute -top-24 -right-24 w-48 h-48 bg-red-500/10 blur-3xl rounded-full pointer-events-none" />
              
              <div className="relative z-10">
                <div className="w-12 h-12 rounded-2xl bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/20">
                  <Trash2 className="text-red-400" size={24} />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">{confirmDialog.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed mb-8">
                  {confirmDialog.message}
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setConfirmDialog(null)}
                    className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-sm font-semibold transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      confirmDialog.onConfirm();
                      setConfirmDialog(null);
                    }}
                    className="flex-1 py-3 rounded-xl bg-red-500 hover:bg-red-400 text-white text-sm font-bold transition-all shadow-lg shadow-red-500/20"
                  >
                    Proceed
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default ChatPage;
