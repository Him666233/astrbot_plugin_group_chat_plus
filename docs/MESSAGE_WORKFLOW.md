# 消息工作流程详解

> 本文档完整描述了群聊增强插件从**收到消息**到**发出回复**的完整处理流程，以及每个环节涉及的配置项。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考](CONFIG_REFERENCE.md) | [项目结构](PROJECT_STRUCTURE.md) | [桌面端兼容](DESKTOP_COMPATIBILITY.md)

---

## 流程总览

```
群聊消息到达
    ↓
Phase 1 · 基础验证
    ↓
Phase 2 · 消息增强
    ↓
Phase 3 · 触发检测（@消息 / 关键词）
    ↓
Phase 4 · 概率筛选（第一层过滤）
    ↓
Phase 5 · 消息内容处理（图片/表情/戳一戳等）
    ↓
Phase 6 · 群聊等待窗口（批量收集）
    ↓
Phase 7 · AI 决策判断（第二层过滤 — "读空气"）
    ↓
Phase 7.5 · Smart 并发合并（concurrent_mode=smart 时，仅作用于普通消息批次合并与回复阶段提示增强；主动对话占用会话时的等待检测仍复用通用并发轮询参数）
    ↓
Phase 8 · AI 回复生成
    ↓
Phase 9 · 回复后处理（概率提升/打字延迟/错别字等）
```

---

## Phase 1 · 基础验证

消息到达 `on_group_message()` 后，首先进行一系列前置检查，任何一项不通过则**直接丢弃消息**。

> **执行优先级**：`on_group_message` 使用 `priority=-1`，低于默认值 0，确保其他插件的消息处理器先执行。

| 检查项 | 说明 | 相关配置 |
|--------|------|----------|
| 群聊总开关 | 插件是否启用 | `enable_group_chat` |
| 群组白名单 | 是否在允许的群列表中（空=全部允许） | `enabled_groups` |
| 消息去重 | 是否是重复收到的同一条消息 | — （内部机制） |
| 私聊过滤 | 群聊处理器不处理私聊消息 | — |
| 指令过滤 | 以 `/`、`!`、`#` 等开头的指令消息被跳过 | `enable_command_filter`、`command_prefixes`、`enable_full_command_detection`、`full_command_list`、`enable_command_prefix_match`、`command_prefix_match_list` |
| 🆕 插件兼容性 | 其他插件是否已发送回复（`_has_send_oper`） | — （自动检测）。检测到时仍缓存消息到上下文池，但跳过 AI 处理 |

---

## Phase 2 · 消息增强

通过基础验证的消息进入增强处理阶段，为后续流程补充额外信息。

### 2.1 欢迎消息解析

检测新成员入群消息（如"xxx加入了群聊"），根据配置决定后续处理方式。

| 配置项 | 作用 |
|--------|------|
| `enable_welcome_message_parsing` | 是否启用入群消息识别 |
| `welcome_message_mode` | 处理模式：`normal`（正常流程）、`skip_probability`（跳过概率直接到AI判断）、`skip_all`（跳过概率和AI判断直接回复）、`parse_only`（仅解析不触发回复） |

### 2.2 转发消息解析

将 QQ / OneBot 合并转发消息解析为可读文本，让 AI 能理解转发内容。该步骤发生在 AI 决策前：解析器会直接把事件消息链中的 `Forward` 组件替换成单个 `Plain(text=...)`，并同步更新 `message_str`，因此后续消息增强、上下文构建与 AI 回复看到的始终是一条已经展开好的文本消息，而不是拆成多条独立消息。

对嵌套转发，解析器会在深度限制内递归展开；当结构异常、接口失败或超过限制时，仅对对应嵌套块做占位式降级，不会让整条消息处理流程中断。

| 配置项 | 作用 |
|--------|------|
| `enable_forward_message_parsing` | 是否解析 QQ / OneBot 合并转发消息 |
| `forward_max_nesting_depth` | 嵌套转发的最大解析深度（0=不展开嵌套，仅保留占位式降级；1-10=在限制内递归展开） |

### 2.3 @全体成员过滤

| 配置项 | 作用 |
|--------|------|
| `enable_ignore_at_all` | 忽略@全体成员消息，避免群公告触发AI |
| `at_all_message_mode` | `@全体成员` 专用处理模式：可按普通消息处理、跳过概率筛选、跳过概率+读空气，或仅临时提升当前消息概率 |
| `at_all_probability_boost_value` | `at_all_message_mode=probability_boost` 时，仅对当前这条@全体成员消息增加的临时概率值 |

> `@全体成员` 与 `@他人过滤` 是两条独立规则：如果先命中 `enable_ignore_at_all`，消息会直接短路；若未忽略，再按 `at_all_message_mode` 决定它后续是像普通消息一样处理、跳过概率筛选、跳过概率+读空气，还是只对当前这一条消息临时提升概率。

---

## Phase 3 · 触发检测

检测消息中的特殊触发条件。**显式@机器人和触发关键词会跳过 Phase 4 的概率筛选；`@全体成员` 是否跳过则由其专用模式单独决定。**

### 3.1 @消息检测

如果消息@了机器人，则标记为 `is_at_message = True`，**跳过概率筛选**直接进入 AI 决策阶段。

### 3.2 触发关键词检测

扫描消息文本，匹配预设的触发关键词。

| 配置项 | 作用 |
|--------|------|
| `trigger_keywords` | 触发词列表（如AI角色名/别名），命中后跳过概率筛选 |
| `keyword_smart_mode` | 智能模式：即使命中关键词也保留 AI 决策判断（Phase 7），而非直接回复 |

### 3.3 黑名单关键词

| 配置项 | 作用 |
|--------|------|
| `blacklist_keywords` | 黑名单词列表，命中后**直接丢弃消息** |

---

## Phase 4 · 概率筛选（第一层过滤）

> 这是插件的**第一道过滤门槛**。对于没有触发@或关键词的普通消息，需要通过随机概率检查才能继续。

### 4.1 基础概率

每条消息生成一个 0-1 的随机数，与当前概率值比较：

