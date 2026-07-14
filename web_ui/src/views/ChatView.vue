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
    />
    <div v-else class="flex-1 flex items-center justify-center text-gray-400">
      <p>选择一个会话或新建一个开始</p>
    </div>
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
import ChatSidebar from "../components/ChatSidebar.vue";
import ChatWindow from "../components/ChatWindow.vue";
import NewChatDialog from "../components/NewChatDialog.vue";

const chatStore = useChatStore();
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const showNewDialog = ref(false);

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

function sendPrompt(text: string) {
  if (!chatStore.currentChatId) return;

  const ws = chatStore.connectWS(chatStore.currentChatId);
  const userMsg = { role: "user", content: text, event_type: null, created_at: new Date().toISOString(), id: Date.now(), tool_name: null };
  chatStore.currentMessages.push(userMsg as any);
  chatStore.running = true;

  ws.onopen = () => ws.send(JSON.stringify({ type: "prompt", content: text }));

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
