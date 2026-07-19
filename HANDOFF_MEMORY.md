# Chat Plus 重构版：AI 接手记忆

这份文件是给下一位接手本项目的 AI/开发者看的项目全景说明。它的重点不是“下一步该做什么”，而是先把当前项目到底是什么、已经做到哪、哪些只是架构边界、哪些地方不能误判为已完成，讲清楚。

项目路径：

- `D:\new-test\astrbot_plugin_group_chat_plus`

工作区根目录：

- `D:\new-test`

参考材料目录：

- `D:\new-test\Reference materials`

## 一句话判断

`astrbot_plugin_group_chat_plus` 现在是一个 AstrBot 插件的“重构骨架 + 公共消息解析层”，不是完整可用的 Chat Plus 成品。

它已经有：

- AstrBot 插件入口。
- 群聊事件接收器。
- 配置读取和配置 schema（含 message_parsing 消息解析配置）。
- 指令过滤保护。
- 群聊黑名单守卫。
- 回复管线第二步：元数据前缀拼接（发送者/时间戳/群环境/群角色）。
- 回复管线第二步：普通 Reply 引用消息展开（只接普通引用，不等于完整正文组件展开）。
- 一套相对完整的公共消息解析器。
- 大量用于后续回复链路的结构化模块边界。

它还没有：

- 完整正文消息组件展开接入管线（@、图片、转发等的原位替换；普通 Reply 引用已先接入）。
- 真正的普通回复生成。
- LLM 调用。
- 提示词构建。
- 消息窗口/等待机。
- 历史持久化。
- 私聊功能接入。
- Web 面板。
- 旧版完整功能迁移。

所以接手时不要把这个项目误认为“功能已经完整，只差一点点”。真实状态是：入口和解析基础已经打好，回复系统还没接上。

## 当前项目的真实形态

这个项目是 `Chat Plus` 的全新原子化重构版。它从旧版庞大插件里拆出更小的模块，把“接收消息、过滤消息、解析消息、构建上下文、决定是否回复、生成回复、发送回复”这些环节拆开。

当前最扎实的部分是 `common/parsers`，也就是“把 AstrBot/平台消息组件转成模型可读文本”的公共解析层。群聊入口已经能接住事件并做基础过滤，但还没有把真实 AstrBot event 解析后送入完整回复生成链路。

可以把当前代码理解为：

```text
AstrBot 插件入口
  -> 群聊接收器
    -> 指令/空消息/send_oper/启用群检查
      -> 群聊回复管线入口
        -> 黑名单守卫 (第一步)
          -> 消息解析子管线 (第二步)
            -> 2.1 元数据前缀拼接 ✅ (发送者/时间戳/环境/角色)
            -> 2.2 普通 Reply 引用展开 ✅
            -> 2.3 完整正文组件展开 ❌ 未接入（@、图片、转发等）

公共解析器
  -> 已经较完整（普通 Reply 已接入群聊子管线；完整正文组件展开仍待后续接入）
  -> 元数据前缀相关的 sender/timestamp/identity 函数已被管线第二步调用
```

也就是说，目前“消息解析能力”比“群聊回复能力”成熟得多；群聊管线已经先接入普通
Reply 引用，但还没有接入完整正文组件展开和回复生成。

## 目录地图

### 根目录文件

- `main.py`
  - AstrBot 插件入口。
  - 注册两个事件处理器：
    - 高优先级全消息类型处理器：只负责指令预标记。
    - 低优先级群聊处理器：正式接收群聊消息。

- `metadata.yaml`
  - AstrBot 插件元数据。
  - 当前版本是 `0.0.0`，描述也明确是重构骨架。

- `_conf_schema.json`
  - AstrBot 配置面板 schema。
  - 当前包含运行时总开关、群聊开关、启用群、用户黑名单、指令过滤、消息解析（message_parsing）配置。

- `README.md`
  - 非常简短，只说明这是重构工作区。

- `HANDOFF_MEMORY.md`
  - 当前这份 AI 接手记忆。

### `common/`

公共能力包。这里的代码应尽量不依赖“群聊”或“私聊”概念，未来群聊和私聊都应该复用它。

主要子目录：

- `common/models`
  - 配置模型已实际使用。
  - 消息、会话、决策模型目前是预留边界。