| 配置项 | 作用 |
|--------|------|
| `initial_probability` | 基础概率值（默认 0.02 = 2%） |
| `after_reply_probability` | 刚回复后的提升概率（默认 0.8），用于促进连续对话 |
| `probability_duration` | 回复后概率提升的持续时间（秒） |

### 4.2 概率调节器

基础概率会被以下系统实时调整：

#### 动态时段概率

根据一天中的不同时段调整概率，模拟作息节奏。

| 配置项 | 作用 |
|--------|------|
| `enable_dynamic_reply_probability` | 是否启用时段概率调整 |
| `reply_time_periods` | 时段配置（JSON字符串），每个时段定义 name/start/end/factor |
| `reply_time_transition_minutes` | 时段之间的平滑过渡时间（分钟） |
| `reply_time_use_smooth_curve` | 使用正弦曲线过渡（而非线性） |
| `reply_time_min_factor` / `reply_time_max_factor` | factor 的最小/最大限制 |

> 示例：`factor: 0.2` 表示概率降为基础值的 20%；`factor: 1.3` 表示概率提升到 130%。

#### 频率调整器

分析群聊消息节奏，动态调整回复频率。支持额外推理模式。

| 配置项 | 作用 |
|--------|------|
| `enable_frequency_adjuster` | 启用频率分析 |
| `frequency_ai_include_persona` | 是否为频率判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性群聊参与强度判断 |
| `frequency_ai_persona_name` | 仅在 `frequency_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格；填写完整人格名=强制让频率判断AI按该人格判断，找不到时自动回退 |
| `frequency_check_interval` | 分析间隔（秒） |
| `frequency_analysis_message_count` | 分析的消息数量 |
| `frequency_decrease_factor` / `frequency_increase_factor` | 降低/提升系数 |
| `frequency_min_probability` / `frequency_max_probability` | 调整后的概率范围 |
| `enable_frequency_ai_reasoning` | 开启频率判断AI额外推理。AI必须先输出推理块，再在最后一行单独给出判断结论 |
| `frequency_ai_reasoning_log` | 开启后将频率判断AI推理相关内容输出到日志 |
| `frequency_ai_reasoning_log_mode` | 推理日志输出模式：`processed` = 处理后的推理块，`raw` = 模型原始文本 |
| `judgment_reasoning_start_marker` / `judgment_reasoning_end_marker` | 频率判断AI与读空气AI、主动对话判断AI共用同一套推理起止标志符 |

#### 概率硬限制

强制将最终概率限制在范围内。

| 配置项 | 作用 |
|--------|------|
| `enable_probability_hard_limit` | 启用硬限制 |
| `probability_min_limit` / `probability_max_limit` | 最小/最大概率值 |

#### 表情过滤

纯表情/贴图消息降低概率。

| 配置项 | 作用 |
|--------|------|
| `enable_emoji_filter` | 启用表情检测 |
| `emoji_probability_decay` | 衰减系数（0.7 = 降低70%） |
| `emoji_decay_min_probability` | 衰减后的概率下限 |

#### 消息质量预判

根据消息内容质量调整概率。

| 配置项 | 作用 |
|--------|------|
| `enable_message_quality_scoring` | 启用质量预判 |
| `message_quality_question_boost` | 疑问句/话题消息的概率提升量 |
| `message_quality_water_reduce` | 纯水聊/复读消息的概率降低量 |

#### 拟人模式

模拟人类的"沉默→关注→参与"行为模式。

| 配置项 | 作用 |
|--------|------|
| `enable_humanize_mode` | 启用拟人模式 |
| `humanize_silent_mode_threshold` | 连续 N 条消息未回复后进入沉默 |
| `humanize_silent_max_duration` | 沉默最长持续时间（秒） |
| `humanize_silent_max_messages` | 沉默中收到 N 条消息后醒来 |
| `humanize_enable_dynamic_threshold` | 动态调整消息计数阈值 |
| `humanize_interest_keywords` | 兴趣话题关键词（检测到时提升概率） |
| `humanize_interest_boost_probability` | 兴趣话题的概率提升量 |

#### 用户黑名单

| 配置项 | 作用 |
|--------|------|
| `enable_user_blacklist` | 启用用户黑名单 |
| `blacklist_user_ids` | 被屏蔽的用户ID列表 |

### 4.3 概率筛选结果

- **通过** → 进入 Phase 5（内容处理）
- **未通过** → 消息被缓存到"待处理池"（pending cache），作为后续回复的上下文参考，但**不触发 AI 判断和回复**

| 配置项 | 作用 |
|--------|------|
| `pending_cache_max_count` | 待处理池最大消息数 |
| `pending_cache_ttl_seconds` | 缓存消息的过期时间（在下一条消息到来时执行清理） |
| `enable_idle_cache_flush` | 启用冷群缓存自动转正：群聊静默超过触发延迟后，自动将待处理池消息写入历史，避免过期丢失 |
| `idle_cache_flush_delay_seconds` | 冷群转正触发延迟（秒，默认600），建议 ≤ `pending_cache_ttl_seconds` |

---

## Phase 5 · 消息内容处理

通过概率筛选的消息进入内容处理阶段，提取和转换消息中的各种内容。

### 5.1 @他人过滤

| 配置项 | 作用 |
|--------|------|
| `enable_ignore_at_others` | 忽略@其他用户的消息（不影响@全体成员） |
| `ignore_at_others_mode` | `strict` 或 `allow_with_bot`；当前实现语义为：存在@他人且**没有同时@AI**时会被过滤，若同时@AI则允许继续处理。多人@、重复@同一人时按完整提及结构统一判断。 |

### 5.1.1 多重@解析注入

在@全体过滤、@他人过滤之后，插件会对消息中的 At 组件做统一解析，并把解析结果以内联方式注入到原始消息内部：
- `@AI` → `[At:bot_id|你]`
- `@他人` → `[At:10002|张三]`
- 解析失败 → `[At:10002|解析失败]`
- 多个@、重复@同一人、`@AI + @多人` 混合场景都会按原始出现顺序逐个保留，不做折叠

旧版 `【@指向说明】...` 仍然保留，但每条消息最多注入一次，只做高层提醒，不逐个展开所有At对象。

### 5.2 @全体成员专用模式

| 配置项 | 作用 |
|--------|------|
| `at_all_message_mode` | `normal`（按普通消息处理）、`skip_probability`（跳过概率筛选但保留读空气AI）、`skip_all`（跳过概率筛选和读空气AI）、`probability_boost`（仅对当前这条@全体成员消息临时提升概率） |
| `at_all_probability_boost_value` | `at_all_message_mode=probability_boost` 时，对当前这一条@全体成员消息增加的临时概率值 |

### 5.3 图片处理

将图片转换为文字描述，让AI能理解图片内容。

| 配置项 | 作用 |
|--------|------|
| `enable_image_processing` | 启用图片处理 |
| `image_to_text_scope` | 处理范围：`all`（所有消息）、`mention_only`（@或关键词触发时）、`at_only`（仅@时）、`keyword_only`（仅关键词触发时） |
| `image_to_text_provider_id` | 图片转文字的AI提供商ID（**必填**） |
| `image_to_text_prompt` | 发送给AI的图片描述提示语 |
| `image_to_text_timeout` | API调用超时时间 |
| `max_images_per_message` | 单条消息最大处理图片数 |
| `enable_image_description_cache` | 缓存图片描述结果（节省API调用） |
| `image_description_cache_max_entries` | 缓存最大条目数 |

### 5.4 消息元数据注入

| 配置项 | 作用 |
|--------|------|
| `include_timestamp` | 为消息添加时间戳 `[YYYY-MM-DD 周x HH:MM:SS]` |
| `include_sender_info` | 为消息添加发送者信息 `[Name(ID:xxx)]` |

**单独的、不包含任何信息的 @ 消息强化（默认启用，窗口阈值可配置）**：
- 当消息是“仅@AI且没有文字、图片、关键词等其他内容”的单独 @ 消息时，系统前面只负责识别事实，不会立刻把提醒文案混进元数据
- 这里的“仅@AI”是严格语义：允许重复多个 `@AI`，但不能混入 `@别人` 或 `@全体成员`
- 与之相对，在候选冷却/重新叫出AI的判断里，插件会采用更宽松的 contains_ai 语义：只要空消息里包含了 `@AI`，即使同时也有 `@别人` 或 `@全体成员`，也可视为“把AI叫了出来”
- 这类消息会参考最近缓存消息摘要，以及“最近一次明确回复对象”是否与当前发送者相同
- 系统会同时检查“时间窗口 + 消息数窗口”，两者都满足才保留 same-user / recent-summary 这层关联
- 关联窗口由 `single_at_message_reply_link_max_messages` 与 `single_at_message_reply_link_max_seconds` 控制；两者是共同作用，不是二选一
- 只有在前置过滤和读空气筛选都通过后，进入回复生成阶段时，才会动态追加一段中性的上下文提醒
- 即使命中同一人，也不会强制要求 AI 接上文，只会提醒它优先参考最近上下文，自然判断

### 5.5 戳一戳处理

| 配置项 | 作用 |
|--------|------|
| `poke_message_mode` | 戳一戳响应模式：`ignore`（忽略）、`bot_only`（仅响应戳机器人）、`all`（响应所有） |
| `poke_bot_skip_probability` | 戳机器人时跳过概率检查 |
| `poke_enabled_groups` | 启用戳一戳的群（空=全部） |
| `enable_poke_trace_prompt` | 记录谁戳了机器人，并告知AI |
| `poke_trace_max_tracked_users` / `poke_trace_ttl_seconds` | 追踪用户数/追踪时长；超过人数上限时会移除当前最早登记的记录 |

**处理顺序与历史保留规则**：
- 先经过用户伪造 `[Poke:poke]` 文本标识符过滤
- 再经过真实 poke 事件检测（仅 QQ + aiocqhttp / OneBot poke notice）
- 再经过 `poke_message_mode`、群白名单等原有过滤机制
- **只有最终确实由本插件接手处理的真实 poke**，才会在概率筛选/读空气前额外生成一条“戳一戳历史事件文本”
- 当前轮 AI 看到的仍是运行时 `[戳一戳提示]...`；保存历史时这类运行时提示会被过滤，但新的事件文本会保留下来，供后续上下文理解

### 5.6 缓存消息摘要

将待处理池中的近期未回复消息汇总，作为上下文提供给 AI，让 AI 了解"之前说了什么"。

---

## Phase 6 · 群聊等待窗口

> 收到一条消息后先等待一小段时间，看是否有更多消息到来，然后将它们**批量合并**处理。模拟人类"看完再回"的行为。

| 配置项 | 作用 |
|--------|------|
| `enable_group_wait_window` | 启用等待窗口 |
| `group_wait_window_timeout_ms` | 等待超时时间（毫秒，200-30000） |
| `group_wait_window_max_extra_messages` | 最多额外收集的消息数 |
| `group_wait_window_max_users` | 最多同时追踪的用户数 |
| `group_wait_window_attention_decay_per_msg` | 每收到一条消息时注意力衰减量 |
| `group_wait_window_at_mode` | @消息窗口行为模式（force_close/intercept/immediate/bypass）。这里的“@消息”核心上仍然是 @AI 自己；普通 `@别人` / `@多个别人` 不应仅因为包含At就误触发窗口打断逻辑。 |
| `group_wait_window_keyword_mode` | 关键词消息窗口行为模式（intercept/force_close/immediate/bypass） |
| `group_wait_window_poke_mode` | 戳一戳窗口行为模式（bypass/force_close） |
| `group_wait_window_merge_at_list_mode` | @合并模式 whitelist/blacklist（在 at_mode=intercept/immediate/force_close 时生效）。命中后，窗口逻辑只会洗刷掉 @AI 自己的 At 组件，不会移除或折叠其他人的 At。 |
| `group_wait_window_merge_at_user_list` | @合并的用户列表（在 at_mode=intercept/immediate/force_close 时生效）。无论名单如何命中，窗口侧都只洗刷 AI 自己的 At，不洗刷他人的 At，不折叠重复的他人 At。 |

**消息类型行为模式**：每种消息类型可独立配置与窗口的交互方式：
- `force_close` — 可开启窗口；窗口期内再次收到同一用户的 @AI 消息时，若命中名单，则先剥离 @AI 并按窗口缓存链处理后立即结束窗口；未命中名单则回退为原有强制结束窗口
- `intercept` — 可开启窗口；窗口期内被窗口侧接管的 @AI 消息会剥离 @AI 并缓存到窗口中批量处理
- `immediate` — 不开启窗口；但若已有窗口，窗口期内再次收到同一用户的 @AI 消息时，若命中名单，则先剥离 @AI 并按窗口缓存链处理后立即结束窗口；未命中名单则回退为原有强制结束窗口
- `bypass` — 不开启窗口；不影响已有窗口，消息完全独立处理

---

## Phase 7 · AI 决策判断（第二层过滤 — "读空气"）

> 这是插件的**核心机制**。通过概率筛选的消息，由 AI 来判断"现在适不适合回复"。

### 7.1 回复密度检查

在调用 AI 决策前，先检查近期回复频率：

| 配置项 | 作用 |
|--------|------|
| `enable_reply_density_limit` | 启用回复密度限制 |
| `reply_density_window_seconds` | 统计窗口（秒） |
| `reply_density_max_replies` | 窗口内最大回复数（硬限制） |
| `reply_density_soft_limit_ratio` | 软限制比例（默认0.6，即60%时开始提示AI） |
| `reply_density_ai_hint` | 软限制时向AI注入提示 |

- 达到**硬限制** → 直接跳过 AI 判断，消息仅缓存
- 达到**软限制** → 继续 AI 判断，但在提示词中加入"你已经回复较多，适当减少"

### 7.2 AI 决策调用

构建提示词并调用 AI，让其判断是否应该回复。提示词中会在显眼位置额外说明：\n- 如果本次判断已注入人格，则按该人格视角判断；如果没有注入人格，则按中性判断任务执行\n- 关键词是如何被代码直接提取并通过 `[系统信息-关键词触发]` 传给 AI 的\n\n提示词中包含：

| 信息 | 来源 |
|------|------|
| 读空气系统指令 | 内置 + `decision_ai_extra_prompt` |
| 是否被@/关键词触发 | Phase 3 结果 |
| 当前注意力状态 | 注意力机制（若启用） |
| 当前情绪状态 | 情绪系统（若启用） |
| 对话疲劳等级 | 疲劳系统（若启用） |
| 回复密度提示 | 密度限制（若软限制触发） |
| 兴趣话题信息 | 拟人模式（若启用） |
| 决策历史 | 拟人模式（保持一致性） |
| 记忆信息 | 记忆注入（若 `memory_insertion_timing = pre_decision`） |
| 近期未缓存消息 | 提供上下文 |

| 配置项 | 作用 |
|--------|------|
| `decision_ai_provider_id` | 决策AI的提供商ID（留空用默认）。同时也是主动对话判断AI和频率判断AI的提供商 |
| `decision_ai_include_persona` | 是否为读空气AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性判断任务执行 |
| `decision_ai_persona_name` | 仅在 `decision_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格；填写完整人格名=强制让读空气AI按该人格判断，找不到时自动回退 |
| `decision_ai_prompt_mode` | 提示词模式：`append`（追加到内置提示后）或 `override`（完全覆盖） |
| `decision_ai_extra_prompt` | 自定义的额外决策提示词 |
| `decision_ai_timeout` | 决策AI调用超时（秒） |
| `enable_decision_ai_reasoning` | 开启读空气AI额外推理。AI必须先输出推理块，再在最后一行单独给出 yes/no，推理块自动剥离 |
| `decision_ai_reasoning_log` | 开启后将读空气AI推理相关内容输出到日志 |
| `decision_ai_reasoning_log_mode` | 推理日志输出模式：`processed` = 处理后的推理块，`raw` = 模型原始文本 |
| `judgment_reasoning_start_marker` | 三个判断型AI共享的推理起始符（默认 `[[GCP_REASONING_START]]`，Web 面板三处入口同步显示/同步生效） |
| `judgment_reasoning_end_marker` | 三个判断型AI共享的推理截止符（默认 `[[GCP_REASONING_END]]`，Web 面板三处入口同步显示/同步生效） |

