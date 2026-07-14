<template>
  <aside class="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
    <div class="px-4 py-3 border-b border-gray-100">
      <button @click="$emit('new')" class="w-full bg-blue-500 hover:bg-blue-600 text-white rounded-lg py-2 text-sm font-medium">
        + 新建会话
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="chat in chats"
        :key="chat.id"
        @click="$emit('select', chat.id)"
        :class="[
          'px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50 text-sm',
          chat.id === currentId ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
        ]"
      >
        <div class="flex items-center gap-2">
          <span>{{ chat.agent_type === 'data_analysis' ? '📊' : '🤖' }}</span>
          <span class="truncate font-medium text-gray-700">{{ chat.title }}</span>
        </div>
        <div class="text-xs text-gray-400 mt-0.5">{{ chat.agent_type === 'data_analysis' ? '数据分析' : '通用' }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { ChatInfo } from "../api/chat";
defineProps<{ chats: ChatInfo[]; currentId: number | null }>();
defineEmits<{ select: [id: number]; new: [] }>();
</script>