- `common/parsers`
  - 当前项目最完整的部分。
  - 负责把平台消息组件、字典消息段、引用、转发、媒体、身份、时间戳等转成文本。

- `common/platform`
  - 平台适配边界。
  - 目前多数文件是预留说明，实际可用的是解析器里的 `platform_api.py`。

- `common/state`
  - 运行时状态边界。
  - 目前是预留，用于未来会话注册、锁、缓存。

- `common/storage`
  - 持久化边界。
  - 目前是预留，用于未来历史记录和上下文存储。

- `common/utils`
  - 当前实际使用：
    - `config_reader.py`
    - `command_filter.py`
    - `blacklist_checker.py`
    - `ids.py`
  - 其他工具文件多为后续边界说明。

### `group_chat/`

群聊运行时包。当前已经接入的是真正的群聊入口和初步管线。

已实际使用：

- `entry.py`
  - 群聊事件接收器。
  - 做运行时开关、群聊开关、群白名单、空事件、指令跳过、send_oper 跳过。

- `pipeline_entry.py`
  - 从群聊入口进入内部管线的过渡层。
  - 提取 `sender_id` 和 `self_id` 并调用 `run_reply_pipeline`。

- `pipeline/message_guard.py`
  - 当前管线第一步。
  - 做用户黑名单检查。

- `pipeline/reply_pipeline.py`
  - 当前只调用黑名单守卫和消息解析子管线。
  - 守卫通过后进入消息解析子管线，解析完成后写入 `_chat_plus_reply_accepted`。
  - 后续上下文构建、回复决策、回复生成都还没实现。

- `pipeline/message_parsing_pipeline.py`
  - 消息解析子管线入口（从 reply_pipeline 第二步进入）。
  - 当前接入 2.1 元数据前缀拼接和 2.2 普通 Reply 引用展开。
  - @、图片、文件、合并转发等完整正文组件展开仍预留。
  - 编排层，每步调用独立文件。

- `pipeline/prepend_message_metadata.py`
  - 子管线 2.1：把发送者名称/ID、时间戳、群环境名称/ID、群角色标签拼到消息正文前面。
  - 由 `message_parsing_pipeline` 调用。
  - 正文内部的消息组件不在此展开；普通 Reply 引用由 `expand_reply_messages.py` 处理。

- `pipeline/expand_reply_messages.py`
  - 子管线 2.2：只展开当前消息链中的普通 Reply 引用。
  - 保留普通文本槽位，其他组件暂不输出，避免提前接入完整正文组件展开。

预留边界：

- `decision_gate.py`
  - 未来判断回复/等待/忽略。

- `trigger_detector.py`
  - 未来检测 @AI、关键词、引用触发等。

- `window_policy.py`
  - 未来做消息窗口、静默等待、批次收集。

- `history_view.py`
  - 未来把历史消息投影成提示词可用视图。

- `focus_selector.py`
  - 未来在群聊多人上下文中选择重点消息/话题。

- `prompt_builder.py`
  - 未来构建 LLM 提示词。

- `reply_service.py`
  - 未来编排提示词、LLM 调用和消息发送。

- `session_loop.py`
  - 未来如果需要单群串行循环或后台会话循环，在这里接。

- `inbox.py`
  - 未来如果需要消息队列/缓冲区，在这里接。

### `private_chat/`

私聊运行时包。目前没有接入 AstrBot 入口。只有预留边界：

- `entry.py`
- `session_loop.py`

不要误以为私聊已经可用。

## 当前入口调用链

从 AstrBot 到当前项目内部，真实调用链是：

```text
AstrBot
  -> ChatPlusPlugin.command_filter_handler(event)
    -> GroupChatReceiver.handle_command_filter(event)
      -> CommandDetector.is_command_message(event)
      -> CommandMessageStore.mark(message_id)

AstrBot
  -> ChatPlusPlugin.on_group_message(event)
    -> GroupChatReceiver.handle_message(event)
      -> _should_watch_event(event)
      -> _is_empty_event(event)
      -> CommandMessageStore.contains(message_id)
      -> getattr(event, "_has_send_oper", False)
      -> launch_reply_pipeline(event, config, logger)
        -> run_reply_pipeline(event, config, sender_id, self_id, logger)
          -> check_group_message_allowed(config, sender_id)     [第一步]
          -> run_message_parsing_pipeline(event, config, ...)    [第二步]
            -> build_message_metadata_prefix(event, config, ...) [2.1]
              -> resolve_sender_info / resolve_message_timestamp
              -> resolve_group_info / resolve_group_role
              -> build_current_message_prefix
            -> expand_reply_messages(event, config, ...)         [2.2]
              -> parse_reply_segment(...)                        [普通 Reply 引用]
          -> _set_extra(event, "_chat_plus_reply_accepted", True)
```

