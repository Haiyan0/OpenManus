<template>
  <aside class="w-64 bg-panel/80 backdrop-blur-xl border-r border-white/10 flex flex-col shrink-0">
    <!-- 品牌区 -->
    <div class="px-4 pt-4 pb-3 border-b border-white/10 shrink-0">
      <div class="flex items-center gap-2.5 mb-3">
        <span class="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center text-sm font-bold text-white shadow-glow">元</span>
        <div class="min-w-0">
          <h1 class="text-sm font-semibold text-gray-100 leading-tight">元梦空间</h1>
          <p class="text-[10px] text-gray-500 tracking-[0.2em]">OPENMANUS AI</p>
        </div>
      </div>
      <button
        @click="$emit('new')"
        class="w-full gradient-primary hover:opacity-90 hover:shadow-glow text-white rounded-xl py-2 text-sm font-medium transition-all"
      >
        + 新建会话
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="flex-1 overflow-y-auto py-2 px-2">
      <div
        v-for="chat in chats"
        :key="chat.id"
        @click="$emit('select', chat.id)"
        :class="[
          'px-3 py-2.5 cursor-pointer text-sm group relative transition-all rounded-xl mb-1 border',
          chat.id === currentId
            ? 'bg-white/10 border-white/15'
            : 'hover:bg-white/5 border-transparent',
        ]"
      >
        <div class="flex items-center gap-2">
          <span class="text-base">{{ chat.agent_type === 'data_analysis' ? '📊' : '🤖' }}</span>
          <span
            class="truncate font-medium flex-1"
            :class="chat.id === currentId ? 'text-gray-100' : 'text-gray-300'"
          >{{ chat.title }}</span>
          <button
            @click.stop="$emit('delete', chat.id)"
            class="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all text-xs px-1"
            title="删除会话"
          >🗑</button>
        </div>
        <div
          class="text-xs mt-0.5"
          :class="chat.id === currentId ? 'text-cyan-300/80' : 'text-gray-500'"
        >{{ chat.agent_type === 'data_analysis' ? '数据分析' : '通用' }}</div>
        <!-- 选中态渐变光条 -->
        <div
          v-if="chat.id === currentId"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-full gradient-primary"
        ></div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { ChatInfo } from "../api/chat";
defineProps<{ chats: ChatInfo[]; currentId: number | null }>();
defineEmits<{ select: [id: number]; new: []; delete: [id: number] }>();
</script>
