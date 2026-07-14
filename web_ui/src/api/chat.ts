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

export interface WorkspaceFile {
  name: string;
  path: string;
  size: number;
  is_dir: boolean;
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
  /** 列出 workspace 中的生成文件 */
  listWorkspaceFiles: (chatId: number) =>
    client.get<WorkspaceFile[]>(`/api/chats/${chatId}/workspace/files`),
  /** 构造下载链接（可直接用于浏览器 <a> 标签） */
  workspaceDownloadUrl: (chatId: number, filePath: string) => {
    const token = localStorage.getItem("access_token");
    // 通过 query 参数带 token，让浏览器直接触发下载
    return `/api/chats/${chatId}/workspace/download?path=${encodeURIComponent(filePath)}&token=${token}`;
  },
};