### 7.3 注意力机制对决策的影响

| 配置项 | 作用 |
|--------|------|
| `enable_attention_mechanism` | 启用多用户注意力追踪 |
| `attention_increased_probability` | 高注意力用户的提升概率 |
| `attention_decreased_probability` | 低注意力用户的降低概率 |
| `attention_duration` | 注意力提升持续时间 |
| `attention_max_tracked_users` | 最大同时追踪用户数 |
| `attention_decay_halflife` | 注意力指数衰减半衰期 |
| `enable_attention_emotion_detection` | 检测消息情绪调整注意力 |
| `enable_attention_spillover` | 注意力溢出到其他用户 |
| `attention_spillover_ratio` | 溢出比例 |
| `enable_attention_cooldown` | 高注意力后冷却 |
| `cooldown_max_duration` | 最大冷却时间 |

#### 注意力冷却（未接续谈保护 + 正式冷却）

| 配置项 | 作用 |
|--------|------|
| `enable_attention_cooldown` | 启用注意力冷却 |
| `enable_cooldown_auto_release` | 启用正式冷却超时自动解冻 |
| `cooldown_max_duration` | 最大冷却时间 |
| `cooldown_trigger_threshold` | 触发阈值 |
| `enable_pending_attention_cooldown` | 启用未接续谈保护层 |
| `pending_cooldown_grace_user_messages` | 未接续谈保护阶段最多观察同一用户后续多少条自己的消息 |
| `pending_cooldown_max_wait_seconds` | 未接续谈保护最长等待时间 |
| `pending_cooldown_same_user_probability_floor` | 未接续谈保护期间给同一用户保留的最低概率保护 |

