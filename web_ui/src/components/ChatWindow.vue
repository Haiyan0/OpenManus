<template>
  <div class="flex-1 flex flex-col h-screen">
    <!-- 顶栏 -->
    <header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
      <div>
        <h2 class="font-semibold text-gray-800">{{ title }}</h2>
        <p class="text-xs text-gray-400">Agent: {{ agentType }} · {{ running ? '运行中' : '就绪' }}</p>
      </div>
      <span v-if="running" class="flex items-center gap-1 text-sm text-yellow-600">
        <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-600 border-t-transparent rounded-full"></span>
        运行中
      </span>
      <span v-else class="text-sm text-green-600">⚡ 就绪</span>
    </header>

    <!-- 消息区 -->
    <main ref="msgContainer" class="flex-1 overflow-y-auto px-4 py-6 space-y-2">
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-5xl mb-4">🤖</span>
        <p>在下方输入你的任务</p>
      </div>
      <MessageBubble v-for="(msg, i) in messages" :key="i" :msg="msg" />
    </main>

    <!-- 输入 -->
    <footer class="bg-white border-t border-gray-200 px-4 py-3 shrink-0">
      <div class="flex gap-2 max-w-3xl mx-auto">
        <input
          v-model="input"
          @keydown.enter="send"
          :disabled="running"
          placeholder="输入你的任务，按 Enter 发送..."
          class="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />
        <button
          @click="send"
          :disabled="running || !input.trim()"
          class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
        >发送 ▶</button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import MessageBubble from "./MessageBubble.vue";
import type { MessageInfo } from "../api/chat";

const props = defineProps<{
  messages: (MessageInfo & Record<string, any>)[];
  title: string;
  agentType: string;
  running: boolean;
}>();

const emit = defineEmits<{ send: [text: string] }>();

const input = ref("");
const msgContainer = ref<HTMLElement | null>(null);

function send() {
  const text = input.value.trim();
  if (!text || props.running) return;
  emit("send", text);
  input.value = "";
}

watch(() => props.messages.length, () => {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight;
    }
  });
});
</script>
