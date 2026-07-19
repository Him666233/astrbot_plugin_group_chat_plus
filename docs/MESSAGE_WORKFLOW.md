# 消息工作流程详解

> 本文档完整描述了群聊增强插件从**收到消息**到**发出回复**的完整处理流程，以及每个环节涉及的配置项。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考](CONFIG_REFERENCE.md) | [项目结构](PROJECT_STRUCTURE.md) | [桌面端兼容](DESKTOP_COMPATIBILITY.md)

---

## 流程总览

```
群聊消息到达
    ↓
Phase 0 · 空消息过滤（直接丢弃平台产生的真空消息，不进入任何后续流程）
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
Phase 7.5 · Smart 并发合并（concurrent_mode=smart 时，作用于普通消息批次合并、Smart+GWW 窗口融合、以及决策/回复双阶段批次感知提示增强；主动对话占用会话时的等待检测仍复用通用并发轮询参数）
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

转发节点内部按消息段顺序解析：文字、引用、@、图片、视频、语音、文件、表情等内容会依次写入同一条文本。媒体段能提取到 URL、文件名、路径、ID、MD5 等原始信息时，会写成 `[图片: ...]`、`[视频: ...]`、`[语音: ...]`、`[文件: ...]`；提取不到时只在该位置写入 `[图片（识别失败）]`、`[视频（识别失败）]`、`[语音（识别失败）]`、`[文件（识别失败）]`，不会吞掉同一节点里的其他内容。

引用消息会先解析其内联 `content/message/chain/origin`，没有内联内容时再尝试按引用 ID 获取原消息。引用内容里如果继续包含图片、视频、语音、文件或嵌套转发，仍然走同一套逐段解析和局部占位逻辑。转发内部的图片表情包只在平台提供可靠字段时标记为 `[表情包图片]`；缺少 `sub_type`、`summary`、`image_type` 等表情包识别字段时无法可靠区分，会按普通图片处理。

| 配置项 | 作用 |
|--------|------|
| `enable_forward_message_parsing` | 是否解析 QQ / OneBot 合并转发消息 |
| `forward_max_nesting_depth` | 嵌套转发的最大解析深度（0=不展开嵌套，仅保留占位式降级；1-10=在限制内递归展开） |

### 2.3 @全体成员过滤

| 配置项 | 作用 |
|--------|------|
| `enable_ignore_at_all` | 忽略@全体成员消息，避免群公告触发AI。开启后消息直接短路——不缓存、不保存、不处理 |
| `at_all_message_mode` | `@全体成员` 专用处理模式：可按普通消息处理、跳过概率筛选、跳过概率+读空气，或仅临时提升当前消息概率 |
| `at_all_probability_boost_value` | `at_all_message_mode=probability_boost` 时，仅对当前这条@全体成员消息增加的临时概率值 |

> `@全体成员` 与 `@他人过滤` 是两条独立规则：如果先命中 `enable_ignore_at_all`，消息会直接短路；若未忽略，再按 `at_all_message_mode` 决定它后续是像普通消息一样处理、跳过概率筛选、跳过概率+读空气，还是只对当前这一条消息临时提升概率。短路或后续只缓存不回复时，插件只消费当前事件的 AstrBot 默认 LLM 兜底，避免平台再次强制回复；这不会主动停止事件传播，也不会阻止其他插件按框架顺序处理。

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

**匹配规则：** 大小写敏感，子串匹配（`in` 运算符），仅匹配消息链中的用户消息文本（不包含时间戳、发送者信息、`[系统提示]` 等后续注入的元数据）。**注意：如果启用了转发消息解析（Phase 2.2），解析后的转发内容文本也会作为消息文本的一部分参与匹配**——转发内容中的关键词同样会触发响应。详见 [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md#关键词系统)。

### 3.3 黑名单关键词

| 配置项 | 作用 |
|--------|------|
| `blacklist_keywords` | 黑名单词列表，命中后**直接丢弃消息** |

**匹配规则：** 与触发关键词相同——大小写敏感，子串匹配，同样覆盖转发解析后的内容。

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

> **缓存消息的内部结构**：待处理池中的每条缓存消息以字典形式存储，**消息内容（content）与元数据字段分离**：
> - `content`：纯消息文本，已包含转发解析结果、引用消息格式化文本（`[引用 >>> ...]`）、@内联标记（`[At:xxx|name]`）、视频/语音/文件占位标记（`[视频: /path]` 等）。图片方面：概率筛选未通过时未解析的 `[图片]` 占位会被移除，AI 决策不通过时已转文字的保留 `[图片内容: xxx]` 或多模态路径 `[图片: /path]`。
> - 元数据字段：`sender_id`、`sender_name`、`message_timestamp`、`mention_info`、`is_at_message`、`has_trigger_keyword`、`persistent_poke_event_text`、`group_id`、`group_name`、`group_role` 等独立存储，每条消息绑定自己的元数据，不会与其他消息混淆。
>
> 当缓存消息被 AI 作为"📦近期未回复"背景上下文读取时，系统从元数据字段中取出时间戳和发送者拼接到消息前缀，但**不注入 `[系统提示]`**（背景上下文不需要"有人在@你"等触发说明）。当缓存消息转正保存到磁盘时，系统调用 `add_metadata_from_cache` 完整拼接所有元数据（时间戳、发送者、@指向说明、`[戳一戳事件]` 等），再经 `MessageCleaner.clean_message` 剥离运行时提示后落盘。

| 配置项 | 作用 |
|--------|------|
| `pending_cache_max_count` | 待处理池最大消息数 |
| `pending_cache_ttl_seconds` | 缓存消息的过期时间（在下一条消息到来时执行清理） |
| `enable_idle_cache_flush` | 启用冷群缓存自动转正：群聊静默超过触发延迟后，自动将待处理池消息写入自定义存储和 `platform_message_history` 表（可在 Web Chat UI 中查看），避免过期丢失 |
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

当 `@全体成员` 消息最终进入概率过滤缓存、决策不回复缓存或窗口缓冲，而没有由插件发送回复时，插件会把当前事件标记为已由插件接管默认 LLM 兜底。这个标记只作用于当前事件，不参与缓存定位；下一条消息会重新按平台唤醒规则判断。

### 5.3 多媒体消息处理

支持图片、视频、语音、文件四种媒体类型的识别与传递。

**图片处理**：两种模式可选：
- **多模态直传**：`enable_image_processing=true` 且 `image_to_text_provider_id` 留空时，图片 URL 直接传递给多模态 AI，消息文本中内联 `[图片: /path/to/image.png]` 标记（路径紧跟在标记右边，与视频/语音/文件标记格式一致）。这条路径不受 `max_images_per_message` 截断；若单张图片路径提取失败，对应位置降级为 `[图片（识别失败）]`
- **转文字模式**：配置 `image_to_text_provider_id` 后，先按图片缓存逐张命中，命中的图片替换为 `[图片内容: xxx]`；未命中的图片再调用 AI 转文字。仍然失败的图片会按原顺序降级为 `[图片（识别失败）]`，不继续传递原始图片
- **过滤模式**：`enable_image_processing=false` 或当前消息不符合 `image_to_text_scope` 时，原始图片会被直接剥离，不写入图片失败占位；过滤后严格等于空字符串 `""` 的消息会被丢弃，只剩空格、换行或制表符仍按有内容保留

| 配置项 | 作用 |
|--------|------|
| `enable_image_processing` | 启用图片处理 |
| `image_to_text_scope` | 处理范围：`all`（所有消息）、`mention_only`（@或关键词触发时）、`at_only`（仅@时）、`keyword_only`（仅关键词触发时） |
| `image_to_text_provider_id` | 图片转文字的AI提供商ID（留空=多模态直传模式） |
| `image_to_text_prompt` | 发送给AI的图片描述提示语 |
| `image_to_text_timeout` | API调用超时时间。配置了 `image_to_text_fallback_provider_ids` 时，超时/报错/空响应会自动切换备用提供商；仅当 `image_to_text_provider_id` 非空时激活 |
| `image_to_text_fallback_provider_ids` | 🔁 图片转文字备用提供商列表，留空=不启用。每个提供商单独计时 |
| `max_images_per_message` | 单条消息最大图片转文字数量；不限制多模态直传图片数 |
| `enable_image_description_cache` | 缓存图片描述结果（节省API调用） |
| `image_description_cache_max_entries` | 缓存最大条目数；当前主缓存文件为 `image_cache/descriptions.jsonl`，若检测到旧版残留路径 `image_description_cache.json`，清理逻辑也会兼容处理 |

**非图片媒体（视频/语音/文件）**：插件自动提取文件路径，内联注入到消息文本中：
- `[视频: /path/to/video.mp4]` — 路径提取成功；失败时降级为 `[视频]` 占位符
- `[语音: /path/to/audio.amr]` — 路径提取成功，同时传入 `audio_urls` 供多模态 AI 直读；失败时降级为 `[语音]` 占位符
- `[文件: name, /path/to/file]` — 路径提取成功；失败时降级为 `[文件: name]` 占位符

**缓存行为**：消息进入缓存时会清空不可长期依赖的 `image_urls`；缓存/窗口缓存只保留已经解析成文字的 `[图片内容: xxx]`（AI 转换）和 `[Image: xxx]`（平台自动理解），多模态直传的内联路径 `[图片: /path/to/image.png]` 也会保留（与视频/语音/文件标记一致）。原始无语义占位（`[图片]`、`[Image]`）和图片识别失败占位（`[图片（识别失败）]`、`[Image Captioning Failed]`）都会被移除。视频/语音/文件标记均保留。经过所有过滤后仅当内容严格等于空字符串 `""` 时才丢弃；只剩空格、换行或制表符仍按有内容保留。

### 5.3.1 图片缓存与重置边界

- **图片缓存清理**（包括 `gcp_clear_image_cache` 指令与 Web 面板对应操作）只清理图片描述缓存，不清理 `chat_history/...` 聊天记录、注意力、概率或主动对话状态。
- 当前主缓存文件为 `image_cache/descriptions.jsonl`；旧版若遗留 `image_description_cache.json`，系统会在清理时一并兼容处理，但该旧路径不再是当前主实现。
- **单会话重置**（`gcp_reset_here`）会删除该会话的插件自定义聊天记录 JSON 文件、清理该会话全部运行态（20+ 项）、设置 `history_cutoff.json` 截止时间戳（仅过滤 `platform_message_history` 表读取）。**不会**把图片描述缓存当成会话历史一起清掉。若自定义 JSON 文件因异常未被删除，可通过 Web 会话管理或文件管理器找到 `chat_history/<platform>/<type>/<chat_id>.json` 手动清空或删除。
- **全局重置**（`gcp_reset`）会清插件维护的全局运行态与本地持久化缓存、删除全部 `chat_history/` 目录文件，并为所有已知会话设置 `history_cutoff.json` 截止时间戳。图片描述缓存清理仍是独立动作。
- **⚠️ 截止时间戳的覆盖范围**：仅对 `platform_message_history` 表（SQLite）的读取路径生效（消息有 `created_at` 字段可比较）。以下路径**不受截止过滤**：
  - 插件自定义 `chat_history/...` JSON 存储（回退路径）— 依赖 reset 时直接删文件，无运行时过滤
  - AstrBot 官方 `conversations` 表（LLM 对话上下文）— 需执行平台 `/reset` 清理
  - 若自定义存储文件因异常未被删除而残留旧消息，AI 仍可能读到；此时可重试 `gcp_reset_here` 或通过 Web 端/文件管理器手动清空对应 JSON 文件

### 5.4 消息元数据注入

消息的最终格式为：**`[系统元数据]: [用户消息内容]`**，冒号 `:` 是系统信息与用户消息的固定分界线。所有系统提示词（时间戳、发送者、触发方式、`[戳一戳事件]` 持久化文本等）均拼接在冒号之前，用户发送的实际内容（含 @ 解析、转发解析、图片描述、`[引用 >>> ...]` 引用消息解析等）在冒号之后。**`[戳一戳提示]` 不在消息内部的元数据或内容中**，而是由 `format_context_for_ai` 在上下文拼接时追加到分隔符 `=====` 之外，仅运行时供 AI 参考，保存时由过滤规则自动移除。当任何系统元数据都不存在（所有开关关闭且无触发）时，不注入冒号。

| 配置项 | 作用 |
|--------|------|
| `include_timestamp` | 为消息添加时间戳 `[YYYY-MM-DD 周x HH:MM:SS]`（在冒号前） |
| `include_sender_info` | **仅控制冒号前元数据区**：为消息添加发送者信息 `[Name(ID:xxx)]`，同时控制 `[系统提示]` 触发方式说明的注入（在冒号前）。**不受此开关控制、始终输出的发送者信息**：引用消息内部的被引用者身份（`[引用 >>> Name(ID:xxx): ...]`）、@消息标签中的被@者解析（`[At:ID\|昵称]`）、戳一戳事件/提示文本中的发起者与目标身份——这四类发送者信息在消息内容区硬编码，关闭本开关无法隐藏 |

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
- **只有最终确实由本插件接手处理的真实 poke**，才会生成两层戳一戳标注：
  - **`[戳一戳事件]`**（持久化）：注入到消息格式中「冒号前」的系统元数据区域，随消息一起保存到历史上下文，不会被后续过滤清理
  - **`[戳一戳提示]`**（运行时仅 AI 可见）：追加在上下文分隔符 `=====` 之外，当前轮决策 AI 和回复 AI 均可看到，但保存时由 `MessageCleaner` 过滤规则自动移除
- 平台侧只提供 `Poke` 组件且正文为空时，插件会把真实组件格式化为 `[ComponentType.Poke]`，作为用户内容区占位；持久化语义仍由 `[戳一戳事件]` 提供
- 触发反戳时，会先后保存用户戳一戳事件（user 视角）和 AI 反戳动作（assistant 视角），均写入官方存储与自定义存储并绑定当前会话。所有戳一戳历史事件与 AI 正文回复分开保存，不拼接成同一条消息
- 戳过对方追踪提示（`[戳过对方提示]`）同样属于运行时提示，保存时会被过滤

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
| `group_wait_window_poke_mode` | 戳一戳窗口行为模式（bypass/force_close）。**无论配置为何种模式，戳一戳消息本身永远不会被窗口拦截缓存**——它始终走独立的正常处理流程（→ 概率 → AI决策 → 回复）。`force_close` 仅强制结束当前窗口（让窗口锚点消息立即进入后续流程），不影响戳一戳自身的处理路径。 |
| `group_wait_window_merge_at_list_mode` | @合并模式 whitelist/blacklist（在 at_mode=intercept/immediate/force_close 时生效）。命中后，窗口逻辑只会洗刷掉 @AI 自己的 At 组件，不会移除或折叠其他人的 At。 |
| `group_wait_window_merge_at_user_list` | @合并的用户列表（在 at_mode=intercept/immediate/force_close 时生效）。无论名单如何命中，窗口侧都只洗刷 AI 自己的 At，不洗刷他人的 At，不折叠重复的他人 At。 |

**消息类型行为模式**：每种消息类型可独立配置与窗口的交互方式。@消息和关键词消息在各模式下的核心行为一致（先缓存进窗口，再根据模式决定是否立即结束窗口），差异仅在于消息特有的预处理方式（@消息剥离 @AI 组件、关键词消息打掉关键词标记）。戳一戳消息永不缓存进窗口，仅根据模式决定是否 force_close 已有窗口：

**@消息**（`at_mode`）：受 `@合并名单`（whitelist/blacklist）精细控制
- `force_close` — 可开启窗口；窗口期内再次收到同一用户的 @AI 消息时，若命中名单，则先剥离 @AI 并按窗口缓存链处理后立即结束窗口；未命中名单则回退为原有强制结束窗口
- `intercept` — 可开启窗口；窗口期内被窗口侧接管的 @AI 消息会剥离 @AI 并缓存到窗口中批量处理
- `immediate` — 不开启窗口；但若已有窗口，窗口期内再次收到同一用户的 @AI 消息时，若命中名单，则先剥离 @AI 并按窗口缓存链处理后立即结束窗口；未命中名单则回退为原有强制结束窗口
- `bypass` — 不开启窗口；不影响已有窗口，消息完全独立处理

重复 @AI 会作为同一条消息中的多个 AI 提及处理，不会被误判为 @他人；若消息只有一个或多个 @AI 且没有正文，会进入单独无信息 @ 的判断链。`@AI + @他人` 或 `@AI + @全体` 这类混合消息不会被当作单独无信息 @；窗口接管时只剥离 AI 自己的 At 组件，剥离前的原始 @ 结构仍通过 `mention_info` 保留，用于 AI 展示和历史转正。`@全体` 的说明会通过 `is_at_all_message` 或 `mention_info.has_at_all` 兜底保存。

**关键词消息**（`keyword_mode`）：不受 `@合并名单` 控制，同用户的窗口内关键词消息**总是先被缓存进窗口**（关键词标记统一打掉），再按模式决定是否立即结束窗口
- `force_close` — 可开启窗口；窗口期内收到关键词消息会被缓存进窗口，随后立即结束窗口，与窗口内其他消息一起批量处理
- `intercept` — 可开启窗口；窗口期内收到关键词消息会被缓存进窗口（关键词标记打掉），窗口继续等待后续消息
- `immediate` — 不开启窗口；但若已有窗口，窗口期内收到关键词消息会被缓存进窗口，随后立即结束窗口，与窗口内其他消息一起批量处理
- `bypass` — 不开启窗口；不影响已有窗口，消息完全独立处理

### 窗口消息的令牌绑定与回落机制

每个等待窗口在创建时分配唯一递增令牌（`gww_token`）。窗口期内被拦截的每条消息都会携带该令牌写入缓存（`window_buffered=True, gww_token=<窗口令牌>`）。

> **窗口缓冲消息的触发标记清零**：窗口缓冲消息在写入缓存时，`is_at_message`、`has_trigger_keyword`、`persistent_poke_event_text` 会被**有意清零**（分别设为 `False`、`False`、`""`）。这是故意的设计：窗口机制将拦截的消息"降级"为普通上下文消息，统一交由窗口锚点消息批量处理，避免被拦截的消息在后续转正/回落流程中误触发独立的 @/关键词/戳一戳响应逻辑。消息的原始 @ 信息仍通过 `mention_info` 字段保留。
> `@全体` 不属于独立触发标记清零的范围：窗口缓冲消息会额外保留 `is_at_all_message`，并且转正时还会读取 `mention_info.has_at_all` 作为兜底，因此 AI 当前轮和后续历史都能看到 @全体说明。
> 如果被窗口吸收的消息同时也是平台唤醒消息，插件会消费当前事件的默认 LLM 兜底，防止平台在窗口已缓存后又为同一条消息触发默认回复。窗口隔离仍然由 `sender_id + gww_token` 控制；Smart 融合时才额外使用显式的 `gww_merge_group_id`。

**窗口批次的精准回落**：当窗口锚点消息经过读空气AI判定"不回复"后，系统会将该窗口令牌对应的所有窗口缓冲消息自动转为普通缓存（移除 `window_buffered` 标记）。若普通链路因主动对话/冷群转正 owner 占用等待超时而回退为普通缓存，也会同步把当前 `gww_token` 绑定的窗口缓冲消息转为普通缓存。回落机制具备三层隔离：

- **会话隔离**（`chat_id`）：不同群聊/私信的缓存互不影响
- **用户隔离**（`sender_id`）：仅转换当前窗口所属用户的消息，同群其他用户的窗口消息不受影响
- **窗口隔离**（`gww_token`）：同一用户先后或并发存在的多个窗口之间，令牌精确绑定，不会互相污染

回落后的消息等同于普通缓存消息：参与后续 Phase-1 转正、冷群转正、按时间戳与其它普通消息统排顺序。这确保了下一次成功触发回复时，上下文的先后顺序始终正确，旧窗口消息不会再以"追加消息"形式误拼入新对话。

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
| `decision_ai_timeout` | 决策AI调用超时（秒）。配置了 `decision_ai_fallback_provider_ids` 时，超时/报错/空响应会自动切换到下一个备用提供商重试 |
| `decision_ai_fallback_provider_ids` | 🔁 备用决策AI提供商列表（读空气/主动对话预判断/频率判断三处共用），留空=不启用。每个提供商单独计时 |
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
| `fatigue_closing_probability` | 中度/重度疲劳时发出结束语的概率。轻度疲劳不触发 |

### 7.5 决策结果

- **YES（应该回复）** → 进入 **Phase 7.5**（Smart 并发合并，仅 smart 模式）→ Phase 8（回复生成）
- **NO（不应该回复）** → 消息被缓存到待处理池（pending cache），等待后续某次成功回复时通过 Phase-1 转正写入自定义存储（custom_storage），或通过冷群转正在静默超时后自动写入。期间作为”📦近期未回复”上下文供 AI 参考
- **补充：如果 Phase 8 的普通群聊回复最终得到的是空文本** → 不会保存 AI 回复，也不会触发”成功回复后”的冷却解除/最近明确回复对象等副作用；但当前用户消息、待转正缓存以及窗口缓冲消息仍会继续按正常保存链路写入历史，避免上下文断裂

---

## Phase 7.5 · Smart 并发合并（`concurrent_mode=smart` 时生效）

> 此 Phase 仅在 `concurrent_mode=smart` 配置时启用，`legacy`（默认）模式下直接跳过至 Phase 8。

### 工作原理

消息在群聊入口通过去重和指令过滤后，会先把 `arrival_seq` 提前注册到 `SmartConcurrentManager`，确保后续即使图片处理、转发解析或其他前置流程耗时不同，anchor 仍按真实到达顺序决定。经过 Phase 5（内容处理）后、Phase 7（AI 决策判断）前，再挂载可合并的 payload 并按已注册顺序协调批次：

```
消息A → 群聊入口 register_arrival → 内容处理完成 → attach_payload
消息B → 群聊入口 register_arrival → 内容处理完成 → attach_payload
  ↓