> 说明：
> - 这套保护补丁只用于**普通概率路径消息**（非@AI、非关键词触发），专门减少“上一条看起来不是发给AI的话把下一条普通消息误伤掉”的情况。其他人的消息不会推进或取消该用户的未接续谈保护。
> - `enable_attention_cooldown` 是正式冷却总开关；`enable_pending_attention_cooldown` 只控制是否先进入待冷却阶段。也就是说：开冷却 + 开待冷却 = 先待冷却再转正式冷却；开冷却 + 关待冷却 = 直接进入正式冷却。
> - “读空气未回复衰减”现在是独立机制：不启用冷却时可直接生效；启用冷却时，只有正式冷却后才会对该用户执行衰减。
> - 正式冷却相关的超时自动解冻，只受 `enable_cooldown_auto_release` / `cooldown_max_duration` 控制；待冷却阶段只会超时失效，不会自动转成正式冷却。
> - 冷却状态不再长期落盘，而是运行态内存数据；插件或平台重启后会清空。
> - 如果某个用户已经不在当前会话的注意力追踪列表中，则该用户的待冷却/正式冷却状态会在同步检查时被直接移除，不再继续推进。

### 7.4 对话疲劳对决策的影响

| 配置项 | 作用 |
|--------|------|
| `enable_conversation_fatigue` | 启用对话疲劳 |
| `fatigue_threshold_light` / `medium` / `heavy` | 轻/中/重疲劳的消息数阈值 |
| `fatigue_probability_decrease_light` / `medium` / `heavy` | 对应的概率衰减量 |
| `fatigue_closing_probability` | 疲劳时发出结束语的概率 |

