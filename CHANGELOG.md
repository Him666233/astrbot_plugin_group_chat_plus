## 📝 更新日志

### V1.2.3.hotfix.2 (2026-05-29)

**AI 提示词注入顺序全面优化（缓存命中占比大幅提升）+ 逐插件上下文追踪全面升级（全字段覆盖+具名隔离）+ Agent 调用非图片媒体全链路扩展 + 消息元数据化防注入机制 + 戳一戳双层标注与引用消息格式重构 + 用户名称全链路兜底 + 主动对话重复启动防护 + 多轮工具调用链路修复 + IPV6 全面兼容管控 + Web 面板 UX 全面增强（自动刷新重构/心跳同步/图表主题适配/悬浮窗移动端适配/访问日志与封禁管理修复）+ AstrBot v4 重启认证升级 + 多项细节修复 + 文档全面更新**

**🧠 AI 提示词注入顺序优化与缓存命中提升**:
- **缓存友好的提示词拼接顺序全面重排** — 对所有 AI 模块的提示词拼接逻辑进行了系统性重排，将静态指令（角色设定、行为规则、输出格式要求等跨请求不变的内容）统一放在 system_prompt 的前半部分，将动态内容（当前时间信息、平台注入的聊天历史、用户消息等每轮不同的内容）放在后半部分。涉及模块包括：群聊回复 AI（`reply_handler.py` 的 `SYSTEM_REPLY_PROMPT`）、私聊回复 AI（`private_chat_reply_handler.py` 的 `SYSTEM_REPLY_PROMPT`）、读空气 AI（`decision_ai.py` 的系统提示词拼接）、频率调整 AI（`frequency_adjuster.py` 的提示词拼接）、主动对话生成 AI（`proactive_chat_manager.py` 的 `default_proactive_prompt`）。同一静态前缀在连续多次 API 调用之间保持字节级不变，使 Anthropic prompt cache 能够持续命中，大幅降低首 token 延迟与 API 费用
- **提示词内部位置引用同步修正** — 由于静态内容从 prompt 后半部分移至前半部分，所有提示词中"上方/上述/前面"等位置引用措辞全部更新为"下方"，与实际的物理拼接顺序保持一致。AI 不会因方向措辞与内容实际所在位置不一致而产生理解偏差（如"上述规则"实际上在它的下面）
- **用户自定义提示词的覆盖/拼接模式同步适配** — 覆盖模式（用户自定义系统提示词完全替代默认）和拼接模式（用户自定义提示词紧跟默认系统提示词）均改为缓存友好顺序输出，确保自定义配置用户也能享受缓存命中提升
- **增强提示词防回声/防复读约束** — 回复 AI 和主动对话生成 AI 的提示词中新增防回声引导段落，提示 AI "你的任务是产生有价值的新内容，不是重复或轻微改写用户已经说过的内容。如果用户消息中包含多条内容，针对最有讨论价值的方向回复，而不是把每条都复述一遍"。同时提示词中移除了可能被 AI 理解为"复述当前话题"的模糊用语，改为"根据上下文自然延伸"的正面引导

**🔌 逐插件上下文追踪全面升级**:
- **monkey-patch 替换为 handler wrapper 架构** — 彻底废弃通过 monkey-patch `call_event_hook` 拦截第三方插件注入的方式（该方式依赖 Python from-import 语义，在特定加载顺序下会失效成为死代码），改为在 `OnLLMRequestEvent` 的 handler 列表上直接包装每个第三方 handler：包装器在执行前后拍摄 prompt 和 contexts 的快照，通过差分法精确计算每个插件独立注入的内容，实时写入 `event._gcp_per_plugin_injections` 字典。本插件自己的 handler（priority=-1，最后执行）读取该字典实现逐插件标记隔离
- **第三方标记从统一编号升级为具名首尾配对隔离** — prompt 中的第三方注入标记从原有的 `[第三方插件片段 N] ... [/第三方插件片段 N]` 统一匿名编号格式，升级为携带插件名的首尾配对格式：`[第三方插件:插件名 补充信息] ... [/第三方插件:插件名 补充信息]`。contexts 中的注入标记从 `[第三方插件注入上下文]` 升级为 `[第三方插件:插件名 注入上下文] ... [/第三方插件:插件名 注入上下文]`。AI 可明确区分不同插件的注入来源（如"天气插件告诉我的"vs"翻译插件告诉我的"），不会混淆不同插件的补充信息
- **全字段追踪覆盖消除重复显示** — 原有差分法仅追踪 prompt 和 contexts 两个通道，现扩展为全字段追踪，新增覆盖：`system_prompt`（插件通过 event.set_extra("system_prompt", ...) 注入）、`extra_user_content_parts`（插件追加的用户消息片段）、`image_urls`（插件追加的图片 URL）、`audio_urls`（插件追加的音频 URL）。所有通道统一走逐插件标记合并管道，同一插件通过多个通道注入的重复内容（如同时在 contexts 和 extra_user_content_parts 中注入同一段信息）通过指纹去重自动合并，不再在最终 prompt 中重复出现
- **上下文差分指纹去重** — `_gcp_fingerprint_context(msg)` 函数对每个 context 消息生成快速指纹（截取前 120 字符并压缩空白），用于跨插件的注入 diff 去重，避免不同插件注入相同上下文信息时出现重复显示
- **Web 端与架构文档同步更新** — Web 面板的提示词预览中，第三方插件注入标记的展示格式同步更新为具名配对格式，架构文档中「与其他插件的兼容性」章节扩充了逐插件追踪机制的完整说明

**📦 Agent 调用兼容性全面扩充**:
- **视频/语音/文件三类非图片媒体完整支持** — 在 `image_handler.py` 的媒体提取管线中新增三个独立提取通道：① 视频组件（`Video`）→ 提取文件路径，注入 `[视频: /data/videos/xxx.mp4]` 内联标记；② 语音组件（`Record`）→ 提取音频路径，注入 `[语音]` 标记，路径注入 `audio_urls` 字段供 LLM 访问；③ 文件组件（`File`）→ 提取文件名和路径，注入 `[文件: 报告.pdf]` 标记。三类媒体覆盖消息链遍历、标记内联注入、缓存剥离前富化（保留有路径的标记、剥离纯占位符）、保存传递全链路，与既有图片处理逻辑（`[图片]` / `[图片内容: xxx]`）完全平行一致
- **纯语音/纯文件消息防丢弃** — `image_handler.py` 的 `_extract_image_urls_structured()` 返回值从二元组 `(image_urls, image_descriptions)` 扩展为五元组 `(image_urls, image_descriptions, audio_urls, video_paths, file_infos)`，调用方同步更新。语音消息和文件消息在 `main.py` 的空消息入口过滤环节被视为有效内容，防止纯语音/纯文件的合法消息被误判为真空消息而丢弃

**💬 消息系统提示词统一元数据化（杜绝提示词注入伪造）**:
- **冒号前元数据区 + 冒号后用户内容区严格分离** — `message_processor.py` 的 `format_message_for_ai()` 方法重构为两段式输出格式：冒号 `:` 之前为系统元数据区，仅包含系统生成的元信息（时间戳 `[2026-05-29 周四 14:30:00]`、发送者信息 `Name(ID:12345)`、`[戳一戳事件]` 持久化文本、`[系统提示]` 触发方式说明）；冒号之后仅保留用户消息的原始内容（含 @ 提及内联解析 `[At:ID|解析结果]`）。用户无法通过消息内容注入伪造的时间戳、发送者身份或戳一戳事件文本——因为用户输入的所有字符都在冒号之后，而系统元数据在冒号之前，两者不存在字符重叠区间
- **引用消息的 `>>>` 分隔符同样在冒号前注入** — 引用消息标记（`[引用: Name(ID): 原文...]`）及其 `>>>` 分隔符均注入在冒号前元数据区，被引用内容与用户当前消息正文之间通过冒号明确切分
- **`[戳一戳提示]` 运行时注入在分隔符之外** — 运行时戳一戳提示（`[戳一戳提示] @Name 戳了戳你`）由 `main.py` 的 `format_context_for_ai()` 在构建完整上下文时追加到消息块分隔符之外，不进入冒号前元数据区。持久化戳一戳事件（`[戳一戳事件]`）则注入冒号前并随消息保存到历史。两种戳一戳标记职责清晰、互不重叠，过滤清理规则不会误伤持久化戳一戳事件
- **元数据区注入由独立开关控制** — `include_timestamp` 控制时间戳是否注入冒号前；`include_sender_info` 同时控制发送者信息和 `[系统提示]` 是否注入冒号前。两个开关独立可控，用户可根据需要裁剪元数据区的信息量

**👆 戳一戳事件双层标注机制与引用消息格式重构**:
- **戳一戳双层标注** — 戳一戳事件的文本标注从单一模式重构为双层：① 持久化层（`[戳一戳事件]`）— 由 `message_processor.py` 的 `build_persistent_poke_event_text()` 构建，注入到冒号前元数据区，包含发送者→目标者的完整身份信息（`Name(ID:xxx) 戳了戳 Name(ID:yyy)` 或 `Name(ID:xxx) 戳了戳你`），随消息一起保存到自定义聊天历史，不会被填充率超限丢弃或过滤清理移除；② 运行时提示层（`[戳一戳提示]`）— 由 `main.py` 在处理当前消息时动态追加到分隔符之外，仅在当前轮次对 AI 可见，不进入持久化存储。两层标注分工明确：持久化层保证历史上下文的完整性，运行时层保证当前轮次的即时提示
- **引用消息格式重构** — 引用消息的构建从简单的 `[引用: 原文]` 格式升级为三段式结构：`[引用: Name(ID:xxx): 原文...]\n>>>\n`。`>>>` 符号作为引用块结束的可视标识，同时追加换行使被引用内容与用户新消息正文物理分行。当被引用消息来源为 AI 自身时，发送者名称后自动追加 `(你)` 标注（格式：`Name(ID:xxx)(你)`），帮助 AI 识别自己的历史发言；当引用内容无法获取时（如消息已被删除或不在数据库中），保留发送者框架并标注 `(无法获取引用内容)`；仅当发送者和内容全部缺失时才跳过引用标记
- **多条引用独立解析** — 消息链中存在多个引用组件时，每个引用独立提取和格式化，不再合并为单一引用块；当引用消息嵌套（引用中包含引用）时跳过递归展开，保留原始引用格式避免无限循环
- **过滤规则与全部文档同步更新** — `message_cleaner.py` 中的内容过滤正则模式同步适配新的引用消息格式（`>>>` 分隔符不破坏现有匹配），`MESSAGE_WORKFLOW.md` 新增引用消息格式完整章节，`ARCHITECTURE.md` 同步引用消息解析说明

