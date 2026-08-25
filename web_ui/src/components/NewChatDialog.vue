<template>
  <div v-if="show" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-panel/95 backdrop-blur-xl border border-white/10 rounded-2xl p-6 w-96 shadow-glow">
      <h3 class="font-semibold text-lg mb-4 text-gray-100">新建会话</h3>
      <label class="block text-sm font-medium text-gray-400 mb-2">选择 Agent 类型</label>
      <select v-model="selected" class="w-full bg-white/5 border border-white/10 text-gray-200 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-purple-400/60 [&>option]:bg-panel">
        <option value="general">🤖 通用 Agent (Manus)</option>
        <option value="data_analysis">📊 数据分析 Agent</option>
        <option value="quick_query">⚡ 快速查询</option>
        <option value="wechat_publish">📰 公众号发布</option>
      </select>
      <label class="block text-sm font-medium text-gray-400 mb-2">会话标题（可选）</label>
      <input v-model="title" class="w-full bg-white/5 border border-white/10 text-gray-200 rounded-lg px-3 py-2 text-sm mb-4 placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-400/60" placeholder="输入标题..." />
      <div class="flex gap-2 justify-end">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-400 hover:bg-white/5 hover:text-gray-200 rounded-lg transition-colors">取消</button>
        <button @click="confirm" class="px-4 py-2 text-sm gradient-primary hover:opacity-90 hover:shadow-glow text-white rounded-lg transition-all">创建</button>
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