### 7.5 决策结果

- **YES（应该回复）** → 进入 **Phase 7.5**（Smart 并发合并，仅 smart 模式）→ Phase 8（回复生成）
- **NO（不应该回复）** → 消息被存入自定义存储（custom_storage），作为未来回复的历史上下文
- **补充：如果 Phase 8 的普通群聊回复最终得到的是空文本** → 不会保存 AI 回复，也不会触发“成功回复后”的冷却解除/最近明确回复对象等副作用；但当前用户消息、待转正缓存以及窗口缓冲消息仍会继续按正常保存链路写入历史，避免上下文断裂

---

## Phase 7.5 · Smart 并发合并（`concurrent_mode=smart` 时生效）

> 此 Phase 仅在 `concurrent_mode=smart` 配置时启用，`legacy`（默认）模式下直接跳过至 Phase 8。

### 工作原理

AI 决策确认回复（Phase 7）后、实际调用 AI 生成回复（Phase 8）前，`SmartConcurrentManager` 尝试将**同期到达并通过 AI 决策**的其他消息合并进当前处理上下文：

```
消息A → AI决策通过 → 注册到待合并队列
消息B → AI决策通过 → 注册到待合并队列
  ↓
消息A 进入并发锁定、开始处理
  ↓
Phase 7.5：消息A 尝试合并 → 发现消息B 在队列中
  → 将消息B 标记为"已合并"
  → 消息B 的内容追加至 window_buffered_messages 区域
  → 消息B 的 cached_data 写入窗口缓冲缓存（Phase-2 保存路径）
  → 重新生成包含消息B 的 formatted_context
  ↓
消息B 的处理协程：检测到 is_merged=True → 跳过独立AI调用 → 返回
  ↓
Phase 8：AI 一次性感知消息A + 消息B 的内容，生成完整回复
```

### 与现有机制的关系

| 机制 | 是否冲突 | 说明 |
|------|---------|------|
| 群聊等待窗口（GWW） | 不冲突 | GWW 在 Phase 6 拦截（AI 决策前）；Smart 合并在 Phase 7.5（AI 决策后）；两者处理不同场景 |
| legacy 并发锁 | 不冲突 | Smart 模式下，被合并的消息检测到 `is_merged=True` 后直接返回，不再参与锁等待 |
| 多用户消息 | 天然支持 | 合并区域格式含发送者名字和 ID，AI 可区分多人消息 |
| 历史记录 | 完整保存 | 合并的消息以 `window_buffered=True` 写入缓存，经 Phase-2（`after_message_sent`）正常保存到历史 |

### 相关配置

| 配置项 | 作用 |
|--------|------|
| `concurrent_mode` | `legacy`（默认，向后兼容）或 `smart`（智能合并模式） |
| `smart_concurrent_merge_wait` | 合并超时时间（秒），超时后未被合并的消息作为独立消息处理（默认 30 秒） |
| `concurrent_wait_max_loops` | legacy 模式：最大等待循环次数 |
| `concurrent_wait_interval` | legacy 模式：每次循环等待秒数 |

### 7.5 Smart 并发批次回复提示（可选增强）

当 `concurrent_mode=smart` 且 `enable_smart_batch_reply_hint=true` 时：
- Smart 模式不仅会把当前消息后紧接着到达的追加消息一起注入上下文；
- 回复阶段还会动态提示 AI：当前触发对象仍是本次的主要回复对象；
- 如果批次里其他人的消息确实值得接，可以像真人一样自然顺带带一句；
- 如果其他人的消息不值得回，可以忽略；
- 不要机械逐条点名回答，也不要强行把所有人都回一遍。

这项增强只影响“怎么组织这次回复”，不会改变读空气AI在 Phase 7 中的主体判断语义，也不会改写保存历史、注意力记录、最近明确回复对象等下游逻辑。动态提示会在保存前自动过滤，不会进入普通历史正文。

---

## Phase 7.5 · Smart 并发合并

当 `concurrent_mode=smart` 时，插件会在普通消息主线上尝试按真实到达顺序合并批次，让读空气AI和回复AI一起感知当前消息后紧接着到达的追加消息，以减少顺序颠倒和逐条重复回复。

⚠️ 这里的 Smart 逻辑主要作用于“普通消息批次合并”和“回复阶段提示增强”，不直接改变主动对话流程本身。

