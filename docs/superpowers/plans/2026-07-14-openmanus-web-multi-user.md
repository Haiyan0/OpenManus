# OpenManus 多用户 Web 服务实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 `feat/web-chat` 分支上的单用户 Web 聊天原型扩展为多用户 Web 服务，支持独立账号、多 Agent 类型路由（Manus/DataAnalysis）、MySQL 持久化、Docker Sandbox 用户隔离、Vue 3 前端。

**Architecture:** FastAPI 单进程后端 + Vue 3 SPA 前端 + MySQL 云端数据库 + Docker Sandbox（每用户每会话独立容器，文件挂载到宿主机隔离目录）。JWT 无状态认证贯穿 REST 和 WebSocket。会话（Chat）作为解耦用户与 Agent 的中间层。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, aiomysql, PyJWT, passlib[bcrypt], docker SDK, Vue 3 + Vite + Pinia + Vue Router 4 + Tailwind CSS + axios + marked.js。

## Global Constraints

- Python 版本：3.12（conda 环境 `open_manus`）
- 开发环境：Windows 11 + Docker Desktop；生产环境：Linux + Docker Engine
- 路径统一使用 `pathlib.Path`，代码里全部用 `/`，禁止硬编码 `\`
- MySQL 使用云端实例，连接参数通过 `config.toml` 的 `[web]` 段读取
- 现有目录不动：`app/agent/`、`app/sandbox/`、`app/tool/`、`app/flow/` 严格禁止修改（仅可 import）
- 现有事件流格式保留：`step_start`/`thinking`/`tool_start`/`tool_end`/`assistant`/`done`/`error` 七种事件类型的 JSON schema 与 `app/web/agent_runner.py` 现有实现完全一致
- 前端构建产物路径：`web_ui/dist/`，服务器通过 FastAPI StaticFiles 挂载
- 测试框架：pytest + pytest-asyncio（已在 requirements.txt）
- 所有新代码模块的 docstring 用简体中文
- 提交信息用简体中文，格式 `<type>(<scope>): <描述>`
- 所有异步 Agent 执行必须放进 `asyncio.create_task`，禁止阻塞主 event loop
- Sandbox 容器命名规范：`sandbox_user{user_id}_chat{chat_id}_{8位hex}`

---

## 阶段总览

| 阶段 | 任务范围 | 完成后可验证的能力 |
|------|---------|--------------------|
| **阶段 A**：基础设施 | Task 1-3 | 数据库连通、Web 配置可读、依赖安装 |
| **阶段 B**：认证 | Task 4-5 | 可通过 REST 注册、登录、拿到 JWT |
| **阶段 C**：会话 CRUD | Task 6-7 | 可创建、查询、删除会话 |
| **阶段 D**：Sandbox 隔离 | Task 8-9 | 每会话独立容器 + 隔离目录 |
| **阶段 E**：Agent 路由 + WebSocket | Task 10-12 | 通过 WebSocket 与指定 Agent 对话，事件流回推 |
| **阶段 F**：文件管理 | Task 13 | 上传/下载/删除文件 |
| **阶段 G**：Vue 前端 | Task 14-18 | 完整浏览器端交互 |
| **阶段 H**：集成与部署 | Task 19-20 | 端到端验证 + systemd 部署脚本 |

---

## 阶段 A：基础设施

### Task 1：新增 Web 依赖 + config.toml 扩展

**Files:**
- Modify: `requirements.txt` (末尾追加)
- Modify: `config/config.example.toml` (末尾追加 `[web]` 段)
- Modify: `config/config.toml` (末尾追加 `[web]` 段，如已存在则跳过)

**Interfaces:**
- Consumes: 无
- Produces: 后续任务可以 `pip install` 后 import `aiomysql`、`sqlalchemy`、`passlib`、`jwt`

- [ ] **Step 1：追加 requirements 依赖行**

编辑 `requirements.txt`，在文件末尾追加：

```
# Web 多用户服务依赖
aiomysql~=0.2.0
sqlalchemy[asyncio]~=2.0.36
passlib[bcrypt]~=1.7.4
PyJWT~=2.10.1
python-multipart~=0.0.20
```

> 注：`python-multipart` 用于 FastAPI 处理 multipart/form-data（文件上传）。

- [ ] **Step 2：安装依赖**

Run:
```powershell
pip install aiomysql~=0.2.0 "sqlalchemy[asyncio]~=2.0.36" "passlib[bcrypt]~=1.7.4" PyJWT~=2.10.1 python-multipart~=0.0.20
```

Expected: 全部成功安装，无红色 error 输出。

- [ ] **Step 3：追加 config.example.toml 的 [web] 段**

在 `config/config.example.toml` 末尾追加：

```toml
# Web 多用户服务配置
[web]
mysql_host = "your-cloud-mysql-host"
mysql_port = 3306
mysql_user = "openmanus"
mysql_password = "your-password"
mysql_database = "openmanus_web"

jwt_secret_key = "please-change-me-to-random-string-in-production"
jwt_expire_hours = 24

sandbox_data_root = "C:/Data/openmanus"
static_dir = "web_ui/dist"
```

- [ ] **Step 4：追加 config.toml 的 [web] 段并填入真实值**

在 `config/config.toml` 末尾追加同样结构，把 `mysql_host` / `mysql_password` / `jwt_secret_key` 填成你的实际值。

- [ ] **Step 5：提交**

```powershell
git add requirements.txt config/config.example.toml
git commit -m "chore(web): 新增多用户 Web 服务依赖与配置模板"
```

---

### Task 2：扩展 Config 类支持 [web] 段

**Files:**
- Modify: `app/config.py` (在 `SandboxSettings` 之后插入 `WebSettings`，在 `AppConfig` 添加 `web_config` 字段，在 `_load_initial_config` 里解析 `[web]`)
- Create: `tests/web/__init__.py` (空文件)
- Create: `tests/web/test_config.py`

**Interfaces:**
- Consumes: `requirements.txt` 已安装 `sqlalchemy`
- Produces:
  ```python
  from app.config import config
  config.web                     # -> WebSettings 实例
  config.web.mysql_host          # str
  config.web.mysql_port          # int
  config.web.mysql_user          # str
  config.web.mysql_password      # str
  config.web.mysql_database      # str
  config.web.jwt_secret_key      # str
  config.web.jwt_expire_hours    # int
  config.web.sandbox_data_root   # pathlib.Path
  config.web.static_dir          # pathlib.Path
  config.web.mysql_url           # str, SQLAlchemy 异步连接 URL
  ```

- [ ] **Step 1：创建测试目录与失败测试**

创建 `tests/web/__init__.py`（空）。

创建 `tests/web/test_config.py`：

```python
"""测试 Web 配置加载。"""
from pathlib import Path

from app.config import config


def test_web_config_exists():
    """config.web 应返回 WebSettings 实例。"""
    assert config.web is not None
    assert hasattr(config.web, "mysql_host")


def test_web_config_types():
    """字段类型应正确。"""
    assert isinstance(config.web.mysql_host, str)
    assert isinstance(config.web.mysql_port, int)
    assert isinstance(config.web.jwt_expire_hours, int)
    assert isinstance(config.web.sandbox_data_root, Path)
    assert isinstance(config.web.static_dir, Path)


def test_mysql_url_format():
    """mysql_url 应为 SQLAlchemy 异步兼容格式。"""
    url = config.web.mysql_url
    assert url.startswith("mysql+aiomysql://")
    assert config.web.mysql_user in url
    assert config.web.mysql_database in url
```

- [ ] **Step 2：运行测试确认失败**

Run: `pytest tests/web/test_config.py -v`
Expected: FAIL，报错 `AttributeError: 'Config' object has no attribute 'web'`

- [ ] **Step 3：在 app/config.py 添加 WebSettings**

在 `app/config.py` 里 `SandboxSettings` 类之后插入：

```python
class WebSettings(BaseModel):
    """Web 多用户服务配置。"""

    mysql_host: str = Field(..., description="MySQL 主机地址")
    mysql_port: int = Field(3306, description="MySQL 端口")
    mysql_user: str = Field(..., description="MySQL 用户名")
    mysql_password: str = Field(..., description="MySQL 密码")
    mysql_database: str = Field(..., description="MySQL 数据库名")

    jwt_secret_key: str = Field(..., description="JWT 签名密钥")
    jwt_expire_hours: int = Field(24, description="JWT 有效期（小时）")

    sandbox_data_root: Path = Field(
        default=Path("C:/Data/openmanus"),
        description="用户数据根目录（sandbox 挂载点）",
    )
    static_dir: Path = Field(
        default=Path("web_ui/dist"),
        description="前端静态文件目录（相对项目根）",
    )

    @property
    def mysql_url(self) -> str:
        """拼装 SQLAlchemy 异步 MySQL 连接串。"""
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )
```

- [ ] **Step 4：在 AppConfig 添加 web_config 字段**

在 `app/config.py` 的 `AppConfig` 类里添加：

```python
    web_config: Optional[WebSettings] = Field(None, description="Web 服务配置")
```

- [ ] **Step 5：在 _load_initial_config 解析 [web]**

在 `_load_initial_config` 方法末尾（`daytona_settings = DaytonaSettings()` 附近）加入：

```python
        web_config_raw = raw_config.get("web", {})
        web_settings = WebSettings(**web_config_raw) if web_config_raw else None
```

并在最下方的 `config_dict = {...}` 里加入：

```python
            "web_config": web_settings,
```

- [ ] **Step 6：添加 config.web 属性访问器**

在 `Config` 类里（`workspace_root` 属性上方）加入：

```python
    @property
    def web(self) -> WebSettings:
        """获取 Web 服务配置。"""
        if self._config.web_config is None:
            raise RuntimeError(
                "Web 配置未找到，请在 config.toml 中添加 [web] 段"
            )
        return self._config.web_config
```

- [ ] **Step 7：运行测试验证通过**

Run: `pytest tests/web/test_config.py -v`
Expected: 3 passed

- [ ] **Step 8：提交**

```powershell
git add app/config.py tests/web/__init__.py tests/web/test_config.py
git commit -m "feat(web): 扩展 Config 支持 [web] 段配置"
```

---

### Task 3：SQLAlchemy 异步数据库引擎 + 连接冒烟测试

**Files:**
- Create: `app/web/database.py`
- Create: `tests/web/test_database.py`
- Create: `pytest.ini`（如已存在则修改）

**Interfaces:**
- Consumes: `config.web.mysql_url`（来自 Task 2）
- Produces:
  ```python
  from app.web.database import Base, engine, AsyncSessionLocal, get_db
  # Base: 所有 ORM 模型的基类 (DeclarativeBase 子类)
  # engine: AsyncEngine 实例
  # AsyncSessionLocal: async_sessionmaker[AsyncSession]
  # get_db(): async generator, yields AsyncSession
  ```

- [ ] **Step 1：写失败测试**

创建 `tests/web/test_database.py`：

```python
"""数据库连接冒烟测试。

要求 config.toml [web] 段填了真实凭据且 MySQL 可达，
且目标数据库已创建（CREATE DATABASE openmanus_web CHARACTER SET utf8mb4）。
"""
import pytest
from sqlalchemy import text