消息A（最小 arrival_seq）执行 claim_batch（快照，一次性的）
  → 吸收消息B（payload_ready=True、非强制消息、未达批次上限）
  → 消息B 标记为 consumed
  → 消息B 的内容存入 _smart_batch_snapshots[A_id]（独立字典，非消息缓存）
  ↓
消息B 的处理协程：检测到 is_consumed=True → 跳过 DecisionAI → 返回
  （消息B 的 cached_data 通过 anchor 的 _smart_batch_snapshots 保留，将在回复后一并保存）
  ↓
消息A 进入 Phase 7（DecisionAI）→ Phase 8（ReplyHandler）
  → 两个 AI 均感知批次中所有消息（通过 format_context_for_ai(window_buffered_messages=...)）
```

这里的 `window_buffered_messages` 是上下文展示参数，不等同于 GWW 窗口缓存开关。Smart follower 的完整消息先保存在 `_smart_batch_snapshots[anchor_id]` 中，这是 Smart 专用的临时批次快照，不写入 `MessageCacheManager.pending_messages_cache`，也不属于普通缓存或 GWW 窗口缓存。`format_context_for_ai()` 只要收到非空追加消息列表，就会生成“紧接着的追加消息”区域；因此即使未开启 GWW，读空气 AI 和回复 AI 也能看到 Smart 批次中的完整 follower 消息。

普通等待窗口（GWW）与 Smart 批次合并不同：GWW 按 `(chat_id, sender_id)` 开窗，并用 `gww_token` 绑定同一窗口批次。窗口内被图片/At/缓存过滤处理后若内容严格为空字符串，则不会缓存、不会计数，但会刷新窗口 deadline；只剩空白符号则会保留。普通回复生成上下文、AI 回复后的 `[追加消息上下文]` 标记、Phase-2 转正与清理默认只处理当前发送者当前窗口令牌对应的窗口消息，不会串到同群其他用户或旧窗口。

当 Smart 批次吸收的多条消息各自带有 GWW 窗口令牌时，插件会为这些窗口建立运行时融合组。融合组不会改写原始 `gww_token`，也不会影响未参与本批次的普通窗口；它只让本批次的窗口上下文读取、DecisionAI/ReplyAI 视图、窗口回落、Phase-2 保存与清理按同一个窗口集合统一执行。融合后的窗口消息按原始时间戳排序，不重新套用等待窗口的额外消息数量限制。

### 批次合并的双重上限

数量上限和时间上限**同时启动、各自独立、谁先触发即停止**：

| 上限类型 | 触发机制 | 默认值 | 说明 |
|----------|----------|--------|------|
| 数量上限 | `claim_batch` 吸收循环中计数达到即停 | 20 条（`smart_concurrent_max_batch_size`） | 剩余消息留在待合并池由下一批次处理 |
| 时间上限 | `_cleanup_expired_locked` 清理超过时限的待合并消息 | 30 秒（`smart_concurrent_merge_wait`） | 超时消息转为独立处理 |
| 强制消息边界 | `is_forced=True`（@消息/关键词触发）的吸收循环中 break | — | 关键词触发消息作为批次边界；@AI 消息可按配置作为 follower 被吸收，吸收后会阻止独立默认 LLM 二次处理 |

`claim_batch` 是一次性快照，不会持续等待收集更多消息。非强制消息在首次快照前有一个可配置的收拢延迟（`smart_concurrent_claim_delay`，默认 0.3 秒），用于给几乎同时到达的消息挂载 payload 的机会，减少"晚到 50ms 就被分到下一批"的情况。调用那一刻能吸收多少就吸收多少（受上限约束），收不完的留在待合并池给下一轮。

### 被吸收消息的三种处理路径

| 路径 | 场景 | 行为 |
|------|------|------|
| 决策前被吸收 | 消息在 Phase 7 前被 anchor 吸收 | 返回，内容通过 anchor 的 `_smart_batch_snapshots` 保留；anchor 回复后一并保存至存储 |
| DecisionAI 判定不回复 | anchor 的 AI 判定不回复 | 被吸收的消息剥除特殊标记，转为普通消息缓存（与未通过概率筛选的消息一致），等待后续转正 |
| 决策后被吸收 | anchor 已通过 DecisionAI 但被更新的 anchor 吸收 | anchor 自身 + 其吸收的 followers 均转为普通消息缓存，等待后续转正 |

被吸收的消息不会丢失——无论在哪种路径下，消息内容都会被保留（通过 anchor 的批次保存或普通消息缓存）。

被吸收消息会保留各自的 `cached_data`，包括正文、图片/媒体解析、@ 提及结构、@全体标记、戳一戳事件文本、发送者与环境元数据。若 follower 是平台侧空正文的真实戳一戳组件，保存时会使用 `[ComponentType.Poke]` 作为内容占位，同时保留 `[戳一戳事件]` 元数据，避免因正文为空被跳过。

### 与现有机制的关系

| 机制 | 是否冲突 | 说明 |
|------|---------|------|
| 空消息过滤（Phase 0） | 不冲突 | 真空消息在入口处直接丢弃，不注册 arrival、不参与合并 |
| 群聊等待窗口（GWW） | 协同增强 | Smart 在群聊入口提前登记到达顺序，并在 Phase 5 后挂载 payload / claim；GWW 在 Phase 6 拦截窗口消息。被 GWW 拦截的消息独立缓存，不会进入 Smart claim_batch。Smart 自身的 follower 使用 `_smart_batch_snapshots` 保存，不依赖 GWW 开关，也不会污染窗口缓存；追加消息展示区只是复用同一种上下文格式。Smart 模式 + GWW 同时开启时，若同一 Smart 批次涉及多个窗口，会通过融合组统一读取这些窗口缓冲消息；后续窗口回落、Phase-2 保存与清理也按同一融合组处理。普通未融合窗口仍按 `sender_id + gww_token` 精确隔离 |
| legacy 并发锁 | 不冲突/兜底 | Smart 模式下，被吸收的消息检测到 consumed 后直接返回；未被吸收的消息进入传统并发保护循环等待 |
| 多用户消息 | 天然支持 | 合并区域格式含发送者名字和 ID，AI 可区分多人消息 |
| 历史记录 | 完整保存 | 合并的消息在 anchor 的 `after_message_sent` 中经 smart_batch_messages 转为普通格式（含元数据），正常保存至历史 |

### 相关配置

| 配置项 | 作用 |
|--------|------|
| `concurrent_mode` | `legacy`（默认，向后兼容）或 `smart`（智能合并模式） |
| `smart_concurrent_merge_wait` | 合并超时时间（秒），超时后未被合并的消息作为独立消息处理（默认 30 秒） |
| `smart_concurrent_max_batch_size` | 单批次最多吸收的消息数（默认 20，建议 1-50） |
| `smart_concurrent_claim_delay` | 快照前收拢延迟（秒），给几乎同时到达的消息挂载 payload 的机会（默认 0.3，建议 0.1-0.5） |
| `concurrent_wait_max_loops` | 通用并发等待的最大检测轮数（legacy 和 Smart 均复用） |
| `concurrent_wait_interval` | 通用并发等待的每轮检测间隔（秒） |

### 7.5 Smart 并发批次提示（可选增强）

当 `concurrent_mode=smart` 且 `enable_smart_batch_reply_hint=true` 时：
- Smart 模式不仅会把当前消息后紧接着到达的追加消息一起注入上下文；
- 决策阶段（读空气AI）动态追加 `[系统提示-Smart并发决策]`，告知 AI：当前消息是判断主对象，追加消息仅作背景参考，不要替追加消息做决定；
- 回复阶段（回复AI）动态追加 `[系统提示-Smart并发]`，告知 AI：当前触发对象仍是主要回复对象，追加消息可选择性顺带回应或大方忽略；
- 这些提示由 `MessageCleaner` 在保存前自动过滤（正则匹配 `[系统提示-Smart并发]` 整块），不会进入普通历史正文。

---

## Phase 7.5 · Smart 并发合并

当 `concurrent_mode=smart` 时，插件会在普通消息主线上尝试按真实到达顺序合并批次，让读空气AI和回复AI一起感知当前消息后紧接着到达的追加消息，以减少顺序颠倒和逐条重复回复。Smart 批次中的 follower 先进入专用快照，不进入普通缓存池或 GWW 窗口缓存池；只有需要回退时才会显式转为普通缓存。Smart 模式与 GWW 同时开启时，如果同一 Smart 批次涉及多个等待窗口，插件会为这些窗口建立融合组；AI 上下文构建、窗口回落、Phase-2 保存与清理都会按该融合组统一处理。

⚠️ 这里的 Smart 逻辑主要作用于”普通消息批次合并”、”Smart+GWW 窗口融合”以及”决策/回复双阶段批次提示增强”，不直接改变主动对话流程本身。

⚠️ 如果某个会话此时正被主动对话流程占用，普通链路在缓存转正/保存前的等待检测，当前仍然复用通用的 `concurrent_wait_max_loops` 与 `concurrent_wait_interval` 轮询参数，而不会切换成 Smart 专属等待策略。

⚠️ 选择 `concurrent_mode=smart`，也不代表传统并发保护会完全失效；更准确地说，是普通对话链路会优先尝试 Smart 批处理，但底层传统并发等待与兜底保护仍然存在，用于处理主动对话占用、等待超时、以及 Smart 未覆盖的异常路径。


AI 决定要回复后，进入回复生成阶段。

### 8.1 上下文构建

| 配置项 | 作用 |
|--------|------|
| `max_context_messages` | 历史消息最大条数（-1=配置层不额外限制，但仍受系统保护硬上限500条约束） |
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

1. 先用**短消息**（或空消息占位符）和**全平台工具集**触发 `event.request_llm(tool_set=...)`  
2. 让其他插件与平台 Hook 先运行（如 maid_agent 可重写 `req.func_tool` 管控工具）  
3. 最后在 `on_llm_request` 中恢复：
   - `req.prompt = 插件完整 full prompt`，并在安全判定通过时吸收第三方通过 `req.prompt` 追加的长期提示文本到一个固定兼容补充区
   - `req.contexts = 插件既有 contexts 策略值`，并在安全判定通过时保留第三方注入的长期记忆型 / 伪工具调用型上下文
   - `req.system_prompt = 插件人格 + 其他插件附加内容（正常路径下会尽量去掉已知平台 LTM 重复注入）`
   - `req.extra_user_content_parts`、`image_urls`、`audio_urls`、`video_paths`、`file_infos` 会合并其他插件的安全增量；只有高置信度识别为平台 GCC 重复群聊历史的 extra part 会被移除。其中 `video_paths` / `file_infos` 通过 `event extras`（`_plugin_media_video_paths` / `_plugin_media_file_infos`）传递，合并后写回供后续钩子和第三方插件读取
   - `req.func_tool` 由 `reply_handler` 提前注入全平台工具集，`on_llm_request` 钩子**只读不写**，由其他插件（如 maid_agent）自由管控实际可用工具。工具提醒基于最终的 `req.func_tool` 生成，确保提醒内容与 AI 实际可调用工具一致

当前版本对恢复阶段做了**兼容增强**：
- `system_prompt` 继续优先沿用旧版精确字符串命中路径
- 若平台对 persona 包装或换行做了轻微调整，则尝试轻量兼容识别
- 若第三方插件把长期说明、记忆文本或伪工具调用注入到了 `req.prompt` / `req.contexts`，插件会尝试按“短消息基线 + 结构特征”吸收这些**安全增量**，让 AI 继续可见
- 吸收后的 prompt/context/extra 补充内容会进入固定的运行时兼容补充区，并为不同片段加上明显边界，避免不同插件提示词混在一起
- 若仍无法高置信度识别，则进入**保守回退模式**：优先保留当前 `req.system_prompt`，并输出 warning 日志，但**不会中断回复流程**

🆕 V1.2.3.hotfix.1：Hook 恢复完成后，会追加 `PLUGIN_CUSTOM_STATIC_INSTRUCTIONS` 中存储的静态系统指令到 `req.system_prompt` 末尾，提高 AI 服务商整块缓存命中率。`req.prompt` 中原静态指令已移除重复副本，改为一行兜底指引 `[请严格遵循 system prompt 中的指令进行回复]`，确保钩子失败时 AI 仍能正常响应。

因此：
- 成功路径下，效果与旧版尽量保持一致
- 失败路径下，最差退化为“可能重复但仍可回复”，不会因为提示词识别失败导致整条消息链崩掉；对于不确定是否属于平台重复上下文的第三方注入，默认保留而不是误删


| 配置项 | 作用 |
|--------|------|
| `enable_tools_reminder` | 是否启用工具提醒文本。开启后，在 `on_llm_request` 阶段基于**当前会话最终可见工具集**生成工具提示并追加到 `system_prompt` 末尾；关闭后不注入任何工具提醒文本，但不影响 AI 实际调用工具 |
| `tools_reminder_persona_filter` | 是否在提醒层按人格过滤工具。仅在 `enable_tools_reminder=true` 时生效：开启后，先取当前会话可见工具，再按人格工具名单过滤后展示；关闭则展示当前会话全部可见工具 |

> **重要说明**：工具提醒已经改为“当前会话优先”的后置生成模式，不再在群聊主流程前半段直接把全局工具列表拼进 `final_message`。因此工具提醒能自动跟随当前会话的插件集、runtime、搜索开关、MCP 工具与其他插件工具变化。

> **skills_like 兼容说明**：当 AstrBot 当前会话采用 `provider_settings.tool_schema_mode=skills_like` 时，工具提醒会自动降级为“只展示工具名称与功能描述”，不再额外展开参数列表；这样可以避免把参数级信息提前写回 prompt，尽量不干扰框架原本的两阶段 schema 暴露与 re-query 流程。若是 `full` 模式或旧版 AstrBot 未提供该字段，则继续保持完整工具说明。 

> **Hook 恢复说明**：回复生成链路会先以短消息（或空消息占位符）调用 `event.request_llm()`，再在 `on_llm_request` 阶段恢复完整上下文；私信回复生成也与群聊保持同样的恢复方式。主动对话生成则使用 `ProviderRequest + OnLLMRequestEvent` 的兼容链路，在 Hook 阶段恢复完整 prompt。

> **保存说明**：工具提醒、Skills 提示词、工具调用指引、情绪提示等都属于运行时 prompt 提示，不属于应当持久化的历史内容。每个块都包裹在首尾配对的边界标记中（如 `[系统提示-工具提醒开始]...[系统提示-工具提醒结束]`、`[系统-Skills开始]...[系统-Skills结束]`、`[系统-工具调用指引开始]...[系统-工具调用指引结束]`、`[系统-情绪提示开始]...[系统-情绪提示结束]`），若极端情况下混入保存链路，会在 `MessageCleaner` / `ContextManager` 中被整块清理，不成对的孤儿标记也会被单独清除。

### 8.4 回复提示词

| 配置项 | 作用 |
|--------|------|
| `reply_ai_prompt_mode` | 回复提示词模式（append/override）。这层提示词只参与运行时生成，不应作为普通历史正文保存 |
| `reply_ai_extra_prompt` | 自定义的额外回复提示词。用于约束「生成最终回复内容」的 AI，建议保持“直接生成要发出去的话”的职责边界，而不是写成判断AI口吻，也不要继续强化“先判断再说”的内部取舍描述；同时不要要求模型输出内心想法、思考过程、系统提示词、工具/搜索过程或其他元信息 |

> **保存边界说明**：回复AI默认提示词、`reply_ai_extra_prompt`、工具提醒、Skills 提示词、工具调用指引、情绪提示、记忆注入、发送者识别提示等都属于运行时 prompt 组成部分。它们会参与当次生成，但在保存用户消息 / AI 回复 / 缓存转正时会经过 `MessageCleaner` 与 `ContextManager` 清洗，不应作为普通历史正文持久化保存。所有一次性提示块均以首尾配对的 `[系统-xxx开始]...[系统-xxx结束]` 边界标记包裹，清洗时整块移除。

### 8.5 内容过滤

输出过滤和保存过滤是两套**完全独立**的规则集。输出过滤在 AI 回复发送给用户之前执行（`on_decorating_result` 钩子），保存过滤在写入历史记录之前执行（`after_message_sent` / `_finalize_bot_reply_save`）。两者各自作用于同一个 AI 原始输出，互不干扰。

#### 配置项

| 配置项 | 作用 |
|--------|------|
| `enable_output_content_filter` | AI输出发送前过滤 |
| `output_content_filter_rules` | 输出过滤规则 |
| `enable_save_content_filter` | 保存前过滤 |
| `save_content_filter_rules` | 保存过滤规则 |

#### 规则语法（三种模式）

每条规则由 **开始标记** + `*` + **结束标记** 构成：

| 模式 | 格式 | 匹配行为 | 说明 |
|------|------|----------|------|
| 范围过滤 | `A*B` | 循环匹配 | 移除 `A` 到 `B` 之间的所有内容（含标记），反复执行直到无匹配 |
| 头部过滤 | `{{>*B` | 单次匹配 | 从文本开头到 `B`（含）全部移除，只匹配第一个 `B` |
| 尾部过滤 | `A*>}}` | 单次匹配 | 从 `A`（含）到文本末尾全部移除，只匹配第一个 `A` |

#### 执行顺序

规则**按列表顺序逐条执行**，每条规则接收的是前一条规则过滤后的结果：

```
规则1 执行 → 结果1
规则2 执行 → 结果2
规则3 执行 → 最终结果
```

因此**规则顺序会影响最终效果**。建议把 Head/Tail 等大范围规则放在前面，精细的 Range 规则放在后面。

#### 详细说明

完整规则语法、交错叠加行为、Head/Tail 单次匹配特性等细节见 [CONFIG_REFERENCE.md § 内容过滤](CONFIG_REFERENCE.md#内容过滤)。

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

### 8.7 多轮工具调用交叉保存与异常终止处理

当 AI 在一次回复中调用多个工具或发生多轮工具调用（Agent Loop）时，插件通过三个钩子协同工作，按实际执行顺序将 AI 中间推理文本与工具调用记录交错保存到对话历史。每个工具调用独立生成一个 `[工具调用记录开始]...[工具调用记录结束]` 块。

**工具调用记录保存长度配置**：
- `tool_call_max_args_length`（默认5000字符）：控制单个工具调用参数的保存长度
- `tool_call_max_result_length`（默认10000字符）：控制单个工具调用结果的保存长度
- 支持三种模式：完全省略（0，使用占位符）、自定义截断（正数，超出部分截断并添加"..."）、完全不限制（-1，真正无上限）
- 这两个配置针对每个独立的工具调用，而非所有工具调用的总和

（完整的工具调用原始数据由平台 `_save_to_history` 保存到 conversation 存储，此处为摘要格式供 AI 参考历史上下文使用）

#### 正常流程

```
Agent Loop 开始
  ↓
