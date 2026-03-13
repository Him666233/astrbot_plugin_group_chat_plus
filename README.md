# 群聊增强插件 (Chat Plus)

<div align="center">

[![Version](https://img.shields.io/badge/version-v1.2.1-blue.svg)](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.11.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)

一个以 **AI读空气** 为核心的群聊增强插件，让你的Bot更懂氛围、更自然地参与群聊互动

## ⚠️ 注意: AstrBot平台自带的说明文档查看器有一定的问题，可能会导致点击跳转按钮之后，没办法跳转到正常的说明文件中，建议直接在项目的github仓库中查看或者是直接下载压缩包，然后解压自行翻看

[快速开始](#-快速开始) • [功能总览](#-功能总览) • [推荐配置](#-v121-完整推荐配置保守版) • [更新日志](#-更新日志)

[深度指南与常见问题](docs/ARCHITECTURE.md) • [消息工作流程详解](docs/MESSAGE_WORKFLOW.md) • [配置项完整参考](docs/CONFIG_REFERENCE.md) • [项目结构说明](docs/PROJECT_STRUCTURE.md)

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

> **图片处理须知：** 目前必须配置 `image_to_text_provider_id`（图片转文字提供商ID）才能正常处理图片。留空直接传递图片给多模态AI的方式目前无法可靠工作。

## ⚠️ 私聊功能警告

> **私聊处理功能目前仍在开发中，请勿开启 `enable_private_chat`！** 当前版本的私聊模块尚未完善，开启可能导致异常行为。请耐心等待后续版本正式支持。

---

## 📚 文档导航

> 不知道从哪里看起？根据你的需求选择对应的文档：

| 你想了解… | 去看这个文档 |
|-----------|-------------|
| **AI 回复太多/太少/读空气不准怎么调？** | [深度指南 → 常见问题排查](docs/ARCHITECTURE.md#ai-回复频率相关问题) |
| **Web 管理面板怎么用？打不开怎么办？** | [深度指南 → Web 管理面板](docs/ARCHITECTURE.md#web-管理面板相关问题) |
| **插件的工作原理是什么？为什么要"偷天换日"？** | [深度指南 → 工作原理](docs/ARCHITECTURE.md#一句话概括) |
| **平台的"群聊上下文感知"和"自动理解图片"怎么配？** | [深度指南 → 平台配置](docs/ARCHITECTURE.md#推荐的平台设置) |
| **某个配置项是什么意思？默认值是多少？** | [配置项完整参考](docs/CONFIG_REFERENCE.md) |
| **一条消息从收到到回复经历了什么流程？** | [消息工作流程详解](docs/MESSAGE_WORKFLOW.md) |
| **代码文件结构和各模块职责？** | [项目结构说明](docs/PROJECT_STRUCTURE.md) |
| **我用的其他插件和本插件会冲突吗？** | [深度指南 → 兼容性](docs/ARCHITECTURE.md#与其他插件的兼容性) |
| **记忆插件怎么选？为什么推荐适配过的？** | [深度指南 → 记忆插件](docs/ARCHITECTURE.md#记忆插件的兼容性为什么要用适配过的记忆插件) |

---
## 🤝 插件合作

### AstrBot智能自学习插件

与 [astrbot_plugin_self_learning](https://github.com/NickCharlie/astrbot_plugin_self_learning) 建立官方合作关系：

- **本插件** 负责"智能决策何时回复" — AI读空气、动态概率、注意力机制
- **自学习插件** 负责"智能优化如何回复" — 对话风格学习、人格自动优化、好感度系统

两者功能互补，推荐组合使用。欢迎加入 **QQ群 1021544792** 交流！

---

## 🆕 v1.2.1 更新亮点

**本次更新带来了全新的 Web 管理面板，以及多项拟人化和智能化增强。**

### 全新 Web 管理面板

- **可视化配置管理** — 支持在 Web 界面直接修改插件配置，无需手动编辑 JSON
- **访问日志与统计** — 实时查看消息处理记录、回复统计图表、各群聊活跃度
- **IP 安全管理** — 白名单/黑名单/封禁管理，防爬虫自动封禁，IP 访问控制
- **JWT 认证保护** — Bearer Token + Cookie 双重认证，暴力破解分级锁定，会话安全

### 新增功能

| 功能 | 说明 |
|------|------|
| **回复密度限制** | 限制短时间内(默认5min)最多回复次数，防止刷屏，超限后AI可感知 |
| **消息质量预判** | 疑问句/话题消息加权，纯水聊消息降权，动态调整回复概率 |
| **欢迎消息解析** | 解析群成员入群欢迎消息，可选是否跳过概率筛选直接处理 |
| **主动对话AI判断** | 主动发言前额外用AI判断当前时机是否合适，减少尬聊 |
| **忽略@全体成员** | 独立开关过滤@all消息，避免群公告等无效触发 |
| **历史截止时间戳** | 执行插件清除指令后记录截止点，读取平台历史时自动过滤旧消息，解决 `/reset` 不清 platform_message_history 的问题 |
| **多工具调用兼容** | AI单次推理调用多个工具或多轮工具调用时，按实际执行顺序将文本与工具记录交错保存到历史 |

### 兼容性

- 完全向下兼容 v1.2.0 配置，升级无需修改任何配置
- 新功能默认使用安全合理的默认值

---

## 📖 功能总览

### 核心机制

- **AI读空气** — 两层过滤：概率筛选 + AI智能判断，精准控制回复时机
- **动态概率系统** — 回复后概率提升促进连续对话，时段概率模拟作息节奏
- **注意力机制** — 多用户同时追踪(0-1连续值)，指数衰减，情绪检测，注意力溢出
- **智能缓存** — "缓存+转正"机制，未回复消息保留上下文，下次回复时自动合并
- **记忆系统** — 支持 LivingMemory（混合检索+人格隔离）和 Legacy （稳定，推荐）双模式

### 社交行为

- **主动对话** — 沉默后AI自然发起话题，自适应互动评分系统，越聊越开心
- **对话疲劳** — 连续对话后逐渐降低回复倾向，模拟真人节奏
- **拟人增强** — 沉默状态机、兴趣话题检测、决策历史一致性
- **吐槽系统** — 连续被无视时AI会"吐槽"，让Bot更有性格

### 真实感增强

- **打字错误** — 基于拼音相似性的自然错别字 (默认2%概率)
- **情绪系统** — 根据对话检测情绪状态，影响回复语气
- **回复延迟** — 模拟打字速度，避免秒回
- **频率调整** — 自动分析群聊节奏，动态调整回复频率

### 消息处理

- **图片处理** — 支持图片转文字，可配置范围，结果自动缓存
- **转发解析** — QQ合并转发消息自动解析为可读文本
- **关键词系统** — 触发词跳过概率/智能模式，黑名单词直接过滤
- **戳一戳** — 智能响应QQ戳一戳，支持反戳和回复后戳
- **@消息优先** — @机器人消息跳过所有判断直接回复

### 安全与管理

- **指令过滤** — 自动跳过 `/help` 等指令消息
- **用户黑名单** — 屏蔽特定用户
- **@他人过滤** — 避免插入他人私密对话
- **重复拦截** — 防止AI发送重复内容
- **内容过滤** — 发送前/保存前过滤AI输出

---

## 🚀 快速开始

### 安装

1. 在 AstrBot 插件市场搜索安装，或下载本仓库放入 `/data/plugins` 目录
2. 安装依赖：`pip install pypinyin`
3. 重启 AstrBot，在插件管理面板中配置

> **使用打包启动器部署的用户请注意**：若启动后报错 `ModuleNotFoundError: No module named 'aiohttp'`，请额外执行 `pip install aiohttp>=3.8.0`（详见下方依赖说明）。

### 依赖要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| AstrBot | >= v4.11.0 | 平台框架 |
| `pypinyin` | >= 0.44.0 | 打字错误生成器（拼音相似性），**需手动安装** |
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

## 🎯 v1.2.1 完整推荐配置（保守版）

以下是 v1.2.1 全功能推荐配置，偏保守方向调整，AI不会过于频繁发言但也不会完全沉默，适合大多数群聊场景。

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
  "reply_ai_prompt_mode": "append",
  "reply_ai_extra_prompt": "",

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
  "memory_plugin_mode": "legacy",
  "livingmemory_version": "v1",
  "livingmemory_top_k": 5,
  "memory_insertion_timing": "pre_decision",

  "enable_tools_reminder": false,
  "tools_reminder_persona_filter": false,

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
  "attention_decrease_on_no_reply_step": 0.15,
  "attention_decrease_threshold": 0.3,
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
  "cooldown_max_duration": 600,
  "cooldown_trigger_threshold": 0.3,
  "cooldown_attention_decrease": 0.2,

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
  "group_wait_window_merge_at_messages": true,
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
> - `memory_plugin_mode` 设为 `"auto"` 会自动检测已安装的记忆插件（优先 LivingMemory）
> - `reply_time_periods` 和 `proactive_time_periods` 的值为 JSON 字符串格式
> - `enable_private_chat` **必须保持 false**，私聊功能尚未完善
> - 本推荐配置偏保守，AI发言频率较低，如需更活跃可适当提高 `initial_probability` 和 `after_reply_probability`
> - 其他所有配置项的详细说明均可在 AstrBot 插件配置面板中直接查看

---


### 记忆插件支持

| 插件 | 模式 | 特性 |
|------|------|------|
| [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) | LivingMemory | 混合检索、智能总结、自动遗忘、会话隔离、人格隔离 |
| [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) | Legacy （推荐）| 传统记忆模式，兼容旧版 ，稳定性高|

---

## 📝 更新日志

### v1.2.1 (2026-03-13)

**新增 Web 管理面板 + 多项拟人化与智能化增强**

**🖥️ 全新 Web 管理面板**:
- **可视化配置编辑** — 在网页界面直接修改插件全部配置项，无需手动编辑 JSON
- **实时统计图表** — 查看消息处理量、回复率、各群聊活跃度趋势
- **访问日志** — 实时记录消息事件，支持按群/用户/时间筛选
- **IP 安全管理** — 白名单/黑名单/封禁管理，防爬虫自动检测与封禁，支持封禁持久化重启恢复
- **JWT 双重认证** — Bearer Token + Cookie，暴力破解分级锁定（5/10/15/20次 → 30/60/300/600秒），会话安全可靠
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
- 完全向下兼容 v1.2.0 配置，零成本升级
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