from app.web.database import AsyncSessionLocal, engine


@pytest.mark.asyncio
async def test_engine_can_connect():
    """引擎应能建立到 MySQL 的实际连接。"""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_session_lifecycle():
    """AsyncSessionLocal 应能创建 session 并成功查询。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 2 + 3"))
        assert result.scalar() == 5
```

- [ ] **Step 2：运行测试确认失败**

Run: `pytest tests/web/test_database.py -v`
Expected: FAIL，报错 `ModuleNotFoundError: No module named 'app.web.database'`

- [ ] **Step 3：创建 app/web/database.py**

```python
"""SQLAlchemy 2.0 异步引擎、Session 工厂、FastAPI 依赖注入。"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import config


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


engine = create_async_engine(
    config.web.mysql_url,
    echo=False,
    pool_pre_ping=True,   # 自动检测断开的连接
    pool_recycle=3600,    # 每小时回收一次连接（避免云端超时）
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 用的异步 session 生成器。

    使用方式:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 4：确保 pytest-asyncio 使用 auto 模式**

检查项目根有无 `pytest.ini` 或 `pyproject.toml` 里的 `[tool.pytest.ini_options]`。如果没有，创建 `pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5：运行测试验证通过**

Run: `pytest tests/web/test_database.py -v`
Expected: 2 passed

> 若失败，检查：(1) MySQL 是否可达；(2) `config.toml [web]` 凭据是否正确；(3) 数据库 `openmanus_web` 是否已在云端创建（如未创建，需先手动 `CREATE DATABASE openmanus_web CHARACTER SET utf8mb4;`）。

- [ ] **Step 6：提交**

```powershell
git add app/web/database.py tests/web/test_database.py pytest.ini
git commit -m "feat(web): 添加 SQLAlchemy 异步引擎与 session 工厂"
```

---

## 阶段 B：认证

### Task 4：User 模型 + 认证服务（密码哈希 + JWT）

**Files:**
- Create: `app/web/auth/__init__.py` (空文件)
- Create: `app/web/auth/models.py`
- Create: `app/web/auth/service.py`
- Create: `tests/web/test_auth_service.py`

**Interfaces:**
- Consumes: `Base` (from `app.web.database`), `config.web.jwt_secret_key`, `config.web.jwt_expire_hours`
- Produces:
  ```python
  from app.web.auth.models import User
  # ORM 模型: id, username, password_hash, created_at

  from app.web.auth.service import (
      hash_password, verify_password,
      create_access_token, decode_access_token,
  )
  hash_password(plain: str) -> str
  verify_password(plain: str, hashed: str) -> bool
  create_access_token(user_id: int, username: str) -> str
  decode_access_token(token: str) -> dict  # {"user_id": int, "username": str, "exp": int}
                                            # 无效时抛 jwt.PyJWTError 子类
  ```

- [ ] **Step 1：创建目录与失败测试**

创建 `app/web/auth/__init__.py`（空）。

创建 `tests/web/test_auth_service.py`：

```python
"""认证服务：密码哈希与 JWT。"""
import pytest

from app.web.auth.service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    """密码哈希后可正确验证。"""
    plain = "my_secret_password"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_roundtrip():
    """JWT 签发后可解码。"""
    token = create_access_token(user_id=42, username="alice")
    payload = decode_access_token(token)
    assert payload["user_id"] == 42
    assert payload["username"] == "alice"
    assert "exp" in payload


def test_invalid_token_raises():
    """无效 token 应抛 jwt 异常。"""
    import jwt as pyjwt

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token("not.a.valid.token")
```

- [ ] **Step 2：运行确认失败**

Run: `pytest tests/web/test_auth_service.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.web.auth'`

- [ ] **Step 3：创建 User 模型**

`app/web/auth/models.py`:

```python
"""用户 ORM 模型。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.web.database import Base


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
```

- [ ] **Step 4：创建认证服务**

`app/web/auth/service.py`:

```python
"""密码哈希 + JWT 签发/验证服务。"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from passlib.context import CryptContext

from app.config import config


# bcrypt 上下文，deprecated="auto" 让 passlib 处理过期哈希算法
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """将明文密码哈希为 bcrypt 字符串。"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return _pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str) -> str:
    """签发 JWT access token。"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": now + timedelta(hours=config.web.jwt_expire_hours),
        "iat": now,
    }
    return pyjwt.encode(
        payload,
        config.web.jwt_secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并校验 JWT。无效时抛 pyjwt.PyJWTError。"""
    return pyjwt.decode(
        token,
        config.web.jwt_secret_key,
        algorithms=["HS256"],
    )
```

- [ ] **Step 5：手动建表（首次）**

在云端 MySQL 上执行：

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 6：运行测试验证通过**

Run: `pytest tests/web/test_auth_service.py -v`
Expected: 3 passed

- [ ] **Step 7：提交**

```powershell
git add app/web/auth/ tests/web/test_auth_service.py
git commit -m "feat(auth): User 模型 + 密码哈希 + JWT 服务"
```

---

### Task 5：认证 REST 路由（注册/登录）+ FastAPI 依赖

**Files:**
- Create: `app/web/auth/schemas.py`
- Create: `app/web/auth/router.py`
- Create: `app/web/dependencies.py`
- Create: `tests/web/test_auth_router.py`
- Modify: `app/web/server.py`（挂载 auth 路由）

**Interfaces:**
- Consumes: `User`, `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `get_db`
- Produces:
  ```python
  # HTTP:
  # POST /api/auth/register  {username, password} -> {id, username, access_token}
  # POST /api/auth/login     {username, password} -> {id, username, access_token}

  # FastAPI 依赖:
  from app.web.dependencies import get_current_user
  # get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) -> User
  # 无效或缺失时抛 HTTPException(401)
  ```

- [ ] **Step 1：写失败测试**

创建 `tests/web/test_auth_router.py`：

```python
"""注册与登录 API 端到端测试。"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.server import app


@pytest.fixture
def unique_username() -> str:
    """每次测试用唯一用户名，避免污染数据库。"""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_register_returns_token(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["username"] == unique_username
        assert "access_token" in data
        assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_fails(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_flow(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/login",
            json={"username": unique_username, "password": "pw123456"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(unique_username):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/api/auth/register",
            json={"username": unique_username, "password": "pw123456"},
        )
        resp = await ac.post(
            "/api/auth/login",
            json={"username": unique_username, "password": "wrong_pw"},
        )
        assert resp.status_code == 401
```

- [ ] **Step 2：运行确认失败**

Run: `pytest tests/web/test_auth_router.py -v`
Expected: FAIL, 404 或 ModuleNotFoundError

- [ ] **Step 3：创建请求/响应 schemas**

`app/web/auth/schemas.py`:

```python
"""注册/登录请求响应模型。"""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    id: int
    username: str
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 4：创建 auth 路由**

`app/web/auth/router.py`:

```python
"""认证 REST 路由: /api/auth/*"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.auth.models import User
from app.web.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.web.auth.service import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.web.database import get_db


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """注册新用户。用户名重复时返回 400。"""
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username)
    return AuthResponse(id=user.id, username=user.username, access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """登录，密码错或用户不存在均返回 401。"""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(user_id=user.id, username=user.username)
    return AuthResponse(id=user.id, username=user.username, access_token=token)
```

- [ ] **Step 5：创建 get_current_user 依赖**

`app/web/dependencies.py`:

```python
"""FastAPI 依赖注入: 认证用户等。"""
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.auth.models import User
from app.web.auth.service import decode_access_token
from app.web.database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Authorization Header 提取 JWT，返回对应 User。"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺失认证 token",
        )
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 token",
        )

    result = await db.execute(select(User).where(User.id == payload["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user
```

- [ ] **Step 6：修改 app/web/server.py 挂载 auth 路由**

用以下内容 **完全替换** `app/web/server.py`（保留原 WebSocket 端点将在 Task 12 重写）：

```python
"""FastAPI 服务器 — OpenManus 多用户 Web 后端。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.web.auth.router import router as auth_router


app = FastAPI(title="OpenManus Web", version="0.2.0")

app.include_router(auth_router)

# 静态资源（暂保留旧的单页原型，Vue 前端将在 Task 14+ 替换）
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """返回临时首页。Vue 前端就绪后将替换。"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "OpenManus Web API. See /docs for API 文档。"}
```

- [ ] **Step 7：安装 httpx 测试客户端（若未安装）**

```powershell
pip install "httpx>=0.28"
```

- [ ] **Step 8：运行测试验证通过**

Run: `pytest tests/web/test_auth_router.py -v`
Expected: 4 passed

- [ ] **Step 9：提交**

```powershell
git add app/web/auth/schemas.py app/web/auth/router.py app/web/dependencies.py app/web/server.py tests/web/test_auth_router.py
git commit -m "feat(auth): 注册/登录 REST 路由 + get_current_user 依赖"
```

---

## 阶段 C：会话 CRUD

### Task 6：Chat + Message ORM 模型

**Files:**
- Create: `app/web/chat/__init__.py` (空文件)
- Create: `app/web/chat/models.py`
- Create: `tests/web/test_chat_models.py`

**Interfaces:**
- Consumes: `Base` (from `app.web.database`), `User` (from `app.web.auth.models`)
- Produces:
  ```python
  from app.web.chat.models import Chat, Message

  # Chat 字段:
  #   id: int, user_id: int, title: str, agent_type: str,
  #   sandbox_id: str | None, status: str,
  #   created_at: datetime, updated_at: datetime
  #   AGENT_TYPES = {"general", "data_analysis"}

  # Message 字段:
  #   id: int, chat_id: int, role: str, content: str | None,
  #   tool_name: str | None, tool_args: dict | None,
  #   event_type: str | None, extra_data: dict | None,
  #   created_at: datetime
  ```

> 注：SQLAlchemy 保留了 `metadata` 属性，所以设计文档里的 `metadata` 字段在 Python 侧命名为 `extra_data`，数据库列名可保持 `metadata` 或改为 `extra_data`（本计划用 `extra_data` 以避免混淆）。

- [ ] **Step 1：写失败测试**

`tests/web/test_chat_models.py`:

```python
"""Chat / Message ORM 模型 CRUD 冒烟测试。"""
import uuid

import pytest
from sqlalchemy import select

from app.web.auth.models import User
from app.web.auth.service import hash_password
from app.web.chat.models import Chat, Message
from app.web.database import AsyncSessionLocal


@pytest.fixture
async def user():
    """在数据库中创建一个测试用户并返回。"""
    async with AsyncSessionLocal() as db:
        u = User(
            username=f"chatuser_{uuid.uuid4().hex[:8]}",
            password_hash=hash_password("pw"),
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        yield u


@pytest.mark.asyncio
async def test_chat_crud(user):
    async with AsyncSessionLocal() as db:
        chat = Chat(user_id=user.id, title="测试会话", agent_type="general")
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
        assert chat.id > 0
        assert chat.status == "active"


@pytest.mark.asyncio
async def test_message_belongs_to_chat(user):
    async with AsyncSessionLocal() as db:
        chat = Chat(user_id=user.id, agent_type="data_analysis")
        db.add(chat)
        await db.commit()
        await db.refresh(chat)

        msg = Message(
            chat_id=chat.id,
            role="user",
            content="帮我分析",
            event_type=None,
        )
        db.add(msg)
        await db.commit()

        result = await db.execute(
            select(Message).where(Message.chat_id == chat.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].content == "帮我分析"
```

- [ ] **Step 2：运行确认失败**

Run: `pytest tests/web/test_chat_models.py -v`
Expected: FAIL, ModuleNotFoundError

- [ ] **Step 3：创建 Chat / Message 模型**

`app/web/chat/models.py`:

```python
"""聊天会话与消息 ORM 模型。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.web.database import Base


AGENT_TYPES = {"general", "data_analysis"}
CHAT_STATUS = {"active", "archived"}


class Chat(Base):
    """会话表。每个用户可以有多个会话，每会话绑定一种 Agent 类型。"""

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新会话")
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    sandbox_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class Message(Base):
    """会话消息表。存储 user/assistant/tool/system 各类消息。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
```

- [ ] **Step 4：手动建表**

在 MySQL 上执行：

```sql
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
);

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
);
```

- [ ] **Step 5：运行测试验证通过**

Run: `pytest tests/web/test_chat_models.py -v`
Expected: 2 passed

- [ ] **Step 6：提交**

```powershell
git add app/web/chat/__init__.py app/web/chat/models.py tests/web/test_chat_models.py
git commit -m "feat(chat): Chat 与 Message ORM 模型"
```

---

### Task 7：会话 CRUD REST 路由

**Files:**
- Create: `app/web/chat/schemas.py`
- Create: `app/web/chat/service.py`
- Create: `app/web/chat/router.py`
- Create: `tests/web/test_chat_router.py`
- Modify: `app/web/server.py`（挂载 chat 路由）

**Interfaces:**
- Consumes: `Chat`, `Message`, `AGENT_TYPES`, `get_current_user`, `get_db`
- Produces:
  ```python
  # HTTP:
  # GET    /api/chats                    -> List[ChatOut]
  # POST   /api/chats  {agent_type, title?} -> ChatOut
  # GET    /api/chats/{id}               -> ChatDetail (含最近 50 条消息)
  # DELETE /api/chats/{id}               -> {"ok": true}
  # GET    /api/chats/{id}/messages?before_id=&limit=50 -> List[MessageOut]

  # Python service (供 WebSocket 层复用):
  from app.web.chat.service import (
      create_chat, get_user_chats, get_chat_or_404,
      delete_chat, list_messages, save_message,
  )
  create_chat(db, user_id: int, agent_type: str, title: str | None) -> Chat
  get_chat_or_404(db, chat_id: int, user_id: int) -> Chat
  save_message(db, chat_id: int, role: str, content: str | None,
               event_type: str | None = None,
               tool_name: str | None = None,
               tool_args: dict | None = None,
               extra_data: dict | None = None) -> Message
  ```

- [ ] **Step 1：写失败测试**

`tests/web/test_chat_router.py`:

```python
"""会话 CRUD REST 端到端测试。"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.server import app


async def _register_and_get_token(ac: AsyncClient) -> tuple[str, int]:
    username = f"chatapi_{uuid.uuid4().hex[:8]}"
    resp = await ac.post(
        "/api/auth/register",
        json={"username": username, "password": "pw123456"},
    )
    body = resp.json()
    return body["access_token"], body["id"]


@pytest.mark.asyncio
async def test_create_and_list_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 创建
        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "data_analysis", "title": "分析报告"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        chat = resp.json()
        assert chat["agent_type"] == "data_analysis"
        assert chat["title"] == "分析报告"
        chat_id = chat["id"]

        # 列表
        resp = await ac.get("/api/chats", headers=headers)
        assert resp.status_code == 200
        chats = resp.json()
        assert any(c["id"] == chat_id for c in chats)


@pytest.mark.asyncio
async def test_create_chat_invalid_agent_type():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "not_a_real_agent"},
            headers=headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats", json={"agent_type": "general"}, headers=headers
        )
        chat_id = resp.json()["id"]

        resp = await ac.delete(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 200

        resp = await ac.get(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_access_others_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token_a, _ = await _register_and_get_token(ac)
        token_b, _ = await _register_and_get_token(ac)

        # A 创建
        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "general"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        chat_id = resp.json()["id"]

        # B 访问，应 404（不暴露资源存在与否）
        resp = await ac.get(
            f"/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/chats")
        assert resp.status_code == 401
```

- [ ] **Step 2：运行确认失败**

Run: `pytest tests/web/test_chat_router.py -v`
Expected: FAIL

- [ ] **Step 3：创建 chat schemas**

`app/web/chat/schemas.py`:

```python
"""会话与消息的请求/响应模型。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    agent_type: str = Field(..., description="general | data_analysis")
    title: str | None = Field(None, max_length=200)


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    agent_type: str
    sandbox_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str | None
    tool_name: str | None
    tool_args: dict[str, Any] | None
    event_type: str | None
    extra_data: dict[str, Any] | None
    created_at: datetime


class ChatDetail(ChatOut):
    messages: list[MessageOut] = []
```

- [ ] **Step 4：创建 chat service（供 router 与 WebSocket 复用）**

`app/web/chat/service.py`:

```python
"""会话与消息业务逻辑。"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.chat.models import AGENT_TYPES, Chat, Message


async def create_chat(
    db: AsyncSession,
    user_id: int,
    agent_type: str,
    title: str | None = None,
) -> Chat:
    """创建新会话。agent_type 非法时抛 400。"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"agent_type 必须是 {sorted(AGENT_TYPES)} 之一",
        )
    chat = Chat(
        user_id=user_id,
        agent_type=agent_type,
        title=title or "新会话",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def get_user_chats(db: AsyncSession, user_id: int) -> list[Chat]:
    """按更新时间倒序返回用户的所有活跃会话。"""
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user_id, Chat.status == "active")
        .order_by(desc(Chat.updated_at))
    )
    return list(result.scalars().all())


async def get_chat_or_404(
    db: AsyncSession, chat_id: int, user_id: int
) -> Chat:
    """获取指定会话，会话不存在或不属于该用户时抛 404。"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()
    if chat is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return chat


async def delete_chat(db: AsyncSession, chat: Chat) -> None:
    """删除会话（级联删除 messages）。"""
    await db.delete(chat)
    await db.commit()


async def list_messages(
    db: AsyncSession,
    chat_id: int,
    before_id: int | None = None,
    limit: int = 50,
) -> list[Message]:
    """按 id 倒序分页返回消息，用于历史加载。"""
    query = select(Message).where(Message.chat_id == chat_id)
    if before_id is not None:
        query = query.where(Message.id < before_id)
    query = query.order_by(desc(Message.id)).limit(limit)

    result = await db.execute(query)
    rows = list(result.scalars().all())
    return list(reversed(rows))  # 返回给前端时按时间正序


async def save_message(
    db: AsyncSession,
    chat_id: int,
    role: str,
    content: str | None,
    event_type: str | None = None,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> Message:
    """持久化一条消息并返回。"""
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        event_type=event_type,
        tool_name=tool_name,
        tool_args=tool_args,
        extra_data=extra_data,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
```

- [ ] **Step 5：创建 chat router**

`app/web/chat/router.py`:

```python
"""会话 CRUD 路由: /api/chats/*"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.web.auth.models import User
from app.web.chat.schemas import ChatCreate, ChatDetail, ChatOut, MessageOut
from app.web.chat.service import (
    create_chat,
    delete_chat,
    get_chat_or_404,
    get_user_chats,
    list_messages,
)
from app.web.database import get_db
from app.web.dependencies import get_current_user


router = APIRouter(prefix="/api/chats", tags=["chat"])


@router.get("", response_model=list[ChatOut])
async def api_list_chats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatOut]:
    chats = await get_user_chats(db, user.id)
    return [ChatOut.model_validate(c) for c in chats]


@router.post("", response_model=ChatOut)
async def api_create_chat(
    payload: ChatCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await create_chat(db, user.id, payload.agent_type, payload.title)
    return ChatOut.model_validate(chat)


@router.get("/{chat_id}", response_model=ChatDetail)
async def api_get_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatDetail:
    chat = await get_chat_or_404(db, chat_id, user.id)
    msgs = await list_messages(db, chat_id, limit=50)
    detail = ChatDetail.model_validate(chat)
    detail.messages = [MessageOut.model_validate(m) for m in msgs]
    return detail


@router.delete("/{chat_id}")
async def api_delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chat = await get_chat_or_404(db, chat_id, user.id)
    # 注意：Sandbox 清理将在 Task 9 中接入
    await delete_chat(db, chat)
    return {"ok": True}


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def api_list_messages(
    chat_id: int,
    before_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await get_chat_or_404(db, chat_id, user.id)   # 权限校验
    msgs = await list_messages(db, chat_id, before_id=before_id, limit=limit)
    return [MessageOut.model_validate(m) for m in msgs]
```

- [ ] **Step 6：修改 app/web/server.py 挂载 chat 路由**

在 `app.include_router(auth_router)` 之后添加：

```python
from app.web.chat.router import router as chat_router

app.include_router(chat_router)
```

- [ ] **Step 7：运行测试验证通过**

Run: `pytest tests/web/test_chat_router.py -v`
Expected: 5 passed

- [ ] **Step 8：提交**

```powershell
git add app/web/chat/schemas.py app/web/chat/service.py app/web/chat/router.py app/web/server.py tests/web/test_chat_router.py
git commit -m "feat(chat): 会话 CRUD REST 路由 + service 层"
```

---

## 阶段 D：Sandbox 隔离

### Task 8：用户目录管理 + Sandbox 创建/销毁服务

**Files:**
- Create: `app/web/sandbox/__init__.py` (空文件)
- Create: `app/web/sandbox/service.py`
- Create: `tests/web/test_sandbox_service.py`

**Interfaces:**
- Consumes: `config.web.sandbox_data_root`, `DockerSandbox`, `SandboxSettings`
- Produces:
  ```python
  from app.web.sandbox.service import (
      ensure_user_directories,
      create_session_sandbox,
      destroy_session_sandbox,
      get_sandbox_for_chat,
  )
  ensure_user_directories(user_id: int, chat_id: int) -> tuple[Path, Path]
  #    返回 (host_workspace_dir, container_workspace_dir="/workspace")
  #    host 目录: {sandbox_data_root}/users/{user_id}/workspace/{chat_id}/
  create_session_sandbox(user_id: int, chat_id: int, network_enabled: bool) -> DockerSandbox
  destroy_session_sandbox(sandbox: DockerSandbox, chat_id: int) -> None
  get_sandbox_for_chat(user_id: int, chat_id: int) -> DockerSandbox | None
  ```

> **关键兼容性说明**: Docker Desktop for Windows 中，挂载路径必须用 Windows 绝对路径格式（`C:\Data\...`）。在 `_prepare_volume_bindings` 中需确保路径存在。Python `pathlib` 和 `os.makedirs` 跨平台。

- [ ] **Step 1：安装 docker SDK（确认已有）**

```powershell
pip list | findstr docker
```

Expected: `docker` 已安装（requirements.txt 中 `docker~=7.1.0`）

- [ ] **Step 2：写失败测试**

创建 `tests/web/test_sandbox_service.py`：

```python
"""Sandbox 目录创建与清理测试。

注意：这些测试需要 Docker Desktop 运行。
仅测试文件系统层面，不实际启动容器。
"""
import shutil

from app.config import config
from app.web.sandbox.service import ensure_user_directories


def test_ensure_user_directories_creates_paths():
    """应创建正确的目录结构。"""
    host_dir, container_dir = ensure_user_directories(user_id=1, chat_id=42)

    assert host_dir.exists()
    assert str(container_dir) == "/workspace"
    # 验证目录路径符合预期
    assert str(host_dir).endswith("users/1/workspace/42")

    # 清理
    shutil.rmtree(config.web.sandbox_data_root / "users" / "1", ignore_errors=True)
```

- [ ] **Step 3：运行确认失败**

Run: `pytest tests/web/test_sandbox_service.py -v`
Expected: FAIL, ModuleNotFoundError

- [ ] **Step 4：创建 Sandbox 服务**

`app/web/sandbox/service.py`:

```python
"""Sandbox 生命周期管理：用户目录 + Docker 容器。

每个用户 + 会话拥有独立的：
- 主机目录: <sandbox_data_root>/users/<user_id>/workspace/<chat_id>/
- 容器内路径: /workspace
- 容器名: sandbox_u<user_id>_c<chat_id>_<8位hex>
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import config
from app.sandbox.core.sandbox import DockerSandbox
from app.sandbox.core.exceptions import SandboxError

if TYPE_CHECKING:
    from app.config import SandboxSettings

# 简单的内存字典追踪活跃 sandbox: (user_id, chat_id) -> DockerSandbox
_active_sandboxes: dict[tuple[int, int], DockerSandbox] = {}


def ensure_user_directories(user_id: int, chat_id: int) -> tuple[Path, str]:
    """确保用户 + 会话的隔离目录存在。

    返回:
        (host_workspace, "/workspace")
    """
    host_ws = (
        config.web.sandbox_data_root
        / "users"
        / str(user_id)
        / "workspace"
        / str(chat_id)
    )
    host_ws.mkdir(parents=True, exist_ok=True)
    uploads = config.web.sandbox_data_root / "users" / str(user_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return host_ws, "/workspace"


async def create_session_sandbox(
    user_id: int,
    chat_id: int,
    network_enabled: bool = False,
) -> DockerSandbox:
    """为用户创建一个新的会话 Sandbox。

    Args:
        user_id: 用户 ID
        chat_id: 会话 ID
        network_enabled: 是否开启网络（general agent 需要）

    Returns:
        已就绪的 DockerSandbox 实例

    若已有运行中的 sandbox (同一用户+会话)，先销毁旧的。
    """
    key = (user_id, chat_id)
    if key in _active_sandboxes:
        try:
            await _active_sandboxes[key].cleanup()
        except Exception:
            pass

    host_ws, container_ws = ensure_user_directories(user_id, chat_id)

    # 构建 sandbox 配置
    sandbox_config = SandboxSettings(
        image=config.sandbox.image,
        work_dir=container_ws,
        memory_limit=config.sandbox.memory_limit,
        cpu_limit=config.sandbox.cpu_limit,
        timeout=config.sandbox.timeout,
        network_enabled=network_enabled,
    )

    # 创建并启动容器
    sandbox = DockerSandbox(
        config=sandbox_config,
        volume_bindings={str(host_ws): container_ws},
    )
    await sandbox.create()

    _active_sandboxes[key] = sandbox
    return sandbox


async def destroy_session_sandbox(
    sandbox: DockerSandbox | None,
    user_id: int,
    chat_id: int,
) -> None:
    """销毁 sandbox 容器并清理追踪。"""
    key = (user_id, chat_id)
    if sandbox is not None:
        try:
            await sandbox.cleanup()
        except Exception:
            pass
    _active_sandboxes.pop(key, None)


def get_sandbox_for_chat(user_id: int, chat_id: int) -> DockerSandbox | None:
    """获取指定会话的活跃 sandbox（不创建）。"""
    return _active_sandboxes.get((user_id, chat_id))
```

- [ ] **Step 5：运行测试验证通过**

Run: `pytest tests/web/test_sandbox_service.py -v`
Expected: 1 passed

- [ ] **Step 6：补充 SandboxSettings 的导入兼容性**

检查 `app/config.py` 确认 `SandboxSettings` 在模块顶层可 import。测试中 `from app.config import SandboxSettings` 应可正常导入。

- [ ] **Step 7：提交**

```powershell
git add app/web/sandbox/ tests/web/test_sandbox_service.py
git commit -m "feat(sandbox): 用户目录管理 + Sandbox 创建/销毁服务"
```

---

### Task 9：Sandbox 集成到 Chat 路由

**Files:**
- Modify: `app/web/chat/router.py`（创建/删除会话时联动 Sandbox）
- Modify: `app/web/chat/service.py` 或 `router.py`（删除时调用 destroy）
- Create: `tests/web/test_sandbox_integration.py`

**Interfaces:**
- Consumes: `create_session_sandbox`, `destroy_session_sandbox`, `get_chat_or_404`
- Produces: 创建会话时自动创建 Docker Sandbox（后台），删除会话时自动销毁 Sandbox

- [ ] **Step 1：写失败测试**

`tests/web/test_sandbox_integration.py`:

```python
"""Sandbox 与会话集成的端到端测试。

要求 Docker Desktop 正在运行。
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.chat.models import Chat
from app.web.database import AsyncSessionLocal
from app.web.sandbox.service import get_sandbox_for_chat
from app.web.server import app


@pytest.mark.asyncio
async def test_create_chat_creates_sandbox():
    """新建 general 会话应自动创建网络开启的 Sandbox。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        username = f"sandbox_{uuid.uuid4().hex[:8]}"
        resp = await ac.post(
            "/api/auth/register",
            json={"username": username, "password": "pw123456"},
        )
        token = resp.json()["access_token"]
        user_id = resp.json()["id"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "general"},
            headers=headers,
        )
        assert resp.status_code == 200
        chat_id = resp.json()["id"]

        # 验证 Sandbox 已被创建
        sandbox = get_sandbox_for_chat(user_id, chat_id)
        assert sandbox is not None

        # 验证容器内可以执行命令
        result = await sandbox.run_command("echo hello_sandbox")
        assert "hello_sandbox" in result

        # 删除会话 → Sandbox 应被回收
        resp = await ac.delete(f"/api/chats/{chat_id}", headers=headers)
        assert resp.status_code == 200

        sandbox2 = get_sandbox_for_chat(user_id, chat_id)
        assert sandbox2 is None


@pytest.mark.asyncio
async def test_sandbox_network_policy():
    """general agent 打开网络，data_analysis 关闭网络。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        username = f"sboxnet_{uuid.uuid4().hex[:8]}"
        resp = await ac.post(
            "/api/auth/register",
            json={"username": username, "password": "pw123456"},
        )
        token = resp.json()["access_token"]
        user_id = resp.json()["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # data_analysis → 网络应为关闭
        resp = await ac.post(
            "/api/chats",
            json={"agent_type": "data_analysis"},
            headers=headers,
        )
        chat_id = resp.json()["id"]
        sandbox = get_sandbox_for_chat(user_id, chat_id)
        assert sandbox is not None
        # 简单验证：ping 外网应失败（network_enabled=False）
        try:
            await sandbox.run_command("ping -c 1 8.8.8.8", timeout=5)
            ping_ok = True
        except Exception:
            ping_ok = False
        assert not ping_ok, "network_enabled=False 时不应能访问外网"

        # 清理
        await sandbox.cleanup()
```

- [ ] **Step 2：运行确认失败**

Run: `pytest tests/web/test_sandbox_integration.py -v`
Expected: FAIL（新建会话不会创建 Sandbox）

- [ ] **Step 3：修改 Chat 路由集成 Sandbox**

修改 `app/web/chat/router.py` 的 `api_create_chat` 和 `api_delete_chat`：

```python
# 新增 import
from app.web.sandbox.service import (
    create_session_sandbox,
    destroy_session_sandbox,
)


@router.post("", response_model=ChatOut)
async def api_create_chat(
    payload: ChatCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await create_chat(db, user.id, payload.agent_type, payload.title)

    # 后台创建 Sandbox
    try:
        network = payload.agent_type == "general"
        sandbox = await create_session_sandbox(user.id, chat.id, network_enabled=network)
        chat.sandbox_id = sandbox.container.id if sandbox.container else None
        await db.commit()
    except Exception:
        # Sandbox 创建失败不影响会话创建，会话仍可使用
        pass

    return ChatOut.model_validate(chat)


@router.delete("/{chat_id}")
async def api_delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chat = await get_chat_or_404(db, chat_id, user.id)
    # 清理 Sandbox
    sandbox = get_sandbox_for_chat(user.id, chat_id)
    await destroy_session_sandbox(sandbox, user.id, chat_id)
    await delete_chat(db, chat)
    return {"ok": True}
```

> 注：`get_sandbox_for_chat` 需从 `app/web/sandbox/service` 导入，已在 Task 8 中定义。

- [ ] **Step 4：运行测试验证通过**

Run: `pytest tests/web/test_sandbox_integration.py -v`
Expected: 2 passed

- [ ] **Step 5：提交**

```powershell
git add app/web/chat/router.py tests/web/test_sandbox_integration.py
git commit -m "feat(sandbox): 创建/删除会话联动 Docker Sandbox"
```

---

## 阶段 E：Agent 路由 + WebSocket

### Task 10：重构 agent_runner 支持多 Agent 类型

**Files:**
- Modify: `app/web/agent_runner.py`（完全重写为 Agent 工厂 + 每种类型各自的 Observable 包装）

**Interfaces:**
- Consumes: `Manus`, `DataAnalysis`, `DockerSandbox`, `create_session_sandbox`
- Produces:
  ```python
  from app.web.agent_runner import create_observable_agent, AGENT_FACTORY

  # AGENT_FACTORY: dict[str, callable] = {
  #     "general": lambda: ObservableManus(...),
  #     "data_analysis": lambda: ObservableDataAnalysis(...),
  # }
  # create_observable_agent(agent_type: str,
  #     event_queue: asyncio.Queue,
  #     sandbox: DockerSandbox | None = None
  # ) -> ToolCallAgent
  # 返回设置了 event_queue + sandbox 的 Agent 实例
  ```

> 设计原则：保留原有 `ObservableManus` 的事件发射机制（`_emit`、`step`、`think`、`execute_tool`、`run`），新增 `ObservableDataAnalysis` 以相同方式包裹 `DataAnalysis`。

- [ ] **Step 1：读取现有 agent_runner.py 确认事件契约**

Run:
```powershell
git show HEAD:app/web/agent_runner.py
```

确认当前 `ObservableManus` 实现的 7 种事件类型及其字段格式：
- `step_start`: `{step, max_steps}`
- `thinking`: `{content, tool_calls}`
- `tool_start`: `{tool, args}`
- `tool_end`: `{tool, result, ok}`
- `assistant`: `{content}`
- `done`: `{reason}`
- `error`: `{message}`

新增事件：
- `sandbox_ready`: `{sandbox_id}` — Sandbox 就绪通知

- [ ] **Step 2：重写 agent_runner.py**

用以下内容 **完全替换** `app/web/agent_runner.py`：

```python
"""Agent 工厂 + 事件发射包装器。

每种 Agent 类型对应一个 Observable* 子类，在关键生命周期节点
（step/think/execute_tool/run）推送事件到 asyncio.Queue。
"""

import asyncio
from typing import Any

from app.agent.manus import Manus
from app.agent.data_analysis import DataAnalysis
from app.schema import ToolCall


# ── 事件 Emit 辅助 ────────────────────────────────────


async def _emit(queue: asyncio.Queue, event_type: str, data: dict[str, Any]) -> None:
    """推送事件到 asyncio.Queue。"""
    payload = {"type": event_type, **data}
    await queue.put(payload)


# ── ObservableManus ────────────────────────────────────


class ObservableManus(Manus):
    """Manus 的事件注入子类。"""

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise


# ── ObservableDataAnalysis ─────────────────────────────


class ObservableDataAnalysis(DataAnalysis):
    """DataAnalysis 的事件注入子类。

    与 ObservableManus 完全相同的 emit 逻辑。
    """

    event_queue: asyncio.Queue | None = None

    async def step(self) -> str:
        await _emit(
            self.event_queue,
            "step_start",
            {"step": self.current_step + 1, "max_steps": self.max_steps},
        )
        return await super().step()

    async def think(self) -> bool:
        should_act = await super().think()
        last_msg = self.messages[-1] if self.messages else None
        thinking_content = ""
        tool_calls_data: list[dict] = []

        if last_msg and last_msg.role == "assistant":
            thinking_content = last_msg.content or ""
            if last_msg.tool_calls:
                tool_calls_data = [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in last_msg.tool_calls
                ]

        if thinking_content or tool_calls_data:
            await _emit(
                self.event_queue,
                "thinking",
                {"content": thinking_content, "tool_calls": tool_calls_data},
            )

        if not should_act and thinking_content and not tool_calls_data:
            await _emit(self.event_queue, "assistant", {"content": thinking_content})

        return should_act

    async def execute_tool(self, command: ToolCall) -> str:
        await _emit(
            self.event_queue,
            "tool_start",
            {"tool": command.function.name, "args": command.function.arguments},
        )
        result = await super().execute_tool(command)
        ok = not str(result).startswith("Error:")
        await _emit(
            self.event_queue,
            "tool_end",
            {"tool": command.function.name, "result": str(result), "ok": ok},
        )
        return result

    async def run(self, request: str | None = None) -> str:
        try:
            result = await super().run(request)
            await _emit(self.event_queue, "done", {"reason": "completed"})
            return result
        except Exception as exc:
            await _emit(self.event_queue, "error", {"message": str(exc)})
            await _emit(self.event_queue, "done", {"reason": "error"})
            raise


# ── Agent 工厂 ─────────────────────────────────────────


async def create_observable_agent(
    agent_type: str,
    event_queue: asyncio.Queue,
) -> Manus | DataAnalysis:
    """根据 agent_type 创建已初始化的 Observable Agent 实例。

    Args:
        agent_type: "general" → ObservableManus, "data_analysis" → ObservableDataAnalysis
        event_queue: asyncio.Queue，Agent 执行时通过此队列推送事件

    Returns:
        已初始化（含 MCP 连接）的 Agent 实例

    Raises:
        ValueError: agent_type 不在支持列表中
    """
    if agent_type == "general":
        agent = await ObservableManus.create()
    elif agent_type == "data_analysis":
        agent = ObservableDataAnalysis()
    else:
        raise ValueError(f"不支持的 agent_type: {agent_type}")

    agent.event_queue = event_queue
    return agent
```

- [ ] **Step 3：提交**

```powershell
git add app/web/agent_runner.py
git commit -m "refactor(web): agent_runner 支持 Manus + DataAnalysis 两种类型的事件包裹"
```

---

### Task 11：WebSocket Handler — 聊天执行核心

**Files:**
- Create: `app/web/chat/ws_handler.py`

**Interfaces:**
- Consumes: `create_observable_agent`, `create_session_sandbox`, `get_chat_or_404`, `save_message`, `decode_access_token`, `get_current_user`
- Produces:
  ```python
  # ws_handler 通过 server.py 的 WebSocket 路由调用
  # 不直接对外暴露 Python API

  # WebSocket 通信协议:
  # 客户端 → 服务端: {"type": "prompt", "content": "..."}
  # 服务端 → 客户端: 7 种事件类型 (同 agent_runner)
  ```

- [ ] **Step 1：创建 ws_handler.py**

`app/web/chat/ws_handler.py`:

```python
"""WebSocket 聊天端点处理器。

每建立一个 WebSocket = 一个 Agent 实例 + 一个 Sandbox 容器。
消息流: 接收 prompt → Agent 执行 → 事件推流 → 消息持久化 → 完成。
"""
from __future__ import annotations

import asyncio

import jwt as pyjwt
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.logger import logger
from app.web.agent_runner import create_observable_agent
from app.web.auth.models import User
from app.web.auth.service import decode_access_token
from app.web.chat.models import Chat
from app.web.chat.service import get_chat_or_404, save_message
from app.web.database import AsyncSessionLocal
from app.web.sandbox.service import create_session_sandbox, destroy_session_sandbox


async def handle_chat_ws(
    ws: WebSocket,
    chat_id: int,
    token: str,
) -> None:
    """处理单个 WebSocket 聊天连接。

    1. 校验 JWT → 查出 User
    2. 校验 chat 归属
    3. 创建 Sandbox + Agent
    4. 接收 prompt → agent.run() → 事件推流 + 持久化
    5. 清理
    """
    # ── 认证 ──────────────────────────────────────
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError:
        await ws.accept()
        await ws.send_json({"type": "error", "message": "认证失败，请重新登录"})
        await ws.close()
        return

    async with AsyncSessionLocal() as db:
        user_id = payload["user_id"]
        try:
            chat = await get_chat_or_404(db, chat_id, user_id)
        except Exception:
            await ws.accept()
            await ws.send_json({"type": "error", "message": "会话不存在"})
            await ws.close()
            return

        await ws.accept()

        event_queue: asyncio.Queue = asyncio.Queue()
        sandbox = None
        agent = None

        try:
            # 接收第一条消息（prompt）
            data = await ws.receive_json()
            if data.get("type") != "prompt" or not data.get("content"):
                await ws.send_json(
                    {"type": "error", "message": "请发送有效的 prompt"}
                )
                return

            prompt_text = data["content"]

            # 持久化用户消息
            await save_message(
                db, chat_id, role="user", content=prompt_text
            )

            # ── Sandbox ─────────────────────────
            network = chat.agent_type == "general"
            sandbox = await create_session_sandbox(
                user_id, chat_id, network_enabled=network
            )
            logger.info(
                f"Sandbox 就绪: user={user_id}, chat={chat_id}, "
                f"type={chat.agent_type}"
            )

            # ── Agent ───────────────────────────
            agent = await create_observable_agent(
                chat.agent_type, event_queue
            )

            # 启动 Agent（后台执行）
            async def run_agent():
                await agent.run(prompt_text)
                await event_queue.put(None)  # 哨兵

            agent_task = asyncio.create_task(run_agent())

            # ── 事件推流 + 持久化循环 ──────────
            while True:
                event = await event_queue.get()
                if event is None:
                    break

                # 持久化到 MySQL
                try:
                    await save_message(
                        db,
                        chat_id=chat_id,
                        role=_event_role(event),
                        content=event.get("content"),
                        event_type=event["type"],
                        tool_name=event.get("tool"),
                        tool_args=_parse_args(event.get("args")),
                    )
                except Exception as db_err:
                    logger.warning(f"消息持久化失败: {db_err}")

                await ws.send_json(event)

            await agent_task

        except WebSocketDisconnect:
            logger.info(f"WS 断开: user={user_id}, chat={chat_id}")
            if agent_task and not agent_task.done():
                agent_task.cancel()
        except Exception as exc:
            logger.error(f"WS 错误: {exc}")
            try:
                await ws.send_json(
                    {"type": "error", "message": f"服务器错误: {str(exc)}"}
                )
            except Exception:
                pass
        finally:
            if agent:
                try:
                    await agent.cleanup()
                except Exception:
                    pass
            await destroy_session_sandbox(sandbox, user_id, chat_id)
            try:
                await ws.close()
            except Exception:
                pass


def _event_role(event: dict) -> str:
    """根据事件类型映射消息角色。"""
    if event["type"] in ("assistant", "thinking"):
        return "assistant"
    if event["type"] in ("tool_start", "tool_end"):
        return "tool"
    if event["type"] in ("done", "error"):
        return "system"
    return "assistant"


def _parse_args(raw_args) -> dict | None:
    """将工具参数从 JSON 字符串转为 dict（可能已是 dict）。"""
    if raw_args is None:
        return None
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            import json
            return json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw_args}
    return {"raw": str(raw_args)}
```

- [ ] **Step 2：提交**

```powershell
git add app/web/chat/ws_handler.py
git commit -m "feat(chat): WebSocket 聊天处理器 — Agent 执行 + 事件推流 + 持久化"
```

---

### Task 12：重写 server.py — 全路由汇聚

**Files:**
- Modify: `app/web/server.py`（完全重写）
- Modify: `web_run.py`（静态目录路径更新）

**Interfaces:**
- Consumes: `auth_router`, `chat_router`, `ws_handler`
- Produces: 完整的 FastAPI 应用，包含 WebSocket `/ws/{chat_id}?token=xxx` 端点

- [ ] **Step 1：重写 server.py**

用以下内容 **完全替换** `app/web/server.py`：

```python
"""FastAPI 服务器 — OpenManus 多用户 Web 后端。

端点:
    GET  /                  → 聊天前端页面（Vue 构建产物）
    /static/                → 前端静态资源（JS/CSS/图片）
    WS  /ws/{chat_id}       → WebSocket 聊天端点
    /api/auth/*             → 认证路由
    /api/chats/*            → 会话 CRUD 路由
    /api/files/*            → 文件管理路由（Task 13）
"""
from pathlib import Path

from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import config
from app.web.auth.router import router as auth_router
from app.web.chat.router import router as chat_router
from app.web.chat.ws_handler import handle_chat_ws


app = FastAPI(title="OpenManus Web", version="0.2.0")

# ── REST 路由 ────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
# 文件路由将在 Task 13 挂载

# ── 前端静态文件 ─────────────────────────────

static_dir = Path(config.web.static_dir)
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """返回前端首页（Vue 构建产物 index.html）。"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    # 回退：简单 API 信息
    return {
        "message": "OpenManus Web API",
        "docs": "/docs",
        "note": "前端尚未构建，请运行: cd web_ui && npm run build",
    }


# ── WebSocket ────────────────────────────────

@app.websocket("/ws/{chat_id}")
async def websocket_chat(
    ws: WebSocket,
    chat_id: int,
    token: str = Query(...),
):
    """WebSocket 聊天端点。

    客户端连接: ws://host:8080/ws/{chat_id}?token={jwt}
    发送: {"type": "prompt", "content": "你的任务"}
    """
    await handle_chat_ws(ws, chat_id, token)
```

- [ ] **Step 2：确认 web_run.py 指向正确的 app**

读取 `web_run.py`，确认内容是：
```python
import uvicorn
uvicorn.run("app.web.server:app", host="0.0.0.0", port=8080, ...)
```

若有 `reload=True` 保留用于开发，生产环境改为 `reload=False`。文件内容合理则无需修改。

- [ ] **Step 3：启动服务验证路由可用**

```powershell
# 启动服务（后台）
python web_run.py &
```

Run: `curl http://localhost:8080/docs`
Expected: Swagger UI 页面，显示 auth 和 chat 两组路由

Run: `curl http://localhost:8080/api/auth/register -X POST -H "Content-Type: application/json" -d '{"username":"testuser","password":"test123456"}'`
Expected: 返回 `{"id":X,"username":"testuser","access_token":"...","token_type":"bearer"}`

- [ ] **Step 4：提交**

```powershell
git add app/web/server.py
git commit -m "feat(web): 汇聚所有路由到 FastAPI + WebSocket 端点"
```

---

## 阶段 F：文件管理

### Task 13：文件上传/下载/删除 API

**Files:**
- Create: `app/web/files/__init__.py` (空文件)
- Create: `app/web/files/models.py`
- Create: `app/web/files/schemas.py`
- Create: `app/web/files/service.py`
- Create: `app/web/files/router.py`
- Create: `tests/web/test_files.py`
- Modify: `app/web/server.py`（挂载 files 路由）

**Interfaces:**
- Consumes: `get_current_user`, `get_db`, `config.web.sandbox_data_root`
- Produces:
  ```python
  # HTTP:
  # POST   /api/files/upload         multipart/form-data  → {"id", "filename", ...}
  # GET    /api/files?chat_id=       → List[FileInfo]
  # GET    /api/files/{id}/download  → StreamingResponse (Content-Disposition: attachment)
  # DELETE /api/files/{id}           → {"ok": true}
  ```

- [ ] **Step 1：创建文件 ORM + Schema + Service + Router**

创建 `app/web/files/__init__.py`（空）。

`app/web/files/models.py`:

```python
"""用户文件 ORM 模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.web.database import Base


class UserFile(Base):
    """用户上传和生成的文件表。"""

    __tablename__ = "user_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
```

手动建表 SQL（在云端 MySQL 执行）：

```sql
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
);
```

`app/web/files/schemas.py`:

```python
"""文件操作请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    chat_id: int | None
    filename: str
    file_size: int
    mime_type: str | None
    created_at: datetime
```

`app/web/files/service.py`:

```python
"""文件存取业务逻辑。"""
import os
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.web.files.models import UserFile


async def save_uploaded_file(
    db: AsyncSession,
    user_id: int,
    file: UploadFile,
    chat_id: int | None = None,
) -> UserFile:
    """保存上传文件到用户目录并写入数据库记录。"""
    user_dir = config.web.sandbox_data_root / "users" / str(user_id) / "uploads"
    user_dir.mkdir(parents=True, exist_ok=True)

    dest_path = user_dir / file.filename
    # 避免覆盖：重名文件加序号
    counter = 1
    while dest_path.exists():
        stem, ext = os.path.splitext(file.filename)
        dest_path = user_dir / f"{stem}_{counter}{ext}"
        counter += 1

    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    record = UserFile(
        user_id=user_id,
        chat_id=chat_id,
        filename=dest_path.name,
        file_path=str(dest_path.relative_to(config.web.sandbox_data_root)),
        file_size=len(content),
        mime_type=file.content_type,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_user_files(
    db: AsyncSession,
    user_id: int,
    chat_id: int | None = None,
) -> list[UserFile]:
    """列出用户文件，可按会话过滤。"""
    query = select(UserFile).where(UserFile.user_id == user_id)
    if chat_id is not None:
        query = query.where(UserFile.chat_id == chat_id)
    query = query.order_by(UserFile.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_file_or_404(
    db: AsyncSession,
    file_id: int,
    user_id: int,
) -> UserFile:
    """获取文件记录，校验权限。"""
    result = await db.execute(
        select(UserFile).where(UserFile.id == file_id, UserFile.user_id == user_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return record


async def delete_file_record(db: AsyncSession, record: UserFile) -> None:
    """删除数据库记录和磁盘文件。"""
    # 删磁盘
    full_path = config.web.sandbox_data_root / record.file_path
    if full_path.exists():
        full_path.unlink()
    # 删记录
    await db.delete(record)
    await db.commit()
```

`app/web/files/router.py`:

```python
"""文件管理路由: /api/files/*"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.web.auth.models import User
from app.web.database import get_db
from app.web.dependencies import get_current_user
from app.web.files.schemas import FileInfo
from app.web.files.service import (
    delete_file_record,
    get_file_or_404,
    list_user_files,
    save_uploaded_file,
)


router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file,  # UploadFile 从 multipart/form-data 注入
    chat_id: int | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await save_uploaded_file(db, user.id, file, chat_id)
    return FileInfo.model_validate(record)


@router.get("", response_model=list[FileInfo])
async def list_files(
    chat_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    records = await list_user_files(db, user.id, chat_id)
    return [FileInfo.model_validate(r) for r in records]


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await get_file_or_404(db, file_id, user.id)
    full_path = config.web.sandbox_data_root / record.file_path
    return FileResponse(
        str(full_path),
        filename=record.filename,
        media_type=record.mime_type or "application/octet-stream",
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await get_file_or_404(db, file_id, user.id)
    await delete_file_record(db, record)
    return {"ok": True}
```

> 修正：上面的 router 用了 `Form` 但没 import。需要在 router.py 顶部加 `from fastapi import ..., Form, UploadFile`。

- [ ] **Step 2：修改 server.py 挂载 files 路由**

在 `app/web/server.py` 的 `app.include_router(chat_router)` 之后添加：

```python
from app.web.files.router import router as files_router
app.include_router(files_router)
```

- [ ] **Step 3：创建文件管理测试**

`tests/web/test_files.py`:

```python
"""文件上传/下载/删除 API 测试。"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.web.server import app


async def _setup(ac: AsyncClient) -> tuple[str, int]:
    username = f"fileuser_{uuid.uuid4().hex[:8]}"
    resp = await ac.post(
        "/api/auth/register",
        json={"username": username, "password": "pw123456"},
    )
    return resp.json()["access_token"], resp.json()["id"]


@pytest.mark.asyncio
async def test_upload_and_list():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _setup(ac)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("test.csv", b"col1,col2\n1,2\n", "text/csv")}
        resp = await ac.post("/api/files/upload", files=files, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.csv"

        resp = await ac.get("/api/files", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_download_and_delete():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        token, _ = await _setup(ac)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("hello.txt", b"hello world", "text/plain")}
        resp = await ac.post("/api/files/upload", files=files, headers=headers)
        file_id = resp.json()["id"]

        resp = await ac.get(f"/api/files/{file_id}/download", headers=headers)
        assert resp.status_code == 200
        assert resp.text == "hello world"

        resp = await ac.delete(f"/api/files/{file_id}", headers=headers)
        assert resp.status_code == 200

        resp = await ac.get(f"/api/files/{file_id}/download", headers=headers)
        assert resp.status_code == 404
```

- [ ] **Step 4：运行测试**

Run: `pytest tests/web/test_files.py -v`
Expected: 2 passed

- [ ] **Step 5：提交**

```powershell
git add app/web/files/ app/web/server.py tests/web/test_files.py
git commit -m "feat(files): 文件上传/下载/删除 API"
```

---

## 阶段 G：Vue 3 前端

### Task 14：创建 Vite + Vue 3 项目骨架

**Files:**
- Create: `web_ui/package.json`
- Create: `web_ui/vite.config.ts`
- Create: `web_ui/index.html`
- Create: `web_ui/src/main.ts`
- Create: `web_ui/src/App.vue`
- Create: `web_ui/src/router/index.ts`
- Create: `web_ui/src/stores/auth.ts`
- Create: `web_ui/src/api/client.ts`
- Create: `web_ui/src/views/LoginView.vue` (占位)
- Create: `web_ui/src/views/ChatView.vue` (占位)
- Create: `web_ui/src/assets/main.css`

**Interfaces:**
- Consumes: 无
- Produces: `npm run dev` 可在浏览器打开，显示 Hello World；`npm run build` 产出到 `dist/`

- [ ] **Step 1：创建 package.json**

`web_ui/package.json`:

```json
{
  "name": "openmanus-web-ui",
  "private": true,
  "version": "0.2.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5",
    "vue-router": "^4.4",
    "pinia": "^2.2",
    "axios": "^1.7",
    "marked": "^14.0",
    "highlight.js": "^11.10"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1",
    "vite": "^5.4",
    "tailwindcss": "^3.4",
    "autoprefixer": "^10.4",
    "postcss": "^8.4"
  }
}
```

- [ ] **Step 2：创建 vite.config.ts**

```typescript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/ws": { target: "ws://localhost:8080", ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
```

- [ ] **Step 3：安装依赖**

```powershell
cd web_ui
npm install
```

- [ ] **Step 4：创建 index.html + main.ts + App.vue + Tailwind 配置**

`web_ui/index.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenManus Chat</title>
  </head>
  <body class="bg-gray-50">
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`web_ui/src/main.ts`:

```typescript
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./assets/main.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
```

`web_ui/src/App.vue`:

```html
<template>
  <router-view />
</template>
```

`web_ui/src/assets/main.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

pre { background: #1f2937; color: #e5e7eb; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
pre code { background: none; padding: 0; }
code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
.tool-card { transition: border-color 0.3s ease; }
@keyframes spin { to { transform: rotate(360deg); } }
.animate-spin { animation: spin 0.8s linear infinite; }
```

`web_ui/tailwind.config.js`:

```js
export default {
  content: ["./index.html", "./src/**/*.{vue,ts,js}"],
  theme: { extend: {} },
  plugins: [],
};
```

`web_ui/postcss.config.js`:

```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 5：创建路由骨架**