当前到 `_chat_plus_reply_accepted` 就结束了。没有模型回复。

## 配置系统

配置读取入口：

- `common/utils/config_reader.py`

配置模型：

- `common/models/config.py`

配置 schema：

- `_conf_schema.json`

当前配置结构：

```text
runtime
  enabled
  debug_log

group_chat
  enabled
  enabled_groups
  enable_user_blacklist
  blacklist_user_ids
  command_filter
    enabled
    prefixes
    full_match_enabled
    full_commands
    prefix_match_enabled
    prefix_match_commands
    marker_ttl_seconds
  message_parsing
    include_sender
    include_timestamp
    include_environment
    include_group_role
    include_reply_group_role
    include_reply_group_name
    include_reply_group_id
```

配置读取设计：

- AstrBot 原始配置先被标准化为 `PluginConfig`。
- `MessageParsingConfig` 是新增的不可变 dataclass，挂在 `GroupChatConfig.message_parsing` 下。
- `include_sender` 和 `include_timestamp` 是当前消息平行主开关；`include_environment` 和 `include_group_role` 是当前消息扩展开关，只在 `include_sender` 开启时生效。
- 普通 Reply 引用会被动解析；被引用发送者名称、ID 和被引用消息时间戳始终输出。`include_reply_group_role`、`include_reply_group_name`、`include_reply_group_id` 只控制引用前缀里的扩展信息。
- 下游代码不应该直接到处读 AstrBotConfig。
- 新增配置时要同时改：
  - `_conf_schema.json`
  - `common/models/config.py`
  - `common/utils/config_reader.py`

## 指令过滤的设计

指令过滤不是 AstrBot 的命令系统，它只是 Chat Plus 的保护机制。

目的：

- 不让 `/help`、`#xxx`、`!xxx` 这类命令进入普通聊天回复链路。
- 同时不阻断 AstrBot 自身或其他插件继续处理这些命令。

实现位置：

- `common/utils/command_filter.py`
- `group_chat/entry.py`

机制：

1. 高优先级 handler 先检查消息是否像指令。
2. 如果像指令，用稳定消息 ID 记入 `CommandMessageStore`。
3. 低优先级群聊 handler 再查同一个消息 ID。
4. 命中则 Chat Plus 跳过，不进入回复管线。

注意：

- 它只标记，不阻断事件传播。
- 标记有 TTL，避免旧消息 ID 永久影响后续消息。
- 稳定消息 ID 来自 `common/utils/ids.py`。

## 群聊接收器当前会拦哪些消息

`GroupChatReceiver.handle_message()` 当前会跳过：

- 总开关关闭。
- 群聊开关关闭。
- 私聊事件。
- 当前群不在启用群白名单。
- 空消息事件。
- 高优先级阶段标记为指令的消息。
- 其他处理器已经发送消息的事件，即 `event._has_send_oper` 为真。
- 黑名单用户消息，黑名单检查发生在 `reply_pipeline` 的 `message_guard` 阶段。

这些跳过一般会写入 event extra，例如：

- `_chat_plus_empty_message`
- `_chat_plus_skipped_by_command_filter`
- `_chat_plus_skipped_by_send_oper`
- `_chat_plus_skipped_by_blacklist`
- `_chat_plus_group_received`
- `_chat_plus_reply_accepted`

## 公共解析器总体设计

解析器在：

- `common/parsers`

它们的核心设计是“工作链原位替换”。

流程：

```text
任意原始内容
  -> normalize_segments(...)
  -> build_working_chain(...)
  -> parse_chain_in_place(...)
    -> parse_component_at(chain, index, runtime)
      -> 根据 seg_type 分派到具体 handler
      -> 只替换 chain[index]
  -> render_chain_text(...)
```

这个设计的关键点：

