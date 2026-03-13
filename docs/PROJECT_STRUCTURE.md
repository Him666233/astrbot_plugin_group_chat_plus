# 项目结构说明

> 本文档详细描述了群聊增强插件的完整文件结构及每个文件的职责。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程](MESSAGE_WORKFLOW.md) | [配置项参考](CONFIG_REFERENCE.md)

---

## 目录结构总览

```
astrbot_plugin_group_chat_plus/
│
├── main.py                     # 插件主入口
├── metadata.yaml               # 插件元数据
├── _conf_schema.json           # 配置项定义（JSON Schema）
├── requirements.txt            # Python 依赖
├── README.md                   # 项目说明
├── CHANGELOG.md                # 更新日志
├── LICENSE                     # AGPL-3.0 许可证
│
├── docs/                       # 📖 文档目录
│   ├── MESSAGE_WORKFLOW.md     # 消息工作流程详解
│   ├── CONFIG_REFERENCE.md     # 配置项完整参考
│   └── PROJECT_STRUCTURE.md    # 本文件
│
├── web/                        # 🖥️ Web 管理面板
│   ├── __init__.py
│   ├── server.py               # HTTP 服务器（路由/中间件/API）
│   ├── auth.py                 # 认证模块（密码/JWT）
│   ├── security.py             # 安全管理器（防护/封禁/日志）
│   ├── templates/              # HTML 页面模板
│   │   ├── login.html          # 登录页
│   │   ├── panel.html          # 管理面板页
│   │   └── error.html          # 错误/拦截页
│   └── static/                 # 前端静态资源
│       ├── css/                # 样式文件
│       │   ├── main.css        # 主题系统（亮/暗色）
│       │   ├── login.css       # 登录页样式
│       │   ├── config-panel.css# 配置编辑器样式
│       │   ├── charts.css      # 图表样式
│       │   └── tech-tree.css   # 技术树样式
│       └── js/                 # JavaScript 模块
│           ├── api.js          # HTTP 客户端 & Token 管理
│           ├── auth.js         # 前端认证逻辑
│           ├── app.js          # 面板入口
│           ├── charts.js       # 统计图表
│           ├── config-editor.js# 配置可视化编辑器
│           ├── flow-data.js    # 消息流程可视化数据
│           ├── prompt-data.js  # 系统提示词模板数据
│           ├── session-mgr.js  # 会话管理
│           ├── tech-tree.js    # 技术树可视化
│           └── utils.js        # 通用工具函数
│
├── utils/                      # 🧩 群聊工具模块
│   ├── __init__.py             # 模块导出
│   ├── probability_manager.py  # 概率管理器
│   ├── decision_ai.py          # AI 决策（读空气）
│   ├── reply_handler.py        # AI 回复生成
│   ├── message_processor.py    # 消息元数据注入
│   ├── context_manager.py      # 上下文管理器
│   ├── image_handler.py        # 图片处理
│   ├── image_description_cache.py # 图片描述缓存
│   ├── keyword_checker.py      # 关键词检测
│   ├── message_cleaner.py      # 历史消息清洗
│   ├── attention_manager.py    # 注意力机制
│   ├── mood_tracker.py         # 情绪追踪
│   ├── proactive_chat_manager.py # 主动对话
│   ├── humanize_mode.py        # 拟人模式
│   ├── emoji_detector.py       # 表情检测
│   ├── frequency_adjuster.py   # 频率调整
│   ├── typing_simulator.py     # 打字延迟模拟
│   ├── typo_generator.py       # 打字错误生成
│   ├── time_period_manager.py  # 时段概率管理
│   ├── forward_message_parser.py # 转发消息解析
│   ├── welcome_message_parser.py # 欢迎消息解析
│   ├── memory_injector.py      # 长期记忆注入
│   ├── tools_reminder.py       # 工具提示
│   ├── platform_ltm_helper.py  # 平台图片说明提取
│   ├── cooldown_manager.py     # 注意力冷却
│   ├── message_cache_manager.py# 待处理消息缓存
│   ├── content_filter.py       # 内容过滤器
│   ├── ai_response_filter.py   # AI 回复验证
│   ├── message_quality_scorer.py # 消息质量预判
│   ├── reply_density_manager.py# 回复密度限制
│   └── _session_guard.py       # 会话安全守卫
│
└── private_chat/               # ⚠️ 私聊模块（开发测试中，非正式版本）
    ├── __init__.py
    ├── private_chat_main.py    # 私聊主处理器
    └── private_chat_utils/     # 私聊工具模块
        ├── __init__.py
        └── ... (14 个模块)    # 群聊工具的私聊版本
```

