import { defineStore } from "pinia";
import { ref } from "vue";
import { chatApi, type ChatInfo, type MessageInfo } from "../api/chat";

export const useChatStore = defineStore("chat", () => {
  const chats = ref<ChatInfo[]>([]);
  const currentChatId = ref<number | null>(null);
  const currentMessages = ref<MessageInfo[]>([]);
  const running = ref(false);

  // WebSocket 实例（每个聊天页一个）
  const ws = ref<WebSocket | null>(null);

  async function loadChats() {
    const res = await chatApi.list();
    chats.value = res.data;
  }

  async function createChat(agentType: string, title?: string): Promise<ChatInfo> {
    const res = await chatApi.create(agentType, title);
    await loadChats();
    return res.data;
  }

  async function deleteChat(id: number) {
    await chatApi.deleteChat(id);
    await loadChats();
    if (currentChatId.value === id) {
      currentChatId.value = null;
      currentMessages.value = [];
    }
  }

  async function loadHistory(chatId: number) {
    const res = await chatApi.get(chatId);
    currentMessages.value = res.data.messages || [];
  }

  async function loadMoreMessages(beforeId: number) {
    if (!currentChatId.value) return;
    const res = await chatApi.getMessages(currentChatId.value, beforeId);
    currentMessages.value = [...res.data, ...currentMessages.value];
  }

  function connectWS(chatId: number) {
    disconnectWS();
    const token = localStorage.getItem("access_token");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/ws/${chatId}?token=${token}`;
    ws.value = new WebSocket(url);
    return ws.value;
  }

  function disconnectWS() {
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
  }

  return {
    chats, currentChatId, currentMessages, running, ws,
    loadChats, createChat, deleteChat, loadHistory, loadMoreMessages,
    connectWS, disconnectWS,
  };
});