**👤 用户名称解析全链路兜底**:
- **统一兜底策略** — 在 `message_processor.py`、`main.py` 的群聊消息处理、Smart 并发批量保存、戳一戳事件构建、转发消息解析、引用消息构建、@ 提及解析等所有涉及用户名称展示的路径上，统一实施相同的名称兜底检查：当 `sender_name` / `user_name` / `target_name` 解析结果为 `None`、空字符串、仅空白、或与对应的 `user_id` 完全相同时，名称字段替换为 `"未知用户"`，原始 ID 字段独立保留不覆盖。确保前端展示和日志排查两不误
- **戳一戳发送者/目标者独立兜底** — `build_persistent_poke_event_text()` 和戳一戳事件缓存构建中，发送者名称和目标的名称各自独立执行兜底检查，不会因其中一个为空而影响另一个的展示
- **转发消息发送者兜底** — `forward_message_parser.py` 解析转发消息中各条子消息的发送者名称时，同样执行名称兜底检查，转发消息内的每条子消息独立受保护
- **Smart 并发批量消息名称保护** — Smart 并发批量保存消息到历史存储时，每条消息独立执行名称兜底，同一批次中某条消息的名称异常不影响其他消息的正常保存和展示

**🔄 主动对话重复启动防护**:
- **后台循环 Task 身份识别** — `proactive_chat_manager.py` 的 `_background_check_loop()` 在启动时记录当前 `asyncio.Task` 对象身份（`_own_task = asyncio.current_task()`），循环的 while 条件从仅检查 `cls._is_running` 升级为同时校验 `cls._background_task is _own_task`（要求两者严格 `is` 相等）。当插件类被重复加载（例如插件重载）后，新加载的类会创建新的后台 task 并设置 `cls._background_task = 新task`，旧 task 在循环条件检查时发现 `cls._background_task is _own_task` 为 `False`，自动退出循环。解决了旧版中"类重载后旧循环因仅检查 `_is_running`（仍为 True）而继续运行"导致的双循环并发冲突——两个循环同时对同一 `_chat_states` 执行检查和触发主动对话，造成重复发送、状态竞争和 API 费用翻倍
- **普通回复时主动对话状态双重保险关闭** — `record_bot_reply(is_proactive=False)` 方法中新增主动对话活跃状态检查：当记录普通回复（非主动对话）时，检查 `state.get("proactive_active", False)`，如果为 `True`（说明主动对话流程异常退出未清理其活跃标记），普通回复主动将其置为 `False` 并输出 debug 日志。这作为一道双重保险，防止残留的 `proactive_active=True` 标记干扰后续主动对话的正常触发（如阻止新主动对话启动、导致 `check_and_handle_reply_after_proactive` 中误判）

**🔧 多轮工具调用链路修复**:
- **LLM_RESULT 误判为最终回复修复** — 修复多轮工具调用中一个关键 Bug：当 AI 在调用工具之前先说一段话（如"让我搜索一下相关信息"），然后调用工具，最后生成最终回复——这种多轮场景下，第一段中间话的类型同样是 `LLM_RESULT`。旧版 `on_decorating_result()` 在收到任何 `LLM_RESULT` 时都强制完成并保存，导致第一段中间话被误当最终回复保存，后续的工具调用结果和真正的 AI 最终回复全部丢失。修复后：`on_decorating_result()` 仅对非 `LLM_RESULT` 类型（如 `GENERAL_RESULT` 异常终止响应）执行强制保存；`LLM_RESULT` 类型的文本累积到内部缓冲区但不触发强制完成。正常的多轮工具调用完成流程由 `on_llm_response` 设置 `_agent_done_flags` → `after_message_sent` 统一构建交错记录并保存。异常终止时（AI 错误标记或非 LLM 终端响应），通过 `_finalize_bot_reply_save()` 兜底保存所有已累积的中间文本和已完成的工具调用记录
- **工具循环异常时反馈结果保存修复** — 修复工具循环调用过程中出现报错（如工具执行超时、返回值格式错误）时，已完成的前几轮工具调用记录和 AI 的中间回复文本无法正常保存到历史的问题：异常处理路径中通过 `_finalize_bot_reply_save()` 构建交错排列的工具调用记录（按照工具调用的实际执行顺序，文本块与工具调用块交替排列），确保异常中断场景下不丢失已完成的上下文

**📊 概率过滤信息描述纠正**:
- **"概率过滤失败"→"概率过滤未通过"** — 全面替换概率过滤链路中的措辞：日志输出（`[概率过滤-缓存]`、`[戳一戳缓存]` 等）、Web 流程图节点标签（`flow-data.js` 中的 `failLabel` 和 `desc`）、代码注释中的相关描述统一从"概率过滤失败"改为"概率过滤未通过"。概率过滤未命中是概率模型的正常随机行为（表示"本轮不回复"而非"功能出错"），"未通过"比"失败"更准确地反映业务语义，避免用户在日志和 Web 面板中看到"失败"字样而误以为系统故障

**🌐 IPV6 全面兼容与边界管控**:
- **全安全机制 IPV6 适配** — Web 面板的所有安全机制均已完整适配 IPv6 地址：IP 访问控制（白名单/黑名单）、IP 封禁管理（手动封禁+自动封禁）、防爬虫检测（UA 匹配+频率限制+扫描路径识别）、速率限制（已登录请求次数窗口）、暴力破解防护（登录失败分级锁定）。`web/security.py` 中新增 `_normalize_ip()` 静态方法，将 IPv4 保持点分十进制、IPv6 压缩为 RFC 5952 规范形式，所有 IP 比较和存储统一走规范化管道。`web/server.py` 中 `_get_client_ip()` 在提取客户端真实 IP 后同样调用 `_normalize_ip()` 进行规范化
- **IP 配置边界校验与警告** — 配置加载时（`web/security.py` 的 `_validate_ip_list()`），对 IP 白名单/黑名单/受保护 IP 列表中的每个条目进行合法性校验：非法的 IPv4/IPv6 地址（如包含 CIDR 网段、非法字符、格式错误）会被识别并输出明确的 WARNING 日志（`配置警告：xxx 中包含 yyy，不是合法的 IPv4/IPv6 地址。仅支持精确地址匹配，不支持 CIDR 网段/子网`）；合法条目自动规范化为标准形式后存储
- **Web 面板监听地址双栈自动化** — 监听地址配置 `web_panel_host` 设为 `0.0.0.0` 或 `::` 时，`server.py` 将 `_host` 设为 `None`（aiohttp 双栈模式），同时监听 IPv4 和 IPv6 所有网络接口。启动日志输出本机所有非链路本地（过滤 `fe80::`）的 IPv4 和 IPv6 地址
- **封禁 IP 错误页增强** — 被封 IP（支持 IPv4 和 IPv6）访问面板时，中间件将请求统一重定向至 `/error?code=blocked`，错误页每 5 秒自动轮询 `/api/auth/verify` 检测解封状态，封禁到期后自动跳转至登录页（已认证用户直达面板）。手动封禁可通过 Web 面板「IP 封禁管理」解封
- **`localhost` 归一化为 `127.0.0.1`** — Web 面板启动日志输出中，将 `localhost` 统一归一化为 `127.0.0.1` 独立一行显示，避免部分环境（如配置了 IPv6 优先的系统）`localhost` 解析到 `::1` 导致浏览器点击链接时的行为不一致

**🔧 Web 面板 UX 全面增强**:

**自动刷新机制重构**:
- **会话列表 3 秒自动刷新** — `session-mgr.js` 中新增 `startAutoRefresh()` / `stopAutoRefresh()` 方法：进入会话列表页自动启动 3 秒间隔的自动刷新（仅在列表页且非编辑模式时执行）；进入会话详情页自动暂停列表刷新（`stopAutoRefresh()`）；返回列表自动恢复刷新（`startAutoRefresh()`）；编辑模式（配置面板打开、文件编辑）期间设置 `_editMode=true`，自动刷新检查到编辑模式直接跳过本轮刷新，避免编辑过程中列表跳变
- **聊天记录增量更新** — `session-mgr.js` 的聊天记录查看面板改为增量更新策略：通过比较新旧消息列表的内容哈希（取每条消息的 `content` + `sender_name` + `timestamp` 拼接后做快速比对），仅对新增/变更的消息条目进行 DOM 局部渲染，而非全量替换。保留用户当前滚动位置（更新前后记录 `scrollTop` 并恢复）。如果增量更新过程中检测到数据不一致（如消息 ID 集合变化超过阈值），自动回退为全量重建确保数据完整性
- **心跳状态自动/手动刷新** — `app.js` 的心跳状态面板支持两套刷新机制：① 自动刷新定时器（`_heartbeatAutoRefreshTimer`）永不停歇，仅通过 `_heartbeatAutoRefreshPaused` 标志位控制是否执行 DOM 更新渲染。Leader 标签页每次心跳 ping 成功后（`/api/auth/heartbeat` 返回 ok），广播 `session-ok` 事件（通过 `BroadcastChannel` API）；Follower 标签页接收 `session-ok` 广播后同步更新 `lastHeartbeatSuccessAt` 和 `lastHeartbeatStatus`，解决 Follower 长期不更新"最近一次心跳成功"时间戳的问题。② 手动刷新按钮（🔄）触发 `_loadHeartbeatStatus()` 完整重新加载。`_loadHeartbeatStatus()` 新增兜底逻辑：只要 `verify` 成功（会话有效），且 `_authMonitor.lastHeartbeatSuccessAt` 尚未记录过成功时间（初始状态为 null），直接用 `Date.now()` 初始化，确保首次加载即显示有意义的时间戳而非"尚未成功"
- **图表页面 3 秒自动刷新开关** — `panel.html` 的图表区新增自动刷新开关 UI（含绿色圆点 `dot active` 状态指示器 + checkbox），用户可自由启停。`charts.js` 中 `startAutoRefresh()` 读取开关状态，仅在开关开启时执行定时更新
- **速率窗口心跳/自动刷新豁免** — 后端 `web/security.py` 的 `check_authenticated_rate()` 新增 `is_auto_refresh` 参数（默认 `False`）：心跳请求（`is_heartbeat=True`）和自动刷新请求（`is_auto_refresh=True`）直接放行，不参与速率窗口计数、不消耗速率配额。前端 `api.js` 中所有自动刷新请求通过 `api.fetch()` 的 `autoRefresh` 选项自动注入 `X-GCP-Auto-Refresh: 1` 请求头，后端 `server.py` 的认证中间件检测该头并设置 `is_auto_refresh=True`
- **无自动刷新页面提示** — 访问日志页刷新按钮旁新增无自动刷新机制提示文字（`本页无自动刷新，有新日志产生时请手动点击刷新按钮获取最新信息`），通过 CSS class `log-refresh-hint` 适配桌面/平板/手机三端及明暗双主题
- **`api.verify` 支持 options 参数** — `api.js` 中 `verify()` 方法新增 `options` 参数（`{ autoRefresh: boolean }`），传递给底层 `api.fetch()` 以触发自动刷新头注入

