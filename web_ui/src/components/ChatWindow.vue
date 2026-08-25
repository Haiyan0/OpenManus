<template>
  <div class="flex-1 flex flex-col h-screen">
    <!-- 顶栏（毛玻璃） -->
    <header class="bg-panel/80 backdrop-blur-xl border-b border-white/10 px-6 py-3 flex items-center justify-between shrink-0">
      <div>
        <h2 class="font-semibold text-gray-100">{{ title }}</h2>
        <p class="text-xs text-gray-500">Agent: {{ agentType }} · {{ running ? '运行中' : '就绪' }}</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="$emit('toggleFiles')"
          class="text-sm px-3 py-1.5 rounded-lg neon-border-btn"
          title="打开/关闭文件面板"
        >📁 文件</button>
        <span
          v-if="running"
          class="flex items-center gap-1.5 text-sm text-yellow-300"
        >
          <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-300 border-t-transparent rounded-full"></span>
          运行中
        </span>
        <span v-else class="flex items-center gap-1.5 text-sm text-cyan-300">
          <span class="animate-pulse-glow inline-block w-2 h-2 rounded-full bg-cyan-400 shadow-glow"></span>
          就绪
        </span>
      </div>
    </header>

    <!-- 消息区 -->
    <main ref="msgContainer" class="flex-1 overflow-y-auto px-4 py-6 space-y-2">
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-500">
        <span class="text-5xl mb-4">🤖</span>
        <p class="text-gray-400">在下方输入你的任务</p>
        <p class="text-xs mt-2 text-gray-600">支持上传 CSV/Excel 等数据文件，Agent 会自动读取分析</p>
      </div>
      <MessageBubble v-for="(msg, i) in messages" :key="i" :msg="msg" />
    </main>

    <!-- 输入区（毛玻璃） -->
    <footer class="bg-panel/80 backdrop-blur-xl border-t border-white/10 px-4 py-3 shrink-0">
      <!-- ask_human 回复区 -->
      <div v-if="waitingForHuman" class="max-w-3xl mx-auto mb-2 p-3 bg-amber-500/10 border border-amber-400/30 rounded-xl">
        <p class="text-xs text-amber-300 mb-2">🤔 Agent 正在等待你的回复...</p>
        <div class="flex gap-2">
          <input
            v-model="humanInput"
            @keydown.enter="replyHuman"
            placeholder="在此输入回复..."
            class="flex-1 bg-white/5 border border-amber-400/30 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-amber-400/60"
          />
          <button
            @click="replyHuman"
            :disabled="!humanInput.trim()"
            class="bg-amber-500 hover:bg-amber-400 disabled:opacity-40 text-white rounded-lg px-4 py-2 text-sm font-medium transition-all"
          >回复</button>
        </div>
      </div>

      <!-- 已上传文件 chips -->
      <div v-if="uploadedFiles.length > 0" class="flex flex-wrap gap-2 mb-2 max-w-3xl mx-auto">
        <div
          v-for="(f, i) in uploadedFiles"
          :key="i"
          class="inline-flex items-center gap-1.5 bg-cyan-400/10 border border-cyan-400/30 rounded-lg px-3 py-1 text-xs text-cyan-300"
        >
          <span>{{ fileIcon(f.name) }}</span>
          <span class="max-w-[120px] truncate" :title="f.name">{{ f.name }}</span>
          <button
            @click="removeFile(i)"
            class="text-cyan-400/70 hover:text-red-400 transition-colors ml-0.5"
            title="移除"
          >✕</button>
        </div>
      </div>

      <div class="flex gap-2 max-w-3xl mx-auto">
        <!-- 上传按钮 -->
        <label
          class="flex items-center justify-center w-10 h-10 rounded-xl border border-white/15 hover:bg-white/5 hover:border-purple-400/50 cursor-pointer transition-all shrink-0"
          :class="{ 'opacity-50 pointer-events-none': running }"
          title="上传数据文件"
        >
          <span class="text-lg">📎</span>
          <input
            ref="fileInput"
            type="file"
            accept=".csv,.xlsx,.xls,.json,.txt,.tsv"
            class="hidden"
            @change="onFileSelected"
            :disabled="running"
          />
        </label>

        <input
          v-model="input"
          @keydown.enter="send"
          :disabled="running"
          placeholder="输入你的任务，按 Enter 发送..."
          class="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-400/60 focus:border-transparent disabled:opacity-50 transition-all"
        />
        <button
          @click="send"
          :disabled="running || !input.trim()"
          class="gradient-primary hover:opacity-90 hover:shadow-glow disabled:opacity-40 disabled:shadow-none text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-all"
        >发送 ▶</button>
      </div>
      <p class="text-xs text-gray-600 text-center mt-1.5 max-w-3xl mx-auto">
        支持上传 CSV、Excel、JSON、TXT 文件。文件仅在当前会话有效，关闭页面后自动清除。
      </p>
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
  waitingForHuman?: boolean;
}>();

const emit = defineEmits<{
  send: [text: string, files: File[]];
  toggleFiles: [];
  sendHumanResponse: [text: string];
}>();

const input = ref("");
const humanInput = ref("");
const msgContainer = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

// 已上传文件列表（保留 File 对象用于后续上传）
const uploadedFiles = ref<File[]>([]);

function fileIcon(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = { csv: "📊", xlsx: "📈", xls: "📈", json: "📋", txt: "📄", tsv: "📊" };
  return map[ext] || "📎";
}

function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  // 限制文件大小 50MB
  if (file.size > 50 * 1024 * 1024) {
    alert("文件大小不能超过 50MB");
    target.value = "";
    return;
  }

  uploadedFiles.value.push(file);
  target.value = ""; // 清除 input，允许重复上传同名文件
}

function removeFile(index: number) {
  uploadedFiles.value.splice(index, 1);
}

function send() {
  const text = input.value.trim();
  if (!text || props.running) return;
  emit("send", text, [...uploadedFiles.value]);
  input.value = "";
  uploadedFiles.value = []; // 发送后清空文件列表
}

function replyHuman() {
  const text = humanInput.value.trim();
  if (!text) return;
  emit("sendHumanResponse", text);
  humanInput.value = "";
}

watch(() => props.messages.length, () => {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight;
    }
  });
});
</script>