`web_ui/src/router/index.ts`:

```typescript
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
```

- [ ] **Step 6：创建 Pinia auth store + axios client**

`web_ui/src/stores/auth.ts`:

```typescript
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
```

`web_ui/src/api/client.ts`:

```typescript
import axios from "axios";

const client = axios.create({ baseURL: "/" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default client;
```

`web_ui/src/api/auth.ts`:

```typescript
import client from "./client";

export const authApi = {
  login: (username: string, password: string) =>
    client.post("/api/auth/login", { username, password }),
  register: (username: string, password: string) =>
    client.post("/api/auth/register", { username, password }),
};
```

- [ ] **Step 7：创建占位页面**

`web_ui/src/views/LoginView.vue`:

```html
<template>
  <div class="min-h-screen flex items-center justify-center">
    <h1 class="text-2xl text-gray-500">登录页面 — 占位</h1>
  </div>
</template>
```

`web_ui/src/views/ChatView.vue`:

```html
<template>
  <div class="min-h-screen flex items-center justify-center">
    <h1 class="text-2xl text-gray-500">聊天页面 — 占位</h1>
  </div>
</template>
```

- [ ] **Step 8：验证开发环境**

```powershell
cd web_ui
npm run dev
# 浏览器打开 http://localhost:5173
# 应看到聊天占位页面；http://localhost:5173/login 应看到登录占位页
```

