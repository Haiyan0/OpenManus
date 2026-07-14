import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("../views/LoginView.vue"), meta: { guest: true } },
    { path: "/chat/:id?", component: () => import("../views/ChatView.vue"), meta: { auth: true } },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem("access_token");
  if (to.meta.auth && !token) return next("/login");
  if (to.meta.guest && token) return next("/chat");
  next();
});

export default router;
