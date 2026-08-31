# GEO 内容生产 Agent 集成设计文档

> 状态：设计已确认 | 日期：2026-08-31 | 作者：Codex

## 1. 背景与目标

### 1.1 现状

`geo-content-sop` skill 提供一套面向 GEO 内容生产的完整 SOP：交互式收集素材、维度与渠道选型、结构定制、缺口追问、正文生成、质量评分，以及交付正文、发布配置单、评分卡三份文件。该能力当前存在于本机 agent skill 体系中，OpenManus Web 用户无法直接选择和使用。

OpenManus 已经有 `quick_query`、`data_analysis`、`wechat_publish` 等业务 Agent 类型，Web 端通过会话类型创建对应 Agent，并复用 WebSocket、用户工作区、文件上传与下载能力。

### 1.2 目标

将 GEO SOP 改造成 OpenManus 中面向普通用户的独立 Agent 类型 `geo_content`：

- Web 前端「新建会话」可选择「GEO 内容生产」Agent。
- Agent 通过聊天式交互推进 GEO SOP 七阶段流程。
- 用户可以粘贴或上传文章内容，作为结构与风格参考进行仿写；只仿结构和表达方式，不复制原文内容。
- Agent 在用户会话工作区保存 `_working-data.md`，支持断线或后续消息恢复上下文。
- Agent 最终在工作区生成正文、发布配置单、评分卡三份文件，供前端文件面板下载。
- GEO 知识资产进入仓库内只读目录，运行时不依赖个人目录下的 skill 路径。

### 1.3 非目标

- 首版不开放普通用户更新 GEO 样本库、benchmark、评分权重或全局知识资产。
- 首版不提供专门表单或向导页面，只做聊天式 Agent 接入。
- 首版不为 `geo_content` 开启 sandbox 网络；用户提供 URL 时，引导用户粘贴正文或上传文件。
- 首版不做真实发布到外部平台；只生成发布配置建议。
- 首版不做管理员样本维护工具。该能力后续可由开发者单独设计权限、审计、并发写入和回滚机制。

---

## 2. 架构设计

### 2.1 组件结构

```text
app/agent/geo_content.py                 -> GeoContent Agent
app/prompt/geo_content.py                -> 系统提示词与下一步提示词
app/tool/geo_content/                    -> GEO 专用工具模块
  __init__.py
  geo_content.py                         -> GeoContentTool
  service.py                             -> 状态、知识读取、交付文件、硬性检查
app/knowledge/geo_content/               -> 仓库内只读 GEO 知识资产
  knowledge-geo.md
  benchmark-data.md
  data-collection-fields.md
  dimension-channel-matrix.md
  section-templates.md
  style-analysis.md
  quality-checklist.md
  scoring-rubric.md
  deliverable-spec.md
```

Web 接入点：

```text
app/web/chat/models.py                   -> AGENT_TYPES 增加 geo_content
app/web/chat/schemas.py                  -> Agent 类型描述增加 geo_content
app/web/agent_runner.py                  -> 创建 ObservableGeoContent
web_ui/src/components/NewChatDialog.vue  -> 新建会话增加 GEO 内容生产选项
```

如上传类型限制阻止参考文章文件上传，补充 `.md`、`.html`、`.docx` 中首版实际支持的格式。若 `.docx` 解析暂不实现，则前端不承诺 `.docx`，只开放 `.txt`、`.md`、`.html`。

### 2.2 Agent 设计

`GeoContentAgent` 继承现有 `ToolCallAgent` 模式：

```python
class GeoContent(ToolCallAgent):
    name: str = "geo_content"
    description: str = "GEO 内容生产智能体，可按 SOP 生成正文、发布配置单和评分卡"
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    max_observe: int = 10000
    max_steps: int = 30
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            GeoContentTool(),
            NormalPythonExecute(),
            AskHuman(),
            Terminate(),
        )
    )
```

职责划分：

