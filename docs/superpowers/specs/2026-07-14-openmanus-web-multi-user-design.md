# OpenManus 多用户 Web 服务 — 设计文档

> 状态：设计完成，待评审  
> 日期：2026-07-14  
> 分支：feat/web-chat

---

## 1. 概述

### 1.1 目标

将 OpenManus Agent 封装为多用户 Web 服务，允许 2-10 人内部团队通过网页浏览器独立使用不同 Agent，互不干扰。

### 1.2 核心需求

| 需求 | 说明 |
|------|------|
| 独立账号 | 每人一个账号，JWT 认证 |
| 多 Agent 类型 | 用户可选择 general（Manus）或 data_analysis（DataAnalysis） |
| 会话管理 | 每人可创建多个会话，切换/删除 |
| 用户隔离 | 文件系统隔离 + Docker Sandbox 容器隔离 |
| 实时推送 | WebSocket 流式推送 Agent 思考/工具调用/回复 |
| 可扩展 | 后续可水平扩展（加 gunicorn workers / PostgreSQL / Redis） |

### 1.3 非目标（本期不做）

- 用户间协作/共享会话
- 第三方 OAuth（GitHub/Google 登录）
- 定时任务/自动化工作流
- 用量统计/计费
- 管理员面板

---

## 2. 开发与部署环境

### 2.1 双环境策略

| 环境 | 操作系统 | 说明 |
|------|----------|------|
| **开发环境** | Windows 11 + conda (open_manus) | 本地编码、调试、单元测试 |
| **生产环境** | Linux 服务器 (内网) | systemd 托管，最终部署 |

### 2.2 环境差异处理