**页面交互与布局修复**:
- **全页面手动刷新 + toast 反馈** — 所有数据页面（会话管理、图表、访问日志、封禁管理、文件管理等）的手动刷新按钮补充完整：点击后通过 `Utils.toast()` 显示操作反馈（"刷新成功"/"刷新失败"）；编辑模式下手动刷新被守卫跳过（`if (this._editMode) return`），避免覆盖用户正在编辑的内容；手动刷新始终调用数据的全量重载方法（而非增量更新），确保用户主动刷新时看到完整最新数据
- **会话列表计数移至右侧** — 会话卡片的群聊/私聊计数标签（如 `12 群聊 / 3 私聊`）从卡片的左侧区域移至右侧，与操作按钮（重置、详情、删除）在同一视觉行，整体层次更清晰
- **按钮布局位移修复** — 修复配置保存按钮与其他控件之间的间距异常（由于 CSS flex 布局 `gap` 属性的计算差异导致按钮在部分浏览器中偏移）
- **插件重启期间自动刷新静默容错** — 自动刷新请求在网络错误或服务端返回 5xx 时静默忽略（不弹 toast、不改变 UI 状态），`api.fetch()` 中对自动刷新请求的 `onError` 回调仅 `console.debug` 输出。重启完成后首次成功的自动刷新自动恢复所有 UI 数据

**图表与主题适配**:
- **柱状图始终重绘适配主题** — `charts.js` 中移除柱状图的主题色缓存守卫逻辑：原先在明暗主题切换时，如果图表数据未变化则跳过重绘导致柱子颜色与新主题不匹配。修复后图表每次 `updateChart()` 都执行完整重绘（`chart.destroy()` + 重新 `new Chart()`），使用当前主题的 CSS 变量（`var(--accent)` 等）动态设置颜色
- **概率柱状图统一红色** — 概率分布图（回复概率、主动对话概率、戳一戳概率等）的柱子颜色从主题色（明暗切换时变化）改为固定红色系（`#ef4444` 及其透明度变体），与其他图表（蓝色系）形成视觉区分，用户可一眼识别概率相关数据
- **"图表无会话"手动刷新修复** — 修复 `charts.js` 中当图表页面无会话数据时（`buildChartData()` 返回空数组），手动刷新按钮被守卫 `if (!hasData) return` 错误拦截的问题：移除该守卫，用户可在任意状态下手动刷新以尝试重新加载数据（如会话刚创建、数据尚未在图表中体现等情况）
- **主题切换时图表立即重绘** — `app.js` 的主题切换逻辑中新增图表重绘触发：调用 `charts.js` 的 `updateChart()` 使柱状图颜色立即适配新主题

**悬浮窗与移动端优化**:
- **悬浮窗拖拽超屏与内容截断修复** — `app.js` 中悬浮窗（`prompt-floater`）的拖拽逻辑从仅检查 `mousedown`/`mousemove` 扩展为同时支持 `touchstart`/`touchmove`/`touchend` 移动端触摸事件。拖拽边界限制增强：`left` 不小于 `0`、不大于 `window.innerWidth - floater.offsetWidth`；`top` 不小于 `0`、不大于 `window.innerHeight - floater.offsetHeight`。内容区域 `max-height` 动态计算确保不超出视口
- **悬浮窗默认宽度防撑大** — `main.css` 中为悬浮窗新增 `min-width: 280px` 和 `max-width: 90vw` 约束，防止内容过长时悬浮窗被撑大到超出可视范围
- **移动端自定义缩放拖拽手柄** — `panel.html` 的悬浮窗右下角新增 `prompt-floater-resize-handle` 自定义手柄元素，`tech-tree.css` 中桌面端隐藏该手柄（使用浏览器原生 `resize: both`），移动端（`max-width: 768px`）隐藏原生 resize 并显示自定义大尺寸手柄（`40px × 40px`），方便手指操作

**访问日志与封禁管理**:
- **访问日志桌面端表格附注列优化** — `main.css` 中访问日志表格的附注列（`note` 列）从固定列宽改为 `auto` 自适应，长文本通过 `text-overflow: ellipsis` + `overflow: hidden` + `white-space: nowrap` 截断溢出，保留完整内容在 `title` 属性中供 hover 查看。移动端卡片布局不受影响
- **封禁 IP 备注 128 字符限制** — Web 前端封禁原因输入框（`#ban-reason-input`）新增 `maxlength="128"` 属性并实时显示字符计数器（如 `45/128`），服务端 `web/server.py` 的封禁接口在写入存储前同步截断超过 128 字符的原因文本（取前 128 字符 + `...`）
- **封禁列表桌面端短列 nowrap** — `main.css` 中封禁列表的短列（来源 IP、封禁时间、到期时间、状态标签）添加 `white-space: nowrap` 防止列宽过窄时文字换行导致行高参差不齐，原因列保持 `white-space: normal` + `word-break: break-word` 允许自动换行
- **封禁原因自动换行不溢出** — 封禁列表的原因列文字通过 `word-break: break-word` + `overflow-wrap: break-word` 自动换行，不会撑破表格或溢出到相邻列

**其他 UX 增强**:
- **Web 面板启动日志三级地址输出** — 启动日志从仅显示 `localhost:端口` 升级为完整三级地址输出：第一级本地（`localhost:端口` + `127.0.0.1:端口`）、第二级内网（本机所有 IPv4 地址 + 非 `fe80::` 的 IPv6 地址，格式 `➜ 内网:`）、第三级公网（通过 ipify/ifconfig.me/icanhazip 三个来源并发获取公网 IP 并去重，格式 `➜ 公网:`）。获取超时 3 秒，任一来源成功即显示。架构文档 `ARCHITECTURE.md` 同步更新了完整的访问地址说明表格
- **Web UI 前端缩放按钮** — `panel.html` 的流程图页面（tech-tree）左上角新增缩放控件组（`#zoom-ctrl`）：`+` 放大（每次 `scale + 0.15`，上限 `3.0`）、`⊡` 适应屏幕（重置 `scale = 1.0`）、`−` 缩小（每次 `scale - 0.15`，下限 `0.3`）。仅在流程图页面显示（`app.js` 的 `switchPage()` 中通过 `classList.toggle('hidden')` 控制），配置面板打开时自动隐藏（`body.config-panel-open #zoom-ctrl { display: none }`）

**🔑 AstrBot v4 平台重启认证升级与 Web 重置行为修正**:
- **JWT 优先 + 密码降级两级认证** — Web 面板触发的插件重载和 AstrBot 重启操作，认证方式从单一密码登录升级为两级策略：第一优先级通过 dashboard 配置中的 `jwt_secret` 直接签发 HS256 JWT token，调用 AstrBot 仪表盘 REST API（重载：`POST /api/plugin/reload`，重启：`POST /api/stat/restart-core`）；JWT 签发失败时自动降级为密码登录（`POST /api/auth/login` → 从 `data.token` 提取 token），兼容旧版 AstrBot v3。JWT 优先策略避免每次重启都需传输明文密码，同时绕过了某些 AstrBot v4 版本中密码登录接口的兼容性变更
- **Web 端重启状态轮询反馈** — `web/server.py` 中新增 `GET /api/restart-status` 接口，返回当前重启/重载操作的状态对象（`{type, status, message, timestamp}`，status 枚举：`pending` → `in_progress` → `success` / `failed`）。前端 `app.js` 在触发重启/重载后启动 2 秒间隔的轮询（最多 60 次 = 2 分钟），状态栏文案根据返回值动态更新（如"插件已重置，AstrBot 重启中...等待服务恢复..."），一旦轮询到服务器恢复（新进程启动）立即 `location.reload()` 刷新页面
- **会话管理重置行为修正** — Web 面板「会话管理」中每张会话卡片上的「重置」按钮（调用 `POST /api/commands/reset-here`）的行为从"等同于聊天指令 `gcp_reset_here`"修正为仅清除运行时状态：调用插件实例的 `_clear_session_runtime()` 清除注意力数据、情绪追踪、概率状态、冷却计时、Smart 并发待合并注册记录和窗口缓冲残留，但**不删除聊天记录文件**、**不设置历史截止时间戳**（`history_cutoff.json`）。重置后自动触发插件重载（reload 模式）使清理立即生效。聊天指令 `gcp_reset_here` 保持原有行为（删文件 + 设截止戳）。两种重置方式的职责明确区分：Web 按钮 = 轻量运行时重置，聊天指令 = 完整历史清除
- **`reset_here` 与 `clear_image_cache` 的 reload 分支补全** — `_handle_cmd_reset_here()` 和 `_handle_cmd_clear_image_cache()` 的 reload 模式分支此前缺失实际的重载触发调用（仅设置了 `auth_mgr.mark_web_initiated_reload()` 但未调用 `_create_deferred_reload_task()`），修复后补全该调用，reload 分支行为与 restart 分支一致
- **cutoff 日志补全** — `gcp_reset_here` 和 `gcp_reset` 操作中的历史截止时间戳（`history_cutoff.json`）创建/更新操作现在输出明确的 INFO 日志（`[会话重置] 已设置历史截止戳: {session_id} → {cutoff_time}`），方便排查跨重置操作的历史记录过滤问题

**🔧 戳一戳消息后提示词注入修复**:
- **反戳后元数据注入不生效修复** — 修复戳一戳消息处理流程中一个隐蔽 Bug：当插件收到戳一戳消息并触发直接反戳（`poke_reverse_on_poke_probability > 0`，即随机反戳概率 > 0）后，旧版代码在发送反戳动作后通过 `event.stop_event()` + `return` 直接终止了整个消息处理链路（包括 `main.py` 中后续的 `include_sender_info`、`include_timestamp` 等元数据注入代码）。这导致：尽管用户在后端配置中开启了发送者信息注入和时间戳注入，但被反戳处理拦截的消息上这两类元数据完全不生效，保存到历史的戳一戳事件文本缺失发送者名称和时间戳。修复后，反戳动作改为通过内部的 `poke_reply_in_progress` 标记控制重复反戳，不再通过 `stop_event()` 中断链路，后续的元数据注入、消息缓存、历史保存等步骤正常执行

**💾 gcp_clear_image_cache 旧版缓存兼容清理**:
- **旧版残留路径兼容清理** — `web/server.py` 的 `_resolve_image_cache_file()` 方法优先返回当前主缓存文件路径（`image_cache/descriptions.jsonl`），若不存在则检测旧版残留路径（`image_description_cache.json`）。`gcp_clear_image_cache` 指令和 Web 面板的图片缓存清理按钮（`POST /api/session/clear-image-cache` 和 `POST /api/commands/clear-image-cache`）均通过 `_clear_image_cache_storage()` 调用此方法，确保从旧版本升级的用户不会留下无法通过正常清理流程移除的孤立缓存文件

