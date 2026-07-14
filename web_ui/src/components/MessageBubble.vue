<template>
  <!-- 用户消息 -->
  <div v-if="msg.role === 'user' && !msg.event_type" class="flex justify-end mb-4">
    <div class="bg-blue-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] shadow-sm">
      <p class="whitespace-pre-wrap text-sm">{{ msg.content }}</p>
    </div>
  </div>

  <!-- 步骤指示器 -->
  <div v-if="msg.event_type === 'step_start'" class="text-center my-3">
    <span class="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1">
      Step {{ (msg as any).step }}/{{ (msg as any).max_steps }}
    </span>
  </div>

  <!-- 思考 -->
  <div v-if="msg.event_type === 'thinking' && msg.content" class="mb-3">
    <details class="bg-gray-100 border border-gray-200 rounded-xl px-4 py-2.5 max-w-[85%]">
      <summary class="text-xs text-gray-500 font-medium cursor-pointer">🤔 思考过程</summary>
      <div class="text-sm text-gray-600 whitespace-pre-wrap mt-1" v-html="renderMd(msg.content)"></div>
    </details>
  </div>

  <!-- 工具执行 -->
  <div v-if="msg.event_type === 'tool_start'" class="mb-3 border-l-4 border-yellow-400 bg-white rounded-r-lg border border-l-0 border-gray-200 px-4 py-2.5 shadow-sm max-w-[85%]">
    <div class="flex items-center gap-2">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-700">{{ (msg as any).tool || msg.tool_name }}</span>
      <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full"></span>
    </div>
  </div>

  <div v-if="msg.event_type === 'tool_end'" class="mb-3 border-l-4 bg-white rounded-r-lg border border-l-0 border-gray-200 px-4 py-2.5 shadow-sm max-w-[85%]"
    :class="(msg as any).ok ? 'border-l-green-400' : 'border-l-red-400'">
    <div class="flex items-center gap-2 mb-1">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-700">{{ msg.tool_name }}</span>
      <span v-if="(msg as any).ok" class="text-green-500 text-xs">✅</span>
      <span v-else class="text-red-500 text-xs">❌</span>
    </div>
    <div v-if="msg.content" class="text-xs text-gray-500 max-h-32 overflow-y-auto whitespace-pre-wrap">{{ msg.content }}</div>
  </div>

  <!-- Agent 回复 -->
  <div v-if="msg.event_type === 'assistant'" class="mb-4">
    <div class="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%] shadow-sm">
      <div class="text-sm text-gray-800 leading-relaxed" v-html="renderMd(msg.content)"></div>
    </div>
  </div>

  <!-- 错误 -->
  <div v-if="msg.event_type === 'error'" class="mb-3">
    <div class="bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 max-w-[85%]">
      <span class="text-sm text-red-700">⚠️ {{ msg.content }}</span>
    </div>
  </div>

  <!-- 完成 -->
  <div v-if="msg.event_type === 'done'" class="text-center my-3">
    <span class="text-xs text-gray-400">— 任务结束 —</span>
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