| 维度 | Windows 开发 | Linux 生产 | 解决方案 |
|------|-------------|-----------|----------|
| Docker | Docker Desktop ✅ | Docker Engine ✅ | API 完全一致，无需适配 |
| Python 路径 | `C:\Users\hyh\anaconda3\envs\open_manus\` | `/opt/conda/envs/open_manus/` | 通过 systemd `Environment` 配置 |
| 数据目录 | `C:\Data\openmanus\` (开发) | `/data/openmanus/` (生产) | `config.toml` 的 `sandbox_data_root` 区分 |
| 文件路径分隔符 | `\` | `/` | `pathlib.Path` 自动处理，代码统一用 `/` |
| Node.js | 本地安装 (Vite 构建用) | **不需要** | 本地 `npm run build` 后产物随代码部署 |
| MySQL | 云端同一实例 | 云端同一实例 | 两个环境连同一个库即可，或开发用本地 MySQL |

### 2.3 开发工作流

```
Windows 本地                          Linux 服务器
┌──────────────────┐                ┌──────────────────┐
│ 1. 编码 + 调试    │                │                  │
│    web_run.py    │                │                  │
│    npm run dev   │                │                  │
│                  │                │                  │
│ 2. 本地集成测试   │                │                  │
│    Docker Sandbox │               │                  │
│    云端 MySQL     │────────────── │  云端 MySQL       │
│                  │                │                  │
│ 3. 构建前端       │                │                  │
│    npm run build │                │                  │
│                  │                │                  │
│ 4. Git Push ─────┼──────────────▶ │ 5. Git Pull       │
│                  │                │    python web_run │
└──────────────────┘                └──────────────────┘
```

### 2.4 无需在 Linux 服务器安装的

- ❌ Node.js（前端已在本地构建好）
- ❌ npm / pnpm
- ❌ Visual Studio / IDE
- ❌ conda（可以用，但不是必须，Python 3.12 venv 也可）
- ✅ 只需：Python 3.12 + Docker + 项目代码

---

## 3. 架构设计

### 3.1 技术栈

#### 后端

| 组件 | 选型 | 用途 |
|------|------|------|
| Web 框架 | FastAPI | REST + WebSocket |
| ASGI 服务器 | Uvicorn | 生产进程管理 |
| 数据库驱动 | aiomysql | 异步 MySQL 连接 |
| ORM | SQLAlchemy 2.0 (async) | 数据库操作 |
| 密码哈希 | passlib[bcrypt] | 用户密码安全存储 |
| JWT | PyJWT | 无状态认证 |
| Docker SDK | docker | 管理用户 Sandbox 容器 |
| 数据校验 | Pydantic v2 | 请求/响应模型（已有） |

```toml
# requirements-web.txt (新增依赖)
aiomysql>=0.2.0
sqlalchemy[asyncio]>=2.0
passlib[bcrypt]>=1.7
PyJWT>=2.8
```

#### 前端

| 组件 | 选型 | 用途 |
|------|------|------|
| 框架 | Vue 3 (Composition API) | SPA 主框架 |
| 构建工具 | Vite | 开发热更新 + 生产打包 |
| UI 样式 | Tailwind CSS | 原子化样式 |
| 状态管理 | Pinia | 用户状态、会话列表 |
| 路由 | Vue Router 4 | 登录页/聊天页 |
| HTTP 客户端 | axios | API 调用 |
| Markdown | marked.js | Agent 回复渲染（已有） |
| 代码高亮 | highlight.js | 代码块语法着色 |
| 图表展示 | ECharts | 数据分析结果预览 |

#### 服务器环境

| 组件 | 说明 |
|------|------|
| 操作系统 | CentOS 7+ / Ubuntu 20.04+ |
| Python | 3.12（已有 conda 环境） |
| MySQL | 8.0（云数据库，通过配置文件连接） |
| Docker | 24+（Sandbox 运行时） |
| Node.js | 20 LTS（仅构建时使用） |

### 3.2 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     Linux 服务器 (内网)                        │
│                                                              │
│  用户浏览器                    systemd 托管                    │
│  ┌──────────┐                ┌──────────────────────────┐    │
│  │ Vue 3 SPA │─── HTTP ───▶ │  Uvicorn (1 worker)       │    │
│  │          │               │  FastAPI                  │    │
│  │ • 登录    │── WebSocket ─▶│                          │    │
│  │ • 聊天    │               │  /api/auth    认证模块    │    │
│  │ • 历史    │               │  /api/chat    会话模块    │    │
│  │ • 文件    │               │  /api/files   文件模块    │    │
│  └──────────┘               │  /ws/{chat_id} WebSocket │    │
│                              └──────┬──────────┬────────┘    │
│                                     │          │              │
│                              ┌──────▼──┐  ┌───▼───────────┐  │
│                              │  云MySQL │  │ Docker Sandbox │  │
│                              │         │  │  per User      │  │
│                              │ • users │  │                │  │
│                              │ • chats │  │ user_1/ws/     │  │
│                              │ • files │  │ user_2/ws/     │  │
│                              └─────────┘  │ user_3/ws/     │  │
│                                           └────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 会话与 Agent 路由模型

```
用户 (User)
  │
  ├─ 会话A (Chat) ─── type: "general"    ─── Manus Agent      ─── Sandbox A
  ├─ 会话B (Chat) ─── type: "data"       ─── DataAnalysis Agent ── Sandbox B
  └─ 会话C (Chat) ─── type: "general"    ─── Manus Agent      ─── Sandbox C