- [ ] **Step 9：验证构建**

```powershell
npm run build
# dist/ 目录应包含 index.html + assets/
```

- [ ] **Step 10：提交**

```powershell
git add web_ui/
git commit -m "feat(frontend): Vite + Vue 3 + Pinia + Vue Router 项目骨架"
```

---

### Task 15：登录/注册页面

**Files:**
- Modify: `web_ui/src/views/LoginView.vue`（完整实现）
- Modify: `web_ui/src/api/auth.ts`（补充类型）

- [ ] **Step 1：实现 LoginView.vue**

用完整登录/注册页面替换占位内容：

```html
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
```

- [ ] **Step 2：更新 auth API 以返回更好的类型**

`web_ui/src/api/auth.ts` 无需改动（已使用 `.data`），但确认内容与 Task 14 一致。

- [ ] **Step 3：验证**

```powershell
cd web_ui && npm run dev
# 浏览器打开 http://localhost:5173/login
# 填写用户名 + 密码 → 注册 → 应跳转到 /chat（当前为占位页面）
```

> 要求后端 `python web_run.py` 已启动在 8080 端口，且 MySQL 可达。

- [ ] **Step 4：提交**

```powershell
git add web_ui/src/views/LoginView.vue
git commit -m "feat(frontend): 登录/注册页面"
```