- Agent 负责对话、判断用户意图、生成大纲、写正文、根据评分结果决定是否补充或重写。
- `GeoContentTool` 负责确定性动作：读取知识资产、维护 `_working-data.md`、检查素材缺口、保存交付文件、执行硬性质量检查。
- `AskHuman` 负责阶段确认和缺口追问。
- `NormalPythonExecute` 只作为辅助工具，用于必要的文本整理或文件读取，不承载 GEO 核心状态机。

### 2.3 知识资产策略

将 `geo-content-sop` 的 references 复制到 `app/knowledge/geo_content/`，作为随项目发布的只读知识资产。运行时所有读取都通过仓库路径完成，不读取 `C:\Users\hyh\.agents\skills\...`。

首版知识资产为只读：

- 普通用户不能写入样本库。
- 普通用户不能改 benchmark。
- 普通用户不能改评分权重。
- Agent 提示词必须明确禁止通过用户指令修改全局知识资产。

开发者后续维护样本库时，通过代码评审和测试更新该目录内容，不作为 Web 用户能力。

### 2.4 GEO 工具接口

`GeoContentTool` 使用单工具多 action 设计，减少 Agent 工具面：

| action | 用途 |
| --- | --- |
| `load_knowledge` | 按主题读取 SOP 知识资产，例如字段说明、渠道矩阵、评分规则、交付规范 |
| `load_state` | 读取当前工作区 `_working-data.md` |
| `save_state` | 保存阶段、素材、缺口、用户确认记录、草稿摘要 |
| `analyze_inputs` | 检查 A-F 字段完整度，返回缺口与建议追问 |
| `save_deliverables` | 保存正文、发布配置单、评分卡三份文件 |
| `quality_check` | 执行硬性检查，例如来源缺失、疑似编造、交付文件字段缺漏 |

工具参数必须限制在用户当前工作区内，避免任意路径读取或写入。所有输出文件写入工作区根目录或受控子目录。

### 2.5 状态文件

`_working-data.md` 位于用户会话工作区，用于恢复同一会话内的 GEO 任务。建议内容结构：

```markdown
# GEO Working Data

## Stage

## Topic

## Business Context

## A-F Materials

## Reference Style

## Dimension And Channel

## Outline Confirmation

## Gaps

## Draft Summary

## Quality Result
```

该文件是内部工作文件，不作为最终交付主文件，但保留在工作区便于恢复和排查。

### 2.6 交付文件

最终按 `deliverable-spec.md` 生成三份文件：

- `{date}_{topic}_正文.md`
- `{date}_{topic}_发布配置单.md`
- `{date}_{topic}_评分卡.md`

文件命名中的 topic 需要清理非法路径字符。若 topic 为空，使用 `geo_content` 作为保底名称。

---

## 3. 用户流程

```text
用户新建 GEO 内容生产会话
  -> Agent 读取或创建 _working-data.md
  -> Agent 收集业务、经验、权威、意图词、来源、FAQ 等 A-F 素材
  -> 用户可粘贴或上传参考文章
  -> Agent 提取参考文章的结构与风格，不复制内容
  -> Agent 推荐维度与渠道
  -> Agent 输出大纲并请求用户确认
  -> Agent 针对缺口追问一次
  -> 缺口仍存在时弱化表达或删除相关板块
  -> Agent 生成正文、发布配置单、评分卡
  -> 工具执行硬性质量检查
  -> 通过后保存三份文件并结束
```

关键约束：

- 有来源才能写确定性事实、数字、人物案例。
- 没来源的内容必须弱化为经验性、建议性或场景性表达。
- 不允许编造客户故事、专家背书、精确数据、奖项资质。
- 参考文章只用于结构、节奏、表达方式和板块组织，不用于内容复用。

---

## 4. Web 端接入

### 4.1 后端

`AGENT_TYPES` 增加 `geo_content`，并在 agent factory 中新增分支。Web 会话仍沿用现有用户隔离工作区与 sandbox 注入模式。

