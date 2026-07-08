const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const {
  FaGlobe, FaSearch, FaChartBar, FaChartLine, FaClock, FaFileAlt,
  FaRedo, FaServer, FaDocker, FaPlug, FaKey, FaDownload, FaRocket,
  FaCheck, FaTimes, FaUser, FaLightbulb, FaArrowRight,
  FaDatabase, FaChartPie, FaBrain
} = require("react-icons/fa");

// === Color Palette (NO # prefix) ===
const C = {
  primary:    "1B3A5C",
  accent:     "2E86C1",
  orange:     "E67E22",
  white:      "FFFFFF",
  lightBg:    "F0F4F8",
  darkText:   "1A1A2E",
  grayText:   "64748B",
  lightGray:  "E2E8F0",
  cardBg:     "FFFFFF",
  success:    "27AE60",
};

// === Icon Helper ===
function renderIconSvg(IconComponent, color = "#000000", size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
}

async function iconToBase64Png(IconComponent, color, size = 256) {
  const svg = renderIconSvg(IconComponent, color, size);
  const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + pngBuffer.toString("base64");
}

function makeShadow() {
  return { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.10 };
}

// === Helpers ===
function addFooter(slide, text) {
  slide.addText(text, {
    x: 0.5, y: 5.1, w: 9, h: 0.35,
    fontSize: 9, color: C.grayText, fontFace: "Microsoft YaHei", align: "center"
  });
}

function slideNumber(slide, num, total) {
  slide.addText(`${num} / ${total}`, {
    x: 8.8, y: 5.15, w: 0.9, h: 0.3,
    fontSize: 8, color: C.grayText, fontFace: "Microsoft YaHei", align: "right"
  });
}