---

### Task 16：Chat API + ChatStore

**Files:**
- Create: `web_ui/src/api/chat.ts`
- Modify: `web_ui/src/stores/auth.ts`（如无需改则不修改）
- Create: `web_ui/src/stores/chat.ts`

- [ ] **Step 1：创建聊天 API 模块**

`web_ui/src/api/chat.ts`:

```typescript
import client from "./client";

export interface ChatInfo {
  id: number;
  user_id: number;
  title: string;
  agent_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MessageInfo {
  id: number;
  role: string;
  content: string | null;
  tool_name: string | null;
  event_type: string | null;
  created_at: string;
}

export const chatApi = {
  list: () => client.get<ChatInfo[]>("/api/chats"),
  create: (agent_type: string, title?: string) =>
    client.post<ChatInfo>("/api/chats", { agent_type, title }),
  get: (id: number) =>
    client.get<ChatInfo & { messages: MessageInfo[] }>(`/api/chats/${id}`),
  deleteChat: (id: number) => client.delete(`/api/chats/${id}`),
  getMessages: (id: number, beforeId?: number, limit = 50) =>
    client.get<MessageInfo[]>(`/api/chats/${id}/messages`, {
      params: { before_id: beforeId, limit },
    }),
};
```

- [ ] **Step 2：创建 ChatStore**