**🐛 其他细节修复**:
- **`proactive_system_prompt` 变量名拆分遗漏修复** — `proactive_chat_manager.py` 的 `_save_proactive_to_history()` 中，保存到历史的系统消息文本使用了不一致的变量引用路径：部分分支引用旧版 `proactive_system_prompt`（此变量在 v1.2.0 重构时已拆分为 `proactive_marker` + `proactive_prompt`），导致特定配置组合下（如重试场景 + 注意力信息注入）主动对话保存到历史的系统提示词拼接异常。修复后统一使用 `proactive_marker + proactive_prompt` 拼接
- **内容过滤规则正则回溯优化** — `content_filter.py` 中部分 Range 过滤正则表达式（`A*B` 模式）在文本中包含大量重复标记边界符号（如 `{{` `}}`）时可能触发灾难性回溯的超时问题，修复后在各规则的 `*` 部分增加了非贪婪量词限定和原子组保护
- **Web 面板幽灵会话根治** — `web/server.py` 的 `_collect_runtime_sessions()` 在收集会话 key 时新增 `_SAFE_SESSION_RE` 正则校验（拒绝空字符串、None、纯空白、含路径遍历字符的异常 key），从源头杜绝异常 key 进入会话列表。同时 `message_cache_manager.py` 的 `cache_message()` 新增 `chat_id` 防御性校验，拒绝无效 chat_id 以避免产生幽灵缓存条目。双重防护确保前端的幽灵会话问题彻底根除（此前仅前端做空数据保护层）
- **编辑保存直接覆盖源文件** — Web 面板文件管理中的在线编辑保存逻辑（`POST /api/files/save`）改为直接覆盖源文件而非创建带有时间戳后缀的备份副本，避免编辑后文件路径变化导致引用该文件的其他功能（如自定义提示词文件）失效

**📚 文档全面补充与更新**:
- **关闭平台「只 @ 机器人是否触发等待」提示补充** — `CONFIG_REFERENCE.md` 的群聊等待窗口配置章节、`ARCHITECTURE.md` 的平台配置建议章节、`_conf_schema.json` 的 `enable_group_wait_window` 配置 hint、`README.md` 的快速开始章节中均新增/强化了关闭平台 `empty_mention_waiting` 开关的提醒说明：平台的空 @ 等待是群级别拦截，会劫持任意用户的消息并人工插入 @bot 后重新入队，与本插件冲突且会导致认错发送者。使用本插件的等待窗口功能前必须先关闭平台侧的同名开关
- **全部说明文档版本号更新** — `README.md`、`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/CONFIG_REFERENCE.md`、`docs/MESSAGE_WORKFLOW.md`、`docs/PROJECT_STRUCTURE.md`、`docs/DESKTOP_COMPATIBILITY.md` 中的所有版本引用从 V1.2.3.hotfix.1 更新为 V1.2.3.hotfix.2
- **架构文档全面更新** — `ARCHITECTURE.md` 扩充了以下章节：第三方插件注入隔离机制（逐插件追踪 → handler wrapper → 具名标记 → 全字段覆盖的完整链路）、Web 面板安全机制（IPV6 全面适配、双栈自动化、速率窗口豁免）、AstrBot v4 重启认证流程（JWT 优先+密码降级）、Web 面板访问地址输出（本地/内网/公网三级）、消息元数据区机制、戳一戳双层标注架构、引用消息三段式格式
- **配置项文档补充** — `CONFIG_REFERENCE.md` 新增/补充了 IPV6 兼容性说明（IP 名单、监听地址、安全机制）、`empty_mention_waiting` 关闭提醒、Web 面板各项新功能的行为说明
- **消息工作流程文档更新** — `MESSAGE_WORKFLOW.md` 补充了消息元数据区注入流程、戳一戳双层标注机制、引用消息解析流程、工具调用多轮链路（正常完成 vs 异常终止的差异路径）
- **项目结构文档更新** — `PROJECT_STRUCTURE.md` 更新了模块列表（新增 `web/auth.py`、`web/security.py` 等之前未列出的模块）和版本信息

**修改文件**:
- `utils/reply_handler.py` — 缓存友好的提示词拼接顺序重排，位置引用从"上方"改为"下方"，覆盖/拼接模式同步适配，新增防回声约束
- `utils/proactive_chat_manager.py` — 后台循环 Task 身份识别防双循环并发，普通回复时主动对话状态双重保险关闭，`proactive_system_prompt` 变量拆分修复，缓存友好的提示词拼接
- `utils/decision_ai.py` — 缓存友好的提示词拼接顺序重排，位置引用从"上方"改为"下方"，覆盖/拼接模式同步适配
- `utils/frequency_adjuster.py` — 缓存友好的提示词拼接顺序重排
- `private_chat/private_chat_utils/private_chat_reply_handler.py` — 缓存友好的提示词拼接顺序重排，覆盖/拼接模式同步适配，新增防回声约束
- `private_chat/private_chat_utils/private_chat_proactive_chat_manager.py` — 同步主模块的主动对话防护和提示词优化
- `utils/image_handler.py` — 新增视频/语音/文件三类媒体的提取、标记内联、缓存剥离前富化管线，纯语音/文件消息防丢弃
- `utils/message_processor.py` — 消息格式重构为冒号前元数据区+冒号后用户内容区，时间戳/发送者信息/戳一戳事件统一注入元数据区，新增兜底名称检查，完整实现戳一戳持久化事件构建
- `utils/message_cache_manager.py` — 新增 `chat_id` 防御性校验拒绝无效 key 防止幽灵会话
- `utils/message_cleaner.py` — 过滤规则正则回溯优化，适配新引用消息格式（`>>>` 分隔符）
- `utils/content_filter.py` — 过滤规则正则回溯优化（非贪婪量词+原子组保护）
- `utils/probability_manager.py` — 概率过滤信息描述从"失败"纠正为"未通过"
- `utils/context_manager.py` — 上下文构建适配元数据区格式，冒号前元数据区正确传递到 AI
- `utils/forward_message_parser.py` — 转发消息发送者名称兜底检查
- `utils/system_prompt_rewriter.py` — 平台提示词清洗适配新消息格式
- `main.py` — 逐插件上下文追踪从 monkey-patch 升级为 handler wrapper 架构（`_gcp_instrumented_call_event_hook` → `_install_per_plugin_context_tracking`），全字段追踪覆盖（system_prompt/extra_user_content_parts/image_urls/audio_urls），逐插件具名标记合并管道（`_merge_per_plugin_prompt_injections` / `_merge_per_plugin_context_injections`），戳一戳消息反戳后元数据注入修复（不再通过 `stop_event()` 中断链路），多轮工具调用 LLM_RESULT 误判修复（`on_decorating_result` 不再强制完成 LLM_RESULT），工具调用异常兜底保存（`_finalize_bot_reply_save`），反戳后消息保存/缓存更新/名称兜底全覆盖，Smart 并发批量名称兜底
- `web/server.py` — AstrBot v4 重启认证 JWT 优先+密码降级（`_do_deferred_reload` / `_do_deferred_restart`），重启状态轮询接口（`GET /api/restart-status`），会话管理重置行为修正（仅清运行时/不删文件/不设截止戳），`reset_here` 与 `clear_image_cache` 的 reload 分支补全，Web 面板启动日志三级地址输出（本地/内网/公网），`localhost` 归一化为 `127.0.0.1`，客户端 IP 规范化管道（`_get_client_ip` + `_normalize_ip`），双栈自动启用，幽灵会话根源修复（`_SAFE_SESSION_RE` 校验），封禁原因 128 字符截断，速率窗口自动刷新豁免（`X-GCP-Auto-Refresh` 头检测）
- `web/security.py` — IP 规范化方法（`_normalize_ip`），IP 合法性校验与边界警告（`_validate_ip_list`），速率限制自动刷新豁免（`check_authenticated_rate` 新增 `is_auto_refresh` 参数），全安全机制 IPv6 适配
- `web/auth.py` — IP 规范化比较（登录、封禁等场景的 IP 匹配）
- `web/templates/panel.html` — 图表自动刷新开关 UI（含绿色圆点指示器），缩放按钮控件（`#zoom-ctrl`），悬浮窗拖拽手柄（`prompt-floater-resize-handle`），访问日志无自动刷新提示文字
- `web/static/js/app.js` — 心跳状态面板完整重构（自动/手动刷新双机制、Leader 广播+Follower 接收、`_loadHeartbeatStatus` 首次加载兜底、增量更新 DOM），主题切换触发图表立即重绘，重启状态轮询反馈，悬浮窗拖拽超屏修复+移动端触摸支持，封禁原因 128 字符限制+计数器，缩放按钮页面切换显隐控制，全页面手动刷新+toast 反馈，插件重启期间自动刷新静默容错
- `web/static/js/session-mgr.js` — 会话列表 3 秒自动刷新（进出详情自动暂停/恢复），编辑模式禁刷新，聊天记录内容比对增量更新+回退全量重建逻辑，幽灵会话计数与清理
- `web/static/js/charts.js` — 柱状图始终重绘移除主题色缓存守卫，概率柱状图统一红色，无会话手动刷新去守卫，3 秒自动刷新开关
- `web/static/js/api.js` — `X-GCP-Auto-Refresh` 请求头自动注入，`verify()` 支持 options 参数，心跳请求不计入速率窗口
- `web/static/js/flow-data.js` — 概率过滤节点标签从"概率过滤失败"改为"概率未通过"
- `web/static/js/tech-tree.js` — 流程图缩放控件交互逻辑
- `web/static/js/prompt-data.js` — 第三方注入标记预览同步更新为具名配对格式
- `web/static/css/main.css` — 悬浮窗默认宽度约束（min/max-width），移动端拖拽手柄样式，访问日志附注列 auto 列宽+截断溢出，封禁列表短列 nowrap+原因列自动换行，自动刷新开关样式（`.auto-refresh-toggle`），无自动刷新提示文字样式（`.log-refresh-hint`）
- `web/static/css/tech-tree.css` — 缩放按钮样式（桌面/移动端适配），悬浮窗 resize handle 样式（桌面端隐藏/移动端显示大尺寸手柄），配置面板打开时缩放按钮隐藏
- `_conf_schema.json` — 配置项 hint 全面修订（IPV6 地址说明、IP 名单边界警告、`empty_mention_waiting` 关闭提醒、概率过滤用语纠正），新增 Web 面板相关配置项 hint 补充
- `metadata.yaml` — 更新版本号到 V1.2.3.hotfix.2，更新插件简介
- `README.md` — 更新版本号、更新亮点章节、更新日志章节
- `CHANGELOG.md` — 更新为 V1.2.3.hotfix.2 版本更新记录
- `docs/ARCHITECTURE.md` — 全面扩充第三方插件注入隔离、Web 安全机制、AstrBot v4 兼容性、消息元数据区、Web 面板访问地址等章节
- `docs/CONFIG_REFERENCE.md` — 补充 IPV6 兼容性说明、`empty_mention_waiting` 关闭提醒、Web 面板各功能行为说明
- `docs/MESSAGE_WORKFLOW.md` — 补充消息元数据区注入流程、戳一戳双层标注、引用消息格式、工具调用多轮链路
- `docs/PROJECT_STRUCTURE.md` — 更新模块列表和版本信息
- `docs/DESKTOP_COMPATIBILITY.md` — 更新版本兼容性表格
- 所有 Python 模块 — 统一更新文件头版本号到 V1.2.3.hotfix.2

---

### V1.2.3.hotfix.1 (2026-05-23)

**AI 回复纲领行动导向重写（杜绝判断文本泄露）+ 内容过滤配置说明补充 + Smart 并发可靠性修复 + 上下文清洗精准化 + 戳一戳消息保存修复 + Web 面板空白会话修复与浏览器兼容性增强 + 判断型 AI 推理日志优化 + 概率日志修复 + 文档全面更新**