```

**交互流程**：
1. 用户登录 → 获取 JWT Token
2. 前端展示会话列表（可新建/切换/删除）
3. 用户点击某会话 → 建立 WebSocket: `/ws/{chat_id}?token={jwt}`
4. 服务端根据 `chat.agent_type` 创建对应 Agent 实例
5. Agent 绑定到该用户专属的 Docker Sandbox
6. 用户发送任务 → Agent 执行 → 结果回流

### 3.4 多用户隔离方案

```
┌─────────────────────────────────────────────────────────────┐
│                       隔离层次                                │
│                                                             │
│  📁 文件系统层                                               │
│  /data/openmanus/users/{user_id}/                            │
│    ├── workspace/     ← Agent 工作目录 (挂载到 Sandbox)       │
│    │   ├── chat_001/  ← 每个会话独立子目录                    │
│    │   │   ├── input.csv                                     │
│    │   │   ├── chart.png                                     │
│    │   │   └── report.html                                   │
│    │   └── chat_002/                                         │
│    └── uploads/      ← 用户上传的原始文件                     │
│                                                             │
│  🐳 容器层                                                   │
│  Docker Container: sandbox_{user_id}_{chat_id}               │
│    - 挂载: /data/.../user_id/workspace/chat_id → /workspace  │
│    - 网络: 按 agent_type 决定是否开启                         │
│    - 资源: 每个 Sandbox 独立 CPU/内存限制                     │
│                                                             │
│  🔐 应用层                                                   │
│    - JWT Token 包含 user_id，每个 API 请求校验                │
│    - WebSocket 建立时验证 chat 归属当前用户                   │
│    - 文件 API 强制限定在用户目录下，禁止路径穿越              │
└─────────────────────────────────────────────────────────────┘
```

**Agent 类型与 Sandbox 策略**：

| Agent 类型 | Sandbox 网络 | 典型文件产出 |
|-----------|-------------|-------------|
| `general` (Manus) | 开启 (需联网搜索/爬取) | .txt, .py, .html |
| `data_analysis` | 按需 (下载数据时开启) | .csv, .png, .html, .pptx |

**会话清理策略**：
- Agent 执行完毕 → Sandbox 保留 30 分钟（用户可能追加任务）
- 30 分钟无活动 → `SandboxManager` 自动回收容器，保留文件
- 用户主动删除会话 → 立即销毁容器，可选保留文件

---

## 4. 项目结构

```
OpenManus/
├── app/
│   ├── agent/                    # Agent 层 (现有，不动)
│   ├── sandbox/                  # Docker Sandbox (现有，复用)
│   ├── tool/                     # 工具层 (现有，不动)
│   ├── flow/                     # Flow 编排 (现有，不动)
│   │
│   ├── web/                      # 🆕 Web 服务模块 (重构扩展)
│   │   ├── __init__.py
│   │   ├── server.py             # FastAPI 应用入口 + 路由注册
│   │   ├── config.py             # Web 专用配置 (MySQL, JWT 等)
│   │   │
│   │   ├── auth/                 # 认证模块
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # User 表模型
│   │   │   ├── schemas.py        # 注册/登录请求响应
│   │   │   ├── service.py        # 注册/登录/Token 签发逻辑
│   │   │   └── router.py         # /api/auth/* 路由
│   │   │
│   │   ├── chat/                 # 聊天会话模块
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # Chat, Message 表模型
│   │   │   ├── schemas.py        # 请求响应模型
│   │   │   ├── service.py        # 会话 CRUD + Agent 调度
│   │   │   ├── router.py         # /api/chat/* 路由
│   │   │   └── ws_handler.py     # WebSocket /ws/{chat_id} 处理器
│   │   │
│   │   ├── files/                # 文件管理模块
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # UserFile 表模型
│   │   │   ├── router.py         # /api/files/* 路由
│   │   │   └── service.py        # 文件上传/下载/列表
│   │   │
│   │   ├── agent_runner.py       # 重构: 支持多种 Agent 类型的工厂调度
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   └── dependencies.py       # FastAPI Depends (get_current_user 等)
│   │
│   └── config.py                 # 全局配置 (现有，扩展 Web 项)
│
├── web_ui/                       # 🆕 Vue 3 前端项目
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.ts               # Vue 应用入口
│   │   ├── App.vue               # 根组件 (含路由出口)
│   │   ├── router/
│   │   │   └── index.ts          # 路由: /login, /chat/:id, /files
│   │   ├── stores/
│   │   │   ├── auth.ts           # 用户登录状态 (Pinia)
│   │   │   └── chat.ts           # 会话列表 + WebSocket 连接 (Pinia)
│   │   ├── api/
│   │   │   ├── client.ts         # axios 实例 + JWT 拦截器
│   │   │   ├── auth.ts           # 登录/注册 API
│   │   │   └── chat.ts           # 会话/消息 API
│   │   ├── views/
│   │   │   ├── LoginView.vue     # 登录/注册页
│   │   │   └── ChatView.vue      # 主聊天页 (侧边栏 + 消息区)
│   │   ├── components/
│   │   │   ├── ChatSidebar.vue   # 会话列表侧边栏
│   │   │   ├── ChatWindow.vue    # 消息展示 + 输入
│   │   │   ├── MessageBubble.vue # 单条消息渲染
│   │   │   └── NewChatDialog.vue # 新建会话弹窗（选择 Agent 类型）
│   │   └── assets/
│   │       └── main.css          # Tailwind 入口
│   └── dist/                     # 构建产物 → Serving 目录
│
├── web_run.py                    # 修改: 同时 serve 前端静态文件
├── config/
│   └── config.toml               # 新增 [web] 段
├── requirements.txt              # 新增 Web 依赖
└── docs/
    ├── sandbox-guide.md
    └── superpowers/specs/
        └── 2026-07-14-openmanus-web-multi-user-design.md  # 本文档
