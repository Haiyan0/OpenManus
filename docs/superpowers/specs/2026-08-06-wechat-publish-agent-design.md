# 微信公众号发布 Agent 集成设计文档

> 状态：已审批 | 日期：2026-08-06 | 作者：bao (AI)

## 1. 背景与目标

### 1.1 现状

`baoyu-post-to-wechat` skill（全局缓存目录 `~/.claude/plugins/cache/baoyu-skills/.../scripts/`）提供发布微信公众号文章的能力，核心是 `wechat-api.ts`（API 方式，快、可自动化）。该能力当前仅存在于 AI 编码助手（Claude Code 等）的 skill 体系中，OpenManus 用户无法在 Web 会话中直接使用。

### 1.2 目标

将 post-to-wechat 的 API 发布能力集成为 OpenManus 的**独立 Agent 类型** `wechat_publish`：

- Web 前端「新建会话」对话框可选「公众号发布」Agent
- Agent 通过工具调用发布文章到公众号**草稿箱**
- 职责灵活：既可发布用户提供的现成 markdown/文本，也可用 python_execute 等工具生成内容后发布（全流程）
- 脚本与 bun 依赖**复制进仓库自包含**，不依赖全局 skill 缓存路径

### 1.3 非目标

- 不做浏览器方式（wechat-article.ts）集成——仅 API 方式
- 不做工具形式集成（已确认仅独立 Agent）
- 不直接发布正式文章——仅草稿箱（`draft/add`），用户到公众号后台确认发布
- 不做 remote-api（SSH 隧道）方式——本机 IP 在白名单内
- 不改动 wechat-api.ts 脚本本身（除非集成需要最小改动）

---

## 2. 架构设计

### 2.1 组件结构

```
app/agent/wechat_publish.py            → WechatPublish Agent（ToolCallAgent 子类）
app/prompt/wechat_publish.py           → 系统提示词 + 下一步提示词
app/tool/wechat_publish/               → 工具模块（自包含）
  ├── __init__.py
  ├── wechat_publish.py                → WechatPublishTool（BaseTool 子类，调 bun 脚本）
  └── scripts/                         → 从 baoyu-skills 复制的脚本（含 package.json、node_modules 由 bun install 生成）
       ├── wechat-api.ts               → 核心：API 发布
       ├── md-to-wechat.ts             → markdown → 微信 HTML
       ├── wechat-http.ts / wechat-image-loader.ts / wechat-image-processor.ts
       │   └── 其他 wechat-api.ts 直接依赖的模块
       └── package.json                → bun 依赖清单（复制后 bun install）
```

### 2.2 脚本复制策略

从全局 skill 目录复制**必要子集**（wechat-api.ts 及其 import 链），不复制浏览器相关脚本（wechat-article.ts、wechat-browser.ts、cdp.ts、clipboard/paste 等）。

复制方式：一次性手动复制（由实施计划列出确切文件清单），脚本 import 均为相对路径（`./wechat-http.ts` 等），复制后无需改 import。

bun 依赖：在 `app/tool/wechat_publish/scripts/` 下执行 `bun install`（或 `npm install` 兼容）生成 `node_modules`（gitignore）。

### 2.3 凭据配置（仓库内）

wechat-api.ts 原生支持三个优先级的凭据来源（wechat-api.ts:516-519）：
1. 环境变量 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`
2. `<cwd>/.baoyu-skills/.env`
3. `~/.baoyu-skills/.env`

选择 **仓库根 `.baoyu-skills/.env`**（第 2 优先级，脚本原生支持，零脚本改动）：

```env
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
```

- 该目录加入 `.gitignore`（参照现有 `config/config.toml` 处理方式，但注意历史跟踪问题——本目录是新建的，无历史包袱）
- 发布参数默认值（theme/author）通过 Agent 工具参数传递，不单独配置段，保持简单

### 2.4 Agent 设计

`WechatPublish` 继承 `ToolCallAgent`：

```python
class WechatPublish(ToolCallAgent):
    name: str = "wechat_publish"
    description: str = "微信公众号发布智能体，可将 markdown 内容发布到公众号草稿箱"
    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT
    max_observe: int = 10000
    max_steps: int = 30
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            WechatPublishTool(),
            NormalPythonExecute(),   # 用于生成/处理文章内容
            AskHuman(),              # 确认发布细节
            Terminate(),
        )
    )
