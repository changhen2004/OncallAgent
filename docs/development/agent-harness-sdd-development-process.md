# Agent Harness + SDD 开发流程规范

本文档用于指导 OnCallAgent 及同类 Agent 项目的 AI 辅助开发流程。核心目标是把 AI 从“直接写代码的助手”约束成“按规格、按工具边界、按反馈循环工作的工程代理”。

参考资料：

- AGENTS.md 规范：https://agents.md/
- OpenAI Agents SDK MCP 文档：https://openai.github.io/openai-agents-js/guides/mcp/
- OpenAI Agents SDK Tools 文档：https://openai.github.io/openai-agents-js/guides/tools/
- GitHub Spec Kit：https://github.com/github/spec-kit
- Spec-Driven Development：https://github.com/github/spec-kit/blob/main/spec-driven.md
- Martin Fowler Harness Engineering：https://martinfowler.com/articles/harness-engineering.html
- Martin Fowler Context Engineering：https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html
- Martin Fowler Maintainability Sensors：https://martinfowler.com/articles/sensors-for-coding-agents.html

## 1. 总原则

Agent 开发不应采用“给一句需求就让 AI 写代码”的方式。规范流程应是：

```text
项目规则 -> 需求规格 -> 人工确认 -> 技术方案 -> 任务拆分 -> 实现 -> 自测验证 -> 文档沉淀 -> 提交存档
```

本流程采用两个基础思想：

- Harness Engineering：把模型之外的规则、工具、上下文、架构约束、测试、审查和可观测性都视为 Agent 的 Harness。
- Spec-Driven Development：规格是源头，代码是规格和实现计划的表达；需求变化必须先更新规格，再更新实现。

人类负责人负责：

- 明确目标、边界、验收标准和优先级。
- 审批方案、关键架构约束和风险取舍。
- 审查最终产物是否符合业务意图。

AI 负责人负责：

- 读取仓库、文档和最新外部资料。
- 产出规格、方案、任务拆分和实现。
- 运行测试、解释失败、修复可修复问题。
- 沉淀文档和变更记录。

## 2. 仓库级上下文入口

每个 Agent 项目必须维护 `AGENTS.md`。它不是完整百科，而是 AI 进入仓库后的导航入口。

`AGENTS.md` 必须包含：

- 项目背景：系统解决什么问题，主要用户是谁。
- 技术栈：语言、框架、数据库、中间件、Agent 框架、模型服务。
- 目录地图：核心目录职责和禁止修改区域。
- 架构约束：模块边界、状态管理、工具调用、RAG、错误处理规则。
- 代码规范：命名、测试、日志、配置、依赖管理。
- 常用命令：启动、测试、构建、局部验证、依赖服务。
- AI 工作规则：先方案后实现、不得跳过测试、不得覆盖用户改动。

OnCallAgent 推荐 `AGENTS.md` 骨架：

```markdown
# AGENTS.md

## 项目背景
OnCallAgent 是面向智能运维值班场景的 Agent 系统，融合 RAG、Prometheus 工具调用和 Plan-Execute-Replan。

## 技术栈
- Python
- FastAPI
- uv
- Qdrant
- Ollama Embedding
- OpenAI 兼容模型接口
- Prometheus

## 核心目录
- `oncallagent/`：FastAPI 应用、Agent 编排、工具和基础设施适配
- `tests/`：单元测试和 API 行为测试
- `docs/runbooks/`：运维知识库和排障手册
- `docs/development/`：流程规范和工程文档
- `config/`：配置模板和本地配置

## 架构约束
- 工具必须显式注入依赖，禁止新增包级可变全局状态。
- Agent 状态必须结构化记录目标、证据、工具调用、预算和停止原因。
- RAG 工具只负责检索，不负责构造 retriever。
- 外部工具必须有超时、错误返回和可观测日志。
- 复杂功能必须先写规格和方案，再实现。

## 验证命令
- `/home/chg/.local/bin/uv run pytest`
- `curl http://localhost:8819/ping`
- `curl http://localhost:8819/plan`