LLM 生成中间文本 → on_decorating_result() 累积到 _pending_bot_replies
  ↓
LLM 调用工具 → 框架执行工具 → 工具结果返回
  ↓
LLM 继续生成 → on_decorating_result() 继续累积
  ↓
...（可能多轮）
  ↓
Agent 完成 → on_agent_done → on_llm_response() 设置 _agent_done_flags
  ↓
after_message_sent() 检测到 agent_done → 弹出 _pending_bot_replies
  → _build_interleaved_tool_reply() 按执行时序交错排列文本与工具记录
  → 每个工具独立生成 [工具调用记录开始]...[工具调用记录结束] 块
  → 保存到 ContextManager（自定义存储 + 官方存储）
```

保存格式示例（同一轮调用两个工具）：
```
让我先查一下记忆和群成员信息
[工具调用记录开始]
- get_memories({"max_count": 10}) → 💭 相关记忆：（根据 tool_call_max_result_length 配置截断）
[工具调用记录结束]
[工具调用记录开始]
- get_group_members_info({}) → {"group_id":...（根据 tool_call_max_result_length 配置截断）
[工具调用记录结束]
印象最深的就是用户了...
```

#### 异常终止处理

当工具调用出错导致 LLM 后续响应异常（如 provider 返回 `role="err"`）时，AstrBot 核心框架**不会触发 `on_agent_done`**，导致 `_agent_done_flags` 永远不会被设置。插件在 `after_message_sent` 中增加了异常检测，确保累积的文本和工具调用记录不会丢失：

1. **AI 错误标记（`_ai_error_message_ids`）** — 插件在 LLM 请求阶段检测到的 AI 调用错误，已标记的消息 ID
2. **非 LLM 终端响应附带待保存文本** — GENERAL_RESULT 类型（如 err/aborted 响应）但有文本内容且有累积文本待保存

> **为什么有意跳过 LLM_RESULT？** 多轮工具调用中，AI 在调用工具前说的中间话（如"让我搜索一下"）与最终回复的类型完全相同，都是 LLM_RESULT。如果在此处对 LLM_RESULT 强制完成，会把第一段中间话当成最终回复保存，导致后续工具调用和 AI 回复全部丢失。正常完成流程由 `on_llm_response` → `_agent_done_flags` → `after_message_sent` 处理，无需强制完成。

任一条件命中时，`after_message_sent` 强制设置 `_agent_done_flags` 并继续走完整的保存链路——弹出 `_pending_bot_replies` 中的累积文本、调用 `_build_interleaved_tool_reply()` 构建交错工具调用记录、通过 `ContextManager.save_bot_message()` 写入双轨存储。

> **注意：** 异常终止响应的内容类型为 GENERAL_RESULT（不是 LLM_RESULT），因此 `on_decorating_result()` 不会对其触发（该钩子仅处理 LLM_RESULT）。异常终止前的中间文本（已在之前几轮 `on_decorating_result` 中累积）和所有已完成的工具调用记录仍会被正确保存。

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
- 若是收到 poke 后反戳成功，会先后保存两条历史事件：先以 user 视角保存发起者的戳一戳事件，再以 assistant 视角保存 AI 反戳动作，均写入官方存储与自定义存储并绑定当前会话
- 所有戳一戳历史事件与 AI 正文回复分开保存，不拼接成同一条消息

### 9.3 重复检测

| 配置项 | 作用 |
|--------|------|
| `enable_duplicate_filter` | 检测并过滤重复回复 |
| `duplicate_filter_check_count` | 检查最近N条回复 |
| `enable_duplicate_time_limit` | 重复检测时间限制 |
| `duplicate_filter_time_limit` | 时间限制（秒） |

### 9.4 存储保存

消息保存采用两阶段机制，同时写入三套存储系统（自定义 JSON、`platform_message_history` 表、`conversations` 表）：

| 阶段 | 保存内容 | 说明 |
|------|----------|------|
| **Phase-1** | 普通缓存消息 + 当前用户消息 + AI回复 | 主体保存。缓存消息会同步写入 `platform_message_history` 表（Web Chat UI 可见）。AI回复若存在当前发送者当前窗口令牌对应的窗口缓冲消息，会自动追加 `[追加消息上下文]` 标记 |
| **Phase-1（空回复降级）** | 普通缓存消息 + 当前用户消息 | 当本次普通群聊回复最终为空文本时触发：不保存 AI 回复，但仍完成缓存消息的上下文补保存（含 `platform_message_history`），避免历史断层 |
| **Phase-1（工具调用异常终止）** | 累积的中间文本 + 工具调用交错记录 + 当前用户消息 + 缓存消息 | 当 Agent 异常终止且 `on_agent_done` 未被调用时触发：通过异常检测强制弹出 `_pending_bot_replies` 中的累积文本，构建交错工具调用记录，照常保存到双轨存储（自定义 + 官方），确保错误链路中也不会漏存 |
| **Phase-2** | 窗口缓冲消息 | 仅在等待窗口收集了追加消息时执行，普通窗口按 `sender_id + gww_token` 精确转正；Smart+GWW 融合组按 `gww_merge_group_id` 一次性转正该组内窗口消息，同样写入 `platform_message_history`，保存在AI回复之后 |
| **冷群转正** | `flush_cached_messages_by_params` 将普通缓存消息与窗口缓冲消息按时间戳合并后同步写入三套存储 | 冷群静默超过 `idle_cache_flush_delay_seconds` 后触发。窗口缓冲消息也一并转正，避免因等不到 Phase-2 而被 TTL 清理后丢失 |
| **窗口回落** | `convert_window_buffered_to_regular` 将当前窗口批次的 `window_buffered=True` 消息转为普通缓存（移除标记） | 当读空气AI判定不回复，或普通链路因主动对话/冷群转正 owner 占用等待超时而回退缓存时自动触发。普通窗口通过 `gww_token` 精确绑定当前窗口批次；Smart+GWW 融合组通过 `gww_merge_group_id` 转换该组内所有窗口消息。转换后消息等同于普通缓存：参与 Phase-1 转正、冷群转正、按时间戳正常排序，彻底避免旧窗口消息在下次回复时被 Phase-2 误拼为"追加消息"，确保上下文顺序始终正确 |

> **时序说明**：Phase-2 的窗口缓冲消息在历史中排在AI回复之后，但AI回复时已通过上下文拼接看到了这些消息。`[追加消息上下文]` 标记帮助后续AI理解这一时序差异。

> **去重说明**：缓存转正写入 `platform_message_history` 时会基于缓存消息自身的稳定 `message_id` 生成 `llm_checkpoint_id`。普通回复、Phase-2 窗口缓冲、主动对话成功转正和冷群转正这些路径如果因并发/重试碰到同一条缓存消息，会优先按 checkpoint 跳过重复写入；若平台接口不支持该字段，则自动退回普通写入，不影响旧平台继续运行。

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
并发占用检查（普通链路/等待窗口/owner）
    ↓（空闲；若等待后释放，会重新跑触发判断）
主动对话预判断AI判断时机是否合适（enable_proactive_ai_judge）
    ↓（合适）
生成并发送主动消息
    ↓
更新互动评分（自适应系统）
```

主动对话没有当前用户 event，因此会优先使用群聊入口最近记录的 `chat_key → platform_id` 映射来恢复真实平台实例；官方会话读写使用 `platform_id:GroupMessage:chat_id`，自定义备用存储仍使用平台类型名路径。发送时先尝试恢复出的首选 `platform_id`；如果平台实例或适配器状态导致发送失败，会先尝试同平台类型的其他实例，再尝试其他可用平台实例，成功后用实际成功的 `used_platform` 保存历史，所有平台都失败则跳过保存，避免出现“没发出去但历史已保存”的假主动对话。它会读取已经保存到官方会话/自定义存储的历史和尚未转正的普通缓存消息。窗口缓冲消息（`window_buffered=True`）属于普通回复流程的实时批次上下文：读空气 AI 和普通回复 AI 会看到它们，但主动对话生成流程不会读取这类尚未转正的窗口缓冲消息；正式保存仍由普通回复 Phase-2 或冷群转正处理。并发判断上，只有已通过概率/强制触发并进入普通候选链路的消息、正在处理的普通消息、活跃等待窗口或已有会话 owner 才会挡住主动对话；单纯刚收到但未通过概率筛选的普通消息不会让主动对话长期饥饿。若主动对话等待普通链路释放，释放后会重新执行一次完整触发判断；判断不通过则跳过本轮，等待下一个 `proactive_check_interval` 周期重新读取上下文和预判断，不会在普通回复刚结束后无条件补发主动消息。

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
| `proactive_ai_judge_timeout` | 主动对话预判断超时。预判断AI与读空气AI、频率判断AI共用 `decision_ai_fallback_provider_ids` 备用列表 |
| `proactive_gen_fallback_provider_ids` | 🔁 主动对话生成备用提供商列表，留空=不启用。生成AI直连平台默认回复AI且超时由平台管理；报错/空响应时切换备用 |
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
