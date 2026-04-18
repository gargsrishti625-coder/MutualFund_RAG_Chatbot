'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Session, DisplayMessage } from '@/lib/types';
import { api } from '@/lib/api';
import { Sidebar } from '@/components/Sidebar';
import { WelcomeScreen } from '@/components/WelcomeScreen';
import { ChatMessages } from '@/components/ChatMessages';
import { InputBar } from '@/components/InputBar';

export default function Home() {
  const [sessions, setSessions]               = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages]               = useState<DisplayMessage[]>([]);
  const [isLoading, setIsLoading]             = useState(false);
  const [inputValue, setInputValue]           = useState('');

  // Track first-message status without re-renders
  const isFirstMessageRef = useRef(true);

  /* ── Load all sessions on mount ─────────────────────────────────── */
  useEffect(() => {
    api.listSessions()
      .then((data) => setSessions(data))
      .catch(console.error);
  }, []);

  /* ── Keep isFirstMessageRef in sync ─────────────────────────────── */
  useEffect(() => {
    isFirstMessageRef.current = messages.length === 0;
  }, [messages.length]);

  /* ── New chat — clear active state ──────────────────────────────── */
  const handleNewChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setInputValue('');
  }, []);

  /* ── Switch to an existing session ──────────────────────────────── */
  const handleSelectSession = useCallback(async (id: string) => {
    if (id === activeSessionId) return;
    setActiveSessionId(id);
    try {
      const detail = await api.getSession(id);
      setMessages(
        detail.history.map((msg, i) => ({
          id:        `${id}-hist-${i}`,
          role:      msg.role as 'user' | 'assistant',
          text:      msg.text,
          timestamp: msg.timestamp,
        }))
      );
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  }, [activeSessionId]);

  /* ── Delete a session ───────────────────────────────────────────── */
  const handleDeleteSession = useCallback(async (id: string) => {
    try {
      await api.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (activeSessionId === id) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }, [activeSessionId]);

  /* ── Send a message (or kick off with an example question) ──────── */
  const handleSend = useCallback(async (overrideQuery?: string) => {
    const query = (overrideQuery ?? inputValue).trim();
    if (!query || isLoading) return;

    setInputValue('');

    // Auto-create session when none is active
    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const newSession = await api.createSession('New conversation');
        sessionId = newSession.session_id;
        setActiveSessionId(sessionId);
        setSessions((prev) => [newSession, ...prev]);
      } catch (err) {
        console.error('Failed to create session:', err);
        return;
      }
    }

    const wasFirstMessage = isFirstMessageRef.current;

    // Optimistic user bubble
    const userMsg: DisplayMessage = {
      id:        `msg-${Date.now()}-u`,
      role:      'user',
      text:      query,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await api.sendMessage(sessionId, query);

      const assistantMsg: DisplayMessage = {
        id:        `msg-${Date.now()}-a`,
        role:      'assistant',
        text:      response.text,
        timestamp: new Date().toISOString(),
        meta: {
          type:         response.type,
          source_url:   response.source_url,
          last_updated: response.last_updated,
          redirect_url: response.redirect_url,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Auto-title the session after the first exchange
      if (wasFirstMessage) {
        const title = query.slice(0, 60) + (query.length > 60 ? '…' : '');
        try {
          await api.renameSession(sessionId, title);
          setSessions((prev) =>
            prev.map((s) =>
              s.session_id === sessionId ? { ...s, title } : s
            )
          );
        } catch { /* non-critical */ }
      }

      // Update message count in sidebar
      setSessions((prev) =>
        prev.map((s) =>
          s.session_id === sessionId
            ? { ...s, message_count: s.message_count + 2 }
            : s
        )
      );
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id:        `msg-${Date.now()}-err`,
          role:      'assistant',
          text:      '⚠ Something went wrong. Please check that the API server is running and try again.',
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [activeSessionId, inputValue, isLoading]);

  const hasMessages = messages.length > 0;

  return (
    <div className="flex min-h-screen">

      {/* ── Left sidebar ─────────────────────────────────────────── */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* ── Main canvas ─────────────────────────────────────────── */}
      <main className="flex-1 ml-72 flex flex-col min-h-screen">

        {/* Sticky glassmorphism top bar */}
        <header className="flex justify-between items-center w-full px-8 h-16 sticky top-0 z-50 bg-surface/80 backdrop-blur-xl border-b border-outline-variant/10">
          <div className="text-xl font-extrabold text-on-surface tracking-tighter font-headline">
            The Precision Ledger
          </div>
          <div className="font-headline font-bold text-sm tracking-tight text-primary">
            Facts-only. No investment advice.
          </div>
        </header>

        {/* Chat / welcome area */}
        <div className="flex-1 flex flex-col">
          {hasMessages ? (
            <ChatMessages messages={messages} isLoading={isLoading} />
          ) : (
            <WelcomeScreen onExampleClick={(q) => handleSend(q)} />
          )}
        </div>

        {/* Footer — visible below messages / cards */}
        <footer className="w-full flex flex-col items-center gap-3 py-6 pb-44 border-t border-outline-variant/10 mt-auto">
          <div className="flex gap-8">
            {['Privacy Policy', 'Terms of Service', 'Regulatory Disclosures'].map((link) => (
              <a
                key={link}
                href="#"
                className="text-[11px] uppercase tracking-widest text-on-surface-variant opacity-60 hover:opacity-100 hover:text-primary transition-all"
              >
                {link}
              </a>
            ))}
          </div>
          <p className="text-[11px] uppercase tracking-widest text-on-surface-variant opacity-40">
            © 2024 The Precision Ledger. For informational purposes only.
          </p>
        </footer>
      </main>

      {/* Fixed input bar — overlays main content, clears the sidebar */}
      <InputBar
        value={inputValue}
        onChange={setInputValue}
        onSend={() => handleSend()}
        isLoading={isLoading}
      />
    </div>
  );
}