## AI 工作规则
- 修改前先检查当前 git 状态。
- 不得回滚用户未要求回滚的改动。
- 新功能先补测试或验收用例。
- 全量测试失败时必须区分本次引入失败和既有失败。
```

## 3. SDD 标准流程

所有非平凡 Agent 功能都必须走 SDD 流程。小修也可以简化，但不得跳过“方案确认”和“验证记录”。

### 3.1 Constitution：项目原则

目标：先定义项目不可违反的规则。

产物：

- `AGENTS.md`
- `docs/architecture.md` 或架构说明文档
- `docs/development/agent-harness-sdd-development-process.md`

必须明确：

- 哪些模块是 Agent 编排层。
- 哪些模块是工具层。
- 哪些模块是基础设施访问层。
- 哪些边界不允许跨越。
- 哪些测试是提交前最低门槛。

### 3.2 Specify：需求规格

目标：只写 what 和 why，不写具体实现。

推荐路径：

```text
specs/<feature-name>/spec.md
```

规格必须包含：

- 背景和问题。
- 用户故事或运维场景。
- 输入、输出和关键交互。
- 成功标准。
- 失败场景。
- 不在本次范围内的内容。

Agent 开发规格必须额外说明：

- Agent 的目标是什么。
- Agent 可使用哪些工具。
- 哪些行为必须交给人类确认。
- 哪些输出必须带证据。

### 3.3 Clarify：澄清和人工确认

目标：在实现前消除高影响歧义。

必须人工确认：

- 功能目标是否正确。
- 验收标准是否可测试。
- 工具权限是否合理。
- 是否允许联网、调用外部 API、写入数据库或执行迁移。
- 是否接受当前测试环境缺口。

禁止行为：

- AI 在用户未确认方案前直接修改核心架构。
- AI 用猜测补齐高风险业务规则。
- AI 把“可以后面改”当成跳过规格的理由。

### 3.4 Plan：技术方案

目标：把规格转成可执行实现计划。

推荐路径：

```text
specs/<feature-name>/plan.md
```

方案必须包含：

- 目标架构。
- 数据流。
- 关键接口和类型。
- 工具治理策略。
- 上下文管理策略。
- 错误处理策略。
- 测试计划。
- 回滚或降级方式。

Agent 方案必须额外包含：

- Prompt 或 System Instruction 的变化。
- State 字段变化。
- Tool 输入输出 schema。
- RAG 检索边界。
- 预算限制：最大迭代、最大工具调用、最大运行时间。
- 熵管理：哪些上下文进入短期状态，哪些沉淀为文档。

### 3.5 Checklist：验收清单

目标：把规格和方案转为可验证条目。

推荐路径：

```text
specs/<feature-name>/checklist.md
```

清单必须具备：

- 每条都能被测试、日志、人工审查或静态检查验证。
- 每条都对应明确的规格或方案来源。
- 不包含“体验更好”“代码更优雅”这类不可验证描述。

示例：

```markdown
- [ ] RAG 工具通过构造函数显式接收 retriever。
- [ ] 未配置 retriever 时返回明确错误，不发生 panic。
- [ ] Chat Agent 和 Plan Executor 均不依赖 RAG 全局变量。
- [ ] 工具层单元测试覆盖正常检索、错误透传、缺失依赖。
```

### 3.6 Tasks：任务拆分

目标：把实现拆成 AI 可稳定执行的小步。

推荐路径：

```text
specs/<feature-name>/tasks.md
```

拆分原则：

- 每个任务只改一个清晰边界。
- 优先纵向切片，避免大规模横向重构。
- 每个任务必须有验证方式。
- 涉及 Agent 行为变化时，先写测试或可复现用例。
- 涉及工具治理时，先定义接口和错误语义。

### 3.7 Implement：实现

目标：按任务逐项实现，不擅自扩大范围。

AI 实现规则：

- 开始前检查 git 状态，避免覆盖用户改动。
- 先读相关代码，再改代码。
- 先写测试或验收用例，再写生产代码。
- 只改与当前任务直接相关的文件。
- 遇到既有失败要记录，不把既有失败误判为本次失败。
- 任何外部资料、库 API、产品行为不确定时，必须通过 MCP 或联网查询官方资料。

### 3.8 Converge：收敛和存档

目标：功能完成后形成可恢复的上下文存档点。

每个功能完成后必须沉淀：

```text
docs/archive/<yyyy-mm-dd>-<feature-name>.md
```

存档内容：

- 需求摘要。
- 方案摘要。
- 关键决策。
- 修改范围。
- 测试命令和结果。
- 已知失败和原因。
- 后续建议。

提交规则：

- 每完成一个功能或可独立回滚的切片，就提交一次。
- commit message 应描述行为变化，而不是只写“update”。
- 提交前必须有最新测试证据。
- 如果全量测试因既有问题失败，commit 说明中必须列出失败项。

## 4. Harness 控制面

Harness 控制分为 Guides 和 Sensors。

### 4.1 Guides：前馈控制

Guides 在 AI 行动前约束行为，用于减少第一次输出错误概率。

常见 Guides：

- `AGENTS.md`：仓库规则入口。
- `spec.md`：需求和验收标准。
- `plan.md`：架构和实现方案。
- `tasks.md`：执行任务列表。
- Prompt 模板：Agent 角色、输出格式、工具使用规则。
- Tool schema：工具输入输出约束。
- 架构约束：禁止全局状态、禁止跨层调用、必须显式注入依赖。
- 示例：成功样例、失败样例、期望输出样例。

OnCallAgent 中的 Guide 示例：

- `RetrieveTool(retriever)` 是工具治理 Guide：工具必须显式接收依赖。
- `RunBudget` 是执行预算 Guide：限制迭代次数、工具调用次数和运行时长。
- `Evidence` 是输出质量 Guide：关键结论必须有证据来源。

### 4.2 Sensors：反馈控制

Sensors 在 AI 行动后观察结果，用于让 AI 自我修正。

常见 Sensors：

- 单元测试。
- 集成测试。
- 编译检查。
- 静态分析。
- lint。
- 日志和 traces。
- 浏览器端到端验证。
- Agent 自评审。
- 人工 code review。
- 生产环境指标和告警。

OnCallAgent 中的 Sensor 示例：

- `/home/chg/.local/bin/uv run pytest`：验证工具层、Agent 编排和 API 行为。
- `curl http://localhost:8819/ping`：验证 FastAPI 服务可用。
- `curl http://localhost:8819/plan`：验证 Prometheus 告警分析路径。
- Prometheus 告警查询：验证 Agent 是否能读取真实运行上下文。
- 工具调用记录：验证 Agent 是否按计划使用工具。

