好的，这是将上述内容整理成的 Markdown 格式文档，方便你阅读和使用。

---

# OpenManus MCP 服务端连接配置指南

## 关键说明

当前 `run_mcp_server.py` 默认只支持 **stdio** 传输（`parse_args` 中 `choices=["stdio"]`），但通过修改代码可以同时支持 **SSE** 模式。
因此，有两种主要连接方式可供选择。

---

## 方式一：stdio（自动模式）⭐ 推荐

### 原理

- 客户端（Manus）启动时，自动以**子进程**方式拉起 MCP 服务端。
- 双方通过**标准输入/输出管道**通信。
- 无需手动预先启动服务端，服务端生命周期由客户端管理。

### 配置步骤

#### Step 1：创建 `config/mcp.json` 文件

在项目根目录的 `config/` 文件夹下创建 `mcp.json`，内容如下：

```json
{
    "mcpServers": {
        "openmanus-local": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "app.mcp.server"]
        }
    }
}
```

> **注意**：`args` 也可以指向入口文件，例如：
>
> ```json
> "args": ["run_mcp_server.py"]
> ```

#### Step 2：启动 Manus

```bash
python main.py
```

### 工作流程

```mermaid
graph LR
    A[python main.py] --> B[Manus.create()]
    B --> C[initialize_mcp_servers]
    C --> D[读取 config/mcp.json]
    D --> E[type="stdio" → 子进程启动 run_mcp_server.py]
    E --> F[通过 stdin/stdout 管道通信]
    F --> G[远程工具自动注册为 mcp_openmanus-local_bash 等]
```

### ✅ 优点

- 零额外配置
- 自动生命周期管理（Agent 退出，服务端自动关闭）
- 适合日常开发和使用

---

## 方式二：SSE（网络模式，适合跨机器或调试）

### 前提条件

需要对 `run_mcp_server.py` 进行小幅修改，以支持 `--transport sse` 参数。

#### 修改内容摘要

1. **在 `app/mcp/server.py` 中**：

   - 修改 `run()` 方法，增加 `host` 和 `port` 参数。
   - 在 `run()` 中根据 `transport` 类型分别调用 `self.server.run()`。
2. **在 `run_mcp_server.py` 中**：

   - 添加 `--host` 和 `--port` 命令行参数。
   - 将解析到的 `host` 和 `port` 传递给 `server.run()`。

> 详细代码改动可参考官方文档或提交记录，此处不再赘述。

### 配置步骤

#### Step 1：在终端 A 中启动 MCP 服务端

```bash
python run_mcp_server.py --transport sse --host 127.0.0.1 --port 8000
```

服务端将在 `http://127.0.0.1:8000/sse` 上监听 SSE 连接。

#### Step 2：创建 `config/mcp.json`（客户端配置）

```json
{
    "mcpServers": {
        "openmanus-remote": {
            "type": "sse",
            "url": "http://127.0.0.1:8000/sse"
        }
    }
}
```

#### Step 3：在终端 B 中启动 Agent（客户端）

```bash
python main.py
```

### 架构示意

```
终端 A（服务端）               终端 B（客户端）
┌─────────────────┐          ┌─────────────────┐
│ run_mcp_server  │  SSE     │ python main.py  │
│ :8000/sse       │◄────────►│ Manus           │
│                 │  HTTP    │  ├─ 本地工具     │
│ bash / browser  │          │  └─ MCP 远程工具 │
│ editor / term   │          │     (通过 SSE)   │
└─────────────────┘          └─────────────────┘
```

### ✅ 优点

- 服务端独立运行，可跨机器部署
- 多个 Agent 可共享同一个服务端
- 便于调试（服务端日志独立可见）

---

## 方式三：使用 `run_mcp.py` 直接测试连接

如果你的目的只是**纯粹测试 MCP 连接**，而不需要 Manus 的本地工具，可以使用专门的测试脚本。

```bash
# stdio 模式（自动拉起服务端）
python run_mcp.py -c stdio

# SSE 模式（需先在另一终端启动服务端）
python run_mcp.py -c sse --url http://127.0.0.1:8000/sse
```

---

## 模式选择速查表

| 场景                              | 推荐配置方式                                           |
| --------------------------------- | ------------------------------------------------------ |
| 日常使用，不想额外操作            | **方式一**（stdio + config/mcp.json）            |
| 服务端与 Agent 分开部署           | **方式二**（SSE：终端A启动服务，终端B启动Agent） |
| 调试 MCP 工具，需要查看服务端日志 | **方式二**（SSE，两个终端，日志独立）            |
| 快速测试 MCP 连通性               | **方式三**（`run_mcp.py`）                     |

---

## 注意事项

- 修改 `run_mcp_server.py` 以支持 SSE 时，记得同步更新 `app/mcp/server.py` 中的 `run()` 方法签名。
- 使用 stdio 模式时，确保 `config/mcp.json` 中的 `command` 和 `args` 正确指向 Python 环境及服务端入口。
- 远程工具注册后，名称会自动添加前缀，格式为 `mcp_{server_id}_{tool_name}`，例如 `mcp_openmanus-local_bash`。