`geo_content` 的 sandbox 网络配置保持关闭，与 `quick_query`、`wechat_publish` 一致。若用户输入 URL，Agent 需要说明首版不直接抓取网页，并要求用户粘贴正文或上传文件。

### 4.2 前端

新建会话弹窗新增「GEO 内容生产」选项。文案重点放在产出结果而非内部 SOP：

- 名称：GEO 内容生产
- 描述：收集素材并生成正文、发布配置单和评分卡

上传类型按实际支持范围更新。首版若只支持文本类参考文章，则开放 `.txt`、`.md`、`.html`。

---

## 5. 错误处理

- 工作区不可用：返回明确错误，提示稍后重试或重新创建会话。
- `_working-data.md` 损坏：保留原文件，创建带时间后缀的恢复文件，并提示用户重新确认关键素材。
- 知识资产缺失：工具返回错误，不进入自由发挥模式。
- 素材不足：通过 `AskHuman` 追问；追问一次后仍不足时，降级表达或删除相关板块。
- 质量硬性检查失败：返回失败项，Agent 回到补充素材或重写阶段。
- 尝试更新样本库或权重：拒绝并说明该能力仅面向开发者维护。
- 用户提供 URL：引导粘贴正文或上传文件，不尝试联网抓取。

---

## 6. 测试策略

### 6.1 TDD 顺序

1. 新增 `GeoContentTool` 状态文件测试：`load_state` / `save_state` 只在工作区内读写。
2. 新增素材完整度测试：A-F 字段缺失时返回明确缺口。
3. 新增交付文件测试：保存三份文件，文件名清理非法字符。
4. 新增权限边界测试：样本库、benchmark、权重更新 action 不存在或被拒绝。
5. 新增质量硬性检查测试：无来源的精确数字、人物案例、资质背书被标记风险。
6. 新增 Agent 创建测试：`geo_content` 能通过 web factory 创建。
7. 新增或更新前端构建验证：新建会话选项存在且构建通过。

### 6.2 验证命令

Python 验证必须使用固定解释器：

```powershell
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\tool\test_geo_content.py -v
C:\Users\hyh\anaconda3\envs\open_manus\python.exe -m pytest tests\web\test_agent_runner.py -v
pre-commit run --files <本次改动文件>
npm --prefix web_ui run build
```

若测试文件名与现有结构不一致，实施时以实际测试目录为准，但验证范围不降低。

---

## 7. 风险与权衡

- Prompt-only 实现速度最快，但阶段状态、评分和交付容易漂移；因此首版采用 Agent + 专用工具的混合方案。
- 完全独立工作流引擎更稳定，但会引入专门 UI 和更多后端接口；首版先复用聊天式 Agent。
- 不开放 URL 抓取会降低一点便利性，但能保持无网络 sandbox、安全边界和可预测性。
- 不开放样本库更新会降低普通用户自定义权重能力，但能避免全局基准被污染。
- `.docx` 支持依赖额外解析能力；首版可以先支持 `.txt`、`.md`、`.html`，后续再补 `.docx`。

---

## 8. 验收标准

- Web 新建会话中出现 `geo_content` / 「GEO 内容生产」选项。
- 后端能创建 `GeoContentAgent`，并注入用户工作区 sandbox。
- Agent 能在工作区创建或恢复 `_working-data.md`。
- Agent 能基于 A-F 素材检查缺口，并通过 `AskHuman` 追问。
- Agent 能读取仓库内 GEO 知识资产，不依赖个人 skill 路径。
- Agent 能保存正文、发布配置单、评分卡三份文件。
- 普通用户无法通过 Agent 更新样本库、benchmark 或评分权重。
- 首版不联网抓取 URL，遇到 URL 会要求用户粘贴或上传正文。
- 相关 Python 测试、改动文件 pre-commit、前端 build 均实际运行并记录结果。