```

### 2.5 工具设计

`WechatPublishTool`（BaseTool 子类）：

- **name**: `wechat_publish`
- **action=1 preview**：`bun wechat-api.ts <file> --dry-run`，本地渲染验证（不联网、不产生草稿），返回渲染结果/错误
- **action=2 publish**：`bun wechat-api.ts <file> [--title ...] [--summary ...] [--author ...] [--theme default] [--cover ...]`，发布到草稿箱，返回 media_id
- **参数**：`file_path`（markdown/html 路径，必填）、`title`、`summary`、`author`、`theme`（默认 default）、`cover`（可选封面路径）、`dry_run`（布尔，true 时走 preview）

执行方式：`asyncio.to_thread` 包裹 `subprocess.run([bun, wechat-api.ts, ...])`（脚本本身是同步 spawnSync 风格 CLI，无需异步子进程），cwd 设为 `scripts/` 目录（保证 `<cwd>/.baoyu-skills/.env` 解析路径正确——注意：脚本查找的是**进程 cwd** 下的 .baoyu-skills/.env，因此 cwd 必须设为仓库根，而非 scripts 目录；详见风险 §6）。

bun 可执行文件解析：`shutil.which("bun")` 优先，缺失时报错提示安装（或回退 `npx -y bun`）。

### 2.6 Web 端接入

| 文件 | 变更 |
|------|------|
| `app/web/chat/models.py` | `AGENT_TYPES` 加入 `"wechat_publish"` |
| `app/web/agent_runner.py` | 新增 `ObservableWechatPublish` 包装类 + `create_observable_agent` 工厂分支 |
| `web_ui/src/` | 新建会话对话框 Agent 选项加入「公众号发布」 |

### 2.7 提示词要点（app/prompt/wechat_publish.py）

1. 职责：发布文章到公众号草稿箱；可先询问内容来源（用户粘贴/文件路径/自行撰写）
2. 流程：内容准备（markdown 落盘 workspace）→ 可选 preview 验证 → publish → 报告 media_id
3. 约束：发布前先 preview（dry-run）校验；封面可选（wechat-api.ts 会自动从内容提取第一张图）；内容未就绪时用 ask_human 澄清

---

## 3. 数据流

```
用户: "帮我发布这篇文章到公众号"
  │
  ▼ WechatPublish ReAct 循环
① ask_human 澄清内容来源（粘贴文本 / 文件路径 / 让 Agent 撰写）
② python_execute 或直接接收 → 内容落盘 workspace/article.md
③ wechat_publish(action=preview, file_path=...)   → bun --dry-run 校验渲染
④ wechat_publish(action=publish, file_path=..., title=..., author=...)
   │ subprocess: bun wechat-api.ts article.md --title ... --author ...
   │ cwd=仓库根 → 读 .baoyu-skills/.env 凭据 → POST api.weixin.qq.com draft/add
   ▼ 返回 media_id
⑤ 报告发布成功 → terminate
```

## 4. 错误处理

- bun 未安装：工具返回明确错误与安装指引（`bun --version` 检查）
- 凭据缺失（.baoyu-skills/.env 不存在或无 WECHAT_APP_ID）：透传 wechat-api.ts 的错误信息，提示检查配置
- 脚本非零退出：捕获 stderr，返回失败原因
- IP 白名单问题（errcode 40164）：透传错误提示，引导用户在公众号后台加白
- 超时：subprocess 加 timeout（默认 60s），超时返回明确错误

## 5. 测试

### 5.1 单元测试（`tests/tool/test_wechat_publish.py`）

- mock `subprocess.run`，断言：
  - publish 模式参数拼装正确（file/--title/--author/--theme/--cover）
  - preview 模式带 `--dry-run`
  - cwd 为仓库根（凭据解析路径正确）
  - 非零退出码 → error 返回
- 无真实网络调用

### 5.2 集成验证（可选，需凭据+白名单）

- `wechat_publish(action=preview, ...)` 真实 dry-run
- `wechat_publish(action=publish, ...)` 真实发布到草稿箱后到公众号后台确认

## 6. 风险与权衡

- **cwd 与凭据路径**：wechat-api.ts 的 `.baoyu-skills/.env` 查找基于**进程 cwd**。若 cwd 设为 scripts/ 目录，会找不到仓库根的 .env。因此工具执行时 cwd 必须为仓库根 `PROJECT_ROOT`（脚本以相对路径 `scripts/wechat-api.ts` 调用）。需在实施时确认脚本行为（读取 `process.cwd()` 还是 `import.meta.dir`）——若脚本基于脚本目录解析，则改为把 .env 放 scripts/ 目录或传环境变量
- **node_modules 体积**：bun install 后 node_modules 较大，加入 .gitignore 即可
- **脚本升级**：全局 skill 更新后需手动重新复制；后续可考虑定期同步（非目标）
- **多用户**：Web 多用户场景下凭据为全局单份（仓库级），所有用户共用同一公众号身份——符合当前单公众号场景
