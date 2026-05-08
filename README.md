# 群聊增强插件 (Chat Plus)

<div align="center">

[![Version](https://img.shields.io/badge/version-v1.2.2-blue.svg)](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.11.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)

一个以 **AI读空气** 为核心的群聊增强插件，让你的Bot更懂氛围、更自然地参与群聊互动

## ⚠️ 注意: AstrBot平台自带的说明文档查看器有一定的问题，可能会导致点击跳转按钮之后，没办法跳转到正常的说明文件中，建议直接在项目的github仓库中查看或者是直接下载压缩包，然后解压自行翻看

[快速开始](#-快速开始) • [功能总览](#-功能总览) • [推荐配置](#-v121-完整推荐配置保守版) • [更新日志](#-更新日志)

[深度指南与常见问题](docs/ARCHITECTURE.md) • [消息工作流程详解](docs/MESSAGE_WORKFLOW.md) • [配置项完整参考](docs/CONFIG_REFERENCE.md) • [项目结构说明](docs/PROJECT_STRUCTURE.md) • [桌面端兼容说明](docs/DESKTOP_COMPATIBILITY.md)

</div>

---

## 🚨 重要声明：防盗版与安全警告

> **本插件完全免费且开源，不会以任何形式进行商业收费！**
>
> 近期我们发现有人疑似在其他渠道贩卖本插件。在此郑重声明：
>
> - 本插件**永久免费、开源**，不存在任何付费版本，不会进行任何商业性收费行为
> - **唯一官方开源仓库**：[GitHub - Him666233/astrbot_plugin_group_chat_plus](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
> - **唯一官方获取渠道**：上述 GitHub 仓库 及 内部内测交流群（QQ群：1021544792）
> - 从其他渠道获取到的版本**可能被篡改并包含恶意代码或病毒**，请务必通过官方渠道获取，保障自身安全
>
> **如果有人向你收费或在非官方渠道分发本插件，请提高警惕！**

---

## ⚠️ 使用前必读

> **关闭AstrBot官方自带的主动回复功能！** 本插件的智能回复与官方主动回复是完全独立的两套系统，同时开启会导致重复回复、刷屏、API费用翻倍等问题。如果您有其他主动回复/主动对话类插件也建议关闭，避免冲突。

> **必须开启平台的“群聊上下文感知”！** 这是本插件正常工作的关键前提之一。不开启时，插件拿到的群聊历史与上下文信息会明显不完整，可能导致读空气判断失真、回复上下文错乱、主动对话判断不准，严重时会表现成“像没理解群里刚刚在聊什么”。推荐配置与原因说明见：[深度指南 → 平台配置](docs/ARCHITECTURE.md#推荐的平台设置)

> **图片处理须知：** 目前必须配置 `image_to_text_provider_id`（图片转文字提供商ID）才能正常处理图片。留空直接传递图片给多模态AI的方式目前无法可靠工作。

## ⚠️ 私聊功能警告

> **私聊处理功能目前仍在开发中，请勿开启 `enable_private_chat`！** 当前版本的私聊模块尚未完善，开启可能导致异常行为。请耐心等待后续版本正式支持。

---

## 📚 文档导航

> 不知道从哪里看起？根据你的需求选择对应的文档：

| 你想了解… | 去看这个文档 |
|-----------|-------------|
| **AI 回复太多/太少/读空气不准怎么调？** | [深度指南 → 常见问题排查](docs/ARCHITECTURE.md#ai-回复频率相关问题) |
| **某些 Skill / MCP 工具在开启插件后报参数错配怎么办？** | [深度指南 → 常见问题排查](docs/ARCHITECTURE.md#开启工具提醒后某些-skill--工具出现参数串扰怎么办) |
| **Web 管理面板怎么用？打不开怎么办？** | [深度指南 → Web 管理面板](docs/ARCHITECTURE.md#web-管理面板相关问题) |
| **插件的工作原理是什么？为什么要"偷天换日"？** | [深度指南 → 工作原理](docs/ARCHITECTURE.md#一句话概括) |
| **平台的"群聊上下文感知"和"自动理解图片"怎么配？** | [深度指南 → 平台配置](docs/ARCHITECTURE.md#推荐的平台设置) |
| **某个配置项是什么意思？默认值是多少？** | [配置项完整参考](docs/CONFIG_REFERENCE.md) |
| **一条消息从收到到回复经历了什么流程？** | [消息工作流程详解](docs/MESSAGE_WORKFLOW.md) |
| **代码文件结构和各模块职责？** | [项目结构说明](docs/PROJECT_STRUCTURE.md) |
| **使用 AstrBot 桌面端？重启不生效？路径找不到？** | [桌面端兼容说明](docs/DESKTOP_COMPATIBILITY.md) |
| **我用的其他插件和本插件会冲突吗？** | [深度指南 → 兼容性](docs/ARCHITECTURE.md#与其他插件的兼容性) |
| **如果 AstrBot 或其他插件改了内部提示词结构，会不会影响兼容？** | [深度指南 → 兼容性与回退机制](docs/ARCHITECTURE.md#system_prompt-兼容增强与保守回退机制) |
| **记忆插件怎么选？为什么推荐适配过的？** | [深度指南 → 记忆插件](docs/ARCHITECTURE.md#记忆插件的兼容性为什么要用适配过的记忆插件) |

---
## 🤝 插件合作

### AstrBot智能自学习插件

与 [astrbot_plugin_self_learning](https://github.com/NickCharlie/astrbot_plugin_self_learning) 建立官方合作关系：

- **本插件** 负责"智能决策何时回复" — AI读空气、动态概率、注意力机制
- **自学习插件** 负责"智能优化如何回复" — 对话风格学习、人格自动优化、好感度系统

两者功能互补，推荐组合使用。欢迎加入 **QQ群 1021544792** 交流！

### 工具参数串扰排查

如果你发现某些 Skill / MCP 工具在**关闭本插件时正常**、**开启本插件后更容易出现参数错配**，例如：

- `unexpected keyword argument 'silent'`
- `Tool handler parameter mismatch`
- 某个工具收到了明显属于另一个工具的参数

可以优先按这个顺序排查：

1. 确认 AstrBot 当前会话的 `provider_settings.tool_schema_mode`
   - `skills_like`：本插件现在会自动把工具提醒降级为“只展示工具名称与功能描述”
   - `full` / 旧版 AstrBot：仍会完整展示名称、描述和参数
2. 临时关闭 `enable_tools_reminder` 再复测一次
   - 如果问题明显缓解，通常说明是提醒层参数提示过细引发的串扰，而不是工具本身损坏
3. 对照报错工具的真实签名
   - 例如 `astrbot_execute_shell` 只接受 `command / background / env`
   - 如果日志里出现了明显属于其他工具的参数（如 Python 工具常见的 `silent`），就是典型串扰

更详细的背景说明和排障建议见：
- [深度指南 → 开启工具提醒后，某些 Skill / 工具出现参数串扰怎么办？](docs/ARCHITECTURE.md#开启工具提醒后某些-skill--工具出现参数串扰怎么办)

---

## 🆕 v1.2.2 更新亮点

**本次更新为三个判断型AI引入统一的"额外推理协议"，大幅提升判断准确率，同时完全向后兼容。**

### 判断型AI额外推理协议

| 功能 | 说明 |
|------|------|
| **读空气AI额外推理** | 开启 `enable_decision_ai_reasoning` 后，AI必须先在标志符内输出推理过程，再在最后一行单独给出 yes/no；推理块自动剥离不影响判定 |
| **主动对话判断AI额外推理** | 开启 `enable_proactive_ai_reasoning` 后，主动对话时机判断AI同样遵循“推理块 + 最后一行 yes/no”的严格协议，解析失败仍保持"跳过不进冷却"行为 |
| **频率判断AI额外推理** | 开启 `enable_frequency_ai_reasoning` 后，频率判断AI必须先输出推理块，再在最后一行单独给出「正常/过于频繁/过少」 |
| **共享起止标志符** | 三个AI共享同一套 `judgment_reasoning_start_marker` / `judgment_reasoning_end_marker`，默认 `[[GCP_REASONING_START]]` / `[[GCP_REASONING_END]]` |
| **推理过程日志** | 各AI独立配置是否将推理信息写到 AstrBot 日志（`decision_ai_reasoning_log` 等），并可选择 `processed`（处理后的推理块）或 `raw`（模型原始文本） |

**兼容说明**：额外推理开关默认仍为 `false`，新的日志输出模式默认值为 `processed`，完全向下兼容，旧配置无需修改。

### LivingMemory 人格ID兼容

- 新增 `livingmemory_persona_compat_mode`，用于兼容新版 `resolve_selected_persona`、旧版 `get_default_persona_v3` 以及更早期 `get_personas_by_key` 三套人格解析方式
- `livingmemory_version` 现已支持 `auto`，用于自动识别 LivingMemory 是 `v2 initializer` 架构还是 `v1` 直挂架构，避免手动选错版本
- 默认 `auto`，会自动按“新接口 -> 旧接口 -> 更旧接口”顺序回退，解决新版环境下 `PersonaManager` 不再提供 `get_personas_by_key` 导致的人格ID获取失败问题
- 如需排查特殊环境，可切换为 `resolver_only`、`legacy_only` 或 `off`
- Web 面板技术树里的「记忆注入」节点现已同步展示 `livingmemory_version` 与 `livingmemory_persona_compat_mode`，可直接在可视化界面调试兼容策略

---

## 🆕 v1.2.1 更新亮点

**本次更新带来了全新的 Web 管理面板，以及多项拟人化和智能化增强。**

### 全新 Web 管理面板

- **可视化配置管理** — 支持在 Web 界面直接修改插件配置，无需手动编辑 JSON
- **访问日志与统计** — 实时查看消息处理记录、回复统计图表、各群聊活跃度
- **IP 安全管理** — 白名单/黑名单/封禁管理，防爬虫自动封禁，IP 访问控制
- **Argon2id + JWT 认证保护** — Web 面板密码使用 Argon2id 内存硬化哈希，JWT + HttpOnly Cookie + 服务端会话表协同管理登录态，暴力破解分级锁定，会话安全
- **多设备并存登录** — 默认允许多设备/多浏览器并存登录，不会互踢；改密码、密码重置、非 Web 面板发起的服务端重启会统一使旧会话失效
- **心跳探测与缓冲重试** — 前台/后台低频心跳探测会话状态；网络异常时进入缓冲重试期，不会单次失败就立即判定断联；同一浏览器多标签页通过 Leader/Follower 协同，避免重复探测
- **JWT 密钥与密码物理分离** — JWT 签名密钥独立存储于 `jwt_secret.json`，与密码哈希文件隔离，防止单一泄露导致全面失守
- **Content-Security-Policy 严格防护** — 基于 nonce 的 CSP（script-src 不再使用 unsafe-inline），有效防御 XSS 注入攻击
- **敏感文件保护** — Web 文件管理 API 对认证文件、日志、封禁数据等敏感资源实施访问控制
- **安全边界配置只读展示** — `web_panel_trust_proxy`、`web_panel_ip_bind_check` 以及心跳频率/重试策略等安全敏感项只能在 AstrBot 传统配置界面修改，Web 面板中仅只读显示
- **配置文件名提示** — 在「配置流程图」和「核心设置」页面右下角显示当前实际配置文件名，便于确认正在编辑的目标配置
- **左上角插件版本显示** — 面板左上角会直接显示当前插件版本号，服务端从 `metadata.yaml` 安全读取并渲染，只输出版本文本，不向前端暴露插件目录或本地路径

> **技术树中的“共用配置”标签说明**
>
> 当且仅当同一个配置键会在 **两个或多个真实的技术树步骤配置面板** 中出现时，Web 技术树才会在该字段右上角显示“共用配置”标签，并在鼠标悬停时说明它与哪些入口共用。
>
> 当前主要包括：
> - `enable_smart_batch_reply_hint`：同时出现在 **AI决策判定 → 并发锁定** 和 **回复生成 → AI回复生成**
> - `judgment_reasoning_start_marker` / `judgment_reasoning_end_marker`：同时出现在 **概率判定系统 → 频率调整器**、**AI决策判定 → AI读空气决策**、**主动对话 → 概率与决策 → 主动对话预判断**
> - 内容过滤、打字错误模拟、回复延迟这三组共用后处理配置：同时出现在 **消息处理流水线** 的对应步骤，以及 **主动对话 → 共用处理** 下的对应步骤
>
> 这些标签只用于解释“为什么这里会重复出现”以及“它还出现在哪些入口”；它们指向的仍然是同一个真实配置值，在任意一处修改，其他共用入口都会同步生效。普通单入口配置项、仅结构上重复但并不会形成多个真实编辑入口的字段，不会显示这种标签。

### 新增功能

| 功能 | 说明 |
|------|------|
| **回复密度限制** | 限制短时间内(默认5min)最多回复次数，防止刷屏，超限后AI可感知 |
| **消息质量预判** | 疑问句/话题消息加权，纯水聊消息降权，动态调整回复概率 |
| **欢迎消息解析** | 解析群成员入群欢迎消息，可选是否跳过概率筛选直接处理 |
| **主动对话AI判断** | 主动发言前额外用AI判断当前时机是否合适，减少尬聊 |
| **忽略@全体成员** | 独立开关过滤@all消息，避免群公告等无效触发 |
| **@全体成员专用模式** | 在不忽略@all时，可单独选择跳过概率、跳过概率+读空气，或仅临时提升当前这条消息的概率 |
| **历史截止时间戳** | 执行插件清除指令后记录截止点，读取平台历史时自动过滤旧消息，解决 `/reset` 不清 platform_message_history 的问题 |
| **多工具调用兼容** | AI单次推理调用多个工具或多轮工具调用时，按实际执行顺序将文本与工具记录交错保存到历史 |

### 兼容性

- v1.2.0 的大部分行为保持兼容，但冷却相关旧键已进入迁移提示流程；如仍保留旧键，请按新键名调整配置
- 冷却状态改为运行态内存，插件重启后会清空；注意力/情绪等长期状态文件仍继续保留
- 所有新功能均有合理默认值，不影响现有行为

### 冷却机制升级与迁移说明

从本版本开始，注意力冷却机制有两点重要变化：

1. **旧兼容配置项已移除**
   - `attention_decrease_on_no_reply_step` → 改为 `attention_decay_on_no_reply_step`
   - `attention_decrease_threshold` → 改为 `attention_decay_on_no_reply_min_threshold`
   - `cooldown_attention_decrease` → 合并到独立未回复衰减语义，由 `attention_decay_on_no_reply_step` 表达
   - `enable_attention_decay_on_confirmed_no_reply` → 改为 `enable_attention_decay_on_no_reply`
   - `confirmed_no_reply_attention_decrease_step` → 改为 `attention_decay_on_no_reply_step`
   - `pending_cooldown_at_cancel_active` / `skip_no_reply_decay_during_pending_reconnect` → 已取消，行为改为内建固定规则

2. **冷却状态不再长期持久化**
   - 正式冷却和待冷却现在只保存在运行态内存中
   - 插件或平台重启后，冷却状态会自然清空
   - 注意力本体、情绪态度等长期数据仍继续保存在原有长期文件中，不受影响

如果插件启动时检测到旧版冷却配置项或旧版 `cooldown_data.json`，会在日志中输出迁移提示，并在后台自动把旧冷却数据迁入当前运行态内存，再安全清理旧冷却残留。

---


### 核心机制

- **AI读空气** — 两层过滤：概率筛选 + AI智能判断，精准控制回复时机；在 Smart 并发模式下，读空气判断也会参考当前消息之后紧接着到达的追加消息，而不是只看单条消息
- **动态概率系统** — 传统模式下回复后临时提升促进连续对话，时段概率模拟作息节奏；注意力模式开启后由注意力机制接管回复后加成
- **注意力机制** — 多用户同时追踪(0-1连续值)，指数衰减，情绪检测，注意力溢出；注意力冷却已升级为“候选冷却 → 正式冷却”的双阶段结构，专门减少普通概率路径消息的误伤；“读空气未回复衰减”改为独立机制，可在无冷却模式下单独生效，也可在冷却模式下与正式冷却协同（仅在开启注意力模式时生效）
- **智能缓存** — "缓存+转正"机制，未回复消息保留上下文，下次回复时自动合并；支持冷群自动转正，群聊长时间静默后自动将缓存写入历史，避免过期丢失
- **记忆系统** — 支持 LivingMemory（混合检索+人格隔离）和 Legacy 双模式，auto 模式自动检测适配插件
- **并发协调** — 群聊支持 legacy / smart 两种并发模式；smart 会按真实到达顺序选主消息并批量感知追加消息，legacy 保持传统串行兜底；普通对话、主动对话、冷群转正之间自动互斥，无需额外配置
- **Smart批次回复提示增强** — 可选开关。开启后，Smart 模式下回复阶段会动态提示 AI：当前触发对象仍是主要回复对象，但可以像真人一样自然顺带回应批次中的其他消息；不值得回的消息也可以忽略。该提示只存在于运行时，保存历史前会自动过滤

### 社交行为

- **主动对话** — 沉默后AI自然发起话题，自适应互动评分系统，越聊越开心
- **对话疲劳** — 连续对话后逐渐降低回复倾向，模拟真人节奏
- **拟人增强** — 沉默状态机、兴趣话题检测、决策历史一致性
- **吐槽系统** — 连续被无视时AI会"吐槽"，让Bot更有性格

### 真实感增强

- **打字错误** — 基于拼音相似性的自然错别字 (默认2%概率)
- **情绪系统** — 根据对话检测情绪状态，影响回复语气
- **回复延迟** — 模拟打字速度，避免秒回
- **频率调整** — 自动分析群聊节奏，动态调整基础回复频率；与传统回复后提升解耦，可在提升结束后继续维持基础概率修正

### 消息处理

- **图片处理** — 支持图片转文字，可配置范围，结果自动缓存
- **转发解析** — 面向 QQ / OneBot 场景解析合并转发消息，支持在深度限制内展开嵌套转发，并将整条转发内容折叠为单条可读文本继续参与后续 AI 流程
- **关键词系统** — 触发词跳过概率/智能模式，黑名单词直接过滤
- **戳一戳** — 智能响应QQ戳一戳，支持反戳和回复后戳；对本插件**实际接手处理**的真实戳一戳事件，会自动把“谁戳了谁”的事件语义保留到历史上下文中，便于后续AI理解。启用“戳过对方追踪提示”后，还会在短时间内追踪被AI戳过的用户；若追踪人数超过上限，会移除当前最早登记的记录。此行为无独立配置项，是否生效取决于当前 `poke_message_mode`、平台是否为 QQ+aiocqhttp/OneBot poke notice，以及该群是否允许本插件处理戳一戳消息
- **@消息优先** — @机器人消息跳过所有判断直接回复；`@全体成员` 与 `@他人过滤` 独立处理，可单独配置为按普通消息处理、跳过概率筛选、跳过概率+读空气，或仅对当前这条消息临时提升概率；对于单独的、不包含任何信息的 @ 消息，系统会默认启用中性上下文强化，并在通过前置过滤与读空气筛选后，再提醒 AI 优先参考最近上下文但不要强行续话；这层关联会同时受时间窗口和消息数窗口约束。`@全体成员` 的解析说明会随消息一起保存，供后续缓存转正与历史上下文继续使用

### 安全与管理

- **指令过滤** — 自动跳过 `/help` 等指令消息
- **用户黑名单** — 屏蔽特定用户
- **@他人过滤** — 避免插入他人私密对话
- **重复拦截** — 防止AI发送重复内容
- **内容过滤** — 发送前/保存前过滤AI输出
- **桌面端兼容** — 自动检测 AstrBot 桌面端环境，适配重启机制差异（[详细说明](docs/DESKTOP_COMPATIBILITY.md)）

---

## 🚀 快速开始

### 安装

1. 在 AstrBot 插件市场搜索安装，或下载本仓库放入 `/data/plugins` 目录
2. 安装依赖：`pip install pypinyin`
3. 重启 AstrBot，在插件管理面板中配置

> **Web 面板认证文件说明**：当前版本将认证数据拆分为两个独立文件——`web_data/auth.json`（密码哈希）和 `web_data/jwt_secret.json`（JWT 密钥），实现物理隔离。如果你是从旧版升级，且旧版的 `auth.json` 中同时包含密码和 JWT secret，系统会在启动时自动分离到独立文件，无需手动操作。若旧版密码文件保存在插件数据**根目录**下（而非 `web_data/` 子目录），请先将其移动到 `web_data/auth.json` 后再启动。
>
> **密码哈希升级说明**：1.2.2版本起，Web 面板密码默认使用 `Argon2id` 内存硬化哈希。旧版本 `PBKDF2-SHA256` 密码数据无需手动迁移，用户使用原密码首次登录成功后会自动透明升级到 `Argon2id`。无论是用户自定义密码，还是重置后生成的默认随机密码，都支持无缝跨版本升级。
>
> **Web 面板会话补充说明**：当前版本的 Web 面板会话已升级为 `JWT + HttpOnly Cookie + 服务端会话表`。登录页遇到有效会话时会直接跳转到面板；若检测到令牌过期、密码已修改、服务端重启或（开启 `web_panel_ip_bind_check` 时）IP 变化，会统一要求重新登录。前台/后台心跳频率、失败重试基准与最大重试间隔现已提供独立配置项，但这些参数属于安全敏感配置，只能通过 AstrBot 传统配置界面修改，Web 面板中为只读显示。
>
> **反向代理补充说明**：如果反向代理与 Web 面板部署在同一台机器，系统在检测到连接来源为 `127.0.0.1 / ::1` 时会自动读取 `X-Real-IP / X-Forwarded-For` 获取真实客户端 IP，因此即使未开启 `web_panel_trust_proxy`，也可能正常拿到真实 IP；若反向代理不在本机，则需要显式开启 `web_panel_trust_proxy` 才会信任代理头。该项现已归类为安全边界配置，只能在传统配置界面修改。
>
> **默认密码安全提醒**：首次安装或重置密码后，系统会以 WARNING 级别向 AstrBot 日志输出默认密码及安全警告。请务必登录后立即修改为自定义密码——修改后明文副本将自动删除，日志中也不再输出任何密码信息。

> **使用打包启动器部署的用户请注意**：若启动后报错 `ModuleNotFoundError: No module named 'aiohttp'`，请额外执行 `pip install aiohttp>=3.8.0`（详见下方依赖说明）。

### 依赖要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| AstrBot | >= v4.11.0 | 平台框架 |
| `pypinyin` | >= 0.44.0 | 打字错误生成器（拼音相似性），**需手动安装** |
| `argon2-cffi` | >= 23.1.0 | Web 面板密码哈希（Argon2id），插件会随 `requirements.txt` 自动安装 |
| `aiohttp` | >= 3.8.0 | Web 管理面板 HTTP 服务器，通常由 AstrBot 平台自动安装，**无需手动安装** |

> **关于 `aiohttp`**：该库是 AstrBot 平台本身的核心依赖，通过 pip 或源码方式部署时，AstrBot 在安装时会自动包含此依赖，插件本身无需重复声明。但若使用 **AstrBot 新版打包启动器（exe/独立包）** 进行部署，平台依赖可能未完整暴露给插件环境，此时需要手动安装：`pip install aiohttp>=3.8.0`

- **推荐**: `astrbot_plugin_livingmemory` 或 `astrbot_plugin_play_sy` (记忆系统)

---

### 关于 platform_message_history 历史消息清除

AstrBot 的 `/reset` 指令只清除 `conversations` 表，**不会**清除 `platform_message_history` 表，导致旧历史消息可能被 AI 持续读取。

**本插件的解决方案**：执行 `gcp_reset` 或 `gcp_reset_here` 指令后，插件会记录一个截止时间戳。此后从平台历史读取消息时，截止点之前的所有消息都会被自动过滤——表里的数据虽然还在，但 AI 看不到，效果等同于已清除。

**如需彻底清除数据库中的历史记录**，有两种方式：

> ⚠️ `platform_message_history` 存储在 `data/data_v4.db`（SQLite），同一数据库还存有人格配置、会话记录、插件配置等所有平台数据。**不建议直接删除 data_v4.db**，否则所有数据全部丢失。

**方式一（推荐）：仅清除 platform_message_history 表**

```bash
sqlite3 data/data_v4.db "DELETE FROM platform_message_history;"
```

**方式二：使用插件清除指令（推荐日常使用）**

执行 `gcp_reset_here` 后，插件记录截止时间戳，之后 AI 不再读取截止点之前的旧消息，无需操作数据库。

> **说明**：这是 AstrBot 平台层面的设计遗漏（`/reset` 未清理 `platform_message_history`），本插件通过截止时间戳机制在插件层进行了修复。

---

## 🎯 完整推荐配置（保守版）

以下是当前版本的全功能推荐配置，偏保守方向调整，AI不会过于频繁发言但也不会完全沉默，适合大多数群聊场景。

> 说明：示例里同时保留了 `after_reply_probability` 与 `probability_duration`，它们只在**传统模式**（`enable_attention_mechanism = false`）下生效；若开启注意力机制，则回复后加成会改由注意力机制按用户接管。

> 所有配置项的详细说明均可在 AstrBot 插件配置面板中查看，此处仅列出推荐值。

```json
{
  "enable_group_chat": true,
  "enabled_groups": [],
  "enable_debug_log": false,

  "decision_ai_provider_id": "",
  "initial_probability": 0.08,
  "after_reply_probability": 0.8,
  "probability_duration": 120,
  "decision_ai_prompt_mode": "append",
  "decision_ai_extra_prompt": "",
  "decision_ai_timeout": 30,
  "reply_timeout_warning_threshold": 120,
  "reply_generation_timeout_warning": 60,
  "concurrent_wait_max_loops": 15,
  "concurrent_wait_interval": 5.0,
  "concurrent_mode": "legacy",
  "enable_smart_batch_reply_hint": true,
  "smart_concurrent_merge_wait": 30.0,
  // 说明：当 concurrent_mode=smart 且开启 enable_smart_batch_reply_hint 时，
  // 回复阶段会动态提示 AI：当前触发对象仍是主要回复对象，但可以自然顺带回应批次中的其他消息；
  // 这类提示只存在于运行时，保存历史前会自动过滤
  "reply_ai_prompt_mode": "append",
  "reply_ai_extra_prompt": "",
  // 说明：reply_ai_extra_prompt 用于“生成最终回复内容”的运行时提示词，
  // 建议保持“直接生成要发出去的话”的职责边界，不要写成 yes/no 判断口吻；
  // 默认提示词预览仅在 Web 面板对应配置项中展示，传统配置页面不会显示
  // 这类提示词只参与当次生成，不应作为普通历史正文保存

  "include_timestamp": true,
  "include_sender_info": true,
  "enable_forward_message_parsing": false,
  "forward_max_nesting_depth": 3,
  "enable_welcome_message_parsing": false,
  "welcome_message_mode": "skip_probability",
  "max_context_messages": -1,
  "custom_storage_max_messages": 500,
  "pending_cache_max_count": 20,
  "pending_cache_ttl_seconds": 1800,

  "enable_image_processing": true,
  "image_to_text_scope": "mention_only",
  "image_to_text_provider_id": "你的图片转文字AI提供商ID",
  "image_to_text_prompt": "请详细描述这张图片的内容",
  "image_to_text_timeout": 60,
  "max_images_per_message": 10,
  "enable_image_description_cache": true,
  "image_description_cache_max_entries": 500,
  "platform_image_caption_max_wait": 2.0,
  "platform_image_caption_retry_interval": 2,
  "platform_image_caption_fast_check_count": 10,
  "probability_filter_cache_delay": 10000,

  "enable_emoji_filter": true,
  "emoji_probability_decay": 0.7,
  "emoji_decay_min_probability": 0.05,

  "enable_memory_injection": true,
  "memory_plugin_mode": "auto",
  "livingmemory_version": "auto",
  "livingmemory_persona_compat_mode": "auto",
  "livingmemory_top_k": 5,
  "memory_insertion_timing": "pre_decision",

  "enable_tools_reminder": false,
  "tools_reminder_persona_filter": false,
  // 说明：若 AstrBot 当前会话使用 provider_settings.tool_schema_mode=skills_like，
  // 工具提醒会自动只展示工具名称与功能描述，不再展开参数列表

  "trigger_keywords": ["填写你的AI角色名字/别名"],
  "keyword_smart_mode": true,
  "blacklist_keywords": [],

  "enable_user_blacklist": false,
  "blacklist_user_ids": [],

  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#"],
  "enable_full_command_detection": true,
  "full_command_list": ["new", "help", "reset"],
  "enable_command_prefix_match": false,
  "command_prefix_match_list": [],

  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": false,
  "poke_bot_probability_boost_reference": 0.3,
  "poke_reverse_on_poke_probability": 0.0,
  "enable_poke_after_reply": true,
  "poke_after_reply_probability": 0.1,
  "poke_after_reply_delay": 0.5,
  "enable_poke_trace_prompt": true,
  "poke_trace_max_tracked_users": 5,
  "poke_trace_ttl_seconds": 300,
  "poke_enabled_groups": [],

  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "enable_ignore_at_all": true,

  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.8,
  "attention_decreased_probability": 0.08,
  "attention_duration": 120,
  "attention_max_tracked_users": 10,
  "attention_decay_halflife": 300,
  "emotion_decay_halflife": 600,
  "attention_boost_step": 0.35,
  "attention_decrease_step": 0.12,
  "enable_attention_decay_on_no_reply": true,
  "attention_decay_on_no_reply_step": 0.2,
  "attention_decay_on_no_reply_min_threshold": 0.3,
  "emotion_boost_step": 0.1,
  "enable_attention_emotion_detection": true,
  "attention_enable_negation": true,
  "attention_positive_emotion_boost": 0.1,
  "attention_negative_emotion_decrease": 0.15,
  "enable_attention_spillover": true,
  "attention_spillover_ratio": 0.3,
  "attention_spillover_decay_halflife": 90,
  "attention_spillover_min_trigger": 0.4,
  "enable_attention_cooldown": true,
  "enable_cooldown_auto_release": true,
  "cooldown_max_duration": 600,
  "cooldown_trigger_threshold": 0.3,
  "enable_pending_attention_cooldown": true,
  "pending_cooldown_grace_user_messages": 1,
  "pending_cooldown_max_wait_seconds": 60,
  "pending_cooldown_same_user_probability_floor": 0.18,

  "enable_conversation_fatigue": true,
  "fatigue_reset_threshold": 300,
  "fatigue_threshold_light": 3,
  "fatigue_threshold_medium": 5,
  "fatigue_threshold_heavy": 8,
  "fatigue_probability_decrease_light": 0.15,
  "fatigue_probability_decrease_medium": 0.25,
  "fatigue_probability_decrease_heavy": 0.4,
  "fatigue_closing_probability": 0.35,

  "enable_typo_generator": true,
  "typo_error_rate": 0.02,

  "enable_mood_system": true,
  "enable_negation_detection": true,
  "mood_decay_time": 300,
  "mood_cleanup_threshold": 3600,
  "mood_cleanup_interval": 600,

  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 20,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 15,
  "frequency_min_message_count": 5,
  "frequency_decrease_factor": 0.85,
  "frequency_increase_factor": 1.1,
  "frequency_min_probability": 0.03,
  "frequency_max_probability": 0.85,

  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,

  "enable_proactive_chat": true,
  "proactive_silence_threshold": 1800,
  "proactive_probability": 0.2,
  "proactive_check_interval": 120,
  "proactive_require_user_activity": true,
  "proactive_min_user_messages": 3,
  "proactive_user_activity_window": 300,
  "proactive_max_consecutive_failures": 3,
  "proactive_cooldown_duration": 2400,
  "proactive_enable_quiet_time": true,
  "proactive_quiet_start": "23:00",
  "proactive_quiet_end": "07:00",
  "proactive_transition_minutes": 30,
  "proactive_use_attention": true,
  "proactive_temp_boost_probability": 0.4,
  "proactive_temp_boost_duration": 120,
  "proactive_enabled_groups": [],
  "enable_proactive_at_conversion": false,
  "enable_proactive_ai_judge": true,
  "proactive_ai_judge_timeout": 15,

  "enable_adaptive_proactive": true,
  "score_increase_on_success": 15,
  "score_decrease_on_fail": 10,
  "score_quick_reply_bonus": 5,
  "score_multi_user_bonus": 10,
  "score_streak_bonus": 5,
  "score_revival_bonus": 20,
  "interaction_score_decay_rate": 2,
  "interaction_score_min": 10,
  "interaction_score_max": 100,

  "enable_complaint_system": true,
  "complaint_trigger_threshold": 2,
  "complaint_decay_on_success": 2,
  "complaint_max_accumulation": 15,

  "enable_dynamic_reply_probability": true,
  "reply_time_periods": "[{\"name\":\"深夜睡眠\",\"start\":\"23:00\",\"end\":\"07:00\",\"factor\":0.2},{\"name\":\"午休时段\",\"start\":\"12:00\",\"end\":\"14:00\",\"factor\":0.5},{\"name\":\"晚间活跃\",\"start\":\"19:00\",\"end\":\"22:00\",\"factor\":1.3}]",
  "reply_time_transition_minutes": 30,
  "reply_time_min_factor": 0.1,
  "reply_time_max_factor": 2.0,
  "reply_time_use_smooth_curve": true,
  "enable_probability_hard_limit": false,

  "enable_reply_density_limit": true,
  "reply_density_window_seconds": 300,
  "reply_density_max_replies": 4,
  "reply_density_soft_limit_ratio": 0.6,
  "reply_density_ai_hint": true,

  "enable_message_quality_scoring": true,
  "message_quality_question_boost": 0.1,
  "message_quality_water_reduce": 0.1,

  "enable_dynamic_proactive_probability": true,
  "proactive_time_periods": "[{\"name\":\"深夜睡眠\",\"start\":\"23:00\",\"end\":\"07:00\",\"factor\":0.2},{\"name\":\"午休时段\",\"start\":\"12:00\",\"end\":\"14:00\",\"factor\":0.5},{\"name\":\"晚间活跃\",\"start\":\"19:00\",\"end\":\"22:00\",\"factor\":1.3}]",
  "proactive_time_transition_minutes": 45,
  "proactive_time_min_factor": 0.0,
  "proactive_time_max_factor": 2.0,
  "proactive_time_use_smooth_curve": true,

  "enable_humanize_mode": true,
  "humanize_silent_mode_threshold": 3,
  "humanize_silent_max_duration": 600,
  "humanize_silent_max_messages": 8,
  "humanize_enable_dynamic_threshold": true,
  "humanize_base_message_threshold": 1,
  "humanize_max_message_threshold": 3,
  "humanize_include_decision_history": true,
  "humanize_interest_keywords": ["填写AI感兴趣的话题关键词"],
  "humanize_interest_boost_probability": 0.25,

  "enable_output_content_filter": false,
  "output_content_filter_rules": [],
  "enable_save_content_filter": false,
  "save_content_filter_rules": [],

  "enable_group_wait_window": true,
  "group_wait_window_timeout_ms": 3000,
  "group_wait_window_max_extra_messages": 3,
  "group_wait_window_max_users": 5,
  "group_wait_window_attention_decay_per_msg": 0.05,
  "group_wait_window_at_mode": "force_close",
  "group_wait_window_keyword_mode": "intercept",
  "group_wait_window_poke_mode": "bypass",
  "group_wait_window_merge_at_list_mode": "whitelist",
  "group_wait_window_merge_at_user_list": [],

  "enable_duplicate_filter": true,
  "duplicate_filter_check_count": 5,
  "enable_duplicate_time_limit": true,
  "duplicate_filter_time_limit": 1800,

  "enable_private_chat": false
}
```

> **配置要点：**
> - `enabled_groups` 留空 = 所有群聊启用，填写群号 = 仅指定群组启用
> - `trigger_keywords` 填写你AI角色的名字/别名，让别人叫它时更容易触发回复
> - `humanize_interest_keywords` 填写AI感兴趣的话题关键词，检测到时提升回复概率
> - `image_to_text_provider_id` **必须填写**你的图片转文字AI提供商ID，否则图片处理无法工作
> - `decision_ai_provider_id` 留空使用默认提供商，建议使用轻量快速的模型
> - `concurrent_mode` 默认推荐保留 `legacy`；如果你更在意连续多条消息的一体化理解，可切到 `smart`
> - `smart_concurrent_merge_wait` 仅在 `smart` 模式下生效，用于控制批次等待清理时间；它不依赖 GWW
> - 主动对话与普通对话之间的并发互斥是内部自动生效的，不需要单独配置；未开启主动对话时，这套保护不会额外影响普通群聊流程
> - `memory_plugin_mode` 默认 `"auto"` 会自动检测已安装的记忆插件（优先 LivingMemory → 回退 Legacy → 都没有则跳过），无需手动选择
> - `reply_time_periods` 和 `proactive_time_periods` 的值为 JSON 字符串格式
> - `enable_private_chat` **必须保持 false**，私聊功能尚未完善
> - 如果你使用 **注意力模式**（`enable_attention_mechanism = true`），`after_reply_probability` 会被注意力机制替代，注意力溢出、注意力冷却、对话疲劳等注意力专属机制才会参与
> - 如果你使用 **传统模式**（`enable_attention_mechanism = false`），`after_reply_probability` 会作为群聊会话级的回复后临时提升；再次成功回复会刷新 `probability_duration` 计时，且后续仍会继续受到动态时间段、消息质量、回复密度、概率硬限制等后置机制影响
> - `enable_probability_hard_limit` 属于最终后置限制层；开启后，无论前面是传统模式还是注意力模式，最终概率都会被截断到 `[probability_min_limit, probability_max_limit]`
> - 本推荐配置当前默认启用了注意力模式；如需切回传统模式，建议同时关闭 `enable_attention_mechanism`，再重点调整 `after_reply_probability` 与 `probability_duration`
> - 本推荐配置偏保守，AI发言频率较低，如需更活跃可适当提高 `initial_probability`；若使用传统模式，也可适当提高 `after_reply_probability`
> - 其他所有配置项的详细说明均可在 AstrBot 插件配置面板中直接查看

---

## 并发处理机制

### 两种并发处理模式

通过 `concurrent_mode` 配置可以切换两种并发处理策略：

#### legacy 模式（默认）

同一群聊同时收到多条消息时，新消息等待旧消息处理完再依次独立处理，每条消息各自调用 AI 并各自回复。

```
消息A → 处理中（6-8秒 AI 调用）→ 回复A
消息B →     等待中...         → 等待完成 → 处理消息B → 回复B
```

特点：简单可靠，向后兼容，是最兜底的并发保护模式；但可能产生逐条回复的重复感。

#### smart 模式

smart 模式会先按**真实到达顺序**登记消息，再由最早到达的消息担任主消息（anchor）。主消息在进入读空气 AI 前，就会吸收当前消息之后紧接着到达、且已准备好的后续消息；这些追加消息可能来自**不同用户**。

```
消息A(先到) → arrival_seq=1 → 完成前置处理
消息B(后到) → arrival_seq=2 → 完成前置处理
    ↓
消息A 成为 anchor
    → 在读空气AI之前吸收消息B
    → 消息B 标记为 consumed，不再独立处理
    → DecisionAI / ReplyAI 都看到同一批上下文
    ↓
AI 一次性感知 A + 追加消息B → 生成统一回复
```

追加消息会复用“当前消息后紧接着又收到的消息”这套上下文表达，保留发送者名字、ID 与时间信息（若相关配置开启），让 AI 自己判断这些消息是否需要一并参考。

### Smart 与群聊等待窗口（GWW）的关系

- **两者可以配合，但互不依赖**
- GWW 负责“同一用户短时间内连续拆分消息”的补收集
- Smart 负责“同群并发消息按真实顺序批处理”
- 即使不开 GWW，Smart 也能独立工作
- 进入 GWW 的消息不会再进入 Smart 批处理流程
- 窗口追加消息区域会复用 GWW 的展示增强逻辑：基础 `@` 解析会展开为 `[At:ID|解析结果]`，`@全体` 会补充说明，持久化戳一戳事件文本也会显示给 AI；但主消息专用的 `[系统提示]` / `【@指向说明】` 不会直接塞进追加消息区

### 主动对话与普通对话的协调

主动对话、普通对话、冷群转正之间现在会自动做会话级互斥：

- **普通对话优先级最高**：用户新消息一来，普通回复链优先处理
- **主动对话自动避让**：主动对话开始前会检查当前群聊是否已有普通对话在处理
- **冷群转正最低优先级**：只有在群聊没有普通对话 / 主动对话占用时才执行
- 这套协调是**内部强制生效**的，不需要新增任何配置；如果没开启主动对话功能，这部分保护基本不会参与

### 动态提示词说明

在 Smart 并发、主动对话预判断、主动对话生成等场景下，插件会按需动态插入“追加消息 / 多用户 / 顺序参考”提示词：

- 这些提示词**不是写死**在总系统提示词里的
- 只有相关场景真正发生时才会插入
- 保存历史时会自动过滤，不会污染长期上下文
- **不影响图片转文字 AI**，图片转文字相关配置和职责保持不变

### 判断型AI与人格的独立控制

现在三个判断型AI都支持各自独立控制是否包含人格，以及可选地指定一个“只给这个判断AI使用的人格”：

- **读空气AI**：判断当前消息该不该回复
- **主动对话判断AI**：判断当前时机适不适合主动开口
- **频率判断AI**：判断整体发言频率是正常、过多还是过少

默认行为不变：这三个判断型AI默认仍会跟随**当前会话当前生效的人格**。

但如果你的某个人格写得更偏“角色扮演”或强情绪表达，导致判断型AI容易把自己理解成正在演角色，而不是做纯判断任务，就可以：

1. 保持默认的回复生成AI不变
2. 只对这三个判断型AI单独关闭人格注入，或单独指定一个更适合做判断的人格

#### 为什么只有这三个AI支持独立人格？

因为它们的职责都是“做判断”，而不是“直接生成要发出去的话”。

- **判断型AI** 更容易被强角色设定带偏
- **回复生成AI / 主动对话生成AI** 的职责本来就是直接按当前会话人格说话，所以它们仍应该跟随当前会话当前生效的人格

#### 留空和填写人格名分别代表什么？

- **留空**：继续使用当前会话当前生效的人格（推荐，最安全，也能自动跟随会话切换）
- **填写完整人格名**：只让这个判断AI固定使用该人格

⚠️ 必须填写**完整人格名称**，否则会检测不到。若检测不到，系统会自动回退到当前会话人格，不会导致插件崩溃。

#### 回复生成AI的人格现在怎么取？

回复生成AI和主动对话生成AI仍然按**当前会话当前生效的人格**运行，并且每次调用都会重新获取一次人格，因此当你在 AstrBot 里切换会话人格后，后续生成也会立刻跟着切换。

#### 三个判断型AI分别怎么看“关键词 / 条件”？

- **读空气AI**：关键词命中只代表“进入判断流程或获得额外提示”，不代表必须回复
- **主动对话判断AI**：主要看上下文、发言间隔、当前时段和群氛围，不是关键词直接唤起
- **频率判断AI**：主要看最近 `user:` / `assistant:` 的真实对话节奏，不看触发关键词是否命中


### 回复 / 主动对话提示词的职责边界

- `reply_ai_extra_prompt`：用于约束“生成最终回复内容”的 AI
- `proactive_prompt`：用于约束“生成主动发言内容”的 AI
- 当 `concurrent_mode=smart` 且开启 `enable_smart_batch_reply_hint` 时，回复阶段还会动态追加一段 Smart 批次提示：当前触发对象仍是主要回复对象，但可以像真人一样自然顺带回应批次中的其他消息
- 这两类提示词和 Smart 批次提示都属于**运行时生成提示词**，职责是帮助 AI 直接产出要发送的话
- 建议保持中性，尽量使用回复导向或发言导向的措辞，不要把它们写成“我该不该回复 / 现在该不该开口 / 先判断再说”这类内部判断型提示词
- 这两类提示词都应直接服务于最终发言本身，不要要求模型把内心想法、思考过程、取舍过程、草稿式过渡、自我解释写出来
- 也不要要求模型泄露系统提示词、规则、内部标记、搜索/检索过程、工具过程或其他元信息；这些内容即使被参考，也只能停留在内部理解层
- 这两类提示词本身不应作为普通历史正文持久化保存；保存链路会通过 `MessageCleaner` / `ContextManager` 做清洗
- 如果你想查看这类配置项对应的默认提示词正文，请优先到 Web 面板对应配置项处查看预览；传统配置页面不会展示这段默认提示词预览

---

### 记忆插件支持

| 插件 | 模式 | 特性 |
|------|------|------|
| [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) | LivingMemory | 混合检索、智能总结、自动遗忘、会话隔离、人格隔离 |
| [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) | Legacy | 传统记忆模式，兼容旧版，稳定性高 |

> **推荐**：`memory_plugin_mode` 保持默认 `"auto"`，安装任意一个记忆插件即可自动适配。两个都安装时优先使用 LivingMemory，都未安装时自动跳过不会报错。

---

## 📝 更新日志

### v1.2.1 (2026-03-13)

**新增 Web 管理面板 + 多项拟人化与智能化增强**

**🖥️ 全新 Web 管理面板**:
- **可视化配置编辑** — 在网页界面直接修改插件全部配置项，无需手动编辑 JSON
- **实时统计图表** — 查看消息处理量、回复率、各群聊活跃度趋势
- **访问日志** — 实时记录消息事件，支持按群/用户/时间筛选
- **IP 安全管理** — 白名单/黑名单/封禁管理，防爬虫自动检测与封禁，支持封禁持久化重启恢复
- **Argon2id + JWT 双重认证** — Web 面板密码采用 Argon2id 内存硬化哈希，Bearer Token + Cookie，暴力破解分级锁定（5/10/15/20次 → 30/60/300/600秒），会话安全可靠
- **技术树可视化** — 功能关联图谱，直观了解各模块工作流程

**🆕 新增功能**:
- **回复密度限制** — 滑动窗口统计短时间内回复次数（默认5分钟内4次），超过软限制时降低概率，达到硬限制后停止回复；支持向AI注入提示说明当前状态
- **消息质量预判** — 对疑问句/话题性消息加权提升回复概率，对纯水聊/复读消息降权；让AI更愿意回应有价值的消息
- **欢迎消息解析** — 自动识别群成员入群欢迎消息，可配置为直接跳过概率筛选或完整AI判断流程
- **主动对话AI判断** — 在主动发言前增加一层AI判断，分析当前群聊气氛是否适合打招呼，减少不合时宜的主动发言
- **忽略@全体成员** — 新增 `enable_ignore_at_all` 独立开关，避免群公告/管理通知等@all消息触发AI
- **历史截止时间戳** — 执行 `gcp_reset` 或 `gcp_reset_here` 后，在 `history_cutoff.json` 记录当前时间作为截止点；从 `platform_message_history` 读取历史时自动过滤截止点之前的消息。这解决了 AstrBot 平台 `/reset` 指令只清 `conversations` 表、不清 `platform_message_history` 表导致的旧消息残留问题——执行插件清除指令后，旧历史虽然仍存在于数据库，但对 AI 来说等同于已清除
- **多工具调用兼容** — AI 在单次推理中调用多个工具或发生多轮工具调用时，按实际执行顺序将 AI 中间文本与工具调用记录（调用名称+参数+返回值）交错保存到对话历史；兼容 ToolCall 对象和 dict 两种格式，支持无最终文本输出时的兜底保存

**🔧 兼容性**:
- v1.2.0 的大部分行为保持兼容，但冷却相关旧键已进入迁移提示流程；如仍保留旧键，请按新键名调整配置
- 冷却状态改为运行态内存，插件重启后会清空；注意力/情绪等长期状态文件仍继续保留
- 所有新功能均有合理默认值，不影响现有行为

**修改文件**:
- `web/` — **新增** 完整 Web 管理面板（server.py / auth.py / security.py / templates / static）
- `utils/reply_density_manager.py` — **新增** 回复密度管理器
- `utils/message_quality_scorer.py` — **新增** 消息质量预判器
- `utils/welcome_message_parser.py` — **新增** 欢迎消息解析器
- `main.py` — 集成新模块，新增相关配置项读取
- `_conf_schema.json` — 新增 10+ 个配置项
- `metadata.yaml` — 更新版本号到 v1.2.1

---

> 📋 **[查看完整更新日志 →](CHANGELOG.md)**

---

## 🤝 贡献与反馈

如遇问题请开启 `enable_debug_log` 获取详细日志后在 [GitHub Issues](https://github.com/Him666233/astrbot_plugin_group_chat_plus/issues) 提交，欢迎 Pull Request！

也欢迎加入 **QQ群 1021544792** 进行交流、反馈Bug和功能建议！

---

## 📜 许可证

本项目采用 **AGPL-3.0 License** 开源协议。

---

## 🙏 致谢

### 灵感来源

> 本插件的开发从以下开源项目中获得了灵感，特此感谢。我们并未直接使用其代码，但借鉴了其优秀的功能设计：

- [astrbot_plugin_SpectreCore](https://github.com/23q3/astrbot_plugin_SpectreCore) — 作者：23q3
- [MaiBot](https://github.com/MaiM-with-u/MaiBot) — 作者：Mai.To.The.Gate 组织及众多贡献者

### 记忆插件

> 本插件支持两种记忆插件，优秀的记忆系统让AI的判断和回复更加智能，特此感谢：

- **智能：** [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) — 作者：lxfight's Astrbot Plugins 组织及众多贡献者
- **传统(推荐)：** [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) — 作者：kjqwdw

### 其他

- [astrbot_plugin_restart](https://github.com/Zhalslar/astrbot_plugin_restart) — 重启功能参考，作者：Zhalslar
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) — 优秀的Bot框架

---

## 👤 作者

**Him666233** — [@Him666233](https://github.com/Him666233)

---

## ⭐ Star History

如果这个插件对你有帮助，请给个Star支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=Him666233/astrbot_plugin_group_chat_plus&type=Date)](https://star-history.com/#Him666233/astrbot_plugin_group_chat_plus&Date)

---

<div align="center">

Made with ❤️ by Him666233

</div>