```

---

## 5. 数据库设计

### 5.1 表结构

```sql
-- ── 用户表 ──────────────────────────────────────────
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,          -- bcrypt 哈希
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── 会话表 ──────────────────────────────────────────
CREATE TABLE chats (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL,
    title       VARCHAR(200) NOT NULL DEFAULT '新会话',
    agent_type  VARCHAR(50)  NOT NULL DEFAULT 'general',   -- general | data_analysis
    sandbox_id  VARCHAR(100) NULL,              -- Docker 容器 ID，结束后置 NULL
    status      VARCHAR(20)  NOT NULL DEFAULT 'active',    -- active | archived
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_status (user_id, status)
);

-- ── 消息表 ──────────────────────────────────────────
CREATE TABLE messages (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    chat_id     INT          NOT NULL,
    role        VARCHAR(20)  NOT NULL,           -- user | assistant | tool | system
    content     TEXT         NULL,               -- 消息文本 / 工具返回值
    tool_name   VARCHAR(100) NULL,               -- 工具名称 (role=tool 时有值)
    tool_args   JSON         NULL,               -- 工具调用参数
    event_type  VARCHAR(30)  NULL,               -- thinking | tool_start | tool_end | ...
    metadata    JSON         NULL,               -- 扩展字段
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    INDEX idx_chat_time (chat_id, created_at)
);

-- ── 用户文件表 ──────────────────────────────────────
CREATE TABLE user_files (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL,
    chat_id     INT          NULL,               -- 所属会话，可为空
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(500) NOT NULL,           -- 相对于用户目录的路径
    file_size   BIGINT       NOT NULL DEFAULT 0,
    mime_type   VARCHAR(100) NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL,
    INDEX idx_user (user_id)
);
```

### 5.2 表关系

```
users 1──N chats 1──N messages
  │              │
  └──N user_files ──N (chat 可为 null)
