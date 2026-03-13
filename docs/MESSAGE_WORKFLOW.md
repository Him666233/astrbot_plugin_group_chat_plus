# 消息工作流程详解

> 本文档完整描述了群聊增强插件从**收到消息**到**发出回复**的完整处理流程，以及每个环节涉及的配置项。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考](CONFIG_REFERENCE.md) | [项目结构](PROJECT_STRUCTURE.md)

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
Phase 8 · AI 回复生成
    ↓
Phase 9 · 回复后处理（概率提升/打字延迟/错别字等）
```

---

## Phase 1 · 基础验证

消息到达 `on_group_message()` 后，首先进行一系列前置检查，任何一项不通过则**直接丢弃消息**。

| 检查项 | 说明 | 相关配置 |
|--------|------|----------|
| 群聊总开关 | 插件是否启用 | `enable_group_chat` |
| 群组白名单 | 是否在允许的群列表中（空=全部允许） | `enabled_groups` |
| 消息去重 | 是否是重复收到的同一条消息 | — （内部机制） |
| 私聊过滤 | 群聊处理器不处理私聊消息 | — |
| 指令过滤 | 以 `/`、`!`、`#` 等开头的指令消息被跳过 | `enable_command_filter`、`command_prefixes`、`enable_full_command_detection`、`full_command_list`、`enable_command_prefix_match`、`command_prefix_match_list` |

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

将QQ合并转发消息解析为可读文本，让AI能理解转发内容。

| 配置项 | 作用 |
|--------|------|
| `enable_forward_message_parsing` | 是否解析合并转发消息 |
| `forward_max_nesting_depth` | 嵌套转发的最大解析深度（0-10） |

### 2.3 @全体成员过滤

| 配置项 | 作用 |
|--------|------|
| `enable_ignore_at_all` | 忽略@全体成员消息，避免群公告触发AI |

---

## Phase 3 · 触发检测

检测消息中的特殊触发条件。**被触发的消息将跳过 Phase 4 的概率筛选**，直接进入后续阶段。

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

分析群聊消息节奏，动态调整回复频率。

| 配置项 | 作用 |
|--------|------|
| `enable_frequency_adjuster` | 启用频率分析 |
| `frequency_check_interval` | 分析间隔（秒） |
| `frequency_analysis_message_count` | 分析的消息数量 |
| `frequency_decrease_factor` / `frequency_increase_factor` | 降低/提升系数 |
| `frequency_min_probability` / `frequency_max_probability` | 调整后的概率范围 |

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
| `pending_cache_ttl_seconds` | 缓存消息的过期时间 |

---

## Phase 5 · 消息内容处理

通过概率筛选的消息进入内容处理阶段，提取和转换消息中的各种内容。

### 5.1 @他人过滤

| 配置项 | 作用 |
|--------|------|
| `enable_ignore_at_others` | 忽略@其他用户的消息 |
| `ignore_at_others_mode` | `strict`（严格过滤）或 `allow_with_bot`（同时@了机器人则允许） |

### 5.2 图片处理

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

### 5.3 消息元数据注入

| 配置项 | 作用 |
|--------|------|
| `include_timestamp` | 为消息添加时间戳 `[YYYY-MM-DD 周x HH:MM:SS]` |
| `include_sender_info` | 为消息添加发送者信息 `[Name(ID:xxx)]` |

### 5.4 戳一戳处理

| 配置项 | 作用 |
|--------|------|
| `poke_message_mode` | 戳一戳响应模式：`ignore`（忽略）、`bot_only`（仅响应戳机器人）、`all`（响应所有） |
| `poke_bot_skip_probability` | 戳机器人时跳过概率检查 |
| `poke_enabled_groups` | 启用戳一戳的群（空=全部） |
| `enable_poke_trace_prompt` | 记录谁戳了机器人，并告知AI |
| `poke_trace_max_tracked_users` / `poke_trace_ttl_seconds` | 追踪用户数/追踪时长 |

### 5.5 缓存消息摘要

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
| `group_wait_window_merge_at_messages` | 是否合并等待窗口内的@消息 |
| `group_wait_window_merge_at_list_mode` | @合并模式（whitelist/blacklist） |
| `group_wait_window_merge_at_user_list` | @合并的用户列表 |

**智能中断**：如果等待窗口期间收到新的@消息，立即结束等待并处理。

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

构建提示词并调用 AI，让其判断是否应该回复。提示词中包含：

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
| `decision_ai_provider_id` | 决策AI的提供商ID（留空用默认） |
| `decision_ai_prompt_mode` | 提示词模式：`append`（追加到内置提示后）或 `override`（完全覆盖） |
| `decision_ai_extra_prompt` | 自定义的额外决策提示词 |
| `decision_ai_timeout` | 决策AI调用超时（秒） |

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

### 7.4 对话疲劳对决策的影响