`web_ui/src/stores/chat.ts`:

```typescript
import { defineStore } from "pinia";
import { ref } from "vue";
import { chatApi, type ChatInfo, type MessageInfo } from "../api/chat";

export const useChatStore = defineStore("chat", () => {
  const chats = ref<ChatInfo[]>([]);
  const currentChatId = ref<number | null>(null);
  const currentMessages = ref<MessageInfo[]>([]);
  const running = ref(false);

  // WebSocket 实例（每个聊天页一个）
  const ws = ref<WebSocket | null>(null);

  async function loadChats() {
    const res = await chatApi.list();
    chats.value = res.data;
  }

  async function createChat(agentType: string, title?: string): Promise<ChatInfo> {
    const res = await chatApi.create(agentType, title);
    await loadChats();
    return res.data;
  }

  async function deleteChat(id: number) {
    await chatApi.deleteChat(id);
    await loadChats();
    if (currentChatId.value === id) {
      currentChatId.value = null;
      currentMessages.value = [];
    }
  }

  async function loadHistory(chatId: number) {
    const res = await chatApi.get(chatId);
    currentMessages.value = res.data.messages || [];
  }

  async function loadMoreMessages(beforeId: number) {
    if (!currentChatId.value) return;
    const res = await chatApi.getMessages(currentChatId.value, beforeId);
    currentMessages.value = [...res.data, ...currentMessages.value];
  }

  function connectWS(chatId: number) {
    disconnectWS();
    const token = localStorage.getItem("access_token");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/ws/${chatId}?token=${token}`;
    ws.value = new WebSocket(url);
    return ws.value;
  }

  function disconnectWS() {
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
  }

  return {
    chats, currentChatId, currentMessages, running, ws,
    loadChats, createChat, deleteChat, loadHistory, loadMoreMessages,
    connectWS, disconnectWS,
  };
});
```

- [ ] **Step 3：验证编译**

```powershell
cd web_ui && npm run build
```

Expected: 无 TypeScript 编译错误。

- [ ] **Step 4：提交**

```powershell
git add web_ui/src/api/chat.ts web_ui/src/stores/chat.ts
git commit -m "feat(frontend): Chat API 模块 + Pinia ChatStore"
```

---

### Task 17：聊天主页面（ChatView + 组件）

**Files:**
- Modify: `web_ui/src/views/ChatView.vue`（完整实现）
- Create: `web_ui/src/components/ChatSidebar.vue`
- Create: `web_ui/src/components/ChatWindow.vue`
- Create: `web_ui/src/components/MessageBubble.vue`
- Create: `web_ui/src/components/NewChatDialog.vue`

- [ ] **Step 1：实现 ChatSidebar**

`web_ui/src/components/ChatSidebar.vue`:

```html
<template>
  <aside class="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
    <div class="px-4 py-3 border-b border-gray-100">
      <button @click="$emit('new')" class="w-full bg-blue-500 hover:bg-blue-600 text-white rounded-lg py-2 text-sm font-medium">
        + 新建会话
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="chat in chats"
        :key="chat.id"
        @click="$emit('select', chat.id)"
        :class="[
          'px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50 text-sm',
          chat.id === currentId ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
        ]"
      >
        <div class="flex items-center gap-2">
          <span>{{ chat.agent_type === 'data_analysis' ? '📊' : '🤖' }}</span>
          <span class="truncate font-medium text-gray-700">{{ chat.title }}</span>
        </div>
        <div class="text-xs text-gray-400 mt-0.5">{{ chat.agent_type }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { ChatInfo } from "../api/chat";
defineProps<{ chats: ChatInfo[]; currentId: number | null }>();
defineEmits<{ select: [id: number]; new: [] }>();
</script>
```

- [ ] **Step 2：实现 MessageBubble**

`web_ui/src/components/MessageBubble.vue`:

```html
<template>
  <!-- 用户消息 -->
  <div v-if="msg.role === 'user' && !msg.event_type" class="flex justify-end mb-4">
    <div class="bg-blue-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] shadow-sm">
      <p class="whitespace-pre-wrap text-sm">{{ msg.content }}</p>
    </div>
  </div>

  <!-- 步骤指示器 -->
  <div v-if="msg.event_type === 'step_start'" class="text-center my-3">
    <span class="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1">
      Step {{ (msg as any).step }}/{{ (msg as any).max_steps }}
    </span>
  </div>

  <!-- 思考 -->
  <div v-if="msg.event_type === 'thinking' && msg.content" class="mb-3">
    <details class="bg-gray-100 border border-gray-200 rounded-xl px-4 py-2.5 max-w-[85%]">
      <summary class="text-xs text-gray-500 font-medium cursor-pointer">🤔 思考过程</summary>
      <div class="text-sm text-gray-600 whitespace-pre-wrap mt-1" v-html="renderMd(msg.content)"></div>
    </details>
  </div>

  <!-- 工具执行 -->
  <div v-if="msg.event_type === 'tool_start'" class="mb-3 border-l-4 border-yellow-400 bg-white rounded-r-lg border border-l-0 border-gray-200 px-4 py-2.5 shadow-sm max-w-[85%]">
    <div class="flex items-center gap-2">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-700">{{ (msg as any).tool || msg.tool_name }}</span>
      <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full"></span>
    </div>
  </div>

  <div v-if="msg.event_type === 'tool_end'" class="mb-3 border-l-4 bg-white rounded-r-lg border border-l-0 border-gray-200 px-4 py-2.5 shadow-sm max-w-[85%]"
    :class="(msg as any).ok ? 'border-l-green-400' : 'border-l-red-400'">
    <div class="flex items-center gap-2 mb-1">
      <span class="text-sm">🔧</span>
      <span class="text-sm font-medium text-gray-700">{{ msg.tool_name }}</span>
      <span v-if="(msg as any).ok" class="text-green-500 text-xs">✅</span>
      <span v-else class="text-red-500 text-xs">❌</span>
    </div>
    <div v-if="msg.content" class="text-xs text-gray-500 max-h-32 overflow-y-auto whitespace-pre-wrap">{{ msg.content }}</div>
  </div>

  <!-- Agent 回复 -->
  <div v-if="msg.event_type === 'assistant'" class="mb-4">
    <div class="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%] shadow-sm">
      <div class="text-sm text-gray-800 leading-relaxed" v-html="renderMd(msg.content)"></div>
    </div>
  </div>

  <!-- 错误 -->
  <div v-if="msg.event_type === 'error'" class="mb-3">
    <div class="bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 max-w-[85%]">
      <span class="text-sm text-red-700">⚠️ {{ msg.content }}</span>
    </div>
  </div>

  <!-- 完成 -->
  <div v-if="msg.event_type === 'done'" class="text-center my-3">
    <span class="text-xs text-gray-400">— 任务结束 —</span>
  </div>
</template>

<script setup lang="ts">
import type { MessageInfo } from "../api/chat";
import { marked } from "marked";

defineProps<{ msg: MessageInfo & Record<string, any> }>();

function renderMd(text: string | null): string {
  if (!text) return "";
  try { return marked.parse(text) as string; } catch { return text; }
}
</script>
```

- [ ] **Step 3：实现 ChatWindow**

`web_ui/src/components/ChatWindow.vue`:

```html
<template>
  <div class="flex-1 flex flex-col h-screen">
    <!-- 顶栏 -->
    <header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
      <div>
        <h2 class="font-semibold text-gray-800">{{ title }}</h2>
        <p class="text-xs text-gray-400">Agent: {{ agentType }} · {{ running ? '运行中' : '就绪' }}</p>
      </div>
      <span v-if="running" class="flex items-center gap-1 text-sm text-yellow-600">
        <span class="animate-spin inline-block w-3 h-3 border-2 border-yellow-600 border-t-transparent rounded-full"></span>
        运行中
      </span>
      <span v-else class="text-sm text-green-600">⚡ 就绪</span>
    </header>

    <!-- 消息区 -->
    <main ref="msgContainer" class="flex-1 overflow-y-auto px-4 py-6 space-y-2">
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-5xl mb-4">🤖</span>
        <p>在下方输入你的任务</p>
      </div>
      <MessageBubble v-for="(msg, i) in messages" :key="i" :msg="msg" />
    </main>

    <!-- 输入 -->
    <footer class="bg-white border-t border-gray-200 px-4 py-3 shrink-0">
      <div class="flex gap-2 max-w-3xl mx-auto">
        <input
          v-model="input"
          @keydown.enter="send"
          :disabled="running"
          placeholder="输入你的任务，按 Enter 发送..."
          class="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />
        <button
          @click="send"
          :disabled="running || !input.trim()"
          class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
        >发送 ▶</button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import MessageBubble from "./MessageBubble.vue";
import type { MessageInfo } from "../api/chat";

const props = defineProps<{
  messages: (MessageInfo & Record<string, any>)[];
  title: string;
  agentType: string;
  running: boolean;
}>();

const emit = defineEmits<{ send: [text: string] }>();

const input = ref("");
const msgContainer = ref<HTMLElement | null>(null);

function send() {
  const text = input.value.trim();
  if (!text || props.running) return;
  emit("send", text);
  input.value = "";
}

watch(() => props.messages.length, () => {
  nextTick(() => {
    if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight;
  });
});
</script>
```

- [ ] **Step 4：实现 NewChatDialog**

`web_ui/src/components/NewChatDialog.vue`:

```html
<template>
  <div v-if="show" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl p-6 w-96 shadow-xl">
      <h3 class="font-semibold text-lg mb-4">新建会话</h3>
      <label class="block text-sm font-medium text-gray-600 mb-2">选择 Agent 类型</label>
      <select v-model="selected" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4">
        <option value="general">🤖 通用 Agent (Manus)</option>
        <option value="data_analysis">📊 数据分析 Agent</option>
      </select>
      <label class="block text-sm font-medium text-gray-600 mb-2">会话标题（可选）</label>
      <input v-model="title" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4" placeholder="输入标题..." />
      <div class="flex gap-2 justify-end">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg">取消</button>
        <button @click="confirm" class="px-4 py-2 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded-lg">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{ show: boolean }>();
const emit = defineEmits<{ close: []; confirm: [agentType: string, title: string] }>();

const selected = ref("general");
const title = ref("");

function confirm() {
  emit("confirm", selected.value, title.value);
  title.value = "";
}
</script>
```

- [ ] **Step 5：实现 ChatView.vue（组装所有组件）**

`web_ui/src/views/ChatView.vue`（完全重写占位版本）：

```html
<template>
  <div class="flex h-screen">
    <ChatSidebar
      :chats="chatStore.chats"
      :currentId="chatStore.currentChatId"
      @select="switchChat"
      @new="showNewDialog = true"
    />
    <ChatWindow
      v-if="chatStore.currentChatId"
      :messages="chatStore.currentMessages"
      :title="currentTitle"
      :agentType="currentAgentType"
      :running="chatStore.running"
      @send="sendPrompt"
    />
    <div v-else class="flex-1 flex items-center justify-center text-gray-400">
      <p>选择一个会话或新建一个开始</p>
    </div>
    <NewChatDialog
      :show="showNewDialog"
      @close="showNewDialog = false"
      @confirm="createAndEnter"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "../stores/chat";
import { useAuthStore } from "../stores/auth";
import ChatSidebar from "../components/ChatSidebar.vue";
import ChatWindow from "../components/ChatWindow.vue";
import NewChatDialog from "../components/NewChatDialog.vue";

const chatStore = useChatStore();
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const showNewDialog = ref(false);

const currentTitle = computed(() =>
  chatStore.chats.find((c) => c.id === chatStore.currentChatId)?.title || ""
);
const currentAgentType = computed(() =>
  chatStore.chats.find((c) => c.id === chatStore.currentChatId)?.agent_type || ""
);

onMounted(async () => {
  await chatStore.loadChats();
  const id = Number(route.params.id);
  if (id) await switchChat(id);
});

async function switchChat(id: number) {
  chatStore.currentChatId = id;
  await chatStore.loadHistory(id);
  router.replace(`/chat/${id}`);
}

async function createAndEnter(agentType: string, title: string) {
  showNewDialog.value = false;
  const chat = await chatStore.createChat(agentType, title || undefined);
  router.push(`/chat/${chat.id}`);
  await switchChat(chat.id);
}

function sendPrompt(text: string) {
  if (!chatStore.currentChatId) return;

  const ws = chatStore.connectWS(chatStore.currentChatId);
  const userMsg = { role: "user", content: text, event_type: null, created_at: new Date().toISOString(), id: Date.now(), tool_name: null };
  chatStore.currentMessages.push(userMsg as any);
  chatStore.running = true;

  ws.onopen = () => ws.send(JSON.stringify({ type: "prompt", content: text }));

  ws.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    if (evt.type === "tool_end") {
      // 找到最近的 tool_start 替换为 tool_end
      for (let i = chatStore.currentMessages.length - 1; i >= 0; i--) {
        const m = chatStore.currentMessages[i];
        if (m.event_type === "tool_start" && m.tool_name === evt.tool) {
          chatStore.currentMessages[i] = {
            ...m,
            content: evt.result,
            ok: evt.ok,
            event_type: "tool_end",
          };
          return;
        }
      }
    }
    chatStore.currentMessages.push({
      id: Date.now(),
      role: evt.type === "tool_start" || evt.type === "tool_end" ? "tool" : "assistant",
      content: evt.content || evt.message || null,
      tool_name: evt.tool || null,
      event_type: evt.type,
      created_at: new Date().toISOString(),
      step: evt.step,
      max_steps: evt.max_steps,
      ok: evt.ok,
    } as any);

    if (evt.type === "done") {
      chatStore.running = false;
      chatStore.disconnectWS();
    }
  };

  ws.onclose = () => { chatStore.running = false; };
  ws.onerror = () => { chatStore.running = false; chatStore.currentMessages.push({ role: "assistant", content: "连接失败", event_type: "error", created_at: new Date().toISOString(), id: Date.now(), tool_name: null } as any); };
}
</script>
```

- [ ] **Step 6：验证构建**

```powershell
cd web_ui && npm run build
```

Expected: 无编译错误，产出 `dist/` 目录到 `web_ui/dist/`。

> **注意**：Task 14 的 vexe.config.ts 中 proxport 应已有 copy 处理。构建产物路径需与 `config.toml` 的 `static_dir = "web_ui/dist"` 一致。

- [ ] **Step 7：提交**

```powershell
git add web_ui/src/views/ChatView.vue web_ui/src/components/
git commit -m "feat(frontend): 聊天主页面 — ChatView + Sidebar + ChatWindow + MessageBubble"
```

---

### Task 18：集成测试 — 前后端联调

**Files:**
- 无新建文件
- 验证范围：登录 → 创建会话 → WebSocket 对话 → 文件上传/下载

- [ ] **Step 1：启动后端**

```powershell
python web_run.py
```

- [ ] **Step 2：构建前端后启动预览 或 使用 dev 代理**

```powershell
cd web_ui
npm run dev        # Vite dev server 在 5173，API 代理到 8080
```

- [ ] **Step 3：手动测试场景**

在浏览器打开 `http://localhost:5173`：