**🧠 AI 回复纲领行动导向重写（杜绝判断文本泄露）**:
- **群聊回复 AI 提示词重写** — 将 `reply_handler.py` 的 `SYSTEM_REPLY_PROMPT` 从原先包含"只回复""不应回复"等严格规则和负面示例的判断型措辞，彻底重写为行动导向纲领：首句改为"你的任务：直接生成回复内容。系统已将消息交给你处理，你无需考虑'该不该回复'或'该不该开口'——这些判断已经完成。"，核心原则精简为"你只负责生成回复文本，不负责判断、不负责分析、不负责解释为什么回复或不回复"，新增"回复身份"专节列出所有应避免的内部判断/过渡句式（"是否该回复""现在该不该开口""我决定这么说""我先想一下"等），并明确指示"如果你脑中有判断、犹豫、筛选、改写、取舍，这些都只能停留在内部，不要写出来"。去除原有冗长的负面示例列表，改为正面引导式的行动说明
- **私聊回复 AI 提示词同步重写** — `private_chat_reply_handler.py` 的 `SYSTEM_REPLY_PROMPT` 同步重写为行动导向：首句改为"你的任务：直接生成回复内容。系统已将消息交给你处理，你无需考虑'该不该回复'——这些判断已经完成。"，核心原则同步精简，与群聊回复 AI 保持一致的防泄露语义
- **主动对话生成 AI 提示词重写** — `proactive_chat_manager.py` 的 `default_proactive_prompt` 重写为行动导向：首句改为"你的任务：直接生成你要说的话。系统已经完成了'现在适不适合主动开口'的判断，你无需再考虑该不该说话。你只需根据上下文自然地发起话题：可以延续最近的讨论，可以回应未回复的消息，也可以开启全新话题。无论选择哪个方向，直接说出来就好，不要解释你的选择。"，新增"不要输出判断腔"和"不要外显内部取舍过程"两条核心要求，去除原有冗余的禁止列表，改为简洁的行动引导
- **Web 端提示词预览同步** — `prompt-data.js` 中读空气 AI、回复 AI、主动对话 AI 三处默认提示词预览内容同步更新为行动导向版本，与后端实际使用的提示词保持一致，Web 面板用户看到的预览即实际生效内容
- **彻底杜绝判断文本泄露** — 三种回复 AI（群聊/私信/主动对话）的提示词现在均以"你的任务：直接生成..."开头，从第一条指令就建立行动框架。AI 不再看到"判断是否回复""决定要不要说话"等判断型措辞，因此不会在输出中残留"我觉得现在不适合开口""我应该回复这条"等内部决策语言，从源头杜绝判断文本泄露到用户可见的回复中

**📝 内容过滤配置说明全面补充**:
- **规则执行顺序说明** — `_conf_schema.json` 中 `output_content_filter_rules` 和 `save_content_filter_rules` 的 hint 新增规则执行顺序说明：规则按列表顺序逐条执行，后一条在前一条的结果上继续过滤，规则顺序会影响最终效果；建议将 Head/Tail 等大范围规则放在前面，精细的 Range 规则放在后面
- **三种模式匹配行为差异** — 补充三种过滤模式的精确行为差异说明：① 范围过滤（`A*B`）循环匹配直到文本中再无匹配，可清除所有出现的标记块；② 头部过滤（`{{>*B`）仅匹配第一个结束标记 B，不循环；③ 尾部过滤（`A*>}}`）仅匹配第一个开始标记 A，不循环。明确标注各模式的循环/单次行为差异
- **输出/保存过滤适用范围** — 在 `_content_filter_section_header`、`enable_output_content_filter`、`enable_save_content_filter` 三处的 hint 中明确注明：输出过滤和保存过滤的开关对「普通回复」和「主动对话生成」两条路径同时生效，共用同一套过滤规则和同一个过滤器实例，没有单独的路径开关。主动对话的回复在发送前和保存前同样经过这两道过滤
- **典型场景建议** — `save_content_filter_rules` 的 hint 新增典型使用场景指引：输出保留思考过程、保存时过滤 → 只在 save 规则配置；输出过滤思考过程、保存时保留 → 只在 output 规则配置；两者都过滤 → 两套规则各自配置
- **内容过滤模块文档注释补充** — `content_filter.py` 模块头部注释补充了过滤适用范围的说明，明确输出过滤控制 AI 发送给用户看的内容、保存过滤控制 AI 写入历史记录的内容，两套规则完全独立互不影响

**🔄 Smart 并发可靠性修复**:
- **被吸收消息存储丢失修复** — 修复 Smart 并发模式下，被 anchor 吸收的 follower 消息在特定路径（尤其是 anchor 自身也被更高优先级的消息吸收时）中存储引用丢失的问题，确保所有被吸收的消息都能在批次回复后正确写入历史存储，不再出现"消息明明被AI看到了但历史里找不到"的情况
- **空消息入口过滤增强** — Smart 并发管理器在消息注册到达序号之前增加空消息检测层，平台产生的真空消息在入口处直接丢弃，不注册到达序号、不参与批次合并、不进入任何后续处理流程，杜绝空消息污染批次或占用并发资源
- **批次双上限（数量/时间）加固** — 数量上限（`smart_concurrent_max_batch_size`）和时间上限（`smart_concurrent_merge_wait`）的生效逻辑进一步加固：两者同时启动、各自独立计数、任一触发立即停止合并，修复了极端并发场景下双上限可能被绕过导致批次无限膨胀的边界问题
- **回复提示词防判断泄露** — 修复 Smart 并发回复阶段追加的批次提示在某些条件下残留判断型措辞，导致回复 AI 在生成最终发言时泄露内部决策逻辑的问题。现在批次提示严格限定为"当前主回对象+可自然顺带回应"的中性引导，不包含任何判断/决策语义，且保存历史前通过 `MessageCleaner` 兜底过滤

**📝 上下文构建与提示词精细化**:
- **Smart 并发提示词调整** — 优化 Smart 模式下追加消息区域的上下文表达方式，让 AI 更清晰地理解"追加消息是几乎同时到达的背景参考"而非需要逐条回复的新消息；批次回复提示文本更加简洁，减少不必要的啰嗦说明
- **平台提示词清洗精度提升** — 调整上下文构建中对平台提示词的清洗策略：`SystemPromptRewriter` 在 system_prompt 路径的 LTM 剥离逻辑中，对平台注入的群聊历史条目格式匹配更加精确（支持条目内多行消息的完整保留，不再错误地跨条目切割）；对 prompt 路径的 LTM 检测，双重条件（header 短语 + 条目格式）同时命中才判定为平台 LTM 文本并丢弃，进一步降低第三方插件内容被误过滤的概率

**⏱️ Smart 并发触发前可配置实停**:
- **快照前收拢延迟（`smart_concurrent_claim_delay`）** — 新增配置项，控制 anchor 在执行 `claim_batch`（一次性快照）前等待的极短时间（默认 0.3 秒，可配置范围 0~2 秒）。在这个短暂窗口内，几乎同时到达的消息有机会完成 payload 挂载（图片描述提取、转发解析等），从而被同一批次吸收，显著减少"晚到几十毫秒就被分到下一批"的情况
- **仅非强制消息等待** — @消息、关键词触发的强制消息不等待实停延迟，立即执行快照，保证高优先级消息的响应速度不受影响
- **与合并超时独立** — 实停延迟是快照前的短暂收拢（毫秒级），与合并超时时间上限（秒级）互不干扰，各自独立生效

**👆 戳一戳消息处理修复**:
- **戳一戳消息保存修复** — 修复了收到戳一戳消息并在处理流程中触发直接反戳后，插件错误地在反戳动作完成后直接 `return`，导致后续的消息记录保存（用户戳一戳事件文本 + AI 反戳动作事件文本）和上下文缓存更新全部被跳过的关键 Bug。修复后无论反戳动作是否成功，用户戳一戳事件与 AI 反戳动作事件都会正确保存到官方存储和自定义存储，消息缓存也正常更新，不会因反戳而丢失上下文

**🔧 Web 面板修复与增强**:
- **空白会话修复** — 修复 Web 端在极小概率下出现空白会话的问题：当会话的运行时状态在 Web API 查询的极短窗口内刚好被清理时，会话管理接口返回了不完整的数据导致前端渲染空白。修复后增加了空数据保护层，对缺失关键字段的会话自动填充安全默认值并标记为"已过期"，前端正常展示而非白屏。此问题在插件重启后会自然消失（因运行时状态重建），但修复后不再需要重启
- **重置指令范围补充** — 补充 Web 面板中重置/清理指令的覆盖范围：全局重置（`gcp_reset`）现在正确覆盖了 Smart 并发管理器的待合并池、等待窗口令牌追踪、以及运行中的批次状态；单会话重置（`gcp_reset_here`）现在正确清理了该会话的 Smart 待合并注册记录和窗口缓冲残留，确保重置后不会出现"旧批次数据干扰新消息处理"的问题
- **Web 前端浏览器兼容性扩大** — 修复了部分非 Chromium 内核浏览器（如旧版 Safari、Firefox ESR、部分嵌入式 WebView）在加载 Web 管理面板时出现的渲染问题：CSS `dvh` 单位的 fallback 处理、`-webkit-overflow-scrolling` 的跨浏览器兼容、`backdrop-filter` 毛玻璃效果的渐进增强降级、以及部分 ES2020+ 语法在旧版浏览器上的兼容性 polyfill。确保使用不同内核的浏览器均能正常加载和操作面板，不会出现布局错乱、白屏或交互失效

**🧠 判断型 AI 推理日志优化**:
- **推理未生效时的日志说明** — 优化判断型 AI（读空气 AI、频率调整 AI、主动对话判断 AI）中额外推理功能的日志输出：当用户开启了额外推理但模型实际返回的结果中未检测到推理标记时，系统现在会输出明确的 WARNING 日志，提示"推理已开启但模型未输出推理块，可能原因：模型不支持/提示词被覆盖/推理标记不匹配"，而不是静默地跳过推理解析。这能帮助用户快速定位"为什么开了推理但AI不听话直接输出结果"的问题
- **推理日志分类输出** — 每种判断型 AI 的推理日志现在携带明确的来源标签（`[读空气AI推理]` / `[频率AI推理]` / `[主动对话判断AI推理]`），方便在 AstrBot 日志中区分不同判断链路的推理内容

**🩹 概率日志修复**:
- **概率计算日志准确性修复** — 修复了概率计算链路中若干日志输出的值不准确的问题：部分中间步骤的日志在打印概率值时使用了缓存变量而非实时计算值，导致日志显示的"当前概率"与实际用于判断的概率不一致（判断本身使用正确值，仅日志显示有误）。修复后所有日志输出的概率值均与实际决策用值保持一致，方便调试和调参

