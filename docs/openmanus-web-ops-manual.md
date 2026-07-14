# OpenManus Web 多用户服务 — 运行与运维手册

> **版本**：0.2.0 | **分支**：feat/web-chat | **更新日期**：2026-07-14
> **面向读者**：初级 Python 程序员，具备基本的命令行和数据库操作能力
> **覆盖范围**：本地开发运行、生产部署、日常运维、故障排查

---

## 目录

1. [项目概览](#1-项目概览)
2. [本地开发环境搭建](#2-本地开发环境搭建)
3. [数据库初始化](#3-数据库初始化)
4. [启动与停止](#4-启动与停止)
5. [运行测试](#5-运行测试)
6. [生产部署](#6-生产部署)
7. [日常运维](#7-日常运维)
8. [配置参考](#8-配置参考)
9. [架构速查](#9-架构速查)
10. [故障排查](#10-故障排查)

---

## 1. 项目概览

### 1.1 这是什么

OpenManus Web 是一个多用户 AI Agent Web 服务。用户通过浏览器登录后，可以创建聊天会话，让 AI Agent（通用 Manus / 数据分析 DataAnalysis）自动执行任务。每个用户的会话运行在独立的 Docker 容器中，互不干扰。

### 1.2 核心组件

```
浏览器 (Vue 3 SPA)
      │
      ├── HTTP REST ──▶ FastAPI (uvicorn) ──▶ MySQL (云端)
      │
      └── WebSocket ──▶ Agent 执行引擎 ──▶ Docker Sandbox (每会话一个容器)
```

| 组件              | 技术                        | 用途                       |
| ----------------- | --------------------------- | -------------------------- |
| **后端**    | Python 3.12 + FastAPI       | REST API + WebSocket       |
| **数据库**  | MySQL 8.0 (云端)            | 用户、会话、消息、文件记录 |
| **Sandbox** | Docker 容器                 | Agent 隔离执行环境         |
| **前端**    | Vue 3 + Vite + Tailwind CSS | 单页应用（SPA）            |
| **认证**    | JWT (HS256, 24h有效期)      | 无状态用户认证             |

### 1.3 关键文件清单

```
OpenManus/
├── web_run.py                    # 🔑 启动入口：python web_run.py
├── web_ui/                       # 前端源码
│   ├── src/                      #   Vue 组件/API/Store
│   └── dist/                     #   构建产物（直接 serving）
├── app/
│   ├── web/                      # 🆕 多用户 Web 模块
│   │   ├── server.py             #   FastAPI 应用 + 全路由汇聚
│   │   ├── database.py           #   SQLAlchemy 异步引擎
│   │   ├── dependencies.py       #   get_current_user 依赖注入
│   │   ├── agent_runner.py       #   Agent 工厂（Manus/DataAnalysis）
│   │   ├── auth/                 #   认证：User 模型、JWT、注册/登录
│   │   ├── chat/                 #   会话：Chat/Message 模型、CRUD、WebSocket
│   │   ├── files/                #   文件：上传/下载/删除
│   │   └── sandbox/              #   Sandbox：Docker 容器生命周期
│   ├── agent/                    # Agent 实现（不动）
│   └── sandbox/                  # Docker Sandbox 核心（不动）
├── config/
│   ├── config.example.toml       # 配置模板
│   └── config.toml               # 实际配置（gitignore）
├── deploy/
│   ├── deploy.sh                 # Linux 一键部署脚本
│   └── openmanus-web.service     # systemd 服务文件
├── tests/web/                    # Web 模块测试
└── docs/
    └── sandbox-guide.md          # Sandbox 详细手册
```

---

## 2. 本地开发环境搭建

### 2.1 前置条件

| 软件                       | 最低版本 | 检查命令             |
| -------------------------- | -------- | -------------------- |
| Windows 11 / macOS / Linux | —       | —                   |
| Python                     | 3.12     | `python --version` |
| Docker Desktop             | 24+      | `docker --version` |
| Node.js（仅前端开发）      | 20 LTS   | `node --version`   |
| MySQL（云端或本地）        | 8.0      | `mysql --version`  |

### 2.2 一次性搭建（Windows 11 为例）

```powershell
# 1. 进入项目目录
cd C:\Code\OpenManus

# 2. 创建并激活 conda 环境
conda create -n open_manus python=3.12 -y
conda activate open_manus

# 3. 安装 Python 依赖（包含 Web 服务依赖）
pip install -r requirements.txt

# 4. 安装浏览器自动化（可选，Manus agent 需要）
playwright install

# 5. 拉取 Docker sandbox 镜像
docker pull python:3.12-slim

# 6. 配置文件
#    复制 config/config.example.toml → config/config.toml
#    编辑 config.toml，填入 LLM API 密钥和 MySQL 连接信息
#    确保末尾有 [web] 段（详见第 8 节"配置参考"）

# 7. 初始化数据库（详见第 3 节）

# 8. 安装前端依赖并构建（仅前端开发时需要）
cd web_ui
npm install
npm run build      # 产出 dist/ 目录
cd ..
```

### 2.3 验证环境

```powershell
# 验证 Python 依赖
python -c "import fastapi, uvicorn, sqlalchemy, aiomysql, passlib, jwt, docker; print('Python 依赖 OK')"

# 验证配置
python -c "from app.config import config; print('MySQL:', config.web.mysql_host); print('Sandbox:', config.web.sandbox_data_root)"

# 验证 Docker
docker ps
```

---

## 3. 数据库初始化

本项目使用 **MySQL 云端数据库**（也可以本地安装）。需要在 MySQL 中创建数据库和 4 张表。

### 3.1 创建数据库

用你熟悉的 MySQL 客户端（Navicat、DBeaver、mysql CLI）连接数据库，执行：

```sql
CREATE DATABASE IF NOT EXISTS openmanus_web
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

### 3.2 建表

按顺序执行以下 4 条 CREATE TABLE（注意外键依赖顺序）：

```sql
-- 1. 用户表（最先创建，被其他表引用）
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 会话表
CREATE TABLE IF NOT EXISTS chats (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL,
    title       VARCHAR(200) NOT NULL DEFAULT '新会话',
    agent_type  VARCHAR(50)  NOT NULL DEFAULT 'general',
    sandbox_id  VARCHAR(100) NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 消息表
CREATE TABLE IF NOT EXISTS messages (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    chat_id     INT          NOT NULL,
    role        VARCHAR(20)  NOT NULL,
    content     TEXT         NULL,
    tool_name   VARCHAR(100) NULL,
    tool_args   JSON         NULL,
    event_type  VARCHAR(30)  NULL,
    extra_data  JSON         NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    INDEX idx_chat_time (chat_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 用户文件表
CREATE TABLE IF NOT EXISTS user_files (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL,
    chat_id     INT          NULL,
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(500) NOT NULL,
    file_size   BIGINT       NOT NULL DEFAULT 0,
    mime_type   VARCHAR(100) NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.3 验证建表

```sql
USE openmanus_web;
SHOW TABLES;
-- 应输出：users, chats, messages, user_files
```

### 3.4 配置连接

编辑 `config/config.toml` 的 `[web]` 段，填入真实数据库凭据：

```toml
[web]
mysql_host = "你的MySQL主机地址"
mysql_port = 3306
mysql_user = "openmanus"
mysql_password = "你的密码"
mysql_database = "openmanus_web"

jwt_secret_key = "请生成一个随机字符串替换这里"
jwt_expire_hours = 24

sandbox_data_root = "C:/Data/openmanus"     # Windows 本地
# sandbox_data_root = "/data/openmanus"     # Linux 生产
static_dir = "web_ui/dist"
```

> ⚠️ **关键**：`jwt_secret_key` 必须改为随机字符串。以下是详细说明。

#### 什么是 jwt_secret_key

它就是一把**签名密钥**。可以理解为：你给每个登录用户发了一张"电子门禁卡"（JWT token），`jwt_secret_key` 就是你用来在门禁卡上盖章的**私人印章**。

**它在哪里被使用？** 只有两处，都在 `app/web/auth/service.py` 里：

| 场景 | 函数 | 做了什么 |
|------|------|----------|
| 用户登录时——签发 token | `create_access_token()` | 用密钥对 token 签名（盖章） |
| 用户每次请求 API 时——验证 token | `decode_access_token()` | 用同一把密钥验证签名（验章） |

```
用户登录                              用户后续请求 API
  POST /api/auth/login                 GET /api/chats
  {username, password}                 Header: Bearer <token>
  │                                    │
  ▼                                    ▼
create_access_token()              decode_access_token()
  用 jwt_secret_key 签名             用 jwt_secret_key 验签
  生成 token → 返回前端              签名有效？→ 通过
                                      签名无效/过期？→ 401

流程：用户登录成功 → 后端签发 JWT → 前端存到 localStorage
    → 后续请求前端自动在 Header 里带 token → 后端验证签名通过
```

**为什么必须改？** token 的内容（用户名、用户 ID）只是 base64 编码，任何人都能解码看到。但 token 末尾的**签名**是哈希过的——只有持有同一把 `jwt_secret_key` 的人才能生成合法签名。如果密钥是公开的 `"please-change-me..."`，攻击者可以伪造任意用户的 token 来冒充登录。

**如何生成？** 一行命令就能生成一个安全的随机密钥：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

输出示例：`dGg7XpQ2vL9mKj8wR1yF3bN6cA5eH4sT` —— 复制粘贴到 `jwt_secret_key` 即可。

**开发 + 生产注意事项：**
- Windows 开发机和 Linux 服务器**用同一个值**最佳——这样跨环境不会有 token 验证问题
- 如果不小心泄露（比如提交到了公开仓库），立即生成新的——所有已登录用户需重新登录即可
- 这个值**不需要记在脑子里**，它只存在于 `config.toml` 这一处

---

## 4. 启动与停止

### 4.1 本地开发（Windows）

```powershell
# 确保 conda 环境已激活
conda activate open_manus

# 确保 Docker Desktop 正在运行
docker ps

# 启动后端服务
cd C:\Code\OpenManus
python web_run.py
```

后端启动后：

- **API 文档**：http://localhost:8080/docs （Swagger UI，可交互测试所有 API）
- **聊天界面**：http://localhost:8080 （Vue 3 SPA）
- **WebSocket**：`ws://localhost:8080/ws/{chat_id}?token={jwt}`

### 4.2 前端独立开发（可选）

如果只改前端代码，可以分开启动：

```powershell
# 终端 1：启动后端
python web_run.py

# 终端 2：启动前端 dev server（自动代理 /api 到 8080）
cd web_ui
npm run dev
# 访问 http://localhost:5173
```

前端 dev server 通过 Vite proxy 自动将 `/api` 请求转发到后端 8080 端口。

### 4.3 停止服务

```powershell
# 直接 Ctrl+C 即可停止 uvicorn

# 如果后台运行，查找并终止
Get-Process -Name python | Where-Object {$_.CommandLine -like "*web_run*"}
# 或
taskkill /F /IM python.exe    # 注意：会杀死所有 Python 进程
```

---

## 5. 运行测试

### 5.1 测试概览

测试文件位于 `tests/web/`，采用 TDD（测试驱动开发）编写。

| 测试文件                        | 测试范围             | 需要 MySQL | 需要 Docker |
| ------------------------------- | -------------------- | ---------- | ----------- |
| `test_config.py`              | WebSettings 配置加载 | 否         | 否          |
| `test_auth_service.py`        | 密码哈希 + JWT       | 否         | 否          |
| `test_auth_router.py`         | 注册/登录 API        | 是         | 否          |
| `test_database.py`            | 数据库连接冒烟       | 是         | 否          |
| `test_chat_models.py`         | Chat/Message ORM     | 是         | 否          |
| `test_chat_router.py`         | 会话 CRUD API        | 是         | 否          |
| `test_sandbox_service.py`     | 目录创建             | 否         | 否          |
| `test_sandbox_integration.py` | Sandbox 容器集成     | 是         | 是          |

### 5.2 运行命令

```powershell
# 运行不依赖数据库的测试（始终可通过）
pytest tests/web/test_config.py tests/web/test_auth_service.py tests/web/test_sandbox_service.py -v

# 运行所有测试（需要 MySQL + Docker Desktop 运行中）
pytest tests/web/ -v

# 运行单个测试
pytest tests/web/test_auth_service.py::test_jwt_roundtrip -v

# 显示详细输出
pytest tests/web/ -v -s
```

### 5.3 测试预期结果

如果 MySQL 不可达（使用占位符凭据），依赖数据库的测试会报 `OperationalError`，这是**预期行为**。不依赖数据库的 5 个测试应该始终通过：

```
tests/web/test_config.py::test_web_config_exists   ✅
tests/web/test_config.py::test_web_config_types     ✅
tests/web/test_config.py::test_mysql_url_format     ✅
tests/web/test_auth_service.py::test_hash_and_verify_password ✅
tests/web/test_auth_service.py::test_jwt_roundtrip  ✅
tests/web/test_auth_service.py::test_invalid_token_raises ✅
tests/web/test_sandbox_service.py::test_ensure_user_directories_creates_paths ✅
```

---

## 6. 生产部署

### 6.1 部署架构

```
Linux 服务器
├── /opt/OpenManus/               ← 项目代码（git clone）
├── /data/openmanus/              ← 用户文件存储
│   └── users/{user_id}/
│       ├── workspace/{chat_id}/  ← Agent 工作目录（挂载到容器）
│       └── uploads/             ← 用户上传文件
├── systemd: openmanus-web        ← 托管进程
└── Docker: sandbox_u*_c*_*      ← 每会话独立容器
```

### 6.2 首次部署（Linux 服务器）

```bash
# 1. 克隆代码，切换到 web 分支
git clone <repo-url> /opt/OpenManus
cd /opt/OpenManus
git checkout feat/web-chat

# 2. 安装依赖
pip install -r requirements.txt

# 3. 拉取 Docker sandbox 镜像
docker pull python:3.12-slim

# 4. 配置（关键步骤！）
cp config/config.example.toml config/config.toml
# 用 vim/nano 编辑 config.toml：
#   - 填入真实的 LLM API 密钥
#   - 在 [web] 段填入真实 MySQL 凭据
#   - 修改 jwt_secret_key 为随机字符串
#   - 修改 sandbox_data_root = "/data/openmanus"

# 5. 创建数据目录
sudo mkdir -p /data/openmanus
sudo chown -R $USER:$USER /data/openmanus

# 6. 初始化数据库（见第 3 节）

# 7. 安装 systemd 服务
sudo cp deploy/openmanus-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openmanus-web
sudo systemctl start openmanus-web

# 8. 验证
sudo systemctl status openmanus-web
curl http://localhost:8080/
```

也可以使用一键部署脚本：

```bash
bash deploy/deploy.sh
```

### 6.3 更新部署（已有实例运行中）

```bash
cd /opt/OpenManus
git pull origin feat/web-chat

# 如果有新依赖
pip install -r requirements.txt

# 重新构建前端（如果前端代码有更新）
cd web_ui && npm install && npm run build && cd ..

# 重启服务
sudo systemctl restart openmanus-web
```

### 6.4 查看日志

```bash
# 实时日志
sudo journalctl -u openmanus-web -f

# 最近 100 行
sudo journalctl -u openmanus-web -n 100

# 只看错误
sudo journalctl -u openmanus-web -p err
```

---

## 7. 日常运维

### 7.1 健康检查

```bash
# REST API 是否响应
curl http://localhost:8080/

# 数据库是否连通（需要配置正确）
python -c "import asyncio; from app.web.database import engine; from sqlalchemy import text; asyncio.run(engine.connect()).execute(text('SELECT 1')); print('DB OK')"

# Docker 是否可用
docker ps
```

### 7.2 用户管理

```bash
# 查看所有用户（通过 API — 需管理员 token，目前无管理员面板，直接用 SQL）
mysql -h <host> -u openmanus -p -e "SELECT id, username, created_at FROM openmanus_web.users;"

# 删除用户（CASCADE 会同时删除其会话、消息、文件）
# mysql -e "DELETE FROM openmanus_web.users WHERE username='用户名';"
```

### 7.3 清理 Docker 资源

Agent 执行完毕后 Sandbox 会被 WebSocket Handler 的 `finally` 块自动回收。如果出现异常导致孤儿容器残留：

```bash
# 查看本项目创建的容器
docker ps -a --filter "name=sandbox_u"

# 批量删除已停止的 Sandbox 容器
docker container prune --filter "name=sandbox_u" -f

# 查看磁盘占用
docker system df

# 全面清理（谨慎！会删除所有未使用的镜像/容器/卷）
docker system prune -a
```

### 7.4 清理用户文件

```bash
# 用户文件存放在 sandbox_data_root 下
# 查看各用户磁盘占用
du -sh /data/openmanus/users/*/

# 删除指定用户的文件（谨慎）
rm -rf /data/openmanus/users/{user_id}/
```

### 7.5 监控建议

| 指标          | 查看方式                                                         |
| ------------- | ---------------------------------------------------------------- |
| 服务是否运行  | `sudo systemctl status openmanus-web`                          |
| 内存占用      | `top -p $(pgrep -f web_run)`                                   |
| Docker 容器数 | `docker ps --filter "name=sandbox" \| wc -l`                    |
| 磁盘空间      | `df -h /data/openmanus`                                        |
| 错误日志      | `sudo journalctl -u openmanus-web -p err --since "1 hour ago"` |

---

## 8. 配置参考

### 8.1 config.toml `[web]` 段完整参考

```toml
[web]
# ── MySQL 云数据库 ──────────────────────────
mysql_host = "your-cloud-mysql-host"    # 必填
mysql_port = 3306                        # 默认 3306
mysql_user = "openmanus"                 # 必填
mysql_password = "your-password"         # 必填
mysql_database = "openmanus_web"         # 必填

# ── JWT 认证 ──────────────────────────────
jwt_secret_key = "随机字符串"            # 必填，务必修改！
jwt_expire_hours = 24                    # Token 有效期（小时）

# ── 文件存储 ──────────────────────────────
# Windows 本地：
sandbox_data_root = "C:/Data/openmanus"
# Linux 生产：
# sandbox_data_root = "/data/openmanus"

# ── 前端静态文件 ──────────────────────────
static_dir = "web_ui/dist"
```

### 8.2 LLM 配置（已有，`[llm]` 段）

```toml
[llm]
model = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
api_key = "sk-你的密钥"
max_tokens = 8192
temperature = 0.0
```

这是 Agent 执行任务调用的 LLM。API 格式兼容 OpenAI，可以换成任何兼容的 API（如 Claude、GPT-4o 等）。

### 8.3 Sandbox 配置（已有，`[sandbox]` 段）

```toml
[sandbox]
# use_sandbox = false       # 当前 Web 服务不用这个开关
image = "python:3.12-slim"  # Sandbox 容器镜像
work_dir = "/workspace"     # 容器内工作目录
memory_limit = "512m"       # 每容器内存上限
cpu_limit = 1.0             # 每容器 CPU 上限
timeout = 300               # 命令超时（秒）
network_enabled = false     # 默认关闭网络
```

> **注意**：`network_enabled` 在 `config.toml` 中设置的是默认值。Web 服务会按 Agent 类型覆盖：`general` 类型（Manus）开启网络，`data_analysis` 类型关闭网络。

### 8.4 配置加载优先级

1. config.toml 文件中的值
2. 代码中的 `Field(default=...)` 默认值

当前版本暂未实现环境变量覆盖，后续可以扩展。

---

## 9. 架构速查

### 9.1 目录结构

```
app/web/
├── server.py                FastAPI app + 路由注册
├── database.py              SQLAlchemy: Base, engine, AsyncSessionLocal, get_db()
├── dependencies.py          FastAPI Depends: get_current_user
├── agent_runner.py          ObservableManus + ObservableDataAnalysis + 工厂函数
│
├── auth/
│   ├── models.py            User (users 表)
│   ├── schemas.py           RegisterRequest, LoginRequest, AuthResponse
│   ├── service.py           hash_password, verify_password, create_access_token, decode_access_token
│   └── router.py            POST /api/auth/register, POST /api/auth/login
│
├── chat/
│   ├── models.py            Chat, Message (chats 表, messages 表)
│   ├── schemas.py           ChatCreate, ChatOut, ChatDetail, MessageOut
│   ├── service.py           create_chat, get_user_chats, get_chat_or_404, save_message, ...
│   ├── router.py            GET/POST/DELETE /api/chats, GET /api/chats/{id}/messages
│   └── ws_handler.py        WebSocket /ws/{chat_id} → handle_chat_ws()
│
├── files/
│   ├── models.py            UserFile (user_files 表)
│   ├── schemas.py           FileInfo
│   ├── service.py           save_uploaded_file, list_user_files, get_file_or_404, delete_file_record
│   └── router.py            POST/GET/DELETE /api/files
│
└── sandbox/
    └── service.py           ensure_user_directories, create_session_sandbox, destroy_session_sandbox
```

### 9.2 API 总表

| 方法   | 路径                         | 认证 | 说明                             |
| ------ | ---------------------------- | ---- | -------------------------------- |
| POST   | `/api/auth/register`       | 否   | 注册`{username, password}`     |
| POST   | `/api/auth/login`          | 否   | 登录 →`{access_token, user}`  |
| GET    | `/api/chats`               | 是   | 当前用户的会话列表               |
| POST   | `/api/chats`               | 是   | 新建会话`{agent_type, title?}` |
| GET    | `/api/chats/{id}`          | 是   | 会话详情 + 最近消息              |
| DELETE | `/api/chats/{id}`          | 是   | 删除会话（含 Sandbox 回收）      |
| GET    | `/api/chats/{id}/messages` | 是   | 分页历史消息                     |
| POST   | `/api/files/upload`        | 是   | 上传文件（multipart）            |
| GET    | `/api/files`               | 是   | 文件列表`?chat_id=`            |
| GET    | `/api/files/{id}/download` | 是   | 下载文件                         |
| DELETE | `/api/files/{id}`          | 是   | 删除文件                         |
| WS     | `/ws/{chat_id}?token=`     | 是   | WebSocket 聊天连接               |

### 9.3 WebSocket 事件协议（7 种类型）

| 事件           | 方向           | 关键字段                     | 触发时机       |
| -------------- | -------------- | ---------------------------- | -------------- |
| `prompt`     | 客户端→服务端 | `content`                  | 用户发送任务   |
| `step_start` | 服务端→客户端 | `step`, `max_steps`      | 每步开始       |
| `thinking`   | 服务端→客户端 | `content`, `tool_calls`  | LLM 思考       |
| `tool_start` | 服务端→客户端 | `tool`, `args`           | 工具调用开始   |
| `tool_end`   | 服务端→客户端 | `tool`, `result`, `ok` | 工具调用结束   |
| `assistant`  | 服务端→客户端 | `content`                  | Agent 最终回复 |
| `done`       | 服务端→客户端 | `reason`                   | 任务完成       |
| `error`      | 服务端→客户端 | `message`                  | 异常           |

### 9.4 用户隔离三层模型

```
📁 文件系统层
   /data/openmanus/users/{user_id}/
     ├── workspace/{chat_id}/    ← Agent 工作目录（挂载到容器 /workspace）
     └── uploads/               ← 用户上传文件

🐳 容器层
   Docker Container: sandbox_u{user_id}_c{chat_id}_{hex}
     网络: general 开启 / data_analysis 关闭

🔐 应用层
   JWT token 校验 → 每个 API/WebSocket 请求验证身份
   chat 归属校验 → 只能访问自己的会话
   文件访问 → 强制限定在用户目录内
```

### 9.5 Agent 创建流程（WebSocket 连接时）

```
客户端连接 ws://host:8080/ws/{chat_id}?token={jwt}
  │
  ├─ 1. decode_access_token(token)  → user_id
  ├─ 2. get_chat_or_404(db, chat_id, user_id)  → chat
  ├─ 3. create_session_sandbox(user_id, chat_id, network)  → DockerSandbox
  ├─ 4. create_observable_agent(chat.agent_type, queue)  → Agent
  ├─ 5. agent.run(prompt)  → 事件推流 + 持久化到 MySQL
  └─ 6. finally: 销毁 Sandbox + 清理 Agent
```

---

## 10. 故障排查

### 10.1 启动失败

| 症状                                           | 可能原因                     | 解决                                |
| ---------------------------------------------- | ---------------------------- | ----------------------------------- |
| `ModuleNotFoundError: No module named 'xxx'` | 依赖未安装                   | `pip install -r requirements.txt` |
| `RuntimeError: Web 配置未找到`               | config.toml 缺少`[web]` 段 | 参考 config.example.toml 添加       |
| `Can't connect to MySQL`                     | 数据库不可达                 | 检查 MySQL 是否在线、防火墙、凭据   |
| `No such image: python:3.12-slim`            | Sandbox 镜像未拉取           | `docker pull python:3.12-slim`    |
| `Docker SDK 报错`                            | Docker Desktop 未运行        | 启动 Docker Desktop                 |

### 10.2 API 返回 401

```
{"detail": "缺失认证 token"}
```

**原因**：客户端没有在请求头携带 JWT。**解决**：

1. 先调用 `POST /api/auth/login` 获取 token
2. 后续请求在 Header 中加 `Authorization: Bearer {token}`

```
{"detail": "无效或过期的 token"}
```

**原因**：JWT 已过期（默认 24 小时）。
**解决**：重新登录获取新 token。

### 10.3 WebSocket 连接失败

```
ws.onerror 触发 → "连接失败"
```

**排查步骤**：

1. 确认后端已启动：`python web_run.py`
2. 确认端口正确：WebSocket URL 中端口是否与后端一致
3. 检查 URL 格式：`ws://localhost:8080/ws/{chat_id}?token={jwt}`
4. 检查 Docker Desktop 是否运行（Sandbox 创建依赖 Docker）

### 10.4 Agent 执行失败

Agent 执行中出错时，WebSocket 会推送 `{"type": "error", "message": "..."}`。

**常见原因**：

- LLM API 密钥不对 → 检查 `config.toml` 的 `[llm]` 段
- LLM API 不可达 → 检查网络、API 地址
- Docker Sandbox 创建失败 → 检查 Docker Desktop、镜像是否存在
- 命令执行超时 → 默认 300s，复杂任务可能需要更长时间

### 10.5 Docker 容器不回收

如果异常导致 Sandbox 容器未自动清理：

```bash
# 列出所有 OpenManus Sandbox 容器
docker ps -a --filter "name=sandbox_u" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

# 手动删除特定容器
docker rm -f sandbox_u1_c42_a1b2c3d4

# 批量删除所有已停止的
docker container prune --filter "name=sandbox_u" -f
```

### 10.6 端口被占用

```
ERROR: [Errno 10048] address already in use
```

```powershell
# Windows: 查看谁占用了 8080
netstat -ano | findstr :8080

# 杀死占用进程（替换 PID）
taskkill /F /PID 12345
```

### 10.7 前端页面空白

访问 `http://localhost:8080` 看到 JSON `{"message": "OpenManus Web API", "note": "前端尚未构建"...}`

**原因**：`web_ui/dist/` 目录不存在或为空。
**解决**：

```powershell
cd web_ui
npm install
npm run build
cd ..
# 重新启动 python web_run.py
```

### 10.8 重新开始

如果想完全重置环境：

```powershell
# 1. 清空数据库（谨慎！会丢失所有数据）
# 在 MySQL 中执行：
# DROP DATABASE openmanus_web;
# CREATE DATABASE openmanus_web CHARACTER SET utf8mb4;
# 重新执行第 3 节的建表 SQL

# 2. 清空用户文件
Remove-Item -Recurse -Force C:\Data\openmanus\users\*

# 3. 清理 Docker 容器
docker ps -a --filter "name=sandbox_u" -q | ForEach { docker rm -f $_ }

# 4. 重启服务
python web_run.py
```

---

## 附录 A：常用命令速查

```powershell
# ── 启动 ──
python web_run.py                                        # 启动后端
cd web_ui && npm run dev                                 # 启动前端 dev server

# ── 测试 ──
pytest tests/web/ -v                                     # 全部 Web 测试
pytest tests/web/test_config.py -v                       # 仅配置测试（无需数据库）
pytest tests/web/test_auth_service.py -v                 # 仅认证服务测试（无需数据库）

# ── 验证 ──
curl http://localhost:8080/                              # REST 根路径
curl http://localhost:8080/docs                          # Swagger API 文档
python -c "from app.web.server import app; print('OK')"  # 导入验证

# ── Docker ──
docker ps --filter "name=sandbox_u"                      # 查看 Sandbox 容器
docker pull python:3.12-slim                             # 拉取镜像
docker system prune -a                                    # 全面清理（谨慎）

# ── 数据库 ──
# 查看用户：SELECT id, username, created_at FROM openmanus_web.users;
# 查看活跃会话：SELECT id, user_id, agent_type, title FROM openmanus_web.chats WHERE status='active';
# 消息数：SELECT chat_id, COUNT(*) FROM openmanus_web.messages GROUP BY chat_id;

# ── Git ──
git log --oneline -5                                     # 最近提交
git status                                               # 当前变更
```

## 附录 B：目录权限参考（Linux）

```bash
# 项目目录
sudo chown -R openmanus:openmanus /opt/OpenManus

# 用户数据目录
sudo mkdir -p /data/openmanus
sudo chown -R openmanus:openmanus /data/openmanus

# Docker socket（允许非 root 用户操作 Docker）
sudo usermod -aG docker openmanus
# 重新登录后生效
```

## 附录 C：环境变量扩展（可选）

当前版本主要使用 `config.toml` 配置。如果需要通过环境变量覆盖（例如 Docket 部署、CI/CD），可在 `app/config.py` 的 `WebSettings` 中使用 `Field(default_factory=...)` 模式扩展，从 `os.environ` 读取回退值。

---

> **维护者**：如果你在运维过程中发现了新问题或解决了新故障，请在本文档的对应章节中补充你的经验，帮助后续的维护者。