- 不直接修改 AstrBot 原始 message chain。
- 不把图片、@、引用、文件都抽到开头或结尾。
- 每个组件在原位置被替换成模型可读文本。
- 多个 @、多张图、多个文件的位置关系能保留。
- 引用内部和转发节点内部也走同样的原位替换流程。

## 解析器三种层级

### 1. 纯解析函数

输入一个对象或字段，返回字符串，不修改工作链。

代表：

- `at_parser.py`
  - `parse_at_segment`
  - `parse_at_message`
  - `parse_at_others_hint`

- `media_parser.py`
  - `parse_image_info`
  - `parse_record_info`
  - `parse_video_info`
  - `parse_file_info`
  - `parse_media_segment`

- `sender_parser.py`
  - `parse_sender_display`
  - `parse_sender_context_prefix`
  - `resolve_sender_info`

- `timestamp_parser.py`
  - `format_timestamp`
  - `resolve_message_timestamp`

- `identity_parser.py`
  - `parse_current_sender_identity`
  - `parse_self_environment_identity`
  - `parse_at_target_identity`
  - `parse_reply_sender_identity`
  - `parse_forward_sender_identity`

- `reply_parser.py`
  - `parse_reply_segment`
  - `build_reply_text`

- `forward_parser.py`
  - `parse_forward_segment`
  - `parse_forward_nodes`

### 2. 槽位替换函数

输入 `chain` 和 `index`，只替换当前槽位。

代表：

- `component_slot_parser.py`
  - `parse_component_at`
  - `_handle_plain_text_slot`
  - `_handle_identity_slot`
  - `_handle_media_slot`
  - `_handle_at_slot`
  - `_handle_reply_slot`
  - `_handle_poke_slot`
  - `_handle_forward_slot`
  - `_handle_misc_slot`

- `identity_slot_parser.py`
  - `replace_person_identity_slot`
  - `replace_current_sender_identity_slot`
  - `replace_self_environment_identity_slot`
  - `replace_at_target_identity_slot`
  - `replace_reply_sender_identity_slot`
  - `replace_forward_sender_identity_slot`

### 3. 链路入口函数

负责构建工作链、循环替换、渲染结果。

代表：

- `message_parser.py`
  - `parse_message_segments`
  - `parse_message_text`
  - `parse_current_message_text`
  - `parse_message_chain_in_place`
  - `render_message_chain`

- `current_chain_parser.py`
  - 当前主消息链入口。

- `reply_chain_parser.py`
  - 引用消息内部入口。

- `forward_chain_parser.py`
  - 转发节点内部入口。

## 解析运行时 ParserRuntime

位置：

- `common/parsers/parser_runtime.py`

`ParserRuntime` 用来在解析链路里传横切信息：

- `event`
- `bot`
- `self_id`
- `self_name`
- `call_action`
- `parse_context`
- `max_depth`
- `depth`
- `scope`

`scope` 当前有：

- `current`
- `reply`
- `forward`

用途：

- 当前主消息、引用内部、转发节点内部必须区分。
- 引用和转发不能错误套用当前主消息的身份/环境。
- 转发嵌套深度要受控。

## 当前支持的消息组件解析

当前解析器已经支持：

- 纯文本。
- @ 某人。
- @ 全体。
- 图片。
- 表情包图片识别。
- 语音/音频。
- 视频。
- 文件。
- 表情。
- JSON。
- 分享。
- 音乐。
- 联系人。
- 位置。
- 戳一戳。
- 引用消息。
- 合并转发消息。
- 转发节点。
- 嵌套转发。
- 当前消息发送者身份槽位。
- AI 自身环境身份槽位。
- 普通人物身份槽位。
- @ 目标身份槽位。
- 引用发送者身份槽位。
- 转发节点发送者身份槽位。
- 未知消息段兜底。

## 组件归一化

位置：

- `common/parsers/component_normalizer.py`

作用：

- 把 AstrBot 组件对象、OneBot 风格 dict、API 返回 dict、JSON 字符串等统一成：

```python
(seg_type, data)
```

支持的 AstrBot 组件包括：

- `Plain`
- `At`
- `AtAll`
- `Face`
- `Image`
- `Record`
- `Video`
- `File`
- `Reply`
- `Forward`
- `Node`
- `Nodes`
- `Poke`
- `Json`

如果 AstrBot 组件导入失败，解析器仍能在测试环境里运行，dict 形态仍可解析。