**📚 文档全面补充与更新**:
- **全部说明文档更新** — 更新了项目中所有说明文档的版本号、功能描述和配置说明，确保与 V1.2.3.hotfix.1 版本的实际功能保持一致
- **配置项文档补充** — `CONFIG_REFERENCE.md` 新增了 `smart_concurrent_claim_delay` 等新配置项的完整说明
- **消息工作流程文档更新** — `MESSAGE_WORKFLOW.md` 补充了 Smart 并发快照前实停延迟的流程说明
- **桌面端兼容文档更新** — `DESKTOP_COMPATIBILITY.md` 更新了版本兼容性表格
- **项目结构文档更新** — `PROJECT_STRUCTURE.md` 更新了模块列表和版本信息
- **深度指南文档更新** — `ARCHITECTURE.md` 更新了相关的机制说明和版本引用

**修改文件**:
- `utils/reply_handler.py` — AI 回复纲领重写为行动导向（去除严格规则和负面示例，杜绝判断文本泄露），Smart 并发提示词调整，批次回复提示防判断泄露
- `utils/proactive_chat_manager.py` — 主动对话 AI 回复纲领重写为行动导向，判断型 AI 推理日志优化
- `utils/decision_ai.py` — 判断型 AI 提示词语义优化，推理日志优化（未生效时 WARNING 提示 + 来源标签）
- `private_chat/private_chat_utils/private_chat_reply_handler.py` — 私聊 AI 回复纲领同步重写为行动导向
- `utils/content_filter.py` — 模块文档注释补充过滤适用范围说明
- `web/static/js/prompt-data.js` — Web 端提示词预览同步更新为行动导向版本
- `_conf_schema.json` — 内容过滤配置 hint 全面补充（规则执行顺序、三种模式匹配行为差异、输出/保存过滤适用范围说明），新增 `smart_concurrent_claim_delay` 配置项
- `utils/smart_concurrent_manager.py` — Smart 并发被吸收消息存储丢失修复，空消息入口过滤，批次双上限加固，快照前实停延迟
- `utils/system_prompt_rewriter.py` — 平台提示词清洗精度提升（system_prompt 路径条目格式精确匹配 + prompt 路径双重条件检测）
- `utils/message_cleaner.py` — 新增 Smart 批次提示泄露兜底过滤规则
- `utils/frequency_adjuster.py` — 频率判断 AI 推理日志优化
- `utils/probability_manager.py` — 概率计算日志准确性修复
- `main.py` — 戳一戳消息保存修复，新增 `smart_concurrent_claim_delay` 配置项读取，Smart 并发重置范围补充
- `web/server.py` — Web 面板空白会话修复（空数据保护层），重置指令覆盖范围补充
- `web/templates/panel.html` — 浏览器兼容性增强（CSS fallback、渐进增强降级）
- `web/templates/login.html` — 浏览器兼容性增强
- `web/static/js/app.js` — ES2020+ 语法兼容性 polyfill
- `web/static/js/tech-tree.js` — 浏览器兼容性 polyfill
- `web/static/js/session-mgr.js` — 空白会话保护层
- `web/static/css/main.css` — 跨浏览器 CSS 兼容性（dvh fallback、backdrop-filter 降级、-webkit- 前缀补充）
- `metadata.yaml` — 更新版本号到 V1.2.3.hotfix.1，更新插件简介
- `README.md` — 更新版本号、更新亮点和更新日志
- `CHANGELOG.md` — 更新为 V1.2.3.hotfix.1 版本更新记录
- `docs/ARCHITECTURE.md` — 更新版本引用和机制说明
- `docs/CONFIG_REFERENCE.md` — 新增 Smart 快照前实停延迟配置项说明，补充内容过滤配置说明
- `docs/MESSAGE_WORKFLOW.md` — 补充 Smart 并发快照前实停延迟流程说明
- `docs/PROJECT_STRUCTURE.md` — 更新模块列表和版本信息
- `docs/DESKTOP_COMPATIBILITY.md` — 更新版本兼容性表格
- 所有 Python 模块 — 统一更新文件头版本号到 V1.2.3.hotfix.1

---

### v1.2.2-hotfix.1 (2026-05-18)

**Smart 并发模式 + 注意力冷却重构 + System Prompt 兼容增强 + Web 面板安全全面加固（含暴力破解防护升级）+ 消息处理链路重构 + 判断型 AI 增强**

**🔄 Smart 并发模式**:
- **消息批次智能合并** — 同群多条消息按真实到达顺序注册，最早到达的担任主消息(anchor)，在读空气 AI 前吸收已准备好的后续消息，支持多用户批处理
- **统一上下文回复** — AI 一次性感知来自不同用户的同批次消息，生成连贯统一的自然回复，减少逐条回复的重复感
- **legacy / smart 双模式可切换** — 默认 legacy 传统串行模式保证兜底兼容；切换 smart 后启用智能合并
- **Smart批次回复提示增强** — 可选开关（`enable_smart_batch_reply_hint`，默认开启）。开启后 Smart 模式下回复阶段动态插入一段提示：当前触发 anchor 消息的用户仍是主要回复对象，但 AI 可以像真人一样自然顺带回应批次中来自其他用户的消息；不值得回的消息可以大方忽略。该提示只存在于运行时上下文，保存历史前会自动过滤
- **与 GWW 独立解耦** — Smart 模式不依赖群聊等待窗口(GWW)，两者可独立使用也可配合

**🛡️ System Prompt 兼容增强**:
- **SystemPromptRewriter 三级策略** — 保守增强版 system_prompt 重写器：① **精确命中**（默认，置信度最高）— 从原始 system_prompt 和当前 persona 的 `system_prompt` 文本中提取用户人格内容作为锚点，在平台上调整请求前，从 `raw_system_prompt` 中精确匹配人格边界，将人格之前的内容识别为「第三方插件前置内容（prefix）」，之后的内容识别为「其他插件后置内容（suffix）」并双重保留；② **轻量归一化** — 精确匹配失效时使用人格关键词定位和空白归一化策略重试；③ **保守回退** — 完全无法定位人格时宁重复不缺漏，保证主回复链不断。日志显式提示当前策略与置信度
- **差分法四大通道覆盖** — system_prompt（前/后缀识别）、prompt（短消息基线分割）、contexts（结构特征差分）、extra_user_content_parts（原样保护），全部第三方注入自动保留。5 条兼容路径全面覆盖：向 `system_prompt` 前插入规则块/管理指令、后追加状态面板/记忆文本、向 `req.contexts` 注入对话示例、向 `req.prompt` 前后追加长期说明、向 `extra_user_content_parts` 追加内容块等所有第三方注入方式均可被差分法自动识别并保留
- **提示词构建排版优化** — 将大型静态系统指令（GCP 插件自身的行为规范、规则和配置说明）从 `prompt` 前端移入 `system_prompt` 尾部，利用 LLM 服务商对 system_prompt 整块缓存优于 prompt 拼接的特性，提高每次 AI 调用的缓存命中概率，不改变原语义。该调整同时增强了与其他插件提示词的共存能力：无论第三方插件向哪个通道注入内容，本插件通过差分法自动提取并保留
- **回退保护** — 识别失败时进入保守兼容模式：宁重复不缺漏，保证主回复链不断，日志显式提示当前策略与置信度
- **注入透明化** — 其他插件内容以 `[第三方插件片段]` / `[第三方插件注入上下文]` / `[第三方插件补充信息]` 边界标记分隔，不同插件信息不会混淆。注入说明透明的分层引用，保留原文顺序（prefix → persona → suffix）

**🧊 注意力冷却重构**:
- **候选冷却 → 正式冷却双阶段** — 同一用户消息先进入「未接续谈保护」候选阶段（仅观察同一用户的后续消息，可配置 `pending_cooldown_grace_user_messages` / `pending_cooldown_max_wait_seconds`），观察期过后再决定是否升级为正式冷却，大幅减少误伤
- **冷却自动解除** — 正式冷却用户达到 `cooldown_max_duration`（默认 600 秒）后自动解冻
- **读空气未回复衰减独立化** — 从冷却机制中解耦，可在无冷却模式下单独生效
- **冷却状态纯运行时化** — 不再持久化到磁盘，重启后自动清空

**🔒 Web 面板安全全面升级**:
- **Argon2id 内存硬化哈希** — 替换 PBKDF2-SHA256 作为默认密码哈希算法（`ARGON2_TIME_COST=3`, `ARGON2_MEMORY_COST=65536`, `ARGON2_PARALLELISM=4`），有效抵抗 GPU 并行暴力破解
- **JWT + HttpOnly Cookie + 服务端会话表** — 会话安全全面升级，支持令牌过期/密码修改/令牌版本轮换/IP 变化时自动要求重新登录，JWT 密钥每次启动自动轮换
- **密码透明迁移** — 旧版本 PBKDF2-SHA256 密码在用户首次登录成功后自动透明升级为 Argon2id，无需手动操作
- **登录 IP 绑定校验** — 可选将客户端 IP 绑定到 JWT 令牌，防止令牌被劫持后在其他网络环境使用
- **全操作令牌校验链** — Web 面板所有 API 操作均需通过 JWT 验证 → 令牌版本校验 → 会话查找 → 会话状态检查 → 过期检查 → IP 绑定检查 → 心跳触摸 的完整安全链
- **后端文件实时保护** — 敏感文件（auth.json、jwt_secret.json、sessions.json、bans.json、access_log）禁止通过 Web API 读取或下载，后端直接拒绝所有对核心安全文件的访问请求；配置文件下载只允许下载插件自身配置文件，API 不接受任何前端传入的文件路径参数，仅在后端通过 `os.path.basename()` 提取安全文件名返回，永远不暴露服务器绝对路径
- **安全响应头全面配置** — 所有页面统一注入安全响应头：`X-Content-Type-Options: nosniff`（禁止 MIME 类型嗅探）/ `X-Frame-Options: DENY`（禁止页面被嵌入 frame，防点击劫持）/ `X-XSS-Protection: 1; mode=block`（启用浏览器 XSS 过滤器）/ `Referrer-Policy: no-referrer`（不泄露 Referrer）/ `Permissions-Policy: geolocation=(), microphone=(), camera=()`（禁用敏感硬件 API），全方位防止各类注入攻击
- **Nonce-based 严格 CSP** — Content-Security-Policy 使用每次请求唯一的 Base64 nonce（`secrets.token_urlsafe(24)`），三套独立 CSP 模板分别服务于登录页、面板页和错误/拦截页。script-src 不再依赖 `unsafe-inline`，内联脚本通过 nonce 匹配验证，外部脚本由 `'self'` 放行（同样不经 nonce），从源头阻断 XSS 代码注入
- **防爬虫与速率限制** — 可疑 UA 模式（bot/crawler/spider/scanner 等）自动检测与封禁，扫描路径探测（.php/.asp/.env/.git/wp-admin/.DS_Store 等常见漏洞扫描路径）自动拦截返回错误页，1 分钟滑动窗口速率限制（认证前 `/api/auth/login` 独立限频、认证后其他 API 独立限频，均为 1 分钟滑动窗口），`/robots.txt` 显式禁止所有爬虫收录
- **暴力破解分级锁定** — 登录失败递增锁定：5 次 → 30s / 10 次 → 60s / 15 次 → 300s / 20 次 → 600s / 30 次 → 1800s / 50 次 → 3600s；频率检测（默认 10 秒内失败 3 次直接封禁 IP）；窗口期衰减（默认 1 小时无活动自动清零失败计数）；达到最大阶梯解锁后再次尝试自动永久封禁（可配置封禁时长）。所有参数均可通过传统配置调整（Web 端只读）；受保护 IP（`web_panel_protected_ips`）永不被封禁
- **访问日志自定义工具提示** — 桌面端鼠标悬停、移动端点按显示完整附注，深色/浅色双主题自适应，自动边界检测
- **IP 访问控制** — 支持白名单/黑名单模式（`web_panel_ip_mode`：`whitelist` 仅允许白名单 IP / `blacklist` 禁止黑名单 IP），白名单 IP 绕过爬虫检测与封禁检查。反向代理部署在同机时自动读取 `X-Real-IP` / `X-Forwarded-For` 头获取真实客户端 IP（环回地址自动信任）；反向代理不在本机时需显式开启 `web_panel_trust_proxy` 才会信任代理头
- **心跳保活机制** — 前端定时心跳请求（`POST /api/auth/heartbeat`）维持会话活性。可见标签页和隐藏标签页使用独立可配置的心跳间隔（`web_panel_heartbeat_visible_interval_seconds` / `web_panel_heartbeat_hidden_interval_seconds`），心跳失败时采用指数退避重试策略（`web_panel_heartbeat_retry_base_seconds` → `web_panel_heartbeat_retry_max_seconds`）。心跳请求不触发认证速率限制，但正常更新服务端会话的 `last_heartbeat_at` 活跃时间戳；若 JWT 令牌过期（24 小时绝对有效期）或密码/令牌版本变更，下一次心跳直接返回 401 由前端统一处理重新登录
- **认证文件物理隔离** — auth.json 与 jwt_secret.json 分离存储，旧版混合文件启动时自动分离
- **日志自动清理** — 访问日志支持按保留天数自动清理（`web_panel_log_auto_clean` / `web_panel_log_retention_days` / `web_panel_log_clean_interval_hours`）

