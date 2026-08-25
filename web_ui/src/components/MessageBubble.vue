<template>
  <!-- ask_human：Agent 向用户提问 -->
  <div v-if="msg.event_type === 'ask_human'" class="mb-4">
    <div class="bg-amber-500/10 border border-amber-400/25 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%]">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-base">🤔</span>
        <span class="text-xs font-medium text-amber-300">Agent 向你提问</span>
      </div>
      <div class="text-sm text-gray-300 whitespace-pre-wrap" v-html="renderMd(msg.content || '')"></div>
    </div>
  </div>

  <!-- 用户消息（紫青渐变气泡） -->
  <div v-if="msg.role === 'user' && !msg.event_type" class="flex justify-end mb-4">
    <div class="gradient-primary text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] shadow-glow">
      <p class="whitespace-pre-wrap text-sm">{{ msg.content }}</p>
    </div>
  </div>

  <!-- 步骤指示器 -->
  <div v-if="msg.event_type === 'step_start'" class="text-center my-3">
    <span class="text-xs text-gray-500 bg-white/5 border border-white/10 rounded-full px-3 py-1">
      Step {{ (msg as any).step }}/{{ (msg as any).max_steps }}
    </span>
  </div>

  <!-- 思考 -->
  <div v-if="msg.event_type === 'thinking' && msg.content" class="mb-3">
    <details class="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 max-w-[85%]">
      <summary class="text-xs text-gray-400 font-medium cursor-pointer">🤔 思考过程</summary>
      <div class="text-sm text-gray-400 whitespace-pre-wrap mt-1" v-html="renderMd(msg.content)"></div>
    </details>
  </div>

  <!-- 工具执行中 -->
  <div v-if="msg.event_type === 'tool_start'" class="mb-3 border-l-4 border-yellow-400/70 bg-white/5 rounded-r-lg border border-l-0 border-white/10 px-4 py-2.5 max-w-[85%]">
    <div class="flex items-center gap-2">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-200">{{ (msg as any).tool || msg.tool_name }}</span>
      <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full"></span>
    </div>
  </div>

  <!-- 工具执行完成 -->
  <div v-if="msg.event_type === 'tool_end'" class="mb-3 border-l-4 bg-white/5 rounded-r-lg border border-l-0 border-white/10 px-4 py-2.5 max-w-[85%]"
    :class="(msg as any).ok ? 'border-l-cyan-400' : 'border-l-red-400'">
    <div class="flex items-center gap-2 mb-1">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-200">{{ msg.tool_name }}</span>
      <span v-if="(msg as any).ok" class="text-cyan-400 text-xs">✅</span>
      <span v-else class="text-red-400 text-xs">❌</span>
    </div>
    <div v-if="msg.content" class="text-xs text-gray-500 max-h-32 overflow-y-auto whitespace-pre-wrap">{{ msg.content }}</div>
  </div>

  <!-- Agent 回复（深灰卡片） -->
  <div v-if="msg.event_type === 'assistant'" class="mb-4">
    <div class="bg-white/5 border border-white/10 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%]">
      <div class="text-sm text-gray-200 leading-relaxed" v-html="renderMd(msg.content)"></div>
    </div>
  </div>

  <!-- 错误 -->
  <div v-if="msg.event_type === 'error'" class="mb-3">
    <div class="bg-red-500/10 border border-red-400/25 rounded-xl px-4 py-2.5 max-w-[85%]">
      <span class="text-sm text-red-400">⚠️ {{ msg.content }}</span>
    </div>
  </div>

  <!-- 完成 -->
  <div v-if="msg.event_type === 'done'" class="text-center my-3">
    <span class="text-xs text-gray-600">— 任务结束 —</span>
  </div>
</template>

<script setup lang="ts">
import type { MessageInfo } from "../api/chat";
import { marked } from "marked";

defineProps<{ msg: MessageInfo & Record<string, any> }>();

function renderMd(text: string | null): string {
  if (!text) return "";
  try { return marked.parse(text) as string; } catch { return text; }
}
</script>
