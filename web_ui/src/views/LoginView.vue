<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="bg-white rounded-2xl shadow-md p-8 w-full max-w-md">
      <div class="text-center mb-6">
        <span class="text-4xl">🤖</span>
        <h1 class="text-xl font-semibold text-gray-800 mt-2">OpenManus Chat</h1>
        <p class="text-sm text-gray-400 mt-1">{{ isRegister ? "注册新账号" : "登录你的账号" }}</p>
      </div>

      <form @submit.prevent="submit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">用户名</label>
          <input
            v-model="username"
            type="text"
            required
            class="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="请输入用户名"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">密码</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="6"
            class="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="请输入密码"
          />
        </div>

        <p v-if="errorMsg" class="text-sm text-red-500">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
        >
          {{ loading ? "请稍后..." : (isRegister ? "注册" : "登录") }}
        </button>
      </form>

      <p class="text-center text-sm text-gray-400 mt-4">
        {{ isRegister ? "已有账号？" : "还没有账号？" }}
        <button @click="toggleMode" class="text-blue-500 hover:underline">{{ isRegister ? "去登录" : "去注册" }}</button>
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
