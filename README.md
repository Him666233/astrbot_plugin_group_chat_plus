# 群聊增强插件 (Chat Plus)

<div align="center">

[![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.11.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)

一个以 **AI读空气** 为核心的群聊增强插件，让你的Bot更懂氛围、更自然地参与群聊互动

[快速开始](#-快速开始) • [功能总览](#-功能总览) • [推荐配置](#-v120-完整推荐配置) • [更新日志](#-更新日志)

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
## 🤝 插件合作

### AstrBot智能自学习插件

与 [astrbot_plugin_self_learning](https://github.com/NickCharlie/astrbot_plugin_self_learning) 建立官方合作关系：

- **本插件** 负责"智能决策何时回复" — AI读空气、动态概率、注意力机制
- **自学习插件** 负责"智能优化如何回复" — 对话风格学习、人格自动优化、好感度系统

两者功能互补，推荐组合使用。欢迎加入 **QQ群 1021544792** 交流！

---

## 🆕 v1.2.0 更新亮点

**这是一次重大更新**，完全重构了上下文管理和内存管理机制，大幅提升AI判断准确性和系统稳定性。

### 核心重构

- **上下文管理全面重构** — 重写了整条消息获取、缓存、存储链路，彻底解决上下文断裂和AI认错人问题。概率判断失败的消息也会被缓存，确保AI始终能看到完整对话流
- **内存管理机制重构** — 防止内存泄漏，长时间运行更加稳定。所有数据结构都有自动清理和容量保护
- **充分利用平台机制** — 自动提取平台的图片理解结果，减少重复API调用，为AI提供最佳上下文

### 新增功能

| 功能 | 说明 |
|------|------|
| **群聊等待窗口** | 同一用户连续发送多条消息时，合并处理而非逐条回复 |
| **拟人增强模式** | 沉默状态机、决策历史追踪、兴趣话题匹配、动态消息阈值 |
| **对话疲劳机制** | 连续对话轮次越多回复倾向越低，模拟真人疲劳感 |
| **转发消息解析** | 自动解析QQ合并转发消息，转换为可读文本供AI理解 |
| **图片描述缓存** | 本地缓存图片转文字结果，相同图片不重复调用API，省钱 |
| **注意力冷却机制** | AI判断不回复时智能降低注意力，避免注意力虚高 |
| **表情包概率衰减** | QQ表情包消息自动降低触发概率，减少无意义回复 |
| **AI回复内容过滤** | 发送前/保存前过滤AI输出中的不需要内容 |
| **重复消息拦截** | 防止AI发送与近期回复重复的内容 |

### 兼容性

- 适配新版 AstrBot (>= v4.11.0)
- 适配新版 LivingMemory 记忆插件 (v1/v2 自动检测)
- 完全向下兼容 v1.1.x 配置，升级无需修改任何配置

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

### 依赖要求

- **必需**: AstrBot >= v4.0.0
- **必需**: `pypinyin >= 0.44.0`
- **推荐**: `astrbot_plugin_livingmemory` 或 `strbot_plugin_play_sy` (记忆系统)

---

## 🎯 v1.2.0 完整推荐配置

以下是 v1.2.0 全功能推荐配置，适合希望Bot表现得最接近真人的场景。

> 所有配置项的详细说明均可在 AstrBot 插件配置面板中查看，此处仅列出推荐值。

```json
{
  "enable_group_chat": true,
  "enabled_groups": [],
  "enable_debug_log": false,

  "decision_ai_provider_id": "",
  "initial_probability": 0.15,
  "after_reply_probability": 0.15,
  "probability_duration": 120,
  "decision_ai_prompt_mode": "append",
  "decision_ai_extra_prompt": "",
  "decision_ai_timeout": 30,
  "reply_timeout_warning_threshold": 120,
  "concurrent_wait_max_loops": 15,
  "concurrent_wait_interval": 5.0,
  "reply_ai_prompt_mode": "append",
  "reply_ai_extra_prompt": "",

  "include_timestamp": true,
  "include_sender_info": true,
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

  "enable_emoji_filter": true,
  "emoji_probability_decay": 0.7,
  "emoji_decay_min_probability": 0.1,

  "enable_memory_injection": true,
  "memory_plugin_mode": "legacy",
  "livingmemory_version": "v1",
  "livingmemory_top_k": 5,
  "memory_insertion_timing": "pre_decision",

  "enable_tools_reminder": false,

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
  "poke_after_reply_probability": 0.15,
  "poke_after_reply_delay": 0.5,
  "enable_poke_trace_prompt": true,
  "poke_trace_max_tracked_users": 5,
  "poke_trace_ttl_seconds": 300,
  "poke_enabled_groups": [],

  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "enable_ignore_at_all": true,

  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.1,
  "attention_duration": 120,
  "attention_max_tracked_users": 10,
  "attention_decay_halflife": 300,
  "emotion_decay_halflife": 600,
  "attention_boost_step": 0.4,
  "attention_decrease_step": 0.1,
  "attention_decrease_on_no_reply_step": 0.15,
  "attention_decrease_threshold": 0.3,
  "emotion_boost_step": 0.1,
  "enable_attention_emotion_detection": true,
  "attention_enable_negation": true,
  "attention_positive_emotion_boost": 0.1,
  "attention_negative_emotion_decrease": 0.15,
  "enable_attention_spillover": true,
  "attention_spillover_ratio": 0.35,
  "enable_attention_cooldown": true,
  "cooldown_max_duration": 600,
  "cooldown_trigger_threshold": 0.3,
  "cooldown_attention_decrease": 0.2,

  "enable_conversation_fatigue": true,
  "fatigue_reset_threshold": 300,
  "fatigue_threshold_light": 3,
  "fatigue_threshold_medium": 5,
  "fatigue_threshold_heavy": 8,
  "fatigue_probability_decrease_light": 0.1,
  "fatigue_probability_decrease_medium": 0.2,
  "fatigue_probability_decrease_heavy": 0.35,
  "fatigue_closing_probability": 0.3,

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

  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,

  "enable_proactive_chat": true,
  "proactive_silence_threshold": 600,
  "proactive_probability": 0.3,
  "proactive_check_interval": 60,
  "proactive_require_user_activity": true,
  "proactive_min_user_messages": 3,
  "proactive_user_activity_window": 300,
  "proactive_max_consecutive_failures": 3,
  "proactive_cooldown_duration": 1800,
  "proactive_enable_quiet_time": true,
  "proactive_quiet_start": "23:00",
  "proactive_quiet_end": "07:00",
  "proactive_transition_minutes": 30,
  "proactive_use_attention": true,
  "proactive_temp_boost_probability": 0.5,
  "proactive_temp_boost_duration": 120,
  "proactive_enabled_groups": [],
  "enable_proactive_at_conversion": false,

  "enable_adaptive_proactive": true,
  "score_increase_on_success": 15,
  "score_decrease_on_fail": 8,
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
  "humanize_interest_boost_probability": 0.3,

  "enable_output_content_filter": false,
  "output_content_filter_rules": [],
  "enable_save_content_filter": false,
  "save_content_filter_rules": [],

  "enable_group_wait_window": true,
  "group_wait_window_timeout_ms": 3000,
  "group_wait_window_max_extra_messages": 3,
  "group_wait_window_max_users": 5,
  "group_wait_window_attention_decay_per_msg": 0.05,

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
> - 其他所有配置项的详细说明均可在 AstrBot 插件配置面板中直接查看

---


### 记忆插件支持

| 插件 | 模式 | 特性 |
|------|------|------|
| [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) | LivingMemory | 混合检索、智能总结、自动遗忘、会话隔离、人格隔离 |
| [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) | Legacy （推荐）| 传统记忆模式，兼容旧版 ，稳定性高|

---

## 📝 更新日志

### v1.2.0 (2026-02-26)

**重大更新：上下文管理与内存管理机制完全重构**

**核心重构**:
- **上下文管理全面重写** — 重构整条消息获取、缓存、格式化、存储链路
  - 概率判断失败的消息也进入缓存，AI始终能看到完整对话流
  - 统一发送者信息格式，彻底解决AI认错人问题
  - 智能去重，缓存转正机制更加可靠
- **内存管理机制重构** — 所有数据结构都有自动清理和容量保护，防止内存泄漏
- **平台机制充分利用** — 自动提取平台图片理解结果，减少重复API调用

**新增功能**:
- **群聊等待窗口** — 同一用户连续发消息时合并处理，避免消息碎片化
- **拟人增强模式** — 沉默状态机、决策历史追踪、兴趣话题匹配、动态消息阈值
- **对话疲劳机制** — 三级疲劳(轻/中/重)，连续对话越多回复倾向越低
- **转发消息解析** — 自动解析QQ合并转发消息为可读文本
- **图片描述缓存** — 本地缓存图片转文字结果，相同URL不重复调用
- **注意力冷却机制** — AI不回复时智能降低注意力，带保护阈值
- **表情包概率衰减** — QQ表情包消息自动降低触发概率
- **AI回复内容过滤** — 发送前/保存前按规则过滤AI输出
- **重复消息拦截** — 检查近期回复防止AI发送重复内容
- **指令前缀匹配** — 支持参数化指令的前缀匹配过滤

**兼容性**:
- 适配新版 AstrBot (>= v4.11.0)
- 适配 LivingMemory v1/v2 自动检测
- 完全向下兼容 v1.1.x 配置

---

### v1.1.2 (2025-11-29)

**🆕 核心功能更新：关键词智能模式 + 智能自适应主动对话**

**核心更新**:
- ✨ **关键词智能模式（Keyword Smart Mode）** - 让关键词触发更灵活智能
  - 新增 `keyword_smart_mode` 配置项（默认关闭）
  - **传统模式（关闭）**：检测到关键词 → 跳过概率筛选 + 跳过AI判断 → 必定回复
  - **智能模式（开启）**：检测到关键词 → 跳过概率筛选 + **保留AI判断** → AI决定是否回复
  - 拒绝机械式回复，让AI根据上下文智能判断是否应该回复
  - 适用场景：避免关键词误触发（如"帮助"出现在其他对话中）
  
- ✨ **完整指令字符串检测（Full Command Detection）** - 更精准的指令过滤
  - 新增 `enable_full_command_detection` 配置项（默认关闭）
  - 新增 `full_command_list` 配置项（默认：`["new", "help", "reset"]`）
  - 支持全字符串匹配：单独的 `new`、`@机器人 new` 识别为指令
  - 不匹配部分内容：`new你好`、`@机器人 new你好` 视为普通消息
  - 自动去除@组件和空白符进行匹配，更智能
  - 与前缀检测互补：前缀检测处理 `/help`，完整检测处理 `new`
  
- 📊 **智能自适应主动对话** - 互动评分系统
  - 新增 `enable_adaptive_proactive` 配置项（默认开启）
  - **互动评分机制**：根据群聊互动反馈自动调整Bot活跃度
    - 成功互动（有人回复）→ 加分（默认+15分）
    - 失败互动（无人理会）→ 扣分（默认-8分）
    - 快速回复（30秒内）→ 额外奖励（+5分）
    - 多人回复 → 额外奖励（+10分）
    - 连续成功 → 连击奖励（+5分）
    - 低分复苏 → 鼓励奖励（+20分）
  - **评分影响**：
    - 高分群聊（>70分）→ 主动对话概率提升、沉默阈值缩短
    - 低分群聊（<30分）→ 主动对话概率降低、沉默阈值延长
    - 极低分群聊（<20分）→ 显著抑制，进入"冷淡期"
  - **自动衰减**：每24小时无互动 → 自动扣2分（防止吃老本）
  - **评分范围**：10-100分（保底分数给翻身机会）
  - 让AI像真人一样：越聊越开心，冷场自动收敛

- 🎯 **注意力机制增强** - 智能衰减与情感检测
  - 新增 `attention_decrease_on_no_reply_step` 配置项（默认0.15）
    - AI判断不回复时，智能降低对该用户的注意力
    - 表示用户可能在跟别人聊天，AI应减少关注
    - 只对高注意力用户生效，避免过度惩罚
  - 新增 `attention_decrease_threshold` 配置项（默认0.3）
    - 保护机制：注意力低于此值时不再衰减
    - 给用户保留一定关注度，避免完全忽视
  - 新增 `enable_attention_emotion_detection` 配置项（默认关闭）
    - AI回复时分析消息的正负面情绪
    - 正面消息额外提升情绪值，负面消息降低情绪值
  - 新增情感关键词配置（`attention_emotion_keywords`）
    - 独立于情绪追踪系统的情感检测
    - 支持否定词检测（`attention_enable_negation`）
  - 更智能的注意力转移，更自然的情感反应

- 👆 **戳一戳功能增强** - 智能概率增值
  - 优化 `poke_bot_skip_probability` 配置逻辑
    - **开启**：戳机器人时跳过概率筛选（旧行为保持）
    - **关闭**：戳机器人时参与概率判断，但增加额外概率
  - 新增 `poke_bot_probability_boost_reference` 配置项（默认0.3）
    - 参考值而非直接增加值，系统智能决定实际增值
    - 根据情绪、注意力等因素动态调整
    - 情绪负面时减少增值，情绪正面时允许更多增值
    - 更拟人化的戳一戳响应机制
  - 新增 `poke_enabled_groups` 配置项
    - 戳一戳功能的群组白名单
    - 留空=所有群启用，填群号=仅指定群启用
    - 与全局 `enabled_groups` 独立控制

- 🧠 **智能记忆系统适配** - 支持LivingMemory插件
  - 🆕 **双模式记忆插件支持**
    - **LivingMemory模式**（新增，推荐）
      - 插件：`astrbot_plugin_livingmemory`
      - 特性：混合检索、智能总结、自动遗忘
      - 会话隔离、人格隔离、动态人格切换
      - 按重要性×相关性×新鲜度自动排序
    - **Legacy模式**（传统）
      - 插件：`strbot_plugin_play_sy`
      - 兼容v1.1.1及之前版本的配置
  - 🆕 新增 `memory_plugin_mode` 配置项（默认`"auto"`）
    - `auto`：自动检测，优先LivingMemory
    - `livingmemory`：强制使用LivingMemory
    - `legacy`：强制使用Legacy模式
  - 🆕 新增 `memory_top_k` 配置项（默认5）
    - LivingMemory模式：指定召回记忆数量
    - `-1`：召回所有相关记忆（最多1000条）
    - Legacy模式：忽略此配置
  - ⚡ **LivingMemory模式优势**
    - 混合检索：关键词+语义+时间多维度
    - 智能总结：自动提取长对话关键信息
    - 自动遗忘：根据重要性和时间淡化旧记忆
    - 会话隔离：每个群聊记忆独立
    - 人格隔离：支持多人格场景
    - 动态切换：实时获取当前人格，切换立即生效
    - 智能排序：记忆按综合得分排序，重要的在前
  - 📍 在 `memory_injector.py` 中完全重构
    - 新增双模式支持逻辑
    - 新增LivingMemory API调用
    - 新增会话+人格隔离机制
    - 优化记忆格式化输出（含重要性星级显示）
  - 🔒 完全向后兼容，自动检测并选择合适模式

**🔧 架构重构与优化** - 核心流程全面升级
- 🏗️ **消息上下文获取完全重构**
  - 重构整个消息上下文获取流程
  - 统一规范化发送者名字添加逻辑
  - **彻底解决AI认错人问题**
    - 每条消息明确标注发送者ID和名字
    - 历史消息格式统一，避免混淆
    - 上下文构建时强制保留发送者信息
  - 提升上下文质量，AI能准确识别每个发言者
  
- 💾 **智能缓存策略优化**
  - **概率判断失败时也会缓存消息**（重要改进）
  - 旧版：概率失败 → 消息丢失 → 上下文不完整
  - 新版：概率失败 → 消息缓存 → 等待下次一起提供
  - **构建最完整的上下文消息**
    - 不会因概率判断失败而丢失用户对话
    - AI能看到完整的群聊流程，减少"断章取义"
    - **大大减少乱读空气通过的情况**
  - 缓存策略更智能，上下文连续性更好
  
- 🔍 **AI响应过滤器** - 新增 `ai_response_filter.py`
  - **解决思考模型误判问题**
  - **背景**：某些LLM（如o1/o1-mini/DeepSeek-R1等）输出带思考链
    ```
    示例输出：
    <think>
    用户问的是天气，我应该回复...
    </think>
    好的，今天天气不错
    ```
  - **问题**：读空气AI看到完整输出（含思考链）→ 误判为"要回复"
  - **解决方案**：
    - 新增 `ai_response_filter.py` 智能过滤器
    - 在读空气AI判断前自动过滤思考链
    - 支持多种思考链格式：
      - `<think>...</think>`
      - `<thinking>...</thinking>`
      - `【思考】...【/思考】`
      - 其他常见格式
    - 只保留最终回复内容供读空气AI判断
  - **效果**：
    - 避免思考链内容影响读空气判断
    - 提高判断准确性，减少误判
    - 兼容主流思考模型（o1系列、DeepSeek-R1等）
  - 📍 在 `decision_ai.py` 中自动调用过滤器
  
- 🛠️ **代码质量提升**
  - 统一错误处理机制
  - 优化日志输出格式
  - 提升代码可维护性

**🔧 吐槽系统优化** - 修复冷却重置问题
  - 🔧 **累积失败次数独立追踪**
    - 旧版：吐槽依赖 `consecutive_failures`，冷却时被重置
    - 新版：新增 `total_proactive_failures` 字段，独立累积
    - 吐槽基于累积失败次数，不受冷却影响
  - 🔧 **配置合理性检查**
    - 新增 `complaint_trigger_threshold` 配置项（默认2次）
    - 累积失败达到此次数后才开始检查吐槽等级
    - 与 `max_failures` 独立，可以 >= max_failures
  - 🔧 **吐槽衰减机制**
    - 新增 `complaint_decay_on_success` 配置项（默认2次）
    - 每次成功互动减少部分累积失败次数
    - 新增时间衰减：长时间无新失败自动衰减
    - 新增累积上限：`complaint_max_accumulation`（默认15次）
  - 让Bot的情绪变化更自然，不会因冷却而"失忆"

**🆕 防误判机制（主动对话）** - v1.2.0核心改进
  - 🔒 **严格状态追踪**
    - 新增 `proactive_active` 标记：主动对话发送成功后才激活
    - 新增 `proactive_outcome_recorded` 标记：防止重复记录结果
    - 只有真正发送成功的主动对话才进入检测
  - 🔒 **多人回复追踪**
    - 在整个临时提升期内持续追踪所有回复用户
    - 但不在接收消息时判定成功，等待AI真正决定回复
    - 避免"用户回复但AI不回复"被误判为成功
  - 🔒 **结果判定时机优化**
    - 成功判定：AI决定回复时才记录成功
    - 失败判定：维持期结束且无人理会时记录失败
    - 冷却期内不重复触发主动对话

**技术实现**:
- 📍 **核心架构重构**
  - 在 `context_manager.py` 中完全重构消息上下文获取流程
    - 统一消息格式化：所有消息强制包含发送者ID和名字
    - 优化缓存策略：概率失败的消息也进入缓存队列
    - 智能去重：避免重复消息影响上下文质量
  - 在 `main.py` 中优化消息处理流程
    - 规范化发送者名字添加逻辑
    - 确保每条消息都有完整的发送者信息
    - 彻底解决AI认错人的问题
- 📍 **AI响应过滤器**（新增 `ai_response_filter.py`）
  - `filter_thinking_tags` 方法：智能识别并过滤思考链
  - 支持多种格式：XML标签、中文标记、Markdown代码块等
  - 在 `decision_ai.py` 中自动调用，无需用户配置
  - 兼容主流思考模型（o1、o1-mini、DeepSeek-R1等）
- 📍 在 `main.py` 中新增关键词智能模式检测逻辑
  - `_check_probability_before_processing` 方法中区分智能模式
  - `_should_do_ai_decision` 方法中根据模式决定AI判断
- 📍 在 `main.py` 中新增完整指令检测逻辑
  - `_is_command_message` 方法增强，支持全字符串匹配
  - 自动去除@组件、空格、空白符后匹配
- 📍 在 `memory_injector.py` 中完全重构记忆系统
  - 新增双模式检测和切换逻辑
  - LivingMemory模式：会话+人格隔离、智能排序
  - Legacy模式：兼容旧版配置
- 📍 在 `ProactiveChatManager` 中新增评分系统
  - `update_interaction_score` 方法：更新评分
  - `record_proactive_success_for_score` 方法：记录成功
  - `record_proactive_failure_for_score` 方法：记录失败
  - `calculate_adaptive_parameters` 方法：根据评分计算参数
  - `apply_score_decay` 方法：时间衰减
- 📍 在 `ProactiveChatManager` 中新增防误判机制
  - `proactive_active` 字段：主动对话激活状态
  - `proactive_outcome_recorded` 字段：结果记录标记
  - `total_proactive_failures` 字段：累积失败次数（独立）
- 📍 在 `AttentionManager` 中新增智能衰减逻辑
  - `record_no_reply_attention_decrease` 方法：不回复时衰减
  - `detect_message_emotion` 方法：情感检测
  - 独立的情感关键词和否定词配置
- 📍 在戳一戳处理中新增智能概率增值
  - 根据情绪、注意力动态计算实际增值
  - 情绪负面时大幅减少，情绪正面时允许更多
- 🔒 完全向后兼容v1.1.1，旧配置继续有效
- 🔒 所有新功能都有合理的默认值

**配置示例**（完整功能）:
```json
{
  "initial_probability": 0.15,
  "after_reply_probability": 0.15,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "attention_decrease_on_no_reply_step": 0.15,
  "attention_decrease_threshold": 0.3,
  "enable_attention_emotion_detection": true,
  "trigger_keywords": ["帮助", "机器人"],
  "keyword_smart_mode": true,
  "enable_full_command_detection": true,
  "full_command_list": ["new", "help", "reset", "clear"],
  "enable_proactive_chat": true,
  "enable_adaptive_proactive": true,
  "score_increase_on_success": 15,
  "score_decrease_on_fail": 8,
  "interaction_score_min": 10,
  "interaction_score_max": 100,
  "enable_complaint_system": true,
  "complaint_trigger_threshold": 2,
  "complaint_decay_on_success": 2,
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": false,
  "poke_bot_probability_boost_reference": 0.3,
  "poke_enabled_groups": []
}
```

**升级说明**:
- 从v1.1.1升级无需任何配置修改
- 新功能默认关闭或使用安全默认值
- 智能自适应主动对话默认开启（`enable_adaptive_proactive: true`）
- 关键词智能模式默认关闭（`keyword_smart_mode: false`），保持兼容
- 完整指令检测默认关闭（`enable_full_command_detection: false`）
- 100%向后兼容

**修改文件**:
- `_conf_schema.json` - 新增20+个配置项（关键词智能模式、完整指令检测、评分系统、注意力增强、戳一戳增强、吐槽优化、记忆插件配置等）
- `main.py` - 关键词智能模式、完整指令检测、评分系统集成、防误判机制、消息上下文获取重构、发送者名字添加逻辑优化
- `utils/context_manager.py` - **完全重构**消息上下文获取流程、优化缓存策略（概率失败也缓存）、规范化发送者信息格式
- `utils/proactive_chat_manager.py` - 评分系统、防误判机制、吐槽系统优化
- `utils/attention_manager.py` - 智能衰减、情感检测、独立配置
- `utils/memory_injector.py` - **完全重构**支持LivingMemory和Legacy双模式、会话+人格隔离
- `utils/decision_ai.py` - 集成AI响应过滤器、优化读空气判断流程
- `utils/ai_response_filter.py` - **新增**思考链过滤器，支持多种思考模型（o1/DeepSeek-R1等）

**重要说明**:
- **关键词智能模式**：建议谨慎启用，需要配合优质的决策AI提示词
- **智能自适应主动对话**：默认开启，会自动调整Bot在不同群聊的表现
- **评分系统**：基于v1.2.0内核，后续版本将继续优化
- **防误判机制**：解决了早期版本"用户回复但AI不理会却被误判为成功"的问题
- **架构重构**：消息上下文获取和缓存策略的重构是v1.1.2的核心改进之一，大幅提升AI判断准确性
- **AI响应过滤器**：如果你使用思考模型（o1/DeepSeek-R1等）作为读空气AI，过滤器会自动工作，无需额外配置
- **智能缓存**：即使概率判断失败，消息也会被缓存，确保AI始终能看到完整对话上下文

**🤝 插件合作**:
- **AstrBot智能自学习插件**：v1.1.2版本与 [astrbot_plugin_self_learning](https://github.com/NickCharlie/astrbot_plugin_self_learning) 建立官方合作关系
- **完美互补**：本插件负责"智能决策何时回复"，自学习插件负责"智能优化如何回复"
- **推荐组合使用**：读空气能力 + 人格学习 = 最智能的群聊Bot体验
- **进一步合作**：更深度的API接口兼容正在开发中，将实现双向数据共享、统一决策引擎等高级功能，敬请期待！
- **交流群**：欢迎加入 QQ群 1021544792（ChatPlus & 自学习插件用户交流群）

---

### v1.1.1 (2025-11-15)

**🧩 稳定性与拟人化体验升级**

**主动对话体验优化**：
- 调整主动聊天调度逻辑，显式区分“正常沉默触发”和“主动后等待回应阶段”。
- 在主动消息发送后的临时概率提升维持期内，不再重复触发新的主动开场，避免早期版本可能出现的“连续自言自语”现象。
- 仅当维持期结束且仍无人理会时，才按 `proactive_max_consecutive_failures` / `proactive_cooldown_duration` 进行连续失败计数与冷却，修复了部分环境下“自动重试/冷却参数难以生效”的问题。

**上下文与用户识别改进**：
- 升级 `ContextManager`，统一使用结构化的 `AstrBotMessage` 存储与还原历史消息，确保在多平台/多群场景下上下文提取更加稳定。
- 在格式化上下文时，更可靠地根据 `sender.user_id` 与机器人ID对齐，标记【你自己的历史回复】，减少“把别人发的内容误当成自己的历史回复”的情况。
- 结合新的系统提示词约束，让决策AI/回复AI在使用历史时更聚焦于当前新消息，且不会在回复中泄露任何系统提示或内部标记。

**戳一戳追踪与互动细化**：
- 新增戳一戳追踪提示开关及相关配置：
  - `enable_poke_trace_prompt`, `poke_trace_max_tracked_users`, `poke_trace_ttl_seconds`。
- 当启用时，AI在对某用户执行戳一戳后，会在一段时间内看到 `[戳过对方提示]`，更自然地延续这段互动；提示仅对AI可见，不写入官方历史。
- `MessageCleaner` 新增对应清理规则，确保这些内部提示不会污染正式聊天记录。

**重置指令与配置新增**：
- 新增两条插件指令：
  - `gcp_reset`：插件级重置，清空本插件全局缓存并触发重载/重启。
  - `gcp_reset_here`：会话级重置，仅清理当前群的本插件状态与本地缓存。
- 新增配置项：`plugin_reset_allowed_user_ids`，用于控制哪些用户可以触发上述重置指令（空列表=允许所有人）。
- README 中补充了“切换人设/提示词时如何配合重置指令与 AstrBot 官方会话清空指令”的推荐操作流程，降低人格混乱风险。

**其它修复与细节优化**：
- 调整若干日志与异常处理路径，使与 `ProactiveChatManager`、`ContextManager`、注意力管理等相关的错误更易排查。
- 小幅优化内部清理逻辑，确保在会话重置与插件重置后，概率/注意力/主动对话等状态都会被正确刷新。
- 删除之前使用AI辅助开发时，AI莫名其妙添加但实际上没有实现的功能配置选项。

---

### v1.1.0 (2025-11-12)

**🆕 主动聊天与时段概率（拟人化升级）**

**核心更新**:
- ✨ **主动聊天（Proactive Chat）**: 群聊长时间沉默后，AI可自然开场或延展话题
  - 支持用户活跃度判断与失败冷却，避免自说自话
  - 支持禁用时段与过渡，深夜自动安静不打扰
  - 主动发言后提供短时“更关注回复”的临时概率提升
- ✨ **时段概率（Time Periods）**: 根据时间段动态调整普通回复与主动聊天概率
  - 支持平滑过渡（ease-in-out），更拟合作息与社交节奏
  - 支持上下限系数，避免过高或过低
- ✨ **概率硬限制**: 一键将最终概率限制在区间内，简化配置（谨慎使用）

**提示词更新**:
- 🔧 **决策AI**和**回复AI**系统提示词优化
  - 强化“只关注当前新消息”的判断原则
  - 内置“防重复”与“禁元信息”规则，禁止提及系统提示或内部机制
  - 对【戳一戳】与【@指向说明】的理解更自然

**戳一戳增强**:
- 🆕 **回复后戳一戳**: 主动回复后可按概率轻微戳一下对方（延迟可配）
- 🆕 **收到戳一戳时反戳概率**: 支持直接反戳并结束后续流程（不拦截其他插件）

**新增配置项（部分）**:
- 主动聊天：`enable_proactive_chat`, `proactive_silence_threshold`, `proactive_probability`, `proactive_check_interval`, `proactive_require_user_activity`, `proactive_min_user_messages`, `proactive_user_activity_window`, `proactive_max_consecutive_failures`, `proactive_cooldown_duration`, `proactive_enable_quiet_time`, `proactive_quiet_start`, `proactive_quiet_end`, `proactive_transition_minutes`, `proactive_prompt`, `proactive_use_attention`, `proactive_at_probability`, `proactive_temp_boost_probability`, `proactive_temp_boost_duration`, `proactive_enabled_groups`
- 普通回复时段概率：`enable_dynamic_reply_probability`, `reply_time_periods`, `reply_time_transition_minutes`, `reply_time_min_factor`, `reply_time_max_factor`, `reply_time_use_smooth_curve`
- 主动聊天时段概率：`enable_dynamic_proactive_probability`, `proactive_time_periods`, `proactive_time_transition_minutes`, `proactive_time_min_factor`, `proactive_time_max_factor`, `proactive_time_use_smooth_curve`
- 概率硬限制：`enable_probability_hard_limit`, `probability_min_limit`, `probability_max_limit`
- 戳一戳增强：`enable_poke_after_reply`, `poke_after_reply_probability`, `poke_after_reply_delay`, `poke_reverse_on_poke_probability`

**工作流程补充**:
- 📋 **时间段系数应用**: 在概率计算阶段应用时间段系数（含过渡/上下限/曲线）
- 📋 **主动聊天轮询**: 定时检查群聊沉默、用户活跃、失败冷却与禁用时段
- 📋 **临时概率提升**: 主动聊天发言后，在短时间内提升后续回复概率，更拟人化

---

### v1.0.9 (2025-11-06)

**🎯 功能更新：戳一戳支持 + @他人消息过滤**

**核心更新**:
- ✨ **戳一戳消息处理功能** - 智能识别和响应QQ戳一戳互动
  - 新增 `poke_message_mode` 配置项，支持三种处理模式：
    - `ignore`: 忽略所有戳一戳消息（最大兼容）
    - `self_only`: 只处理戳机器人自己的戳一戳消息（默认）
    - `all`: 处理所有戳一戳消息（包括别人戳别人）
  - **平台限制**: 仅支持QQ平台的aiocqhttp消息平台
  - **智能提示**: AI能收到清晰的戳一戳提示词，理解戳一戳互动
    - 戳机器人：`[戳一戳提示]有人在戳你，戳你的人是：XXX(ID:XXX)`
    - 戳别人：`[戳一戳提示]这条消息是别人在戳别人，不是别人在戳你...`
  - **系统提示过滤**: 戳一戳提示词在缓存时保存，保存到官方历史时自动过滤
  - **防伪造机制** 🆕: 自动检测并过滤手动输入的`[Poke:poke]`文本标识符
    - 如果消息**只包含**`[Poke:poke]`（忽略空格），直接丢弃消息
    - 如果消息**同时包含**`[Poke:poke]`和其他内容，过滤掉标识符，保留其他内容
    - 支持各种变体（大小写不敏感，支持空格变体如`[ Poke : poke ]`）
    - 防止用户通过手动输入来伪造戳一戳消息，避免AI误判
  - **最大兼容**: 不影响其他插件和官方功能
  - 适用场景：增强AI互动性，让AI能自然回应戳一戳动作

- ✨ **@他人消息过滤功能** - 避免插入他人私密对话
  - 新增 `enable_ignore_at_others` 配置项，控制是否启用此功能（默认关闭）
  - 新增 `ignore_at_others_mode` 配置项，支持两种过滤模式：
    - `strict`: 只要消息中@了其他人就直接忽略（严格模式）
    - `allow_with_bot`: 消息中@了其他人但也@了机器人时继续处理（宽松模式）
  - **智能检测**: 自动识别消息中的At组件，区分@机器人和@其他人
  - **边界感保持**: 避免AI插入他人的私密对话、安慰、询问等场景
  - **最大兼容**: 仅本插件跳过处理，不影响其他插件和官方功能
  - 适用场景：保持对话边界感，减少不必要的AI触发

**技术实现**:
- 📍 在普通处理器中添加戳一戳消息检测逻辑（黑名单检测后执行）
  - 参考 `astrbot_plugin_llm_poke` 插件实现戳一戳事件检测
  - 检测QQ平台的poke事件（post_type=notice, notice_type=notify, sub_type=poke）
  - 根据配置模式决定是否处理，保存poke_info供后续使用
- 📍 在普通处理器中添加戳一戳标识符过滤逻辑（@他人过滤后、戳一戳检测前执行）
  - 新增 `MessageCleaner.is_only_poke_marker()` 方法检测纯标识符消息
  - 如果消息只包含`[Poke:poke]`（忽略空格），直接返回丢弃
  - 使用正则表达式支持大小写不敏感和空格变体
- 📍 在MessageCleaner中添加戳一戳文本标识符过滤方法
  - 新增 `filter_poke_text_marker()` 方法过滤消息中的`[Poke:poke]`标识符
  - 集成到 `extract_raw_message_from_event()` 的所有提取路径中
  - 自动在提取消息时过滤掉伪造的戳一戳标识符
- 📍 在MessageProcessor中添加戳一戳系统提示词生成逻辑
  - `add_metadata_to_message`和`add_metadata_from_cache`都支持poke_info参数
  - 根据is_poke_bot区分戳机器人和戳别人的情况
  - 使用[]括号而非【】括号，确保能被正确过滤
- 📍 在MessageCleaner中添加戳一戳系统提示词过滤规则
  - 支持过滤所有可能的戳一戳提示词格式组合
  - 保存到官方历史时自动过滤，保持历史记录干净
- 📍 在DecisionAI和ReplyHandler提示词中添加戳一戳标记说明
  - 告诉决策AI如何判断是否回复戳一戳消息
  - 告诉回复AI如何自然回应戳一戳（俏皮话、调侃等）
- 📍 在普通处理器中添加@他人消息过滤逻辑（黑名单检测后、戳一戳标识符过滤前执行）
  - 检测消息中的At组件，区分@机器人和@其他人
  - 根据配置模式决定是否跳过处理
  - 过滤掉@全体成员（@all）的情况
- 🔒 完全向后兼容v1.0.8，旧配置继续有效
- 🔒 所有新功能都有合理的默认值（默认关闭，不影响现有行为）

**工作流程更新**:
- 📋 步骤0（消息标记检查）新增三个检测环节：
  - **@他人消息过滤检测**（在黑名单检测后执行）
    - 检查`enable_ignore_at_others`配置
    - `strict`模式：@了其他人 → 跳过处理
    - `allow_with_bot`模式：@了其他人但未@机器人 → 跳过处理
  - **戳一戳标识符过滤检测** 🆕（在@他人过滤后执行）
    - 检测消息是否只包含`[Poke:poke]`标识符（忽略空格）
    - 如果是纯标识符 → 直接丢弃消息，记录日志
    - 如果包含其他内容 → 继续处理（在步骤6提取消息时自动过滤标识符）
  - **戳一戳消息检测**（在标识符过滤后执行）
    - 检查`poke_message_mode`配置
    - `ignore`模式：检测到戳一戳 → 跳过处理
    - `self_only`模式：戳的是机器人 → 保存poke_info继续，否则跳过
    - `all`模式：所有戳一戳 → 保存poke_info继续
- 📋 步骤6（提取消息）：
  - `MessageCleaner.extract_raw_message_from_event()` 自动过滤`[Poke:poke]`标识符
  - 在所有提取路径中都应用过滤，确保消息内容干净
- 📋 步骤7（缓存消息）：
  - 缓存中新增`poke_info`字段，保存戳一戳信息
- 📋 步骤7.5（添加元数据）：
  - 检测poke_info，存在则添加戳一戳系统提示词
  - 戳机器人和戳别人使用不同的提示词格式

**数据流更新**:
- 🔄 消息进入 → 指令过滤 → 用户黑名单检测 → **@他人消息过滤** 🆕 → **戳一戳标识符过滤** 🆕 → **戳一戳消息检测** 🆕 → 基础检查 → ...
- 🔄 消息提取环节：`extract_raw_message_from_event()` → **自动过滤[Poke:poke]标识符** 🆕 → 返回纯净消息内容
- 🔄 缓存结构新增字段：`poke_info`（包含is_poke_bot, poker_id, target_id等信息）
- 🔄 元数据添加环节：mention_info处理 → **poke_info处理** 🆕 → 发送者识别系统提示 → ...

**提示词优化**:
- 📝 **DecisionAI提示词**新增戳一戳标记说明：
  - 告诉AI如何判断是否回复戳一戳消息
  - "有人在戳你"：可以考虑回复一句俏皮话或表达反应
  - "别人在戳别人"：通常不需要回复，除非想评论这个互动
- 📝 **ReplyHandler提示词**新增戳一戳标记说明：
  - 告诉AI如何自然回应戳一戳
  - "有人在戳你"：可以回复俏皮话、表达反应或调侃对方
  - "别人在戳别人"：理解这个互动但不要过度介入

**使用效果**:
- ✅ AI能识别和回应戳一戳互动，增强趣味性
- ✅ 避免AI误判别人戳别人的情况
- ✅ 防止用户通过手动输入`[Poke:poke]`来伪造戳一戳消息
- ✅ 自动过滤消息中的戳一戳标识符，保持消息内容干净
- ✅ 避免AI插入他人私密对话，保持边界感
- ✅ 灵活配置，适应不同场景需求
- ✅ 完全不影响其他插件和官方功能
- ✅ 系统提示词自动过滤，保持历史记录干净

**适用场景**:
- **戳一戳功能**:
  - 增强互动性，让AI能回应戳一戳动作
  - 监控群内戳一戳互动（all模式）
  - 只响应戳机器人的情况（self_only模式）
- **@他人过滤功能**:
  - 避免AI插入他人的安慰、询问等私密对话
  - 保持对话边界感，不干扰他人互动
  - 配合@机器人功能使用（allow_with_bot模式）

**配置示例**:
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot"
}
```

**修改文件**:
- `_conf_schema.json` - 新增四个配置项（戳一戳模式 + 戳机器人跳过概率 + @他人过滤开关 + @他人过滤模式）
- `main.py` - 添加戳一戳检测方法、@他人过滤方法、戳一戳标识符过滤、概率跳过逻辑、新配置项读取
  - 新增 `_check_poke_message` 方法
  - 新增 `_should_ignore_at_others` 方法
  - 新增戳一戳标识符过滤逻辑（在步骤0，@他人过滤后执行）
  - 增强 `_check_probability_before_processing` 方法，支持戳机器人跳过概率
  - 更新版本号到v1.0.9
- `utils/message_processor.py` - 支持poke_info参数，生成戳一戳系统提示词
  - `add_metadata_to_message`新增poke_info参数
  - `add_metadata_from_cache`新增poke_info参数
  - 更新版本号到v1.0.9
- `utils/message_cleaner.py` - 添加戳一戳文本标识符和系统提示词过滤功能
  - 新增 `filter_poke_text_marker()` 方法，过滤消息中的`[Poke:poke]`文本标识符
  - 新增 `is_only_poke_marker()` 方法，检测消息是否只包含`[Poke:poke]`标识符
  - 在 `extract_raw_message_from_event()` 中集成标识符过滤
  - 支持过滤所有戳一戳系统提示词格式
  - 更新版本号到v1.0.9
- `utils/decision_ai.py` - 提示词中添加戳一戳标记说明
  - 更新版本号到v1.0.9
- `utils/reply_handler.py` - 提示词中添加戳一戳标记说明
  - 更新版本号到v1.0.9
- `metadata.yaml` - 更新版本号到v1.0.9

**升级说明**:
- 从v1.0.8升级无需任何配置修改
- 不影响现有功能和行为
- 100%向后兼容

**注意事项**:
- 戳一戳功能仅支持QQ平台的aiocqhttp消息平台
- 其他平台会自动跳过戳一戳检测
- 戳一戳提示词使用[]括号而非【】括号，确保能被正确过滤
- 戳一戳标识符过滤在消息处理的最早阶段执行，确保不会被误判
- 过滤逻辑支持大小写不敏感和各种空格变体（如`[ Poke : poke ]`）
- @他人过滤不会影响其他插件和官方功能，仅本插件跳过处理

---

### v1.0.8 (2025-11-04)

**🔧 小更新：频率动态调整增强 + 内存管理优化**

**核心更新**:
- ✨ **内存管理优化** - 情绪系统新增自动清理机制，防止内存泄漏
  - 新增 `mood_cleanup_threshold` 配置项（默认3600秒）
    - 控制群组情绪记录超过多长时间未更新将被清理
    - 可设置为0禁用自动清理
    - 建议：小型机器人7200秒，中型3600秒，大型1800秒
  - 新增 `mood_cleanup_interval` 配置项（默认600秒）
    - 控制多久检查一次并清理不活跃的群组情绪记录
    - 建议：300-1200秒
  - 自动清理长期未活跃的群组情绪记录，释放内存
  - 活跃群组不受影响，情绪记录一直保留
  - 性能影响极小（每10分钟检查一次，耗时<1ms）
- ✨ **频率调整精细控制** - 新增三个配置项，精确控制频率调整行为
  - 新增 `frequency_analysis_timeout` 配置项（默认20秒）
    - 控制AI分析发言频率时的超时时间
    - 如果AI响应慢可以适当增加，建议20-30秒
    - 避免分析超时影响主流程
  - 新增 `frequency_adjust_duration` 配置项（默认360秒）
    - 控制频率调整后的新概率持续多长时间
    - 建议设置为检查间隔的2倍左右，确保在下次检查前持续生效
    - 避免概率频繁跳变，保持稳定性
  - 新增 `frequency_analysis_message_count` 配置项（默认15条）
    - 控制分析发言频率时获取多少条最近消息
    - 活跃群聊可以设置更多(20-30)，冷清群聊可以设置更少(10-15)
    - 更灵活地适应不同群聊的活跃度

**技术实现**:
- 📍 在情绪追踪器中添加自动清理机制
  - 定期检查群组情绪记录的活跃度
  - 清理超过阈值时间未更新的群组记录
  - 支持通过配置禁用自动清理
- 📍 在频率调整器中添加可配置的超时时间控制
- 📍 添加概率调整持续时间的配置支持
- 📍 添加分析消息数量的可配置选项
- 🔒 完全向后兼容v1.0.7，旧配置继续有效
- 🔒 所有新配置项都有合理的默认值

**工作流程更新**:
- 📋 步骤16（频率调整）：
  - 收集消息时使用可配置的数量（frequency_analysis_message_count）
  - AI分析时使用可配置的超时（frequency_analysis_timeout）
  - 调整后的概率持续可配置的时间（frequency_adjust_duration）

**数据流更新**:
- 🔄 频率统计 → 定期AI分析（**可配置超时、消息数量**）→ 调整概率参数（**持续可配置时间**）→ 影响下次判断

**使用效果**:
- ✅ 防止内存泄漏，长期运行内存占用稳定
- ✅ 自动释放不活跃群组的记录，不影响活跃群组
- ✅ 更精确地控制频率调整行为
- ✅ 避免AI分析超时影响主流程
- ✅ 概率调整更稳定，不会频繁跳变
- ✅ 灵活适应不同活跃度的群聊
- ✅ 性能更可控，可根据实际情况优化

**适用场景**:
- 长期运行的机器人（防止内存泄漏）
- 加入大量群组的机器人（自动清理不活跃群组记录）
- AI提供商响应速度较慢的场景（增加超时时间）
- 需要更长时间保持调整后概率的场景（增加持续时间）
- 群聊活跃度差异较大的场景（调整分析消息数量）
- 需要精细控制频率调整行为的场景

**配置示例**:
```json
{
  "mood_cleanup_threshold": 3600,
  "mood_cleanup_interval": 600,
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 25,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 20
}
```

**修改文件**:
- `_conf_schema.json` - 新增五个配置项（两个内存管理 + 三个频率调整）
- `main.py` - 添加新配置项的读取和应用逻辑
- `utils/mood_tracker.py` - 添加自动清理机制，支持可配置的清理策略
- `utils/frequency_adjuster.py` - 更新频率调整器支持新配置
- `metadata.yaml` - 更新版本号到v1.0.8
- 所有工具模块 - 更新版本号到v1.0.8

**升级说明**:
- 从v1.0.7升级无需任何配置修改
- 新配置项会自动使用默认值
- 如需自定义可按需修改配置
- 100%向后兼容

---

### v1.0.7 (2025-11-04)

**🎯 功能更新：用户管理与情绪系统增强**

**核心更新**:
- ✨ **用户黑名单功能** - 精准控制插件响应范围
  - 新增 `enable_user_blacklist` 配置项，控制是否启用用户黑名单
  - 新增 `blacklist_user_ids` 配置项，指定要屏蔽的用户ID列表
  - 黑名单用户的消息将被本插件忽略，但不影响其他插件和官方功能(注意:虽然黑名单功能可以阻止消息在本插件中运行，但消息不会被阻止其他的插件和官方功能依然可以接收到消息，可能会被读取，然后进行回复，建议配合其他黑名单功能插件使用)
  - 支持字符串和数字类型的用户ID
  - 适用场景：屏蔽刷屏用户、机器人账号等干扰账号

- ✨ **情绪系统智能否定词检测** - 提升情绪判断准确性
  - 新增 `enable_negation_detection` 配置项（默认启用）
  - 新增 `negation_words` 配置项，可自定义否定词列表
  - 新增 `negation_check_range` 配置项，设置否定词检查范围
  - 新增 `mood_keywords` 配置项，可自定义情绪关键词
  - 智能识别"不难过"、"一点也不开心"等否定表达
  - 避免情绪误判，让AI更准确理解用户真实情绪

**技术实现**:
- 📍 在普通处理器中添加用户黑名单检测（指令过滤后执行）
- 📍 情绪检测器增强：检查关键词前N个字符内是否有否定词
- 📍 支持从 `_conf_schema.json` 读取默认配置（单一数据源）
- 🔒 完全向后兼容，所有新功能默认可用
- 🔒 黑名单检测不影响其他插件，仅控制本插件行为

**工作流程更新**:
- 📋 高优先级处理器：指令过滤 → 普通处理器 → **用户黑名单检测**
- 📋 情绪检测流程：关键词匹配 → **否定词检查** → 情绪确认

**数据流更新**:
- 🔄 新增用户黑名单检测环节（在指令过滤之后）
- 🔄 情绪检测增加否定词过滤步骤

**使用效果**:
- ✅ 精准屏蔽干扰用户，提升群聊质量
- ✅ 情绪判断更准确，减少误判
- ✅ 完全不影响其他插件和官方功能
- ✅ 配置灵活，可自定义否定词和情绪关键词

**适用场景**:
- 需要屏蔽特定用户的群聊
- 希望提升情绪检测准确性的场景
- 需要自定义情绪关键词的群聊

**配置示例**:
```json
{
  "enable_user_blacklist": true,
  "blacklist_user_ids": ["123456789", "987654321"],
  "enable_negation_detection": true,
  "negation_words": ["不", "没", "别", "一点也不"],
  "negation_check_range": 5
}
```

**修改文件**:
- `main.py` - 添加用户黑名单检测逻辑
- `utils/mood_tracker.py` - 增强情绪检测，支持否定词检测
- `_conf_schema.json` - 新增黑名单和否定词相关配置项
- `metadata.yaml` - 更新版本号和描述

---

### v1.0.6 (2025-11-03)

**🔧 维护更新：代码规范性与稳定性优化**

**本次更新内容**:
- 🛠️ **代码规范性提升**: 修复硬编码路径问题，符合AstrBot官方规范
  - 优化数据目录初始化逻辑，添加规范性提示
  - 改进兼容性回退机制，使用debug级别日志避免噪音
- 🔒 **稳定性增强**: 改进图片处理内部实现
  - 使用位置索引映射代替对象内存地址，避免潜在的对象生命周期问题
  - 提升图片转文字功能的健壮性和可靠性
- ✅ **功能保持**: 所有功能与v1.0.5完全一致，仅优化内部实现

**技术说明**:
- 本次更新为纯维护性更新，不涉及任何功能变更
- 代码质量提升，符合AstrBot插件开发最佳实践
- 100%向后兼容，可直接从v1.0.5升级

---

### v1.0.5 (2025-11-03)

**🎯 小更新：指令标识过滤**

**核心更新**:
- ✨ **指令标识过滤机制**: 避免插件处理指令消息
  - 新增 `enable_command_filter` 配置项，控制是否启用指令过滤
  - 新增 `command_prefixes` 配置项，自定义需要过滤的指令前缀（默认：`/`、`!`、`#`）
  - 支持多种指令格式检测：
    1. 直接以前缀开头（如 `/help`、`!status`）
    2. @机器人后跟指令（如 `@机器人 /help`）
    3. 消息链中@后跟指令（如 `@[AT:123456] /command`）
  - 插件只会跳过处理，不拦截消息，其他插件仍可正常工作

**技术实现**:
- 📍 使用高优先级处理器（`@filter.event_message_type`，priority=sys.maxsize-1）
- 📍 新增 `command_filter_handler()` 方法，最先执行指令检测
- 📍 **核心突破**：使用 `event.message_obj.message` 获取原始消息链
  - ⚠️ AstrBot 的 WakingCheckStage 会修改 `event.message_str`（移除指令前缀）
  - ✅ 但原始消息链 `event.message_obj.message` 不会被修改
  - ✅ 通过检查原始消息链，可准确识别指令前缀
- 📍 新增 `_is_command_message()` 方法，检查原始消息链中的 Plain 组件
- 📍 新增 `_get_message_id()` 方法，生成消息唯一标识
- 📍 使用消息ID标记机制（`self.command_messages`）实现跨处理器通信
- 📍 自动清理超过10秒的旧标记（每次检测时执行）
- 🔒 简洁高效，直接检查第一个 Plain 组件的原始文本
- 🔒 默认开启（`enable_command_filter: true`），无需手动配置
- 🔒 完全不影响其他插件的正常工作（不调用 `event.stop_event()`）

**工作流程更新**:
- 📋 新增高优先级处理器 `command_filter_handler()`
  - 在所有其他处理器之前执行（priority=sys.maxsize-1）
  - 检查是否启用指令过滤
  - 检查消息是否匹配配置的指令前缀
  - 匹配成功则生成消息ID并标记到 `self.command_messages`
  - 清理超过10秒的旧标记
  - 直接返回，不阻止事件传播
- 📋 步骤0: 普通处理器 `on_group_message()` 首先检查消息标记
  - 如果消息ID在 `self.command_messages` 中，直接返回跳过处理
  - 否则继续正常的步骤1-步骤N

**数据流更新**:
- 🔄 新增高优先级处理器（priority=sys.maxsize-1），在所有其他处理器之前执行
- 🔄 使用消息ID标记机制实现跨处理器通信
- 🔄 检测到指令后标记消息但不阻止事件传播，其他插件可正常处理
- 🔄 普通处理器检查消息标记，如已标记则跳过处理
- 🔄 自动清理超过10秒的旧标记，避免内存泄漏

**使用效果**:
- ✅ 避免AI回复指令消息，减少不必要的API调用
- ✅ 提高插件与其他指令插件的兼容性
- ✅ 用户体验更好，指令不会触发AI回复
- ✅ 完全不影响其他插件的正常工作（只标记不拦截）
- ✅ 高优先级确保指令最先被识别
- ✅ 消息标记机制确保本插件的所有处理器都能识别指令
- ✅ 自动清理机制避免内存泄漏

**适用场景**:
- 安装了其他指令插件（如管理插件、工具插件）
- 不希望AI回复以特定前缀开头的消息
- 想要更精确地控制插件的触发范围

**配置示例**:
```json
{
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#", ":"]
}
```

**修改文件**:
- `main.py` - 新增高优先级处理器 `command_filter_handler()`
- `main.py` - 重写 `_is_command_message()` 方法，使用原始消息链检测
- `main.py` - 新增 `_get_message_id()` 方法，生成消息唯一标识
- `main.py` - 在 `__init__` 中新增 `self.command_messages` 字典用于消息标记
- `main.py` - 在 `on_group_message()` 开头检查消息标记
- `_conf_schema.json` - 新增 `enable_command_filter` 和 `command_prefixes` 配置项（默认开启）

---

### v1.0.4 (2025-11-02)

**🎯 小更新：发送者识别增强 + AI提示词优化**

**核心更新**:
- ✨ **发送者识别系统提示（Sender Recognition）**: 根据触发方式添加系统提示
  - 识别三种触发方式：@消息、关键词触发、AI主动回复
  - @消息："[系统提示]注意,现在有人在直接@你并且给你发送了这条消息，@你的那个人是XXX"
  - 关键词触发："[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息，这条消息的发送者是XXX"
  - AI主动回复："[系统提示]注意，你刚刚看到了这条消息，你打算回复他，发送这条消息的人是XXX"
  - 帮助AI正确识别谁在说话，提升对话的上下文理解能力

**AI提示词优化**:
- 🔧 **决策AI防重复机制**: 
  - 新增"【防止重复】必须检查的事项"章节
  - 要求AI在判断前检查历史回复，避免重复表达相同观点
  - 强调只有当前消息提出新问题、新角度时才考虑回复
  - 禁止输出任何元信息（如"我根据规则判断..."）
- 🔧 **回复AI防重复增强**: 
  - 新增"【严禁重复】必须执行的检查步骤"
  - 要求逐条对比历史回复，相似度>50%必须换角度
  - 绝对禁止重复相同句式、观点陈述、回应模式
  - 强调即使话题相关也要用新方式表达
- 🔧 **严禁元叙述规则**: 
  - 新增"【严禁元叙述】特别重要"章节
  - 绝对禁止说"看到你@我了"、"注意到你在说XXX"等元信息
  - 强调要像人类一样直接回复内容，不解释回复动机
  - 人类不会说"我看到你@我了，所以我来回复"，应该直接说"怎么了？"

**技术实现**:
- 📍 在缓存消息时保存触发方式信息（`is_at_message`、`has_trigger_keyword`）
- 📍 在添加元数据时根据触发方式(`trigger_type`)添加相应的系统提示
- 📍 系统提示**仅用于AI判断和生成回复时理解上下文**
- 📍 使用MessageCleaner在保存到历史时**过滤掉系统提示**
- 🔒 系统提示**不会持久化保存**，只在临时处理过程中存在
- 🔒 使用半角方括号[]标记系统提示，便于过滤

**工作流程更新**:
- 📋 步骤7: 缓存消息时记录触发方式信息
- 📋 步骤7.5: 为当前消息添加元数据时根据触发方式添加临时系统提示
- 📋 步骤14: 保存消息到自定义存储前使用MessageCleaner清理系统提示
- 📋 after_message_sent: 保存到官方系统前清理系统提示

**数据流更新**:
- 🔄 概率筛选后增加"记录触发方式"环节
- 🔄 添加元数据时增加"临时系统提示"生成
- 🔄 缓存消息包含`trigger_type`字段
- 🔄 AI判断和生成回复时可见系统提示
- 🔄 保存到历史前使用MessageCleaner过滤系统提示
- 🔄 最终保存的历史消息不包含临时系统提示

**使用效果**:
- ✅ AI能清楚知道消息是@触发、关键词触发还是主动回复
- ✅ AI能准确识别发送者身份，提升对话连贯性
- ✅ 防止AI重复表达相同观点，避免啰嗦
- ✅ 禁止AI暴露内部逻辑，回复更自然真实
- ✅ 系统提示仅在处理时起作用，不会污染历史记录
- ✅ 历史消息保持干净，只包含真实对话内容

**修改文件**:
- `main.py` - 在缓存和添加元数据时记录和使用触发方式
- `utils/message_processor.py` - 增加`trigger_type`参数，根据触发方式添加系统提示
- `utils/decision_ai.py` - 优化决策AI提示词，增加防重复机制
- `utils/reply_handler.py` - 优化回复AI提示词，增加防重复和禁元叙述机制
- `utils/message_cleaner.py` - 更新过滤规则，识别系统提示标记

---

### v1.0.3 (2025-10-31)

**🎯 小更新：@提及智能识别**

**核心更新**:
- ✨ **@提及检测机制**: AI能正确理解@别人的消息
  - 自动检测消息中的@组件，识别被@的用户
  - 添加特殊标记【@指向说明】，明确消息的真实指向
  - AI理解这条消息不是发给自己的，避免误回复

**AI提示词优化**:
- 🔧 **决策AI增强**: 
  - 添加了对【@指向说明】标记的说明
  - 明确对@别人的消息要谨慎判断，尊重私密对话空间
  - 只在明确欢迎多人参与的场合才介入
  - 强调禁止输出元信息（不允许说"我根据规则判断..."）
  - **[新增]** 添加核心原则：优先关注当前新消息，避免被历史话题带偏
  - **[新增]** 所有判断情况加上"当前消息"前缀，强调判断依据
- 🔧 **回复AI增强**: 
  - 告知AI【@指向说明】和【原始内容】标记的含义
  - 禁止在回复中提及"系统提示"、"根据规则"、"@指向说明"等元信息
  - 引导AI保持边界感，作为旁观者自然评论，不要主导@别人的对话
  - 不要直接回答发给被@者的问题，不要替被@者给建议
  - **[新增]** 添加核心原则：识别当前消息核心内容，避免回复重复
  - **[新增]** 要求检查自己的历史回复，不要说相同或相似的话

**技术实现**:
- 📍 在概率判断后、图片处理前执行检测（main.py第985行）
- 💾 @信息保存到消息缓存的`mention_info`字段
- 🔒 使用全角方括号【】确保不被MessageCleaner过滤
- ✅ 完整的错误处理，不影响主流程

**消息格式**:
```
正常消息：
[2025-10-31 12:34:56] 张三(ID:12345): 你好

@别人的消息：
[2025-10-31 12:34:56] 张三(ID:12345): 
【@指向说明】这条消息通过@符号指定发送给其他用户（被@用户：李四，ID：67890），并非发给你本人。
【原始内容】@李四 你好呀
```

**使用效果**:
- ✅ 决策AI知道消息不是@自己，可以根据上下文判断是否参与
- ✅ 回复AI理解消息指向，自然参与对话而不暴露内部逻辑
- ✅ 标记永久保留到历史消息，后续AI也能正确理解

**修改文件**:
- `main.py` - 添加 `_check_mention_others()` 检测方法
- `utils/message_processor.py` - 增强元数据处理支持mention_info
- `utils/decision_ai.py` - 优化决策AI提示词，添加核心原则
- `utils/reply_handler.py` - 优化回复AI提示词，添加核心原则和避重复机制
- `utils/context_manager.py` - 增强上下文格式化，突出当前消息并标记AI历史回复

---

### v1.0.2 (2025-10-30)

**🎉 重大更新：让AI对话更像真人 + 注意力机制增强**

**核心更新**:
- ✨ **打字错误生成器（Typo Generator）**: 
  - 基于拼音相似性添加自然错别字（2%默认错误率）
  - 智能跳过代码、链接等特殊格式
  - 30%概率在符合条件的消息中触发
- ✨ **情绪追踪系统（Mood Tracker）**: 
  - 支持多种情绪类型（开心、难过、生气、惊讶等）
  - 动态更新情绪状态并影响回复语气
  - 5分钟自动衰减机制
- ✨ **回复延迟模拟（Typing Simulator）**: 
  - 模拟真人打字速度（默认15字/秒）
  - 添加±30%随机波动，最大延迟3秒
  - 避免秒回，增加真实感
- ✨ **频率动态调整（Frequency Adjuster）**: 
  - AI自动分析发言频率（每3分钟）
  - 自动调整回复概率（±15%）
  - 自适应不同群聊的节奏

**🌟 注意力机制增强（v1.0.1 → v1.0.2 重大升级）**:
- ✨ **多用户注意力追踪**: 
  - 从单用户升级为最多追踪10个用户（可配置）
  - 每个用户独立的注意力分数（0-1）和情绪值（-1到+1）
  - 同时保持对多个用户的关注，更自然
- ✨ **渐进式概率调整**: 
  - 不再是固定的0.9/0.1跳变
  - 根据注意力分数平滑计算：`基础概率 × (1 + 注意力 × 提升幅度) × (1 + 情绪 × 0.3)`
  - 概率变化更自然，更像真人
- ✨ **情绪态度系统**: 
  - 对每个用户维护情绪态度（-1负面到+1正面）
  - 正面情绪提升回复概率，负面情绪降低
  - 情绪随时间自动恢复中性（半衰期10分钟）
- ✨ **指数衰减机制**: 
  - 注意力不再突然清零，而是自然衰减
  - 半衰期5分钟：5分钟→50%，10分钟→25%
  - 更符合真人的注意力衰减规律
- ✨ **智能清理机制**: 
  - 自动清理长时间未互动（30分钟）且注意力极低（<0.05）的用户
  - 新用户可以顶替不活跃用户，不会占满名额
  - 综合排序：注意力分数 + 最后互动时间
- ✨ **数据持久化**: 
  - 保存到 `data/plugin_data/chat_plus/attention_data.json`
  - 60秒间隔自动保存（避免频繁写磁盘）
  - 重启bot后自动加载，注意力状态不丢失
  - 符合 AstrBot 平台规范，更新插件不影响数据

**新增配置项**:
- `enable_typo_generator`, `typo_error_rate`
- `enable_mood_system`
- `enable_typing_simulator`, `typing_speed`, `typing_max_delay`
- `enable_frequency_adjuster`, `frequency_check_interval`
- `attention_max_tracked_users`, `attention_decay_halflife`, `emotion_decay_halflife`, `enable_emotion_system` （注意力增强）
- `attention_boost_step`, `attention_decrease_step`, `emotion_boost_step` （注意力调整幅度自定义）

**新增依赖**:
- `pypinyin >= 0.44.0` - 用于拼音转换

**技术实现**:
- 模块化设计，所有新功能可独立开关
- 完全向后兼容v1.0.1，旧配置继续有效
- 参考MaiBot项目的优秀设计（简化实现）
- 使用 `StarTools.get_data_dir()` 确保数据目录规范
- 异步锁保护，避免竞态条件

**性能优化**:
- 注意力数据内存占用极小（100个群聊约100KB）
- 自动保存限频（60秒间隔），避免频繁IO
- 智能清理机制，自动维护合理的数据规模

**致谢**:
- 本版本新功能参考了 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 项目的设计理念

---

### v1.0.1 (2025-10-29)

**🎯 新增注意力机制**

**核心更新**:
- ✨ **注意力机制（Attention Mechanism）**: 让Bot像真人一样专注对话
  - 回复某用户后会持续关注ta的发言（可配置提升概率）
  - 其他用户插话时降低回复概率（避免频繁切换话题）
  - 支持时间窗口配置，超时后恢复普通判断
  - 提供 `enable_attention_mechanism`、`attention_increased_probability`、`attention_decreased_probability`、`attention_duration` 四个配置项

**功能增强**:
- 🔧 **提示词模式选择**: 新增 `decision_ai_prompt_mode` 和 `reply_ai_prompt_mode` 配置
  - `append` 模式：拼接在默认系统提示词后面（推荐）
  - `override` 模式：完全覆盖默认系统提示词（需填写完整提示词）
  
**工作流程优化**:
- 📋 完整处理流程新增"步骤5：注意力机制调整"
- 📋 "步骤18：调整读空气概率"更新为"步骤18：调整读空气概率 / 记录注意力"
- 🔄 支持注意力机制与传统概率提升两种模式（互斥）

**使用场景**:
- 💡 新增"场景6：注意力机制Bot"配置示例
- 💡 适用于需要Bot专注单一对话的场景

---

### v1.0.0 (2025-10-28)

**🎉 初始版本发布**

**核心功能**:
- ✅ AI读空气判断（两层过滤机制）
- ✅ 动态概率调整（回复后自动提升）
- ✅ 智能缓存系统（避免上下文断裂）
- ✅ 官方历史同步（自动保存到conversation表）
- ✅ @消息优先处理（跳过判断直接回复）

**增强功能**:
- ✅ 消息元数据（时间戳+发送者信息）
- ✅ 图片处理（转文字/多模态/应用范围可选）
- ✅ 上下文管理（灵活配置历史数量）
- ✅ 记忆植入（支持LivingMemory和Legacy双模式，v1.1.2增强）
- ✅ 工具提醒（自动提示可用工具）
- ✅ 触发关键词（特定词直接回复）
- ✅ 黑名单关键词（过滤不想处理的消息）

**技术特性**:
- ✅ 最大兼容性设计（仅监听不拦截）
- ✅ 完善的错误处理（30秒超时保护）
- ✅ 详细的调试日志（可追踪完整流程）
- ✅ 线程安全（并发处理支持）
- ✅ 智能去重（缓存转正时自动去重）

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