### 4.3 计算型控制和推理型控制

计算型控制是确定性的，优先级最高：

- 编译。
- 单元测试。
- 静态分析。
- schema 校验。
- 超时和预算检查。

推理型控制是不完全确定的，用于补充判断：

- AI code review。
- 架构方案评审。
- Prompt 质量评审。
- 文档一致性评审。
- 复杂 Agent 行为评估。

工程规则：

- 能用计算型控制解决的问题，不交给推理型控制。
- 推理型控制必须输出证据、风险和建议，不得只给“看起来可以”。
- Sensors 不能长期全绿或长期全红；长期全绿说明检查太弱，长期全红说明检查过敏或环境不稳定。

## 5. Agent 开发专用规范

### 5.1 上下文工程

上下文不是越多越好，而是要可定位、可压缩、可验证。

每个 Agent 任务的上下文包应包含：

- 用户目标。
- 当前规格。
- 当前计划。
- 相关代码入口。
- 可用工具列表。
- 约束和禁止事项。
- 最近测试结果。
- 已知失败。

上下文管理规则：

- `AGENTS.md` 只放稳定规则。
- `specs/` 放功能级规格和计划。
- `docs/` 放长期知识。
- 当前会话只保留当前任务必要上下文。
- 长任务必须周期性总结：已完成、当前状态、剩余任务、风险。
- 不能把一次性聊天结论长期依赖在模型记忆中，必须写入文档。

### 5.2 架构约束

Agent 系统必须明确分层：

```text
API Layer -> Agent Orchestration -> Tool Layer -> Infrastructure Adapter
```

OnCallAgent 分层约束：

- API Layer 只负责请求解析和响应。
- Agent Orchestration 负责 Chat Agent、Plan-Execute-Replan、状态流转。
- Tool Layer 负责工具包装、schema、错误语义、超时。
- Infrastructure Adapter 负责 Qdrant、Prometheus、Ollama、LLM API 等外部依赖。

禁止事项：

- 禁止工具层持有包级可变全局状态。
- 禁止 Agent 层直接拼接底层基础设施调用细节。
- 禁止 Prompt 里硬编码会变化的外部配置。
- 禁止工具静默吞错。
- 禁止没有预算限制的 Agent 循环。

推荐模式：