---

## 根目录文件

### main.py — 插件主入口

插件的核心文件（约 8400+ 行），包含：

- **插件类定义** — 继承 AstrBot 插件基类，注册事件处理器
- **配置读取** — 从 `_conf_schema.json` 读取并初始化所有配置项
- **模块初始化** — 创建并管理所有 `utils/` 中的工具模块实例
- **事件处理器**：
  - `on_group_message()` — 群聊消息入口，执行 Phase 1-3
  - `_process_message()` — 消息主处理管线，执行 Phase 4-9
  - `on_llm_request()` — LLM 请求钩子（优先级 -1），负责上下文注入和历史处理
  - `after_message_sent()` — 消息发送后的统计和状态更新
- **主动对话** — 定时任务，独立于消息流程运行
- **Web 面板启动** — 初始化 Web 服务器

### metadata.yaml — 插件元数据

定义插件名称、版本号（v1.2.1）、作者、描述、AstrBot 最低版本要求等。AstrBot 平台通过此文件识别和管理插件。

### _conf_schema.json — 配置定义

约 94KB 的 JSON Schema 文件，定义了 100+ 个配置项的：
- 字段名与数据类型
- 默认值
- 描述文本（显示在 AstrBot 配置面板中）
- 枚举选项（如 `image_to_text_scope` 的可选值）

### requirements.txt — 依赖

```
pypinyin    # 拼音处理，用于打字错误生成器
```

> `aiohttp` 为 AstrBot 平台自带依赖，通常无需手动安装。

---

## web/ — Web 管理面板

> v1.2.1 新增的完整 Web 管理界面。

### server.py — HTTP 服务器

Web 面板的核心文件，基于 `aiohttp` 构建，包含：

- **路由注册** — 登录页、面板页、API 端点、静态资源
- **中间件** — 路径遍历防护 → IP 访问控制 → 防爬虫检测 → JWT 认证 → 安全头注入
- **API 处理器**：
  - `/api/login` — 用户认证
  - `/api/change-password` — 密码修改
  - `/api/config` — 配置读取与保存
  - `/api/stats` — 统计数据
  - `/api/logs` — 访问日志
  - `/api/bans` — 封禁管理
- **静态资源服务** — 区分公共静态（`/static/`）和受保护静态（`/panel/static/`）

### auth.py — 认证模块

- **密码管理** — PBKDF2-HMAC-SHA256 哈希，安全的密码存储和验证
- **JWT 管理** — Token 创建、验证、过期检查、IP 绑定

### security.py — 安全管理器

- **暴力破解防护** — 分级锁定（5/10/15/20 次失败 → 30/60/300/600 秒锁定）
- **防爬虫检测** — User-Agent 匹配、请求频率限制、扫描路径模式识别
- **IP 封禁** — 手动封禁 + 自动封禁，封禁持久化（`bans.json`），重启恢复
- **访问日志** — 记录所有请求，支持按类型/IP/时间筛选

### templates/ — HTML 模板

| 文件 | 说明 |
|------|------|
| `login.html` | 登录页面，公开访问，独立于面板代码 |
| `panel.html` | 管理面板主页面，需 JWT 认证。加载各 JS 模块 |
| `error.html` | 统一错误页面，通过 URL 参数 `code` 区分类型（`blocked`/`403`/`404`） |

### static/css/ — 样式文件

| 文件 | 说明 |
|------|------|
| `main.css` | 主样式 + 主题系统。`:root` 定义暗色变量，`:root[data-theme="light"]` 定义亮色变量 |
| `login.css` | 登录页专用样式 |
| `config-panel.css` | 配置编辑器的复杂表单样式 |
| `charts.css` | 统计图表样式 |
| `tech-tree.css` | 技术树/功能关联图谱样式 |

### static/js/ — JavaScript 模块

| 文件 | 说明 |
|------|------|
| `api.js` | HTTP 客户端封装，自动携带 Bearer Token，统一错误处理 |
| `auth.js` | 前端认证逻辑，Token 存取 |
| `app.js` | 面板应用入口，初始化各模块，不含登录逻辑（登录在独立页面） |
| `charts.js` | 基于 Canvas 的实时统计图表（消息量、回复率、群活跃度） |
| `config-editor.js` | 配置可视化编辑器，根据 JSON Schema 动态生成表单 |
| `flow-data.js` | 消息处理流程的可视化数据定义 |
| `prompt-data.js` | 系统提示词模板的预置数据 |
| `session-mgr.js` | 会话管理界面 |
| `tech-tree.js` | 技术树/功能关联图谱的渲染逻辑 |
| `utils.js` | 通用工具函数（格式化、DOM 操作等） |

