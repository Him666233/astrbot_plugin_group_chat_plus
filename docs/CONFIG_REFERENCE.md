# 配置项完整参考

> 本文档列出了群聊增强插件的**所有配置项**，包含类型、默认值和详细说明。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程](MESSAGE_WORKFLOW.md) | [项目结构](PROJECT_STRUCTURE.md) | [桌面端兼容](DESKTOP_COMPATIBILITY.md)

---

## 目录

- [基础设置](#基础设置)
- [Web 管理面板](#web-管理面板)
- [桌面端兼容](#桌面端兼容)
- [概率与决策系统](#概率与决策系统)
- [消息格式与上下文](#消息格式与上下文)
- [消息缓存](#消息缓存)
- [图片处理](#图片处理)
- [关键词系统](#关键词系统)
- [用户黑名单](#用户黑名单)
- [指令过滤](#指令过滤)
- [@消息处理](#消息处理)
- [戳一戳系统](#戳一戳系统)
- [转发消息解析](#转发消息解析)
- [欢迎消息解析](#欢迎消息解析)
- [群聊等待窗口](#群聊等待窗口)
- [表情过滤](#表情过滤)
- [消息质量预判](#消息质量预判)
- [回复密度限制](#回复密度限制)
- [注意力机制](#注意力机制)
- [对话疲劳](#对话疲劳)
- [动态时段概率](#动态时段概率)
- [拟人模式](#拟人模式)
- [主动对话](#主动对话)
- [自适应互动评分](#自适应互动评分)
- [主动对话时段概率](#主动对话时段概率)
- [吐槽系统](#吐槽系统)
- [情绪系统](#情绪系统)
- [频率调整器](#频率调整器)
- [打字模拟](#打字模拟)
- [打字错误生成](#打字错误生成)
- [重复过滤](#重复过滤)
- [记忆系统](#记忆系统)
- [工具提示](#工具提示)
- [内容过滤](#内容过滤)
- [回复生成](#回复生成)
- [历史管理指令](#历史管理指令)
- [私聊功能（开发中）](#私聊功能开发中)

---

## 基础设置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_group_chat` | bool | `true` | **总开关**，关闭后插件完全不处理群聊消息 |
| `enabled_groups` | list | `[]` | 启用的群组ID列表。留空 = 所有群聊都启用；填写群号 = 仅指定群组启用 |
| `enable_debug_log` | bool | `false` | 开启后输出详细调试日志，用于排查问题；当 `on_llm_request` 的 system_prompt 重写进入兼容增强或保守回退路径时，也会通过该日志帮助判断当前是精确命中、轻量兼容识别，还是低置信度保守模式 |

---

## Web 管理面板

> v1.2.1 新增，提供可视化管理界面。

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_web_panel` | bool | `false` | 启用 Web 管理面板 HTTP 服务 |
| `web_panel_port` | int | `1451` | Web 面板端口号 |
| `web_panel_host` | string | `"0.0.0.0"` | 监听地址。`0.0.0.0` = 所有网络接口，`127.0.0.1` = 仅本机访问 |

### 安全配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_reset_password` | bool | `false` | 设为 `true` 后重启，密码将重置为随机值并显示在日志中；重置后的新密码会直接使用 Argon2id 哈希保存 |
| `web_panel_trust_proxy` | bool | `false` | 信任反向代理的 `X-Real-IP` / `X-Forwarded-For` 头。**这是安全边界配置，仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** 当反代与面板部署在同一台机器、后端看到的连接来源为 `127.0.0.1 / ::1` 时，即使关闭此开关，也会自动读取代理头获取真实 IP；若反代不在本机，才需要显式开启 |
| `web_panel_ip_bind_check` | bool | `true` | 登录 IP 绑定校验。开启后登录时会把客户端 IP 绑定到会话令牌中，后续普通请求、面板访问和心跳都会校验当前 IP 是否与登录时一致。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_visible_interval_seconds` | int | `300` | 前台页面可见时的心跳检测间隔（秒）。用于尽快发现令牌过期、密码修改、服务端重启等状态变化。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_hidden_interval_seconds` | int | `1200` | 后台标签页的心跳检测间隔（秒），默认 20 分钟。用于降低后台页面资源占用和误触发高频请求。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_retry_base_seconds` | int | `15` | 心跳失败后进入缓冲重试期时的基准间隔（秒）。前端会基于该值做退避重试，而不是单次失败就立即判定断联。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_retry_max_seconds` | int | `120` | 心跳失败重试的最大间隔（秒）。连续失败时会逐步拉长重试间隔，但不会超过此上限。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |

### IP 访问控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_ip_mode` | string | `"disabled"` | IP 访问控制模式：`disabled`（不启用）、`whitelist`（白名单，仅允许列表内IP）、`blacklist`（黑名单，拒绝列表内IP） |
| `web_panel_ip_list` | list | `[]` | 白名单/黑名单 IP 地址列表 |
| `web_panel_protected_ips` | list | `[]` | 受保护IP列表，永远不会被封禁（配置文件专属，Web端只读） |

### 防爬虫与已登录请求保护

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_anti_spider` | bool | `false` | 启用防爬虫检测（UA 匹配 + 频率限制 + 扫描路径识别） |
| `web_panel_anti_spider_rate_limit` | int | `60` | 匿名请求每分钟请求数阈值，超过则可能触发临时封禁 |
| `web_panel_anti_spider_ban_duration` | int | `300` | 自动封禁持续时间（秒） |
| `web_panel_authenticated_rate_limit` | int | `240` | **已登录请求**的独立速率阈值（次/分钟）。与匿名防爬虫阈值分开计算，用于保证已登录后防护仍然生效，同时避免正常面板操作被匿名阈值误伤。注意：会话心跳请求不会触发封禁，但仍会记录会话活跃状态。 |

### 日志管理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_log_auto_clean` | bool | `false` | 自动清理过期访问日志 |
| `web_panel_log_retention_days` | int | `7` | 日志保留天数 |
| `web_panel_log_clean_interval_hours` | int | `24` | 清理检查间隔（小时） |

---

## 桌面端兼容

> v1.2.2 新增。AstrBot 桌面端（Desktop Edition）使用 Tauri 托管后端进程，重启机制与标准版不同。详细说明见 [桌面端兼容文档](DESKTOP_COMPATIBILITY.md)。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `desktop_mode` | string | `"auto"` | 桌面端模式。`auto` = 自动检测（推荐），`force_desktop` = 强制桌面端模式，`force_standard` = 强制标准版模式 |
| `desktop_detected_env` | string | `""` | 🔒 **只读**。自动检测结果，由插件写入。格式示例：`env:ASTRBOT_DESKTOP_CLIENT=1`、`path:ASTRBOT_ROOT=~/.astrbot`、`none` |

**自动检测依据（按优先级）：**

1. 环境变量 `ASTRBOT_DESKTOP_CLIENT=1`（桌面端打包模式设置，最可靠）
2. `ASTRBOT_ROOT` 指向 `~/.astrbot`（桌面端默认数据目录）
3. `ASTRBOT_WEBUI_DIR` 包含 `resources` 路径（桌面端打包资源特征）
4. `PYTHONNOUSERSITE=1` + `ASTRBOT_ROOT` 同时存在（桌面端环境隔离特征）

**桌面端模式下的行为差异：**

- `gcp_reset` / `gcp_reset_here` / `gcp_clear_image_cache` 指令重启后，会附加桌面端提示
- Web 面板重启操作响应中包含 `is_desktop` 标识
- 日志中输出额外的桌面端进程管理警告

---

## 概率与决策系统

### 基础概率

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_probability` | float | `0.02` | 基础回复概率。每条消息有 2% 的概率通过第一层筛选。值越高，AI越活跃 |
| `after_reply_probability` | float | `0.8` | 传统模式下的回复后提升概率。仅在关闭 `enable_attention_mechanism` 时生效；AI刚成功回复后，会对整个群聊会话临时使用该概率，促进连续对话。该提升不区分用户，新的成功回复会刷新持续时间。若开启注意力机制，则这一项不会参与当前会话计算，而是由注意力机制按用户接管 |
| `probability_duration` | int | `120` | 传统模式下回复后提升的持续时间（秒）。这是按整个群聊会话生效的时间窗口，不是按单个用户计算；若配置异常，系统会自动矫正为安全值 |

### 概率硬限制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_probability_hard_limit` | bool | `false` | 强制将最终概率限制在 [min, max] 范围内。它是最终后置限制层，对传统模式、注意力模式以及其他概率增减结果都会生效 |
| `probability_min_limit` | float | `0.05` | 概率下限，确保即使多重衰减也不会低于此值 |
| `probability_max_limit` | float | `0.8` | 概率上限，防止叠加后概率过高 |

### 决策AI配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `decision_ai_provider_id` | string | `""` | 执行"读空气"判断的AI提供商ID。留空使用 AstrBot 默认提供商。同时也是主动对话判断AI和频率判断AI的提供商 |
| `decision_ai_include_persona` | bool | `true` | 是否为读空气AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性判断任务执行，不额外注入人格 |
| `decision_ai_persona_name` | string | `""` | 仅在 `decision_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让读空气AI按该人格判断。若找不到则自动回退到当前会话人格 |
| `decision_ai_prompt_mode` | string | `"append"` | 决策提示词模式。`append`：在内置提示词后追加自定义内容；`override`：完全用自定义内容替换内置提示词。Smart 批次回复提示增强不作用于这里的判断主体，读空气AI仍以当前消息发送者为主要判断对象 |
| `decision_ai_extra_prompt` | string | `""` | 自定义决策提示词。可用于微调 AI 的判断标准。开启额外推理时，最终仍必须收敛到 yes/no。Smart 批次回复提示增强不会让这里承担“多目标回复规划”的职责 |
| `decision_ai_timeout` | int | `30` | 决策AI调用超时（秒）。超时后视为"不回复"。若遇到 `upstream_empty_output` / `empty output` 一类上游空响应，日志会优先标记为“上游模型返回空输出”，避免与普通限流混淆 |
| `enable_decision_ai_reasoning` | bool | `false` | 开启读空气AI额外推理模式。开启后AI必须先输出推理块，再在最后一行单独输出 yes/no；最终结论不得附带解释、前后缀或标点。推理块自动剥离不影响判定。解析失败默认不回复 |
| `decision_ai_reasoning_log` | bool | `false` | 开启后将读空气AI的推理相关内容输出到 AstrBot 日志，方便调试 |
| `decision_ai_reasoning_log_mode` | string | `"processed"` | 读空气AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |
| `judgment_reasoning_start_marker` | string | `"[[GCP_REASONING_START]]"` | 三个判断型AI（读空气、主动对话判断、频率判断）共用的推理起始符。此项在三处 Web 入口中会同步显示与同步生效 |
| `judgment_reasoning_end_marker` | string | `"[[GCP_REASONING_END]]"` | 三个判断型AI共用的推理截止符。此项在三处 Web 入口中会同步显示与同步生效 |

### 超时与并发

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `reply_timeout_warning_threshold` | int | `120` | 回复超过此时间（秒）发出警告日志 |
| `reply_generation_timeout_warning` | int | `60` | 回复生成超过此时间（秒）发出警告 |
| `concurrent_wait_max_loops` | int | `10` | 通用并发等待的最大检测轮数。总最大等待时间 = `concurrent_wait_max_loops × concurrent_wait_interval`。不仅影响普通消息并发等待，也会影响主动对话占用会话时、普通链路在缓存转正/保存前的等待检测，以及冷群缓存自动转正判断会话是否仍忙碌时的等待逻辑 |
| `concurrent_wait_interval` | float | `1.0` | 通用并发等待的每轮检测间隔（秒）。例如默认 `10 × 1.0 = 最多等待 10 秒`。即使 `concurrent_mode=smart`，主动对话占用等待和冷群缓存自动转正等待目前仍复用这套通用轮询参数，而不是切换成 Smart 专属等待逻辑 |
| `concurrent_mode` | string | `"legacy"` | 并发模式。`legacy` = 传统逐条等待处理，是普通对话链路最基础、最兜底的并发保护方式；`smart` = 在普通对话主线上优先尝试按真实到达顺序合并批次，让决策AI/回复AI一起感知当前消息后紧接着到达的追加消息。注意：这个模式选择主要只影响普通对话流程，不直接改变主动对话流程本身；即使选择了 `smart`，传统并发等待/兜底保护也不会消失，主动对话占用检测以及若干等待链路仍然复用传统轮询逻辑 |
| `enable_smart_batch_reply_hint` | bool | `true` | 仅在 `concurrent_mode=smart` 时生效。开启后，回复阶段会动态提示 AI：当前触发对象仍是主要回复对象，但可以像真人一样自然顺带回应批次中的其他消息；不值得回的也可忽略。该提示只存在于运行时，保存历史前会自动过滤 |
| `smart_concurrent_merge_wait` | float | `30.0` | Smart 模式下批次待合并超时时间（秒） |

---

## 消息格式与上下文

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `include_timestamp` | bool | `true` | 为每条消息添加时间戳，格式：`[2026-03-13 周四 14:30:00]`。帮助AI理解时间关系 |
| `include_sender_info` | bool | `true` | 为每条消息添加发送者信息，格式：`[用户名(ID:12345)]`。帮助AI区分不同发言人 |
| `max_context_messages` | int | `-1` | 传递给AI的最大历史消息条数。`-1` = 不限制（由模型上下文窗口决定） |
| `single_at_message_reply_link_max_messages` | int | `8` | 单独的、不包含任何信息的 @ 消息可继续参考最近上下文的最大消息数窗口。系统会与时间窗口同时检查，两者都满足才保留这层关联。`0` = 关闭这一维限制，仅保留时间窗口。 |
| `single_at_message_reply_link_max_seconds` | int | `180` | 单独的、不包含任何信息的 @ 消息可继续参考最近上下文的最长时间窗口（秒）。系统会与消息数窗口同时检查，两者都满足才保留这层关联。`0` = 关闭这一维限制，仅保留消息数窗口。 |

**单独的、不包含任何信息的 @ 消息上下文强化（默认启用，窗口阈值可配置）**

当用户发送的是“只 @ AI、没有文字、图片、关键词等其他有效内容”的消息时：
- 系统会先完成前置过滤和读空气筛选
- 这里的“只 @ AI”是严格语义：允许重复多个 `@AI`，但不能混入 `@别人` 或 `@全体成员`
- 只有在最终决定回复后，才会在回复阶段动态追加一段中性的上下文提醒
- 会参考最近缓存消息摘要，以及“最近一次明确回复对象”是否与当前发送这条消息的人相同
- same-user 提醒与近期摘要都会同时受“时间窗口 + 消息数窗口”双限制约束，不是二选一
- 即使命中同一人，也只会提醒 AI 优先参考最近上下文，不会强制要求它续上文
- 如果不是同一个人，或任一窗口超限，则自动降级为更中性的自由判断提醒

另有一条更宽松的内部语义专用于“候选冷却/重新叫出 AI”判断：只要空消息里包含了 `@AI`，即使同时还 `@别人` 或 `@全体成员`，也会被视为“把 AI 叫了出来”，用于决定是否重新给予最低增长与解除候选冷却。

---

## 消息缓存

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `custom_storage_max_messages` | int | `500` | 自定义消息存储的最大条数。`0` = 禁用，`-1` = 不限制。用于保存完整的群聊上下文 |
| `pending_cache_max_count` | int | `10` | 待处理消息池的最大条数。未通过概率筛选的消息暂存于此，下次回复时作为上下文合并 |
| `pending_cache_ttl_seconds` | int | `1800` | 待处理消息的过期时间（秒），超过后在下一条消息到来时自动清理 |
| `enable_idle_cache_flush` | bool | `false` | **冷群缓存自动转正**。开启后，当群聊静默超过 `idle_cache_flush_delay_seconds` 秒没有任何新消息时，自动将待处理池中的缓存消息转正写入历史记录，避免因过期被丢弃导致的上下文断裂。每收到一条新消息都会重置计时器（滑动窗口）。**建议将 `idle_cache_flush_delay_seconds` 设置为小于等于 `pending_cache_ttl_seconds` 的值**，否则缓存会在触发转正前就因过期而被清除。 |
| `idle_cache_flush_delay_seconds` | int | `600` | 冷群转正触发延迟（秒）。群聊静默多久后触发一次自动转正。与 `pending_cache_ttl_seconds` 相互独立：此项控制转正时机，过期时间控制缓存丢弃时机。范围 60-7200 秒。需开启 `enable_idle_cache_flush` 后生效。 |

---

## 图片处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_image_processing` | bool | `false` | 启用图片处理功能，将图片转换为文字描述 |
| `image_to_text_scope` | string | `"mention_only"` | 图片处理范围：`all`（所有消息中的图片）、`mention_only`（@或关键词触发时）、`at_only`（仅@消息）、`keyword_only`（仅关键词触发时） |
| `image_to_text_provider_id` | string | `""` | 图片转文字的AI提供商ID。**必须填写**，留空将无法处理图片 |
| `image_to_text_prompt` | string | `"请详细描述这张图片的内容"` | 发送给图片AI的提示语 |
| `image_to_text_timeout` | int | `60` | 图片处理API调用超时（秒）。图片转文字仍走独立的 `provider.text_chat()` 直连链路，不经过回复 Hook |
| `max_images_per_message` | int | `10` | 单条消息最大处理图片数量（1-50） |
| `enable_image_description_cache` | bool | `false` | 缓存图片描述结果，相同图片不重复调用API，节省费用 |
| `image_description_cache_max_entries` | int | `500` | 图片描述缓存的最大条目数 |
| `platform_image_caption_max_wait` | float | `2.0` | 等待平台图片说明的最大时间（秒） |
| `platform_image_caption_retry_interval` | int | `2` | 平台图片说明重试间隔 |
| `platform_image_caption_fast_check_count` | int | `10` | 快速检查次数 |
| `probability_filter_cache_delay` | int | `10000` | 概率过滤缓存延迟（毫秒） |

---

## 关键词系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trigger_keywords` | list | `[]` | 触发关键词列表。消息中包含这些词时**跳过概率筛选**，直接进入AI决策。建议填写AI角色的名字和别名 |
| `keyword_smart_mode` | bool | `false` | 智能模式。开启后，即使命中关键词也保留AI决策判断（而非直接回复），减少无意义触发 |
| `blacklist_keywords` | list | `[]` | 黑名单关键词。消息包含这些词时**直接丢弃**，不做任何处理 |

---

## 用户黑名单

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_user_blacklist` | bool | `false` | 启用用户黑名单 |
| `blacklist_user_ids` | list | `[]` | 被屏蔽的用户ID列表，这些用户的消息将被完全忽略 |

---

## 指令过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_command_filter` | bool | `true` | 自动跳过指令消息（如 `/help`、`!reset`），避免与其他插件冲突 |
| `command_prefixes` | list | `["/", "!", "#"]` | 指令前缀列表。以这些字符开头的消息被视为指令 |
| `enable_full_command_detection` | bool | `false` | 精确匹配模式。消息完全等于列表中的命令时才被过滤 |
| `full_command_list` | list | `["new", "help", "reset"]` | 精确匹配的命令列表 |
| `enable_command_prefix_match` | bool | `false` | 前缀匹配模式。消息以列表中的字符串开头时被过滤 |
| `command_prefix_match_list` | list | `[]` | 前缀匹配列表 |

---

## @消息处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_ignore_at_others` | bool | `false` | 忽略@其他用户的消息，避免插入他人的对话；此配置不影响@全体成员。关闭时，无论消息里是单个@他人、多个@他人、重复@同一人，还是 `@AI + @他人` 混合场景，都不会因为这项功能而被跳过。 |
| `ignore_at_others_mode` | string | `"strict"` | 过滤模式：`strict` 或 `allow_with_bot`；此配置不影响@全体成员。当前实现语义为：`strict` = 只要消息里存在@他人，且**没有同时@AI**，就跳过；`allow_with_bot` = 存在@他人但也同时@AI时允许继续处理。多人@、重复@同一人时按完整提及结构统一判断，不只看第一个@对象。 |
| `enable_ignore_at_all` | bool | `false` | 忽略@全体成员消息，避免群公告触发AI |
| `at_all_message_mode` | string | `"skip_probability"` | `@全体成员` 专用处理模式：`normal`（按普通消息处理）、`skip_probability`（跳过概率筛选，保留读空气AI）、`skip_all`（跳过概率筛选和读空气AI，直接回复）、`probability_boost`（仅为当前这条@全体成员消息临时提升概率） |
| `at_all_probability_boost_value` | float | `0.3` | 仅在 `at_all_message_mode="probability_boost"` 时生效。为当前这一条@全体成员消息临时增加的概率值，不影响后续消息 |

---

## 戳一戳系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poke_message_mode` | string | `"bot_only"` | 戳一戳响应模式：`ignore`（完全忽略）、`bot_only`（仅响应戳机器人）、`all`（响应所有戳一戳）。**只有当前模式允许本插件实际处理的真实 poke**，才会自动生成并保存“谁戳了谁”的历史事件文本；被该模式提前忽略的 poke 不会进入这一步 |
| `poke_bot_skip_probability` | bool | `true` | 戳机器人时跳过概率检查，直接进入AI决策 |
| `poke_bot_probability_boost_reference` | float | `0.3` | 戳一戳概率提升参考值 |
| `poke_reverse_on_poke_probability` | float | `0.0` | 被戳后立即反戳的概率（0 = 不反戳）。若反戳动作真实成功，会额外单独保存一条 AI 视角的戳一戳历史事件 |
| `enable_poke_after_reply` | bool | `false` | 回复消息后戳用户一下。若动作真实成功，会额外单独保存一条 AI 视角的戳一戳历史事件 |
| `poke_after_reply_probability` | float | `0.1` | 回复后戳用户的概率 |
| `poke_after_reply_delay` | float | `0.5` | 回复后到戳之间的延迟（秒） |
| `enable_poke_trace_prompt` | bool | `false` | 追踪谁戳了机器人，并在提示词中告知AI |
| `poke_trace_max_tracked_users` | int | `5` | 最大追踪用户数。超过上限时会移除当前最早登记的记录 |
| `poke_trace_ttl_seconds` | int | `300` | 追踪记录保留时间（秒） |
| `poke_enabled_groups` | list | `[]` | 启用戳一戳功能的群列表（空=所有群） |

---

## 转发消息解析

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_forward_message_parsing` | bool | `false` | 启用 QQ / OneBot 合并转发解析。解析器会把转发内容整理成单条可读文本并继续参与后续上下文与 AI 流程，而不是拆成多条消息 |
| `forward_max_nesting_depth` | int | `3` | 嵌套转发的最大解析深度（0=不展开嵌套，仅保留占位式降级；最大10）。在深度范围内会递归展开子转发，并尽量保留发送者信息与时间戳格式 |

---

## 欢迎消息解析

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_welcome_message_parsing` | bool | `false` | 检测群成员入群欢迎消息 |
| `welcome_message_mode` | string | `"skip_probability"` | 处理模式：`normal`（正常走完整流程）、`skip_probability`（跳过概率筛选，仍需AI决策）、`skip_all`（跳过概率和AI决策，直接回复）、`parse_only`（仅解析标记，不触发回复） |

---

## 群聊等待窗口

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_group_wait_window` | bool | `false` | 启用等待窗口。收到消息后短暂等待，收集后续消息一起处理，避免逐条回复 |
| `group_wait_window_timeout_ms` | int | `3000` | 等待超时（毫秒，200-30000）。越长越能收集到完整信息，但响应越慢 |
| `group_wait_window_max_extra_messages` | int | `3` | 最多额外收集的消息数量 |
| `group_wait_window_max_users` | int | `5` | 最多同时追踪的发送者数量 |
| `group_wait_window_attention_decay_per_msg` | float | `0.05` | 窗口内每收到一条消息时注意力衰减量 |
| `group_wait_window_at_mode` | string | `"force_close"` | @消息窗口行为模式（force_close/intercept/immediate/bypass）。这里的“@消息”核心上仍然是**@AI自己**的消息；普通 `@别人` / `@多个别人` 不应仅因为包含At就误触发窗口打断逻辑。 |
| `group_wait_window_keyword_mode` | string | `"intercept"` | 关键词消息窗口行为模式（intercept/force_close/immediate/bypass） |
| `group_wait_window_poke_mode` | string | `"bypass"` | 戳一戳窗口行为模式（bypass/force_close） |
| `group_wait_window_merge_at_list_mode` | string | `"whitelist"` | @消息窗口接管的用户过滤模式（在 `at_mode=intercept/immediate/force_close` 时生效）。命中后，窗口逻辑只会洗刷掉 **@AI 自己的 At 组件**，不会移除或折叠其他人的 At；其他人相关的原始 At 与解析结果仍需正常保留进缓存/转正/历史。 |
| `group_wait_window_merge_at_user_list` | list | `[]` | @消息窗口接管的用户ID列表（在 `at_mode=intercept/immediate/force_close` 时生效）。留空表示对所有用户生效；无论名单如何命中，窗口侧都只洗刷 AI 自己的 At，不洗刷他人的 At，不折叠重复的他人 At。 |

---

## 表情过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_emoji_filter` | bool | `false` | 检测纯表情/贴图消息，降低其触发概率 |
| `emoji_probability_decay` | float | `0.7` | 衰减系数。`0.7` 表示概率降低到原来的 30%（即衰减 70%） |
| `emoji_decay_min_probability` | float | `0.05` | 衰减后的概率下限，确保不会降为零 |

---

## 消息质量预判

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_message_quality_scoring` | bool | `true` | 根据消息内容质量动态调整概率 |
| `message_quality_question_boost` | float | `0.1` | 疑问句/话题性消息的概率提升量（+10%） |
| `message_quality_water_reduce` | float | `0.1` | 纯水聊/复读消息的概率降低量（-10%） |

---

## 回复密度限制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_reply_density_limit` | bool | `true` | 限制单位时间内的回复频率，防止刷屏 |
| `reply_density_window_seconds` | int | `300` | 统计时间窗口（秒），默认5分钟 |
| `reply_density_max_replies` | int | `4` | 窗口内最大回复次数（硬限制），达到后停止回复 |
| `reply_density_soft_limit_ratio` | float | `0.6` | 软限制比例。默认 0.6 表示达到 60%（即 4×0.6≈2 次）时开始提示AI减少回复 |
| `reply_density_ai_hint` | bool | `true` | 软限制触发时是否在提示词中告知AI当前状态 |

---

## 注意力机制

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_mechanism` | bool | `false` | 启用多用户注意力追踪。每个用户有 0-1 之间的连续注意力值。开启后会替代传统的 `after_reply_probability` 回复后临时提升模式，两者互斥 |
| `attention_increased_probability` | float | `0.8` | 高注意力用户的回复概率 |
| `attention_decreased_probability` | float | `0.08` | 低注意力用户的回复概率 |
| `attention_duration` | int | `120` | 注意力提升持续时间（秒） |
| `attention_max_tracked_users` | int | `10` | 最大同时追踪用户数 |

### 衰减与变化

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `attention_decay_halflife` | int | `300` | 注意力指数衰减半衰期（秒），每过半衰期注意力减半 |
| `attention_boost_step` | float | `0.35` | 回复用户时注意力提升步长 |
| `attention_decrease_step` | float | `0.12` | 注意力主动降低步长 |
| `enable_attention_decay_on_no_reply` | bool | `true` | 是否启用“读空气未回复衰减”机制 |
| `attention_decay_on_no_reply_step` | float | `0.2` | 普通概率路径消息被读空气判定不回复时的单次注意力衰减幅度 |
| `attention_decay_on_no_reply_min_threshold` | float | `0.3` | 只有注意力高于此值时，未回复衰减才生效 |

### 情绪检测

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_emotion_detection` | bool | `true` | 检测消息情绪以调整注意力 |
| `emotion_decay_halflife` | int | `600` | 情绪状态衰减半衰期 |
| `emotion_boost_step` | float | `0.1` | 情绪触发的注意力提升 |
| `attention_enable_negation` | bool | `true` | 检测否定情绪 |
| `attention_positive_emotion_boost` | float | `0.1` | 积极情绪的注意力提升 |
| `attention_negative_emotion_decrease` | float | `0.15` | 消极情绪的注意力降低 |

### 注意力溢出

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_spillover` | bool | `true` | 对一个用户的高注意力会"溢出"到同群其他用户 |
| `attention_spillover_ratio` | float | `0.3` | 溢出比例（30%） |
| `attention_spillover_decay_halflife` | int | `90` | 溢出效果衰减半衰期 |
| `attention_spillover_min_trigger` | float | `0.4` | 触发溢出的最小注意力值 |

### 注意力冷却

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_cooldown` | bool | `true` | 启用注意力冷却。它是正式冷却总开关：开启后，普通概率路径消息 no-reply 会进入冷却链路；若同时开启待冷却保护层，则先进入待冷却再决定是否升级为正式冷却；若关闭待冷却保护层，则直接进入正式冷却 |
| `enable_cooldown_auto_release` | bool | `true` | 是否允许正式冷却在超时后自动解冻；关闭时只会在该用户最终被 AI 回复时解除 |
| `cooldown_max_duration` | int | `600` | 正式冷却的最大持续时间（秒） |
| `cooldown_trigger_threshold` | float | `0.3` | 触发冷却的注意力阈值 |
| `enable_pending_attention_cooldown` | bool | `true` | 启用未接续谈保护层。开启后先进入待冷却，再视同一用户后续消息决定是否升级为正式冷却；关闭后将直接进入正式冷却 |
| `pending_cooldown_grace_user_messages` | int | `1` | 未接续谈保护阶段最多观察同一用户后续多少条自己的消息 |
| `pending_cooldown_max_wait_seconds` | int | `60` | 未接续谈保护最长等待时间（秒），超时后自动失效 |
| `pending_cooldown_same_user_probability_floor` | float | `0.18` | 未接续谈保护期间给同一用户保留的最低概率保护 |

> **重要说明**：
> - 这套机制分为两段：**待冷却（未接续谈保护）** 和 **正式冷却**。待冷却是否启用由 `enable_pending_attention_cooldown` 单独控制；正式冷却则由 `enable_attention_cooldown` 总控。
> - “读空气未回复衰减”现在是独立机制：未开启冷却时，可直接对普通 no-reply 执行衰减；开启冷却后，只有在用户正式进入冷却时才执行该衰减，待冷却阶段不会衰减。
> - `enable_cooldown_auto_release` / `cooldown_max_duration` 只作用于**正式冷却**，不作用于待冷却阶段。
> - 正式冷却与待冷却都只保存在**运行态内存**中，插件或平台重启后会清空，不再作为长期文件持久化。
> - 只有仍在当前会话注意力追踪列表中的用户，待冷却/正式冷却才有意义；若用户已不在注意力追踪列表中，会被自动从冷却名单中移除。
> - 这套保护补丁只作用于**普通概率路径消息**（非@AI、非关键词触发）。关键词唤醒和@AI消息不走这套误伤保护逻辑；但一旦这些路径最终成功触发回复，仍会统一解除正式冷却。

### 冷却升级迁移说明

以下旧配置项已移除，不再建议继续保留在配置文件中：

- `attention_decrease_on_no_reply_step` → `attention_decay_on_no_reply_step`
- `attention_decrease_threshold` → `attention_decay_on_no_reply_min_threshold`
- `cooldown_attention_decrease` → `attention_decay_on_no_reply_step`
- `enable_attention_decay_on_confirmed_no_reply` → `enable_attention_decay_on_no_reply`
- `confirmed_no_reply_attention_decrease_step` → `attention_decay_on_no_reply_step`
- `pending_cooldown_at_cancel_active` → 无替代，统一改为“最终成功回复即解除正式冷却”
- `skip_no_reply_decay_during_pending_reconnect` → 无替代，统一改为“待冷却观察期内固定不衰减”

升级后如果检测到这些旧键，插件会在启动日志中输出迁移提示。

同时，旧版独立 `cooldown_data.json` 中的冷却数据会在启动后由后台任务自动迁入当前运行态内存，再安全清理旧冷却残留；注意力、情绪等长期状态文件不会因此被删除。


| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_conversation_fatigue` | bool | `false` | 启用对话疲劳。连续对话后逐渐降低回复意愿，模拟真人节奏 |
| `fatigue_reset_threshold` | int | `300` | 疲劳重置的沉默时间（秒），不说话这么久后疲劳清零 |
| `fatigue_threshold_light` | int | `3` | 轻度疲劳的消息数阈值 |
| `fatigue_threshold_medium` | int | `5` | 中度疲劳的消息数阈值 |
| `fatigue_threshold_heavy` | int | `8` | 重度疲劳的消息数阈值 |
| `fatigue_probability_decrease_light` | float | `0.15` | 轻度疲劳的概率衰减 |
| `fatigue_probability_decrease_medium` | float | `0.25` | 中度疲劳的概率衰减 |
| `fatigue_probability_decrease_heavy` | float | `0.4` | 重度疲劳的概率衰减 |
| `fatigue_closing_probability` | float | `0.35` | 疲劳时 AI 发出结束语（如"我先忙了"）的概率 |

---

## 动态时段概率

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_dynamic_reply_probability` | bool | `false` | 根据一天中的不同时段调整回复概率 |
| `reply_time_periods` | string | `"[]"` | 时段配置，JSON字符串格式。每个时段含 `name`、`start`、`end`、`factor` |
| `reply_time_transition_minutes` | int | `30` | 时段之间的平滑过渡时间（分钟） |
| `reply_time_use_smooth_curve` | bool | `true` | 使用正弦曲线（而非线性）过渡 |
| `reply_time_min_factor` | float | `0.1` | factor 最小值限制 |
| `reply_time_max_factor` | float | `2.0` | factor 最大值限制 |

> **factor 说明**：`factor: 0.2` = 概率降到基础值的 20%；`factor: 1.0` = 无变化；`factor: 1.5` = 概率提升到 150%

**时段配置示例：**
```json
[
  {"name": "深夜睡眠", "start": "23:00", "end": "07:00", "factor": 0.2},
  {"name": "午休时段", "start": "12:00", "end": "14:00", "factor": 0.5},
  {"name": "晚间活跃", "start": "19:00", "end": "22:00", "factor": 1.3}
]
```

---

## 拟人模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_humanize_mode` | bool | `false` | 启用拟人化行为模式，模拟人类的"沉默→关注→参与"对话节奏 |
| `humanize_silent_mode_threshold` | int | `3` | 连续 N 条消息未回复后进入沉默状态 |
| `humanize_silent_max_duration` | int | `600` | 沉默最长持续时间（秒） |
| `humanize_silent_max_messages` | int | `8` | 沉默中收到 N 条消息后自动醒来 |
| `humanize_enable_dynamic_threshold` | bool | `true` | 动态调整消息计数阈值 |
| `humanize_base_message_threshold` | int | `1` | 动态阈值的基础值 |
| `humanize_max_message_threshold` | int | `3` | 动态阈值的最大值 |
| `humanize_include_decision_history` | bool | `true` | 在AI决策中包含历史决策记录，保持一致性 |
| `humanize_interest_keywords` | list | `[]` | 兴趣话题关键词。检测到时提升回复概率 |
| `humanize_interest_boost_probability` | float | `0.25` | 兴趣话题的概率提升量 |

---

## 主动对话

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_proactive_chat` | bool | `false` | 启用主动对话。群聊沉默一段时间后，AI自动发起话题 |
| `proactive_silence_threshold` | int | `1800` | 群聊沉默多久后可能触发主动对话（秒，默认30分钟） |
| `proactive_probability` | float | `0.2` | 满足条件后主动发言的概率 |
| `proactive_check_interval` | int | `120` | 定时检查间隔（秒） |
| `proactive_enabled_groups` | list | `[]` | 启用主动对话的群列表（空=所有启用群聊的群） |

### 用户活跃要求

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `proactive_require_user_activity` | bool | `true` | 要求有用户近期活跃才触发（避免在深夜没人的群自言自语） |
| `proactive_min_user_messages` | int | `3` | 近期至少有这么多条用户消息 |
| `proactive_user_activity_window` | int | `300` | 活跃时间窗口（秒） |

### 失败保护

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `proactive_max_consecutive_failures` | int | `3` | 连续被无视 N 次后进入冷却 |
| `proactive_cooldown_duration` | int | `2400` | 冷却持续时间（秒） |

### 安静时段

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `proactive_enable_quiet_time` | bool | `true` | 启用安静时段限制 |
| `proactive_quiet_start` | string | `"23:00"` | 安静时段开始 |
| `proactive_quiet_end` | string | `"07:00"` | 安静时段结束 |
| `proactive_transition_minutes` | int | `30` | 安静时段边界平滑过渡 |

### AI 判断

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_proactive_ai_judge` | bool | `true` | 主动发言前由主动对话预判断AI判断当前是否适合说话 |
| `proactive_ai_judge_include_persona` | bool | `true` | 是否为主动对话预判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性时机判断执行 |
| `proactive_ai_judge_persona_name` | string | `""` | 仅在 `proactive_ai_judge_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让主动对话预判断AI按该人格判断当前是否适合开口。若找不到则自动回退 |
| `proactive_ai_judge_prompt` | string | `""` | 主动对话预判断提示词。留空使用默认提示词。Web 面板可展开查看完整默认内容；传统配置页面不会显示这段预览，如需查看建议到 Web 面板对应配置项处查看。开启额外推理时无需手动写入推理协议；若缺失，系统会自动补充并保留你的原始提示词正文 |
| `proactive_ai_judge_timeout` | int | `15` | 主动对话预判断超时（秒）。该判断链路仍使用独立的 `provider.text_chat()` 直连方式，与回复生成 Hook 链分离 |
| `enable_proactive_ai_reasoning` | bool | `false` | 开启主动对话判断AI额外推理模式。AI必须先输出推理块，再在最后一行单独输出 yes/no；最终结论不得附带解释、前后缀或标点。推理块自动剥离。解析失败默认不触发（不进入冷却） |
| `proactive_ai_reasoning_log` | bool | `false` | 开启后将主动对话判断AI的推理相关内容输出到 AstrBot 日志 |
| `proactive_ai_reasoning_log_mode` | string | `"processed"` | 主动对话判断AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |

### 后续效果

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `proactive_use_attention` | bool | `true` | 主动对话使用注意力机制 |
| `proactive_temp_boost_probability` | float | `0.4` | 主动对话后临时概率提升 |
| `proactive_temp_boost_duration` | int | `120` | 临时提升持续时间（秒） |
| `enable_proactive_at_conversion` | bool | `false` | 主动对话是否转换为@消息 |

---

## 自适应互动评分

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_adaptive_proactive` | bool | `true` | 根据用户互动效果自动调整主动对话策略 |
| `score_increase_on_success` | int | `15` | 成功获得回复时加分 |
| `score_decrease_on_fail` | int | `10` | 被无视时减分 |
| `score_quick_reply_bonus` | int | `5` | 快速获得回复的额外加分 |
| `score_multi_user_bonus` | int | `10` | 多人参与回复的额外加分 |
| `score_streak_bonus` | int | `5` | 连续成功的额外加分 |
| `score_revival_bonus` | int | `20` | 低分时重新获得互动的加分 |
| `interaction_score_decay_rate` | int | `2` | 每日自然衰减分数 |
| `interaction_score_min` | int | `10` | 最低分数 |
| `interaction_score_max` | int | `100` | 最高分数 |

---

## 主动对话时段概率

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_dynamic_proactive_probability` | bool | `false` | 按时段调整主动对话的概率 |
| `proactive_time_periods` | string | `"[]"` | 时段配置（与回复时段格式相同） |
| `proactive_time_transition_minutes` | int | `45` | 时段过渡时间 |
| `proactive_time_min_factor` | float | `0.0` | factor 最小值 |
| `proactive_time_max_factor` | float | `2.0` | factor 最大值 |
| `proactive_time_use_smooth_curve` | bool | `true` | 使用正弦曲线过渡 |

---

## 吐槽系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_complaint_system` | bool | `true` | 连续被无视时AI会"吐槽"或抱怨，让Bot更有性格 |
| `complaint_trigger_threshold` | int | `2` | 触发吐槽的最低连续被无视次数 |
| `complaint_max_accumulation` | int | `15` | 最大累积被无视次数 |
| `complaint_decay_on_success` | int | `2` | 成功获得回复时减少的累积次数 |

---

## 情绪系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_mood_system` | bool | `false` | 启用情绪追踪，检测对话中的情绪变化并影响AI回复语气 |
| `enable_negation_detection` | bool | `true` | 检测否定表达（如"不"、"没有"等） |
| `mood_decay_time` | int | `300` | 情绪自然衰减时间（秒） |
| `mood_cleanup_threshold` | int | `3600` | 清理过期情绪记录的时间阈值 |
| `mood_cleanup_interval` | int | `600` | 情绪清理检查间隔 |

---

## 频率调整器

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_frequency_adjuster` | bool | `false` | 分析群聊消息节奏，自动调整回复频率 |
| `frequency_ai_include_persona` | bool | `true` | 是否为频率判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格，并按该人格在当前时段下应有的活跃倾向判断；关闭时按中性群聊参与强度判断 |
| `frequency_ai_persona_name` | string | `""` | 仅在 `frequency_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让频率判断AI按该人格判断“正常 / 过于频繁 / 过少”。若找不到则自动回退 |
| `frequency_check_interval` | int | `180` | 分析间隔（秒） |
| `frequency_analysis_timeout` | int | `20` | 分析超时 |
| `frequency_adjust_duration` | int | `360` | 调整效果持续时间 |
| `frequency_analysis_message_count` | int | `15` | 参与分析的消息数量 |
| `frequency_min_message_count` | int | `5` | 最少消息数才进行分析 |
| `frequency_decrease_factor` | float | `0.85` | 降低频率系数 |
| `frequency_increase_factor` | float | `1.1` | 提升频率系数 |
| `frequency_min_probability` | float | `0.03` | 调整后概率下限 |
| `frequency_max_probability` | float | `0.85` | 调整后概率上限 |
| `enable_frequency_ai_reasoning` | bool | `false` | 开启频率判断AI额外推理模式。AI必须先输出推理块，再在最后一行单独输出「正常/过于频繁/过少」之一；最终结论不得附带解释、前后缀或标点。推理块自动剥离。解析失败默认不调整概率 |
| `frequency_ai_reasoning_log` | bool | `false` | 开启后将频率判断AI的推理相关内容输出到 AstrBot 日志 |
| `frequency_ai_reasoning_log_mode` | string | `"processed"` | 频率判断AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |

> 说明：频率判断AI使用的推理起止标志符与读空气AI、主动对话判断AI共用，Web 面板会在三处入口同步显示同一套配置。

---

## 打字模拟

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_typing_simulator` | bool | `false` | 模拟打字延迟，根据回复长度等待相应时间后发送 |
| `typing_speed` | float | `15.0` | 打字速度（字符/秒） |
| `typing_max_delay` | float | `3.0` | 最大延迟（秒） |

---

## 打字错误生成

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_typo_generator` | bool | `false` | 基于拼音相似性生成自然错别字，让AI回复更像真人打字 |
| `typo_error_rate` | float | `0.02` | 错别字概率（2% = 每50个字平均1个错别字） |

---

## 重复过滤

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_duplicate_filter` | bool | `true` | 检测AI是否发送了重复内容并过滤 |
| `duplicate_filter_check_count` | int | `5` | 检查最近 N 条回复 |
| `enable_duplicate_time_limit` | bool | `true` | 启用重复检测时间限制 |
| `duplicate_filter_time_limit` | int | `1800` | 时间限制（秒），超过此时间的旧回复不参与重复检测 |

---

## 记忆系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_memory_injection` | bool | `false` | 将长期记忆注入AI上下文，让AI记住之前的对话 |
| `memory_plugin_mode` | string | `"auto"` | 记忆模式：`auto`（自动检测，优先 LivingMemory → 回退 Legacy → 都没有则跳过）、`legacy`（传统模式，稳定性高）、`livingmemory`（智能模式，混合检索+人格隔离）。auto 模式下两个插件都安装时优先使用 LivingMemory，都未安装时自动跳过记忆注入不会报错 |
| `memory_insertion_timing` | string | `"post_decision"` | 记忆注入时机：`pre_decision`（决策前，记忆影响"是否回复"）、`post_decision`（决策后，记忆只影响"回复内容"） |
| `livingmemory_version` | string | `"auto"` | LivingMemory 架构版本适配方式：`auto`（推荐，自动识别 v2/v1）、`v2`（2.x+ 新架构）、`v1`（1.x 旧架构） |
| `livingmemory_persona_compat_mode` | string | `"auto"` | LivingMemory 人格ID兼容模式：`auto`（推荐，自动尝试新版/旧版人格接口）、`resolver_only`、`legacy_only`、`off` |
| `livingmemory_top_k` | int | `5` | 召回的记忆条数，仅在 livingmemory 模式或 auto 检测到 LivingMemory 时有效 |

> Web 面板说明：以上 LivingMemory 相关配置已同步挂载到技术树的「记忆注入」节点，可在 Web 配置面板直接修改。

---

## 工具提示

> 兼容增强说明：`on_llm_request` 中的 `system_prompt` 重写现在优先复用旧版精确命中路径；若平台 persona 包装或空白有轻微变化，会自动尝试轻量兼容识别。若仍无法高置信度识别，则插件进入**保守回退模式**：优先保留当前 `req.system_prompt`，并输出 warning 日志，但不会阻断回复流程，也不会影响 `req.prompt` / `req.contexts` / `req.func_tool` 的主语义恢复。
>
> 排查建议：
> - 想看本次走了哪条兼容路径，请开启 `enable_debug_log`
> - 若未开 debug 仍看到 warning，通常说明当前 AstrBot 或第三方插件的提示词结构变化较大，插件已经优先选择“不断链、尽量保留内容”的保守模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_tools_reminder` | bool | `false` | 是否启用**工具提醒文本**。开启后，插件会在 `on_llm_request` 阶段基于**当前会话最终可见工具集**生成一段运行时提示词，告诉 AI 当前会话里有哪些工具可用；关闭后完全不注入任何工具提醒文本。**注意：此开关只影响提醒，不影响 AstrBot 原生工具调用能力。** |
| `tools_reminder_persona_filter` | bool | `false` | 是否在工具提醒层按当前会话人格过滤工具。仅在 `enable_tools_reminder=true` 时生效：开启后，先取当前会话可见工具，再按人格允许工具名单过滤后展示；关闭则展示当前会话全部可见工具。**它只影响提醒展示，不再拦截实际工具调用。** |

### 工具提醒的运行规则

- 工具提醒不再在群聊主流程前半段提前拼进 `final_message`，而是延后到 `on_llm_request` 阶段生成。
- 提醒文本的来源不再是全局工具管理器的裸列表，而是**当前会话最终 `req.func_tool`**，因此会自动兼容：
  - AstrBot 内置工具
  - 联网搜索工具
  - 知识库 / 数据库检索类工具（只要它们以 tool 形式进入当前会话）
  - sandbox / local runtime 工具
  - 其他插件注册的工具
  - 用户额外添加工具 / MCP 工具
- 会话隔离优先于人格过滤：会先按当前会话可见工具集收口，再决定是否叠加人格过滤展示。
- 当 AstrBot 当前会话的 `provider_settings.tool_schema_mode=skills_like` 时，工具提醒会**自动降级为仅展示工具名称与功能描述**，不再展开参数列表，以避免干扰框架的两阶段工具 schema 暴露流程、减少跨工具参数串扰。
- 当 `tool_schema_mode=full` 或当前 AstrBot 版本/配置中无法识别该字段时，工具提醒保持原有完整展示（名称 + 描述 + 参数）。
- 若工具提醒生成失败、人格解析失败或当前会话工具获取失败，会自动降级为**跳过提醒**，但不会阻断回复流程，也不会清空实际工具集。

### 历史保存与过滤

- 工具提醒文本属于**运行时 prompt 提示**，不应进入官方历史或自定义历史。
- 为防止极端情况下提示词混入保存链路，工具提醒块会包裹专用标记：
  - `[系统提示-工具提醒开始]`
  - `[系统提示-工具提醒结束]`
- `MessageCleaner` 与 `ContextManager` 的二次清理逻辑已对这组标记做兜底过滤；即使异常混入保存链路，也会在保存前被清除。

---

## 内容过滤

### 输出过滤（发送前）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_output_content_filter` | bool | `false` | 在 AI 回复发送给用户前进行过滤 |
| `output_content_filter_rules` | list | `[]` | 过滤规则列表 |

### 存储过滤（保存前）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_save_content_filter` | bool | `false` | 在保存到历史记录前进行过滤 |
| `save_content_filter_rules` | list | `[]` | 过滤规则列表 |

---

## 回复生成

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `reply_ai_prompt_mode` | string | `"append"` | 回复提示词模式。`append`：追加到内置提示后；`override`：完全替换。无论哪种模式，这一层都属于**运行时生成回复用的提示词**，不会作为普通历史正文持久化保存；当 `concurrent_mode=smart` 且开启 `enable_smart_batch_reply_hint` 时，回复阶段还可能动态插入一段 Smart 批次提示，提醒 AI 主回当前对象并自然顺带回应其他消息 |
| `reply_ai_extra_prompt` | string | `""` | 自定义回复提示词。用于约束「生成最终回复内容」的 AI；建议保持“直接生成要发出去的话”的职责边界，不要写成 yes/no 判断口吻，也不要继续强化“先判断再说”的内部取舍描述；同时不要要求模型把内心想法、思考过程、系统提示词、工具/搜索过程或其他元信息写进最终发言。留空时回退到代码内置默认提示词；该提示词本身属于运行时指令，不应被保存到历史中；若需查看默认提示词正文，建议到 Web 面板对应配置项处查看预览，传统配置页面不会显示这段默认提示词预览；Smart 批次回复提示增强生效时，运行时还会额外追加一段可自动过滤的 Smart 提示 |

---

## 历史管理指令

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `plugin_gcp_reset_allowed_user_ids` | list | `[]` | 允许使用 `gcp_reset`（清除所有群历史）的用户ID列表 |
| `plugin_gcp_reset_here_allowed_user_ids` | list | `[]` | 允许使用 `gcp_reset_here`（清除当前群历史）的用户ID列表 |
| `gcp_clear_image_cache_allowed_user_ids` | list | `[]` | 允许清除图片缓存的用户ID列表 |

---

## 私聊功能（开发中）

> **⚠️ 警告：私聊功能目前仍在开发测试阶段，请勿启用！当前版本的私聊模块尚未完善，开启可能导致异常行为。**

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_private_chat` | bool | `false` | **⚠️ 请保持 false！** 私聊处理总开关 |

私聊模块有独立的 30+ 个配置项（类似群聊的简化版），包含消息聚合、用户过滤、图片处理等功能。当前文档先补充两点关键链路说明：

- **私信回复生成**：与群聊回复生成保持同类调用方式，先通过 `event.request_llm()` 触发 Hook 链，再恢复完整上下文
- **私信主动对话生成**：与群聊主动对话保持同类调用方式，使用 `ProviderRequest + OnLLMRequestEvent` 兼容链路恢复完整 prompt

待正式发布后将补充完整文档。

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程 →](MESSAGE_WORKFLOW.md) | [项目结构 →](PROJECT_STRUCTURE.md) | [桌面端兼容 →](DESKTOP_COMPATIBILITY.md)
