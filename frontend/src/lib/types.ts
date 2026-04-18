export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  history: HistoryMessage[];
}

export interface MessageResponse {
  type: 'answer' | 'refusal';
  text: string;
  source_url: string | null;
  last_updated: string | null;
  redirect_url: string | null;
}

/** Enriched message used in the UI (includes optional response metadata) */
export interface DisplayMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  meta?: {
    type: 'answer' | 'refusal';
    source_url?: string | null;
    last_updated?: string | null;
    redirect_url?: string | null;
  };
}