⚠️ 如果某个会话此时正被主动对话流程占用，普通链路在缓存转正/保存前的等待检测，当前仍然复用通用的 `concurrent_wait_max_loops` 与 `concurrent_wait_interval` 轮询参数，而不会切换成 Smart 专属等待策略。

⚠️ 选择 `concurrent_mode=smart`，也不代表传统并发保护会完全失效；更准确地说，是普通对话链路会优先尝试 Smart 批处理，但底层传统并发等待与兜底保护仍然存在，用于处理主动对话占用、等待超时、以及 Smart 未覆盖的异常路径。


AI 决定要回复后，进入回复生成阶段。

### 8.1 上下文构建

| 配置项 | 作用 |
|--------|------|
| `max_context_messages` | 历史消息最大条数（-1=不限制） |
| `custom_storage_max_messages` | 自定义存储最大条数 |

### 8.2 记忆注入

| 配置项 | 作用 |
|--------|------|
| `enable_memory_injection` | 启用长期记忆注入 |
| `memory_plugin_mode` | 模式：`auto`（默认，自动检测：优先 LivingMemory → 回退 Legacy → 都没有则跳过）、`legacy`（传统模式）、`livingmemory`（智能模式） |
| `memory_insertion_timing` | 注入时机：`pre_decision`（决策前，影响是否回复）或 `post_decision`（决策后，只影响回复内容） |
| `livingmemory_version` | LivingMemory架构适配方式：`auto`（推荐，自动识别 v2/v1）、`v2`、`v1` |
| `livingmemory_persona_compat_mode` | 人格ID兼容方式：`auto`（推荐）/ `resolver_only` / `legacy_only` / `off` |
| `livingmemory_top_k` | 记忆召回条数 |

> Web 面板中的技术树「记忆注入」节点会同步展示以上配置，便于直接在可视化界面调整记忆兼容策略。

### 8.3 工具提示与 Hook 恢复

回复生成阶段不会一开始就把完整上下文直接塞给 `event.request_llm()`。当前链路仍然保持原有设计：

1. 先用**短消息**（或空消息占位符）触发 `event.request_llm()`  
2. 让其他插件与平台 Hook 先运行  
3. 最后在 `on_llm_request` 中恢复：
   - `req.prompt = 插件完整 full prompt`
   - `req.contexts = 插件既有 contexts 策略值`
   - `req.system_prompt = 插件人格 + 其他插件附加内容（正常路径下会尽量去掉已知平台 LTM 重复注入）`

当前版本对 `system_prompt` 恢复做了**兼容增强**：
- 优先沿用旧版精确字符串命中路径
- 若平台对 persona 包装或换行做了轻微调整，则尝试轻量兼容识别
- 若仍无法高置信度识别，则进入**保守回退模式**：优先保留当前 `req.system_prompt`，并输出 warning 日志，但**不会中断回复流程**

因此：
- 成功路径下，效果与旧版尽量保持一致
- 失败路径下，最差退化为“可能重复但仍可回复”，不会因为提示词识别失败导致整条消息链崩掉


| 配置项 | 作用 |
|--------|------|
| `enable_tools_reminder` | 是否启用工具提醒文本。开启后，在 `on_llm_request` 阶段基于**当前会话最终可见工具集**生成工具提示并注入到运行时 prompt；关闭后不注入任何工具提醒文本，但不影响 AI 实际调用工具 |
| `tools_reminder_persona_filter` | 是否在提醒层按人格过滤工具。仅在 `enable_tools_reminder=true` 时生效：开启后，先取当前会话可见工具，再按人格工具名单过滤后展示；关闭则展示当前会话全部可见工具 |

> **重要说明**：工具提醒已经改为“当前会话优先”的后置生成模式，不再在群聊主流程前半段直接把全局工具列表拼进 `final_message`。因此工具提醒能自动跟随当前会话的插件集、runtime、搜索开关、MCP 工具与其他插件工具变化。

> **skills_like 兼容说明**：当 AstrBot 当前会话采用 `provider_settings.tool_schema_mode=skills_like` 时，工具提醒会自动降级为“只展示工具名称与功能描述”，不再额外展开参数列表；这样可以避免把参数级信息提前写回 prompt，尽量不干扰框架原本的两阶段 schema 暴露与 re-query 流程。若是 `full` 模式或旧版 AstrBot 未提供该字段，则继续保持完整工具说明。 

> **Hook 恢复说明**：回复生成链路会先以短消息（或空消息占位符）调用 `event.request_llm()`，再在 `on_llm_request` 阶段恢复完整上下文；私信回复生成也与群聊保持同样的恢复方式。主动对话生成则使用 `ProviderRequest + OnLLMRequestEvent` 的兼容链路，在 Hook 阶段恢复完整 prompt。

> **保存说明**：工具提醒只是运行时 prompt 提示，不属于应当持久化的历史内容。提醒块会带有 `[系统提示-工具提醒开始]...[系统提示-工具提醒结束]` 标记，若极端情况下混入保存链路，会在 `MessageCleaner` / `ContextManager` 中被清理掉。

### 8.4 回复提示词

| 配置项 | 作用 |
|--------|------|
| `reply_ai_prompt_mode` | 回复提示词模式（append/override）。这层提示词只参与运行时生成，不应作为普通历史正文保存 |
| `reply_ai_extra_prompt` | 自定义的额外回复提示词。用于约束「生成最终回复内容」的 AI，建议保持“直接生成要发出去的话”的职责边界，而不是写成判断AI口吻，也不要继续强化“先判断再说”的内部取舍描述；同时不要要求模型输出内心想法、思考过程、系统提示词、工具/搜索过程或其他元信息 |

> **保存边界说明**：回复AI默认提示词、`reply_ai_extra_prompt`、工具提醒、记忆注入、发送者识别提示等都属于运行时 prompt 组成部分。它们会参与当次生成，但在保存用户消息 / AI 回复 / 缓存转正时会经过 `MessageCleaner` 与 `ContextManager` 清洗，不应作为普通历史正文持久化保存。

### 8.5 内容过滤