## 当前主消息文本格式

当前主消息完整解析入口：

- `parse_current_message_text(...)`

输出形式：

```text
[时间] 发送者: 正文
```

例如：

```text
[2026-07-04 周六 13:20:00] Alice(ID:123)[管理员]: 你好 @Bob(ID:456) [图片: url=...]
```

重要规则：

- 冒号前是元数据区。
- 冒号后是用户正文区。
- 只有元数据区非空时（即至少有一条元数据被拼接）才会追加冒号。如果发送者和时间戳开关都关闭，不产生孤立冒号。
- 当前实现继承了旧版”有元数据才加冒号”的实际行为。

## 时间戳规则

位置：

- `common/parsers/timestamp_parser.py`

规则：

- 当前主消息使用当前消息对象携带的时间戳。
- 引用消息使用被引用消息自己的时间戳。
- 转发节点使用节点自己的时间戳。
- 不使用当前系统时间乱兜底。
- 时间格式为：

```text
YYYY-MM-DD 周X HH:MM:SS
```

如果时间不可得，部分前缀会显示 `未知时间`，部分内部函数会返回空字符串或 `0`，取决于调用语境。

## 身份解析边界

位置：

- `common/parsers/identity_parser.py`
- `common/parsers/identity_slot_parser.py`
- `common/parsers/sender_parser.py`

最重要的边界：

- 用户 ID 和环境 ID 不能混。
- 群 ID 是环境 ID，不是用户 ID。
- 当前发送者身份可以附加当前聊天环境名称和环境 ID。
- AI 自身环境身份可以附加当前聊天环境名称和环境 ID。
- 普通人物身份不附加环境 ID。
- @ 目标身份不附加环境 ID。
- 引用消息发送者身份不附加当前环境 ID。
- 转发节点发送者身份不附加当前环境 ID。

文案里已经刻意写了“环境ID，不是用户ID”，不要删。

## 引用消息解析

位置：

- `common/parsers/reply_parser.py`
- `common/parsers/reply_chain_parser.py`

引用解析策略：

1. 先从 Reply 组件自带字段里找引用内容。
2. 支持字段：
   - `chain`
   - `message`
   - `content`
   - `origin`
   - `message_str`
   - `text`
   - `raw_message`
3. 如果组件只有引用 ID，就通过平台 `get_msg` 拉取原消息。
4. 拉到的消息会转成 node-like dict。
5. 引用内部用 `reply` 作用域解析。
6. 群聊管线已通过 `expand_reply_messages.py` 接入普通 Reply 引用展开。

引用内容输出类似：

```text
[引用 >>> [2026-07-04 周六 13:20:00] Alice(ID:123): 原消息内容]
```

基础信息规则：

- 被引用发送者名称、发送者 ID、被引用消息时间戳始终输出；缺失时使用未知占位。
- 如果被引用消息由 AI 自己发送，会在发送者名称后标注 `(你)`。
- 引用发送者群身份、对应群聊名称、对应群聊环境 ID 是独立配置项。
- 引用内部的 @ 组件使用专用解析器，仍按原位置逐个替换；多个 @ 不会合并到摘要里。
- 引用内部 @ 目标会显示名称和 ID；如果 @ 目标是 AI 自己，会标注 `(你)`。
- `include_reply_group_role` 开启时，引用内部 @ 目标也会复用同一个群身份开关，按被引用消息对应群聊环境查询并附加群身份。
- 引用内部 @ 全体会输出 `@全体成员`，不会误当作普通用户 ID。

如果无法获取内容，会输出明确占位，并尽量保留引用 ID。

## 合并转发解析

位置：

- `common/parsers/forward_parser.py`
- `common/parsers/forward_chain_parser.py`

转发解析支持：

- AstrBot `Forward`。
- AstrBot `Node`。
- AstrBot `Nodes`。
- OneBot 风格 dict。
- API 返回的 list/dict。
- JSON 字符串。
- 内联节点。
- 只有 forward ID 的节点，需要调用 `get_forward_msg`。
- 兜底调用 `get_msg`。
- 嵌套转发。

重要保护：

- `FORWARD_NESTING_HARD_LIMIT = 10`
- 默认 `max_depth = 3`
- `API_CALL_HARD_LIMIT = 30`
- `parse_context` 里有：
  - `api_call_count`
  - `active_forward_ids`
  - `forward_cache`
  - `message_cache`