**💬 @消息 / 欢迎消息 / 戳一戳消息处理全面重构**:
- **@消息处理完全重构** — 重新设计 @ 消息的识别、过滤与上下文构建全链路：区分「纯 @AI」（仅 @机器人，不含其他信息）与「@AI+文字/图片/其他人/全体」场景，通过 `contains_ai`（消息中是否包含 @AI）与 `only_ai`（消息是否仅包含 @AI 无其他内容）双模式判定语义。空 @ 消息默认开启最近上下文强化，关联窗口同时检查消息数量（`single_at_message_reply_link_max_messages`）与时间跨度（`single_at_message_reply_link_max_seconds`），在通过读空气筛选后以中性口吻动态追加一段上下文提醒（提取近期缓存摘要与最近明确回复对象信息），让 AI 优先参考近期对话但不强行续话
- **欢迎消息解析对齐** — 入群欢迎消息支持四种处理模式（`normal` 正常处理 / `skip_probability` 跳过概率筛选 / `skip_all` 直接忽略 / `parse_only` 仅解析不回复），统一到主消息处理链路，不再独立绕过概率筛选与 AI 决策流程
- **戳一戳消息处理重构** — 支持三种模式（`ignore` 忽略所有 / `bot_only` 仅处理戳机器人 / `all` 处理所有戳一戳），重构为可配置概率跳过（`poke_bot_skip_probability`）和概率增值参考（`poke_bot_probability_boost_reference`），在群聊等待窗口（GWW）中支持 `bypass`（戳一戳绕过 GWW，不打断普通消息的收集）/ `force_close`（戳一戳强制关闭 GWW，优先处理）两种行为模式。戳一戳系统提示词在保存历史时自动过滤，不污染长期上下文
- **三种消息类型链路统一对齐** — @消息、欢迎消息、戳一戳消息的黑名单检查 → 概率筛选 → 读空气决策 → 回复生成全流程完全对齐，极短间隔连续消息场景下不再出现状态错乱。GWW 等待窗口内各消息类型的处理行为可独立配置（@消息 `force_close` / 关键词 `intercept` / 戳一戳 `bypass`），互不干扰

**🧠 判断型 AI 人格选择与额外推理**:
- **判断型 AI 独立人格配置** — 读空气判断 AI、频率调节 AI、主动对话判断 AI 三个判断链路均可独立选择是否注入人格（`decision_ai_include_persona` / `enable_frequency_ai_include_persona` / `enable_proactive_ai_include_persona`），且可分别指定使用哪一个人格（`decision_ai_persona_name` / `frequency_ai_persona_name` / `proactive_ai_persona_name`），留空则自动跟随当前会话生效人格。填写时必须使用完整人格名，否则系统检测不到时自动回退到当前会话人格，不会导致插件崩溃。回复生成 AI 和主动对话生成 AI 仍按当前会话人格运行（每次调用重新获取，切换会话人格后立即生效），不受此配置影响
- **额外推理全覆盖** — 三个判断型 AI 均支持独立开启额外推理（`enable_decision_ai_reasoning` / `enable_frequency_ai_reasoning` / `enable_proactive_ai_reasoning`）。开启后 AI 在给出最终判定前先自由输出推理块，推理内容由起始标记 `[[GCP_REASONING_START]]` 和截止标记 `[[GCP_REASONING_END]]`（三处共用配置，Web 面板三处入口同步显示与同步生效）包裹，然后在最后一行的标记后单独输出最终判定结果（yes/no 或 正常/过于频繁/过少）。系统通过 `ai_response_filter.py` 自动剥离推理块提取最终判定，不影响下游概率/状态更新。无论是原生带思考能力的模型（如 DeepSeek-R1）还是原生不带思考的模型均支持，让 AI 先推理一段再输出结果，保证答案更加精确
- **推理日志可控** — 每个判断 AI 的推理日志可独立开关与选择输出模式（`processed` 处理后推理块 / `raw` 模型原始文本），方便调试判断依据
- **推理协议自动补充** — 如果用户自定义了判断提示词但未包含额外推理协议（起始标记/截止标记/输出格式说明），系统自动在提示词末尾补充推理格式说明而非退回默认提示词，兼顾自定义语义与推理格式规范

**❄️ 冷群缓存自动转正**:
- **冷群转正机制** — 群聊长时间静默（无新消息）达到配置时间（`idle_cache_flush_delay_seconds`，默认 600 秒，可配置范围 60~7200 秒）后，缓存中尚未被回复的未转正消息自动转正写入持久存储（自定义存储 `chat_history/` + 平台官方历史 `platform_message_history` + 平台官方会话 `conversations`），防止群聊沉默过久导致缓存过期清空、上下文割裂。转正后的消息在下次 AI 回复时可被正常读取作为上下文参考
- **手动开启** — 默认关闭（`enable_idle_cache_flush` 默认 `false`），需手动开启。仅在确实需要长期保留冷群上下文的场景下启用
- **并发安全** — 转正执行前检测会话是否仍被其他处理链路（普通回复/主动对话）占用，忙碌时跳过当次转正在下次调度时重试；转正过程同时收集窗口缓冲消息（`window_buffered=True`），确保 GWW 窗口期内暂存的消息不因等不到后续消息触发而无法转正、最终丢失

**🔧 工具提醒逻辑重构**:
- **只提醒不控制** — 工具提醒从全局工具列表改为当前会话的 `req.func_tool` 实时生成，自动适应 AstrBot 内置工具（shell/cron/send_message 等）、WebSearch、知识库、沙箱、MCP、其他插件的 `@llm_tool` 注册工具等动态工具集。工具提醒仅做提醒和提示义务，不拦截也不限制 AI 的实际工具调用，AI 可完整调用平台上所有可用工具而不受提醒内容限制
- **skills_like 模式智能降级** — 检测到 `provider_settings.tool_schema_mode=skills_like` 时，自动只展示工具名称与功能描述，不展开参数列表。这样做是为了尽量不干扰 AstrBot 在 `skills_like` 模式下的两阶段工具 schema 暴露与 re-query 流程，同时减少跨工具参数串扰（如 `unexpected keyword argument 'silent'` 等典型串扰错误）。当 `tool_schema_mode=full` 或旧版 AstrBot 未提供该字段时，保持完整展示（名称 + 描述 + 参数）
- **生成失败静默降级** — 提醒文本生成异常时自动跳过提醒而非阻断回复流程
- **提醒文本历史过滤** — `[系统提示-工具提醒开始]...[系统提示-工具提醒结束]` 标记块在保存历史时自动清除，不污染上下文

**🔗 多轮工具调用交叉保存**:
- **按执行顺序交错保存** — AI 在单次推理中调用多个工具或发生多轮工具调用时，按实际执行顺序将 AI 中间推理文本与工具调用记录（调用名称 + 参数 + 返回值）交错写入对话历史，而非将所有工具调用记录全部堆在末尾。这样 AI 在后续轮次中能按真实执行时序理解工具调用上下文，而非面对一堆脱序的工具结果
- **交叉保存时机** — 每次工具调用完成即刻保存到历史，而非等待全部调用结束后批量写入，确保即使中途某次工具调用失败，已完成的工具调用记录也不丢失
- **格式兼容** — 同时兼容 ToolCall 对象和 dict 两种工具调用格式，支持 AI 无最终文本输出（仅工具调用）时的兜底保存

**🔍 Web 面板智能搜索与 UI 优化**:
- **科技树智能搜索** — 在科技树菜单顶部搜索框（快捷键 `Ctrl+K` / `Cmd+K`）输入关键词，可智能搜索所有配置项的名称（最高权重 35 分）、配置键名（32 分）、键标签（14 分）、提示文本（12 分）和描述文本（8 分），按匹配度加权排序。支持空格分词多关键词组合搜索、中文紧凑匹配（忽略空格差异）、键盘上下键导航结果列表。点击结果后自动定位到科技树中对应节点并高亮闪烁，不用再在大量配置中逐个翻找。搜索索引在各面板视图加载时自动构建，覆盖科技树中的所有配置节点
- **科技树连接线修复** — 修复连接线在部分节点布局下不准确与不直观的问题，同时跳过 `branchType: alternative` 分支步骤的连接线绘制（这些分支步骤在视觉上不需要连线连接），让科技树视图更加清晰
- **手机端全面适配** — 侧边栏改为滑入式抽屉（带毛玻璃遮罩层，点击遮罩自动关闭），顶部增加移动端专用导航栏（汉堡菜单 + 品牌标题 + 版本号），搜索框全宽显示并支持触屏输入，搜索结果改为底部抽屉式面板（最大高度 `50dvh`，避免遮挡过多内容），配置区域使用动态视口高度（`100dvh` 替代 `100vh`，解决移动浏览器地址栏变化导致的布局问题），按钮文字和间距适配小屏触控，内容区开启 `-webkit-overflow-scrolling: touch` 支持 iOS 惯性滚动
- **动画与视觉优化** — 优化侧边栏过渡动画、步骤节点入场动效、粒子路径动画的贝塞尔曲线缓动参数，让交互更加直观自然。登录页同样支持移动端适配
- **关联配置可视化标记** — 对存在关联或互斥关系的配置项增加特殊标志符（如关联箭头、互斥警告图标）与补充说明文字，多层级配置选项（如主开关下的子选项）在面板中展示完整的生效条件与优先级说明，让用户一眼看清配置之间的依赖与影响关系

