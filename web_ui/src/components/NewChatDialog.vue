<template>
  <div v-if="show" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl p-6 w-96 shadow-xl">
      <h3 class="font-semibold text-lg mb-4">新建会话</h3>
      <label class="block text-sm font-medium text-gray-600 mb-2">选择 Agent 类型</label>
      <select v-model="selected" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4">
        <option value="general">🤖 通用 Agent (Manus)</option>
        <option value="data_analysis">📊 数据分析 Agent</option>
        <option value="quick_query">⚡ 快速查询</option>
      </select>
      <label class="block text-sm font-medium text-gray-600 mb-2">会话标题（可选）</label>
      <input v-model="title" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4" placeholder="输入标题..." />
      <div class="flex gap-2 justify-end">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg">取消</button>
        <button @click="confirm" class="px-4 py-2 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded-lg">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{ show: boolean }>();
const emit = defineEmits<{ close: []; confirm: [agentType: string, title: string] }>();

const selected = ref("general");
const title = ref("");

function confirm() {
  emit("confirm", selected.value, title.value);
  title.value = "";
}
</script>
