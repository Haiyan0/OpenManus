import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { authApi } from "../api/auth";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<{ id: number; username: string } | null>(
    JSON.parse(localStorage.getItem("user") || "null")
  );
  const token = ref<string | null>(localStorage.getItem("access_token"));

  const isLoggedIn = computed(() => !!token.value);

  function setAuth(data: { id: number; username: string; access_token: string }) {
    user.value = { id: data.id, username: data.username };
    token.value = data.access_token;
    localStorage.setItem("user", JSON.stringify(user.value));
    localStorage.setItem("access_token", data.access_token);
  }

  function logout() {
    user.value = null;
    token.value = null;
    localStorage.removeItem("user");
    localStorage.removeItem("access_token");
  }

  return { user, token, isLoggedIn, setAuth, logout };
});
