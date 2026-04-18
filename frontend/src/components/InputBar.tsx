'use client';

import { useRef, useEffect, KeyboardEvent } from 'react';

interface InputBarProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  isLoading: boolean;
}

export function InputBar({ value, onChange, onSend, isLoading }: InputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  return (
    /* Gradient overlay anchored left-72 to match the sidebar width */
    <div className="fixed bottom-0 left-72 right-0 p-6 bg-gradient-to-t from-surface via-surface/95 to-transparent pointer-events-none z-30">
      <div className="max-w-3xl mx-auto pointer-events-auto">

        {/* Input surface */}
        <div className="relative bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant/10 p-2 flex items-end gap-2 focus-within:shadow-2xl transition-all duration-300">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a factual question about mutual funds…"
            rows={1}
            className="flex-1 bg-transparent resize-none border-none outline-none focus:ring-0 px-4 py-3 text-on-surface placeholder:text-on-surface-variant/50 text-sm leading-relaxed disabled:opacity-50"
            style={{ maxHeight: '140px', fontFamily: "'Public Sans', sans-serif" }}
          />

          <button
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            className="bg-primary text-on-primary w-12 h-12 rounded-lg flex items-center justify-center hover:bg-on-primary-container transition-colors shadow-sm active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            aria-label="Send"
          >
            {isLoading ? (
              <span className="material-symbols-outlined text-[20px] animate-spin">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined text-[20px]">send</span>
            )}
          </button>
        </div>

        {/* Sub-label */}
        <div className="mt-2 text-center">
          <p className="text-[10px] uppercase tracking-[0.2em] text-on-surface-variant/40 font-semibold">
            Encrypted &amp; Verified Factual Response Engine
          </p>
        </div>
      </div>
    </div>
  );
}
