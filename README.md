# 群聊增强插件 (Group Chat Plus)

<div align="center">

[![Version](https://img.shields.io/badge/version-v1.0.2-blue.svg)](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.0.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)

一个以 **AI读空气** 为核心的群聊增强插件，让你的Bot更懂氛围、更自然地参与群聊互动

[功能特性](#-功能特性) • [安装方法](#-安装方法) • [配置指南](#-配置指南) • [工作原理](#-工作原理) • [常见问题](#-常见问题)

</div>

---

## 本插件的开发从以下开源项目中获得了灵感，特此感谢。我们并未直接使用其代码，但借鉴了其优秀的功能设计：

- 项目名称：astrbot_plugin_SpectreCore
- 项目仓库地址：https://github.com/23q3/astrbot_plugin_SpectreCore
- 项目作者：23q3

- 项目名称：MaiBot
- 项目仓库地址：https://github.com/MaiM-with-u/MaiBot
- 项目作者：Mai.To.The.Gate 组织及众多贡献者


## 本插件开发的记忆系统借用strbot_plugin_play_sy(又名：ai_memory)，优秀的记忆插件搭配让AI的判断和回复更加智能，特此感谢：

- 项目名称：strbot_plugin_play_sy
- 项目仓库地址：https://github.com/kjqwer/strbot_plugin_play_sy
- 项目作者：kjqwdw


## 📖 插件简介

在群聊场景中，Bot需要像真人一样"读懂气氛"——既不能过于活跃导致刷屏，也不能完全沉默失去存在感。本插件通过**AI智能判断**、**动态概率调整**和**智能缓存机制**，让Bot实现真正的"读空气"能力。

### 🎯 核心优势

- **🧠 AI读空气** - 通过专门的AI判断是否应该回复当前消息
- **📈 动态概率** - 回复后自动提升触发概率，促进连续对话
- **🎯 注意力机制** - 像真人一样专注对话，避免频繁切换话题（v1.0.1新增）
- **✍️ 打字错误** - 自动添加少量自然的错别字，让回复更真实（v1.0.2新增）
- **😊 情绪系统** - AI根据对话产生情绪变化，影响回复语气（v1.0.2新增）
- **⏱️ 延迟模拟** - 模拟真人打字速度，避免秒回（v1.0.2新增）
- **📊 频率调整** - 自动分析发言频率并动态调整概率（v1.0.2新增）
- **💾 智能缓存** - 保存未回复消息的上下文，避免记忆断裂
- **💬 会话隔离** - 每个会话的所有功能数据等完全隔离，每个会话不会互相污染和干扰
- **🔄 官方同步** - 自动同步到AstrBot官方对话系统
- **🤝 最大兼容** - 仅监听消息不拦截，不影响其他插件

---

## ✨ 功能特性

### 核心功能

| 功能 | 说明 | 优势 |
|------|------|------|
| **AI读空气判断** | 两层过滤机制：概率筛选 + AI智能判断 | 精准控制回复时机，避免过度活跃 |
| **动态概率调整** | AI回复后自动提升触发概率 | 促进连续对话，营造自然互动 |
| **注意力机制** | 回复某用户后持续关注ta的发言（v1.0.1新增） | 像真人一样专注对话，避免频繁切换话题 |
| **智能缓存系统** | 保存"通过筛选但未回复"的消息 | 下次回复时保持完整上下文 |
| **官方历史同步** | 自动保存到AstrBot对话系统 | 与官方功能完美集成 |
| **@消息优先** | @消息跳过所有判断直接回复 | 确保重要消息不遗漏 |

### 真实性增强功能（v1.0.2 新增）

| 功能 | 说明 | 优势 |
|------|------|------|
| **打字错误生成** | 2%概率添加自然的拼音相似错别字 | 避免过于完美，增加真实感 |
| **情绪追踪系统** | 根据对话检测并维护情绪状态 | 回复更有感情，更像真人 |
| **回复延迟模拟** | 基于文本长度模拟打字速度 | 避免秒回，营造真实感 |
| **频率动态调整** | AI自动分析并调整发言频率 | 自适应群聊节奏，更自然 |

### 增强功能

<details>
<summary><b>📝 消息元数据增强</b></summary>

- **时间戳信息**: 为消息添加发送时间（年月日时分秒）
- **发送者信息**: 添加发送者ID和昵称
- 帮助AI更好理解对话场景和时间关系
</details>

<details>
<summary><b>🖼️ 图片处理支持</b></summary>

- **三种处理模式**:
  - 模式1: 禁用图片（过滤图片消息）
  - 模式2: 多模态AI直接处理图片
  - 模式3: AI图片转文字 → 文本描述
- **应用范围可选**: 全部消息 / 仅@消息
- **图片描述缓存**: 自动保存图片描述到上下文
</details>

<details>
<summary><b>🔗 上下文管理</b></summary>

- 灵活配置历史消息数量（0 / 正数 / -1不限制）
- 自动合并缓存消息，避免上下文断裂
- 智能去重，防止重复保存
- 自动清理过期缓存（30分钟）
</details>

<details>
<summary><b>🧩 高级集成</b></summary>

- **记忆植入**: 强制调用 `strbot_plugin_play_sy` 长期记忆插件
- **工具提醒**: 自动提示AI当前可用的所有工具
- **触发关键词**: 配置特定关键词跳过判断直接回复
- **黑名单关键词**: 过滤不想处理的消息
</details>

<details>
<summary><b>🎭 真实性增强（v1.0.2 新增）</b></summary>

- **打字错误生成器**: 
  - 基于拼音相似性自动添加错别字
  - 智能跳过代码、链接等特殊内容
  - 可配置错误率（默认2%）和触发概率
- **情绪追踪系统**:
  - 支持多种情绪类型（开心、难过、生气、惊讶等）
  - 情绪会影响AI回复的语气和内容
  - 自动衰减机制（5分钟后恢复平静）
- **回复延迟模拟**:
  - 模拟真人打字速度（可配置字/秒）
  - 添加随机波动更自然
  - 可配置最大延迟时间
- **频率动态调整**:
  - 定期分析发言频率（可配置间隔）
  - AI自动判断并调整回复概率
  - 自适应不同群聊的活跃度
</details>

---

## 🚀 安装方法

### 直接下载

1. 下载整个 `astrbot_plugin_group_chat_plus` 文件夹
2. 将文件夹放入AstrBot的 `/data/plugins` 目录下
3. 重启AstrBot
4. 在AstrBot插件管理面板中找到插件并配置

### 📦 安装依赖

**v1.0.2 开始新增的依赖**：本插件需要 `pypinyin` 库（用于打字错误生成）

```bash
# 进入插件目录
cd astrbot_plugin_group_chat_plus

# 安装依赖
pip install -r requirements.txt
```

或手动安装：
```bash
pip install pypinyin
```

### 依赖要求

- **必需**: AstrBot >= v4.0.0
- **必需**: `pypinyin >= 0.44.0` （v1.0.2开始新增的打字错误生成器需要）
- **可选**: `strbot_plugin_play_sy` （记忆植入功能需要）

---

## ⚙️ 配置指南

### 快速开始配置

如果你是第一次使用，推荐使用以下配置快速开始：

**方案1: 传统动态概率模式**
```json
{
  "initial_probability": 0.3,
  "after_reply_probability": 0.8,
  "probability_duration": 120,
  "decision_ai_timeout": 30,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "enabled_groups": []
}
```

**方案2: 增强注意力机制模式（v1.0.2升级，推荐）**
```json
{
  "initial_probability": 0.1,
  "after_reply_probability": 0.1,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "attention_duration": 120,
  "attention_max_tracked_users": 10,
  "attention_decay_halflife": 300,
  "emotion_decay_halflife": 600,
  "enable_emotion_system": true,
  "attention_boost_step": 0.4,
  "attention_decrease_step": 0.1,
  "emotion_boost_step": 0.1,
  "decision_ai_timeout": 30,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "enabled_groups": []
}
```

**方案3: 真实感增强模式（v1.0.2全功能，最推荐）**
```json
{
  "initial_probability": 0.1,
  "after_reply_probability": 0.1,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "attention_duration": 120,
  "attention_max_tracked_users": 10,
  "attention_decay_halflife": 300,
  "emotion_decay_halflife": 600,
  "enable_emotion_system": true,
  "attention_boost_step": 0.4,
  "attention_decrease_step": 0.1,
  "emotion_boost_step": 0.1,
  "enable_typo_generator": true,
  "typo_error_rate": 0.02,
  "enable_mood_system": true,
  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "decision_ai_timeout": 30,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "enabled_groups": []
}
```

> 💡 **配置建议**: 
> - 方案1：传统模式，灵活简单
> - 方案2：增强注意力机制，多用户追踪+情绪系统（v1.0.2升级）
> - 方案3：真实感增强，最接近真人（v1.0.2全功能推荐）

### 详细配置说明

#### 📊 概率控制（核心配置）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_probability` | float | 0.3 | **初始读空气概率**<br>AI初始判断是否回复消息的概率，范围0.0-1.0<br>示例: 0.1=10%概率触发 |
| `after_reply_probability` | float | 0.8 | **回复后概率**<br>AI回复后临时提升的概率，促进连续对话<br>建议: 设置为0.7-0.9<br>⚠️ 注意：启用注意力机制后此项将被覆盖 |
| `probability_duration` | int | 120 | **概率提升持续时间（秒）**<br>提升概率的持续时间，超时后恢复初始概率<br>建议: 120-600秒 |

> 💡 **概率调整建议**:
> - 轻度活跃: `0.05` → `0.6` (持续180秒)
> - 中度活跃: `0.1` → `0.8` (持续300秒)
> - 高度活跃: `0.3` → `0.95` (持续600秒)

#### 🎯 增强注意力机制（v1.0.1 新增，v1.0.2 增强）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_mechanism` | bool | false | **启用增强注意力机制** ⭐ 已升级<br>开启后，AI会智能追踪多个用户的注意力和情绪态度<br>✨ 多用户同时追踪、渐进式概率调整、情绪系统、指数衰减<br>⚠️ 开启后会替换掉原来的传统概率提升模式，启用后建议将 `after_reply_probability` 设为与 `initial_probability` 相同 |
| `attention_increased_probability` | float | 0.9 | **注意力提升参考值** ⭐ 已升级<br>作为最大提升概率的参考值，实际会根据注意力分数(0-1)渐进式计算<br>不再是固定值，更自然的概率变化<br>建议: 0.9 |
| `attention_decreased_probability` | float | 0.1 | **注意力降低参考值** ⭐ 已升级<br>作为最低概率的参考值，注意力很低或情绪负面时会降到此值附近<br>建议: 0.05-0.15 |
| `attention_duration` | int | 120 | **注意力数据清理周期（秒）** ⭐ 已升级<br>超过此时间×3未互动的用户会被清理<br>注意力会按指数衰减（半衰期5分钟），不再突然清零<br>建议: 120-300秒 |
| `attention_max_tracked_users` | int | 10 | **最大追踪用户数** 🆕 v1.0.2<br>每个群聊最多同时追踪多少个用户的注意力和情绪<br>超过后会移除注意力最低的用户<br>建议: 5-15 |
| `attention_decay_halflife` | int | 300 | **注意力衰减半衰期（秒）** 🆕 v1.0.2<br>注意力分数减半所需的时间<br>值越小衰减越快，AI更容易转移注意力<br>建议: 300秒(5分钟) |
| `emotion_decay_halflife` | int | 600 | **情绪衰减半衰期（秒）** 🆕 v1.0.2<br>情绪值减半所需的时间<br>值越小情绪恢复越快<br>建议: 600秒(10分钟) |
| `enable_emotion_system` | bool | true | **启用情绪态度系统** 🆕 v1.0.2<br>开启后，AI会对每个用户维护情绪态度（-1负面到+1正面）<br>负面情绪会降低回复概率，正面情绪会提升<br>情绪随时间自动恢复中性<br>需要同时启用注意力机制 |
| `attention_boost_step` | float | 0.4 | **被回复用户注意力增加幅度** 🆕 v1.0.2<br>每次回复某用户后，该用户的注意力分数增加多少（范围0-1）<br>值越大，AI对该用户的关注提升越快<br>建议: 0.2-0.5 |
| `attention_decrease_step` | float | 0.1 | **其他用户注意力减少幅度** 🆕 v1.0.2<br>回复某用户后，其他用户的注意力分数减少多少（范围0-1）<br>值越大，AI注意力转移越明显<br>建议: 0.05-0.15 |
| `emotion_boost_step` | float | 0.1 | **被回复用户情绪增加幅度** 🆕 v1.0.2<br>每次回复某用户后，该用户的情绪值增加多少（范围0-1）<br>值越大，情绪变化越快<br>建议: 0.05-0.2 |

> 💡 **注意力机制增强说明**:
> 
> **v1.0.2 升级内容**：
> - ✨ **多用户追踪**: 同时追踪最多10个用户（可配置），不再只记录1个
> - ✨ **渐进式调整**: 概率根据注意力分数(0-1)平滑计算，不再0.9/0.1跳变
> - ✨ **情绪态度系统**: 对每个用户维护情绪值（-1到+1），影响回复倾向
> - ✨ **指数衰减**: 注意力随时间自然衰减（半衰期5分钟），不突然清零
> - ✨ **智能清理**: 自动清理长时间未互动且注意力低的用户，新用户能顶替
> - ✨ **数据持久化**: 保存到 `data/plugin_data/chat_plus/attention_data.json`，重启不丢失
> 
> **工作原理**：
> - Bot回复用户A后，A的注意力分数提升（默认 +0.4，可通过 `attention_boost_step` 配置）
> - 其他用户的注意力轻微降低（默认 -0.1，可通过 `attention_decrease_step` 配置）
> - 被回复用户的情绪值提升（默认 +0.1，可通过 `emotion_boost_step` 配置）
> - 概率计算：`基础概率 × (1 + 注意力分数 × 提升幅度) × (1 + 情绪值 × 0.3)`
> - 5分钟后注意力自然衰减到50%，10分钟后25%，永不突然归零
> - 30分钟未互动 + 注意力<0.05 → 自动清理，释放名额
> 
> **适用场景**：
> - 希望Bot与多个用户同时保持关注，而非只盯着一个人
> - 希望概率变化更平滑自然，而非跳变
> - 希望情绪影响对话（正面情绪提升，负面情绪降低）
> - 希望数据持久化，重启后保留注意力状态
> 
> **示例配置**（活跃群聊）：
> ```json
> {
>   "enable_attention_mechanism": true,
>   "attention_increased_probability": 0.9,
>   "attention_decreased_probability": 0.05,
>   "attention_max_tracked_users": 15,
>   "attention_decay_halflife": 300,
>   "emotion_decay_halflife": 600,
>   "enable_emotion_system": true,
>   "attention_boost_step": 0.4,
>   "attention_decrease_step": 0.1,
>   "emotion_boost_step": 0.1
> }
> ```

#### 🤖 AI提供商配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `decision_ai_provider_id` | string | "" | **读空气AI提供商ID**<br>用于判断是否回复的AI，留空使用默认<br>建议: 使用轻量快速的模型 |
| `decision_ai_extra_prompt` | string | "" | **读空气AI额外提示词**<br>自定义判断逻辑，留空使用默认积极模式 |
| `decision_ai_prompt_mode` | string | "append" | **读空气AI提示词模式**<br>• `append`: 拼接在默认系统提示词后面<br>• `override`: 完全覆盖默认系统提示词（需填写额外提示词） |
| `decision_ai_timeout` | int | 30 | **读空气AI超时时间（秒）**<br>AI判断的超时时间，超时将默认不回复<br>• 快速AI: 20-30秒<br>• 较慢AI: 40-60秒 |
| `reply_ai_extra_prompt` | string | "" | **回复AI额外提示词**<br>自定义回复风格 |
| `reply_ai_prompt_mode` | string | "append" | **回复AI提示词模式**<br>• `append`: 拼接在默认系统提示词后面<br>• `override`: 完全覆盖默认系统提示词（需填写额外提示词） |

#### 📝 消息元数据

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `include_timestamp` | bool | true | **包含时间戳**<br>为消息添加发送时间（格式：2025年01月27日 15:30:45） |
| `include_sender_info` | bool | true | **包含发送者信息**<br>添加发送者ID和昵称（格式：[发送者: 张三(ID: 123456)]） |

#### 🗂️ 上下文配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_context_messages` | int | -1 | **最大上下文消息数**<br>• `-1`: 不限制（推荐）<br>• `正数`: 限制数量<br>• `0`: 不获取历史 |

#### 🖼️ 图片处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_image_processing` | bool | false | **允许处理图片**<br>开启后可处理包含图片的消息 |
| `image_to_text_scope` | string | "all" | **图片转文字应用范围**<br>• `all`: 对所有消息适用<br>• `mention_only`: 仅@消息（推荐，节省API） |
| `image_to_text_provider_id` | string | "" | **图片转文字AI提供商ID**<br>留空则使用多模态AI直接处理图片 |
| `image_to_text_prompt` | string | "请详细描述这张图片的内容" | **图片转文字提示词** |
| `image_to_text_timeout` | int | 60 | **图片转文字超时时间（秒）**<br>AI调用超时时间，根据提供商速度调整<br>• 快速API: 30-60秒<br>• 本地模型: 90-120秒 |

> ⚠️ **图片处理注意**:
> - 留空 `image_to_text_provider_id` 需要确保默认AI支持多模态
> - 建议将 `image_to_text_scope` 设为 `mention_only` 避免频繁调用API
> - 图片描述会自动保存到缓存，下次回复时保持上下文
> - 如果出现图片转文字超时，请适当增加 `image_to_text_timeout` 值

#### 🧩 高级功能

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_memory_injection` | bool | false | **启用强制记忆植入**<br>强制调用 `strbot_plugin_play_sy` 插件获取长期记忆<br>⚠️ 需要先安装记忆插件 |
| `enable_tools_reminder` | bool | false | **启用工具提醒**<br>自动提示AI当前可用的所有工具 |

#### 🔑 关键词配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trigger_keywords` | list | [] | **触发关键词列表**<br>包含这些关键词时跳过读空气判断，直接回复<br>示例: `["帮助", "查询", "天气"]` |
| `blacklist_keywords` | list | [] | **黑名单关键词列表**<br>包含这些关键词时直接忽略消息<br>示例: `["广告", "推广"]` |

#### 🎯 启用范围

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled_groups` | list | [] | **启用的群组列表**<br>• `[]`: 所有群聊启用（推荐测试）<br>• `["群号1", "群号2"]`: 仅指定群启用（推荐生产）<br>⚠️ 本插件仅支持群聊，不处理私聊 |

#### 🎭 真实性增强配置（v1.0.2 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_typo_generator` | bool | true | **启用打字错误生成器**<br>为AI回复添加少量自然的错别字 |
| `typo_error_rate` | float | 0.02 | **单字错误概率**<br>每个字产生错误的概率（2%=每50字约1个错字） |
| `enable_mood_system` | bool | true | **启用情绪系统**<br>AI根据对话产生情绪变化，影响回复语气 |
| `enable_typing_simulator` | bool | true | **启用回复延迟模拟**<br>模拟真人打字速度，避免秒回 |
| `typing_speed` | float | 15.0 | **打字速度（字/秒）**<br>模拟打字的速度，用于计算延迟时间<br>建议: 10-20字/秒 |
| `typing_max_delay` | float | 3.0 | **最大延迟时间（秒）**<br>回复延迟的上限，避免等待过久 |
| `enable_frequency_adjuster` | bool | true | **启用频率动态调整**<br>AI自动分析发言频率并调整概率 |
| `frequency_check_interval` | int | 180 | **频率检查间隔（秒）**<br>多久分析一次发言频率<br>建议: 180-300秒 |

> 💡 **真实性增强说明**:
> - 所有功能默认启用，经过调优，开箱即用
> - 打字错误率2%表示平均每50字出现1个错字，非常自然
> - 情绪系统会在检测到情绪关键词后维护5分钟，然后自动衰减
> - 延迟模拟基于文本长度计算，短消息快速回复，长消息延迟更久
> - 频率调整会消耗额外的AI调用（每3分钟一次），注意API成本
> - 如需关闭所有新功能恢复v1.0.1体验，将所有enable开关设为false

#### 🐛 调试配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_debug_log` | bool | false | **启用详细日志**<br>输出详细的调试信息，便于排查问题 |

---

## 🔧 工作原理

### 完整处理流程

```
📨 收到群消息
    ↓
【步骤1】基础检查
    ├─ 检查群组是否启用
    ├─ 检查是否bot自己的消息
    └─ ✅ 通过 → 继续
    ↓
【步骤2】黑名单关键词检查
    ├─ 包含黑名单关键词？
    └─ ❌ 是 → 丢弃消息
    └─ ✅ 否 → 继续
    ↓
【v1.0.2】记录消息（用于频率统计）
    └─ 频率调整器记录消息计数
    ↓
【步骤3】@消息检测
    ├─ 是否@机器人？
    └─ 记录状态 → 继续
    ↓
【步骤4】触发关键词检查
    ├─ 包含触发关键词？
    └─ 记录状态 → 继续
    ↓
【步骤5】读空气概率判断（含增强注意力机制）
    ├─ 是@消息或触发关键词？
    │   └─ ✅ 是 → 跳过概率判断
    └─ ❌ 否 → 开始概率判断
        ├─ 获取当前概率（initial_probability或after_reply_probability）
        ├─ 启用注意力机制（v1.0.2增强）？
        │   └─ ✅ 是 → 应用增强注意力调整
        │       ├─ 从持久化数据加载用户档案（多用户）
        │       ├─ 应用时间衰减（指数衰减，半衰期5分钟）
        │       ├─ 清理长时间未互动用户（30分钟+注意力<0.05）
        │       ├─ 获取当前用户的注意力分数(0-1)和情绪值(-1到1)
        │       ├─ 渐进式概率计算：
        │       │   └─ 调整概率 = 基础概率 × (1 + 注意力分数 × 提升幅度) × (1 + 情绪值 × 0.3)
        │       ├─ 注意力分数高（>0.1）→ 概率提升（渐进式）
        │       └─ 注意力分数低（<0.1）→ 概率轻微降低
        ├─ 随机值 < 调整后概率？
        └─ ❌ 否 → 丢弃消息
        └─ ✅ 是 → 继续
    ↓
【步骤6】提取纯净原始消息
    ├─ 使用MessageCleaner提取不含元数据的原始消息
    ├─ 检查是否是空@消息（纯@无其他内容）
    └─ ✅ 提取完成 → 继续
    ↓
【步骤6.5】处理图片内容（在缓存之前）
    ├─ mention_only模式检查
    │   └─ 非@消息的图片 → 丢弃（不缓存）
    ├─ 未启用图片处理？
    │   └─ 纯图片消息 → 丢弃
    │   └─ 图文消息 → 移除图片
    ├─ 配置了图片转文字AI？
    │   └─ ✅ 是 → 调用AI转为文字描述
    │       ├─ 使用配置的超时时间（image_to_text_timeout）
    │       ├─ 转换成功 → 图片描述替换图片内容
    │       └─ 超时或失败 → 降级处理（移除图片或丢弃）
    └─ 否 → 使用多模态AI直接处理（保留图片）
    ↓
【步骤7】缓存处理后的用户消息（不含元数据）
    ├─ 只缓存处理后的纯净消息（不含元数据）
    ├─ 如有图片描述，已包含在消息内容中
    ├─ 添加到pending_messages_cache
    ├─ 保存发送者ID、名字、时间戳（用于后续添加元数据）
    ├─ 清理超过30分钟的旧消息
    └─ 限制缓存最多10条
    ↓
【步骤7.5】为当前消息添加元数据（用于发送给AI）
    ├─ 使用处理后的消息（图片已处理）
    ├─ 添加时间戳（可选，格式：2025年01月27日 15:30:45）
    ├─ 添加发送者信息（可选，格式：[发送者: 张三(ID: 123456)]）
    └─ ✅ 元数据添加完成（仅用于AI识别，不影响缓存）
    ↓
【步骤8】提取历史上下文
    ├─ 从官方存储读取历史消息
    ├─ 合并缓存中的消息（去重）
    ├─ 应用max_context_messages限制
    └─ 格式化为AI可读文本
    ↓
【步骤9】决策AI判断
    ├─ 是@消息或触发关键词？
    │   └─ ✅ 是 → 跳过决策AI
    │       └─ 如果是@消息，检查是否已被其他插件处理
    └─ ❌ 否 → 调用决策AI
        ├─ 构建完整提示词（含人格+上下文）
        ├─ 调用AI判断（使用配置的超时时间 decision_ai_timeout）
        └─ 解析yes/no结果
            ├─ 超时 → 默认不回复，保存消息到自定义存储，退出
            ├─ ❌ no → 保存消息到自定义存储（含元数据），退出
            └─ ✅ yes → 继续
    ↓
【步骤10】标记会话
    └─ 添加到processing_sessions（用于after_message_sent识别）
    ↓
【步骤11】注入记忆（可选）
    ├─ 启用记忆植入？
    └─ ✅ 是 → 检查记忆插件可用性
        └─ 调用 strbot_plugin_play_sy 获取记忆
        └─ 注入到消息中
    ↓
【步骤12】注入工具信息（可选）
    ├─ 启用工具提醒？
    └─ ✅ 是 → 获取可用工具列表
        └─ 注入到消息中
    ↓
【步骤12.5】注入情绪状态（v1.0.2 新增）
    ├─ 启用情绪系统？
    └─ ✅ 是 → 根据最近对话更新情绪
        ├─ 检测情绪关键词（开心、难过、生气等）
        ├─ 更新情绪状态和强度
        ├─ 检查情绪衰减（5分钟后回归平静）
        └─ 注入情绪提示词到prompt（如：[当前情绪状态: 你感到开心]）
    ↓
【步骤13】调用AI生成回复
    ├─ 构建完整消息（上下文+情绪+记忆+工具+额外提示词）
    ├─ 调用默认AI生成回复
    └─ ✅ 生成回复
    ↓
【步骤13.5】添加打字错误（v1.0.2 新增）
    ├─ 启用打字错误生成器？
    └─ ✅ 是 → 处理回复文本
        ├─ 检查是否应添加错字（长度、格式判断）
        │   ├─ 太短（<10字）→ 跳过
        │   ├─ 包含代码/链接/特殊格式 → 跳过
        │   └─ 30%概率触发
        ├─ 提取汉字位置
        ├─ 按2%概率为每个字生成错误
        └─ 使用拼音相似字替换（如：的→得、在→再）
    ↓
【步骤13.6】模拟打字延迟（v1.0.2 新增）
    ├─ 启用回复延迟模拟？
    └─ ✅ 是 → 计算并执行延迟
        ├─ 判断是否应该延迟
        │   ├─ 太短（≤3字）→ 快速回复
        │   └─ 包含特殊标记 → 不延迟
        ├─ 基础延迟 = 文本长度 / 打字速度（默认15字/秒）
        ├─ 添加随机波动（±30%）
        ├─ 限制在合理范围（0.5-3.0秒）
        └─ 等待延迟后继续
    ↓
【步骤14】保存用户消息到自定义存储
    ├─ 从缓存读取处理后的消息内容（不含元数据）
    ├─ 使用缓存中的发送者信息添加元数据
    ├─ 保存到自定义历史存储（data/chat_history/）
    └─ ✅ 保存完成
    ↓
【步骤15】发送回复
    └─ yield 返回回复内容给用户
    ↓
【步骤15（并行）】调整读空气概率 / 记录注意力（v1.0.2增强）
    ├─ 启用注意力机制？
    │   └─ ✅ 是 → 记录被回复的用户（增强版）
    │       ├─ 提升该用户注意力分数（默认+0.4，可配置attention_boost_step，叠加式，最高1.0）
    │       ├─ 提升该用户情绪值（默认+0.1，可配置emotion_boost_step，正面交互）
    │       ├─ 更新互动次数、时间戳、消息预览
    │       ├─ 降低其他用户注意力（默认-0.1，可配置attention_decrease_step，轻微）
    │       ├─ 清理不活跃用户（30分钟+注意力<0.05）
    │       ├─ 限制追踪用户数（最多10个，移除优先级最低的）
    │       └─ 自动保存到磁盘（60秒间隔，data/plugin_data/chat_plus/attention_data.json）
    └─ ❌ 否 → 提升概率至after_reply_probability
        └─ 持续probability_duration秒后恢复initial_probability
    ↓
【步骤16】检查并调整发言频率（v1.0.2 新增）
    ├─ 启用频率动态调整？
    └─ ✅ 是 → 检查是否到达检查间隔
        ├─ 条件1: 距离上次检查 > frequency_check_interval（默认180秒）
        ├─ 条件2: 消息数量 >= 8条
        └─ ✅ 满足条件 → 启动频率分析
            ├─ 收集最近10条对话记录
            ├─ 调用AI判断发言频率（正常/过于频繁/过少）
            ├─ 根据判断调整概率
            │   ├─ 过于频繁 → 降低15%（×0.85）
            │   ├─ 过少 → 提升15%（×1.15）
            │   └─ 正常 → 保持不变
            ├─ 限制概率范围（0.05-0.95）
            └─ 更新检查状态，重置计数器
    ↓
【after_message_sent钩子】（在回复发送后自动触发）
    ├─ 检查是否本插件处理的会话（通过processing_sessions标记）
    ├─ 清除会话标记
    ├─ 检查result是否为LLM结果
    ├─ 提取AI回复文本
    ├─ 从缓存获取用户消息
    │   ├─ 读取缓存中的原始消息（不含元数据）
    │   └─ 使用缓存中的发送者信息添加元数据
    ├─ 准备待转正的缓存消息（除最后一条外的所有缓存）
    │   ├─ 遍历每条缓存消息
    │   ├─ 使用各自的发送者信息添加元数据
    │   └─ 构建转正列表
    ├─ 保存到官方对话系统（conversation表）
    │   ├─ 合并缓存消息（带元数据）
    │   ├─ 智能去重（与现有官方历史比对）
    │   ├─ 保存：缓存消息 + 当前用户消息 + AI回复
    │   └─ 验证保存成功
    └─ ✅ 成功 → 清空pending_messages_cache
    └─ ❌ 失败 → 保留缓存（待下次使用或清理）
    ↓
✅ 完成
```

### 智能缓存机制

插件采用独特的**缓存+转正**机制，避免上下文断裂：

```
场景1: AI决定回复
    用户消息A → 缓存 → AI回复 → 缓存转正 → 保存到官方系统 → 清空缓存

场景2: AI决定不回复
    用户消息A → 缓存 → AI不回复 → 保存到自定义存储（不清空缓存）
    用户消息B → 缓存 → AI回复 → 缓存转正（含A+B） → 保存到官方系统 → 清空缓存

结果: 官方对话系统中包含完整的上下文（A+B+回复），没有丢失A！
```

#### 缓存特性：

- **自动清理**: 超过30分钟的消息自动移除
- **容量限制**: 最多保留10条消息
- **图片描述保存**: 图片转文字的描述也保存在缓存中
- **智能去重**: 转正时自动过滤重复消息
- **线程安全**: 多会话并发处理安全

### @消息优先机制

```
@消息处理流程:
    检测到@机器人
        ↓
    跳过概率判断（必定处理）
        ↓
    跳过决策AI判断（必定回复）
        ↓
    检查其他插件是否已回复
        ├─ 已回复 → 退出（避免重复）
        └─ 未回复 → 继续处理
```

---

## 🎨 使用场景与配置推荐

### 场景1: 话痨型Bot（高度活跃）

**适用**: 娱乐群、游戏群、小规模测试群

```json
{
  "initial_probability": 0.4,
  "after_reply_probability": 0.95,
  "probability_duration": 600,
  "max_context_messages": 30,
  "decision_ai_extra_prompt": "你是一个活泼开朗、喜欢聊天的角色。在大部分情况下都应该积极参与讨论。"
}
```

### 场景2: 平衡型Bot（中度活跃）

**适用**: 技术群、学习群、日常交流群

```json
{
  "initial_probability": 0.1,
  "after_reply_probability": 0.8,
  "probability_duration": 300,
  "max_context_messages": 20,
  "decision_ai_extra_prompt": "你是一个友好的助手，在有价值的讨论中参与，避免打断私人对话。"
}
```

### 场景3: 沉稳型Bot（轻度活跃）

**适用**: 工作群、正式群、大规模群

```json
{
  "initial_probability": 0.05,
  "after_reply_probability": 0.6,
  "probability_duration": 180,
  "max_context_messages": 10,
  "decision_ai_extra_prompt": "你是一个专业、谨慎的助手，只在明确需要你帮助或回答问题时才回复。"
}
```

### 场景4: 图片处理Bot

**适用**: 需要理解图片内容的群

```json
{
  "enable_image_processing": true,
  "image_to_text_scope": "mention_only",
  "image_to_text_provider_id": "your_vision_ai_id",
  "image_to_text_prompt": "请详细描述这张图片的内容，包括主要物体、场景、文字等信息",
  "initial_probability": 0.2
}
```

### 场景5: 关键词触发Bot

**适用**: 客服群、工具群

```json
{
  "trigger_keywords": ["帮助", "help", "查询", "查看", "指令"],
  "blacklist_keywords": ["广告", "推广", "加群"],
  "initial_probability": 0.05,
  "enabled_groups": ["123456789", "987654321"]
}
```

### 场景6: 注意力机制Bot（v1.0.1 新增）

**适用**: 希望Bot像真人一样"专注对话"的场景

```json
{
  "initial_probability": 0.1,
  "after_reply_probability": 0.1,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "attention_duration": 120,
  "decision_ai_extra_prompt": "你是一个专注的对话者，倾向于与一个人深入交流，而不是频繁切换话题。"
}
```

**说明**: 
- 启用后，Bot回复某人后会持续关注ta的发言（0.9高概率回复）
- 其他人插话时概率降低到0.05，避免频繁切换对话对象
- 实现更自然的"一对一"对话体验
- 注意：建议将 `after_reply_probability` 设为与 `initial_probability` 相同

### 场景7: 真实感增强Bot（v1.0.2 新增，强烈推荐）

**适用**: 希望Bot表现得最接近真人的场景

```json
{
  "initial_probability": 0.15,
  "after_reply_probability": 0.15,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "attention_duration": 120,
  "enable_typo_generator": true,
  "typo_error_rate": 0.02,
  "enable_mood_system": true,
  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "decision_ai_extra_prompt": "你是一个真实的人类，会有情绪波动，偶尔打错字，说话时需要思考时间。根据心情和话题参与讨论，保持自然真实的表现。"
}
```

**说明**: 
- 结合注意力机制，让对话更专注
- 启用打字错误，2%错误率非常自然
- 启用情绪系统，回复更有感情
- 启用延迟模拟，避免秒回
- 启用频率调整，自适应群聊节奏
- 这是最接近真人表现的配置组合

---

## 💡 提示词定制

### 决策AI提示词示例

#### 积极参与型
```
你是一个热情友好的群聊成员，喜欢参与讨论。

应该回复的情况：
- 话题与你感兴趣的领域相关（动漫、游戏、科技、编程等）
- 有人提问或寻求帮助
- 讨论内容与你之前的发言相关
- 可以提供有价值的信息或观点
- 群聊气氛活跃，适合互动

不应该回复的情况：
- 明显是他人的私密对话
- 只是简单的寒暄（早、晚安、吃饭了吗等）
- 纯表情或无意义内容
- 重复或已解决的问题

不确定时倾向于回复，保持群聊活跃。
```

#### 专业助手型
```
你是一个专业的技术助手，谨慎判断是否需要参与。

应该回复的情况：
- 直接向你提问
- 讨论技术问题且你有专业见解
- 需要纠正明显的错误信息
- 话题与你的专业领域高度相关

不应该回复的情况：
- 闲聊或娱乐话题
- 他人已给出正确答案
- 私人对话
- 超出你的知识范围

默认保持专业和谨慎，只在必要时发言。
```

#### 角色扮演型
```
你正在扮演一个特定角色：[角色名]
性格特点：[性格描述]
说话风格：[风格描述]

根据你的角色特点判断是否参与对话：
- 符合角色人设的话题积极参与
- 不符合人设的话题保持沉默
- 保持角色的一致性和真实感

示例：
如果你是"技术宅"，对编程、游戏话题感兴趣
如果你是"文学少女"，对书籍、诗词话题感兴趣
```

### 回复AI提示词示例

#### 自然对话型
```
回复要求：
- 保持自然、轻松的对话风格
- 可以适当使用表情和网络用语
- 避免过于正式或生硬
- 回复长度适中，不要过长或过短
- 如果不确定，可以提出问题引导对话
```

#### 简洁专业型
```
回复要求：
- 直接回答问题，简洁明了
- 使用专业术语但确保易懂
- 必要时提供代码示例或链接
- 避免闲聊和无关内容
```

---

## ❓ 常见问题

<details>
<summary><b>Q1: 为什么Bot回复太频繁/太少？</b></summary>

**A**: 这是概率配置问题，请调整：

- **太频繁**: 降低 `initial_probability` 和 `after_reply_probability`
- **太少**: 提高这两个概率值
- 建议从 `0.1` 开始测试，观察效果后逐步调整
- 也可以通过 `decision_ai_extra_prompt` 调整决策AI的判断逻辑
</details>

<details>
<summary><b>Q2: 为什么@消息没有回复？</b></summary>

**A**: 可能的原因：

1. 其他插件已经处理了这条消息（本插件会检测并避免重复回复）
2. 群组未在 `enabled_groups` 列表中
3. 检查日志看是否有错误信息
4. 确认 `enable_debug_log` 开启后查看详细流程
</details>

<details>
<summary><b>Q3: 图片转文字不工作？</b></summary>

**A**: 检查以下配置：

1. `enable_image_processing` 是否为 `true`
2. `image_to_text_provider_id` 是否填写（留空则需多模态AI）
3. 如果留空，确认默认AI支持视觉能力
4. 检查 `image_to_text_scope` 设置（`all` 或 `mention_only`）
5. 查看日志确认是否有API调用错误
</details>

<details>
<summary><b>Q4: 缓存消息会丢失吗？</b></summary>

**A**: 不会丢失，缓存机制确保：

1. 通过筛选但AI未回复的消息会保存到自定义历史
2. 下次AI回复时会一起转正到官方系统
3. 即使30分钟后清理，也已经保存在自定义存储中
4. 缓存只是临时中转，最终都会持久化
</details>

<details>
<summary><b>Q5: 记忆植入功能如何使用？</b></summary>

**A**: 使用步骤：

1. 先安装 `strbot_plugin_play_sy` (AI记忆插件)
2. 配置该插件并确保正常工作
3. 在本插件中设置 `enable_memory_injection` 为 `true`
4. 本插件会自动调用记忆插件获取相关记忆
5. 记忆内容会注入到AI的输入中
</details>

<details>
<summary><b>Q6: 可以在私聊中使用吗？</b></summary>

**A**: **不可以**。本插件设计为群聊专用：

- 私聊消息会直接跳过处理
- 这是因为私聊场景不需要"读空气"
- 私聊建议使用AstrBot官方的对话功能
</details>

<details>
<summary><b>Q7: 如何调试插件问题？</b></summary>

**A**: 调试步骤：

1. 设置 `enable_debug_log` 为 `true`
2. 重启插件或重载插件
3. 发送测试消息
4. 查看日志输出的详细流程（15个步骤）
5. 定位是哪个步骤出现问题
6. 根据日志信息调整配置或排查错误
</details>

<details>
<summary><b>Q8: 会影响其他插件吗？</b></summary>

**A**: **不会**。本插件设计为最大兼容：

- 使用 `@event_message_type` 监听而非拦截
- 不修改event对象
- 不阻断消息传递
- @消息会检测其他插件是否已回复
- 可以与任何其他插件共存
</details>

<details>
<summary><b>Q9: 如何设置仅在特定群启用？</b></summary>

**A**: 配置 `enabled_groups`：

```json
{
  "enabled_groups": ["123456789", "987654321"]
}
```

- 留空 `[]`: 所有群聊启用
- 填写群号: 仅指定群启用
- 群号是字符串格式
- 可以随时添加或移除群号
</details>

<details>
<summary><b>Q10: 决策AI超时怎么办？</b></summary>

**A**: 插件有超时保护机制：

- 超时后默认判定为"不回复"
- 不会卡住或影响其他消息
- 如果经常超时，可以：
  - **调整超时时间**: 增加 `decision_ai_timeout` 配置值（默认30秒）
  - **更换AI模型**: 使用更快的AI提供商
  - **减少上下文**: 降低 `max_context_messages` 减少输入长度
  - **检查网络**: 确认AI服务的响应速度正常
</details>

<details>
<summary><b>Q11: 增强注意力机制是什么？v1.0.2有什么升级？</b></summary>

**A**: 注意力机制让Bot像真人一样"专注对话"，v1.0.2升级为多用户追踪+情绪系统：

**v1.0.2 升级内容**:
- ✨ **多用户追踪**: 同时追踪最多10个用户，不再只记录1个
- ✨ **渐进式调整**: 概率根据注意力分数(0-1)平滑变化，不再0.9/0.1跳变
- ✨ **情绪态度系统**: 对每个用户维护情绪值（-1到+1），影响回复倾向
- ✨ **指数衰减**: 注意力随时间自然衰减（半衰期5分钟），不突然清零
- ✨ **智能清理**: 自动清理长时间未互动且注意力低的用户，新用户能顶替
- ✨ **数据持久化**: 保存到 `data/plugin_data/chat_plus/attention_data.json`，重启不丢失

**工作原理**:
- Bot回复用户A后，A的注意力分数提升（默认 +0.4，可通过 `attention_boost_step` 配置，叠加式，最高1.0）
- 同时轻微降低其他用户注意力（默认 -0.1，可通过 `attention_decrease_step` 配置）
- 正面交互会提升情绪值（默认 +0.1，可通过 `emotion_boost_step` 配置），负面情绪会降低回复概率
- 概率计算：`基础概率 × (1 + 注意力分数 × 提升幅度) × (1 + 情绪值 × 0.3)`
- 5分钟后注意力自然衰减到50%，10分钟后25%，永不突然归零
- 30分钟未互动 + 注意力<0.05 → 自动清理，释放名额给新用户
- **可自定义调整幅度**: 如果觉得注意力变化太剧烈，可以调低 `attention_boost_step` 和 `attention_decrease_step`

**使用方法**:
1. 设置 `enable_attention_mechanism` 为 `true`
2. 配置 `attention_increased_probability`（建议0.9，作为参考最大值）
3. 配置 `attention_decreased_probability`（建议0.05-0.15，作为参考最小值）
4. 配置 `attention_max_tracked_users`（建议10-15，根据群活跃度）
5. 配置 `enable_emotion_system` 为 `true`（启用情绪系统）
6. 【可选】调整注意力变化幅度：
   - `attention_boost_step`（默认0.4，建议0.2-0.5）- 被回复用户注意力增加幅度
   - `attention_decrease_step`（默认0.1，建议0.05-0.15）- 其他用户注意力减少幅度
   - `emotion_boost_step`（默认0.1，建议0.05-0.2）- 情绪增加幅度
   - 如果觉得注意力转移太快/太慢，可以调整这些参数
7. 建议将 `after_reply_probability` 设为与 `initial_probability` 相同

**适用场景**:
- 希望Bot与多个用户同时保持关注，而非只盯着一个人
- 希望概率变化更平滑自然，而非跳变
- 希望情绪影响对话（正面情绪提升，负面情绪降低）
- 希望数据持久化，重启后保留注意力状态
- 活跃群聊，多人同时对话

**注意事项**:
- 启用后会覆盖 `after_reply_probability` 设置
- 数据会自动保存到磁盘（60秒间隔）
- 重启bot后会自动加载历史数据
- 每个群聊的数据完全隔离，不会互相影响

**示例效果**:
```
场景：群聊有用户A、B、C

1. Bot回复用户A
   → A的注意力: 0.0 → 0.4
   → B、C的注意力: 0.0 → 0.0

2. 用户A继续发言（2分钟后）
   → A的注意力: 0.4（衰减后）→ 0.8
   → 概率大幅提升（渐进式）

3. 用户B插话
   → B的注意力: 0.0
   → 概率略微降低（比传统模式自然）

4. Bot回复用户B
   → A的注意力: 0.8 → 0.7（轻微降低）
   → B的注意力: 0.0 → 0.4（提升）
   → 现在同时追踪A和B

5. 30分钟后
   → A的注意力自然衰减到接近0
   → 如果A长时间不发言，会被自动清理
   → 新用户D可以加入追踪
```
</details>

<details>
<summary><b>Q12: 提示词模式 append 和 override 有什么区别？</b></summary>

**A**: 两种模式的区别：

**append 模式（推荐）**:
- 将额外提示词拼接在默认系统提示词后面
- 保留插件的默认判断逻辑
- 只需填写补充说明，可以留空
- 适合大部分场景

**override 模式（高级）**:
- 完全覆盖默认系统提示词
- 需要自己编写完整的提示词
- 不能留空，否则AI无法正常工作
- 适合有特殊需求的高级用户

**使用建议**:
- 默认使用 append 模式
- 只有在完全了解插件工作原理，且需要完全自定义时才使用 override
- override 模式需要编写完整的判断逻辑提示词
</details>

<details>
<summary><b>Q13: 打字错误功能会不会影响代码回复？</b></summary>

**A**: 不会。打字错误生成器有智能过滤：

- 自动跳过代码块（```包围的内容）
- 自动跳过链接（http/https开头）
- 自动跳过特殊格式（如命令、路径等）
- 只对自然语言文本生效
- 错误率2%非常自然，不会影响理解
- 如果担心，可以设置 `enable_typo_generator: false` 关闭
</details>

<details>
<summary><b>Q14: 情绪系统如何工作？会消耗额外token吗？</b></summary>

**A**: 情绪系统工作原理：

**工作机制**:
- 检测消息中的情绪关键词（如"开心"、"生气"、"难过"等）
- 更新群聊的情绪状态
- 在生成回复前注入情绪提示词
- 5分钟后自动衰减回归平静

**token消耗**:
- 只在检测到情绪时添加一小段提示词（约20-30 tokens）
- 相比整体对话，消耗可忽略不计
- 不会额外调用AI接口
- 性能影响极小
</details>

<details>
<summary><b>Q15: 回复延迟会不会让用户等太久？</b></summary>

**A**: 延迟设计合理，不会：

**延迟计算**:
- 基于文本长度：短消息快，长消息慢
- 默认打字速度：15字/秒（正常人类速度）
- 添加随机波动：±30%，更自然
- 最大延迟限制：3秒（可配置）

**实际效果**:
- 10字消息：约0.5-1秒
- 50字消息：约2-4秒（会被限制到3秒）
- 100字消息：约3秒（上限）

**调整建议**:
- 如果觉得太慢：增加 `typing_speed` 或减少 `typing_max_delay`
- 如果想更真实：降低 `typing_speed` 到10-12
</details>

<details>
<summary><b>Q16: 频率动态调整会不会消耗很多API？</b></summary>

**A**: 消耗在可接受范围内：

**消耗情况**:
- 默认每3分钟（180秒）检查一次
- 每次调用消耗约500-1000 tokens（取决于对话历史长度）
- 每小时最多20次调用
- 如果使用便宜的模型（如GPT-3.5），成本几乎可忽略

**节省建议**:
1. 增加检查间隔：设置 `frequency_check_interval` 为300或更高
2. 使用便宜的模型：这个判断不需要高级模型
3. 如果不需要：设置 `enable_frequency_adjuster: false` 关闭

**是否值得**:
- 如果希望Bot自适应群聊节奏：值得开启
- 如果预算紧张或群聊活跃度稳定：可以关闭
</details>

<details>
<summary><b>Q17: 如何从v1.0.1升级到v1.0.2？</b></summary>

**A**: 升级步骤：

1. **安装依赖**：`pip install pypinyin>=0.44.0`
2. **更新插件文件**：替换整个插件文件夹
3. **保留配置**：原有配置完全兼容，无需修改
4. **可选：添加新配置**：在配置中添加v1.0.2的新配置项（不加也能正常运行，使用默认值）
5. **重启插件**：重启AstrBot或重载插件

**注意事项**:
- v1.0.2完全向后兼容v1.0.1
- 所有新功能默认启用，如不需要可单独关闭
- 不会影响现有功能和配置
</details>

---

## 🔍 技术细节

### 模块架构

```
astrbot_plugin_group_chat_plus/
├── main.py                      # 主插件类，事件监听与流程控制
├── metadata.yaml                # 插件元数据
├── _conf_schema.json            # 配置schema定义
├── requirements.txt             # 依赖声明（pypinyin）
└── utils/                       # 工具模块
    ├── __init__.py              # 模块导出
    ├── probability_manager.py   # 概率管理器（动态概率调整）
    ├── attention_manager.py     # 注意力机制管理器（v1.0.1新增）
    ├── message_processor.py     # 消息处理器（元数据添加）
    ├── message_cleaner.py       # 消息清理器（移除不必要的元数据）
    ├── image_handler.py         # 图片处理器（转文字/多模态）
    ├── context_manager.py       # 上下文管理器（历史消息/缓存）
    ├── decision_ai.py           # 决策AI（读空气判断）
    ├── reply_handler.py         # 回复处理器（生成回复）
    ├── memory_injector.py       # 记忆注入器（集成记忆插件）
    ├── tools_reminder.py        # 工具提醒器（提示可用工具）
    ├── keyword_checker.py       # 关键词检查器（触发词/黑名单）
    ├── typo_generator.py        # 打字错误生成器（v1.0.2新增）
    ├── mood_tracker.py          # 情绪追踪系统（v1.0.2新增）
    ├── typing_simulator.py      # 回复延迟模拟器（v1.0.2新增）
    └── frequency_adjuster.py    # 频率动态调整器（v1.0.2新增）
```

### 数据流

```
用户消息 → 黑名单检查 → @/关键词检测 → 注意力机制概率调整
    ↓
概率筛选 → 添加元数据 → 图片处理 → 缓存消息
    ↓
提取历史上下文 ← 合并缓存消息 → 智能去重
    ↓
AI决策判断 → 注入情绪状态 → 注入记忆 → 注入工具信息
    ↓
AI生成回复 → 添加打字错误 → 模拟打字延迟
    ↓
保存用户消息 → 发送回复 → 调整概率/记录注意力
    ↓
更新情绪状态 → 频率动态调整检查
    ↓
【after_message_sent钩子】
    ↓
提取AI回复 → 获取缓存消息 → 添加元数据
    ↓
合并缓存消息 → 智能去重 → 保存到官方系统
    ↓
验证保存 → 清空缓存
    ↓
✅ 完成

【缓存机制数据流】
通过筛选的消息 → 缓存系统（临时存储）
    ↓                           ↓
AI决定回复                  AI决定不回复
    ↓                           ↓
读取缓存添加元数据          保存到自定义存储
    ↓                           ↓
保存到官方系统              保留在缓存中
    ↓                           ↓
清空缓存                    等待下次回复
    ↓                           ↓
✅ 完成                      下次回复时一起转正

【v1.0.2 新增数据流】
情绪检测 → 情绪追踪系统 → 注入到prompt → 影响AI回复 → 自动衰减
频率统计 → 定期AI分析 → 调整概率参数 → 影响下次判断
回复文本 → 打字错误生成器 → 添加错别字 → 增加真实感
回复文本 → 延迟计算器 → 模拟打字延迟 → 避免秒回
```

### 存储结构

#### 插件数据目录（符合 AstrBot 规范）
```
data/
└── plugin_data/
    └── chat_plus/                           # 插件专属数据目录
        ├── chat_history/                    # 历史消息存储
        │   └── {platform_name}/
        │       ├── group/
        │       │   └── {group_id}.json      # 群聊历史
        │       └── private/
        │           └── {user_id}.json       # 私聊历史（预留）
        └── attention_data.json              # 🆕 v1.0.2 注意力数据（持久化）
```

> 💡 **数据目录说明**：
> - 使用 `StarTools.get_data_dir()` 自动获取插件专属目录
> - 保存在 `data/plugin_data/` 下，更新/重装插件时数据不丢失
> - 符合 AstrBot 平台规范

#### 注意力数据结构（v1.0.2 新增）
```json
{
  "aiocqhttp_group_123456": {
    "user_789": {
      "user_id": "789",
      "user_name": "用户A",
      "attention_score": 0.75,
      "emotion": 0.5,
      "last_interaction": 1698765432,
      "interaction_count": 8,
      "last_message_preview": "最后一条消息的预览..."
    },
    "user_456": {
      "user_id": "456",
      "user_name": "用户B",
      "attention_score": 0.3,
      "emotion": -0.2,
      "last_interaction": 1698765000,
      "interaction_count": 3,
      "last_message_preview": "..."
    }
  },
  "aiocqhttp_group_789012": {
    ...
  }
}
```

> 💡 **注意力数据说明**：
> - 每个群聊独立存储（完全隔离）
> - 最多追踪 10 个用户（可配置）
> - 60秒间隔自动保存（避免频繁写磁盘）
> - 重启 bot 后自动加载

#### 缓存结构（内存中）
```python
pending_messages_cache = {
    "chat_id": [
        {
            "role": "user",
            "content": "处理后的消息（不含元数据）",
            "timestamp": 1706347200.0,
            "sender_id": "123456",
            "sender_name": "用户A",
            "message_timestamp": 1706347200.0
        },
        # ... 更多消息（最多10条）
    ]
}
```

---

## 🛠️ 高级用法

### 自定义决策逻辑

通过 `decision_ai_extra_prompt` 可以完全自定义判断逻辑：

```json
{
  "decision_ai_extra_prompt": "判断规则：\n1. 如果消息包含'python'或'代码'，一定回复\n2. 如果是纯表情，不回复\n3. 如果是提问（含'吗'、'?'、'？'），倾向回复\n4. 其他情况根据上下文判断"
}
```

### 多群组差异化配置

虽然插件本身不支持多配置，但可以通过以下方式实现：

1. **方案1**: 部署多个插件实例，每个配置不同的 `enabled_groups`
2. **方案2**: 使用 `decision_ai_extra_prompt` 根据群组特点调整
3. **方案3**: 修改插件代码，支持多配置（需要二次开发）

### 与其他插件联动

#### 与命令插件联动
```json
{
  "blacklist_keywords": ["/", "!"],
  "comment": "过滤命令前缀，避免与命令插件冲突"
}
```

#### 与定时任务联动
```json
{
  "trigger_keywords": ["提醒", "定时"],
  "comment": "关键词触发后可调用定时任务插件"
}
```

---

## 📊 性能与优化

### 性能指标

- **消息处理延迟**: < 2秒（不含AI调用时间）
- **缓存内存占用**: 约10KB/群（10条消息）
- **并发支持**: 多群组并发处理，线程安全
- **历史文件大小**: 约1MB/群/200条消息

### 优化建议

1. **控制上下文数量**: `max_context_messages` 不要设置过大
2. **合理设置概率**: 避免过高的概率导致频繁调用AI
3. **图片处理**: 使用 `mention_only` 减少不必要的API调用
4. **缓存清理**: 默认30分钟清理，无需手动维护
5. **日志管理**: 生产环境关闭 `enable_debug_log`

---

## 📝 更新日志

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
- ✅ 记忆植入（集成ai_memory插件）
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

### 报告问题

如果你遇到Bug或有功能建议，请：

1. 开启 `enable_debug_log` 获取详细日志
2. 在GitHub仓库提交Issue
3. 附上完整的错误信息和配置
4. 描述复现步骤

### 功能建议

欢迎提出新功能建议：

- 描述使用场景
- 说明预期效果
- 附上参考示例（如有）

### 参与开发

欢迎Pull Request：

1. Fork本仓库
2. 创建feature分支
3. 提交代码并测试
4. 提交PR并描述改动

---

## 📜 许可证

本项目采用 **AGPL-3.0 License** 开源协议。

你可以自由地：
- ✅ 使用本插件
- ✅ 修改源码
- ✅ 分发和再分发
- ✅ 用于商业用途

但必须遵守：
- 📝 保留原作者信息
- 📝 包含许可证副本
- 📝 以相同许可证（AGPL-3.0）分发修改版本
- 📝 说明你做了哪些修改
- 📝 如果通过网络提供服务，必须公开完整源代码

> ⚠️ **AGPL-3.0 重要提示**：如果你修改了本插件并在服务器上运行（即使不分发），只要用户通过网络与之交互，你就必须向用户提供修改后的完整源代码。这是 AGPL-3.0 与 GPL 的主要区别。

---

## 👤 作者

**Him666233**

- GitHub: [@Him666233](https://github.com/Him666233)
- 仓库地址: [astrbot_plugin_group_chat_plus](https://github.com/Him666233/astrbot_plugin_group_chat_plus)

---

## 🙏 致谢

感谢以下项目和开发者：

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 优秀的Bot框架
- [astrbot_plugin_SpectreCore](https://github.com/23q3/astrbot_plugin_SpectreCore) - 提供了很多实现参考
- [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) - 记忆系统集成
- [MaiBot](https://github.com/MaiM-with-u/MaiBot) - v1.0.2开始的新功能的设计灵感来源（由Mai.To.The.Gate组织及众多贡献者开发）

---

## ⭐ Star History

如果这个插件对你有帮助，请给个Star⭐支持一下！

---

<div align="center">

**🎉 享受更自然的群聊互动体验！**

Made with ❤️ by Him666233

</div>