转发节点正文使用 `forward` 作用域解析，不套当前消息环境。

## 平台 API 包装

位置：

- `common/parsers/platform_api.py`

当前实际用到的平台 API：

- `get_msg`
- `get_forward_msg`
- `get_group_member_info`
- `get_login_info`

包装原则：

- 从 `event.bot.call_action` 或 `bot.api.call_action` 找入口。
- 所有 API 调用都有超时。
- 所有 API 调用异常都吞掉，返回 `None`。
- 引用和转发共享 `api_call_count`，防止一条消息里 API 调用爆炸。
- `message_id` 参数会尝试多种形态：
  - `message_id` 字符串
  - `id` 字符串
  - `message_id` 整数
  - `id` 整数

## 媒体解析的真实能力

位置：

- `common/parsers/media_parser.py`

当前媒体解析不会做：

- 图片理解。
- OCR。
- 语音识别。
- 视频理解。
- 文件下载。

它只做：

- 提取 URL。
- 提取文件名。
- 提取 path。
- 提取 file_id/image_id/audio_id/video_id。
- 压缩过长引用文本。
- 对 base64 只保留长度信息。
- 判断图片是否像表情包/贴纸。

所以如果后续要接多模态理解，不要以为这里已经做了感知，它只是媒体元信息文本化。

## 当前预留模块的含义

很多短文件不是“没用的垃圾文件”，而是刻意保留的边界说明。它们当前没有实现，是为了后续不要把所有东西重新塞进一个巨型文件。

例如：

- `group_chat/prompt_builder.py`
  - 未来只负责构建提示词。

- `group_chat/decision_gate.py`
  - 未来只负责判断回复/等待/忽略。

- `group_chat/reply_service.py`
  - 未来编排提示词、LLM 调用和发送。

- `common/platform/llm_client.py`
  - 未来封装 AstrBot Provider/LLM 调用。

- `common/platform/message_sender.py`
  - 未来封装平台发送消息。

- `common/storage/history_store.py`
  - 未来做历史持久化。

- `common/state/locks.py`
  - 未来做会话级锁。

这些文件不是已完成功能，不要在文档或回复里说它们已经实现。

## 参考材料

参考材料都在：

- `D:\new-test\Reference materials`

这些目录只作为参考，不要直接修改。

### AstrBot 平台源码

路径：

- `D:\new-test\Reference materials\AstrBot-4.26.4`

用途：

- 查插件生命周期。
- 查事件对象。
- 查消息组件。
- 查公开 API。
- 查配置 schema 格式。

常用位置：

- `docs\zh\dev\star`
- `docs\zh\dev\star\guides\simple.md`
- `docs\zh\dev\star\guides\send-message.md`
- `docs\zh\dev\openapi.md`
- `docs\zh\dev\plugin-platform-adapter.md`
- `astrbot\core\message\components.py`

### 旧版 Chat Plus

路径：

- `D:\new-test\Reference materials\astrbot_plugin_group_chat_plus`

用途：

- 参考旧功能。
- 参考旧配置。
- 参考旧版身份提示、转发解析、消息清理、Web 面板、私聊。

不要照搬：

- 旧版文件太大。
- 很多流程耦合。
- 当前重构目标是拆分边界。

可继承思想：

- 冒号前元数据区和冒号后正文区严格分离。
- 指令消息不进入普通回复链路。
- 特殊消息组件要转成模型可读文本。
- 每条消息应保留发送者和时间戳。

### MaiBot

路径：

- `D:\new-test\Reference materials\MaiBot-1.0.11`

用途：

- 参考消息窗口、等待机、拟人回复节奏、记忆和心流。

不要照搬：

- MaiBot 是独立系统，不是 AstrBot 插件。
- Chat Plus 必须兼容 AstrBot 的插件生命周期和事件模型。

## 重要禁区和原则

1. 不要修改 `Reference materials`。

2. 不要把群聊专属逻辑写进 `common/parsers`。

3. 不要让私聊和群聊各自复制一套解析器。

4. 不要直接原地修改 AstrBot 的原始消息链。

5. 解析组件时只能替换当前槽位，不要把结果挪到头尾。

6. 引用内部使用引用作用域。