```

---

## 6. API 设计

### 6.1 REST API

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 否 | 注册 `{username, password}` |
| POST | `/api/auth/login` | 否 | 登录 → 返回 `{access_token, user}` |
| GET | `/api/chats` | 是 | 当前用户会话列表 |
| POST | `/api/chats` | 是 | 新建会话 `{agent_type}` |
| GET | `/api/chats/{id}` | 是 | 会话详情 + 最新消息 |
| DELETE | `/api/chats/{id}` | 是 | 删除会话 (含 Sandbox 清理) |
| GET | `/api/chats/{id}/messages` | 是 | 分页历史消息 `?before_id=&limit=50` |
| POST | `/api/files/upload` | 是 | 上传文件 (multipart/form-data) |
| GET | `/api/files` | 是 | 用户文件列表 `?chat_id=` |
| GET | `/api/files/{id}/download` | 是 | 下载文件 |
| DELETE | `/api/files/{id}` | 是 | 删除文件 |

### 6.2 WebSocket

```
WS  /ws/{chat_id}?token={jwt}
```

**客户端 → 服务端**：

```json
{"type": "prompt", "content": "帮我分析这份数据"}
```

**服务端 → 客户端**（事件类型）：

| 事件类型 | 说明 | 包含字段 |
|----------|------|----------|
| `step_start` | 步骤开始 | `step`, `max_steps` |
| `thinking` | 思考过程 | `content`, `tool_calls` |
| `tool_start` | 工具调用开始 | `tool`, `args` |
| `tool_end` | 工具调用结束 | `tool`, `result`, `ok` |
| `assistant` | Agent 文本回复 | `content` |
| `done` | 任务完成 | `reason` |
| `error` | 错误 | `message` |

**服务端 WebSocket 处理流程**（`chat/ws_handler.py`）：

```
ws.accept() → 校验 JWT → 校验 chat 归属
→ ensure_sandbox(user_id, chat)    # 创建或复用 Sandbox
→ create_agent(chat.agent_type)    # Manus / DataAnalysis
→ 接收 prompt → agent.run() → 事件推流
→ 消息持久化到 MySQL
→ agent 完成 → 延迟 30min 回收 Sandbox
```

### 6.3 认证机制

- JWT Payload：`{user_id, username, exp}`
- 有效期：24 小时
- REST 传递：`Authorization: Bearer <token>`
- WebSocket 传递：URL 参数 `?token=<jwt>`

---

## 7. 前端设计

### 7.1 页面结构

```
/login                          # 登录/注册页
/chat                           # 聊天主页 (重定向到最近会话)
/chat/:id                       # 具体会话
```

### 7.2 聊天页布局

```
┌──────────────────────────────────────┐
│  🤖 OpenManus          [用户名 ▼]    │  ← 顶栏
├────────────┬─────────────────────────┤
│ 会话列表    │                         │
│            │  会话：数据分析报告       │  ← 标题栏
│ 📊 数据分析 │  ┌─────────────────────┐│
│ 🌐 网页抓取 │  │ Agent: DataAnalysis ││  ← 状态栏
│            │  │ 状态: 就绪           ││
│ [+ 新建]   │  └─────────────────────┘│
│            │                         │
│            │  [消息区域]              │  ← 消息区
│            │  - 用户消息气泡          │
│            │  - 思考折叠面板          │
│            │  - 工具卡片             │
│            │  - Agent 回复 (Markdown) │
│            │                         │
│            │  [输入框]    [发送 ▶]    │  ← 输入区
│            │  [📎 上传文件]           │
└────────────┴─────────────────────────┘
```

**消息渲染规则**（复用现有 `index.html` 的事件处理逻辑）：

| event_type | UI 组件 | 样式 |
|------------|---------|------|
| `user` | 蓝色气泡，右对齐 | `bg-blue-500 text-white` |
| `step_start` | 居中步骤指示器 | `text-xs text-gray-400` |
| `thinking` | 可折叠面板，展开查看 | `bg-gray-100 border` |
| `tool_start` | 工具卡片（黄色左边框 + spinner） | `border-l-4 border-yellow-400` |
| `tool_end` | 合并到 tool_start 卡片（绿色/红色左边框） | `ok ? green : red` |
| `assistant` | 白色气泡 + Markdown 渲染 | `bg-white border` |
| `error` | 红色错误提示 | `bg-red-50 border-red-200` |
| `done` | 居中结束标记 | `text-xs text-gray-400` |

### 7.3 组件树

```
App.vue
├── LoginView.vue                    (route: /login)
└── ChatView.vue                     (route: /chat, /chat/:id)
    ├── ChatSidebar.vue
    │   ├── 会话列表 (v-for)
    │   └── NewChatDialog.vue        (新建按钮弹窗)
    └── ChatWindow.vue
        ├── 标题栏 + 状态
        ├── 消息区域
        │   └── MessageBubble.vue    (v-for, 按 event_type 分发渲染)
        └── 输入区 + 文件上传
