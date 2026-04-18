'use client';

import { useEffect, useRef } from 'react';
import { DisplayMessage } from '@/lib/types';

interface ChatMessagesProps {
  messages: DisplayMessage[];
  isLoading: boolean;
}

export function ChatMessages({ messages, isLoading }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-8">
      <div className="max-w-3xl mx-auto flex flex-col gap-4 pb-44">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

/* ── Single message bubble ───────────────────────────────────────────── */
function MessageBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 msg-enter ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold ${
          isUser ? 'bg-secondary text-on-secondary' : 'bg-primary text-on-primary'
        }`}
      >
        {isUser ? (
          <span className="text-xs font-bold">U</span>
        ) : (
          <span className="material-symbols-outlined text-[16px]">smart_toy</span>
        )}
      </div>

      {/* Bubble + timestamp */}
      <div className={`flex flex-col gap-1 max-w-[72%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-secondary text-on-secondary rounded-xl rounded-br-sm'
              : 'bg-surface-container-highest text-on-surface rounded-xl rounded-bl-sm'
          }`}
        >
          {/* Message text — preserve newlines */}
          {message.text.split('\n').map((line, i, arr) => (
            <span key={i}>
              {line}
              {i < arr.length - 1 && <br />}
            </span>
          ))}

          {/* Meta footer (answer / refusal metadata) */}
          {message.meta && !isUser && (
            <div className="mt-3 pt-3 border-t border-outline-variant/20 flex flex-wrap items-center gap-2">
              {message.meta.type === 'answer' ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary rounded-full text-[11px] font-semibold">
                  <span className="material-symbols-outlined text-[12px]">check_circle</span>
                  Answer
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-error/10 text-error rounded-full text-[11px] font-semibold">
                  <span className="material-symbols-outlined text-[12px]">info</span>
                  Refusal
                </span>
              )}

              {message.meta.source_url && (
                <a
                  href={message.meta.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline text-[11px] font-medium"
                >
                  <span className="material-symbols-outlined text-[12px]">link</span>
                  Source
                </a>
              )}

              {message.meta.last_updated && (
                <span className="text-[11px] text-on-surface-variant opacity-60">
                  Updated {message.meta.last_updated}
                </span>
              )}

              {message.meta.redirect_url && (
                <a
                  href={message.meta.redirect_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-secondary hover:underline text-[11px] font-medium"
                >
                  <span className="material-symbols-outlined text-[12px]">open_in_new</span>
                  Learn more
                </a>
              )}
            </div>
          )}
        </div>

        <span className="text-[10px] text-on-surface-variant opacity-40 px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}

/* ── Typing indicator (three bouncing dots) ──────────────────────────── */
function TypingIndicator() {
  return (
    <div className="flex gap-3 msg-enter">
      <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center bg-primary text-on-primary">
        <span className="material-symbols-outlined text-[16px]">smart_toy</span>
      </div>
      <div className="bg-surface-container-highest rounded-xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1.5 items-center h-5">
          <span className="typing-dot w-2 h-2 rounded-full bg-on-surface-variant/40 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-on-surface-variant/40 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-on-surface-variant/40 inline-block" />
        </div>
      </div>
    </div>
  );
}

function formatTime(isoStr: string): string {
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}
