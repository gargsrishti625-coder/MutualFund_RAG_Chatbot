import type { Session, SessionDetail, MessageResponse } from './types';

// All requests go to /api/* which next.config.js proxies to http://localhost:8000/*
const BASE = '/api';

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (res.status === 204) return null as unknown as T;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? data.error ?? 'Request failed');
  return data as T;
}

export const api = {
  health:        () => req<{ status: string; version: string }>('/health'),
  listSessions:  () => req<Session[]>('/sessions'),
  createSession: (title: string) =>
    req<Session>('/sessions', { method: 'POST', body: JSON.stringify({ title }) }),
  getSession:    (id: string) => req<SessionDetail>(`/sessions/${id}`),
  deleteSession: (id: string) => req<null>(`/sessions/${id}`, { method: 'DELETE' }),
  renameSession: (id: string, title: string) =>
    req<Session>(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  sendMessage:   (sessionId: string, query: string) =>
    req<MessageResponse>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
};