- 依赖显式注入。
- 面向接口编程。
- 工具输入输出 schema 化。
- 状态结构化。
- 错误可分类。
- 证据可追踪。

### 5.3 工具治理

每个工具必须有工具卡。

工具卡模板：

```markdown
## Tool: <tool-name>

- Purpose:
- Owner:
- Input schema:
- Output schema:
- Side effects:
- Timeout:
- Retry policy:
- Error types:
- Permission:
- Observability:
- Tests:
```

工具治理规则：

- 工具必须显式注入依赖。
- 工具不得依赖隐式全局变量。
- 工具必须返回结构化错误或明确错误文本。
- 工具必须说明是否有副作用。
- 写操作工具必须有人类确认或策略授权。
- 外部工具必须设置超时。
- MCP 工具只开放当前任务需要的最小能力。

### 5.4 RAG 规范

RAG 不是“把文档塞给模型”，而是可治理的信息检索链路。

RAG 开发必须定义：

- 知识来源。
- 文档切分策略。
- Embedding 模型。
- 向量库 collection。
- 检索 topK。
- 分数阈值。
- 返回文档格式。
- 缺失结果时的降级策略。
- 引用证据输出规则。

OnCallAgent 约束：

- RAG retriever 由基础设施层构造。
- RAG Tool 只接收 retriever 并执行检索。
- Agent 输出运维建议时必须说明依据来自告警、指标、日志还是知识库。
- 知识库文档变更后必须重新索引并记录索引结果。

### 5.5 反馈循环

Agent 不能只执行一次后结束，必须有反馈循环。

推荐循环：

```text
Plan -> Act -> Observe -> Evaluate -> Replan or Stop
```

每次循环必须记录：

- 当前目标。
- 本轮动作。
- 工具输入。
- 工具输出摘要。
- 证据。
- 消耗预算。
- 下一步决策。
- 停止原因。

停止条件：

- 达到目标。
- 证据不足，需要人类输入。
- 工具失败且无法恢复。
- 超过预算。
- 发现风险操作，需要审批。

### 5.6 熵管理

Agent 项目的熵来自：

- 规格和代码不一致。
- Prompt 越写越长。
- 工具越来越多但缺少权限边界。
- 文档重复和过期。
- 测试长期失败导致失去约束力。
- 会话上下文丢失导致重复决策。

熵管理规则：

- 每个功能只保留一个主规格。
- 决策写入 plan 或 archive，不依赖聊天历史。
- 过期文档必须标注 superseded 或删除。
- Prompt 模板定期压缩，迁移稳定规则到 `AGENTS.md` 或 Skills。
- 工具清单定期审计，删除无 owner、无测试、无用途的工具。
- 长期失败测试必须修复、隔离或明确标记为环境依赖。
- 每次提交都应形成可回退的存档点。

## 6. MCP 和 Skills 使用规范

### 6.1 MCP

MCP 用于给 AI 接入外部工具和实时上下文。

适合接入 MCP 的能力：

- 官方文档查询。
- 浏览器自动化。
- Grafana、Prometheus、日志平台。
- GitHub、Issue、PR。
- 数据库只读查询。
- 设计工具和接口文档。

MCP 使用规则：

- 默认只读。
- 写操作必须显式授权。
- 工具权限按任务最小化。
- 调用外部系统前说明目的。
- 工具输出必须摘要进入 Agent 状态。
- 失败时记录错误和降级路径。

### 6.2 Skills

Skills 用于固化可复用流程。

适合沉淀为 Skills 的流程：

- SDD 规格生成。
- Agent 工具治理审查。
- RAG 质量评估。
- 系统化 Debug。
- 完成前验证。
- 中文代码审查。
- Dify 复现流程。

Skill 编写规则：

- 一个 Skill 只解决一类重复任务。
- Skill 必须说明触发条件。
- Skill 必须列出步骤、输入、输出和验证方式。
- Skill 可引用模板和脚本，但不要把项目私密信息硬编码进去。
- Skill 更新后必须用真实任务验证一次。

## 7. 测试和验证规范

AI 完成功能后必须自己验证。

最低验证矩阵：

