<template>
  <div class="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
    <!-- 装饰光球 -->
    <div class="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-purple-500/20 blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-32 -left-32 w-96 h-96 rounded-full bg-cyan-400/10 blur-3xl pointer-events-none"></div>

    <div class="relative bg-panel/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-glow p-8 w-full max-w-md">
      <div class="text-center mb-6">
        <span class="inline-flex w-14 h-14 rounded-2xl gradient-primary items-center justify-center text-2xl font-bold text-white shadow-glow mb-3">元</span>
        <h1 class="text-xl font-bold gradient-text">元梦空间 · OpenManus Chat</h1>
        <p class="text-sm text-gray-500 mt-1">{{ isRegister ? "注册新账号" : "登录你的账号" }}</p>
      </div>

      <form @submit.prevent="submit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-400 mb-1">用户名</label>
          <input
            v-model="username"
            type="text"
            required
            class="w-full bg-white/5 border border-white/10 text-gray-100 rounded-lg px-4 py-2.5 text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-400/60 focus:border-transparent transition-all"
            placeholder="请输入用户名"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-400 mb-1">密码</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="6"
            class="w-full bg-white/5 border border-white/10 text-gray-100 rounded-lg px-4 py-2.5 text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-400/60 focus:border-transparent transition-all"
            placeholder="请输入密码"
          />
        </div>

        <p v-if="errorMsg" class="text-sm text-red-400">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full gradient-primary hover:opacity-90 hover:shadow-glow disabled:opacity-40 disabled:shadow-none text-white rounded-xl py-2.5 text-sm font-medium transition-all"
        >
          {{ loading ? "请稍后..." : (isRegister ? "注册" : "登录") }}
        </button>
      </form>

      <p class="text-center text-sm text-gray-500 mt-4">
        {{ isRegister ? "已有账号？" : "还没有账号？" }}
        <button @click="toggleMode" class="text-cyan-300 hover:underline">{{ isRegister ? "去登录" : "去注册" }}</button>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { authApi } from "../api/auth";

const router = useRouter();
const authStore = useAuthStore();

const isRegister = ref(false);
const username = ref("");
const password = ref("");
const loading = ref(false);
const errorMsg = ref("");

function toggleMode() {
  isRegister.value = !isRegister.value;
  errorMsg.value = "";
}

async function submit() {
  loading.value = true;
  errorMsg.value = "";
  try {
    const fn = isRegister.value ? authApi.register : authApi.login;
    const res = await fn(username.value, password.value);
    authStore.setAuth(res.data);
    router.push("/chat");
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || "操作失败，请重试";
  } finally {
    loading.value = false;
  }
}
</script>