| 配置项 | 作用 |
|--------|------|
| `enable_output_content_filter` | AI输出发送前过滤 |
| `output_content_filter_rules` | 输出过滤规则 |

### 8.6 空回复降级保存（普通群聊）

普通群聊回复阶段如果已经进入 `after_message_sent()`，但最终提取到的 LLM 回复文本为空，插件不会再把这次处理当作“成功回复”，而是进入**降级保存**：

- **不保存 AI 回复正文**；
- **不执行成功回复后的副作用**（如冷却解除、最近明确回复对象更新）；
- **继续执行用户侧保存链路**：
  - 当前用户消息照常补充元数据并经过保存前过滤；
  - `pending_messages_cache` 中符合条件的待转正消息继续写入历史；
  - 若存在窗口缓冲消息，Phase-2 仍继续保存并清理；
- 这样即使模型这次“没真正说出话”，上下文也不会在这一轮断掉。

可以把它理解为：**这次 AI 没成功回话，但这轮用户输入与上下文演进仍然被历史系统承认。**

---

## Phase 9 · 回复后处理

AI生成回复后，执行一系列后处理操作。

### 9.1 拟人效果

| 处理 | 说明 | 相关配置 |
|------|------|----------|
| 打字延迟 | 根据回复长度模拟打字时间 | `enable_typing_simulator`、`typing_speed`、`typing_max_delay` |
| 打字错误 | 基于拼音相似性生成自然错别字 | `enable_typo_generator`、`typo_error_rate` |

### 9.2 戳一戳回复

| 配置项 | 作用 |
|--------|------|
| `enable_poke_after_reply` | 回复后戳用户 |
| `poke_after_reply_probability` | 戳的概率 |
| `poke_after_reply_delay` | 戳之前的延迟 |

**保存规则**：
- 若 AI 回复后戳一戳动作真实成功，会在正常 AI 回复保存完成后，额外以 **assistant** 视角单独保存一条戳一戳历史事件
- 若是收到 poke 后反戳成功，也会额外单独保存一条 assistant 视角历史事件
- 这两条历史事件与 AI 正文回复分开保存，不拼接成同一条消息

### 9.3 重复检测

| 配置项 | 作用 |
|--------|------|
| `enable_duplicate_filter` | 检测并过滤重复回复 |
| `duplicate_filter_check_count` | 检查最近N条回复 |
| `enable_duplicate_time_limit` | 重复检测时间限制 |
| `duplicate_filter_time_limit` | 时间限制（秒） |

### 9.4 存储保存

消息保存采用两阶段机制：

| 阶段 | 保存内容 | 说明 |
|------|----------|------|
| **Phase-1** | 普通缓存消息 + 当前用户消息 + AI回复 | 主体保存。AI回复若存在窗口缓冲消息，会自动追加 `[追加消息上下文]` 标记 |
| **Phase-1（空回复降级）** | 普通缓存消息 + 当前用户消息 | 当本次普通群聊回复最终为空文本时触发：不保存 AI 回复，但仍完成上下文补保存，避免历史断层 |
| **Phase-2** | 窗口缓冲消息 | 仅在等待窗口收集了追加消息时执行，保存在AI回复之后 |

> **时序说明**：Phase-2 的窗口缓冲消息在历史中排在AI回复之后，但AI回复时已通过上下文拼接看到了这些消息。`[追加消息上下文]` 标记帮助后续AI理解这一时序差异。

| 配置项 | 作用 |
|--------|------|
| `enable_save_content_filter` | 保存前过滤 |
| `save_content_filter_rules` | 保存过滤规则 |

### 9.5 状态更新

回复完成后自动更新以下系统状态：

- **传统模式概率提升**：关闭 `enable_attention_mechanism` 时，`after_reply_probability` 生效，持续 `probability_duration` 秒；如果这段时间内再次成功回复，会刷新计时
- **注意力增强**：开启 `enable_attention_mechanism` 时，对当前用户的注意力提升，并替代传统回复后提升模式
- **情绪更新**：根据对话内容更新情绪状态
- **疲劳累加**：对话轮次计数增加（仅注意力模式）
- **吐槽系统衰减**：成功回复减少被无视计数
- **主动对话状态**：更新互动评分
- **统计记录**：记录回复事件到统计系统
- **回复密度统计**：记录本次回复，供后续密度限制判断使用

---

## 独立系统：主动对话

> 主动对话是一个**独立于消息处理流程**的系统，通过定时任务在群聊沉默一段时间后由 AI 主动发起话题。

### 流程

```
定时检查（每 proactive_check_interval 秒）
    ↓
群聊是否沉默超过 proactive_silence_threshold？
    ↓（是）
🆕 普通对话冷静期检查（AI 刚通过普通流程回复过？）
    ↓（未在冷静期内）
安静时段检查（23:00-07:00默认不触发）
    ↓（不在安静时段）
用户活跃度检查（需要有人在活跃）
    ↓（满足）
随机概率检查 (proactive_probability)
    ↓（通过）
主动对话预判断AI判断时机是否合适（enable_proactive_ai_judge）
    ↓（合适）
生成并发送主动消息
    ↓
更新互动评分（自适应系统）
```

### 🆕 错误处理与零副作用跳过

主动对话流程中，**AI 调用失败被视为「本次操作未发生」**，不会触发任何状态变更：

```
主动对话预判断阶段 (步骤 4.5)
    ├── 判断通过 (yes) → 继续步骤 5
    ├── 判断不通过 (no) → 正常跳过，重置沉默计时器 ✅ 业务逻辑
    ├── 超时 (TimeoutError) → 跳过，不影响任何机制 ❌ 零副作用
    └── AI调用失败 (Exception) → 跳过，不影响任何机制 ❌ 零副作用

AI生成阶段 (步骤 5)
    ├── 生成成功 → 继续发送和保存
    ├── 未生成有效内容 → 跳过
    ├── 超时/网络错误 → 跳过，不影响打分/概率/冷淡期 ❌ 零副作用
    └── 服务商故障 (502等) → 跳过，输出清晰错误信息 ❌ 零副作用

发送/保存阶段 (步骤 6-7)
    ├── 成功 → 步骤8: record_bot_reply + 概率提升
    └── 失败 → 跳过，不影响打分/概率/冷淡期 ❌ 零副作用
```

