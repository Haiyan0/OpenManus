import client from "./client";

export interface ChatInfo {
  id: number;
  user_id: number;
  title: string;
  agent_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MessageInfo {
  id: number;
  role: string;
  content: string | null;
  tool_name: string | null;
  event_type: string | null;
  created_at: string;
}

export const chatApi = {
  list: () => client.get<ChatInfo[]>("/api/chats"),
  create: (agent_type: string, title?: string) =>
    client.post<ChatInfo>("/api/chats", { agent_type, title }),
  get: (id: number) =>
    client.get<ChatInfo & { messages: MessageInfo[] }>(`/api/chats/${id}`),
  deleteChat: (id: number) => client.delete(`/api/chats/${id}`),
  getMessages: (id: number, beforeId?: number, limit = 50) =>
    client.get<MessageInfo[]>(`/api/chats/${id}/messages`, {
      params: { before_id: beforeId, limit },
    }),
};