7. 转发节点内部使用转发作用域。

8. 当前消息身份不要污染引用和转发内部身份。

9. 用户 ID 和环境 ID 必须区分。

10. 不要用当前系统时间冒充消息发送时间。

11. 不要把预留模块说成已实现功能。

12. 新增配置必须同步 schema、模型和读取器。

13. 回复生成还没接入，不要误以为 `_chat_plus_reply_accepted` 表示已经回复。

14. 任何平台 API 调用都要有失败兜底，不能让一个引用/转发拉取失败毁掉整条消息解析。

## 当前验证状态

最近一次本地检查：

```text
python -m compileall -q astrbot_plugin_group_chat_plus
_conf_schema.json ConvertFrom-Json: json ok
reply_parser 内存样例: 引用自己时输出 (你)，并按配置输出群名/环境ID
reply_parser 内存样例: 引用内部多个 @ 原位替换，@AI 标 (你)，@全体单独适配，群身份开关生效
```

含义：

- 插件目录下 Python 文件能编译。
- 配置 schema 是有效 JSON。
- 普通 Reply 引用解析的基础输出形态做过轻量内存样例检查。

注意：

- 这不是端到端 AstrBot 实机测试。
- 没有验证真实平台事件能完整跑完回复生成，因为回复生成尚未接入。
- 没有验证 LLM/provider/message sender，因为这些模块还只是边界。

## AI 接手时的阅读顺序

如果下一位 AI 要理解项目，不要从预留模块开始看。建议按这个顺序读：

1. `main.py`
2. `group_chat/entry.py`
3. `group_chat/pipeline_entry.py`
4. `group_chat/pipeline/reply_pipeline.py`
5. `group_chat/pipeline/message_guard.py`
6. `group_chat/pipeline/message_parsing_pipeline.py`
7. `group_chat/pipeline/prepend_message_metadata.py`
8. `group_chat/pipeline/expand_reply_messages.py`
9. `common/models/config.py`
10. `common/utils/config_reader.py`
11. `common/utils/command_filter.py`
12. `common/parsers/message_parser.py`
13. `common/parsers/message_prefix_parser.py`
14. `common/parsers/component_slot_parser.py`
15. `common/parsers/component_normalizer.py`
16. `common/parsers/reply_parser.py`
17. `common/parsers/forward_parser.py`
18. `common/parsers/identity_parser.py`

读完这些，就能理解当前项目真正能做什么。

## 当前项目最容易被误解的点

### 误解 1：有 `reply_pipeline.py`，所以已经能回复

不对。当前管线做了黑名单守卫（第一步）、元数据前缀拼接（第二步 2.1）和普通 Reply 引用展开（第二步 2.2）。完整正文组件展开（@、图片、转发等）、上下文构建、LLM 调用、回复发送都还没有。

### 误解 2：`common/platform/message_sender.py` 存在，所以已封装发送

不对。它是预留边界。

### 误解 3：`private_chat` 存在，所以私聊已接入

不对。私聊只有预留说明，主入口没有注册私聊处理。

### 误解 4：媒体解析能理解图片/语音

不对。当前只提取媒体元信息。

### 误解 5：转发解析已经在真实平台完整验证

不应这么说。代码有兼容路径、缓存和深度限制，但真实平台适配还需要实机验证。

### 误解 6：大量短文件是无意义空文件

不完全对。它们现在确实没有功能实现，但它们表达了后续架构边界。不要因为它们短就随便塞逻辑进去。

## 最后总结

当前项目的核心价值不是”已经能聊天”，而是：

- 插件入口和群聊接收保护已经搭好。
- 配置系统已经有最小闭环（含 message_parsing 当前消息开关和引用扩展开关）。
- 指令过滤和黑名单守卫已经接入。
- 回复管线第二步（消息解析）已接入，当前做了 2.1 元数据前缀拼接和 2.2 普通 Reply 引用展开。
- 消息解析子管线采用”编排层 + 独立实现文件”的原子化结构，后续步骤可以独立添加。
- 公共解析器已经比较细，能把复杂消息组件转成模型可读文本。
- 未来回复链路的模块边界已经铺开，并且有大量注释说明职责。

下一位 AI 接手时，首先要承认这个真实状态：它是一个正在变成完整插件的重构骨架，解析层先行，回复层待接。