---

## utils/ — 群聊工具模块

> 每个模块负责一个独立功能，由 `main.py` 统一创建和管理实例。

### 核心决策模块

| 文件 | 类 | 说明 |
|------|-----|------|
| `probability_manager.py` | `ProbabilityManager` | 管理动态概率计算，整合回复后提升、时段调整等因素 |
| `decision_ai.py` | `DecisionAI` | 核心"读空气"逻辑。构建提示词 → 调用 AI → 解析 yes/no 决策结果 |
| `reply_handler.py` | `ReplyHandler` | AI 回复生成。构建完整上下文 → 调用 `event.request_llm()` → 后处理 |

### 消息处理模块

| 文件 | 类 | 说明 |
|------|-----|------|
| `message_processor.py` | `MessageProcessor` | 为消息注入元数据（时间戳、发送者信息） |
| `context_manager.py` | `ContextManager` | 管理自定义消息存储 + 同步平台官方历史记录。处理历史截止时间戳 |
| `message_cleaner.py` | `MessageCleaner` | 清洗历史消息，过滤系统提示词和标记 |
| `image_handler.py` | `ImageHandler` | 调用图片转文字 API，提取图片 URL，处理多图 |
| `image_description_cache.py` | `ImageDescriptionCache` | 本地缓存图片描述结果，避免重复 API 调用 |
| `forward_message_parser.py` | `ForwardMessageParser` | 解析 QQ 合并转发消息，支持嵌套转发 |
| `welcome_message_parser.py` | `WelcomeMessageParser` | 检测新成员入群消息 |
| `keyword_checker.py` | `KeywordChecker` | 匹配触发关键词和黑名单关键词 |
| `emoji_detector.py` | `EmojiDetector` | 检测消息是否为纯表情/贴图 |
| `message_quality_scorer.py` | `MessageQualityScorer` | 判断消息质量（疑问句加权、水聊降权） |
| `content_filter.py` | `ContentFilter` | 按规则过滤 AI 输出内容 |
| `ai_response_filter.py` | `AIResponseFilter` | 验证 AI 回复的有效性 |
| `platform_ltm_helper.py` | `PlatformLTMHelper` | 提取平台消息中的图片说明（caption） |

### 行为模拟模块

| 文件 | 类 | 说明 |
|------|-----|------|
| `attention_manager.py` | `AttentionManager` | 多用户注意力追踪（0-1连续值），指数衰减，情绪检测，溢出效应 |
| `mood_tracker.py` | `MoodTracker` | 情绪状态追踪和检测 |
| `humanize_mode.py` | `HumanizeMode` | 拟人模式状态机（沉默→关注→参与），动态消息阈值 |
| `proactive_chat_manager.py` | `ProactiveChatManager` | 主动对话管理，沉默检测，时机判断 |
| `typing_simulator.py` | `TypingSimulator` | 根据文本长度计算打字延迟 |
| `typo_generator.py` | `TypoGenerator` | 基于拼音相似性生成自然错别字 |
| `frequency_adjuster.py` | `FrequencyAdjuster` | 分析群聊消息频率，动态调整回复频率 |
| `time_period_manager.py` | `TimePeriodManager` | 按时段调整概率，支持平滑过渡（正弦曲线） |
| `cooldown_manager.py` | `CooldownManager` | 注意力冷却机制 |

### 辅助模块

| 文件 | 类 | 说明 |
|------|-----|------|
| `reply_density_manager.py` | `ReplyDensityManager` | 滑动窗口统计回复频率，实现软/硬限制 |
| `message_cache_manager.py` | `MessageCacheManager` | 管理待处理消息池（缓存+转正机制） |
| `memory_injector.py` | `MemoryInjector` | 集成长期记忆插件（LivingMemory / Legacy 模式） |
| `tools_reminder.py` | `ToolsReminder` | 提取并提示 AI 当前可用工具 |
| `_session_guard.py` | `SessionGuard` | 会话安全机制，防止并发冲突 |

---

## private_chat/ — 私聊模块

