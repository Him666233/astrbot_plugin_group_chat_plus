# 配置项完整参考

> 本文档列出了群聊增强插件的**所有配置项**，包含类型、默认值和详细说明。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程](MESSAGE_WORKFLOW.md) | [项目结构](PROJECT_STRUCTURE.md)

---

## 目录

- [基础设置](#基础设置)
- [Web 管理面板](#web-管理面板)
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
| `enable_debug_log` | bool | `false` | 开启后输出详细调试日志，用于排查问题 |

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
| `web_panel_reset_password` | bool | `false` | 设为 `true` 后重启，密码将重置为随机值并显示在日志中 |
| `web_panel_trust_proxy` | bool | `false` | 信任反向代理的 `X-Real-IP` / `X-Forwarded-For` 头。仅在使用 Nginx 等反代时开启 |
| `web_panel_ip_bind_check` | bool | `true` | JWT 绑定登录 IP，防止 Token 被窃取后在其他IP使用 |

### IP 访问控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_ip_mode` | string | `"disabled"` | IP 访问控制模式：`disabled`（不启用）、`whitelist`（白名单，仅允许列表内IP）、`blacklist`（黑名单，拒绝列表内IP） |
| `web_panel_ip_list` | list | `[]` | 白名单/黑名单 IP 地址列表 |
| `web_panel_protected_ips` | list | `[]` | 受保护IP列表，永远不会被封禁（配置文件专属，Web端只读） |

### 防爬虫

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_anti_spider` | bool | `false` | 启用防爬虫检测（UA 匹配 + 频率限制 + 扫描路径识别） |
| `web_panel_anti_spider_rate_limit` | int | `60` | 每分钟请求数阈值，超过则封禁 |
| `web_panel_anti_spider_ban_duration` | int | `300` | 自动封禁持续时间（秒） |

### 日志管理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_log_auto_clean` | bool | `false` | 自动清理过期访问日志 |
| `web_panel_log_retention_days` | int | `7` | 日志保留天数 |
| `web_panel_log_clean_interval_hours` | int | `24` | 清理检查间隔（小时） |

---

## 概率与决策系统

### 基础概率

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_probability` | float | `0.02` | 基础回复概率。每条消息有 2% 的概率通过第一层筛选。值越高，AI越活跃 |
| `after_reply_probability` | float | `0.8` | 回复后的提升概率。刚回复过后，概率临时提升到 80%，促进连续对话 |
| `probability_duration` | int | `120` | 回复后概率提升的持续时间（秒），超过后恢复到 `initial_probability` |

### 概率硬限制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_probability_hard_limit` | bool | `false` | 强制将最终概率限制在 [min, max] 范围内 |
| `probability_min_limit` | float | `0.05` | 概率下限，确保即使多重衰减也不会低于此值 |
| `probability_max_limit` | float | `0.8` | 概率上限，防止叠加后概率过高 |

### 决策AI配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `decision_ai_provider_id` | string | `""` | 执行"读空气"判断的AI提供商ID。留空使用 AstrBot 默认提供商。建议使用轻量快速的模型以节省延迟和费用 |
| `decision_ai_prompt_mode` | string | `"append"` | 决策提示词模式。`append`：在内置提示词后追加自定义内容；`override`：完全用自定义内容替换内置提示词 |
| `decision_ai_extra_prompt` | string | `""` | 自定义决策提示词。可用于微调 AI 的判断标准 |
| `decision_ai_timeout` | int | `30` | 决策AI调用超时（秒）。超时后视为"不回复" |

### 超时与并发

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `reply_timeout_warning_threshold` | int | `120` | 回复超过此时间（秒）发出警告日志 |
| `reply_generation_timeout_warning` | int | `60` | 回复生成超过此时间（秒）发出警告 |
| `concurrent_wait_max_loops` | int | `15` | 并发等待最大循环次数（防止死锁） |
| `concurrent_wait_interval` | float | `5.0` | 并发等待每次循环间隔（秒） |

---

## 消息格式与上下文

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `include_timestamp` | bool | `true` | 为每条消息添加时间戳，格式：`[2026-03-13 周四 14:30:00]`。帮助AI理解时间关系 |
| `include_sender_info` | bool | `true` | 为每条消息添加发送者信息，格式：`[用户名(ID:12345)]`。帮助AI区分不同发言人 |
| `max_context_messages` | int | `-1` | 传递给AI的最大历史消息条数。`-1` = 不限制（由模型上下文窗口决定） |

---

## 消息缓存

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `custom_storage_max_messages` | int | `500` | 自定义消息存储的最大条数。`0` = 禁用，`-1` = 不限制。用于保存完整的群聊上下文 |
| `pending_cache_max_count` | int | `10` | 待处理消息池的最大条数。未通过概率筛选的消息暂存于此，下次回复时作为上下文合并 |
| `pending_cache_ttl_seconds` | int | `1800` | 待处理消息的过期时间（秒），超过后自动清理 |

---

## 图片处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_image_processing` | bool | `false` | 启用图片处理功能，将图片转换为文字描述 |
| `image_to_text_scope` | string | `"mention_only"` | 图片处理范围：`all`（所有消息中的图片）、`mention_only`（@或关键词触发时）、`at_only`（仅@消息）、`keyword_only`（仅关键词触发时） |
| `image_to_text_provider_id` | string | `""` | 图片转文字的AI提供商ID。**必须填写**，留空将无法处理图片 |
| `image_to_text_prompt` | string | `"请详细描述这张图片的内容"` | 发送给图片AI的提示语 |
| `image_to_text_timeout` | int | `60` | 图片处理API调用超时（秒） |
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
| `enable_ignore_at_others` | bool | `false` | 忽略@其他用户的消息，避免插入他人的对话 |
| `ignore_at_others_mode` | string | `"strict"` | 过滤模式：`strict`（只要@了非机器人的用户就过滤）、`allow_with_bot`（同时@了机器人则不过滤） |
| `enable_ignore_at_all` | bool | `false` | 忽略@全体成员消息，避免群公告触发AI |

---

## 戳一戳系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poke_message_mode` | string | `"bot_only"` | 戳一戳响应模式：`ignore`（完全忽略）、`bot_only`（仅响应戳机器人）、`all`（响应所有戳一戳） |
| `poke_bot_skip_probability` | bool | `true` | 戳机器人时跳过概率检查，直接进入AI决策 |
| `poke_bot_probability_boost_reference` | float | `0.3` | 戳一戳概率提升参考值 |
| `poke_reverse_on_poke_probability` | float | `0.0` | 被戳后立即反戳的概率（0 = 不反戳） |
| `enable_poke_after_reply` | bool | `false` | 回复消息后戳用户一下 |
| `poke_after_reply_probability` | float | `0.1` | 回复后戳用户的概率 |
| `poke_after_reply_delay` | float | `0.5` | 回复后到戳之间的延迟（秒） |
| `enable_poke_trace_prompt` | bool | `false` | 追踪谁戳了机器人，并在提示词中告知AI |
| `poke_trace_max_tracked_users` | int | `5` | 最大追踪用户数 |
| `poke_trace_ttl_seconds` | int | `300` | 追踪记录保留时间（秒） |
| `poke_enabled_groups` | list | `[]` | 启用戳一戳功能的群列表（空=所有群） |

---

## 转发消息解析

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_forward_message_parsing` | bool | `false` | 解析QQ合并转发消息，将多条转发内容转换为可读文本 |
| `forward_max_nesting_depth` | int | `3` | 嵌套转发的最大解析深度（0=不解析嵌套，最大10） |

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
| `group_wait_window_merge_at_messages` | bool | `false` | 是否在窗口内合并@消息 |
| `group_wait_window_merge_at_list_mode` | string | `"whitelist"` | @消息合并的用户过滤模式 |
| `group_wait_window_merge_at_user_list` | list | `[]` | @消息合并的用户ID列表 |

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
| `enable_attention_mechanism` | bool | `false` | 启用多用户注意力追踪。每个用户有 0-1 之间的连续注意力值 |
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
| `attention_decrease_on_no_reply_step` | float | `0.15` | 未回复时注意力降低步长 |
| `attention_decrease_threshold` | float | `0.3` | 低于此值视为低注意力 |

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
| `enable_attention_cooldown` | bool | `true` | 注意力达到高值后触发冷却期 |
| `cooldown_max_duration` | int | `600` | 最大冷却持续时间（秒） |
| `cooldown_trigger_threshold` | float | `0.3` | 触发冷却的注意力阈值 |
| `cooldown_attention_decrease` | float | `0.2` | 冷却时注意力降低量 |

---

## 对话疲劳

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
| `enable_proactive_ai_judge` | bool | `true` | 主动发言前由AI判断当前是否适合说话 |
| `proactive_ai_judge_timeout` | int | `15` | AI判断超时（秒） |

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
| `frequency_check_interval` | int | `180` | 分析间隔（秒） |
| `frequency_analysis_timeout` | int | `20` | 分析超时 |
| `frequency_adjust_duration` | int | `360` | 调整效果持续时间 |
| `frequency_analysis_message_count` | int | `15` | 参与分析的消息数量 |
| `frequency_min_message_count` | int | `5` | 最少消息数才进行分析 |
| `frequency_decrease_factor` | float | `0.85` | 降低频率系数 |
| `frequency_increase_factor` | float | `1.1` | 提升频率系数 |
| `frequency_min_probability` | float | `0.03` | 调整后概率下限 |
| `frequency_max_probability` | float | `0.85` | 调整后概率上限 |

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
| `memory_plugin_mode` | string | `"legacy"` | 记忆模式：`auto`（自动检测已安装的记忆插件）、`legacy`（传统模式，推荐，稳定性高）、`livingmemory`（智能模式，混合检索+人格隔离） |
| `memory_insertion_timing` | string | `"post_decision"` | 记忆注入时机：`pre_decision`（决策前，记忆影响"是否回复"）、`post_decision`（决策后，记忆只影响"回复内容"） |
| `livingmemory_version` | string | `"v2"` | LivingMemory 版本（v1/v2），仅在 livingmemory 模式下有效 |
| `livingmemory_top_k` | int | `5` | 召回的记忆条数 |

---

## 工具提示

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_tools_reminder` | bool | `false` | 在回复提示词中告知AI当前可用的工具（如搜索、画图等） |
| `tools_reminder_persona_filter` | bool | `false` | 根据当前AI人格过滤工具列表 |

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
| `reply_ai_prompt_mode` | string | `"append"` | 回复提示词模式。`append`：追加到内置提示后；`override`：完全替换 |
| `reply_ai_extra_prompt` | string | `""` | 自定义回复提示词 |

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

私聊模块有独立的 30+ 个配置项（类似群聊的简化版），包含消息聚合、用户过滤、图片处理等功能。待正式发布后将补充完整文档。

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程 →](MESSAGE_WORKFLOW.md) | [项目结构 →](PROJECT_STRUCTURE.md)
