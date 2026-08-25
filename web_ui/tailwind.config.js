export default {
  content: ["./index.html", "./src/**/*.{vue,ts,js}"],
  theme: {
    extend: {
      colors: {
        base: "#0B1020",   // 全局深蓝黑背景
        panel: "#131A2E",  // 面板/顶栏底色
        card: "#1A2340",   // 卡片底色
      },
      boxShadow: {
        glow: "0 0 20px rgba(139,92,246,0.35)", // 紫青霓虹光晕
      },
    },
  },
  plugins: [],
};
