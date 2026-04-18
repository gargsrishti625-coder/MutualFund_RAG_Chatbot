'use client';

import { Session } from '@/lib/types';

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
}: SidebarProps) {
  return (
    <aside className="fixed left-0 top-0 h-screen w-72 z-40 flex flex-col p-6 bg-surface-container-low">
      {/* ── Brand ──────────────────────────────────────────────────── */}
      <div className="mb-8 flex-shrink-0">
        <div className="text-lg font-bold text-primary font-headline leading-tight">
          Private Office
        </div>
        <div className="text-sm text-on-surface-variant opacity-70 mt-0.5">
          Mutual Fund Assistant
        </div>
      </div>

      {/* ── New Chat ───────────────────────────────────────────────── */}
      <button
        onClick={onNewChat}
        className="flex items-center gap-3 px-4 py-3 bg-surface-container-lowest text-primary rounded-lg shadow-sm font-semibold mb-6 hover:bg-surface-container-high transition-all active:scale-[0.98] flex-shrink-0"
      >
        <span className="material-symbols-outlined text-[20px]">add_circle</span>
        <span className="text-sm font-medium">New Chat</span>
      </button>

      {/* ── Primary nav ────────────────────────────────────────────── */}
      <nav className="flex flex-col gap-0.5 mb-4 flex-shrink-0">
        {[
          { icon: 'trending_up',            label: 'Market Insights' },
          { icon: 'account_balance_wallet', label: 'Portfolio Review' },
          { icon: 'bookmark',               label: 'Saved Sources' },
        ].map(({ icon, label }) => (
          <div
            key={label}
            title="Coming soon"
            className="flex items-center gap-3 px-4 py-3 text-on-surface-variant opacity-60 hover:opacity-100 hover:bg-surface-container-highest rounded-lg transition-all cursor-default select-none"
          >
            <span className="material-symbols-outlined text-[20px]">{icon}</span>
            <span className="text-sm font-medium">{label}</span>
          </div>
        ))}
      </nav>

      {/* ── Recent sessions ────────────────────────────────────────── */}
      {sessions.length > 0 && (
        <div className="flex flex-col min-h-0 flex-1">
          <p className="px-4 mb-2 text-[10px] uppercase tracking-widest text-on-surface-variant opacity-50 font-semibold flex-shrink-0">
            Recent
          </p>
          <div className="flex flex-col gap-0.5 overflow-y-auto flex-1">
            {sessions.map((session) => (
              <SessionItem
                key={session.session_id}
                session={session}
                isActive={session.session_id === activeSessionId}
                onSelect={() => onSelectSession(session.session_id)}
                onDelete={() => onDeleteSession(session.session_id)}
              />
            ))}
          </div>
        </div>
      )}

      {sessions.length === 0 && <div className="flex-1" />}

      {/* ── Bottom nav ─────────────────────────────────────────────── */}
      <div className="mt-auto pt-4 border-t border-outline-variant/15 flex flex-col gap-0.5 flex-shrink-0">
        {[
          { icon: 'settings', label: 'Settings' },
          { icon: 'gavel',    label: 'Compliance' },
        ].map(({ icon, label }) => (
          <div
            key={label}
            className="flex items-center gap-3 px-4 py-3 text-on-surface-variant opacity-60 hover:opacity-100 hover:bg-surface-container-highest rounded-lg transition-all cursor-default select-none"
          >
            <span className="material-symbols-outlined text-[20px]">{icon}</span>
            <span className="text-sm font-medium">{label}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}

/* ── Individual session row ──────────────────────────────────────────── */
function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`group flex items-center gap-2 px-4 py-2.5 rounded-lg cursor-pointer transition-all ${
        isActive
          ? 'bg-surface-container-high text-primary'
          : 'text-on-surface-variant hover:bg-surface-container-highest'
      }`}
    >
      <span className="material-symbols-outlined text-[16px] flex-shrink-0 opacity-70">
        chat_bubble
      </span>
      <span className="flex-1 text-sm font-medium truncate">{session.title}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        title="Delete session"
        className="opacity-0 group-hover:opacity-100 text-on-surface-variant hover:text-error transition-all flex-shrink-0"
      >
        <span className="material-symbols-outlined text-[16px]">close</span>
      </button>
    </div>
  );
}