1. 自动跳转到 `/login` → 注册一个新用户
2. 点击 "新建会话" → 选择 general → 创建
3. 输入 "用 python 计算 1 到 100 的和" → 发送
4. 观察：思考面板展开、工具卡片出现、最终回复显示
5. 切换会话 tab → 应可正常切换
6. 上传一个 CSV 文件 → 确认返回 200

- [ ] **Step 4：提交**

仅确认集成无误，无需单独提交（因为无新文件改动）。如有小 bug 修复，合并到之前的某次提交。

---

## 阶段 H：集成与部署

### Task 19：完善 web_run.py + 前端构建后自动 Serving

**Files:**
- Modify: `web_run.py`（确认启动逻辑）
- Create: `deploy.sh` (Linux 部署脚本)

- [ ] **Step 1：确认 web_run.py 内容**

`web_run.py` 应包含：

```python
"""OpenManus Web 服务器启动入口。

Usage:
    python web_run.py                        # 开发环境
    python web_run.py --host 0.0.0.0 --port 8080 --reload

访问:
    http://localhost:8080                    # 前端页面
    http://localhost:8080/docs               # API 文档
"""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true", default=False)
    args = parser.parse_args()

    uvicorn.run(
        "app.web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2：创建 Linux 生产部署脚本**

`deploy.sh`:

```bash
#!/bin/bash
# OpenManus Web 生产部署脚本 (Linux 服务器)
set -e

