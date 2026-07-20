<template>
  <div class="flex h-screen">
    <ChatSidebar
      :chats="chatStore.chats"
      :currentId="chatStore.currentChatId"
      @select="switchChat"
      @new="showNewDialog = true"
    />
    <ChatWindow
      v-if="chatStore.currentChatId"
      :messages="chatStore.currentMessages"
      :title="currentTitle"
      :agentType="currentAgentType"
      :running="chatStore.running"
      @send="sendPrompt"
      @toggle-files="showFilesPanel = !showFilesPanel"
    />
    <div v-else class="flex-1 flex items-center justify-center text-gray-400">
      <p>选择一个会话或新建一个开始</p>
    </div>
    <!-- 文件下载面板 -->
    <WorkspaceFilesPanel
      :chatId="chatStore.currentChatId"
      :visible="showFilesPanel"
    />
    <NewChatDialog
      :show="showNewDialog"
      @close="showNewDialog = false"
      @confirm="createAndEnter"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "../stores/chat";
import { useAuthStore } from "../stores/auth";
import { chatApi } from "../api/chat";
import ChatSidebar from "../components/ChatSidebar.vue";
import ChatWindow from "../components/ChatWindow.vue";
import WorkspaceFilesPanel from "../components/WorkspaceFilesPanel.vue";
import NewChatDialog from "../components/NewChatDialog.vue";

const chatStore = useChatStore();
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const showNewDialog = ref(false);
const showFilesPanel = ref(false);

const currentTitle = computed(() =>
  chatStore.chats.find((c) => c.id === chatStore.currentChatId)?.title || ""
);
const currentAgentType = computed(() =>
  chatStore.chats.find((c) => c.id === chatStore.currentChatId)?.agent_type || ""
);

onMounted(async () => {
  await chatStore.loadChats();
  const id = Number(route.params.id);
  if (id) await switchChat(id);
});

async function switchChat(id: number) {
  chatStore.currentChatId = id;
  await chatStore.loadHistory(id);
  router.replace(`/chat/${id}`);
}

async function createAndEnter(agentType: string, title: string) {
  showNewDialog.value = false;
  const chat = await chatStore.createChat(agentType, title || undefined);
  router.push(`/chat/${chat.id}`);
  await switchChat(chat.id);
}

async function sendPrompt(text: string, files: File[] = []) {
  if (!chatStore.currentChatId) return;

  const chatId = chatStore.currentChatId;

  // 显示上传中提示
  if (files.length > 0) {
    chatStore.currentMessages.push({
      id: Date.now(),
      role: "system",
      content: `正在上传 ${files.length} 个文件...`,
      event_type: "step_start",
      created_at: new Date().toISOString(),
      tool_name: null,
      step: 0,
      max_steps: 0,
    } as any);
  }

  // 先上传所有文件到 workspace
  const uploadedNames: string[] = [];
  for (const file of files) {
    try {
      await chatApi.uploadFile(chatId, file);
      uploadedNames.push(file.name);
    } catch (err: any) {
      chatStore.currentMessages.push({
        id: Date.now(),
        role: "assistant",
        content: `文件上传失败: ${file.name} — ${err?.response?.data?.detail || err.message}`,
        event_type: "error",
        created_at: new Date().toISOString(),
        tool_name: null,
      } as any);
    }
  }

  const ws = chatStore.connectWS(chatId);

  // 构造用户消息显示文本（含已上传文件列表）
  const displayText = uploadedNames.length > 0
    ? `${text}\n\n📎 已上传: ${uploadedNames.join(", ")}`
    : text;

  const userMsg = {
    role: "user",
    content: displayText,
    event_type: null,
    created_at: new Date().toISOString(),
    id: Date.now(),
    tool_name: null,
  };
  chatStore.currentMessages.push(userMsg as any);
  chatStore.running = true;

  // 服务端 prompt：附加上传文件上下文，让 Agent 知道文件就在 /workspace/
  const promptWithFiles = uploadedNames.length > 0
    ? `[用户已上传以下文件到 /workspace/ 目录: ${uploadedNames.join(", ")}]\n\n${text}`
    : text;

  ws.onopen = () => ws.send(JSON.stringify({ type: "prompt", content: promptWithFiles }));

  ws.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    if (evt.type === "tool_end") {
      // 找到最近的 tool_start 替换为 tool_end
      for (let i = chatStore.currentMessages.length - 1; i >= 0; i--) {
        const m = chatStore.currentMessages[i];
        if (m.event_type === "tool_start" && m.tool_name === evt.tool) {
          chatStore.currentMessages[i] = {
            ...m,
            content: evt.result,
            ok: evt.ok,
            event_type: "tool_end",
          } as any;
          return;
        }
      }
    }
    chatStore.currentMessages.push({
      id: Date.now(),
      role: evt.type === "tool_start" || evt.type === "tool_end" ? "tool" : "assistant",
      content: evt.content || evt.message || null,
      tool_name: evt.tool || null,
      event_type: evt.type,
      created_at: new Date().toISOString(),
      step: evt.step,
      max_steps: evt.max_steps,
      ok: evt.ok,
    } as any);

    if (evt.type === "done") {
      chatStore.running = false;
      chatStore.disconnectWS();
    }
  };

  ws.onclose = () => { chatStore.running = false; };
  ws.onerror = () => {
    chatStore.running = false;
    chatStore.currentMessages.push({
      role: "assistant", content: "连接失败", event_type: "error",
      created_at: new Date().toISOString(), id: Date.now(), tool_name: null
    } as any);
  };
}
</script>