**🩺 AI 调用错误处理全面格式化**:
- **5 类错误自动识别** — `format_ai_error()` 自动分类：① HTML 网关错误（502/503/504 状态码，含 Cloudflare "Please enable cookies" 等错误页面提示）→「AI 服务商故障」；② 上游空输出（模型返回空字符串或仅含空白字符）→「上游模型返回空输出」；③ HTTP 状态码错误（400-599，排除已归入网关的 502/503/504）→「请求参数/配置问题」；④ 网络错误（timeout/connection refused/DNS 解析失败等）→「网络问题」；⑤ 未匹配错误 → 自动截断至 300 字符防止日志爆炸
- **零副作用原则** — AI 调用失败时视为「从未发生」：不更新概率评分、不触发注意力变化、不延长冷却、不刷新沉默计时器、不改变任何内部状态，确保单次故障不影响后续判断
- **详细日志化输出** — 每次 AI 调用失败的原因（具体错误类型如 `TimeoutError`/`ConnectionError`/`APIStatusError`）、HTTP 状态码、错误详情均结构化写入日志，方便运维排查

**🖥️ AstrBot 兼容适配**:
- **桌面端自动检测与兼容** — 四级优先级自动检测桌面端环境：① `ASTRBOT_DESKTOP_CLIENT=1` 环境变量（最可靠，桌面端打包模式必设）；② `ASTRBOT_ROOT` 路径特征（桌面端默认指向 `~/.astrbot`）；③ `ASTRBOT_WEBUI_DIR` 资源路径（桌面端内置打包的 WebUI 路径）；④ `PYTHONNOUSERSITE=1` + `ASTRBOT_ROOT` 组合。支持 `auto`（默认，多重策略自动检测）/ `force_desktop`（手动强制桌面端模式）/ `force_standard`（手动强制标准版模式）三种模式，检测依据写入 `desktop_detected_env` 只读字段，Web 面板重启响应中附带 `is_desktop` 与 `desktop_info` 提示。桌面端与标准版在路径结构、重启机制、Python 环境、WebUI 加载方式等存在差异，详细说明见 [桌面端兼容说明](docs/DESKTOP_COMPATIBILITY.md)
- **AstrBot 最新版兼容修复** — 兼容新版 AstrBot (>=4.14) 中 `ToolLoopAgentRunner` 将 contexts 列表每条消息独立处理导致空消息场景下 `get_message_str()` 返回空字符串，进而平台跳过 LLM 调用的问题：空 @ 消息使用占位符替代空字符串保证 LLM 请求正常发起，`on_llm_request` 钩子（priority=-1）在最后将 `req.prompt` 换回完整 `full_prompt`，对 AI 推理行为无影响，同时不影响 LivingMemory 等 priority=0 的插件正常进行向量检索
- **主动对话上下文构建修复** — 修复新版 AstrBot 下主动对话构建上下文时，`contexts` 末尾出现连续 `user` 角色消息导致部分 LLM 返回空响应的问题

**📦 其他新增与修复**:
- **主动对话冷静期** — 普通对话回复后自动进入短期冷静，避免刚聊完就立刻主动发言打断对话节奏
- **LivingMemory 人格兼容模式增强** — 新增 `livingmemory_persona_compat_mode` 配置(auto/resolver_only/legacy_only/off)，适配不同版本的人格隔离策略；版本检测自动兼容 v1/v2 架构差异（`memory_engine` 位置不同，v2 在 `PersonaManager`、v1 在 `Provider`）
- **空@ 中性上下文强化** — 不含信息的单独 @ 消息通过读空气筛选后，在回复阶段动态提取近期缓存摘要与最近明确回复对象信息，以中性口吻提醒 AI 参考上下文但不强行续话
- **Web 面板会话管理修复** — 修复幽灵会话（有存储文件但无运行时状态）和重复会话问题：新增 `POST /api/session/clean-ghosts` 一键清理接口，前端会话列表展示实时幽灵会话计数与清理入口；修复会话列表因平台标识不同导致的重复展示（以 `platform_type_chatid` 复合键去重），数据统计更加准确
- **会话数据暴露最小化** — Web 面板会话查询接口严格按需返回必要字段，不再将完整存储数据一股脑传给前端让前端自己选取；聊天记录内容需单独请求获取，确保只暴露必须暴露的数据
- **自定义存储对齐官方存储** — 修复自定义存储在部分边缘情况下与官方存储（`platform_message_history`）的写入时序不一致问题：统一为「优先读官方 → 回退读自定义」的双轨策略；双轨写入互不阻塞（一条失败另一条仍成功）；`custom_storage_max_messages` 控制容量（0=禁用仅用官方，-1=无限至硬上限 10000）
- **指令匹配修复** — 修复完整指令检测（`enable_full_command_detection`）在部分边界情况下未能正常匹配的问题，确保单独的全匹配指令词（如 `new`、`help`、`reset`）及 `@bot 指令词` 格式被正确识别为指令并跳过 AI 处理，避免指令被当作普通消息发给 AI
- **回复上下文安全加固** — 修复 contexts 末尾连续 `user` 角色消息导致部分 LLM 返回空响应的问题，自动在纯图/纯@/空消息等边缘场景下插入兜底上下文保护，确保 LLM 请求正常发起
- **作者捐赠渠道** — Web 面板侧边栏底部新增「❤️ 支持作者」按钮，点击后弹出确认对话框（"即将跳转至爱发电进行捐赠。如果这个插件帮到了你，欢迎通过爱发电支持作者持续维护与更新。"），确认后在新标签页跳转至爱发电捐赠页面 [afdian.com/a/chat_plus](https://afdian.com/a/chat_plus)。此为作者官方唯一捐赠渠道，本插件完全免费开源，不进行任何商业收费

**🔧 兼容性**:
- 完全向下兼容 v1.2.1 配置，升级无需修改任何配置项
- Smart 并发模式默认关闭（`concurrent_mode` 默认 `legacy`），需手动切换启用
- 注意力冷却旧配置键已进入迁移提示，建议按新键名调整
- 冷群缓存转正默认关闭（`enable_idle_cache_flush` 默认 `false`），需手动开启
- 所有新功能默认使用安全合理的默认值
- 第三方插件提示词全面兼容：只要插件通过 `system_prompt` 前置/后置、`req.contexts`、`req.prompt`、`extra_user_content_parts` 任一通道注入内容，均可被 AI 看到

**修改文件**:
- `utils/smart_concurrent_manager.py` — **新增** Smart 并发批处理管理器
- `utils/system_prompt_rewriter.py` — **新增** 多策略 system_prompt 重写器（精确命中/轻量归一化/保守回退）
- `utils/cooldown_manager.py` — **重构** 候选冷却 → 正式冷却双阶段结构，冷却状态纯运行时化
- `utils/ai_error_formatter.py` — **新增** AI 错误分类与格式化（5 类识别 + 零副作用原则）
- `utils/tools_reminder.py` — **重构** 工具提醒实时生成，skills_like 自动降级，静默失败
- `utils/decision_ai.py` — 新增额外推理协议注入与解析，判断型 AI 人格独立选择
- `utils/frequency_adjuster.py` — 新增频率调节 AI 人格选择与额外推理
- `utils/proactive_chat_manager.py` — 新增主动对话 AI 人格选择与额外推理，AstrBot 新版兼容修复
- `utils/reply_handler.py` — 新增 Smart 批次回复提示增强，缓存命中率优化，空 @ 上下文强化
- `utils/message_processor.py` — @消息/欢迎消息/戳一戳消息处理链路统一重构
- `utils/message_cleaner.py` — 扩展空 @ 消息判定双模式（`contains_ai` / `only_ai`），工具提醒块过滤
- `utils/message_cache_manager.py` — 新增缓存去重处理，冷群转正支持
- `utils/context_manager.py` — 自定义存储对齐官方存储双轨策略，冷群转正写入
- `utils/memory_injector.py` — LivingMemory v1/v2 架构自动检测，人格兼容模式扩展
- `utils/ai_response_filter.py` — **新增** AI 回复过滤与推理块剥离
- `web/server.py` — Web 面板安全全面加固（JWT 全链校验、CSP nonce、安全响应头、防爬虫、速率限制、心跳机制、文件保护、配置下载安全、幽灵会话清理、日志自动清理）
- `web/auth.py` — Argon2id 密码哈希、JWT+会话表认证、密码透明迁移、IP 绑定、令牌版本轮换
- `web/security.py` — IP 访问控制、暴力破解分级锁定、防爬虫与速率限制、封禁持久化
- `web/templates/panel.html` — 移动端导航栏、搜索框、捐赠按钮
- `web/templates/login.html` — 移动端适配
- `web/static/js/app.js` — 配置下载安全加固、捐赠跳转
- `web/static/js/tech-tree.js` — 智能搜索索引构建与匹配、科技树连接线修复
- `web/static/js/utils.js` — 支持作者对话框
- `web/static/js/session-mgr.js` — 幽灵会话检测与清理
- `web/static/js/api.js` — 新增会话清理 API 调用
- `web/static/js/flow-data.js` — 配置项关联标记与说明
- `web/static/css/main.css` — 手机端全面适配样式、动画优化
- `web/static/css/tech-tree.css` — 搜索框样式、搜索结果面板、移动端抽屉式面板
- `main.py` — 集成所有新模块，新增 40+ 配置项读取，冷群转正调度，消息链路重构
- `_conf_schema.json` — 新增 40+ 配置项（Smart 并发、注意力冷却、判断型 AI 推理、冷群转正、桌面端检测、Web 面板安全等）
- `metadata.yaml` — 更新版本号到 v1.2.2-hotfix.1
- `docs/DESKTOP_COMPATIBILITY.md` — **新增** 桌面端兼容说明文档
- `private_chat/` — 私聊模块同步安全加固与兼容修复

---

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
- **多工具调用兼容** — AI 在单次推理中调用多个工具或发生多轮工具调用时，按实际执行顺序将 AI 中间文本与工具调用记录（调用名称+参数+返回值）交错保存到对话历史；兼容 ToolCall 对象和 dict 两种格式，支持无最终文本输出时的兜底保存。工具调用参数和结果的保存长度可通过 `tool_call_max_args_length`（默认5000字符）和 `tool_call_max_result_length`（默认10000字符）配置，支持完全省略（0）、自定义截断（正数）、或完全不限制（-1）
- **通用第三方提示词保留** — 重构第三方插件提示词保留机制，从关键词启发式过滤改为差分法（比较插件自身数据 vs. 当前请求实际内容），自动识别并保留所有其他插件注入到 system_prompt / contexts / prompt 的内容。新增平台 LTM 模式过滤、多级回退策略（空消息/纯图/纯@场景均有保护），以清晰边界标记（`[第三方插件片段]` / `[第三方插件注入上下文]`）确保 AI 不会混淆不同插件的信息，同时保持原始 system_prompt 顺序（prefix → persona → suffix）

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