> **关键区别：正常跳过 vs 异常跳过**
>
> | 场景 | `last_bot_reply_time` | 打分/概率 | 冷淡期 | 原因 |
> |------|:---:|:---:|:---:|------|
> | AI 预判断返回 `no` | ✅ 更新 | — | — | 正常业务结果 |
> | AI 预判断超时/失败 | ❌ 不更新 | ❌ 不变 | ❌ 不触发 | 外部故障 |
> | AI 生成成功并发送 | ✅ 更新 | ✅ 触发 | ✅ 可能退出 | 正常完成 |
> | AI 生成失败 (502等) | ❌ 不更新 | ❌ 不变 | ❌ 不触发 | 服务商故障 |

### 相关配置

| 配置项 | 作用 |
|--------|------|
| `enable_proactive_chat` | 启用主动对话 |
| `proactive_silence_threshold` | 沉默多久后触发（秒） |
| `proactive_normal_reply_cooldown` | 🆕 普通对话冷静期（秒）。AI 通过普通流程回复后在此时间内不触发主动对话，避免「刚回完又主动发言」。设为 0 禁用（默认 60 秒） |
| `proactive_probability` | 触发概率 |
| `proactive_check_interval` | 检查间隔（秒） |
| `proactive_require_user_activity` | 要求有用户活跃 |
| `proactive_min_user_messages` | 最少用户消息数 |
| `proactive_user_activity_window` | 活跃时间窗口 |
| `proactive_max_consecutive_failures` | 连续失败次数上限 |
| `proactive_cooldown_duration` | 失败后冷却时间 |
| `proactive_enable_quiet_time` | 安静时段开关 |
| `proactive_quiet_start` / `proactive_quiet_end` | 安静时段起止 |
| `enable_proactive_ai_judge` | 主动发言前由主动对话预判断AI判断当前是否适合说话 |
| `proactive_ai_judge_include_persona` | 是否为主动对话预判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性时机判断执行 |
| `proactive_ai_judge_persona_name` | 仅在 `proactive_ai_judge_include_persona=true` 时生效。留空=使用当前会话当前生效的人格；填写完整人格名=强制让主动对话预判断AI按该人格判断，找不到时自动回退 |
| `proactive_ai_judge_prompt` | 主动对话预判断提示词。留空使用默认提示词；开启额外推理时无需手动写推理协议，若缺失系统会自动补充且保留原正文 |
| `proactive_ai_judge_timeout` | 主动对话预判断超时 |
| `enable_proactive_ai_reasoning` | 开启主动对话判断AI额外推理。AI必须先输出推理块，再在最后一行单独给出 yes/no，推理块自动剥离 |
| `proactive_ai_reasoning_log` | 开启后将主动对话判断AI推理相关内容输出到日志 |
| `proactive_ai_reasoning_log_mode` | 推理日志输出模式：`processed` = 处理后的推理块，`raw` = 模型原始文本 |
| `judgment_reasoning_start_marker` / `judgment_reasoning_end_marker` | 与读空气AI、频率判断AI共用同一套推理起止标志符 |
| `proactive_enabled_groups` | 启用的群列表 |

### 自适应互动评分

| 配置项 | 作用 |
|--------|------|
| `enable_adaptive_proactive` | 启用自适应评分 |
| `score_increase_on_success` | 成功回复加分 |
| `score_decrease_on_fail` | 被无视减分 |
| `score_quick_reply_bonus` | 快速回复额外加分 |
| `score_multi_user_bonus` | 多人回复额外加分 |
| `score_streak_bonus` | 连续成功额外加分 |
| `score_revival_bonus` | 低分复活额外加分 |
| `interaction_score_decay_rate` | 每日衰减 |
| `interaction_score_min` / `interaction_score_max` | 分数范围 |

### 主动对话时段概率

| 配置项 | 作用 |
|--------|------|
| `enable_dynamic_proactive_probability` | 按时段调整主动概率 |
| `proactive_time_periods` | 时段配置（JSON字符串） |

### 吐槽系统

| 配置项 | 作用 |
|--------|------|
| `enable_complaint_system` | 连续被无视时AI会"吐槽" |
| `complaint_trigger_threshold` | 触发吐槽的失败次数 |
| `complaint_max_accumulation` | 最大累积失败数 |
| `complaint_decay_on_success` | 成功回复时减少的累积数 |

---

## 独立系统：情绪追踪

| 配置项 | 作用 |
|--------|------|
| `enable_mood_system` | 启用情绪系统 |
| `enable_negation_detection` | 检测否定表达 |
| `mood_decay_time` | 情绪自然衰减时间 |
| `mood_cleanup_threshold` | 清理过期情绪的阈值 |
| `mood_cleanup_interval` | 清理检查间隔 |

---

## 流程图：概率计算详解

```
                    initial_probability (基础概率)
                            ↓
                    频率调整基础层
               (base_probability / 覆盖基础概率)
                            ↓
            是否存在传统回复后临时提升？（仅注意力关闭时）
                 ↓是                         ↓否
  after_reply_probability 覆盖当前基础概率        保持当前基础概率
                 ↓
             动态时间段概率调整 (× factor)
                 ↓
          主动对话临时提升（如存在则叠加）
                 ↓
            注意力机制调整（仅注意力开启时）
                 ↓
              表情衰减 / 兴趣话题 / 回复密度
                 ↓
                  消息质量预判 (± boost)
                 ↓
               硬限制截断 [min, max]（用户配置）
                 ↓
                系统边界纠正 [0, 1]
                 ↓
                     最终概率值
                 ↓
              随机数 < 最终概率？
                 ↓            ↓
               通过          未通过
               (→ Phase 5)   (→ 缓存)
```

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考 →](CONFIG_REFERENCE.md) | [项目结构 →](PROJECT_STRUCTURE.md) | [桌面端兼容 →](DESKTOP_COMPATIBILITY.md)
