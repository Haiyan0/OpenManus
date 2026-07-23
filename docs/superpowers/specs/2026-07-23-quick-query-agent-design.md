# QuickQuery Agent 轻量数据查询智能体 — 设计文档

**日期**: 2026-07-23
**分支**: feat/web-chat
**状态**: 已确认

---

## 1. 需求背景

用户在使用 OpenManus Web 平台进行数据分析时，存在大量"轻量查询"场景：只想快速获取特定数据（如"xx项目二月到四月销售额"），不需要走 DataAnalysis Agent 完整的"分析 → 图表 → 报告"流程。

当前 DataAnalysis Agent 拥有 VisualizationPrepare + DataVisualization 工具，提示词天然导向图表生成，即使简单查询也会跑多步骤。同时用户希望 Agent 更主动使用 ask_human 澄清需求歧义。

### 核心需求

1. **按需选择** — 前端提供 Agent 类型选择，用户决定本次是"快速查询"还是"完整分析"
2. **直给数据** — 查询类请求直接返回数据结果（文字/表格），不延伸图表和报告
3. **追问先行** — 遇到指标口径、时间范围、项目名称等不确定信息，主动 ask_human 确认
4. **极简步数** — 一次查询 + 一次 Python 计算即交付，无多余步骤

---

## 2. 架构决策

| 选项 | 描述 | 结论 |
|------|------|------|
| A | **新建 QuickQuery Agent** | **采纳** |
| B | DataAnalysis 扩展轻量模式参数 | 不选 — 工具链强绑定图表流程，动态裁剪加两套提示词会让文件臃肿 |
| C | 放入 Manus | 不选 — Manus 有浏览器/编辑器等无关工具，职责不匹配 |

**决策理由**：新 Agent 工具集极简（4 个工具），系统提示词专注"数据查询 + 追问先行"，职责清晰、易维护。`agent_runner.py` 工厂模式已支持多 Agent 扩展，新增成本低。

---

## 3. 整体架构

```
web_ui/                          ← 前端：创建会话时 agent_type 新增 "quick_query"
app/web/chat/models.py           ← AGENT_TYPES 加入 "quick_query"
app/web/chat/ws_handler.py       ← 无需改动（已通过 agent_type 动态路由）

app/agent/quick_query.py         ← 【新文件】QuickQuery Agent (~50行)
app/prompt/quick_query.py        ← 【新文件】系统提示词 (~40行)
app/web/agent_runner.py          ← 新增 ObservableQuickQuery + 工厂分支 (~20行)

app/tool/company_data_lookup.py  ← 复用
app/tool/chart_visualization/    ← 复用 NormalPythonExecute
    python_execute.py
app/tool/ask_human.py            ← 复用
```

**路由逻辑**：前端创建会话时传 `agent_type: "quick_query"` → `ws_handler` 通过 `create_observable_agent("quick_query", ...)` 创建 Agent → 复用现有 WebSocket 推流/持久化通道。

**Sandbox 复用**：QuickQuery 使用与 DataAnalysis 相同的 Docker Sandbox 基础设施（NormalPythonExecute 在容器内执行），沙箱层无需任何改动。

---

## 4. Agent 设计

### 4.1 工具集（4 个，极简）

| 工具 | 用途 | 来源 |
|------|------|------|
| `CompanyDataLookup` | 匹配 company_data_resource 中的企业/项目 CSV 文件 | 已有，复用 |
| `NormalPythonExecute` | Sandbox 内执行 pandas/数据分析代码 | 已有，复用 |
| `AskHuman` | 遇歧义主动询问，事件驱动到前端 | 已有，复用 |
| `Terminate` | 完成任务后终止 | 已有，复用 |

**不加载**：`VisualizationPrepare`、`DataVisualization` — 从结构上杜绝"自动生成图表"。

### 4.2 系统提示词

```python
SYSTEM_PROMPT = """
你是 QuickQuery，一个轻量数据查询助手，运行在 Sandbox 环境中。

## 核心行为准则

1. **直接给答案**：用户问什么数据，你就查什么。查完直接回复，不要延伸出图表或报告。
   如果用户明确要求图表，告知用户切换到「完整分析」模式更合适。

2. **追问先行**：遇到以下情况，**主动调用 ask_human 确认，不要猜测**：
   - 指标口径不清（如"销售额"是含税还是不含税）
   - 时间范围模糊（如"最近"、"上一段"）
   - 企业/项目名称不完整或存在歧义
   - 用户上传了文件但未说明要分析什么

3. **最少步骤**：目标是一次查询 + 一次 Python 计算即交付结果。
   确认需求后立即读取数据并计算，完成后立即 Terminate。

4. **数据溯源**：回复时说明数据来源（文件路径、筛选条件），让用户知道数据来自哪里。

## 工作流程

1. 收到用户查询 → 判断是否需要澄清
2. 如需澄清 → ask_human 询问
3. 如有公司数据需求 → CompanyDataLookup 查找本地文件
4. 用 NormalPythonExecute 执行 pandas 读取+计算
5. 将计算结果清晰呈现给用户 → Terminate

## 约束

- 不生成图表（无 DataVisualization 工具）
- 不写分析报告，只返回查询结果
- 如果用户需求超出纯查询范围（要求趋势分析、预测、多维对比等），
  告知用户切换「完整分析」模式
- 工作目录：[DIR]
"""
```

