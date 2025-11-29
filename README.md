# 群聊增强插件 (Group Chat Plus)

<div align="center">

[![Version](https://img.shields.io/badge/version-v1.1.2-blue.svg)](https://github.com/Him666233/astrbot_plugin_group_chat_plus)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.0.0-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)](LICENSE)

一个以 **AI读空气** 为核心的群聊增强插件，让你的Bot更懂氛围、更自然地参与群聊互动

[功能特性](#-功能特性) • [安装方法](#-安装方法) • [配置指南](#-配置指南) • [工作原理](#-工作原理) • [常见问题](#-常见问题)

</div>

---

## ⚠️ 重要提醒：使用前必读

**关于与AstrBot官方回复功能的冲突：**

本插件提供的智能回复功能与AstrBot官方的主动回复功能是**完全独立**的两套系统。为了避免冲突和重复回复，**使用本插件前必须关闭AstrBot官方自带的主动回复功能**。

**不关闭官方功能可能导致的问题：**
- ❌ 同一条消息被回复多次
- ❌ 机器人过于频繁回复，刷屏严重
- ❌ 两套回复逻辑冲突，体验变差
- ❌ API调用次数翻倍，费用增加

> 💡 **配置建议**：关闭AstrBot自带的主动回复功能。本插件专注于群聊场景的智能回复。
-（如果您有其他的主动回复或者主动对话等会自动让AI回复内容或发消息的插件也建议关闭，否则可能会导致冲突，或者像打开了AstrBot官方主动回复功能一样，导致一条消息被重复回复或者回复过于频繁等问题。）
---

## ⚠️ 重要警告：图片处理功能说明

**关于图片处理功能的当前限制：**

目前图片处理功能存在一个已知问题：**如果不填写图片转文字提供商的ID（即留空 `image_to_text_provider_id`），尝试直接将图片信息传递给多模态AI的方法目前无法正常工作**。

尽管经过了多次改进和调试，但在不配置图片转文字提供商ID的情况下，虽然代码确实传递了图片的原始信息，但多模态AI始终无法正确接收和处理这些图片数据。由于个人代码水平有限，目前尚未找到根本原因。

**临时解决方案：**
- 请务必配置 `image_to_text_provider_id`，使用图片转文字流程
- 虽然这会经过一层"图片→文字描述→AI处理"的转换，可能导致部分图片细节损失和API费用略微增加
- 但这是目前唯一可靠的图片处理方式

**寻求帮助：**
如果有技术大佬知道如何解决多模态AI直接接收图片数据的问题，欢迎随时提交Issues或Pull Request，我们将非常感谢您的贡献！

---

## 🤝 插件合作：AstrBot智能自学习插件（astrbot_plugin_self_learning）

**我们很高兴宣布与 [AstrBot智能自学习插件](https://github.com/NickCharlie/astrbot_plugin_self_learning) 建立官方合作关系！**

### 为什么推荐同时使用？

**本插件专注于智能回复与群聊互动，自学习插件专注于AI学习与人格优化**，两者完美互补，共同打造最智能的群聊Bot体验！

#### 🎯 功能互补关系

| 维度 | 群聊增强插件（本插件） | 智能自学习插件 |
|------|-------------------|--------------|
| **核心定位** | 智能决策"何时回复" | 智能优化"如何回复" |
| **主要功能** | AI读空气、动态概率、注意力机制 | 对话风格学习、人格自动优化 |
| **数据处理** | 实时上下文管理、消息缓存 | 历史消息分析、风格提炼 |
| **交互优化** | 主动对话、情绪追踪、戳一戳响应 | 好感度系统、情绪状态、表达模式学习 |
| **技术特点** | 双层过滤、互动评分系统 | 机器学习、知识图谱、记忆图系统 |

#### ✨ 自学习插件的核心优势

1. **🧠 全自动学习循环**
   - 实时消息捕获与智能筛选
   - 多维度对话风格分析
   - AI人格自动优化迭代
   - 质量评估与效果验证

2. **❤️ 情感智能系统**
   - 用户好感度管理（单用户最大100分，总分250分上限）
   - 每日随机情绪系统（10种情绪类型）
   - 智能交互分析（称赞、鼓励、侮辱、骚扰等识别）
   - 动态情绪响应融入AI回复

3. **🎨 表达模式学习**（参考MaiBot）
   - 场景-表达模式映射
   - 15天时间衰减的质量管理
   - 知识图谱实体-关系提取
   - 25条消息触发学习节奏控制

4. **🌐 可视化管理系统**
   - 完整的Web管理界面（7833端口）
   - 数据统计与学习轨迹图表
   - 人格管理、审查与备份
   - 社交关系网络可视化分析

#### 🚀 配合使用的效果

**场景1：群聊日常互动**
```
用户A: "今天天气真不错！"
↓
【群聊增强插件】读空气判断 → 概率0.3 → AI判断："适合回复" → 触发回复
↓
【自学习插件】学习用户A的说话风格 → 提取"积极乐观"特征 → 优化人格
↓
Bot: "是啊！这么好的天气出去走走吧~"（融入学习的表达风格）
↓
【群聊增强插件】提升对用户A的注意力 → 下次更容易回复ta
【自学习插件】记录好感度+5 → 情绪状态更积极
```

**场景2：主动对话**
```
【群聊增强插件】检测沉默5分钟 → 互动评分70分（高） → 触发主动对话
↓
【自学习插件】提供学习的表达模式 → 根据当前情绪状态调整语气
↓
Bot: "话说，你们最近有没有发现那个新游戏挺好玩的？"（自然的主动话题）
↓
用户B回复 → 【群聊增强插件】互动评分+15 → 临时概率提升
          → 【自学习插件】好感度+3 → 学习用户B的话题偏好
```

#### 💡 组合使用的优势

✅ **智能决策 + 智能学习** = 既知道"何时说"又知道"怎么说"

✅ **读空气能力 + 人格优化** = 回复时机准确且风格自然

✅ **注意力机制 + 好感度系统** = 双重情感追踪，更真实的社交体验

✅ **互动评分 + 表达学习** = 越聊越聪明，持续进化

✅ **智能缓存 + 记忆图谱** = 完整的上下文理解与长期记忆

✅ **主动对话 + 情绪系统** = 像真人一样有情绪、有节奏的互动

#### 🔧 进一步合作计划

我们正在与自学习插件团队共同开发**更深度的API接口兼容**，**敬请期待！** 我们将持续优化两个插件的协同效果，为您打造最智能、最自然的群聊Bot！

---

**📌 快速开始双插件配置**

1. **安装两个插件**
   ```bash
   # 在AstrBot插件市场分别安装：
   - astrbot_plugin_group_chat_plus（本插件）
   - astrbot_plugin_self_learning（自学习插件）
   ```

2. **推荐配置组合**（本插件）
   ```json
   {
     "initial_probability": 0.15,
     "enable_attention_mechanism": true,
     "enable_proactive_chat": true,
     "enable_adaptive_proactive": true,
     "enable_memory_injection": true,
     "memory_plugin_mode": "auto"
   }
   ```

3. **推荐配置组合**（自学习插件）
   ```json
   {
     "enable_auto_learning": true,
     "enable_affection_system": true,
     "daily_mood_change": true,
     "enable_web_interface": true
   }
   ```

4. **验证配合效果**
   - 群聊增强插件处理回复时机和节奏
   - 自学习插件优化回复内容和风格
   - 两者数据独立但效果叠加

**🎊 欢迎加入QQ群 1021544792** - ChatPlus插件用户和自学习插件用户交流群！

---

## 本插件的开发从以下开源项目中获得了灵感，特此感谢。我们并未直接使用其代码，但借鉴了其优秀的功能设计：

- 项目名称：astrbot_plugin_SpectreCore
- 项目仓库地址：https://github.com/23q3/astrbot_plugin_SpectreCore
- 项目作者：23q3

- 项目名称：MaiBot
- 项目仓库地址：https://github.com/MaiM-with-u/MaiBot
- 项目作者：Mai.To.The.Gate 组织及众多贡献者


## 本插件支持两种记忆插件，优秀的记忆系统让AI的判断和回复更加智能，特此感谢：

**推荐：LivingMemory（v1.1.2新适配，更智能）**
- 项目名称：astrbot_plugin_livingmemory
- 项目仓库地址：https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory
- 特性：混合检索、智能总结、自动遗忘、会话隔离、人格隔离、动态人格切换
- 项目作者: lxfight's Astrbot Plugins 组织及众多贡献者

**传统：AI Memory（Legacy模式）**
- 项目名称：strbot_plugin_play_sy (又名：ai_memory)
- 项目仓库地址：https://github.com/kjqwer/strbot_plugin_play_sy
- 项目作者：kjqwdw

## 本插件从v1.1.1版本开始新增的指令回复所最后用到的重启astrBot的功能取自于astrbot_plugin_restart插件，并且直接参考并使用了相应的代码，特此感谢:

- 项目名称：astrbot_plugin_restart
- 项目仓库地址：https://github.com/Zhalslar/astrbot_plugin_restart
- 项目作者：Zhalslar

---


## 📖 插件简介

在群聊场景中，Bot需要像真人一样"读懂气氛"——既不能过于活跃导致刷屏，也不能完全沉默失去存在感。本插件通过**AI智能判断**、**动态概率调整**和**智能缓存机制**，让Bot实现真正的"读空气"能力。

### 🎯 核心优势

- **🧠 AI读空气** - 通过专门的AI判断是否应该回复当前消息
- **📈 动态概率** - 回复后自动提升触发概率，促进连续对话
- **🎯 注意力机制** - 像真人一样专注对话，追踪多用户注意力和情绪（v1.0.1新增，v1.0.2大幅增强，v1.1.2再次增强）
- **🤖 关键词智能模式** - 触发关键词时可选择保留AI判断，拒绝机械式回复（v1.1.2新增）
- **📊 智能自适应主动对话** - 基于互动评分系统自动调整Bot活跃度，越聊越开心，冷场自动收敛（v1.1.2新增，v1.2.0内核）
- **💬 主动对话功能** - AI会在群聊沉默后主动发起话题，保持存在感（v1.1.0新增）
- **✍️ 打字错误** - 自动添加少量自然的错别字，让回复更真实（v1.0.2新增）
- **😊 情绪系统** - AI根据对话产生情绪变化，影响回复语气（v1.0.2新增，v1.0.7增强）
- **⏱️ 延迟模拟** - 模拟真人打字速度，避免秒回（v1.0.2新增）
- **📊 频率调整** - 自动分析发言频率并动态调整概率（v1.0.2新增）
- **👆 戳一戳支持** - 智能处理戳一戳消息，支持反戳和回复后戳（v1.0.9新增，v1.1.0增强，v1.1.2再次增强）
- **🚫 用户黑名单** - 可屏蔽特定用户，本插件不处理其消息（v1.0.7新增）
- **🚫 @他人过滤** - 可配置忽略@其他人的消息，避免插入他人对话（v1.0.9新增）
- **🔧 完整指令检测** - 支持全字符串匹配指令（如单独的`new`、`help`），更精准过滤（v1.1.2新增）
- **🔧 内存管理** - 自动清理不活跃群组记录，防止内存泄漏（v1.0.8新增）
- **💾 智能缓存** - 保存未回复消息的上下文，避免记忆断裂
- **🧠 智能记忆系统** - 支持LivingMemory插件（v1.1.2新适配），混合检索+智能总结+人格隔离
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

### 社交节奏增强（v1.1.0 新增）

| 功能 | 说明 | 优势 |
|------|------|------|
| **主动聊天** | 群聊长时间沉默后由AI自然开场/延展话题 | 保持存在感，避免死群 |
| **时段概率** | 按时间段动态调整普通回复与主动聊天概率 | 模拟作息与社交节奏，更拟人 |
| **禁用时段** | 夜间自动安静，支持平滑过渡 | 尊重休息，不打扰 |
| **概率硬限制** | 将最终概率限制在区间内 | 简化配置，防止过高/过低 |

### 真实性增强功能（v1.0.2 新增，v1.0.7 增强）

| 功能 | 说明 | 优势 |
|------|------|------|
| **打字错误生成** | 2%概率添加自然的拼音相似错别字 | 避免过于完美，增加真实感 |
| **情绪追踪系统** | 根据对话检测并维护情绪状态 | 回复更有感情，更像真人 |
| **智能否定词检测** 🆕 v1.0.7 | 识别"不难过"等否定表达，避免情绪误判 | 更准确的情绪理解，减少误判 |
| **回复延迟模拟** | 基于文本长度模拟打字速度 | 避免秒回，营造真实感 |
| **频率动态调整** | AI自动分析并调整发言频率 | 自适应群聊节奏，更自然 |

### 管理增强功能（v1.0.7 新增，v1.0.9 增强）

| 功能 | 说明 | 优势 |
|------|------|------|
| **用户黑名单** | 屏蔽特定用户的消息 | 精准控制，避免干扰 |
| **戳一戳消息处理** 🆕 v1.0.9 | 智能识别和处理QQ戳一戳消息 | AI能理解戳一戳互动，自然回应 |
| **@他人消息过滤** 🆕 v1.0.9 | 可配置忽略@其他人的消息 | 避免插入他人私密对话，保持边界感 |

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

- **记忆植入**: 支持两种模式
  - **LivingMemory模式**（v1.1.2新增，推荐）：混合检索、智能总结、自动遗忘、人格隔离
  - **Legacy模式**：传统 `strbot_plugin_play_sy` 插件
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
- **可选**: 记忆插件（记忆植入功能需要，二选一）
  - **推荐**: `astrbot_plugin_livingmemory` （v1.1.2新适配，更智能）
  - 传统: `strbot_plugin_play_sy`

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

**方案4: 互动增强模式（v1.0.9全功能）**
```json
{
  "initial_probability": 0.15,
  "after_reply_probability": 0.15,
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
  "enable_negation_detection": true,
  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 20,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 15,
  "mood_cleanup_threshold": 3600,
  "mood_cleanup_interval": 600,
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#"],
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "decision_ai_timeout": 30,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "enabled_groups": []
}
```

**方案5: 主动聊天 + 时段概率（v1.1.0 新增，v1.1.1 完善，推荐搭配）**
```json
{
  "initial_probability": 0.12,
  "after_reply_probability": 0.65,
  "probability_duration": 180,

  "enable_dynamic_reply_probability": true,
  "reply_time_periods": [
    {"name": "深夜睡眠", "start": "23:00", "end": "07:00", "factor": 0.2},
    {"name": "午休时段", "start": "12:00", "end": "14:00", "factor": 0.5},
    {"name": "晚间活跃", "start": "19:00", "end": "22:00", "factor": 1.3}
  ],
  "reply_time_transition_minutes": 30,
  "reply_time_min_factor": 0.1,
  "reply_time_max_factor": 2.0,
  "reply_time_use_smooth_curve": true,

  "enable_proactive_chat": true,
  "proactive_silence_threshold": 600,
  "proactive_probability": 0.3,
  "proactive_check_interval": 60,
  "proactive_require_user_activity": true,
  "proactive_min_user_messages": 3,
  "proactive_user_activity_window": 300,
  "proactive_enable_quiet_time": true,
  "proactive_quiet_start": "23:00",
  "proactive_quiet_end": "07:00",
  "proactive_transition_minutes": 30,
  "proactive_temp_boost_probability": 0.5,
  "proactive_temp_boost_duration": 120,
  "proactive_max_consecutive_failures": 3,
  "proactive_cooldown_duration": 900,
  "proactive_use_attention": true,
  "proactive_at_probability": 0.3,
  "proactive_enabled_groups": [],

  "enable_dynamic_proactive_probability": true,
  "proactive_time_periods": [
    {"name": "深夜睡眠", "start": "23:00", "end": "07:00", "factor": 0.0},
    {"name": "午休时段", "start": "12:00", "end": "14:00", "factor": 0.3},
    {"name": "晚间超活跃", "start": "19:00", "end": "22:00", "factor": 1.8}
  ],
  "proactive_time_transition_minutes": 45,
  "proactive_time_min_factor": 0.0,
  "proactive_time_max_factor": 2.0,
  "proactive_time_use_smooth_curve": true,

  "enable_probability_hard_limit": true,
  "probability_min_limit": 0.05,
  "probability_max_limit": 0.8,

  "decision_ai_timeout": 30,
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true,
  "enabled_groups": []
}
```

**方案6: 智能自适应增强（v1.1.2 新增，强烈推荐）**
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
  
  "trigger_keywords": ["帮助", "机器人", "问题"],
  "keyword_smart_mode": true,
  
  "enable_full_command_detection": true,
  "full_command_list": ["new", "help", "reset", "clear"],
  
  "enable_proactive_chat": true,
  "proactive_silence_threshold": 300,
  "proactive_probability": 0.2,
  "proactive_check_interval": 60,
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
  "poke_enabled_groups": [],
  
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true
}
```

> 💡 **配置建议**: 
> - 方案1：传统模式，灵活简单
> - 方案2：增强注意力机制，多用户追踪+情绪系统（v1.0.2升级）
> - 方案3：真实感增强，最接近真人（v1.0.2全功能推荐）
> - 方案4：互动增强模式，包含戳一戳回应和边界感保持（v1.0.9全功能推荐）
> - 方案5：主动聊天+时段概率，拟人化作息与社交节奏（v1.1.0新增）
> - **方案6：智能自适应增强，关键词智能模式+互动评分系统（v1.1.2新增，推荐）** ⭐

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

#### 🎯 增强注意力机制（v1.0.1 新增，v1.0.2 增强，v1.1.2 再次增强）

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
| `attention_decrease_on_no_reply_step` | float | 0.15 | **AI不回复时注意力衰减幅度** 🆕 v1.1.2<br>当AI判断不回复某用户时，减少对该用户的注意力<br>表示用户可能在跟别人聊天，AI应减少关注<br>只对高注意力用户生效<br>建议: 0.1-0.2 |
| `attention_decrease_threshold` | float | 0.3 | **注意力衰减保护阈值** 🆕 v1.1.2<br>注意力低于此值时不再衰减<br>给用户保留一定关注度<br>建议: 0.2-0.4 |
| `enable_attention_emotion_detection` | bool | false | **启用注意力情感检测** 🆕 v1.1.2<br>AI回复时分析消息的正负面情绪<br>正面消息额外提升情绪值，负面消息降低<br>独立于情绪追踪系统 |
| `attention_emotion_keywords` | object | {...} | **注意力情感关键词配置** 🆕 v1.1.2<br>用于情感检测的关键词列表（positive/negative）<br>可自定义，留空使用默认配置 |
| `attention_enable_negation` | bool | true | **启用否定词检测（注意力）** 🆕 v1.1.2<br>情感检测时识别否定词<br>如"不开心"不会被判定为"开心" |

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
| `decision_ai_provider_id` | string | "" | **读空气AI提供商ID**<br>用于判断是否回复的AI提供商ID，留空则使用默认提供商<br>建议: 使用轻量快速的模型 |
| `decision_ai_prompt_mode` | string | "append" | **读空气AI提示词模式**<br>• `append`: 拼接在默认系统提示词后面<br>• `override`: 完全覆盖默认系统提示词（需填写额外提示词） |
| `decision_ai_extra_prompt` | text | "" | **读空气AI额外提示词**<br>给判断是否回复的AI添加的自定义提示词<br>append模式下可以留空，留空使用默认积极模式 |
| `decision_ai_timeout` | int | 30 | **读空气AI超时时间（秒）**<br>读空气AI判断的超时时间，超过此时间将默认不回复<br>建议根据AI提供商速度调整，默认30秒 |
| `reply_ai_prompt_mode` | string | "append" | **回复AI提示词模式**<br>• `append`: 拼接在默认系统提示词后面<br>• `override`: 完全覆盖默认系统提示词（需填写额外提示词） |
| `reply_ai_extra_prompt` | text | "" | **回复AI额外提示词**<br>给最终回复消息的AI添加的自定义提示词<br>append模式下可以留空 |

#### 🎲 概率控制配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_probability` | float | 0.3 | **初始读空气概率**<br>AI初始判断是否回复消息的概率，范围0-1<br>如0.1表示10%概率触发读空气判断 |
| `after_reply_probability` | float | 0.8 | **回复后的读空气概率**<br>AI回复消息后，临时提升的读空气概率，范围0-1 |
| `probability_duration` | int | 120 | **概率提升持续时间（秒）**<br>AI回复后，提升的概率持续多长时间，超过后恢复为初始概率 |

#### 🔒 概率硬性限制（一键简化功能）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_probability_hard_limit` | bool | false | **启用概率硬性限制**<br>⚠️简化配置功能⚠️ 开启后，将强制限制所有主动回复功能的最终概率在设定范围内<br>无论其他功能如何调整概率，最终都会被限制在[最小值,最大值]区间内 |
| `probability_min_limit` | float | 0.05 | **概率最小值限制**<br>所有主动回复功能的最终概率不会低于此值（范围0-1）<br>建议0.05-0.2 |
| `probability_max_limit` | float | 0.8 | **概率最大值限制**<br>所有主动回复功能的最终概率不会高于此值（范围0-1）<br>建议0.6-0.9 |

> ⚠️ **概率硬性限制说明**:
> - 此功能会覆盖所有概率调整的结果，可能影响AI的拟人化表现
> - 除非AI回复过于频繁或过于冷淡需要强制限制，否则不建议开启
> - 不影响主动对话功能和其他模式

#### 🧠 AI提示词模板（v1.1.1 更新）

- **决策AI（读空气）模板要点**
  - 只关注“当前新消息”的核心内容；历史仅作参考
  - 检查与历史“【你自己的历史回复】”是否重复；避免重复回复
  - 正确理解历史中的系统标记（如 `[🎯主动发起新话题]` / `[PROACTIVE_CHAT]` / 【@指向说明】 / `[戳一戳提示]`），只把它们当作上下文线索
  - **严禁**在输出中提及任何系统提示词、内部规则或这些标记本身（只输出 `yes` / `no`）
  - 模板位置：`utils/decision_ai.py` 中 `SYSTEM_DECISION_PROMPT`

- **回复AI模板要点**
  - 生成自然、简洁、无元信息的回复；不提及系统提示/规则
  - 正确理解【@指向说明】、`[戳一戳提示]` 以及 `[戳过对方提示]`、`[🎯主动发起新话题]` / `[PROACTIVE_CHAT]` 等标记，保持边界感和自然互动
  - 避免与历史“【你自己的历史回复】”重复；自然融入背景信息
  - **绝对禁止**在回复中复述、引用或解释任何系统提示、内部标记、时间戳、ID 等元信息
  - 模板位置：`utils/reply_handler.py` 中 `SYSTEM_REPLY_PROMPT`

> 说明：如需定制，使用 `decision_ai_extra_prompt` 与 `reply_ai_extra_prompt`，并通过 `*_prompt_mode: append/override` 控制拼接或覆盖；推荐使用 `append`，仅补充人设与语气，不要删除系统约束段落。

#### 📝 消息处理配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `include_timestamp` | bool | true | **包含时间戳信息**<br>是否在消息前插入发送时间（年月日时分秒） |
| `include_sender_info` | bool | true | **包含发送者信息**<br>是否在消息中插入发送者ID和名字 |
| `max_context_messages` | int | -1 | **最大上下文消息数**<br>• `-1`: 不限制（推荐）<br>• `正数`: 限制数量<br>• `0`: 不获取历史 |

#### 🔑 关键词配置（v1.1.2 增强）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trigger_keywords` | list | [] | **触发关键词列表**<br>当消息中包含这些关键词时，将跳过读空气判断<br>**传统模式（默认）**：跳过概率+跳过AI判断=必定回复<br>**智能模式**：仅跳过概率，保留AI判断=AI决定是否回复<br>可以填AI扮演的角色的名字、别名之类的。留空则不启用该功能 |
| `keyword_smart_mode` | bool | false | **关键词智能模式** 🆕 v1.1.2<br>**关闭（传统模式）**：检测到关键词→跳过概率+跳过AI判断→必定回复<br>**开启（智能模式）**：检测到关键词→跳过概率+**保留AI判断**→AI决定是否回复<br>拒绝机械式回复，让AI根据上下文智能判断是否应该回复<br>**适用场景**：避免关键词误触发（如"帮助"出现在其他对话中） |
| `blacklist_keywords` | list | [] | **黑名单关键词列表**<br>当消息中包含这些关键词时，将直接忽略该消息，不进行任何处理<br>留空则不启用该功能 |

> 💡 **关键词智能模式说明** (v1.1.2新增):
> - **传统模式（keyword_smart_mode: false，默认）**：
>   - 行为：触发关键词 → 必定回复（机械式）
>   - 优点：响应快速、确定性高
>   - 缺点：可能误触发（如"我需要帮助处理这个文件"也会回复）
> - **智能模式（keyword_smart_mode: true）**：
>   - 行为：触发关键词 → AI判断是否应该回复
>   - 优点：更智能、更自然，避免误触发
>   - 缺点：需要额外的AI判断调用
> - **建议**：谨慎启用，需要配合优质的决策AI提示词

#### 🚫 用户黑名单配置（v1.0.7 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_user_blacklist` | bool | false | **启用用户黑名单**<br>开启后，黑名单中的用户发送的消息将被本插件忽略<br>⚠️ **重要**：仅本插件忽略，其他插件和官方功能仍可正常处理这些消息 |
| `blacklist_user_ids` | list | [] | **黑名单用户ID列表**<br>需要屏蔽的用户ID列表。这些用户的消息将被本插件忽略<br>但不影响其他插件处理。留空则不屏蔽任何用户 |

> ⚠️ **用户黑名单重要说明**:
> - **局限性**：本插件的黑名单功能**只能阻止本插件处理**黑名单用户的消息
> - **其他系统不受影响**：被屏蔽用户的消息仍然会被以下系统正常处理：
>   - AstrBot官方对话系统
>   - 其他已安装的插件
>   - 其他自动回复功能
> - **可能的问题**：如果您同时开启了AstrBot官方回复功能或其他自动回复插件，黑名单用户的消息可能仍然会触发回复
> - **建议解决方案**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_ignore_at_others` | bool | false | **启用忽略@他人消息功能**<br>开启后，可根据设定的模式自动忽略@了其他人（非机器人）的消息<br>即使消息包含触发关键词，也不会进行任何处理 |
| `ignore_at_others_mode` | string | "strict" | **@他人消息忽略模式**<br>• `strict`: 只要检测到消息中@了其他人就直接忽略<br>• `allow_with_bot`: 如果消息中虽然@了他人但也@了机器人，则继续处理 |

> 💡 **@他人消息过滤说明**:
> - 适用场景：避免插入他人的私密对话，保持对话边界感
> - 不影响其他插件和官方功能
> - 建议使用`allow_with_bot`模式（保留@机器人时的响应能力）

#### 🖼️ 图片处理配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_image_processing` | bool | false | **允许处理图片**<br>是否允许AI回复包含图片的消息 |
| `image_to_text_scope` | string | "mention_only" | **图片转文字应用范围**<br>• `all`: 对所有消息适用<br>• `mention_only`: 对@机器人或包含触发关键词的消息适用（推荐，节省API）<br>• `at_only`: 仅对真正@机器人的消息适用<br>• `keyword_only`: 仅对包含触发关键词的消息适用 |
| `image_to_text_provider_id` | string | "" | **图片转文字AI提供商ID**<br>用于图片转文字的AI提供商ID，留空则直接传递图片<br>请确认接下来的AI都是多模态AI |
| `image_to_text_prompt` | string | "请详细描述这张图片的内容" | **图片转文字提示词**<br>图片转文字时使用的提示词 |
| `image_to_text_timeout` | int | 60 | **图片转文字超时时间（秒）**<br>图片转文字AI调用的超时时间，超过此时间将放弃转换<br>建议根据AI提供商速度调整，默认60秒 |

> ⚠️ **图片处理注意**:
> - 留空 `image_to_text_provider_id` 需要确保默认AI支持多模态
> - 建议将 `image_to_text_scope` 设为 `mention_only` 避免频繁调用API
> - 图片描述会自动保存到缓存，下次回复时保持上下文
> - 如果出现图片转文字超时，请适当增加 `image_to_text_timeout` 值

#### 🧩 高级功能配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_memory_injection` | bool | false | **启用强制记忆植入** 🆕 v1.1.2增强<br>调用记忆插件获取长期记忆，支持两种模式：<br>• **LivingMemory模式**（推荐）：`astrbot_plugin_livingmemory`<br>&nbsp;&nbsp;- 混合检索、智能总结、自动遗忘<br>&nbsp;&nbsp;- 会话隔离、人格隔离、动态人格切换<br>&nbsp;&nbsp;- 按重要性×相关性×新鲜度排序<br>• **Legacy模式**：`strbot_plugin_play_sy`<br>系统自动检测已安装的插件并选择合适模式 |
| `memory_plugin_mode` | string | "auto" | **记忆插件模式** 🆕 v1.1.2<br>• `auto`: 自动检测（优先LivingMemory）<br>• `livingmemory`: 强制使用LivingMemory<br>• `legacy`: 强制使用Legacy模式<br>建议保持auto，让系统自动选择 |
| `memory_top_k` | int | 5 | **记忆召回数量** 🆕 v1.1.2<br>LivingMemory模式召回多少条记忆<br>• 正整数：召回指定数量<br>• `-1`：召回所有相关记忆（最多1000条）<br>Legacy模式忽略此配置<br>建议: 5-10条 |
| `enable_tools_reminder` | bool | false | **启用工具提醒**<br>是否提示AI当前可用的所有工具 |

#### 🎯 启用范围配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled_groups` | list | [] | **启用的群组列表**<br>在哪些群组中启用此插件<br>留空则在所有群聊中启用；填写群号则只在指定群组中启用 |

#### 🐛 调试配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_debug_log` | bool | false | **启用详细日志**<br>开启后会输出更多详细的调试日志，便于排查问题和了解插件运行状态 |

#### � 插件重置配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `plugin_reset_allowed_user_ids` | list | [] | **允许使用插件重置指令的用户ID白名单**<br>可配置多个用户ID，只有在此列表中的用户才能触发重置指令<br>留空=允许所有用户使用。仅在群聊中生效 |

#### 👆 戳一戳增强配置（v1.1.0 新增，v1.1.2 再次增强）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poke_message_mode` | string | "bot_only" | **戳一戳处理模式**<br>`ignore`=忽略；`bot_only`=只处理戳机器人；`all`=处理所有戳一戳并标注谁戳了谁 |
| `poke_bot_skip_probability` | bool | true | **戳机器人时跳过概率筛选** ⭐ v1.1.2优化<br>**开启（默认）**：跳过概率筛选（旧行为）<br>**关闭**：参与概率判断+智能增加额外概率（新行为）<br>仍保留AI读空气判断 |
| `poke_bot_probability_boost_reference` | float | 0.3 | **戳机器人概率增值参考** 🆕 v1.1.2<br>当`poke_bot_skip_probability`关闭时生效<br>参考值而非直接增加，根据情绪/注意力动态调整<br>建议: 0.2-0.5 |
| `poke_enabled_groups` | list | [] | **戳一戳功能启用群组** 🆕 v1.1.2<br>留空=所有群启用，填群号=仅指定群启用<br>与全局`enabled_groups`独立 |
| `poke_reverse_on_poke_probability` | float | 0.0 | **收到戳一戳时反戳概率**<br>0-1；不拦截后续消息处理 |
| `enable_poke_after_reply` | bool | false | **启用回复后戳一戳**<br>仅在主动回复时触发，不在主动聊天中触发 |
| `poke_after_reply_probability` | float | 0.15 | **回复后戳一戳概率** |
| `poke_after_reply_delay` | float | 0.5 | **回复后戳一戳延迟（秒）**<br>模拟思考后再戳，更像真人 |
| `enable_poke_trace_prompt` | bool | false | **启用戳过对方追踪提示**（v1.1.1 新增）<br>开启后，当AI对某用户执行戳一戳（包括回复后戳一戳、收到戳一戳后反戳），在设定时长内若该用户发来消息，会在上下文开头为AI添加`[戳过对方提示]`说明（仅供AI理解，不会写入官方历史） |
| `poke_trace_max_tracked_users` | int | 5 | **戳过对方最大追踪人数**（v1.1.1 新增）<br>每个群聊最多同时追踪多少个被AI戳过的用户。超过后按先进先出移除最早的记录 |
| `poke_trace_ttl_seconds` | int | 300 | **戳过对方提示有效期（秒）**（v1.1.1 新增）<br>从AI戳用户开始，追踪该用户的时长。超过后不再提示并自动清理记录 |

> 💡 **v1.1.2 戳一戳增强说明**:
> - **智能概率增值**: 关闭`poke_bot_skip_probability`后，戳机器人会参与概率判断但智能增加额外概率
> - **动态调整**: 实际增值根据情绪、注意力动态计算，情绪负面时减少，情绪正面时允许更多
> - **群组独立控制**: 可以仅在特定群组启用戳一戳功能
> - **建议配置**: `bot_only` + `poke_bot_skip_probability: true`（默认，最自然）

#### 💬 主动对话功能配置（v1.1.0 新增，v1.1.2 智能自适应升级）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_proactive_chat` | bool | false | **启用主动对话功能**<br>开启后，AI会在长时间沉默后主动发起新话题，模拟真人聊天行为<br>让AI更拟人化，避免群聊死寂 |
| `proactive_silence_threshold` | int | 600 | **沉默时长阈值（秒）**<br>AI沉默多久后可能触发主动对话<br>默认600秒(10分钟)。建议300-1800秒，根据群活跃度调整 |
| `proactive_probability` | float | 0.3 | **主动对话触发概率**<br>超过沉默阈值后，每次检查触发主动对话的概率(0-1)<br>默认0.3。建议0.2-0.5，太高会让AI显得过于主动 |
| `proactive_check_interval` | int | 60 | **检查间隔（秒）**<br>多久检查一次是否应该触发主动对话<br>默认60秒。建议30-120秒，间隔太短会增加CPU占用 |
| `proactive_require_user_activity` | bool | true | **需要用户活跃度**<br>开启后，只有在最近有用户发言时才会主动对话<br>避免在死群突然说话。强烈建议开启 |
| `proactive_min_user_messages` | int | 3 | **最少用户消息数**<br>距离上次AI发言后，至少需要多少条用户消息才能主动对话<br>默认3条。建议2-5条，避免AI过于频繁主动 |
| `proactive_user_activity_window` | int | 300 | **用户活跃时间窗口（秒）**<br>检查多少秒内是否有用户发言<br>默认300秒(5分钟)。用于判断群是否还活跃 |
| `proactive_max_consecutive_failures` | int | 2 | **最大连续失败次数**<br>AI主动发言后无人回复，最多连续尝试几次<br>超过后进入长时间冷却。默认2次。建议1-3次 |
| `proactive_cooldown_duration` | int | 1800 | **失败后冷却时间（秒）**<br>达到最大连续失败次数后的冷却时间<br>默认1800秒(30分钟)。冷却期内不会再主动发言 |
| `proactive_enable_quiet_time` | bool | false | **启用禁用时段**<br>开启后可设置某个时间段禁用主动对话(如深夜)<br>避免打扰用户休息 |
| `proactive_quiet_start` | string | "23:00" | **禁用时段开始时间**<br>禁用时段开始时间，格式为HH:MM(24小时制)<br>例如: 23:00 表示晚上11点开始禁用 |
| `proactive_quiet_end` | string | "07:00" | **禁用时段结束时间**<br>禁用时段结束时间，格式为HH:MM(24小时制)<br>例如: 07:00 表示早上7点结束禁用。支持跨天(如23:00-07:00) |
| `proactive_transition_minutes` | int | 30 | **过渡时长（分钟）**<br>进入/离开禁用时段前的过渡时间<br>概率会在此期间线性变化，避免突然禁用。默认30分钟。建议15-60分钟 |
| `proactive_prompt` | text | 见默认值 | **主动对话提示词**<br>主动发起对话时给AI的专用提示词<br>留空则使用默认提示。可以定制AI主动发言的风格和话题方向 |
| `proactive_use_attention` | bool | true | **主动关注高注意力用户**<br>开启后，主动对话时话题会倾向于注意力高的用户<br>需要先启用注意力机制。让主动对话更有针对性 |
| `proactive_temp_boost_probability` | float | 0.5 | **临时概率提升值**<br>AI主动发言后，短暂提升回复概率的数值(0-1)<br>模拟真人发完消息后会留意回复的行为。默认0.5 |
| `proactive_temp_boost_duration` | int | 120 | **临时概率提升持续时间（秒）**<br>临时概率提升持续多久<br>默认120秒(2分钟)。期间内如有人回复会立即取消提升，超时也会自动取消 |
| `proactive_enabled_groups` | list | [] | **主动对话功能启用的群组列表**<br>在哪些群组中启用主动对话功能<br>留空则在所有群聊中启用；填写群号则只在指定群组中启用<br>与全局的enabled_groups独立，可以单独控制主动对话功能的生效范围 |

#### 📊 智能自适应主动对话配置（v1.1.2 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_adaptive_proactive` | bool | true | **启用智能自适应主动对话** 🆕 v1.1.2<br>根据互动评分自动调整Bot活跃度<br>越聊越开心，冷场自动收敛 |
| `score_increase_on_success` | int | 15 | **成功互动基础加分** 🆕 v1.1.2<br>有人回复主动对话时的基础加分<br>建议: 10-20分 |
| `score_decrease_on_fail` | int | 8 | **失败互动基础扣分** 🆕 v1.1.2<br>无人理会主动对话时的基础扣分<br>建议: 5-10分 |
| `interaction_score_min` | int | 10 | **互动评分最小值** 🆕 v1.1.2<br>评分下限，给翻身机会<br>建议: 10-20分 |
| `interaction_score_max` | int | 100 | **互动评分最大值** 🆕 v1.1.2<br>评分上限，防止过度活跃<br>建议: 80-100分 |
| `enable_complaint_system` | bool | true | **启用吐槽系统** 🆕 v1.1.2<br>连续失败时AI会吐槽<br>让Bot更有情绪 |
| `complaint_trigger_threshold` | int | 2 | **吐槽触发阈值** 🆕 v1.1.2<br>累积失败多少次后开始检查吐槽等级<br>建议: 2-5次 |
| `complaint_decay_on_success` | int | 2 | **成功时减少累积失败次数** 🆕 v1.1.2<br>每次成功互动减少部分累积失败<br>建议: 1-3次 |
| `complaint_max_accumulation` | int | 15 | **累积失败次数上限** 🆕 v1.1.2<br>防止累积过多<br>建议: 10-20次 |

> 💡 **智能自适应主动对话说明** (v1.1.2新增):
> - **互动评分机制**：
>   - 成功互动：基础+15分，快速回复+5分，多人回复+10分，连续成功+5分，低分复苏+20分
>   - 失败互动：基础-8分
> - **评分影响**：
>   - 高分群聊（>70分）：沉默阈值×0.7，概率×1.5，更活跃
>   - 低分群聊（<30分）：沉默阈值×1.5，概率×0.5，更克制
>   - 极低分群聊（<20分）：进入冷淡期，显著抑制（×0.3）
> - **自动衰减**：每24小时无互动→自动扣2分（防止吃老本）
> - **防误判机制**：只有AI真正决定回复时才判定成功，避免"用户回复但AI不理会"的误判
> - **吐槽系统**：累积失败次数独立追踪，不受冷却重置影响，让Bot情绪变化更自然

> 💡 **主动对话功能说明**:
> - **核心功能**: 群聊长时间沉默后由AI主动开场或延展话题
> - **拟人化设计**: 模拟真人发言后留意回复的行为（临时概率提升）
> - **智能控制**: 支持用户活跃度判断、失败冷却、禁用时段等
> - **安全机制**: 避免在死群突然发言，避免深夜打扰用户
> - **独立控制**: 可单独设置启用群组，不影响其他功能
> - **注意力配合**: 可与注意力机制配合，让主动对话更有针对性

#### 🗓️ 时段概率调整配置（v1.1.0 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_dynamic_reply_probability` | bool | false | **启用普通回复的时段概率调整**<br>根据时间段调整 `initial_probability` 和 `after_reply_probability`<br>模拟人类作息规律，让AI在不同时段表现出不同的活跃度 |
| `reply_time_periods` | text(JSON) | 见默认值 | **普通回复时间段配置**<br>配置多个时间段及其概率系数<br>示例：`[{"name":"深夜睡眠","start":"23:00","end":"07:00","factor":0.2},{"name":"午休时段","start":"12:00","end":"14:00","factor":0.5},{"name":"晚间活跃","start":"19:00","end":"22:00","factor":1.3}]`<br>factor说明: 0.2=很困倦(概率降低80%), 1.0=正常, 1.5=很活跃(概率提升50%) |
| `reply_time_transition_minutes` | int | 30 | **过渡时长（分钟）**<br>进入/离开特殊时间段时的平滑过渡时长<br>建议20-60分钟，模拟人类逐渐清醒/困倦的过程 |
| `reply_time_min_factor` | float | 0.1 | **最低概率系数限制**<br>防止概率过低导致AI完全不回复<br>建议0.05-0.3（0.1=最低保留10%活跃度，即使在最困倦的时段也会偶尔回复） |
| `reply_time_max_factor` | float | 2.0 | **最高概率系数限制**<br>防止概率过高导致AI过于活跃<br>建议1.5-3.0（2.0=最高提升到200%，即使在最活跃时段也不会过于频繁） |
| `reply_time_use_smooth_curve` | bool | true | **使用自然曲线过渡**<br>开启后使用ease-in-out曲线模拟人类注意力的自然变化<br>关闭则使用线性过渡。强烈建议开启以获得更真实、更拟人化的效果 |
| `enable_dynamic_proactive_probability` | bool | false | **启用主动对话的时段概率调整**<br>开启后，AI主动发言概率会根据时间段动态调整<br>⚠️重要：如果同时启用了'禁用时段'功能，禁用时段的优先级更高 |
| `proactive_time_periods` | text(JSON) | 见默认值 | **主动对话时间段配置**<br>配置多个时间段及其概率系数。主动对话建议使用更极端的系数<br>示例: `[{"name":"深夜睡眠","start":"23:00","end":"07:00","factor":0.0},{"name":"午休时段","start":"12:00","end":"14:00","factor":0.3},{"name":"晚间超活跃","start":"19:00","end":"22:00","factor":1.8}]`<br>factor说明: 0.0=完全不主动, 0.3=偶尔主动, 1.5-2.0=非常主动 |
| `proactive_time_transition_minutes` | int | 45 | **主动对话过渡时长（分钟）**<br>主动对话的过渡时间建议设置更长<br>避免AI突然变得主动或突然沉默。建议30-90分钟 |
| `proactive_time_min_factor` | float | 0.0 | **主动对话最低概率系数限制**<br>主动对话允许完全禁用(0.0)<br>建议0.0-0.2（0.0=完全不主动，0.2=保留20%主动性） |
| `proactive_time_max_factor` | float | 2.0 | **主动对话最高概率系数限制**<br>防止主动过于频繁<br>建议1.5-2.5（2.0=最高提升到200%主动性，在活跃时段会比较频繁地主动发言） |
| `proactive_time_use_smooth_curve` | bool | true | **主动对话使用自然曲线过渡**<br>开启后使用ease-in-out曲线模拟社交意愿的自然变化<br>强烈建议开启以获得更拟人化的主动对话效果 |

> 💡 **时段概率调整说明**:
> - **模拟作息**: 根据时间段调整AI的活跃度，模拟人类作息规律
> - **双重模式**: 支持普通回复和主动对话的独立时段调整
> - **平滑过渡**: 支持线性和曲线过渡，避免概率突变
> - **安全限制**: 设置最高最低系数限制，防止过度活跃或完全沉默
> - **优先级**: 主动对话的禁用时段优先级高于时段概率调整
> - **配合其他功能**: 与注意力机制、频率调整器等功能自动配合，不会产生冲突

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
| `frequency_analysis_timeout` | int | 20 | **频率分析超时时间（秒）** 🆕 v1.0.8<br>AI分析发言频率时的超时时间<br>如果AI响应慢可以适当增加<br>建议: 20-30秒 |
| `frequency_adjust_duration` | int | 360 | **频率调整持续时间（秒）** 🆕 v1.0.8<br>频率调整后的新概率持续多长时间<br>建议设置为检查间隔的2倍左右<br>建议: 360秒（6分钟） |
| `frequency_analysis_message_count` | int | 15 | **频率分析消息数量** 🆕 v1.0.8<br>分析发言频率时获取多少条最近消息<br>活跃群聊可以设置更多(20-30)，冷清群聊可以设置更少(10-15)<br>建议: 15条 |

> 💡 **真实性增强说明**:
> - 所有功能默认启用，经过调优，开箱即用
> - 打字错误率2%表示平均每50字出现1个错字，非常自然
> - 情绪系统会在检测到情绪关键词后维护5分钟，然后自动衰减
> - 延迟模拟基于文本长度计算，短消息快速回复，长消息延迟更久
> - 频率调整会消耗额外的AI调用（每3分钟一次），注意API成本
> - **v1.0.8增强**：新增三个配置项精细控制频率调整（超时、持续时间、消息数量）
> - 如需关闭所有新功能恢复v1.0.1体验，将所有enable开关设为false

#### 🐛 调试配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_debug_log` | bool | false | **启用详细日志**<br>输出详细的调试信息，便于排查问题 |

#### 🔁 插件/会话重置配置（v1.1.1 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `plugin_reset_allowed_user_ids` | list | [] | **允许使用重置指令的用户ID白名单**<br>控制谁可以在群里执行 `gcp_reset` / `gcp_reset_here` 指令：<br>• 为空或不配置：所有用户都可以触发重置（不推荐在大群开放）<br>• 填写一组用户ID：仅这些用户可以执行重置指令，其它人发送同名命令会被忽略<br>配合 AstrBot 官方“清空会话/清除聊天记录”指令使用，可安全地在中途切换人格/提示词而不产生人格混乱 |

#### 🚫 用户黑名单配置（v1.0.7 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_user_blacklist` | bool | false | **启用用户黑名单**<br>开启后，黑名单中的用户发送的消息将被本插件忽略（不影响其他插件和官方功能） |
| `blacklist_user_ids` | list | [] | **黑名单用户ID列表**<br>需要屏蔽的用户ID列表。这些用户的消息将被本插件忽略，但不影响其他插件处理。留空则不屏蔽任何用户<br>示例: `["123456789", "987654321"]` |

> 💡 **用户黑名单说明**:
> - 黑名单仅对本插件生效，不影响其他插件和AstrBot官方功能
> - 被屏蔽用户的消息仍然会被其他插件和官方对话系统处理
> - 适用场景：屏蔽刷屏用户、机器人账号等
> - 支持字符串和数字类型的用户ID

#### 👆 戳一戳消息处理配置（v1.0.9 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poke_message_mode` | string | "bot_only" | **戳一戳消息处理模式** 🆕 v1.0.9<br>【仅支持QQ平台aiocqhttp】选择如何处理戳一戳消息：<br>- `ignore`: 忽略所有戳一戳消息<br>- `bot_only`: 只处理戳机器人自己的戳一戳消息<br>- `all`: 处理所有戳一戳消息（会添加提示词说明谁戳了谁） |
| `poke_bot_skip_probability` | bool | true | **戳机器人时跳过概率筛选** 🆕 v1.0.9增强<br>开启后，当戳一戳模式为bot_only或all，且戳的是机器人本身时，将跳过概率筛选（必定进入读空气判断），但仍保留读空气AI判断<br>关闭则戳一戳消息与普通消息一样需要通过概率筛选 |

> 💡 **戳一戳消息处理说明**:
> - **平台限制**: 仅支持QQ平台的aiocqhttp消息平台
> - **工作原理**: 
>   - `ignore`模式：本插件完全跳过戳一戳消息，不影响其他插件
>   - `bot_only`模式：只处理戳机器人的消息，AI会收到"[戳一戳提示]有人在戳你"的系统提示
>   - `all`模式：处理所有戳一戳，包括别人戳别人，AI会收到完整的戳一戳信息
> - **概率筛选跳过**: 
>   - 当`poke_bot_skip_probability`开启时，戳机器人会跳过概率筛选（不进行随机判断）
>   - 但仍会进行读空气AI判断，AI会决定是否真的需要回复
>   - 这样既保证了戳机器人有更高的响应率，又不会让每次戳一戳都必然回复
> - **AI理解**: AI能识别戳一戳事件并做出自然回应（如俏皮话、调侃等）
> - **系统提示**: 戳一戳提示词在缓存时保存，保存到正式历史时会被过滤
> - **防伪造机制** 🆕: 
>   - 自动检测并过滤手动输入的`[Poke:poke]`文本标识符
>   - 如果消息**只包含**`[Poke:poke]`（忽略空格），会被直接丢弃
>   - 如果消息**同时包含**`[Poke:poke]`和其他内容，会过滤掉标识符，保留其他内容
>   - 防止用户通过手动输入来伪造戳一戳消息，避免AI误判
>   - 支持各种变体（如`[ Poke : poke ]`、`[poke:poke]`等，大小写不敏感）
> - **最大兼容**: 不影响其他插件和官方功能
> - **推荐配置**: 
>   - 普通场景：`ignore`（忽略，避免误判）
>   - 互动场景：`bot_only`+`poke_bot_skip_probability=true`（默认，戳机器人时跳过概率，响应更积极）
>   - 监控场景：`all`（了解所有戳一戳互动）

#### 🚫 @他人消息过滤配置（v1.0.9 新增）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_ignore_at_others` | bool | false | **启用忽略@他人消息功能** 🆕 v1.0.9<br>开启后，可根据设定的模式自动忽略@了其他人（非机器人）的消息<br>即使消息包含触发关键词，也不会进行任何处理<br>关闭则不进行此项检测 |
| `ignore_at_others_mode` | string | "strict" | **@他人消息忽略模式** 🆕 v1.0.9<br>选择如何处理@他人的消息：<br>- `strict`: 只要检测到消息中@了其他人就直接忽略<br>- `allow_with_bot`: 如果消息中虽然@了他人但也@了机器人，则继续处理<br>需要先启用`enable_ignore_at_others`才生效 |

> 💡 **@他人消息过滤说明**:
> - **工作原理**:
>   - `strict`模式：消息中只要@了其他人（非机器人），本插件直接跳过
>   - `allow_with_bot`模式：消息中@了其他人，但如果也@了机器人，则继续处理
> - **适用场景**:
>   - 避免插入他人的私密对话（如安慰、询问等）
>   - 保持对话边界感，不干扰他人互动
>   - 减少不必要的AI触发
> - **检测逻辑**:
>   - 在黑名单检测之后、戳一戳检测之前执行
>   - 不影响其他插件和官方功能
>   - 过滤掉@全体成员（@all）的情况
> - **推荐配置**:
>   - 默认关闭（`enable_ignore_at_others: false`）
>   - 如需启用建议用`allow_with_bot`模式（保留@机器人时的响应能力）
>   - `strict`模式更严格，适合不希望AI参与任何@他人对话的场景

#### 🧠 情绪系统增强配置（v1.0.7 新增，v1.0.8 增强）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_negation_detection` | bool | true | **启用否定词检测**<br>开启后，情绪检测会识别否定词（如"不难过"不会被判定为"难过"）。强烈建议开启，避免情绪误判 |
| `negation_words` | list | ["不", "没", "别", ...] | **否定词列表**<br>用于情绪检测的否定词列表。当情绪关键词前出现这些词时，会忽略该关键词或反转情绪。可自定义添加(留空将使用默认配置) |
| `negation_check_range` | int | 5 | **否定词检查范围（字符数）**<br>在情绪关键词前检查多少个字符范围内是否有否定词。默认5个字符，可覆盖"一点也不开心"等情况 |
| `mood_keywords` | text | {...} | **情绪关键词配置**<br>各种情绪对应的关键词列表。可自定义添加或修改情绪类型和关键词(留空将使用默认配置)<br>默认包含：开心、难过、生气、惊讶、疑惑、无语、兴奋等情绪 |
| `mood_cleanup_threshold` | int | 3600 | **情绪记录清理阈值（秒）** 🆕 v1.0.8<br>群组情绪记录超过多长时间未更新将被清理，防止内存泄漏<br>设置为0可禁用自动清理<br>建议: 小型机器人7200秒(2小时)、中型3600秒(1小时)、大型1800秒(30分钟) |
| `mood_cleanup_interval` | int | 600 | **情绪记录清理检查间隔（秒）** 🆕 v1.0.8<br>多久检查一次并清理不活跃的群组情绪记录<br>设置过短会增加性能开销，设置过长可能导致内存占用偏高<br>建议: 300-1200秒 |

> 💡 **智能否定词检测说明**:
> - 默认开启，强烈建议保持开启状态
> - 支持检测"不"、"没"、"别"等常见否定词
> - 检测范围默认5个字符，可根据需要调整
> - 示例效果：
>   - "我很难过" → 检测为"难过"情绪
>   - "我不难过" → **不会**被检测为"难过"（被否定词过滤）
>   - "一点也不开心" → **不会**被检测为"开心"（检测范围内有否定词）
> - 可自定义情绪关键词，适配不同群聊风格

> 💾 **内存管理说明** (v1.0.8 新增):
> - **自动清理机制**: 超过阈值时间未活跃的群组情绪记录会被自动清理
> - **防止内存泄漏**: 长期运行后，不活跃群组的记录会逐步释放内存
> - **推荐配置**:
>   - 小型机器人(<20群): `mood_cleanup_threshold: 7200` (2小时)
>   - 中型机器人(20-100群): `mood_cleanup_threshold: 3600` (1小时，默认)
>   - 大型机器人(>100群): `mood_cleanup_threshold: 1800` (30分钟)
> - **禁用清理**: 设置 `mood_cleanup_threshold: 0` 可完全禁用（不推荐）
> - **性能影响**: 清理操作每10分钟执行一次，对性能影响极小

---

## 🔧 工作原理

### 完整处理流程

```
📨 收到群消息
    ↓
【高优先级】指令过滤处理器（v1.0.5新增，v1.1.2增强，priority=sys.maxsize-1）
    ├─ 只处理群消息
    ├─ 检查群组是否启用
    ├─ 【v1.0.5】启用指令过滤且匹配前缀？（如 `/help`、`!status`）
    │   └─ ✅ 是 → 生成消息ID并标记 → return（不阻止事件传播）
    ├─ 【v1.1.2新增】启用完整指令检测且匹配指令列表？（如单独的 `new`、`help`）
    │   ├─ 去除@组件和空白符后进行全字符串匹配
    │   ├─ `new` 匹配，但 `new你好` 不匹配
    │   └─ ✅ 是 → 生成消息ID并标记 → return（不阻止事件传播）
    ├─ ❌ 否 → 不标记，继续传递
    └─ 继续到普通处理器
    ↓
【普通处理器】群消息处理器
    ↓
【步骤0】检查消息标记（v1.0.5新增，v1.1.2增强）
    ├─ 消息ID在指令标记列表中？
    │   └─ ✅ 是 → 跳过处理（已被识别为前缀指令或完整指令）
    ├─  ❌ 否 → 继续正常处理
    ├─ 【v1.0.7新增】检查用户黑名单
    │   └─ 启用黑名单且用户在黑名单中？
    │      └─ ✅ 是 → 跳过处理（不阻止事件传播）
    ├─ 【v1.0.9新增】检查@他人消息过滤
    │   ├─ 启用`enable_ignore_at_others`？
    │   │   └─ ✅ 是 → 检测消息中的At组件
    │   │       ├─ `strict`模式：@了其他人（非机器人）？
    │   │       │   └─ ✅ 是 → 跳过处理（不阻止事件传播）
    │   │       └─ `allow_with_bot`模式：@了其他人但未@机器人？
    │   │           └─ ✅ 是 → 跳过处理（不阻止事件传播）
    │   └─  ❌ 否 → 继续处理
    ├─ 【v1.0.9新增】过滤伪造的戳一戳文本标识符
    │   ├─ 检测消息是否只包含`[Poke:poke]`标识符（忽略空格）？
    │   │   └─ ✅ 是 → 直接丢弃消息（不阻止事件传播）
    │   └─ ❌ 否 → 继续处理
    ├─ 【v1.0.9新增】检测并处理戳一戳消息（仅QQ平台aiocqhttp）
    │   ├─ 检查`poke_message_mode`配置
    │   ├─ `ignore`模式：检测到戳一戳？
    │   │   └─ ✅ 是 → 跳过处理（不阻止事件传播）
    │   ├─ `self_only`模式：检测到戳一戳？
    │   │   ├─ 戳的是机器人自己？
    │   │   │   ├─ ✅ 是 → 保存poke_info，继续处理（后续添加系统提示）
    │   │   │   └─ ❌ 否 → 跳过处理（不阻止事件传播）
    │   │   └─ ❌ 不是戳一戳 → 继续处理
    │   └─ `all`模式：检测到戳一戳？
    │       ├─ ✅ 是 → 保存poke_info，继续处理（后续添加系统提示）
    │       └─ ❌ 否 → 继续处理
    └─  ❌ 否 → 继续传递
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
    ├─ 是@消息？
    │   └─ ✅ 是 → 跳过概率判断
    ├─ 【v1.1.2新增】触发关键词且启用智能模式（keyword_smart_mode）？
    │   └─ ✅ 是 → 跳过概率判断（但保留读空气AI判断，让AI智能决定）
    ├─ 触发关键词且未启用智能模式？
    │   └─ ✅ 是 → 跳过概率判断
    ├─ 【v1.0.9增强】是戳机器人且开启poke_bot_skip_probability？
    │   └─ ✅ 是 → 跳过概率判断（但仍保留读空气AI判断）
    ├─ 【v1.1.2增强】是戳机器人但未开启poke_bot_skip_probability？
    │   └─ ✅ 是 → 增加额外概率（根据情绪、注意力动态计算）
    └─ ❌ 否 → 开始概率判断
        ├─ 获取当前概率（initial_probability或after_reply_probability）
        ├─ 【v1.1.0新增】应用回复时间段概率系数
        │   ├─ 当前时间命中配置的时间段？
        │   │   └─ ✅ 是 → 基础概率 × 时间段系数（提升或降低）
        │   └─ ❌ 否 → 使用默认基础概率
        ├─ 【v1.1.0新增】安静时段检查（Quiet Time）
        │   ├─ 命中安静时段？
        │   │   └─ ✅ 是 → 普通消息抑制（直接丢弃，不调用AI）
        │   │       └─ 注：@消息/触发关键词不受安静时段影响（仍优先）
        │   └─ ❌ 否 → 继续
        ├─ 【v1.1.0新增】概率硬限制检查（当期时间段内）
        │   ├─ 当前时间段已达到回复上限？
        │   │   └─ ✅ 是 → 直接丢弃（不调用AI）
        │   └─ ❌ 否 → 继续
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
        └─ ❌ 否 → 丢弃消息（保存消息到自定义存储（含元数据））
        └─ ✅ 是 → 继续
    ↓
【步骤5.5】检测@提及信息（v1.0.3 新增）
    ├─ 检查消息中是否包含@组件
    ├─ @的是机器人自己或@全体成员？
    │   └─ ✅ 是 → 跳过记录
    └─ ❌ 否 → 记录mention_info
        ├─ 保存被@用户的ID和昵称
        └─ 用于后续添加特殊标记
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
    ├─ 保存mention_info（v1.0.3，如果存在@别人的情况）
    ├─ 清理超过30分钟的旧消息
    └─ 限制缓存最多10条
    ↓
【步骤7.5】为当前消息添加元数据（用于发送给AI）
    ├─ 使用处理后的消息（图片已处理）
    ├─ 添加时间戳（可选，格式：2025年01月27日 15:30:45）
    ├─ 添加发送者信息（可选，格式：[发送者: 张三(ID: 123456)]）
    ├─ 检测mention_info（v1.0.3）
    │   └─ ✅ 存在@别人 → 添加特殊标记
    │       ├─【@指向说明】这条消息通过@符号指定发送给其他用户...
    │       └─【原始内容】实际消息内容
    ├─ 检测poke_info（v1.0.9新增，仅用于AI判断，不保存）
    │   └─ ✅ 存在戳一戳信息 → 添加特殊标记
    │       ├─ 戳机器人："[戳一戳提示]有人在戳你，戳你的人是：XXX(ID:XXX)"
    │       └─ 戳别人："[戳一戳提示]这条消息是别人在戳别人，不是别人在戳你。戳人的人是：XXX，被戳的人是：XXX"
    ├─ 添加发送者识别系统提示（v1.0.4新增，仅用于AI判断，不保存）
    │   └─ 根据触发方式添加不同提示：
    │       ├─ @消息："[系统提示]注意,现在有人在直接@你..."
    │       ├─ 关键词触发："[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息..."
    │       └─ AI主动回复将在后续判断后添加
    └─ ✅ 元数据添加完成（系统提示仅用于AI理解，不会保存到历史）
    ↓
【步骤8】提取历史上下文
    ├─ 从官方存储读取历史消息（基于 AstrBotMessage 结构，保留平台/发送者等信息）
    ├─ 合并缓存中的消息（去重）
    ├─ 应用max_context_messages限制
    └─ 格式化为AI可读文本：标记【你自己的历史回复】，在需要时注入主动对话标记和`[戳过对方提示]`（仅供AI理解，后续会被清理）
    ↓
【步骤9】决策AI判断
    ├─ 是@消息？
    │   └─ ✅ 是 → 跳过决策AI
    │       └─ 如果是@消息，检查是否已被其他插件处理
    ├─ 【v1.1.2新增】触发关键词且未启用智能模式？
    │   └─ ✅ 是 → 跳过决策AI（传统模式：必定回复）
    ├─ 【v1.1.2新增】触发关键词且启用智能模式（keyword_smart_mode）？
    │   └─ ✅ 是 → **保留决策AI判断**（智能模式：让AI决定）
    └─ ❌ 否 → 调用决策AI
        ├─ 构建完整提示词（含人格+上下文）
        ├─ 提示词包含特殊标记说明（v1.0.3）
        │   └─ 告知AI【@指向说明】标记的含义
        ├─ 调用AI判断（使用配置的超时时间 decision_ai_timeout）
        └─ 解析yes/no结果
            ├─ 超时 → 默认不回复，保存消息到自定义存储，退出
            ├─ ❌ no → 保存消息到自定义存储（含元数据），退出
            └─ ✅ yes → 继续
    ↓
【步骤10】标记会话
    └─ 添加到processing_sessions（用于after_message_sent识别）
    ↓
【步骤11】注入记忆（可选，v1.1.2增强）
    ├─ 启用记忆植入？
    └─ ✅ 是 → 自动检测记忆插件模式
        ├─ 【v1.1.2新增】LivingMemory模式（优先）
        │   ├─ 调用 astrbot_plugin_livingmemory
        │   ├─ 混合检索（相关性×重要性×新鲜度）
        │   ├─ 会话隔离 + 人格隔离
        │   └─ 支持动态人格切换
        ├─ Legacy模式（传统）
        │   └─ 调用 strbot_plugin_play_sy
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
    ├─ 构建完整消息（上下文+情绪+记忆[按重要性排序]+工具+额外提示词）
    ├─ 提示词包含特殊标记说明（v1.0.3）
    │   └─ 告知AI【@指向说明】标记的含义
    │   └─ 禁止AI在回复中提及系统标记和元信息
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
    ├─ 使用MessageCleaner清理系统提示（v1.0.4+v1.0.9+v1.1.1）
    │   └─ 过滤掉"[系统提示]"、"[戳一戳提示]"、"[戳过对方提示]"等内部标记，只保留原始消息内容
    ├─ 保存到自定义历史存储（data/chat_history/）
    └─ ✅ 保存完成（不包含临时系统提示）
    ↓
【步骤15】发送回复
    └─ yield 返回回复内容给用户
    ↓
【步骤15（并行）】调整读空气概率 / 记录注意力（v1.0.2增强，v1.1.2再次增强）
    ├─ 【v1.1.2新增】记录主动对话成功（智能自适应）
    │   ├─ 启用自适应主动对话且当前是主动对话的回复？
    │   │   └─ ✅ 是 → 记录成功互动、更新评分
    │   │       ├─ 基础加分：+15分
    │   │       ├─ 快速回复（30秒内）：+5分
    │   │       ├─ 多人回复：+10分
    │   │       ├─ 连续成功：+5分
    │   │       ├─ 低分复苏（<30分）：+20分
    │   │       └─ 清零连续失败次数，减少累积失败次数
    │   └─ ❌ 否 → 跳过
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
    ├─ 【v1.1.0新增】更新时间段统计与硬限制计数
    │   ├─ 回复成功 → 当期时间段计数+1
    │   ├─ 达到硬限制 → 该时间段内后续普通消息不再回复
    │   └─ 注：@消息不受硬限制影响（始终优先）
    ↓
【步骤16】检查并调整发言频率（v1.0.2 新增，v1.0.8 增强）
    ├─ 启用频率动态调整？
    └─ ✅ 是 → 检查是否到达检查间隔
        ├─ 条件1: 距离上次检查 > frequency_check_interval（默认180秒）
        ├─ 条件2: 消息数量 >= 8条
        └─ ✅ 满足条件 → 启动频率分析
            ├─ 收集最近N条对话记录（可通过frequency_analysis_message_count配置，默认15条）🆕 v1.0.8
            ├─ 调用AI判断发言频率（正常/过于频繁/过少）
            │   └─ 使用可配置的超时时间（frequency_analysis_timeout，默认20秒）🆕 v1.0.8
            ├─ 根据判断调整概率
            │   ├─ 过于频繁 → 降低15%（×0.85）
            │   ├─ 过少 → 提升15%（×1.15）
            │   └─ 正常 → 保持不变
            ├─ 限制概率范围（0.05-0.95）
            ├─ 调整后的新概率持续frequency_adjust_duration秒（默认360秒）🆕 v1.0.8
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
【主动聊天调度（v1.1.0新增，并行）】
    ├─ 定时器触发（每T秒）
    ├─ 过滤启用群组与安静时段（Quiet Time）
    ├─ 检查最近活跃度与失败冷却状态
    ├─ 计算主动发言概率：基础 × 时间段系数 × 临时加成
    ├─ 命中概率且未超硬限制？
    │   ├─ ✅ 是 → 构建系统提示，调用AI生成开场消息并发送
    │   └─ ❌ 否 → 跳过或进入冷却（提高失败计数/设置cooldown）
    ├─ 发送后更新计数与失败状态
    └─ 不影响@消息优先级与正常消息流程
    ↓
✅ 完成
```

### 主动聊天调度（v1.1.0 新增，v1.1.1 完善）

独立于消息的定时器调度，面向“主动社交”场景：

```
定时器触发（每 proactive_check_interval 秒）
    ↓
过滤群组（proactive_enabled_groups，如配置为空则所有启用群）
    ↓
检查静默阈值（proactive_silence_threshold）：群聊近期是否“足够安静”
    ↓
【v1.1.2新增】智能自适应参数计算（enable_adaptive_proactive）
    ├─ 根据互动评分（interaction_score，10-100分）调整参数
    ├─ 高分群聊（>70分）：沉默阈值×0.7、概率×1.5、最大失败次数×1.5
    ├─ 低分群聊（<30分）：沉默阈值×1.5、概率×0.5、最大失败次数×0.5
    └─ 极低分群聊（<20分）：进入冷淡期，显著抑制（×0.3）
    ↓
（可选）用户活动门槛（proactive_require_user_activity）
    ├─ 在窗口（proactive_user_activity_window）内统计发言数量
    └─ 不满最小值（proactive_min_user_messages）→ 不触发主动消息
    ↓
应用时间段系数（enable_dynamic_proactive_probability）
    ├─ 使用 proactive_time_periods 与平滑过渡（proactive_time_use_smooth_curve）
    └─ 系数范围由 proactive_time_min_factor / proactive_time_max_factor 约束
    ↓
安静时间抑制（proactive_enable_quiet_time）
    ├─ 处于 quiet_start ~ quiet_end 时间窗，主动概率渐退
    └─ 使用 proactive_transition_minutes 进行过渡
    ↓
临时提升维持期（proactive_temp_boost_probability / proactive_temp_boost_duration）
    ├─ 触发主动消息后，在一小段时间内提升后续普通回复概率，等待他人接话
    ├─ **维持期内不会再次触发新的主动开场**，避免自言自语式刷屏
    └─ 【v1.1.2增强】持续追踪回复用户，等待AI真正决定回复时才判定成功
    ↓
硬上限裁剪（enable_probability_hard_limit）
    └─ 按 probability_min_limit / probability_max_limit 对最终概率夹紧
    ↓
失败与冷却（proactive_max_consecutive_failures / proactive_cooldown_duration）
    ├─ 若维持期结束仍无人理会：记为一次失败尝试
    ├─ 【v1.1.2新增】累积失败次数独立追踪（total_proactive_failures）
    │   ├─ 用于吐槽系统的情绪累积，不受冷却重置影响
    │   └─ 成功互动时减少部分累积次数（complaint_decay_on_success）
    ├─ 连续失败次数达到上限 → 记录失败、更新评分（-8分）、进入冷却期
    └─ 冷却期结束前不再触发新的主动消息
    ↓
【v1.1.2新增】自动评分衰减（时间衰减）
    └─ 每24小时无主动对话尝试 → 自动扣2分（防止"吃老本"）
    ↓
调用决策AI（仅当最终概率通过）→ 根据模板生成主动开场 → 发送
    ↓
【v1.1.2新增】设置主动对话激活标记（proactive_active = True）
    └─ 只有发送成功后才激活，用于后续防误判检测
```

**v1.1.2 互动评分系统说明**：
- **成功互动加分**：基础+15分，快速回复+5分，多人回复+10分，连续成功+5分，低分复苏+20分
- **失败互动扣分**：基础-8分（无额外惩罚）
- **评分影响**：高分群聊更活跃（概率↑、阈值↓），低分群聊更克制（概率↓、阈值↑）
- **防误判机制**：只有AI真正决定回复时才判定成功，避免"用户回复但AI不理会"的误判

提示：主动聊天调度与消息驱动流程相互独立，不影响"@消息优先机制"。

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

说明（v1.1.0）：@消息的“必定处理与必定回复”逻辑保持不变，时间段与主动聊天功能不会影响此优先机制。

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

### 场景8: 戳一戳互动Bot（v1.0.9 新增）

**适用**: 希望Bot能识别和回应戳一戳互动的场景

```json
{
  "initial_probability": 0.15,
  "after_reply_probability": 0.25,
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "enable_attention_mechanism": true,
  "attention_increased_probability": 0.9,
  "attention_decreased_probability": 0.05,
  "decision_ai_extra_prompt": "你是一个活泼有趣的角色。当有人戳你时，可以用俏皮的方式回应，比如调侃对方、表达反应、或者开个小玩笑。保持轻松愉快的氛围。",
  "reply_ai_extra_prompt": "回应戳一戳时要自然俏皮，可以：1.调侃对方（如'干嘛呀，戳我干啥~'）2.表达反应（如'哎呀，吓我一跳'）3.开玩笑（如'戳我？小心我戳回去哦'）。不要太正式，保持轻松愉快。"
}
```

**说明**: 
- 仅支持QQ平台aiocqhttp
- `bot_only`模式：只响应戳机器人的情况，避免误判
- `poke_bot_skip_probability`开启：戳机器人时跳过概率筛选，响应更积极
- AI能识别戳一戳事件并做出自然回应
- 配合注意力机制，戳你的人会获得更多关注
- 适合增强群聊互动性的场景

### 场景9: 边界感保持Bot（v1.0.9 新增）

**适用**: 希望Bot不插入他人私密对话的场景

```json
{
  "initial_probability": 0.1,
  "after_reply_probability": 0.25,
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "enable_attention_mechanism": true,
  "decision_ai_extra_prompt": "你是一个有礼貌、懂分寸的助手。不要随意插入他人的私密对话（如安慰、询问等）。只在公开讨论或明确需要你参与时发言。保持边界感和礼貌。"
}
```

**说明**: 
- `allow_with_bot`模式：@了他人但也@了机器人时继续处理
- 避免AI插入"@某人 你还好吗"等私密对话
- 保持对话边界感，不干扰他人互动
- 减少不必要的AI触发，节省成本
- 适合多人活跃的群聊环境

### 场景10: 完整互动Bot（v1.1.1 全功能推荐）

**适用**: 希望启用所有互动增强功能（v1.0.9+v1.1.1）的场景

```json
{
  "initial_probability": 0.15,
  "after_reply_probability": 0.15,
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
  "enable_negation_detection": true,
  "enable_typing_simulator": true,
  "typing_speed": 15.0,
  "typing_max_delay": 3.0,
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 20,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 15,
  "mood_cleanup_threshold": 3600,
  "mood_cleanup_interval": 600,
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#"],
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "enable_poke_after_reply": true,
  "poke_after_reply_probability": 0.15,
  "poke_after_reply_delay": 0.5,
  "enable_poke_trace_prompt": true,
  "poke_trace_max_tracked_users": 5,
  "poke_trace_ttl_seconds": 300,
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "max_context_messages": -1,
  "include_timestamp": true,
  "include_sender_info": true
}
```

**说明**: 
- 包含所有真实感增强功能（v1.0.2）
- 智能否定词检测，避免情绪误判（v1.0.7）
- 频率分析精细控制，自适应调整（v1.0.8）
- 内存自动清理，长期运行稳定（v1.0.8）
- 指令自动过滤，避免误触发（v1.0.5）
- 支持戳一戳互动回应与回复后戳一戳，并通过`[戳过对方提示]`在短时间内持续跟进被戳用户（v1.0.9+v1.1.1）
- 保持对话边界感（v1.0.9）
- 最完整、最自然的配置方案，适合追求“像真人一样会互动、会记住刚被自己戳过谁”的场景

---

### 场景11：主动社交机器人（新群升温）

适用：刚建群或低活跃群，机器人主动找话题升温。

```json
{
  "enable_proactive_chat": true,
  "proactive_probability": 0.15,
  "proactive_check_interval": 60,
  "proactive_silence_threshold": 180,
  "proactive_enabled_groups": ["123456"],
  "proactive_require_user_activity": true,
  "proactive_min_user_messages": 2,
  "proactive_user_activity_window": 300,
  "enable_dynamic_proactive_probability": true,
  "proactive_time_periods": [
    {"start": "07:00", "end": "10:00", "factor": 1.2},
    {"start": "10:00", "end": "18:00", "factor": 1.0},
    {"start": "18:00", "end": "23:00", "factor": 0.8},
    {"start": "23:00", "end": "07:00", "factor": 0.4}
  ],
  "proactive_time_transition_minutes": 30,
  "proactive_time_min_factor": 0.5,
  "proactive_time_max_factor": 1.3,
  "proactive_time_use_smooth_curve": true,
  "proactive_enable_quiet_time": true,
  "proactive_quiet_start": "22:30",
  "proactive_quiet_end": "08:30",
  "proactive_transition_minutes": 30,
  "enable_probability_hard_limit": true,
  "probability_min_limit": 0.05,
  "probability_max_limit": 0.9,
  "proactive_max_consecutive_failures": 3,
  "proactive_cooldown_duration": 600
}
```

建议：先在少量群试跑，观测日志与体感后再扩大范围。

### 场景12：社交节奏增强（回复时间段+硬上限）

适用：白天更活跃、夜间更克制的需求，不影响@处理。

```json
{
  "enable_dynamic_reply_probability": true,
  "reply_time_periods": [
    {"start": "07:00", "end": "10:00", "factor": 1.2},
    {"start": "10:00", "end": "18:00", "factor": 1.0},
    {"start": "18:00", "end": "23:00", "factor": 0.8},
    {"start": "23:00", "end": "07:00", "factor": 0.5}
  ],
  "reply_time_transition_minutes": 30,
  "reply_time_min_factor": 0.6,
  "reply_time_max_factor": 1.3,
  "reply_time_use_smooth_curve": true,
  "enable_probability_hard_limit": true,
  "probability_min_limit": 0.05,
  "probability_max_limit": 0.9
}
```

说明：时间段系数在硬上限作用下被夹紧，避免异常概率。

### 场景13：安静时间与冷却（夜间克制）

适用：夜间群聊偶尔热闹但希望机器人不抢戏。

```json
{
  "enable_proactive_chat": true,
  "proactive_probability": 0.12,
  "proactive_check_interval": 90,
  "proactive_silence_threshold": 240,
  "proactive_require_user_activity": true,
  "proactive_min_user_messages": 1,
  "proactive_user_activity_window": 600,
  "proactive_enable_quiet_time": true,
  "proactive_quiet_start": "23:00",
  "proactive_quiet_end": "08:00",
  "proactive_transition_minutes": 45,
  "proactive_max_consecutive_failures": 2,
  "proactive_cooldown_duration": 900,
  "enable_probability_hard_limit": true,
  "probability_min_limit": 0.05,
  "probability_max_limit": 0.85
}
```

说明：冷却与安静时间叠加会显著降低夜间主动触发频率，利于休息氛围。

---

## 💡 提示词定制

更新说明（v1.1.0）：
- 默认系统提示词已升级，覆盖“氛围读取AI”和“最终回复AI”。建议用`append`方式仅补充人设与风格，不要删除系统段落。
- 回复中严禁出现任何“系统提示”“规则说明”“内部机制”“时间戳/ID”等元信息；模板已内置强约束，请勿移除。
- 新增戳一戳与【@指向说明】的处理约束已内置，定制时需保持一致；如需个性化可仅调整语气与人设，不改变约束逻辑。

### 决策AI提示词示例

#### 积极参与型
```
你是一个活跃、友好的群聊参与者，请判断是否回复当前这条新消息。

【第一重要】识别当前消息发送者：
⚠️ 在上面的【当前消息发送者】重要提醒中，已经明确告诉你当前给你发消息的人是谁。
- 请记住这个人的名字和ID，判断时不要搞错
- 历史消息中可能有多个用户的发言，请不要把历史中其他用户误认为当前发送者
- 判断是否回复时，要考虑与这个具体发送者的互动关系

【上下文说明】重要理解：
⚠️ 上下文中的消息已按时间顺序排列，形成完整的对话时间线
- 所有历史消息（包括你之前没有回复的消息）都会显示在上下文中，以便你理解完整的对话脉络
- 这些消息可能包含：你回复过的消息、你判断不回复的消息、以及其他人之间的对话
- **你需要识别：当前消息的发送者是在跟谁说话**
  * 如果是跟你说话：考虑回复
  * 如果是跟别人说话：一般不应插入（除非明确邀请你参与）
- **识别连续对话模式**：如果发现某个用户频繁发消息，但这些消息明显是在跟其他人对话（而非跟你），那么当前消息也很可能是跟别人说的

核心原则（重要！）：
1. **优先关注"当前新消息"的核心内容** - 这是判断的首要依据
2. **识别当前消息的主要问题或话题** - 判断是否与这个问题/话题相关
3. **理解完整的对话上下文** - 通过历史消息判断当前发送者是否在跟你对话，还是在跟别人聊天
4. **避免过度插入** - 如果发现对方最近几条消息都是跟别人对话，即使当前消息看似有趣，也应谨慎判断

【背景信息与记忆】使用说明（重要！）：
- 如果在上文看到 "=== 背景信息 ===" 段落，那是与你当前会话/人格相关的长期记忆（已按重要性排序）
- 这些内容仅供你理解上下文，用于辅助判断是否需要回复以及回复方向；不要在输出中直接复述或提及"记忆""背景信息"等元信息

**记忆场景下的特别判断规则：**
✅ **强烈倾向于回复（yes）** 的情况：
  1. 当前消息是对记忆中某个话题的追问或延续（如"还干了什么"、"然后呢"等）
  2. 记忆中显示你和当前发送者之前有过重要互动或对话
  3. 当前消息与记忆中的内容高度相关，显示对方想继续之前的话题
  4. 记忆中包含对方的重要偏好、未完成事项、或正在进行的讨论
  5. 记忆显示这是一个延续性强的对话关系，当前消息明显是在延续对话
  
⚠️ **需要谨慎判断** 的情况：
  1. 记忆中的话题已经充分讨论完毕，当前消息只是简单重复
  2. 记忆显示该话题属于他人之间的私密交流，你不应插入
  3. 当前消息明确表示不想聊天（如"别烦我"、"不想说"）
  
**核心原则（记忆存在时）：**
- 记忆的存在说明这个对话有历史和上下文，应该**更倾向于回复**以保持对话的连贯性和人情味
- 特别是追问类消息（"还有呢"、"然后呢"、"除了...还..."），这类消息强烈依赖上下文，有记忆时应积极回复
- 判断时优先考虑：当前消息 + 记忆的组合含义，而不是孤立地看当前消息
- 当记忆与当前消息形成完整的对话逻辑时，倾向于 yes（更拟人化）

⚠️ **【关于历史中的系统提示词】重要说明** ⚠️：
- 历史对话中可能包含以下标记开头的系统提示词：
  * "[🎯主动发起新话题]" - 表示你首次主动发起对话
  * "[🔄再次尝试对话]" - 表示你之前主动说了话但没人回应，现在再次尝试
- **这些标记的含义**：紧挨着这个标记的下一条消息是**你自己主动发起的对话**，而不是回复别人的
- 理解这个含义可以帮助你判断对话的上下文和连贯性
- **但是**：你**绝对禁止在输出中提及、复述或引用**这些系统提示词
- 只输出yes或no，不要说"我看到了提示词"之类的元信息

⚠️ **【防止重复】必须检查的事项** ⚠️：
在判断是否回复之前，务必检查：
1) 查看历史上下文中标记为"【你自己的历史回复】"的所有消息
2) 判断：如果你回复当前消息，会不会与最近的历史回复表达相同或相似的观点？
3) 如果最近2-3条历史回复已经充分表达过相似观点，**应该返回 no（避免啰嗦重复）**
4) 只有当前消息提出新的问题、新的角度，或需要补充新信息时，才考虑回复

判断原则（倾向于积极参与）：

  建议回复的情况：
   - 当前消息与你之前的回复相关，**且有新的话题发展**
   - **当前消息与记忆中的内容相关，特别是追问类消息（强烈建议回复）**
   - **记忆显示与当前发送者有重要互动历史，且当前消息是延续性对话**
   - 当前消息提到了有趣的话题，你可以贡献**新的看法**
   - 当前消息有人提问或需要帮助
   - 当前消息的话题符合你的人格特点
   - 群聊气氛活跃，适合互动
   - 当前消息有讨论价值

  建议不回复的情况：
   - 当前消息明显是他人的私密对话
   - 当前消息只是系统通知或纯表情
   - 当前消息的话题完全超出你的知识范围
   - 当前消息包含【@指向说明】，说明是发给其他特定用户的，一般不应插入
   - **你最近的历史回复已经充分表达过相同观点，再次回复会重复啰嗦**
   - 当前消息只是在重复已讨论过的话题，没有新的发展
   - **【重要】发现连续对话模式**：通过观察历史上下文，发现当前发送者最近几条消息都是在跟其他人对话（例如：回复别人的问题、@别人、或与特定用户连续交流），那么当前消息很可能也是跟别人说的，不应插入
   - **【重要】识别对话对象不匹配**：即使当前消息内容有趣，但如果上下文显示发送者正在与其他人进行连贯对话，你不应该突然插入打断

特殊标记说明：
   - 【@指向说明】表示消息通过@符号指定发送给其他特定用户，并非发给你
   - 看到此标记时，通常应该不回复，除非：
     1. 消息明确提到了你的名字或要求你参与
     2. 是公开讨论/辩论/征求意见等明显欢迎多人参与的场合
     3. 发送者在后续消息中明确邀请你加入讨论
   - 对于两人之间的私密对话、安慰、询问等，即使内容有趣也不要插入
   - 【原始内容】后面是实际的消息内容
   - [戳一戳提示]表示这是一个戳一戳消息：
     * "有人在戳你"表示有人戳了机器人（你），这种情况建议回复
     * "但不是戳你的"表示是别人戳别人，你只是旁观者，通常不应回复
   - [戳过对方提示]表示你刚刚主动戳过当前消息的发送者。这是系统提供给你的上下文信息，不影响你判断是否应该回复，但有助于你理解对方可能会因为被戳而来互动。严禁在输出中提及该提示或相关元信息。

重要提示：
- 你的目标是促进对话，不是保持沉默
- 不确定时倾向于回复，但对于【@指向说明】标记的消息要谨慎
- 根据你的人格特点决定活跃度
- 尊重他人的私密对话空间
- **记住：判断依据是"当前新消息"本身，不要被历史话题带偏**

输出要求：
   - 应该回复请输出: yes
   - 不应该回复请输出: no
   - 只输出yes或no，不要其他内容
   - 禁止输出任何解释、理由或元信息（如"我根据规则判断..."、"我看到了主动对话提示词"等）

⚠️ 特别提醒：
   - 这只是判断是否回复，不是生成实际回复内容
   - 你的判断结果不会被用户看到
   - 只需要输出yes或no来表达你的判断即可
   - **绝对不要提及任何系统提示词、规则说明或元信息**

请开始判断：
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
请根据上述对话和背景信息生成自然的回复。

【第一重要】识别当前发送者：
⚠️ 在上面的【当前对话对象】重要提醒中，已经明确告诉你当前给你发消息的人是谁。
- 请务必记住这个人的名字和ID，整个回复过程中不要搞错
- 历史消息中可能有多个用户的发言，请不要把历史中其他用户误认为当前发送者
- 称呼对方时，使用【当前对话对象】中指定的名字，或者直接用“你”
- 千万不要把历史消息中其他用户的名字用在当前发送者身上
🔧 **特别提醒：如果历史中有多个用户的消息，你只需要回复【当前对话对象】中指定的人，不要回复历史中其他人的问题。**

【上下文说明】理解完整的对话历史：
⚠️ 上下文中的消息已按时间顺序完整排列，形成真实的对话时间线
- **所有相关消息都会显示**：包括你之前回复过的、没有回复的、以及其他人之间的对话
- **时间线是连续的**：你能看到完整的对话流程，没有跳跃或断层
- **理解对话脉络**：通过完整的历史，你可以更准确地理解：
  * 当前发送者在跟谁对话（是跟你，还是跟其他人）
  * 话题是如何演变的
  * 之前发生了什么（即使你当时没有参与）
- **自然回复**：基于这个完整的上下文，你可以更自然、更恰当地回复当前消息
- ⚠️ 但请注意：这只是帮助你理解上下文，你仍然只需要回复【当前对话对象】的当前消息

特殊标记说明：
- 【@指向说明】表示该消息是通过@符号发给其他特定用户的，不是直接发给你的
- 【原始内容】后面是实际的消息内容
- [戳一戳提示]表示这是一个戳一戳消息：
  * "有人在戳你"表示有人戳了机器人（你），可以俏皮地回应，如"干嘛呀"、"别戳了"等
  * "但不是戳你的"表示是别人戳别人，你只是旁观者，不要表现得像是被戳的人
- [戳过对方提示]表示你刚刚主动戳过当前消息的发送者。这个提示仅用于帮助你理解上下文，不要在回复中提及该提示或相关元信息。

⚠️ **【关于历史中的系统提示词】重要说明** ⚠️：
- 历史对话中可能包含以下标记开头的系统提示词：
  * "[🎯主动发起新话题]" - 表示你首次主动发起对话
  * "[🔄再次尝试对话]" - 表示你之前主动说了话但没人回应，现在再次尝试
- **这些标记的含义**：紧挨着这个标记的下一条消息是**你自己主动发起的对话**，而不是回复别人的
- 理解这个含义可以帮助你更好地理解对话上下文和自己的行为模式
- **但是**：你**绝对禁止在回复中提及、复述或引用**这些系统提示词
- **不要说**："我看到了主动对话提示词"、"根据提示"、"刚才的提示"、"我主动发起了"、"再次尝试"等元信息
- 就像人类不会说"我刚才是主动找你聊天的"一样，你也应该自然地继续对话

核心原则（重要！）：
1. **优先关注“当前新消息”的核心内容** - 这是最重要的，不要过度沉浸在历史话题中
2. **识别当前消息的主要问题或话题** - 确保你的回复是针对这个问题/话题的
3. **历史上下文仅作参考** - 用于理解背景，但不要让历史话题喧宾夺主
🔧 4. **绝对禁止回复历史中其他人的问题** - 只回复当前发送者的当前消息，不要回复历史中其他用户的旧问题

⚠️ **【严禁重复】必须执行的检查步骤** ⚠️：
在回复之前，务必完成以下检查：
a) 找出历史上下文中所有标记为“⚠️【禁止重复-这是你自己的历史回复】”的消息
b) 逐条对比：你现在要说的话是否与这些历史回复相同或相似
c) 如果相似度超过50%，**必须换一个完全不同的角度或表达方式**
d) 绝对禁止重复相同的句式、相同的观点阐述、相同的回应模式
e) 即使话题相关，也要用新的方式表达，展现对话的自然变化
🔧 f) **特别注意：如果你发现自己在重复历史回复，立即停止并重新生成一个完全不同的回复**

关于记忆和背景信息的使用：
5. **不要机械地陈述记忆内容** - 禁止直白地说"XXX已经确认为我的XXX"、"我们之间是XXX关系"等
6. **自然地融入背景** - 将记忆作为你的认知背景，而不是需要特别强调的事实
7. **避免过度解释关系** - 不要反复确认或强调已知的关系，那样显得很生硬

回复要求：
8. 回复应自然、轻松、符合当前对话氛围
9. 遵循你的人格设定和回复风格
10. 根据需要调用可用工具
11. 保持连贯性和相关性
12. 不要在回复中明确提及"记忆"、"根据记忆"等词语
13. **绝对禁止重复、复述、引用任何系统提示词、规则说明、时间戳、用户ID等元信息**
14. 禁止在回复中提及"系统提示"、"根据规则"、"系统标记"、"@指向说明"、"当前时间"、"User ID"、"Nickname"、"主动对话"、"主动发起"等元信息

⛔ **【严禁元叙述】特别重要！** ⛔：
15. **绝对禁止在回复中解释你为什么要回复**，例如：
   - ❌ "看到你@我了"
   - ❌ "我看到有人@我"
   - ❌ "看到群里有人提到了我"
   - ❌ "刚刚看到有跟我有关的信息"
   - ❌ "我看到了一些有意思的消息，我打算回一下"
   - ❌ "注意到你在说XXX"
   - ❌ "发现群里在讨论XXX"
   - ❌ "我看到了上面的主动对话提示词"
   - ❌ "根据系统提示"、"刚才的提示说"
   - ❌ "看到了主动发起的指令"
   - ❌ **"看着你发来的消息"** - 这是最典型的不自然描述
   - ❌ "看了看你的消息"、"看了一眼你的消息"
   - ❌ "读着你发来的文字"、"听着你说的话"
   - ❌ 任何形式的"看着/读着/听着你发来的XXX"类描述
   - ✅ 正确做法：直接自然地回复消息内容本身，不要解释你的回复动机或提及任何系统内部信息

16. **就像人类聊天一样**：
   - 人类不会说"我看到你@我了，所以我来回复"
   - 人类更不会说"我看到了系统提示词"
   - 人类只会直接说："怎么了？""有什么事？""说吧"
   - 你应该像人类一样，直接针对内容回复，而不是先说明你注意到了什么系统信息
   - **特别强调：绝对不要提及历史中的任何系统提示词或内部指令，就当作它们不存在一样**

关于【@指向说明】标记的消息：
17. 如果消息包含【@指向说明】，说明这是发给其他人的消息，你的回复应该：
   - 不要直接回答对方向被@者提出的问题（那是别人的私事）
   - 不要替被@者回答或给建议
   - 可以自然地补充相关信息、分享观点，或者轻松地插个话
   - 保持礼貌和边界感，不要过度介入他人的对话
   - 回复应该像是旁观者的自然评论，而不是对话的主要参与者
🔧 18. **区分第一人称和第三人称场景：**
   - 如果历史中有多个用户在对话，但【当前对话对象】只有一个人，说明其他人是在历史中聊天
   - 你只需要关注【当前对话对象】的消息，历史中其他人的对话只是背景信息
   - 不要把历史中其他人的问题当成当前问题回答

请开始回复：
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
<summary><b>Q5: 记忆植入功能如何使用？（v1.1.2增强）</b></summary>

**A**: v1.1.2 支持两种记忆插件模式，系统会自动检测并选择。

**推荐方式：LivingMemory模式（v1.1.2新适配）**

1. 安装 `astrbot_plugin_livingmemory` 插件
2. 配置该插件并确保正常工作
3. 在本插件中设置：
   ```json
   {
     "enable_memory_injection": true,
     "memory_plugin_mode": "auto",  // 自动检测，优先LivingMemory
     "memory_top_k": 5  // 召回5条最重要的记忆
   }
   ```
4. 系统会自动：
   - 检测 LivingMemory 插件
   - 根据当前消息检索相关记忆
   - 按重要性×相关性×新鲜度排序
   - 注入到AI的输入中

**LivingMemory模式的优势**：
- ✅ **混合检索**：结合关键词、语义、时间多维度检索
- ✅ **智能总结**：自动总结长对话，提取关键信息
- ✅ **自动遗忘**：根据重要性和时间自动淡化旧记忆
- ✅ **会话隔离**：每个群聊的记忆独立
- ✅ **人格隔离**：支持多人格场景，避免人格记忆混淆
- ✅ **动态人格切换**：实时获取当前人格，支持切换人格后立即生效
- ✅ **智能排序**：记忆按综合得分排序，前面的更重要

**传统方式：Legacy模式**

1. 安装 `strbot_plugin_play_sy` 插件
2. 配置该插件并确保正常工作
3. 在本插件中设置 `enable_memory_injection` 为 `true`
4. 系统会自动检测并使用Legacy模式

**配置参数说明**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `memory_plugin_mode` | `"auto"` | 插件模式：`auto`/`livingmemory`/`legacy` |
| `memory_top_k` | `5` | LivingMemory召回数量，`-1`=全部 |

**注意事项**：
- 系统会优先检测 LivingMemory，未找到则回退到 Legacy
- 两种模式不能同时使用
- LivingMemory 模式需要 `astrbot_plugin_livingmemory >= 0.1.0`
- 记忆内容会以 `=== 背景信息 ===` 格式注入到 AI 输入中
</details>

<details>
<summary><b>Q5B: LivingMemory模式和Legacy模式有什么区别？（v1.1.2新增）</b></summary>

**A**: v1.1.2 支持两种记忆插件模式，它们有显著的技术和功能差异。

**功能对比表**：

| 特性 | LivingMemory模式（v1.1.2新增） | Legacy模式（传统） |
|------|----------------------------|-----------------|
| **插件** | `astrbot_plugin_livingmemory` | `strbot_plugin_play_sy` |
| **检索方式** | 混合检索（关键词+语义+时间） | 基于关键词 |
| **召回控制** | 支持（`memory_top_k`配置） | 不支持（全部返回） |
| **智能总结** | ✅ 自动总结长对话 | ❌ 不支持 |
| **自动遗忘** | ✅ 根据重要性和时间淡化 | ❌ 不支持 |
| **会话隔离** | ✅ 强制隔离 | 依赖插件配置 |
| **人格隔离** | ✅ 强制隔离 | ❌ 不支持 |
| **动态人格切换** | ✅ 实时获取当前人格 | ❌ 不支持 |
| **记忆排序** | ✅ 按重要性×相关性×新鲜度 | 按时间排序 |
| **重要性显示** | ✅ 星级显示（⭐-⭐⭐⭐⭐⭐） | ❌ 不显示 |
| **耦合方式** | 松耦合（公开API） | 紧密耦合（直接调用） |

**LivingMemory模式详解**：

**1. 混合检索机制**
```
用户消息: "昨天我们聊的那个游戏怎么样了？"
↓
LivingMemory 检索：
- 关键词匹配："游戏"
- 语义理解："昨天"+"聊过的"
- 时间过滤：优先返回昨天的记忆
- 综合排序：相关性 × 重要性 × 新鲜度
↓
返回：昨天关于游戏的最相关记忆（5条）
```

**2. 智能总结**
- 长对话自动总结为关键信息
- 提取核心要点，避免冗余
- 保留重要细节，丢弃琐碎内容

**3. 会话+人格双重隔离**
```
场景：多群聊 + 多人格

群A（人格：技术助手）：
- 记忆："用户喜欢Python"
- session_id: "aiocqhttp_group_123"
- persona_id: "技术助手"

群B（人格：闲聊伙伴）：
- 记忆："用户喜欢打游戏"
- session_id: "aiocqhttp_group_456"
- persona_id: "闲聊伙伴"

切换人格后：
- 群A 切换为"闲聊伙伴" → 立即获取"闲聊伙伴"的记忆
- 不会混入"技术助手"人格的记忆
```

**4. 智能排序示例**
```json
记忆列表（已按综合得分排序）：
[
  {
    "content": "用户的生日是3月15日",
    "importance": ⭐⭐⭐⭐⭐ (5/5),
    "relevance": 0.95,
    "freshness": 0.8,
    "综合得分": 0.95 × 1.0 × 0.8 = 0.76
  },
  {
    "content": "用户喜欢喝奶茶",
    "importance": ⭐⭐⭐ (3/5),
    "relevance": 0.8,
    "freshness": 0.9,
    "综合得分": 0.8 × 0.6 × 0.9 = 0.43
  },
  {
    "content": "昨天天气不错",
    "importance": ⭐ (1/5),
    "relevance": 0.3,
    "freshness": 1.0,
    "综合得分": 0.3 × 0.2 × 1.0 = 0.06
  }
]
```

**Legacy模式详解**：

**1. 简单调用**
```python
# 直接调用工具函数
memory = await get_memories_tool.handler(event=event)
```

**2. 适用场景**
- 简单的记忆需求
- 不需要人格隔离
- 单群聊场景
- 已有Legacy插件配置

**选择建议**：

**推荐使用LivingMemory的场景**：
- ✅ 多群聊环境
- ✅ 使用多人格功能
- ✅ 需要智能召回和排序
- ✅ 希望记忆有重要性区分
- ✅ 经常切换人格
- ✅ 群聊对话量大，需要智能总结

**继续使用Legacy的场景**：
- ✅ 简单的单群聊场景
- ✅ 已有Legacy插件且运行良好
- ✅ 不需要人格隔离功能
- ✅ 对记忆召回数量没有要求

**迁移建议**：

如果你正在使用Legacy模式，想升级到LivingMemory：

1. **安装LivingMemory插件**
   ```bash
   # 在AstrBot插件市场安装
   # 或手动下载：https://github.com/Soulter/astrbot_plugin_livingmemory
   ```

2. **配置LivingMemory**
   - 参考LivingMemory插件的配置文档
   - 确保插件正常工作

3. **调整本插件配置**
   ```json
   {
     "enable_memory_injection": true,
     "memory_plugin_mode": "auto",  // 自动检测，优先LivingMemory
     "memory_top_k": 5  // 新增：召回5条最重要的记忆
   }
   ```

4. **测试**
   - 发送消息，观察日志
   - 确认记忆正常召回
   - 检查记忆格式（应该包含星级显示）

5. **完成**
   - 系统会自动使用LivingMemory模式
   - Legacy插件可以保留或卸载

**注意事项**：
- 两种模式不能同时使用
- `memory_top_k` 仅对LivingMemory有效
- LivingMemory需要 `astrbot_plugin_livingmemory >= 0.1.0`
- 切换模式后，旧记忆不会自动迁移（两个插件的存储独立）
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
<summary><b>Q16: 频率动态调整会不会消耗很多API？（v1.0.8增强）</b></summary>

**A**: 消耗在可接受范围内：

**消耗情况**:
- 默认每3分钟（180秒）检查一次
- 每次调用消耗约500-1000 tokens（取决于对话历史长度）
- 每小时最多20次调用
- 如果使用便宜的模型（如GPT-3.5），成本几乎可忽略

**v1.0.8新增优化选项** 🆕:
1. **调整分析超时**：通过 `frequency_analysis_timeout` 控制AI分析时间（默认20秒）
   - AI响应慢时增加此值，避免频繁超时
2. **优化分析消息数**：通过 `frequency_analysis_message_count` 控制分析的消息数量（默认15条）
   - 减少此值可降低token消耗
   - 冷清群聊设置10-12条即可
3. **调整持续时间**：通过 `frequency_adjust_duration` 控制调整效果持续时间（默认360秒）
   - 增加此值可减少检查频率，降低API调用次数

**节省建议**:
1. 增加检查间隔：设置 `frequency_check_interval` 为300或更高
2. 减少分析消息数：设置 `frequency_analysis_message_count` 为10-12（v1.0.8新增）
3. 增加持续时间：设置 `frequency_adjust_duration` 为600或更高（v1.0.8新增）
4. 使用便宜的模型：这个判断不需要高级模型
5. 如果不需要：设置 `enable_frequency_adjuster: false` 关闭

**是否值得**:
- 如果希望Bot自适应群聊节奏：值得开启
- 如果预算紧张或群聊活跃度稳定：可以关闭
- v1.0.8的新配置项让你可以在性能和功能之间找到平衡点
</details>

<details>
<summary><b>Q17: 如何使用用户黑名单功能（v1.0.7新增）？</b></summary>

**A**: v1.0.7新增的用户黑名单功能

**功能说明**:
- 可以屏蔽特定用户，让本插件不处理其消息
- 黑名单仅对本插件生效，不影响其他插件和AstrBot官方功能
- 被屏蔽用户的消息仍然会被其他插件和官方对话系统正常处理

**配置方法**:
```json
{
  "enable_user_blacklist": true,
  "blacklist_user_ids": ["123456789", "987654321"]
}
```

**适用场景**:
- ✅ 屏蔽刷屏用户，避免AI被无意义消息触发
- ✅ 屏蔽机器人账号，避免bot之间互相对话
- ✅ 屏蔽特定干扰用户，提升群聊质量

**注意事项**:
- 黑名单只控制本插件行为，其他插件不受影响
- 支持字符串和数字类型的用户ID
- 留空则不屏蔽任何用户
- 被屏蔽用户的@消息也会被本插件忽略
</details>

<details>
<summary><b>Q18: 情绪系统的否定词检测如何工作（v1.0.7新增）？</b></summary>

**A**: v1.0.7增强的情绪系统否定词检测

**功能说明**:
- 智能识别否定词（如"不"、"没"、"别"等）
- 避免误判：将"不难过"误判为"难过"
- 检测关键词前N个字符（默认5个字符）内是否有否定词
- 默认启用，强烈建议保持开启

**工作原理**:
```
检测流程：
1. 发现情绪关键词（如"难过"）
2. 检查前5个字符内是否有否定词
3. 有否定词 → 忽略该关键词
4. 无否定词 → 正常计入情绪分数
```

**示例效果**:
- "我很难过" → 检测为"难过"情绪 ✅
- "我不难过" → **不会**被检测为"难过" ✅
- "一点也不开心" → **不会**被检测为"开心" ✅
- "不太开心" → **不会**被检测为"开心" ✅

**自定义配置**:
```json
{
  "enable_negation_detection": true,
  "negation_words": ["不", "没", "别", "一点也不", "根本不"],
  "negation_check_range": 5,
  "mood_keywords": {
    "开心": ["哈哈", "笑", "开心"],
    "难过": ["难过", "伤心", "哭"]
  }
}
```

**配置说明**:
- `enable_negation_detection`: 是否启用否定词检测（建议保持true）
- `negation_words`: 否定词列表（可自定义）
- `negation_check_range`: 检查范围（字符数）
- `mood_keywords`: 情绪关键词（可自定义情绪类型和关键词）

**注意事项**:
- 留空配置项将使用默认值（从 `_conf_schema.json` 读取）
- 检查范围越大，检测越准确，但可能过度过滤
- 建议保持默认配置，已经过优化
</details>

<details>
<summary><b>Q19: 如何从v1.0.1升级到v1.0.2和其他以上的版本？</b></summary>

**A**: 升级步骤：

1. **安装依赖**：`pip install pypinyin>=0.44.0`
2. **更新插件文件**：替换整个插件文件夹
3. **保留配置**：原有配置完全兼容，无需修改
4. **可选：添加新配置**：在配置中添加v1.0.2和其他以上的版本的新配置项（不加也能正常运行，使用默认值）
5. **重启插件**：重启AstrBot或重载插件

**注意事项**:
- v1.0.2和其他以上的版本完全向后兼容v1.0.1
- 所有新功能默认启用，如不需要可单独关闭
- 不会影响现有功能和配置
</details>

<details>
<summary><b>Q20: v1.0.4的发送者识别系统提示是什么？有什么用？</b></summary>

**A**: v1.0.4新增的发送者识别系统提示功能

**功能说明**:
- 根据消息触发方式（@消息、关键词、AI主动）添加不同的系统提示
- 帮助AI准确识别谁在说话，理解对话上下文
- 提升对话的连贯性和自然度

**三种触发方式的系统提示**:
1. **@消息触发**: "[系统提示]注意,现在有人在直接@你并且给你发送了这条消息，@你的那个人是XXX(ID:xxx)"
2. **关键词触发**: "[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息，这条消息的发送者是XXX(ID:xxx)"
3. **AI主动回复**: "[系统提示]注意，你刚刚看到了这条消息，你打算回复他，发送这条消息的人是XXX(ID:xxx)"

**使用效果**:
- ✅ AI清楚知道是被@、被关键词触发还是主动回复
- ✅ AI能准确识别发送者身份和意图
- ✅ 提升多人对话场景下的上下文理解
- ✅ 系统提示仅在当次判断和回复时起作用
- ✅ 历史记录保持干净，不包含临时系统提示

**配置要求**:
- 需要开启 `include_sender_info: true`（默认开启）
- 系统提示会自动添加，无需额外配置
- 完全向后兼容，不影响旧版配置

**技术细节**:
- 系统提示仅用于AI判断和生成回复时理解上下文
- 保存到历史消息时会被MessageCleaner过滤掉
- **不会持久化保存**，每次都根据触发方式动态生成
- 用户看不到系统提示，不影响最终回复内容
- 如果不需要可以关闭 `include_sender_info`
</details>

<details>
<summary><b>Q21: 如何使用指令过滤功能（v1.0.5新增）？</b></summary>

**A**: v1.0.5新增的指令标识过滤功能

**功能说明**:
- 使用高优先级处理器（priority=sys.maxsize-1）在最早阶段识别指令
- **核心技术**：检查原始消息链 `event.message_obj.message`，而非被修改过的 `event.message_str`
- 通过消息ID标记机制通知本插件的其他处理器跳过该消息
- 避免AI回复这些指令，减少不必要的API调用
- 完全不影响其他插件的正常工作（只标记不拦截，不调用 `event.stop_event()`）
- 自动清理超过10秒的旧标记，避免内存泄漏

**配置方法**:
```json
{
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#", ":"]
}
```

**支持的指令格式**:
1. 直接以前缀开头：`/help`、`!status`
2. @机器人后跟指令：`@机器人 /help`
3. 消息链中@后跟指令：`@[AT:123456] /command`

**适用场景**:
- ✅ 你安装了其他指令插件（如管理插件、工具插件）
- ✅ 不希望AI回复以特定前缀开头的消息
- ✅ 想要更精确地控制插件的触发范围

**注意事项**:
- 默认开启，如需可手动关闭 `enable_command_filter: false`
- 可以自定义指令前缀列表，留空则不过滤
- 只影响本插件，不影响其他插件的指令处理
</details>

<details>
<summary><b>Q22: v1.0.4的AI防重复机制如何工作？</b></summary>

**A**: v1.0.4对AI提示词进行了重大优化，增加防重复机制

**决策AI防重复**:
- 在判断是否回复前，检查历史上下文中的"【你自己的历史回复】"
- 如果最近2-3条回复已充分表达相同观点，判断为"不回复"
- 只有当前消息提出新问题、新角度时才考虑回复
- 避免AI啰嗦重复，保持对话精练

**回复AI防重复**:
- 找出历史上下文中所有"【你自己的历史回复】"
- 逐条对比：现在要说的话是否与历史回复相似
- 如果相似度>50%，必须换完全不同的角度或表达方式
- 绝对禁止重复相同句式、观点陈述、回应模式
- 即使话题相关也要用新方式表达

**严禁元叙述**:
- 绝对禁止说"看到你@我了"、"注意到你在说XXX"等元信息
- 要像人类一样直接回复内容，不解释回复动机
- 人类不会说"我看到你@我了，所以我来回复"
- 应该直接说"怎么了？""有什么事？"等自然回复

**使用效果**:
- ✅ AI不会重复表达相同观点
- ✅ 对话更自然、更有变化
- ✅ AI不会暴露内部逻辑
- ✅ 回复更像真人

**如何使用**:
- 自动生效，无需额外配置
- 已内置到默认提示词中
- 如果使用自定义提示词，建议参考README中的新提示词示例
</details>

<details>
<summary><b>Q23: v1.0.8的频率调整增强有什么用？如何配置？</b></summary>

**A**: v1.0.8对频率动态调整功能进行了精细化增强

**新增功能说明**:
v1.0.8新增了三个配置项，让频率调整功能更加灵活和高效：

1. **`frequency_analysis_timeout`（默认20秒）**
   - 控制AI分析发言频率时的超时时间
   - 解决问题：避免因AI响应慢导致分析超时
   - 使用建议：如果你的AI提供商响应较慢，可以增加到25-30秒

2. **`frequency_adjust_duration`（默认360秒）**
   - 控制频率调整后的新概率持续多长时间
   - 解决问题：让概率调整更稳定，避免频繁跳变
   - 使用建议：建议设置为检查间隔的2倍左右（如检查间隔180秒，持续时间设360秒）

3. **`frequency_analysis_message_count`（默认15条）**
   - 控制分析发言频率时获取多少条最近消息
   - 解决问题：灵活适应不同活跃度的群聊
   - 使用建议：
     - 活跃群聊：20-30条（更准确的判断）
     - 中等群聊：15条（默认值）
     - 冷清群聊：10-12条（减少token消耗）

**配置示例**:

**场景1：AI响应慢的情况**
```json
{
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 30,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 15
}
```

**场景2：活跃群聊，需要精准判断**
```json
{
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 180,
  "frequency_analysis_timeout": 20,
  "frequency_adjust_duration": 360,
  "frequency_analysis_message_count": 25
}
```

**场景3：冷清群聊，节省API消耗**
```json
{
  "enable_frequency_adjuster": true,
  "frequency_check_interval": 300,
  "frequency_analysis_timeout": 20,
  "frequency_adjust_duration": 600,
  "frequency_analysis_message_count": 10
}
```

**使用效果**:
- ✅ 更精确地控制频率调整行为
- ✅ 避免AI分析超时影响主流程
- ✅ 概率调整更稳定，不会频繁跳变
- ✅ 灵活适应不同活跃度的群聊
- ✅ 性能更可控，可根据实际情况优化token消耗

**升级说明**:
- 从v1.0.7升级到v1.0.8无需修改任何配置
- 新配置项会自动使用默认值
- 如需优化可按需调整上述配置项
- 100%向后兼容
</details>

<details>
<summary><b>Q24: 情绪系统的内存清理机制如何工作（v1.0.8新增）？</b></summary>

**A**: v1.0.8新增了情绪系统内存清理机制，防止长期运行导致的内存泄漏

**问题背景**:
- 之前版本中，每个群组的情绪记录会永久保留在内存中
- 如果机器人加入了大量群组，长期运行后内存占用会持续增长
- v1.0.8添加了自动清理机制解决这个问题

**工作原理**:
```
1. 每个群组有独立的情绪记录（情绪状态、强度、最后更新时间）
2. 定期检查（默认每10分钟）所有群组的情绪记录
3. 清理超过阈值时间（默认1小时）未更新的群组记录
4. 活跃群组的记录会一直保留
5. 清理后如果群组再次活跃，会自动重新创建记录
```

**新增配置项**:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `mood_cleanup_threshold` | 3600 | 清理阈值（秒），超过此时间未更新的群组会被清理 |
| `mood_cleanup_interval` | 600 | 检查间隔（秒），多久检查一次 |

**推荐配置**:

**小型机器人（<20个群）**:
```json
{
  "mood_cleanup_threshold": 7200,
  "mood_cleanup_interval": 1200
}
```

**中型机器人（20-100个群，默认配置）**:
```json
{
  "mood_cleanup_threshold": 3600,
  "mood_cleanup_interval": 600
}
```

**大型机器人（>100个群）**:
```json
{
  "mood_cleanup_threshold": 1800,
  "mood_cleanup_interval": 300
}
```

**禁用自动清理（不推荐）**:
```json
{
  "mood_cleanup_threshold": 0
}
```

**使用效果**:
- ✅ 防止内存泄漏，长期运行内存占用稳定
- ✅ 自动释放不活跃群组的记录
- ✅ 活跃群组不受影响，情绪记录一直保留
- ✅ 性能影响极小（每10分钟检查一次，耗时<1ms）
- ✅ 灵活配置，适应不同规模的机器人

**监控日志**:
当清理发生时，会在日志中看到：
```
[情绪追踪-内存清理] 已清理 5 个不活跃群组的情绪记录 (超过 1.0 小时未活跃)
```

**常见问题**:
- Q: 清理会影响当前活跃的群组吗？
  - A: 不会，只清理超过阈值时间未更新的群组
- Q: 清理后群组再次活跃会怎样？
  - A: 会自动重新创建记录，从默认情绪（平静）开始
- Q: 我需要保留完整的情绪历史怎么办？
  - A: 设置 `mood_cleanup_threshold: 0` 禁用清理（不推荐长期使用）

</details>

<details>
<summary><b>Q25: 戳一戳消息处理功能如何使用（v1.0.9新增）？</b></summary>

**A**: v1.0.9新增了戳一戳消息处理功能，让AI能识别和回应戳一戳互动

**功能介绍**:
- **平台限制**: 仅支持QQ平台的aiocqhttp消息平台
- **智能识别**: 自动检测戳一戳事件并区分戳机器人和戳别人
- **AI理解**: AI能收到清晰的系统提示词，理解戳一戳互动

**三种处理模式**:

**1. ignore模式（忽略）**:
```json
{
  "poke_message_mode": "ignore"
}
```
- 完全忽略所有戳一戳消息
- 本插件跳过处理，不影响其他插件
- 适合不希望AI回应戳一戳的场景

**2. bot_only模式（默认，推荐）**:
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true
}
```
- 只处理戳机器人自己的戳一戳消息
- AI收到提示：`[戳一戳提示]有人在戳你，戳你的人是：XXX(ID:XXX)`
- `poke_bot_skip_probability`开启时，戳机器人会跳过概率筛选，响应更积极
- 仍会进行读空气AI判断，不会每次戳必然回复
- 别人戳别人的消息会被跳过
- 适合希望AI能回应戳一戳但避免误判的场景

**3. all模式（监控场景）**:
```json
{
  "poke_message_mode": "all"
}
```
- 处理所有戳一戳消息，包括别人戳别人
- AI收到详细提示，区分戳机器人和戳别人
- 适合需要监控群内所有戳一戳互动的场景

**AI回复效果**:
- 决策AI会判断是否需要回复戳一戳（考虑氛围和关系）
- 回复AI会生成自然的回应（如俏皮话、调侃、表达反应等）
- 系统提示词在保存到正式历史时会被自动过滤

**使用示例**:
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "initial_probability": 0.15,
  "after_reply_probability": 0.3
}
```

**注意事项**:
- ❌ 不支持其他平台（微信、Telegram等）
- ✅ 系统提示词自动过滤，不会污染历史记录
- ✅ 不影响其他插件和官方功能
- ✅ 可随时切换模式，立即生效

**常见问题**:
- Q: 为什么我的平台不支持？
  - A: 戳一戳功能依赖QQ平台特有的poke事件，其他平台不支持
- Q: 戳一戳提示词会保存到历史吗？
  - A: 不会，缓存时保存，转正时自动过滤
- Q: 可以自定义AI的戳一戳回复吗？
  - A: 可以通过`reply_ai_extra_prompt`添加额外提示，引导AI回复风格
- Q: `poke_bot_skip_probability`是什么意思？
  - A: 开启后，戳机器人时会跳过概率筛选（不进行随机判断），但仍保留读空气AI判断。这样既提高了响应率，又不会每次都回复
- Q: 戳机器人时一定会回复吗？
  - A: 不一定。即使跳过概率筛选，仍会进行读空气AI判断。AI会根据上下文、氛围等因素决定是否回复
- Q: 用户手动输入`[Poke:poke]`会怎么样？
  - A: 插件会自动检测并过滤。如果消息只包含这个标识符（忽略空格），会被直接丢弃；如果同时包含其他内容，会过滤掉标识符保留其他内容。这样可以防止用户伪造戳一戳消息

</details>

<details>
<summary><b>Q26: @他人消息过滤功能如何使用（v1.0.9新增）？</b></summary>

**A**: v1.0.9新增了@他人消息过滤功能，避免AI插入他人私密对话

**功能介绍**:
- **智能检测**: 自动识别消息中的At组件，区分@机器人和@其他人
- **边界感保持**: 避免AI插入他人的安慰、询问等私密对话
- **最大兼容**: 仅本插件跳过处理，不影响其他插件

**配置说明**:

**默认配置（功能关闭）**:
```json
{
  "enable_ignore_at_others": false
}
```
- 不进行@他人消息过滤
- 插件正常处理所有消息
- 适合大部分场景

**启用strict模式（严格模式）**:
```json
{
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "strict"
}
```
- 只要消息中@了其他人（非机器人），就直接跳过
- 即使消息也@了机器人，也会跳过
- 适合希望AI完全不参与任何@他人对话的场景

**启用allow_with_bot模式（宽松模式，推荐）**:
```json
{
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot"
}
```
- 消息中@了其他人，但如果也@了机器人，则继续处理
- 只有纯@他人（不含@机器人）的消息才会跳过
- 适合希望保持边界感但不影响@机器人功能的场景（推荐）

**典型场景**:

**场景1: 私密对话**
```
用户A: @用户B 你最近怎么样？还好吗？
```
- strict模式：跳过（@了其他人）
- allow_with_bot模式：跳过（未@机器人）
- 效果：AI不会插入这种私密询问

**场景2: 群聊讨论**
```
用户A: @机器人 @用户B 你们觉得这个方案怎么样？
```
- strict模式：跳过（@了其他人）
- allow_with_bot模式：**继续处理**（也@了机器人）
- 效果：AI可以参与这种明确希望它参与的讨论

**场景3: 纯@机器人**
```
用户A: @机器人 今天天气怎么样？
```
- strict模式：继续处理（只@了机器人）
- allow_with_bot模式：继续处理（只@了机器人）
- 效果：正常回复

**推荐配置**:
```json
{
  "enable_ignore_at_others": true,
  "ignore_at_others_mode": "allow_with_bot",
  "initial_probability": 0.1,
  "after_reply_probability": 0.25
}
```

**使用效果**:
- ✅ 避免AI插入他人的安慰、询问等私密对话
- ✅ 保持对话边界感，不干扰他人互动
- ✅ 减少不必要的AI触发，节省成本
- ✅ 不影响@机器人的功能（allow_with_bot模式）
- ✅ 不影响其他插件和官方功能

**注意事项**:
- 🔹 默认关闭，需要手动启用
- 🔹 推荐使用allow_with_bot模式（保留@机器人时的响应能力）
- 🔹 @全体成员（@all）会被自动过滤，不影响此功能
- 🔹 仅本插件跳过处理，其他插件仍可正常接收消息

**常见问题**:
- Q: 为什么默认关闭？
  - A: 此功能改变了插件的默认行为，可能不适合所有场景
- Q: strict和allow_with_bot有什么区别？
  - A: strict更严格（@了其他人就跳过），allow_with_bot更灵活（也@了机器人则继续）
- Q: 会影响关键词触发吗？
  - A: 会，即使消息包含触发关键词，只要@了其他人就会跳过（根据模式）

</details>

---

<details>
<summary><b>Q27: 主动聊天为什么不触发？（v1.1.0）</b></summary>

**A**: 逐项排查：

- 功能未启用：`enable_proactive_chat` 必须为 `true`
- 群未匹配：如配置了 `proactive_enabled_groups`，不在列表的群不会触发
- 群不够安静：当前群未达到 `proactive_silence_threshold`（秒）
- 活动门槛未达成：开启了 `proactive_require_user_activity` 但在 `proactive_user_activity_window` 内消息数量未达到 `proactive_min_user_messages`
- 处于安静时间：`proactive_enable_quiet_time` 开启且当前在 `proactive_quiet_start`~`proactive_quiet_end` 范围内（会抑制主动概率）
- 时间段系数过低：`enable_dynamic_proactive_probability` 开启后，当前时间段 `factor` 可能降低到较低值
- 被硬上限夹紧：`enable_probability_hard_limit` 开启后，最终概率会被 `probability_min_limit`/`probability_max_limit` 限制
- 冷却中：连续失败达到 `proactive_max_consecutive_failures` 后进入 `proactive_cooldown_duration` 冷却期

补充说明（v1.1.1）：
- 主动聊天在触发后会进入一个“等待回应+临时概率提升”的维持期，在此期间不会重复触发新的主动开场，以免显得过于执着或刷屏。
- 只有在维持期结束仍无人理会时，才按 `proactive_max_consecutive_failures` / `proactive_cooldown_duration` 的配置进行连续尝试和冷却统计，修复了早期版本中“自动重试/冷却配置难以生效”的问题，使整体节奏更自然。

**建议**：打开日志并关注“Proactive Chat Manager”相关行；先在单群试跑并提高 `proactive_probability` 验证流程正常。
</details>

<details>
<summary><b>Q28: 时间段概率是怎么计算的？（v1.1.0）</b></summary>

**A**: 以回复概率为例（主动概率同理）：

- 启用 `enable_dynamic_reply_probability`
- 在 `reply_time_periods` 中定义时间窗与 `factor`
- 切换时间窗时按 `reply_time_use_smooth_curve` 与 `reply_time_transition_minutes` 平滑过渡
- 最终概率 = `clamp(base_probability × factor, probability_min_limit, probability_max_limit)`

示例：`base=0.15`，早间 `factor=1.2` → `0.18`；夜间 `factor=0.5` → `0.075`，如设置 `probability_min_limit=0.08` 则被夹为 `0.08`.
</details>

<details>
<summary><b>Q29: 概率硬上限会影响哪些场景？（v1.1.0）</b></summary>

**A**: 全局作用，统一夹紧所有最终概率：

- 影响回复概率与主动概率（均在最终阶段裁剪）
- 与时间段系数叠加后再裁剪，避免异常高/低值
- 不影响 @ 消息的必定处理与必定回复逻辑

配置要点：
- 开启 `enable_probability_hard_limit`
- 设置 `probability_min_limit` 与 `probability_max_limit`（建议 `0.05` 与 `0.85~0.9`)
</details>

<details>
<summary><b>Q30: 安静时间如何设置？与主动概率如何协同？（v1.1.0）</b></summary>

**A**: 安静时间用于抑制夜间主动行为：

- 开启 `proactive_enable_quiet_time`
- 设置 `proactive_quiet_start`/`proactive_quiet_end`（支持跨午夜，例如 `22:30` 到 `08:30`）
- 用 `proactive_transition_minutes` 控制渐入/渐出，避免突变
- 与 `enable_dynamic_proactive_probability` 共存：时间段系数先作用，安静时间再抑制，最后由硬上限裁剪

建议：夜间使用较低 `factor`（如 `0.4~0.6`）并开启安静时间，形成双重克制。
</details>

<details>
<summary><b>Q31: 如何使用插件重置指令切换人格？（v1.1.1新增）</b></summary>

**A**: v1.1.1新增了两个重置指令，配合AstrBot官方指令可以完美切换人格：

**重置指令说明**：
- `gcp_reset`：**插件级重置** - 清空本插件全局缓存并触发重载/重启
- `gcp_reset_here`：**会话级重置** - 仅清理当前群的本插件状态与本地缓存

**切换人格的推荐流程**：

1. **第一步：清空AstrBot官方历史记录**
   ```
   /reset
   ```
   或其他AstrBot官方的清空历史指令

2. **第二步：根据情况选择插件重置指令**
   - **完全切换人格**（推荐）：`gcp_reset`
     - 清空所有群的注意力、情绪、主动对话等数据
     - 适用于：更换全新人格、大幅调整配置后
   - **仅当前群切换**：`gcp_reset_here`
     - 只清空当前群的插件数据，其他群不受影响
     - 适用于：单群测试新人格、保留其他群的互动记录

**使用场景**：
- ✅ **切换新人格**：避免新人格被旧的注意力、情绪数据污染
- ✅ **调整重要配置后**：如修改提示词、概率设置等
- ✅ **AI出现胡言乱语**：清理可能的异常状态数据
- ✅ **测试不同配置**：在单群测试时使用`gcp_reset_here`

**权限控制**：
- 通过 `plugin_reset_allowed_user_ids` 配置允许使用重置指令的用户
- 留空 `[]` = 允许所有用户使用（默认）
- 填写用户ID = 仅指定用户可使用

**注意事项**：
- 重置指令只清理本插件的数据，不影响AstrBot官方历史
- 建议先用官方指令清历史，再用插件指令清状态
- `gcp_reset`会影响所有群，请谨慎使用
- 重置后AI需要重新建立注意力和情绪关系

**示例操作**：
```
用户: /reset                    # 清空官方历史
机器人: 已清空对话历史
用户: /gcp_reset                 # 清空插件数据
机器人: 插件已重置，所有缓存已清空
用户: 你好，我是新的主人        # 开始新人格对话
```
</details>

<details>
<summary><b>Q32: 什么是关键词智能模式？如何使用？（v1.1.2新增）</b></summary>

**A**: 关键词智能模式是 v1.1.2 新增的功能，用于解决传统关键词触发的"机械式回复"问题。

**传统模式 vs 智能模式对比**：

| 特性 | 传统模式（默认） | 智能模式（v1.1.2新增） |
|------|-----------------|---------------------|
| 配置 | `keyword_smart_mode: false` | `keyword_smart_mode: true` |
| 触发行为 | 关键词 → 必定回复（机械式） | 关键词 → AI判断是否回复（智能） |
| 概率判断 | 跳过 | 跳过 |
| AI读空气判断 | 跳过 | **保留** |
| 优点 | 响应快速、确定性高 | 更智能、更自然，避免误触发 |
| 缺点 | 可能误触发 | 需要额外的AI判断调用 |

**使用场景示例**：

**问题场景**（传统模式）：
```
用户A: 我需要帮助处理这个文件
Bot: 有什么可以帮助你的吗？   # 误触发"帮助"关键词

用户B: 请问机器人怎么重启？
Bot: 我在这里！             # 误触发"机器人"关键词，但问的是其他机器人
```

**解决方案**（智能模式）：
```json
{
  "trigger_keywords": ["帮助", "机器人", "问题"],
  "keyword_smart_mode": true
}
```

此时：
- 用户说"帮助"时 → 跳过概率判断 → AI分析上下文 → 判断是否真的在叫你
- 避免在"我需要**帮助**处理文件"（跟别人说的）时插入对话
- 但在"**机器人**你好"（明确叫你）时正常回复

**配置建议**：
- ✅ **启用条件**：使用了宽泛的关键词（如"帮助"、"问题"），且希望减少误触发
- ✅ **不启用条件**：关键词非常精确（如Bot的专属昵称），追求响应速度
- ⚠️ **注意**：智能模式需要额外的AI调用，会增加API成本和响应延迟

**完整配置示例**：
```json
{
  "trigger_keywords": ["小助手", "帮忙", "问一下"],
  "keyword_smart_mode": true,
  "decision_ai_extra_prompt": "当用户说'帮忙'时，判断他们是否真的在向你求助，还是只是在跟别人聊天中提到了这个词。"
}
```
</details>

<details>
<summary><b>Q33: 完整指令检测与前缀指令检测有什么区别？（v1.1.2新增）</b></summary>

**A**: v1.1.2 新增的完整指令检测与 v1.0.5 的前缀指令检测互补，覆盖不同的指令格式。

**两种检测模式对比**：

| 特性 | 前缀指令检测（v1.0.5） | 完整指令检测（v1.1.2新增） |
|------|---------------------|----------------------|
| 配置项 | `enable_command_filter` | `enable_full_command_detection` |
| 参数 | `command_prefixes` | `full_command_list` |
| 匹配规则 | 消息**开头**匹配前缀 | 消息**完整**匹配指令 |
| 典型格式 | `/help`、`!status`、`#reset` | `new`、`help`、`reset` |
| 示例匹配 | `/help` ✅ `/help123` ✅ | `new` ✅ `new你好` ❌ |
| @处理 | 不处理@ | 自动去除@和空白符 |

**工作原理示例**：

**前缀指令检测**（v1.0.5）：
```json
{
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#"]
}
```
- `"/help"` → 识别为指令 ✅
- `"!status"` → 识别为指令 ✅
- `"help"` → 不识别 ❌（没有前缀）
- `"/help 我需要帮助"` → 识别为指令 ✅

**完整指令检测**（v1.1.2）：
```json
{
  "enable_full_command_detection": true,
  "full_command_list": ["new", "help", "reset", "clear"]
}
```
- `"new"` → 识别为指令 ✅
- `"help"` → 识别为指令 ✅
- `"new你好"` → 不识别 ❌（不是完整匹配）
- `"@机器人 new"` → 识别为指令 ✅（自动去除@）
- `"  help  "` → 识别为指令 ✅（自动去除空白符）
- `"new session"` → 不识别 ❌（包含额外内容）

**推荐配置**（两者结合使用）：
```json
{
  "enable_command_filter": true,
  "command_prefixes": ["/", "!", "#", ":"],
  "enable_full_command_detection": true,
  "full_command_list": ["new", "help", "reset", "clear", "查询", "设置"]
}
```

这样可以同时过滤：
- 带符号的指令：`/help`、`!status`
- 不带符号的指令关键词：`new`、`help`
- 中文指令：`查询`、`设置`

**适用场景**：
- ✅ **前缀检测**：适合过滤明确的命令行风格指令
- ✅ **完整检测**：适合过滤简短的指令关键词（如LLM的`new`、`continue`等）
- ✅ **两者结合**：覆盖更全面，减少误触发

**注意事项**：
- 完整指令检测是**全字符串匹配**，不会误伤正常对话
- 例如：`"new"` 会被过滤，但 `"new year"` 和 `"renew"` 不会
- 建议只添加常见的、简短的指令关键词到列表中
</details>

<details>
<summary><b>Q34: 智能自适应主动对话是如何工作的？（v1.1.2新增）</b></summary>

**A**: 智能自适应主动对话是 v1.1.2 的核心新功能，让Bot根据群聊互动质量自动调整活跃度。

**核心机制**：

```
互动评分系统（10-100分）
    ↓
根据评分调整参数
    ↓
越聊越开心 / 冷场自动收敛
```

**互动评分计算**：

**成功互动加分**：
- 基础加分：`+15` 分（可配置 `score_increase_on_success`）
- 快速回复（30秒内）：`+5` 分
- 多人回复：`+10` 分
- 连续成功：`+5` 分
- 低分复苏（<30分）：`+20` 分

**失败互动扣分**：
- 基础扣分：`-8` 分（可配置 `score_decrease_on_fail`）
- 无额外惩罚

**评分影响Bot行为**：

| 评分范围 | Bot状态 | 参数调整 |
|---------|--------|---------|
| **>70分** | 🔥高度活跃 | 沉默阈值×0.7，概率×1.5，失败次数上限×1.5 |
| **50-70分** | 😊正常活跃 | 使用原始参数 |
| **30-50分** | 😐逐渐克制 | 根据评分线性调整 |
| **20-30分** | 😔明显克制 | 沉默阈值×1.5，概率×0.5，失败次数上限×0.5 |
| **<20分** | 😞冷淡期 | 显著抑制（×0.3），几乎不主动 |

**自动衰减机制**：
- 每24小时无主动对话尝试 → 自动扣2分
- 防止"吃老本"，确保评分反映当前状态

**防误判机制**：
- 只有AI**真正决定回复**时才判定成功
- 避免"用户回复了但AI不理会"的误判

**完整配置示例**：
```json
{
  "enable_proactive_chat": true,
  "proactive_silence_threshold": 600,
  "proactive_probability": 0.2,
  
  "enable_adaptive_proactive": true,
  "score_increase_on_success": 15,
  "score_decrease_on_fail": 8,
  "interaction_score_min": 10,
  "interaction_score_max": 100
}
```

**实际效果示例**：

**场景1：活跃群聊**
```
初始评分: 50分
Bot主动: "大家今天过得怎么样？"
用户A: "还不错！" (15秒内回复)
用户B: "挺好的"

评分更新: 50 + 15(基础) + 5(快速) + 10(多人) = 80分
下次主动: 沉默阈值从600秒降至420秒，概率从0.2提升至0.3
结果: Bot变得更活跃，更频繁主动
```

**场景2：冷淡群聊**
```
初始评分: 50分
Bot主动: "有什么有趣的话题吗？"
(无人回复120秒)

评分更新: 50 - 8 = 42分
Bot再次主动: "今天天气不错啊"
(依然无人回复)

评分更新: 42 - 8 = 34分
下次主动: 沉默阈值从600秒升至约750秒，概率从0.2降至约0.15
结果: Bot变得更克制，减少主动频率
```

**与吐槽系统的配合**：
- 累积失败2次后，Bot可能会吐槽："感觉大家都不想聊天了..."
- 吐槽会影响情绪系统，让Bot的主动对话更有"人情味"

**适用场景**：
- ✅ 活跃度不稳定的群聊（有时热闹，有时冷清）
- ✅ 希望Bot自动适应群聊氛围
- ✅ 避免Bot在冷场时过度主动（防止被嫌烦）
- ✅ 让Bot在受欢迎时更积极参与

**配置建议**：
- 推荐保持默认配置，已经过优化
- 如果Bot过于敏感，可以调低 `score_decrease_on_fail`
- 如果希望Bot更积极，可以调高 `score_increase_on_success`
</details>

<details>
<summary><b>Q35: 互动评分系统的评分范围和影响是什么？（v1.1.2详解）</b></summary>

**A**: 互动评分系统是 v1.1.2 智能自适应的核心，评分范围 10-100 分，影响Bot的主动对话行为。

**评分等级详解**：

**【90-100分】极度活跃期** 🔥🔥🔥
- **状态**：群聊互动非常好，Bot受到热烈欢迎
- **参数调整**：
  - 沉默阈值：×0.7（例：600秒→420秒）
  - 主动概率：×1.5（例：0.2→0.3）
  - 失败次数上限：×1.5
- **行为表现**：
  - 更快主动发起话题
  - 更高概率触发主动对话
  - 对失败更宽容，不轻易进入冷却
- **如何达到**：连续多次成功互动，且有快速回复和多人参与

**【70-89分】高度活跃期** 🔥🔥
- **状态**：群聊互动良好，Bot表现受欢迎
- **参数调整**：
  - 沉默阈值：×0.7-0.9（渐变）
  - 主动概率：×1.2-1.5（渐变）
- **行为表现**：明显比正常状态更主动
- **如何达到**：多次成功互动，偶尔失败不影响

**【50-69分】正常活跃期** 😊
- **状态**：群聊互动正常，成功与失败相对平衡
- **参数调整**：使用原始配置参数
- **行为表现**：按照配置的标准行为主动
- **维持方法**：保持成功率约50%以上

**【30-49分】逐渐克制期** 😐
- **状态**：群聊互动较少，失败次数开始增多
- **参数调整**：
  - 沉默阈值：×1.0-1.5（渐变增加）
  - 主动概率：×0.5-1.0（渐变降低）
- **行为表现**：逐渐减少主动，更谨慎
- **如何避免**：增加互动，及时回复Bot的主动对话

**【20-29分】明显克制期** 😔
- **状态**：群聊互动很少，Bot主动经常失败
- **参数调整**：
  - 沉默阈值：×1.5（例：600秒→900秒）
  - 主动概率：×0.5（例：0.2→0.1）
  - 失败次数上限：×0.5
- **行为表现**：
  - 主动频率大幅降低
  - 更容易进入冷却期
  - 可能触发吐槽情绪
- **恢复方法**：需要连续几次成功互动，利用低分复苏加成（+20分）

**【10-19分】冷淡期** 😞
- **状态**：群聊几乎不互动，Bot严重受挫
- **参数调整**：
  - 沉默阈值：×1.8+
  - 主动概率：×0.3（大幅抑制）
- **行为表现**：
  - 几乎不主动
  - 即使主动也非常谨慎
  - 强烈的吐槽情绪
- **恢复方法**：低分复苏机制会给予大额加分（+20），鼓励翻身

**评分变化示例**：

**从50分到80分的过程**：
```
Day 1: 50分 → Bot主动 → 用户快速回复 → +20分 = 70分
Day 2: 70分 → Bot主动 → 多人回复 → +25分 = 95分（上限100）
结果: Bot变得非常活跃
```

**从50分到25分的过程**：
```
Day 1: 50分 → Bot主动 → 无人回复 → -8分 = 42分
Day 2: 42分 → Bot主动 → 无人回复 → -8分 = 34分
Day 3: 34分 → Bot主动 → 无人回复 → -8分 = 26分
Day 4: 26分 → Bot几乎不主动了（进入克制期）
```

**低分复苏示例**：
```
当前: 25分（冷淡期）
Bot主动: "好久没人聊天了..."
用户: "抱歉，最近忙"（回复了！）
评分: 25 + 15(基础) + 20(低分复苏) = 60分
结果: 立即恢复到正常状态
```

**配置参数说明**：
```json
{
  "interaction_score_min": 10,        // 最低10分，给翻身机会
  "interaction_score_max": 100,       // 最高100分，防止过度活跃
  "score_increase_on_success": 15,    // 基础加分
  "score_decrease_on_fail": 8         // 基础扣分（较温和）
}
```

**监控评分状态**：
- 启用 `enable_debug_log` 可以在日志中看到评分变化
- 评分数据保存在 `data/plugin_data/chat_plus/proactive_chat_state.json`
</details>

<details>
<summary><b>Q36: 吐槽系统是什么？如何配置？（v1.1.2新增）</b></summary>

**A**: 吐槽系统是 v1.1.2 新增的情绪化功能，让Bot在连续失败时表达情绪，更拟人化。

**工作原理**：

```
累积失败次数追踪（独立于连续失败次数）
    ↓
达到吐槽触发阈值
    ↓
检查吐槽等级（轻微、明显、严重）
    ↓
在主动对话prompt中注入吐槽情绪
    ↓
Bot自然表达不满/失落情绪
```

**吐槽等级划分**：

| 累积失败次数 | 吐槽等级 | Bot情绪表现示例 |
|------------|---------|--------------|
| **2-4次** | 😐轻微吐槽 | "感觉大家都不太想聊天..." |
| **5-9次** | 😔明显吐槽 | "是不是我说错什么了..." |
| **10+次** | 😞严重吐槽 | "好吧，我就安静待着..." |

**与连续失败次数的区别**：

| 特性 | 连续失败次数 | 累积失败次数 |
|------|------------|------------|
| 用途 | 触发冷却期 | 触发吐槽情绪 |
| 重置时机 | 进入冷却期后清零 | **不受冷却影响** |
| 减少方式 | 无法减少 | 成功互动时减少 |
| 上限 | `proactive_max_consecutive_failures` | `complaint_max_accumulation` |

**配置说明**：

```json
{
  "enable_complaint_system": true,
  "complaint_trigger_threshold": 2,        // 累积2次失败后开始检查吐槽
  "complaint_decay_on_success": 2,         // 每次成功减少2次累积
  "complaint_max_accumulation": 15         // 累积上限15次
}
```

**实际运作示例**：

**场景：从正常到吐槽**
```
Day 1 上午:
  累积失败: 0次
  Bot主动: "早上好！" → 无人回复
  累积失败: 1次（未达阈值，不吐槽）

Day 1 下午:
  累积失败: 1次
  Bot主动: "下午茶时间！" → 无人回复
  累积失败: 2次（达到阈值，轻微吐槽）

Day 1 晚上:
  累积失败: 2次
  Bot主动: "感觉今天大家都好忙..." （带轻微吐槽情绪）
  用户回复: "是啊，工作日嘛"
  累积失败: 2 - 2 = 0次（成功互动，减少累积）

Day 2:
  累积失败: 0次
  Bot恢复正常情绪
```

**场景：持续冷场导致严重吐槽**
```
累积失败: 8次
Bot主动: "难道是我的问题吗..." （明显吐槽）
→ 无人回复
累积失败: 9次

累积失败: 9次  
Bot主动: "好吧，可能大家不想聊天..." （明显吐槽）
→ 无人回复
累积失败: 10次

累积失败: 10次
Bot主动: "我就安静待着，有需要再叫我..." （严重吐槽）
→ 有人回复了！
累积失败: 10 - 2 = 8次（减少，但仍在明显吐槽区间）
```

**吐槽提示词注入方式**：

在主动对话的 `proactive_prompt` 中，系统会自动注入吐槽信息：

```
当前情绪状态：
- 你最近主动发起对话时，连续多次无人回应，累积失败次数较多
- 吐槽等级：[轻微/明显/严重]
- 你可以自然地表达一些失落、不满或自我怀疑的情绪
- 但不要过度消极，保持一定的积极性和幽默感

生成主动对话时，可以考虑：
- 轻微吐槽：委婉表达，带点自嘲
- 明显吐槽：明确表达失落，但保持礼貌
- 严重吐槽：明显的不满和失落，但不要攻击性
```

**吐槽效果示例**：

**无吐槽系统（传统）**：
```
Bot: "大家今天过得怎么样？"
（无人回复）
Bot: "有什么有趣的话题吗？"
（无人回复）
Bot: "今天天气不错！"
（每次都是机械式开场）
```

**有吐槽系统（v1.1.2）**：
```
Bot: "大家今天过得怎么样？"
（无人回复）
Bot: "感觉今天大家都挺忙的..."
（无人回复）
Bot: "是不是我的话题不太有趣..."
（带有真实的情绪变化）
```

**配置建议**：

**标准配置（推荐）**：
```json
{
  "enable_complaint_system": true,
  "complaint_trigger_threshold": 2,
  "complaint_decay_on_success": 2,
  "complaint_max_accumulation": 15
}
```

**敏感型Bot（容易吐槽）**：
```json
{
  "complaint_trigger_threshold": 1,      // 失败1次就开始吐槽
  "complaint_decay_on_success": 1,       // 成功减少较少
  "complaint_max_accumulation": 10
}
```

**钝感型Bot（不太吐槽）**：
```json
{
  "complaint_trigger_threshold": 5,      // 失败5次才吐槽
  "complaint_decay_on_success": 3,       // 成功快速恢复
  "complaint_max_accumulation": 20
}
```

**关闭吐槽系统**：
```json
{
  "enable_complaint_system": false
}
```

**注意事项**：
- 吐槽系统不会直接输出固定文本，而是通过prompt让AI自然表达
- 吐槽的具体内容取决于AI的理解和生成能力
- 累积失败次数会持久化保存，重启后保留
- 配合情绪系统使用效果更好
</details>

<details>
<summary><b>Q37: v1.1.2 的戳一戳功能有什么增强？（v1.1.2增强）</b></summary>

**A**: v1.1.2 对戳一戳功能进行了重要增强，增加了智能概率增值和群组独立控制。

**v1.1.2 新增特性**：

**1. 智能概率增值模式**

**旧行为（v1.1.0）**：
```
poke_bot_skip_probability: true  → 跳过概率，必定进入AI判断
poke_bot_skip_probability: false → 正常概率判断
```

**新行为（v1.1.2）**：
```
poke_bot_skip_probability: true  → 跳过概率（保持不变）
poke_bot_skip_probability: false → 参与概率判断 + 智能增加额外概率
```

**智能增值的工作原理**：

```json
{
  "poke_bot_skip_probability": false,
  "poke_bot_probability_boost_reference": 0.3
}
```

当戳机器人时：
1. 不跳过概率判断
2. 根据情绪、注意力动态计算额外概率增值
3. 参考值 `0.3` 不是直接加 0.3，而是一个基准
4. 实际增值 = 参考值 × 情绪系数 × 注意力系数

**示例计算**：
```
基础概率: 0.15
参考增值: 0.3
当前情绪: 正面（系数1.2）
当前注意力: 高（系数1.1）

实际增值 = 0.3 × 1.2 × 1.1 = 0.396
最终概率 = 0.15 + 0.396 = 0.546（约55%）

如果情绪负面（系数0.7）：
实际增值 = 0.3 × 0.7 × 1.1 = 0.231
最终概率 = 0.15 + 0.231 = 0.381（约38%）
```

**对比三种模式**：

| 配置 | 行为 | 适用场景 |
|------|------|---------|
| `skip: true`（默认） | 跳过概率，必定进入AI判断 | 希望戳机器人时响应率最高 |
| `skip: false, boost: 0` | 正常概率判断，无增值 | 戳一戳与普通消息同等对待 |
| `skip: false, boost: 0.3` | 参与概率+智能增值 | 戳一戳有优先权，但不是必定响应 |

**2. 群组独立控制**

**新增配置**：
```json
{
  "poke_enabled_groups": ["123456789", "987654321"]
}
```

**作用**：
- 留空 `[]`：所有群启用戳一戳功能（默认）
- 填写群号：仅指定群启用戳一戳功能
- 与全局 `enabled_groups` 独立

**使用场景**：
```json
{
  "enabled_groups": [],                    // 所有群启用插件
  "poke_enabled_groups": ["123456789"]     // 仅群123456789启用戳一戳
}
```

结果：
- 群 `123456789`：正常回复消息 + 处理戳一戳
- 其他群：正常回复消息，但忽略戳一戳

**完整配置示例**：

**方案1：传统模式（最高响应率）**
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "poke_enabled_groups": []
}
```
- 戳机器人 → 跳过概率 → 必定进入AI判断 → 响应率最高

**方案2：智能增值模式（平衡）**
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": false,
  "poke_bot_probability_boost_reference": 0.3,
  "poke_enabled_groups": []
}
```
- 戳机器人 → 参与概率判断 → 智能增加额外概率 → 考虑情绪和注意力
- 情绪好时响应率高，情绪差时响应率低 → 更拟人化

**方案3：部分群启用**
```json
{
  "poke_message_mode": "bot_only",
  "poke_bot_skip_probability": true,
  "poke_enabled_groups": ["123456789", "987654321"]
}
```
- 仅在指定群响应戳一戳
- 其他群不处理戳一戳消息

**方案4：全部启用，监控所有戳一戳**
```json
{
  "poke_message_mode": "all",              // 处理所有戳一戳
  "poke_bot_skip_probability": true,
  "poke_enabled_groups": []
}
```
- 别人戳别人也会被AI知道
- AI可以观察群内互动氛围

**升级建议**：

从 v1.1.0 升级到 v1.1.2：
- 默认配置保持不变，无需修改
- 如果想尝试智能增值，设置：
  ```json
  {
    "poke_bot_skip_probability": false,
    "poke_bot_probability_boost_reference": 0.3
  }
  ```
- 如果想限制戳一戳功能的群组，配置 `poke_enabled_groups`

**注意事项**：
- 智能增值模式需要启用注意力机制或情绪系统才能发挥最佳效果
- `poke_bot_probability_boost_reference` 建议值：0.2-0.5
- 过高的参考值可能导致戳一戳响应率过高，失去自然感
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
    ├── memory_injector.py       # 记忆注入器（v1.1.2重构：双模式支持）
    ├── tools_reminder.py        # 工具提醒器（提示可用工具）
    ├── keyword_checker.py       # 关键词检查器（触发词/黑名单）
    ├── typo_generator.py        # 打字错误生成器（v1.0.2新增）
    ├── mood_tracker.py          # 情绪追踪系统（v1.0.2新增）
    ├── typing_simulator.py      # 回复延迟模拟器（v1.0.2新增）
    ├── proactive_chat_manager.py# 主动聊天调度器（v1.1.0新增）
    ├── time_period_manager.py   # 时间段概率管理器（v1.1.0新增）
    ├── frequency_adjuster.py    # 频率动态调整器（v1.0.2新增）
    └── ai_response_filter.py    # AI响应过滤器 - 处理带思考链的AI返回 (v1.1.2 新增)
```

### 数据流

```
用户消息 → 【高优先级】指令过滤处理器(v1.0.5) → 生成消息ID并标记(如是指令) → 【普通处理器】检查消息标记 → 【v1.0.7】用户黑名单检测 → 【v1.0.9】@他人消息过滤 → 【v1.0.9】戳一戳检测 → 黑名单关键词检查 → @/关键词检测 → 【v1.0.9增强】戳机器人判断 → 注意力机制概率调整
    ↓
概率筛选(@消息/关键词/戳机器人跳过) → 检测@提及(v1.0.3) → 记录触发方式(v1.0.4) → 添加元数据+临时系统提示(v1.0.4)+戳一戳提示(v1.0.9) → 图片处理
    ↓
缓存消息(含mention_info+trigger_type+poke_info，系统提示临时用于AI理解) → 提取历史上下文 ← 合并缓存消息 → 智能去重
    ↓
AI决策判断(可见系统提示，理解@标记+戳一戳提示+防重复) → 注入情绪状态 → 注入记忆[v1.1.2:自动检测模式,按重要性排序] → 注入工具信息
    ↓
AI生成回复(可见系统提示+戳一戳提示，禁止提及元信息+防重复+严禁元叙述) → 添加打字错误 → 模拟打字延迟
    ↓
清理系统提示(v1.0.4)+戳一戳提示(v1.0.9) → 保存用户消息(仅保留@标记，过滤临时提示) → 发送回复 → 调整概率/记录注意力
    ↓
更新情绪状态 → 频率动态调整检查
    ↓
【after_message_sent钩子】
    ↓
提取AI回复 → 获取缓存消息 → 清理系统提示(v1.0.4)+戳一戳提示(v1.0.9) → 添加元数据(含@标记)
    ↓
合并缓存消息 → 智能去重 → 保存到官方系统(仅保留@标记，不含临时提示)
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
(含@标记+戳一戳信息)       (含@标记+戳一戳信息)
v1.0.3/v1.0.9              v1.0.3/v1.0.9
    ↓                           ↓
保存到官方系统              保留在缓存中
    ↓                           ↓
清空缓存                    等待下次回复
    ↓                           ↓
✅ 完成                      下次回复时一起转正

【v1.0.2 新增数据流】
情绪检测 → 情绪追踪系统 → 注入到prompt → 影响AI回复 → 自动衰减
频率统计 → 定期AI分析（可配置超时、消息数量）→ 调整概率参数（持续可配置时间）→ 影响下次判断 【v1.0.8增强】
回复文本 → 打字错误生成器 → 添加错别字 → 增加真实感
回复文本 → 延迟计算器 → 模拟打字延迟 → 避免秒回

【v1.0.3 新增数据流】
@检测 → 记录mention_info → 添加【@指向说明】标记 → AI理解消息指向 → 保留到历史

【v1.0.9 新增数据流】
@他人消息过滤 → 检测At组件 → 判断模式(strict/allow_with_bot) → 符合条件则跳过处理
戳一戳标识符过滤 → 检测[Poke:poke]文本 → 纯标识符直接丢弃 / 混合内容则过滤标识符 → 防止伪造
戳一戳检测 → 识别poke事件 → 判断模式(ignore/self_only/all) → 保存poke_info → 添加[戳一戳提示] → AI理解并回应
消息提取 → MessageCleaner过滤[Poke:poke]标识符 → 保留纯净内容 → 继续处理

【v1.1.0 新增数据流】
主动聊天调度（独立定时器）→ 过滤群组（proactive_enabled_groups）→ 检查静默阈值（proactive_silence_threshold）→（可选）用户活动门槛（proactive_require_user_activity）→ 应用时间段系数（enable_dynamic_proactive_probability）→ 安静时间抑制（proactive_enable_quiet_time）→ 临时概率提升维持期（proactive_temp_boost_*）→ 硬上限裁剪（enable_probability_hard_limit）→ 失败计数与冷却（proactive_max_consecutive_failures / proactive_cooldown_duration）→ 触发决策与回复
回复时间段概率 → 启用动态时间段（enable_dynamic_reply_probability）→ 作用 `reply_time_periods` 与平滑过渡 → 与硬上限联合裁剪 → 输出最终概率

【v1.1.1 补充数据流】
历史消息存储与提取 → 使用 AstrBotMessage 结构保存 sender/platform 等信息 → 在格式化上下文时标记【你自己的历史回复】并在需要时短暂注入 `[戳过对方提示]`/主动对话标记 → 在写回官方历史前统一通过 MessageCleaner 过滤所有内部系统提示（包括`[系统提示]`、`[戳一戳提示]`、`[戳过对方提示]` 等），只保留用户可见内容
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

#### 主动聊天状态（内存中，v1.1.0）
```python
proactive_state = {
    "aiocqhttp_group_123456": {
        "last_check": 1700000000.0,
        "consecutive_failures": 1,
        "cooldown_until": 1700000600.0,
        "temp_boost_until": 1700000300.0
    },
    # ... 更多群聊
}
```

说明：
- `last_check` 最近一次定时器检查时间戳
- `consecutive_failures` 连续判定失败次数（用于进入冷却）
- `cooldown_until` 冷却期结束时间戳（期间不触发主动消息）
- `temp_boost_until` 临时概率提升结束时间戳
- 数据仅在内存中维护，按需持久化由实现决定（默认不持久化）

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
- [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) - **v1.1.2新适配**的智能记忆系统（推荐使用），提供混合检索、智能总结、会话隔离、人格隔离等强大功能
- [strbot_plugin_play_sy](https://github.com/kjqwer/strbot_plugin_play_sy) - 传统记忆系统集成（Legacy模式支持）
- [MaiBot](https://github.com/MaiM-with-u/MaiBot) - v1.0.2开始的新功能的设计灵感来源（由Mai.To.The.Gate组织及众多贡献者开发）
- [astrbot_plugin_restart](https://github.com/Zhalslar/astrbot_plugin_restart) - v1.1.1开始的指令回复所最后用到的重启astrBot的功能取自于该插件，并且直接参考并使用了相应的代码，特此感谢

---

## ⭐ Star History

如果这个插件对你有帮助，请给个Star⭐支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=Him666233/astrbot_plugin_group_chat_plus&type=Date)](https://star-history.com/#Him666233/astrbot_plugin_group_chat_plus&Date)

---

<div align="center">

**🎉 享受更自然的群聊互动体验！**

Made with ❤️ by Him666233

</div>

