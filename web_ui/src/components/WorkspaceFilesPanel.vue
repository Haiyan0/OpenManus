<template>
  <div class="w-72 flex flex-col h-full bg-[#0D1428]/95 border-l border-white/10 shrink-0">
    <!-- 面板标题栏 -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
      <h3 class="font-medium text-sm text-gray-200 flex items-center gap-2">
        <span>📁</span> 生成文件
      </h3>
      <button
        @click="refresh"
        class="neon-border-btn inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg"
        :class="{ 'opacity-60': loading }"
        title="刷新文件列表"
      >
        <span class="inline-block" :class="{ 'animate-spin': loading }">🔄</span>
        刷新
      </button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="flex items-center justify-center py-8 text-gray-500">
      <span class="animate-spin inline-block w-4 h-4 border-2 border-white/20 border-t-cyan-400 rounded-full mr-2"></span>
      加载中...
    </div>

    <!-- 空态 -->
    <div v-else-if="files.length === 0" class="flex flex-col items-center justify-center py-8 text-gray-500 text-sm">
      <span class="text-2xl mb-2">📭</span>
      <p>暂无生成文件</p>
      <p class="text-xs mt-1 text-gray-600">Agent 执行完成后产物将显示在这里</p>
    </div>

    <!-- 文件列表 -->
    <div v-else class="flex-1 overflow-y-auto py-1">
      <template v-for="item in flattenedFiles" :key="item.path">
        <!-- 目录 -->
        <div
          v-if="item.is_dir"
          class="flex items-center px-4 py-1.5 text-xs text-gray-500 select-none transition-colors"
          :style="{ paddingLeft: `${item.depth * 16 + 16}px` }"
        >
          <span class="mr-1">{{ item._expanded ? '📂' : '📁' }}</span>
          <span
            class="cursor-pointer hover:text-gray-300 transition-colors"
            @click="toggleDir(item.path)"
          >{{ item.name }}</span>
        </div>
        <!-- 文件 -->
        <a
          v-else
          :href="downloadLink(item.path)"
          class="flex items-center justify-between px-4 py-2 hover:bg-white/5 text-sm transition-colors group rounded-lg mx-1"
          :style="{ paddingLeft: `${item.depth * 16 + 16}px` }"
          :title="'点击下载 ' + item.name"
        >
          <span class="flex items-center gap-2 truncate">
            <span class="text-base">{{ iconFor(item.name) }}</span>
            <span class="text-gray-300 truncate group-hover:text-cyan-300 transition-colors">{{ item.name }}</span>
          </span>
          <span class="text-xs text-gray-600 shrink-0 ml-2">{{ formatSize(item.size) }}</span>
        </a>
      </template>
    </div>

    <!-- 底部提示 -->
    <div class="px-4 py-2 border-t border-white/10 text-xs text-gray-600 shrink-0">
      {{ files.length }} 个文件/目录
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { chatApi, type WorkspaceFile } from "../api/chat";

const props = defineProps<{
  chatId: number | null;
  visible: boolean;
}>();

const files = ref<WorkspaceFile[]>([]);
const loading = ref(false);
const collapsedDirs = ref<Set<string>>(new Set());

// 展开/折叠目录
function toggleDir(path: string) {
  if (collapsedDirs.value.has(path)) {
    collapsedDirs.value.delete(path);
  } else {
    collapsedDirs.value.add(path);
  }
  // 触发依赖更新
  collapsedDirs.value = new Set(collapsedDirs.value);
}

// 扁平化文件列表（含深度信息 + 折叠处理）
const flattenedFiles = computed(() => {
  const result: (WorkspaceFile & { depth: number; _expanded: boolean })[] = [];
  const hiddenParents = new Set<string>();

  // 第一遍：找所有被折叠的目录子节点
  for (const f of files.value) {
    if (f.is_dir && collapsedDirs.value.has(f.path)) {
      const prefix = f.path + "/";
      for (const child of files.value) {
        if (child.path.startsWith(prefix)) {
          hiddenParents.add(child.path);
        }
      }
    }
  }

  for (const f of files.value) {
    if (hiddenParents.has(f.path)) continue;
    const depth = f.path.split("/").length - 1;
    result.push({
      ...f,
      depth,
      _expanded: !collapsedDirs.value.has(f.path),
    });
  }
  return result;
});

// MIME 图标映射
function iconFor(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    csv: "📊", json: "📋", md: "📝", txt: "📄", py: "🐍",
    html: "🌐", png: "🖼️", jpg: "🖼️", jpeg: "🖼️", svg: "🎨",
    pdf: "📕", xlsx: "📈", zip: "📦",
  };
  return map[ext] || "📎";
}

// 文件大小格式化
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// 生成认证下载链接（token 通过 query 参数传递，浏览器直接下载可用）
function downloadLink(filePath: string): string {
  return chatApi.workspaceDownloadUrl(props.chatId!, filePath);
}

// 加载文件列表
async function refresh() {
  if (!props.chatId) return;
  loading.value = true;
  try {
    const res = await chatApi.listWorkspaceFiles(props.chatId);
    files.value = res.data;
  } catch {
    files.value = [];
  } finally {
    loading.value = false;
  }
}

// 监听 visible → true 时自动刷新
watch(() => props.visible, (v) => {
  if (v) refresh();
});
// 切换会话时刷新
watch(() => props.chatId, (id) => {
  if (id && props.visible) refresh();
});
</script>