> **⚠️ 开发测试阶段，非正式版本。私聊部分的文件目前处于开发中，代码结构可能不稳定，内容可能混乱，请勿参考其实现细节。**

### 概述

私聊模块是群聊功能的简化版本，主要区别：
- **无概率筛选** — 私聊总是回复（不做"读空气"判断）
- **消息聚合** — 支持等待并批量合并多条消息
- **简化架构** — 较少的功能模块和配置项

### 文件结构

```
private_chat/
├── __init__.py
├── private_chat_main.py              # 私聊主处理器（PrivateChatMain 类）
└── private_chat_utils/               # 私聊版工具模块
    ├── __init__.py
    ├── private_chat_image_handler.py          # 图片处理
    ├── private_chat_image_description_cache.py # 图片描述缓存
    ├── private_chat_message_processor.py       # 消息元数据注入
    ├── private_chat_context_manager.py         # 上下文管理（仅自定义存储）
    ├── private_chat_emoji_detector.py          # 表情检测
    ├── private_chat_forward_message_parser.py  # 转发消息解析
    ├── private_chat_keyword_checker.py         # 关键词检测
    ├── private_chat_memory_injector.py         # 记忆注入
    ├── private_chat_message_cleaner.py         # 消息清洗
    ├── private_chat_mood_tracker.py            # 情绪追踪
    ├── private_chat_proactive_chat_manager.py  # 主动对话
    ├── private_chat_reply_handler.py           # 回复生成
    ├── private_chat_session_guard.py           # 会话安全
    ├── private_chat_time_period_manager.py     # 时段管理
    ├── private_chat_tools_reminder.py          # 工具提示
    ├── private_chat_typing_simulator.py        # 打字模拟
    ├── private_chat_typo_generator.py          # 打字错误
    └── private_chat_content_filter.py          # 内容过滤
```

> 每个文件基本对应 `utils/` 中同名模块的简化版本，适配私聊场景的需求差异。

---

## 数据文件（运行时生成）

以下文件在插件运行过程中自动创建，位于 AstrBot 的 `data/` 目录中：

| 文件 | 说明 |
|------|------|
| `history_cutoff.json` | 历史截止时间戳，记录 `gcp_reset` 执行时间 |
| `bans.json` | IP 封禁记录持久化（Web 面板） |
| `web_panel_password.json` | Web 面板密码哈希存储 |

---

## 模块关系图

```
                         main.py
                     (插件主入口)
                    ┌──────┼──────┐
                    ↓      ↓      ↓
               web/    utils/   private_chat/
            (管理面板) (群聊工具)  (私聊模块 ⚠️)
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
    server.py    auth.py    security.py
    (路由/API)   (认证)     (安全防护)
        ↓
    templates/ + static/
    (前端页面 + 资源)
```

```
main.py 中的消息处理调用链：

on_group_message()
  ├→ keyword_checker        (关键词检测)
  ├→ welcome_message_parser (入群消息)
  ├→ forward_message_parser (转发消息)
  │
  └→ _process_message()
      ├→ probability_manager   (概率计算)
      │   ├→ time_period_manager  (时段调整)
      │   ├→ frequency_adjuster   (频率调整)
      │   └→ humanize_mode        (拟人调整)
      │
      ├→ message_processor     (元数据注入)
      ├→ image_handler         (图片处理)
      │   └→ image_description_cache (缓存)
      ├→ emoji_detector        (表情检测)
      ├→ message_quality_scorer(质量预判)
      │
      ├→ message_cache_manager (等待窗口)
      │
      ├→ reply_density_manager (密度检查)
      ├→ decision_ai           (AI决策 "读空气")
      │   ├→ attention_manager    (注意力状态)
      │   ├→ mood_tracker         (情绪状态)
      │   └→ memory_injector      (pre_decision 记忆)
      │
      ├→ reply_handler         (AI回复生成)
      │   ├→ context_manager      (历史上下文)
      │   ├→ memory_injector      (post_decision 记忆)
      │   ├→ tools_reminder       (工具提示)
      │   └→ content_filter       (输出过滤)
      │
      └→ 回复后处理
          ├→ typing_simulator     (打字延迟)
          ├→ typo_generator       (打字错误)
          ├→ cooldown_manager     (注意力冷却)
          └→ proactive_chat_manager (状态更新)
```

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程 →](MESSAGE_WORKFLOW.md) | [配置项参考 →](CONFIG_REFERENCE.md)