```

---

## 8. 配置设计

### 8.1 config.toml 新增段

```toml
[web]
# MySQL 云数据库连接
mysql_host = "your-cloud-mysql-host"
mysql_port = 3306
mysql_user = "openmanus"
mysql_password = "your-password"
mysql_database = "openmanus_web"

# JWT 认证
jwt_secret_key = "your-secret-key-change-in-production"
jwt_expire_hours = 24

# Sandbox 根目录 (用户隔离的基路径)
sandbox_data_root = "/data/openmanus"

# 前端静态文件
static_dir = "web_ui/dist"
```

### 8.2 环境变量（可选，用于 Docker 部署）

```bash
OPENMANUS_MYSQL_HOST=xxx
OPENMANUS_MYSQL_PASSWORD=xxx
OPENMANUS_JWT_SECRET=xxx
```

Config 加载优先级：环境变量 > config.toml > 默认值

---

## 9. 部署运维

### 9.1 服务器环境准备

```bash
# 1. Docker (Sandbox 运行时)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Python 3.12 + conda
# (已有 conda 环境 open_manus)

# 3. Node.js 20 LTS (仅构建前端时使用)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 4. 创建数据目录
sudo mkdir -p /data/openmanus
sudo chown -R $USER:$USER /data/openmanus
```

### 9.2 构建与启动

```bash
# 1. 安装后端依赖
pip install -r requirements.txt
pip install aiomysql sqlalchemy[asyncio] passlib[bcrypt] PyJWT

# 2. 初始化数据库 (手动执行建表 SQL 或通过 Alembic)
# 在云端 MySQL 上执行 docs/superpowers/specs/2026-07-14-openmanus-web-multi-user-design.md 第4节中的建表语句

# 3. 构建前端
cd web_ui
npm install
npm run build          # 产出到 dist/
cd ..

# 4. 启动服务
python web_run.py
# 访问 http://<服务器IP>:8080
```

### 9.3 systemd 生产部署

```ini
# /etc/systemd/system/openmanus-web.service
[Unit]
Description=OpenManus Web Service
After=network.target docker.service

[Service]
Type=simple
User=openmanus
WorkingDirectory=/opt/OpenManus
Environment="PATH=/opt/conda/envs/open_manus/bin:/usr/bin:/bin"
ExecStart=/opt/conda/envs/open_manus/bin/python web_run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openmanus-web
sudo systemctl status openmanus-web
```

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Docker Sandbox 未集成到 Agent | 需要修改 `PythonExecute` 调用链 | 分阶段：先复用 SandboxManager 做文件隔离，再替换执行器 |
| 单进程 WebSocket 并发限制 | 10 人以上时可能出现连接超时 | 后续加 gunicorn workers + sticky sessions |
| Agent 长时间执行阻塞 asyncio | 其他用户 WebSocket 心跳受影响 | `asyncio.create_task` + 合理超时 |
| MySQL 云端网络延迟 | 每次查询相比本地慢 5-20ms | 使用连接池 (SQLAlchemy QueuePool)，充分预热 |
| 容器资源耗尽 | 多用户同时创建 Sandbox 时 | `SandboxManager.max_sandboxes` 限制 + 资源配额 |

---

## 11. 后续扩展路线

| 阶段 | 内容 | 触发条件 |
|------|------|----------|
| Phase 1 | 本设计完整实现 | 当前 |
| Phase 2 | PostgreSQL 替代 MySQL + Redis 缓存 | 用户 > 20 或查询变慢 |
| Phase 3 | Celery 任务队列 + 多 worker | 并发 > 10 或 Agent 任务 > 5min |
| Phase 4 | Nginx 反向代理 + gunicorn 多进程 | 需要 HTTPS 或负载均衡 |
| Phase 5 | Kubernetes 编排 | 多台服务器 |