echo "=== 1. 安装 Python 依赖 ==="
pip install -r requirements.txt

echo "=== 2. 构建前端 ==="
cd web_ui
npm install
npm run build
cd ..

echo "=== 3. 创建数据目录 ==="
sudo mkdir -p /data/openmanus/users
sudo chown -R $USER:$USER /data/openmanus

echo "=== 4. 启动服务 ==="
echo "启动命令: python web_run.py --host 0.0.0.0 --port 8080"
echo "部署完成！访问 http://$(hostname -I | awk '{print $1}'):8080"
```

```powershell
# Windows 本地部署等效命令:
# web_ui/ 下 npm run build 完成后，python web_run.py 已自动 serve dist/
```

- [ ] **Step 3：提交**

```powershell
git add web_run.py deploy.sh
git commit -m "chore(web): 完善 web_run.py + Linux 部署脚本"
```

---

### Task 20：最终端到端验证 + systemd 服务文件

**Files:**
- Create: `deploy/openmanus-web.service` (systemd 单元文件)
- 无代码改动

- [ ] **Step 1：创建 systemd 服务文件**

`deploy/openmanus-web.service`:

```ini
[Unit]
Description=OpenManus Web Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=openmanus
WorkingDirectory=/opt/OpenManus
Environment="PATH=/opt/conda/envs/open_manus/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/conda/envs/open_manus/bin/python web_run.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2：运行完整测试套件**

```powershell
# 运行所有 web 相关测试
pytest tests/web/ -v

# 预期 (累计):
# test_config.py:      3 passed
# test_database.py:    2 passed
# test_auth_service.py: 3 passed
# test_auth_router.py: 4 passed
# test_chat_models.py: 2 passed
# test_chat_router.py: 5 passed
# test_sandbox_service.py: 1 passed
# test_sandbox_integration.py: 2 passed (需 Docker)
# test_files.py:       2 passed
# ─────────────────────
#  总计: 24 passed
```

- [ ] **Step 3：验证前端构建**

```powershell
cd web_ui
npm run build
cd ..
dir web_ui\dist\index.html  # 应存在
```

- [ ] **Step 4：启动完整服务验证**

```powershell
python web_run.py
# 另一个终端:
curl http://localhost:8080/docs
curl http://localhost:8080/api/auth/register -X POST -H "Content-Type: application/json" -d '{"username":"finaltest","password":"test123456"}'
```

Expected: Swagger UI 正常，注册返回 200 带 JWT。

- [ ] **Step 5：提交最终文件**

```powershell
git add deploy/
git commit -m "chore(deploy): systemd 服务文件 + 最终端到端验证通过"
```

---