| 配置项 | 作用 |
|--------|------|
| `enable_conversation_fatigue` | 启用对话疲劳 |
| `fatigue_threshold_light` / `medium` / `heavy` | 轻/中/重疲劳的消息数阈值 |
| `fatigue_probability_decrease_light` / `medium` / `heavy` | 对应的概率衰减量 |
| `fatigue_closing_probability` | 疲劳时发出结束语的概率 |

### 7.5 决策结果

- **YES（应该回复）** → 进入 Phase 8（回复生成）
- **NO（不应该回复）** → 消息被存入自定义存储（custom_storage），作为未来回复的历史上下文

---

## Phase 8 · AI 回复生成

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
| `memory_plugin_mode` | 模式：`auto`（自动检测）、`legacy`（传统模式，推荐）、`livingmemory`（智能模式） |
| `memory_insertion_timing` | 注入时机：`pre_decision`（决策前，影响是否回复）或 `post_decision`（决策后，只影响回复内容） |
| `livingmemory_version` | LivingMemory版本（v1/v2） |
| `livingmemory_top_k` | 记忆召回条数 |

### 8.3 工具提示

| 配置项 | 作用 |
|--------|------|
| `enable_tools_reminder` | 告知AI可用工具 |
| `tools_reminder_persona_filter` | 按人格过滤工具 |

### 8.4 回复提示词

| 配置项 | 作用 |
|--------|------|
| `reply_ai_prompt_mode` | 回复提示词模式（append/override） |
| `reply_ai_extra_prompt` | 自定义的额外回复提示词 |

### 8.5 内容过滤

| 配置项 | 作用 |
|--------|------|
| `enable_output_content_filter` | AI输出发送前过滤 |
| `output_content_filter_rules` | 输出过滤规则 |

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

### 9.3 重复检测

| 配置项 | 作用 |
|--------|------|
| `enable_duplicate_filter` | 检测并过滤重复回复 |
| `duplicate_filter_check_count` | 检查最近N条回复 |
| `enable_duplicate_time_limit` | 重复检测时间限制 |
| `duplicate_filter_time_limit` | 时间限制（秒） |

### 9.4 存储保存

| 配置项 | 作用 |
|--------|------|
| `enable_save_content_filter` | 保存前过滤 |
| `save_content_filter_rules` | 保存过滤规则 |

### 9.5 状态更新

回复完成后自动更新以下系统状态：

- **概率提升**：`after_reply_probability` 生效，持续 `probability_duration` 秒
- **注意力增强**：对当前用户的注意力提升
- **情绪更新**：根据对话内容更新情绪状态
- **疲劳累加**：对话轮次计数增加
- **吐槽系统衰减**：成功回复减少被无视计数
- **主动对话状态**：更新互动评分
- **统计记录**：记录回复事件到统计系统

---

## 独立系统：主动对话

> 主动对话是一个**独立于消息处理流程**的系统，通过定时任务在群聊沉默一段时间后由 AI 主动发起话题。

### 流程

```
定时检查（每 proactive_check_interval 秒）
    ↓
群聊是否沉默超过 proactive_silence_threshold？
    ↓（是）
安静时段检查（23:00-07:00默认不触发）
    ↓（不在安静时段）
用户活跃度检查（需要有人在活跃）
    ↓（满足）
随机概率检查 (proactive_probability)
    ↓（通过）
AI判断时机是否合适（enable_proactive_ai_judge）
    ↓（合适）
生成并发送主动消息
    ↓
更新互动评分（自适应系统）
```

### 相关配置

| 配置项 | 作用 |
|--------|------|
| `enable_proactive_chat` | 启用主动对话 |
| `proactive_silence_threshold` | 沉默多久后触发（秒） |
| `proactive_probability` | 触发概率 |
| `proactive_check_interval` | 检查间隔（秒） |
| `proactive_require_user_activity` | 要求有用户活跃 |
| `proactive_min_user_messages` | 最少用户消息数 |
| `proactive_user_activity_window` | 活跃时间窗口 |
| `proactive_max_consecutive_failures` | 连续失败次数上限 |
| `proactive_cooldown_duration` | 失败后冷却时间 |
| `proactive_enable_quiet_time` | 安静时段开关 |
| `proactive_quiet_start` / `proactive_quiet_end` | 安静时段起止 |
| `enable_proactive_ai_judge` | AI判断发言时机 |
| `proactive_ai_judge_timeout` | AI判断超时 |
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
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
        时段概率调整    频率调整器    消息质量预判
        (× factor)   (× factor)  (± boost)
              ↓             ↓             ↓
              └─────────────┼─────────────┘
                            ↓
                    after_reply_probability
                   (如果刚回复过，用此值替换)
                            ↓
                     表情衰减 (× decay)
                            ↓
                    拟人模式调整 (动态阈值)
                            ↓
                    硬限制截断 [min, max]
                            ↓
                      最终概率值
                            ↓
                 随机数 < 最终概率？
                    ↓            ↓
                  通过          未通过
                  (→ Phase 5)   (→ 缓存)
```

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考 →](CONFIG_REFERENCE.md) | [项目结构 →](PROJECT_STRUCTURE.md)