async function main() {
  const TOTAL = 14;
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "OpenManus Team";
  pres.title = "OpenManus — 你的 AI 工作助手";

  // Pre-render icons
  const icons = {};
  const iconMap = {
    globe: [FaGlobe, "#2E86C1"],
    search: [FaSearch, "#2E86C1"],
    chartBar: [FaChartBar, "#2E86C1"],
    chartLine: [FaChartLine, "#2E86C1"],
    clock: [FaClock, "#E67E22"],
    fileAlt: [FaFileAlt, "#2E86C1"],
    redo: [FaRedo, "#27AE60"],
    server: [FaServer, "#1B3A5C"],
    docker: [FaDocker, "#1B3A5C"],
    plug: [FaPlug, "#1B3A5C"],
    key: [FaKey, "#E67E22"],
    download: [FaDownload, "#2E86C1"],
    rocket: [FaRocket, "#27AE60"],
    check: [FaCheck, "#27AE60"],
    times: [FaTimes, "#E74C3C"],
    user: [FaUser, "#1B3A5C"],
    lightbulb: [FaLightbulb, "#E67E22"],
    arrowRight: [FaArrowRight, "#2E86C1"],
    database: [FaDatabase, "#2E86C1"],
    chartPie: [FaChartPie, "#2E86C1"],
    brain: [FaBrain, "#2E86C1"],
  };
  for (const [name, [comp, color]] of Object.entries(iconMap)) {
    icons[name] = await iconToBase64Png(comp, color);
  }
  // White variants
  icons.globeWhite = await iconToBase64Png(FaGlobe, "#FFFFFF");
  icons.searchWhite = await iconToBase64Png(FaSearch, "#FFFFFF");
  icons.chartBarWhite = await iconToBase64Png(FaChartBar, "#FFFFFF");
  icons.chartLineWhite = await iconToBase64Png(FaChartLine, "#FFFFFF");

  // ================================================================
  // SLIDE 1: 封面
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.primary };
    // Decorative shapes
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.accent } });
    // Large decorative circle (subtle)
    s.addShape(pres.shapes.OVAL, { x: 7.5, y: -1, w: 4, h: 4, fill: { color: C.accent, transparency: 85 } });
    s.addShape(pres.shapes.OVAL, { x: -1.5, y: 3.5, w: 3.5, h: 3.5, fill: { color: C.accent, transparency: 88 } });

    s.addText("OpenManus", {
      x: 0.8, y: 1.2, w: 8.4, h: 1.0,
      fontSize: 44, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center"
    });
    s.addText("— 你的 AI 工作助手 —", {
      x: 0.8, y: 2.15, w: 8.4, h: 0.6,
      fontSize: 22, fontFace: "Microsoft YaHei", color: C.accent, align: "center"
    });
    // Separator line
    s.addShape(pres.shapes.LINE, { x: 3.5, y: 2.95, w: 3, h: 0, line: { color: C.accent, width: 1.5 } });
    s.addText("让重复性工作自动化，聚焦真正重要的事", {
      x: 0.8, y: 3.15, w: 8.4, h: 0.6,
      fontSize: 16, fontFace: "Microsoft YaHei", color: "A0B4C8", align: "center"
    });
    s.addText("开源 AI 智能体框架  |  企业内部推荐", {
      x: 0.8, y: 4.6, w: 8.4, h: 0.4,
      fontSize: 11, fontFace: "Microsoft YaHei", color: "7B93A8", align: "center"
    });
    slideNumber(s, 1, TOTAL);
  }

  // ================================================================
  // SLIDE 2: 为什么需要 AI 助手
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("每天有多少时间花在重复性工作上？", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // Left side: pain points
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.4, y: 1.4, w: 4.8, h: 3.3,
      fill: { color: "FDF2F2" }, shadow: makeShadow()
    });
    s.addText("日常痛点", {
      x: 0.7, y: 1.5, w: 4.2, h: 0.4,
      fontSize: 16, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
    });
    const pains = [
      ["手动搜索竞品信息，逐页翻看", "2 小时"],
      ["复制粘贴数据到 Excel，手动做图表", "1.5 小时"],
      ["重复整理格式、排版报告", "1 小时"],
    ];
    pains.forEach((p, i) => {
      const y = 2.05 + i * 0.8;
      s.addImage({ data: icons.times, x: 0.75, y: y + 0.02, w: 0.28, h: 0.28 });
      s.addText(p[0], {
        x: 1.15, y: y, w: 2.8, h: 0.35,
        fontSize: 12, fontFace: "Microsoft YaHei", color: C.darkText
      });
      s.addText(`→ ${p[1]}`, {
        x: 3.9, y: y, w: 1.0, h: 0.35,
        fontSize: 12, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
      });
    });

    // Right side: call to action
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.5, y: 1.4, w: 4.2, h: 3.3,
      fill: { color: "F0F7FF" }, shadow: makeShadow()
    });
    s.addImage({ data: icons.lightbulb, x: 7.0, y: 1.7, w: 0.6, h: 0.6 });
    s.addText("如果这些都能交给 AI 呢？", {
      x: 5.7, y: 2.5, w: 3.8, h: 0.8,
      fontSize: 18, fontFace: "Microsoft YaHei", color: C.primary, bold: true, align: "center"
    });
    s.addText([
      { text: "把时间还给真正重要的工作", options: { fontSize: 13, color: C.accent } }
    ], { x: 5.7, y: 3.3, w: 3.8, h: 0.5, align: "center", fontFace: "Microsoft YaHei" });

    s.addText("OpenManus — 让 AI 帮你完成重复性工作", {
      x: 0.5, y: 4.9, w: 9, h: 0.4,
      fontSize: 13, fontFace: "Microsoft YaHei", color: C.accent, bold: true, align: "center"
    });
    slideNumber(s, 2, TOTAL);
  }

  // ================================================================
  // SLIDE 3: 认识 OpenManus
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("OpenManus 是什么？", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    s.addText("一个开源的 AI 智能体框架，能像人类一样操作电脑完成任务", {
      x: 0.5, y: 1.3, w: 9, h: 0.5,
      fontSize: 15, fontFace: "Microsoft YaHei", color: C.grayText, align: "center"
    });

    // 2x2 grid cards
    const cards = [
      [icons.globeWhite, "浏览器自动化", "自动浏览网页\n填写表单、点击按钮", C.accent],
      [icons.searchWhite, "网页搜索与爬取", "智能搜索\n批量抓取网页内容", "2980B9"],
      [icons.chartBarWhite, "Python 数据分析", "自动清洗数据\n统计分析", "1ABC9C"],
      [icons.chartLineWhite, "图表可视化", "一键生成专业图表\n和洞察报告", "8E44AD"],
    ];

    const cardW = 4.15, cardH = 1.7;
    const startX = 0.65, startY = 2.05;
    cards.forEach((c, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const cx = startX + col * (cardW + 0.4);
      const cy = startY + row * (cardH + 0.25);

      s.addShape(pres.shapes.RECTANGLE, {
        x: cx, y: cy, w: cardW, h: cardH,
        fill: { color: c[3] }, shadow: makeShadow()
      });
      s.addImage({ data: c[0], x: cx + 0.3, y: cy + 0.35, w: 0.55, h: 0.55 });
      s.addText(c[1], {
        x: cx + 1.0, y: cy + 0.25, w: 2.9, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei", color: C.white, bold: true
      });
      s.addText(c[2], {
        x: cx + 1.0, y: cy + 0.7, w: 2.9, h: 0.75,
        fontSize: 11, fontFace: "Microsoft YaHei", color: "D5E8F5"
      });
    });

    s.addText("一行命令，立即开始  →  python main.py", {
      x: 0.5, y: 4.9, w: 9, h: 0.4,
      fontSize: 13, fontFace: "Consolas", color: C.accent, bold: true, align: "center"
    });
    slideNumber(s, 3, TOTAL);
  }

  // ================================================================
  // SLIDE 4: 场景一 · 市场调研
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    // Top accent bar
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.orange } });
    s.addText("场景一：市场部的竞品调研", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.orange } });

    // Left: character card
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.4, w: 4.3, h: 3.6,
      fill: { color: "FFF8F0" }, shadow: makeShadow()
    });
    // Avatar circle
    s.addShape(pres.shapes.OVAL, {
      x: 1.8, y: 1.6, w: 1.6, h: 1.6,
      fill: { color: C.orange }
    });
    s.addImage({ data: icons.user, x: 2.35, y: 2.15, w: 0.5, h: 0.5 });
    s.addText("Lisa", {
      x: 0.7, y: 3.3, w: 3.8, h: 0.4,
      fontSize: 20, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, align: "center"
    });
    s.addText("市场部 · 市场分析师", {
      x: 0.7, y: 3.7, w: 3.8, h: 0.3,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText, align: "center"
    });

    // Right: task description
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.2, y: 1.4, w: 4.4, h: 3.6,
      fill: { color: C.lightBg }, shadow: makeShadow()
    });
    s.addText("📋 今日任务", {
      x: 5.5, y: 1.6, w: 3.8, h: 0.4,
      fontSize: 16, fontFace: "Microsoft YaHei", color: C.primary, bold: true
    });
    s.addText("调研 5 家竞品的最新动态、定价策略和用户评价", {
      x: 5.5, y: 2.15, w: 3.8, h: 0.8,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.darkText
    });
    s.addShape(pres.shapes.LINE, { x: 5.5, y: 3.05, w: 3.8, h: 0, line: { color: C.lightGray, width: 1 } });
    s.addText("😰 痛点", {
      x: 5.5, y: 3.2, w: 3.8, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
    });
    s.addText("手动打开每个网站，复制粘贴，至少 3 小时...", {
      x: 5.5, y: 3.55, w: 3.8, h: 0.6,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText
    });
    // Arrow
    s.addImage({ data: icons.arrowRight, x: 7.0, y: 4.2, w: 0.5, h: 0.5 });

    slideNumber(s, 4, TOTAL);
  }

  // ================================================================
  // SLIDE 5: 浏览器自动化
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("OpenManus 自动完成网页调研", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // 3 steps horizontal flow
    const steps = [
      ["下达指令", "告诉 OpenManus\n要调研哪些竞品", C.accent, icons.globeWhite],
      ["自动执行", "打开浏览器 → 搜索 →\n浏览页面 → 提取信息", C.orange, icons.searchWhite],
      ["结构化输出", "关键信息自动\n整理成报告", C.success, icons.fileAlt],
    ];
    const stepW = 2.7, stepH = 2.6, stepGap = 0.35;
    const totalW = steps.length * stepW + (steps.length - 1) * stepGap;
    const sx = (10 - totalW) / 2;
    const sy = 1.6;

    steps.forEach((st, i) => {
      const px = sx + i * (stepW + stepGap);
      // Card
      s.addShape(pres.shapes.RECTANGLE, {
        x: px, y: sy, w: stepW, h: stepH,
        fill: { color: st[2] }, shadow: makeShadow()
      });
      // Step number
      s.addShape(pres.shapes.OVAL, {
        x: px + stepW / 2 - 0.35, y: sy - 0.35, w: 0.7, h: 0.7,
        fill: { color: C.white }
      });
      s.addText(`${i + 1}`, {
        x: px + stepW / 2 - 0.35, y: sy - 0.35, w: 0.7, h: 0.7,
        fontSize: 18, fontFace: "Microsoft YaHei", color: st[2], bold: true, align: "center", valign: "middle"
      });
      // Icon
      s.addImage({ data: st[3], x: px + stepW / 2 - 0.3, y: sy + 0.55, w: 0.6, h: 0.6 });
      // Title
      s.addText(st[0], {
        x: px + 0.2, y: sy + 1.2, w: stepW - 0.4, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center"
      });
      // Desc
      s.addText(st[1], {
        x: px + 0.2, y: sy + 1.6, w: stepW - 0.4, h: 0.8,
        fontSize: 11, fontFace: "Microsoft YaHei", color: "E8F0F8", align: "center"
      });
      // Arrow between steps
      if (i < steps.length - 1) {
        s.addImage({ data: icons.arrowRight, x: px + stepW + 0.05, y: sy + 0.95, w: 0.3, h: 0.3 });
      }
    });

    addFooter(s, "基于 Playwright 浏览器自动化引擎");
    slideNumber(s, 5, TOTAL);
  }

  // ================================================================
  // SLIDE 6: 网页爬取 + 报告
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("批量抓取 + 智能汇总，一份完整的调研报告", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 26, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // Top: process flow
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.3, w: 9, h: 1.2,
      fill: { color: C.lightBg }
    });
    // 5 websites → engine → summary
    const sites = ["竞品A", "竞品B", "竞品C", "竞品D", "竞品E"];
    sites.forEach((site, i) => {
      const sx2 = 0.7 + i * 1.0;
      s.addShape(pres.shapes.RECTANGLE, {
        x: sx2, y: 1.5, w: 0.85, h: 0.55,
        fill: { color: C.white }
      });
      s.addText(site, {
        x: sx2, y: 1.5, w: 0.85, h: 0.55,
        fontSize: 9, fontFace: "Microsoft YaHei", color: C.darkText, align: "center", valign: "middle"
      });
    });
    // Arrow
    s.addText("→", { x: 5.6, y: 1.5, w: 0.3, h: 0.55, fontSize: 20, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei" });
    // Engine
    s.addShape(pres.shapes.RECTANGLE, {
      x: 6.0, y: 1.5, w: 1.3, h: 0.55,
      fill: { color: C.accent }
    });
    s.addText("Crawl4ai\n爬取引擎", {
      x: 6.0, y: 1.5, w: 1.3, h: 0.55,
      fontSize: 9, fontFace: "Microsoft YaHei", color: C.white, align: "center", valign: "middle"
    });
    s.addText("→", { x: 7.35, y: 1.5, w: 0.3, h: 0.55, fontSize: 20, color: C.accent, align: "center", valign: "middle", fontFace: "Microsoft YaHei" });
    // Summary
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.75, y: 1.5, w: 1.5, h: 0.55,
      fill: { color: C.success }
    });
    s.addText("结构化\n汇总报告", {
      x: 7.75, y: 1.5, w: 1.5, h: 0.55,
      fontSize: 9, fontFace: "Microsoft YaHei", color: C.white, align: "center", valign: "middle"
    });
    // Bottom caption
    s.addText("AI 自动完成网页内容提取和结构化整理", {
      x: 0.5, y: 2.15, w: 9, h: 0.25,
      fontSize: 10, fontFace: "Microsoft YaHei", color: C.grayText, align: "center"
    });

    // Bottom: report preview
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 2.7, w: 9, h: 2.2,
      fill: { color: C.white }, shadow: makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 2.7, w: 0.08, h: 2.2, fill: { color: C.accent } });
    s.addText("📄 调研报告摘要", {
      x: 0.85, y: 2.85, w: 8.4, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.primary, bold: true
    });
    const reportItems = [
      "竞品 A：价格策略调整为订阅制，基础版 ¥99/月，企业版 ¥499/月",
      "竞品 B：本月新增 AI 功能模块，主打智能客服和自动回复",
      "竞品 C：用户评价集中在「性价比高」和「客服响应慢」两极",
      "关键发现：3 家竞品都在布局 AI 能力，行业转型趋势明显",
    ];
    reportItems.forEach((item, i) => {
      s.addText(`• ${item}`, {
        x: 0.85, y: 3.3 + i * 0.35, w: 8.4, h: 0.3,
        fontSize: 11, fontFace: "Microsoft YaHei", color: C.darkText
      });
    });

    addFooter(s, "无需手动整理，AI 自动生成结构化报告");
    slideNumber(s, 6, TOTAL);
  }

  // ================================================================
  // SLIDE 7: 场景一小结
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("Lisa 的收获", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.orange } });

    // Left: Before vs After
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.4, w: 5.5, h: 3.4,
      fill: { color: C.lightBg }, shadow: makeShadow()
    });
    // Before
    s.addText("之前", {
      x: 0.8, y: 1.55, w: 1.0, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
    });
    s.addText("手动浏览 5 个网站 → 逐个复制粘贴\n→ Excel 整理 → 撰写报告\n≈ 3-4 小时", {
      x: 0.8, y: 1.95, w: 4.8, h: 0.9,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText
    });
    // Arrow down
    s.addText("▼", { x: 2.8, y: 2.85, w: 0.5, h: 0.3, fontSize: 16, color: C.success, align: "center", fontFace: "Microsoft YaHei" });
    // After
    s.addText("之后", {
      x: 0.8, y: 3.15, w: 1.0, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.success, bold: true
    });
    s.addText("一句话描述需求 → OpenManus 自动完成\n≈ 10 分钟审阅即可", {
      x: 0.8, y: 3.5, w: 4.8, h: 0.7,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.darkText
    });

    // Right: 3 metric cards
    const metrics = [
      ["⏱️", "95%+", "节省时间"],
      ["📋", "全覆盖", "报告完整度"],
      ["🔄", "一键重复", "可复用性"],
    ];
    metrics.forEach((m, i) => {
      const my = 1.4 + i * 1.15;
      s.addShape(pres.shapes.RECTANGLE, {
        x: 6.3, y: my, w: 3.3, h: 0.95,
        fill: { color: C.white }, shadow: makeShadow()
      });
      s.addShape(pres.shapes.RECTANGLE, { x: 6.3, y: my, w: 0.08, h: 0.95, fill: { color: C.accent } });
      s.addText(m[0], {
        x: 6.55, y: my + 0.05, w: 0.5, h: 0.4,
        fontSize: 22, fontFace: "Microsoft YaHei", align: "center"
      });
      s.addText(m[1], {
        x: 7.1, y: my + 0.08, w: 1.2, h: 0.4,
        fontSize: 22, fontFace: "Microsoft YaHei", color: C.accent, bold: true
      });
      s.addText(m[2], {
        x: 6.55, y: my + 0.5, w: 2.8, h: 0.3,
        fontSize: 11, fontFace: "Microsoft YaHei", color: C.grayText
      });
    });

    slideNumber(s, 7, TOTAL);
  }

  // ================================================================
  // SLIDE 8: 场景二 · 数据分析
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });
    s.addText("场景二：数据组的销售分析", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // Left: character card
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.4, w: 4.3, h: 3.6,
      fill: { color: "F0F7FF" }, shadow: makeShadow()
    });
    s.addShape(pres.shapes.OVAL, {
      x: 1.8, y: 1.6, w: 1.6, h: 1.6,
      fill: { color: C.accent }
    });
    s.addImage({ data: icons.user, x: 2.35, y: 2.15, w: 0.5, h: 0.5 });
    s.addText("Tom", {
      x: 0.7, y: 3.3, w: 3.8, h: 0.4,
      fontSize: 20, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, align: "center"
    });
    s.addText("数据组 · 数据分析师", {
      x: 0.7, y: 3.7, w: 3.8, h: 0.3,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText, align: "center"
    });

    // Right: task description
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.2, y: 1.4, w: 4.4, h: 3.6,
      fill: { color: C.lightBg }, shadow: makeShadow()
    });
    s.addText("📋 今日任务", {
      x: 5.5, y: 1.6, w: 3.8, h: 0.4,
      fontSize: 16, fontFace: "Microsoft YaHei", color: C.primary, bold: true
    });
    s.addText("分析本月销售数据，找出趋势，制作部门汇报图表", {
      x: 5.5, y: 2.15, w: 3.8, h: 0.8,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.darkText
    });
    s.addShape(pres.shapes.LINE, { x: 5.5, y: 3.05, w: 3.8, h: 0, line: { color: C.lightGray, width: 1 } });
    s.addText("😰 痛点", {
      x: 5.5, y: 3.2, w: 3.8, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
    });
    s.addText("Excel 公式写半天，图表调来调去总觉得不够专业...", {
      x: 5.5, y: 3.55, w: 3.8, h: 0.6,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText
    });
    s.addImage({ data: icons.arrowRight, x: 7.0, y: 4.2, w: 0.5, h: 0.5 });

    slideNumber(s, 8, TOTAL);
  }

  // ================================================================
  // SLIDE 9: 数据分析过程
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("上传数据 → AI 自动分析", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    const steps = [
      ["上传 CSV", "拖入销售数据文件\n支持 Excel / CSV 格式", C.accent, icons.database],
      ["AI 自动分析", "数据清洗 → 统计计算\n→ 趋势识别 → 异常检测", C.orange, icons.brain],
      ["输出结论", "自然语言描述的\n关键发现和洞察", C.success, icons.lightbulb],
    ];
    const stepW = 2.7, stepH = 2.6, stepGap = 0.35;
    const totalW = steps.length * stepW + (steps.length - 1) * stepGap;
    const sx = (10 - totalW) / 2;
    const sy = 1.6;

    steps.forEach((st, i) => {
      const px = sx + i * (stepW + stepGap);
      s.addShape(pres.shapes.RECTANGLE, {
        x: px, y: sy, w: stepW, h: stepH,
        fill: { color: st[2] }, shadow: makeShadow()
      });
      s.addShape(pres.shapes.OVAL, {
        x: px + stepW / 2 - 0.35, y: sy - 0.35, w: 0.7, h: 0.7,
        fill: { color: C.white }
      });
      s.addText(`${i + 1}`, {
        x: px + stepW / 2 - 0.35, y: sy - 0.35, w: 0.7, h: 0.7,
        fontSize: 18, fontFace: "Microsoft YaHei", color: st[2], bold: true, align: "center", valign: "middle"
      });
      s.addImage({ data: st[3], x: px + stepW / 2 - 0.3, y: sy + 0.55, w: 0.6, h: 0.6 });
      s.addText(st[0], {
        x: px + 0.2, y: sy + 1.2, w: stepW - 0.4, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center"
      });
      s.addText(st[1], {
        x: px + 0.2, y: sy + 1.6, w: stepW - 0.4, h: 0.8,
        fontSize: 11, fontFace: "Microsoft YaHei", color: "E8F0F8", align: "center"
      });
      if (i < steps.length - 1) {
        s.addImage({ data: icons.arrowRight, x: px + stepW + 0.05, y: sy + 0.95, w: 0.3, h: 0.3 });
      }
    });

    addFooter(s, "基于 Python 子进程安全执行，支持 pandas / numpy / matplotlib 等主流库");
    slideNumber(s, 9, TOTAL);
  }

  // ================================================================
  // SLIDE 10: 可视化报告
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("自动生成专业图表和洞察报告", {
      x: 0.5, y: 0.25, w: 9, h: 0.6,
      fontSize: 26, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 0.9, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // Chart examples - 2x2 grid
    const charts = [
      ["柱状图", "各区域销售额对比", C.accent],
      ["折线图", "月度销售趋势", C.orange],
      ["饼图", "产品类别占比", "1ABC9C"],
      ["指标卡", "总销售额 + 同比增长率", "8E44AD"],
    ];
    const cw = 2.0, ch = 0.95;
    charts.forEach((c, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const cx = 0.5 + col * (cw + 0.2);
      const cy = 1.2 + row * (ch + 0.15);
      s.addShape(pres.shapes.RECTANGLE, {
        x: cx, y: cy, w: cw, h: ch,
        fill: { color: c[2] }
      });
      s.addText(c[0], {
        x: cx, y: cy + 0.1, w: cw, h: 0.35,
        fontSize: 14, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center"
      });
      s.addText(c[1], {
        x: cx, y: cy + 0.5, w: cw, h: 0.3,
        fontSize: 9, fontFace: "Microsoft YaHei", color: "E8F0F8", align: "center"
      });
    });

    // Right: insight text area
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.0, y: 1.2, w: 4.6, h: 2.25,
      fill: { color: C.lightBg }
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 5.0, y: 1.2, w: 0.08, h: 2.25, fill: { color: C.accent } });
    s.addText("💡 AI 洞察", {
      x: 5.3, y: 1.3, w: 4.0, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.primary, bold: true
    });
    s.addText("华东区 Q2 销售额同比增长 23%，主要驱动力为 B 产品线。建议：加大华东区 B 产品的营销投入，预计下季度可再提升 15%。", {
      x: 5.3, y: 1.7, w: 4.0, h: 1.0,
      fontSize: 11, fontFace: "Microsoft YaHei", color: C.darkText
    });
    // Revenue callout
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.3, y: 2.65, w: 4.0, h: 0.65,
      fill: { color: C.accent }
    });
    s.addText([
      { text: "总销售额  ", options: { fontSize: 12, color: "C5DEF0" } },
      { text: "¥1,247 万", options: { fontSize: 22, color: C.white, bold: true } },
      { text: "    ", options: { fontSize: 10 } },
      { text: "同比 ↑18.5%", options: { fontSize: 14, color: C.white } },
    ], {
      x: 5.45, y: 2.65, w: 3.7, h: 0.65,
      fontFace: "Microsoft YaHei", valign: "middle"
    });

    // Bottom: KPI row
    const kpis = [
      ["¥1,247万", "总销售额"],
      ["↑18.5%", "同比增长"],
      ["42,891", "订单数"],
      ["4.7/5", "客户评分"],
    ];
    kpis.forEach((k, i) => {
      const kx = 0.5 + i * 2.35;
      s.addShape(pres.shapes.RECTANGLE, {
        x: kx, y: 3.7, w: 2.1, h: 0.95,
        fill: { color: C.white }, shadow: makeShadow()
      });
      s.addText(k[0], {
        x: kx, y: 3.75, w: 2.1, h: 0.5,
        fontSize: 18, fontFace: "Microsoft YaHei", color: C.accent, bold: true, align: "center"
      });
      s.addText(k[1], {
        x: kx, y: 4.25, w: 2.1, h: 0.3,
        fontSize: 10, fontFace: "Microsoft YaHei", color: C.grayText, align: "center"
      });
    });

    addFooter(s, "不仅仅是图表，更是可落地的业务建议");
    slideNumber(s, 10, TOTAL);
  }

  // ================================================================
  // SLIDE 11: 场景二小结
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("Tom 的收获", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    // Left: Before vs After
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.4, w: 5.5, h: 3.4,
      fill: { color: C.lightBg }, shadow: makeShadow()
    });
    s.addText("之前", {
      x: 0.8, y: 1.55, w: 1.0, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: "E74C3C", bold: true
    });
    s.addText("手动清洗数据 → Excel 公式\n→ 调图表样式 → 写分析结论\n≈ 3-5 小时", {
      x: 0.8, y: 1.95, w: 4.8, h: 0.9,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.grayText
    });
    s.addText("▼", { x: 2.8, y: 2.85, w: 0.5, h: 0.3, fontSize: 16, color: C.success, align: "center", fontFace: "Microsoft YaHei" });
    s.addText("之后", {
      x: 0.8, y: 3.15, w: 1.0, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: C.success, bold: true
    });
    s.addText("上传 CSV 数据 → OpenManus 自动完成\n≈ 15 分钟审阅即可", {
      x: 0.8, y: 3.5, w: 4.8, h: 0.7,
      fontSize: 12, fontFace: "Microsoft YaHei", color: C.darkText
    });

    // Right: metrics
    const metrics = [
      ["⏱️", "90%+", "节省时间"],
      ["📊", "专业标准", "图表质量"],
      ["💡", "AI 发现", "分析深度"],
    ];
    metrics.forEach((m, i) => {
      const my = 1.4 + i * 1.15;
      s.addShape(pres.shapes.RECTANGLE, {
        x: 6.3, y: my, w: 3.3, h: 0.95,
        fill: { color: C.white }, shadow: makeShadow()
      });
      s.addShape(pres.shapes.RECTANGLE, { x: 6.3, y: my, w: 0.08, h: 0.95, fill: { color: C.accent } });
      s.addText(m[0], {
        x: 6.55, y: my + 0.05, w: 0.5, h: 0.4,
        fontSize: 22, fontFace: "Microsoft YaHei", align: "center"
      });
      s.addText(m[1], {
        x: 7.1, y: my + 0.08, w: 1.2, h: 0.4,
        fontSize: 22, fontFace: "Microsoft YaHei", color: C.accent, bold: true
      });
      s.addText(m[2], {
        x: 6.55, y: my + 0.5, w: 2.8, h: 0.3,
        fontSize: 11, fontFace: "Microsoft YaHei", color: C.grayText
      });
    });

    slideNumber(s, 11, TOTAL);
  }

  // ================================================================
  // SLIDE 12: 部署方案
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("如何部署 OpenManus？", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    const cards = [
      {
        icon: icons.server, title: "本地部署", color: C.accent,
        items: ["Python 3.12 环境", "配置 LLM API Key", "pip install 一键安装"],
        tag: "个人 / 小团队"
      },
      {
        icon: icons.docker, title: "Docker 沙箱", color: C.primary,
        items: ["Docker 容器隔离运行", "资源限制 + 安全保障", "适合多用户并发"],
        tag: "生产环境"
      },
      {
        icon: icons.plug, title: "MCP 扩展", color: C.orange,
        items: ["连接企业内部工具", "自定义数据源接入", "灵活扩展能力"],
        tag: "深度定制"
      },
    ];
    const cardW = 2.8, cardH = 3.2;
    const startX = 0.5, cardGap = 0.4;
    cards.forEach((card, i) => {
      const cx = startX + i * (cardW + cardGap);
      const cy = 1.4;
      s.addShape(pres.shapes.RECTANGLE, {
        x: cx, y: cy, w: cardW, h: cardH,
        fill: { color: C.white }, shadow: makeShadow()
      });
      // Top accent
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cardW, h: 0.08, fill: { color: card.color } });
      // Icon circle
      s.addShape(pres.shapes.OVAL, {
        x: cx + cardW / 2 - 0.45, y: cy + 0.3, w: 0.9, h: 0.9,
        fill: { color: card.color }
      });
      s.addImage({ data: card.icon, x: cx + cardW / 2 - 0.22, y: cy + 0.52, w: 0.44, h: 0.44 });
      // Title
      s.addText(card.title, {
        x: cx + 0.15, y: cy + 1.35, w: cardW - 0.3, h: 0.4,
        fontSize: 18, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, align: "center"
      });
      // Items
      card.items.forEach((item, j) => {
        s.addText(`• ${item}`, {
          x: cx + 0.3, y: cy + 1.85 + j * 0.3, w: cardW - 0.6, h: 0.25,
          fontSize: 10, fontFace: "Microsoft YaHei", color: C.grayText
        });
      });
      // Tag
      s.addShape(pres.shapes.RECTANGLE, {
        x: cx + 0.4, y: cy + 2.85, w: cardW - 0.8, h: 0.3,
        fill: { color: card.color }
      });
      s.addText(card.tag, {
        x: cx + 0.4, y: cy + 2.85, w: cardW - 0.8, h: 0.3,
        fontSize: 9, fontFace: "Microsoft YaHei", color: C.white, align: "center", valign: "middle"
      });
    });

    addFooter(s, "推荐从本地部署开始，5 分钟即可体验");
    slideNumber(s, 12, TOTAL);
  }

  // ================================================================
  // SLIDE 13: 如何开始
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addText("三步开启你的 AI 助手之旅", {
      x: 0.5, y: 0.3, w: 9, h: 0.7,
      fontSize: 28, fontFace: "Microsoft YaHei", color: C.darkText, bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.2, h: 0.04, fill: { color: C.accent } });

    const steps = [
      {
        num: "1", title: "申请 LLM API Key",
        items: ["OpenAI / Azure / 国产模型均可", "填入 config.toml 配置文件"],
        icon: icons.key, color: C.orange
      },
      {
        num: "2", title: "安装 OpenManus",
        items: ["git clone + pip install", "或使用 uv 包管理器（更快）"],
        icon: icons.download, color: C.accent
      },
      {
        num: "3", title: "输入你的第一个任务",
        items: ["python main.py", "在终端输入任务描述", "坐等 AI 为你工作 ☕"],
        icon: icons.rocket, color: C.success
      },
    ];

    const stepH = 1.1;
    steps.forEach((st, i) => {
      const sy = 1.45 + i * 1.25;
      s.addShape(pres.shapes.RECTANGLE, {
        x: 0.7, y: sy, w: 8.6, h: stepH,
        fill: { color: C.white }, shadow: makeShadow()
      });
      // Left accent
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: sy, w: 0.08, h: stepH, fill: { color: st.color } });
      // Number circle
      s.addShape(pres.shapes.OVAL, {
        x: 1.1, y: sy + 0.25, w: 0.6, h: 0.6,
        fill: { color: st.color }
      });
      s.addText(st.num, {
        x: 1.1, y: sy + 0.25, w: 0.6, h: 0.6,
        fontSize: 20, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center", valign: "middle"
      });
      // Icon
      s.addImage({ data: st.icon, x: 1.9, y: sy + 0.3, w: 0.45, h: 0.45 });
      // Title
      s.addText(st.title, {
        x: 2.5, y: sy + 0.1, w: 3.0, h: 0.4,
        fontSize: 16, fontFace: "Microsoft YaHei", color: C.darkText, bold: true
      });
      // Items
      st.items.forEach((item, j) => {
        s.addText(`• ${item}`, {
          x: 2.5, y: sy + 0.5 + j * 0.28, w: 5.0, h: 0.25,
          fontSize: 11, fontFace: "Microsoft YaHei", color: C.grayText
        });
      });
      // Vertical connector
      if (i < steps.length - 1) {
        s.addShape(pres.shapes.LINE, {
          x: 1.4, y: sy + stepH, w: 0, h: 0.15,
          line: { color: C.lightGray, width: 1.5 }
        });
      }
    });

    slideNumber(s, 13, TOTAL);
  }

  // ================================================================
  // SLIDE 14: 结尾
  // ================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.primary };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.accent } });
    // Decorative circles
    s.addShape(pres.shapes.OVAL, { x: 7.5, y: -1, w: 4, h: 4, fill: { color: C.accent, transparency: 85 } });
    s.addShape(pres.shapes.OVAL, { x: -1.5, y: 3.5, w: 3.5, h: 3.5, fill: { color: C.accent, transparency: 88 } });

    s.addText("让 AI 成为每个人的工作伙伴", {
      x: 0.8, y: 1.0, w: 8.4, h: 0.8,
      fontSize: 30, fontFace: "Microsoft YaHei", color: C.white, bold: true, align: "center"
    });
    s.addShape(pres.shapes.LINE, { x: 3.0, y: 1.9, w: 4, h: 0, line: { color: C.accent, width: 1.5 } });
    s.addText("从今天开始，把重复性工作交给 OpenManus", {
      x: 0.8, y: 2.1, w: 8.4, h: 0.6,
      fontSize: 18, fontFace: "Microsoft YaHei", color: "A0B4C8", align: "center"
    });

    // Info section
    s.addShape(pres.shapes.RECTANGLE, {
      x: 1.5, y: 3.0, w: 7, h: 1.7,
      fill: { color: C.accent, transparency: 30 }
    });
    const infoLines = [
      ["GitHub：", "github.com/FoundationAgents/OpenManus"],
      ["开源协议：", "MIT"],
      ["内部联系人：", "请填入你的 IT 管理员联系方式"],
    ];
    infoLines.forEach((line, i) => {
      s.addText([
        { text: line[0], options: { bold: true, color: C.white, fontSize: 12 } },
        { text: line[1], options: { color: "C5DEF0", fontSize: 12 } },
      ], {
        x: 1.8, y: 3.15 + i * 0.35, w: 6.4, h: 0.3,
        fontFace: "Microsoft YaHei"
      });
    });
    s.addText("欢迎提问 🙋", {
      x: 1.5, y: 4.6, w: 7, h: 0.4,
      fontSize: 16, fontFace: "Microsoft YaHei", color: C.orange, bold: true, align: "center"
    });

    slideNumber(s, 14, TOTAL);
  }

  // === Save ===
  const outPath = "C:\\Code\\OpenManus\\docs\\presentations\\OpenManus_企业内推.pptx";
  await pres.writeFile({ fileName: outPath });
  console.log(`✅ PPT saved to: ${outPath}`);
}

main().catch(err => { console.error("❌ Error:", err); process.exit(1); });