| 类型 | 命令或方式 | 目的 |
| --- | --- | --- |
| 工具层单测 | `/home/chg/.local/bin/uv run pytest tests/test_tools.py` | 验证工具行为 |
| API 检查 | `/home/chg/.local/bin/uv run pytest tests/test_api.py` | 验证路由兼容性 |
| 全量测试 | `/home/chg/.local/bin/uv run pytest` | 验证单元和集成边界测试 |
| 外部依赖 | Qdrant、Ollama、Prometheus | 验证真实依赖链路 |
| Agent 行为 | 示例告警、示例知识库、人工审查 | 验证输出是否符合运维场景 |

验证报告必须包含：

- 执行了哪些命令。
- 每条命令是否通过。
- 失败命令的关键错误。
- 失败是否与本次变更相关。
- 如果未执行某项验证，说明原因。

禁止：

- 未跑测试就说完成。
- 只跑局部测试就声称全量通过。
- 忽略失败输出。
- 把环境依赖失败说成代码没问题而不提供证据。

## 8. 功能存档点

每个功能完成后必须创建存档点。存档点是 AI 开发的“可恢复上下文”。

推荐路径：

```text
docs/archive/<yyyy-mm-dd>-<feature-name>.md
```

模板：

```markdown
# <Feature Name> 存档

## 目标

## 已完成变更

## 架构决策

## 测试结果

## 已知问题

## 后续建议
```

提交前检查：

- 规格已更新。
- 计划已更新。
- 代码已实现。
- 测试已运行。
- 文档已沉淀。
- git diff 已审查。
- commit message 描述行为变化。

推荐 commit 格式：

```text
feat(agent): add explicit retriever injection for rag tool
docs(harness): add agent sdd development process
test(tools): cover missing retriever error path
```

## 9. AI 执行提示模板

### 9.1 新功能开发

```text
请按 Agent Harness + SDD 流程处理这个功能：

1. 先读取 AGENTS.md、相关 spec、plan 和代码入口。
2. 如果没有 spec，先生成 spec 并等待人工确认。
3. 确认后生成 plan 和 tasks。
4. 实现前先写测试或验收用例。
5. 实现时遵守工具治理、显式注入、状态结构化和预算限制。
6. 完成后运行局部测试、编译检查和可行的全量测试。
7. 更新 docs/archive 存档，并给出测试证据。

功能目标：
{feature_goal}
```

### 9.2 Bug 修复

```text
请按系统化 Debug + Harness 反馈循环处理这个问题：

1. 先复现问题或找到失败测试。
2. 说明预期行为和实际行为。
3. 定位最小原因，不要先改代码。
4. 写失败测试证明问题存在。
5. 写最小修复。
6. 运行原失败测试和相关回归测试。
7. 更新存档，说明根因和防回归措施。

问题描述：
{bug_description}
```

### 9.3 Agent 工具治理改造

```text
请按 Harness 工具治理规范改造工具：

1. 查找工具当前依赖、全局状态、副作用和调用点。
2. 先补测试锁定目标行为。
3. 将隐式依赖改为显式注入。
4. 定义工具输入输出 schema 和错误语义。
5. 更新所有调用点。
6. 运行工具层测试和全仓库编译检查。
7. 记录本次改造对架构约束的影响。

目标工具：
{tool_name}
```

## 10. OnCallAgent 当前落地优先级

建议按以下顺序继续改造：

1. 创建根目录 `AGENTS.md`，固化项目规则和测试命令。
2. 持续完善 `oncallagent/harness.py` 与真实 Agent 执行链路的证据记录。
3. 为每个 Tool 增加工具卡、超时、错误分类和调用记录。
4. 将 RAG、Prometheus、CLS MCP 等工具纳入统一 Tool Registry。
5. 为 Plan-Execute-Replan 增加预算停止、证据审查和 Replan 条件。
6. 建立 `specs/` 和 `docs/archive/`，让每个功能形成可恢复存档。
7. 修复或隔离当前全量测试中的环境依赖失败，让测试重新成为可信 Sensor。

## 11. 最小执行守则

如果只能记住 5 条，执行以下规则：

1. 做项目前先写 `AGENTS.md`，把项目背景、技术栈、代码规范和测试命令告诉 AI。
2. 先让 AI 出规格和方案，人工确认后再写代码。
3. 用 MCP 和 Skills 给 AI 配好工具，让它能查最新资料、执行标准流程、访问必要上下文。
4. 功能完成后必须让 AI 自己跑测试，并如实记录通过和失败。
5. 每完成一个功能就沉淀文档并提交代码，形成 AI 的存档点。