### 4.3 Agent 类结构

```python
class QuickQuery(ToolCallAgent):
    name: str = "quick_query"
    description: str = "轻量数据查询智能体，专注快速数据查询与简单计算，不生成图表和报告"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 15  # 对比 DataAnalysis 的 60

    sandbox: Optional[object] = None
    _sandbox_workspace: str = ""

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CompanyDataLookup(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )

    def set_sandbox(self, sandbox, workspace="/workspace", host_workspace=""):
        # 与 DataAnalysis.set_sandbox() 完全相同的逻辑
        ...
```

---

## 5. 改动清单

### 后端改动

| 文件 | 改动 | 量级 |
|------|------|------|
| `app/agent/quick_query.py` | **新增** QuickQuery Agent 类 | ~50 行 |
| `app/prompt/quick_query.py` | **新增** SYSTEM_PROMPT + NEXT_STEP_PROMPT | ~40 行 |
| `app/web/agent_runner.py` | **新增** ObservableQuickQuery + 工厂分支 `elif agent_type == "quick_query"` | ~20 行 |
| `app/web/chat/models.py` | **修改** `AGENT_TYPES` 加入 `"quick_query"` | 1 行 |

### 前端改动

| 位置 | 改动 | 量级 |
|------|------|------|
| `NewChatDialog.vue` | 创建会话时 agent_type 下拉加一项：`"quick_query"`，标签"快速查询" | ~3 行 |
| `ChatView.vue` | 可选：顶部显示当前 Agent 类型标签 | ~5 行 |

### 无需改动

- `ws_handler.py` — 已通过 `chat.agent_type` 动态路由
- `sandbox/service.py` — QuickQuery 复用现有 Sandbox 创建/销毁逻辑
- `company_data_lookup.py` / `ask_human.py` / `python_execute.py` — 直接复用

---

## 6. 边界情况

| 场景 | 处理策略 |
|------|---------|
| CompanyDataLookup 未命中 | 告知用户"本地无该企业/项目数据"，建议上传文件或补充名称 → ask_human |
| 用户上传了文件但没说明指标 | 先用 NormalPythonExecute 读取文件字段/前几行 → ask_human 询问要分析什么 |
| 用户问"帮我看下趋势"等模糊词 | ask_human 确认时间范围、指标；若需要图表建议切换到 DataAnalysis |
| 用户问的问题需要图表 | 告知：快速查询模式不生成图表，请切换到「完整分析」模式 |
| Sandbox 创建失败 | 降级到宿主机 Python 执行（与现有 DataAnalysis 逻辑一致） |
| 用户连续追问（多轮对话） | QuickQuery 支持多轮（ws_handler 已有 while True 循环，无需改造） |

---

## 7. ask_human 使用策略

采用 **宽松建议** 模式（选项 B）：

- 系统提示词要求"遇到不确定的优先询问"，但不强制每轮都先问
- 模型自行判断：问题明确时直接查，有歧义时先 ask_human
- 工具返回错误/模糊结果时，提示词已引导走 ask_human 路径

---

## 8. max_steps 与成本控制

| 参数 | QuickQuery | DataAnalysis | 理由 |
|------|-----------|-------------|------|
| max_steps | **15** | 60 | 限制步数膨胀，简单查询无需多步 |
| 工具数 | **4** | 6 | 无图表工具，减少 LLM 选择空间 |
| 典型步骤 | 1-5 步 | 5-20 步 | 确认→查数据→计算→回复→终止 |

---

## 9. 验收标准

1. 前端创建"快速查询"会话，QuickQuery Agent 正确启动
2. 问"某项目X月到Y月销售额"→ Agent 执行 CompanyDataLookup + Python 计算 → 直接返回数值/表格 → 调用 Terminate 结束
3. 问"帮我分析下销售趋势"→ Agent 询问时间范围/指标（ask_human）→ 收到回复后执行查询
4. 不调用 VisualizationPrepare / DataVisualization
5. 总步数 ≤ 15
6. Sandbox 正常创建/销毁，无资源泄漏
7. 切换到"完整分析"模式后 DataAnalysis Agent 正常工作（回归验证）

---

## 10. 文件树（新增/修改）

```
app/
├── agent/
│   └── quick_query.py          # 【新增】
├── prompt/
│   └── quick_query.py          # 【新增】
└── web/
    ├── agent_runner.py          # 【修改】
    └── chat/
        └── models.py            # 【修改】

web_ui/src/
├── components/
│   └── NewChatDialog.vue        # 【修改】
└── views/
    └── ChatView.vue             # 【修改】
```
