# 配置项完整参考

> 本文档列出了群聊增强插件的**所有配置项**，包含类型、默认值和详细说明。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程](MESSAGE_WORKFLOW.md) | [项目结构](PROJECT_STRUCTURE.md) | [桌面端兼容](DESKTOP_COMPATIBILITY.md)

---

## 目录

- [基础设置](#基础设置)
- [Web 管理面板](#web-管理面板)
- [桌面端兼容](#桌面端兼容)
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
| `enable_debug_log` | bool | `false` | 开启后输出详细调试日志，用于排查问题；当 `on_llm_request` 的 system_prompt 重写进入兼容增强或保守回退路径时，也会通过该日志帮助判断当前是精确命中、轻量兼容识别，还是低置信度保守模式 |

---

## Web 管理面板

> v1.2.1 新增，提供可视化管理界面。

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_web_panel` | bool | `false` | 启用 Web 管理面板 HTTP 服务 |
| `web_panel_port` | int | `1451` | Web 面板端口号 |
| `web_panel_host` | string | `"0.0.0.0"` | 监听地址。`0.0.0.0` = 所有 IPv4 接口（自动启用双栈同时监听 IPv6），`::` = 所有 IPv6 接口，`127.0.0.1` / `::1` = 仅本机访问。支持单个 IPv4/IPv6 地址（如 `192.168.1.5` 或 `2001:db8::1`），不支持 CIDR 网段 |

### 安全配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_reset_password` | bool | `false` | 设为 `true` 后重启，密码将重置为随机值并显示在日志中；重置后的新密码会直接使用 Argon2id 哈希保存 |
| `web_panel_trust_proxy` | bool | `false` | 信任反向代理的 `X-Real-IP` / `X-Forwarded-For` 头，并在可信代理来源下使用 `X-Forwarded-Proto` / `X-Forwarded-Host` 判断安全上下文与同源写请求。**这是安全边界配置，仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** 当反代与面板部署在同一台机器、后端看到的连接来源为 `127.0.0.1 / ::1` 时，即使关闭此开关，也会自动读取合法代理头获取真实 IP；若反代不在本机，才需要显式开启。公网直连时不要开启，否则客户端可伪造代理头 |
| `web_panel_ip_bind_check` | bool | `true` | 登录 IP 绑定校验。开启后登录时会把客户端 IP 绑定到会话令牌中，后续普通请求、面板访问和心跳都会校验当前 IP 是否与登录时一致。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_visible_interval_seconds` | int | `300` | 前台页面可见时的心跳检测间隔（秒）。用于尽快发现令牌过期、密码修改、服务端重启等状态变化。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_hidden_interval_seconds` | int | `1200` | 后台标签页的心跳检测间隔（秒），默认 20 分钟。用于降低后台页面资源占用和误触发高频请求。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_retry_base_seconds` | int | `15` | 心跳失败后进入缓冲重试期时的基准间隔（秒）。前端会基于该值做退避重试，而不是单次失败就立即判定断联。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |
| `web_panel_heartbeat_retry_max_seconds` | int | `120` | 心跳失败重试的最大间隔（秒）。连续失败时会逐步拉长重试间隔，但不会超过此上限。**仅允许在 AstrBot 传统配置界面修改，Web 端只读显示。** |

> **Web 面板边界说明**：页面、静态资源和 API 统一经过后端中间件安全检查，不依赖前端隐藏按钮或前端跳转作为安全边界。文件管理只允许处理插件数据目录中的普通数据文件；`auth.json`、`jwt_secret.json`、`sessions.json`、访问日志、封禁数据及其同名备份文件等核心安全文件不会在文件列表中暴露，读取、修改和删除都会被后端直接拒绝。会话管理里的聊天记录查看/编辑针对的是插件自定义 `chat_history/...` 历史文件，不是 AstrBot 官方 ConversationManager 历史。除登录、认证状态探测、Logo 和 `robots.txt` 等公开入口外，所有 `/api/*` 非公开接口都必须在后端通过 IP 黑白名单/封禁检查、JWT + 服务端会话校验，以及防爬虫/已登录速率限制后才会返回数据或执行写入。令牌缺失、无效或过期时，受保护 API 会直接返回 401，不进入业务处理；浏览器地址栏直接访问 API 时会在完成安全检查后跳转到统一无权限错误页，不返回业务数据。
>
> **浏览器安全头说明**：页面响应会附加统一安全头，包括禁止 MIME 嗅探、禁止被 iframe 嵌入、禁止跨源资源读取、关闭敏感缓存、限制权限策略和 `no-referrer` 等。登录页、面板页、错误页使用基于随机 nonce 的 CSP 限制脚本执行；nonce 每次响应即时生成，不长期保存。相关机制均为标准 HTTP/浏览器安全能力，现代 Chromium、Firefox、WebKit 内核均可识别；旧浏览器不支持的头部会被忽略，不影响后端认证和访问控制。
>
> **配置文件下载说明**：在配置流程图或核心设置页面右下角的配置文件浮窗中，提供了当前配置文件的下载功能。下载为**只读**操作，不暴露服务器绝对路径（仅返回文件名与内容），须通过完整认证链路（当前 IP 可访问 + JWT 真实有效 + 服务端会话未过期 + 防爬虫/已登录速率限制）。每次下载均写入 Web 面板访问日志（附注标明成功/失败原因）。配置文件浮窗上方还有一组**流程图缩放控件**（+ 放大 / ⊡ 适应屏幕 / − 缩小），仅在「配置流程图」页面显示。故障排查：[常见问题](ARCHITECTURE.md#q-点击下载按钮后提示下载失败怎么办)

### IP 访问控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_ip_mode` | string | `"disabled"` | IP 访问控制模式（同时兼容 IPv4 和 IPv6）：`disabled`（不启用）、`whitelist`（白名单，仅允许列表内IP）、`blacklist`（黑名单，拒绝列表内IP） |
| `web_panel_ip_list` | list | `[]` | 白名单/黑名单 IP 地址列表。支持 IPv4 和 IPv6 地址，仅做精确地址匹配（不支持 CIDR 网段/子网/IP段） |
| `web_panel_protected_ips` | list | `[]` | 受保护IP列表（永不封禁）。支持 IPv4 和 IPv6，最高优先级不受任何机制影响。配置文件专属，Web端只读 |

`web_panel_ip_mode` 若被手动写成非法值，运行时会按失败关闭处理：除受保护 IP 外，其余来源都会被拒绝，避免异常配置意外放开访问控制。

IP 名单在运行时只装载合法的单个 IPv4/IPv6 地址；同一 IPv6 地址的压缩、半压缩或完整展开写法会先规范化再匹配，重复项会去重。CIDR 网段、域名和非法条目不会参与匹配，并会在日志中输出配置警告。

IP 相关机制优先级如下：

- **受保护 IP**：最高优先级，永远放行，不会被黑/白名单、封禁表、防爬虫、已登录速率限制或登录爆破锁定影响；只能在 AstrBot 传统配置界面修改。
- **白名单模式**：只有名单内 IP 能访问。白名单 IP 不写入封禁表，也不受防爬虫和已登录速率限制影响，但输错密码仍会走登录爆破的阶梯锁定；如需完全免锁定，应加入受保护 IP。
- **黑名单模式**：名单内 IP 直接拒绝访问，优先于封禁表，不向外暴露具体内部数据。
- **封禁表**：由手动封禁、防爬虫自动封禁、登录爆破封禁共用，同一 IP 只保留一条记录；重复手动封禁会更新该记录，不会产生多条冲突记录。受保护 IP 和当前白名单 IP 若因历史数据或手工篡改出现在封禁表中，会在启动、配置更新或读取封禁列表时被自动清理。

### 防爬虫与已登录请求保护

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_anti_spider` | bool | `false` | 启用防爬虫检测（UA 匹配 + 频率限制 + 扫描路径识别），对 IPv4 和 IPv6 地址均生效 |
| `web_panel_anti_spider_rate_limit` | int | `60` | **匿名/公开结果请求**（无令牌、令牌过期或无效，以及 `/error`、`/robots.txt` 的非阻断记账）每分钟请求数阈值，超过则可能触发临时封禁 |
| `web_panel_anti_spider_ban_duration` | int | `300` | 自动封禁持续时间（秒） |
| `web_panel_authenticated_rate_limit` | int | `240` | **已登录请求**（持有有效 JWT 令牌，可正常使用面板）的独立速率阈值（次/分钟）。用户未配置时回退为 `max(240, anti_spider_rate_limit × 4)`。数据图表、会话管理、心跳状态展示等自动刷新请求会计入此滑动窗口，防止伪造自动刷新请求头绕过限速；前端会通过防重入、后台标签页暂停展示类刷新等方式降低误触发概率。只有 `/api/auth/heartbeat` 专用认证心跳不计入已登录速率窗口，但仍必须通过 IP 和令牌校验。 |

`robots.txt` 始终返回固定的 `Disallow: /`，不参与 IP 封禁、黑白名单、UA 指纹拦截或拦截跳转，用于让正常爬虫和已被拦截的来源都能读取禁止抓取规则。它仍会计入匿名频率窗口，命中阈值时只记录并封禁 IP，不替换协议响应。统一错误页不做 UA 指纹重复拦截，但固定使用匿名频率限制，并带有禁止索引响应头，避免拦截页被搜索引擎收录。错误页的核心状态文案由后端按固定错误码直接渲染，前端脚本只做辅助展示和解封轮询；`reason` 只信任服务端一次性跳转令牌中的值，不读取 URL 参数。

自动刷新请求中的 `X-GCP-Auto-Refresh` 仅用于前端区分请求来源，不是后端安全豁免依据。直接调用后端接口、篡改前端或伪造该请求头，都无法跳过 IP 可访问性、令牌有效性和对应速率检测。

公开页面和内部 API 都有后端输入校验：登录密码、改密字段、IP 名单、封禁备注、分页参数、文件路径和文件内容都会在服务端检查类型、长度和可接受范围；历史访问日志和封禁备注从磁盘恢复或返回前也会做文本清洗。前端校验只用于交互提示，不能作为安全边界。

### 暴力破解防护

> ⚠️ **安全底线配置**：以下配置项仅可在 AstrBot 传统配置界面修改，Web 面板中为只读显示。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_brute_force_window` | int | `3600` | 失败计数重置窗口（秒）。指定时间内无新失败记录时自动清零该 IP 失败计数，防止偶尔输错的用户长期累积。设为 0=永不过期。**仅限传统配置界面修改。** |
| `web_panel_brute_force_rate_window` | int | `10` | 频率检测窗口（秒）。在此窗口内失败达到 `rate_count` 次，直接封禁该 IP。设为 0 关闭频率检测。**仅限传统配置界面修改。** |
| `web_panel_brute_force_rate_count` | int | `3` | 频率检测触发次数。在 `rate_window` 秒内失败达到此值触发 IP 封禁。建议 2-5。**仅限传统配置界面修改。** |
| `web_panel_brute_force_tiers` | text | `"[[5,30],[10,60],[15,300],[20,600],[30,1800],[50,3600]]"` | JSON 格式阶梯锁定规则 `[[次数, 锁定秒数], ...]`，自动按次数升序排列。**仅限传统配置界面修改。** |
| `web_panel_brute_force_ban_duration` | int | `0` | 频率异常或达最大阶梯后继续尝试的封禁时长（秒）。0=永久封禁（写入 bans.json）。**仅限传统配置界面修改。** |

**防护逻辑流程：**
1. 用户提交密码 → 检查 IP 是否在锁定期 → 是则返回 429（需等待解锁）
2. 密码错误 → 记录失败 → **频率检测**：N 秒内失败 M 次？→ 直接封禁 IP
3. **窗口衰减**：距上次失败超过 `brute_force_window` 秒？→ 重置计数
4. **阶梯锁定**：按当前失败次数查找对应阶梯 → 设置 `锁定截止时间 = now + 锁定时长`
5. **永久封禁**：已达最大阶梯且解锁后仍继续失败？→ `ban_ip()` 写入 bans.json
6. 密码正确 → 重置该 IP 的失败计数和锁定状态

**⚠️ 极端情况说明 — 为什么要关注 `web_panel_brute_force_window`：**

此配置项存在一个安全性与易用性的权衡，请根据你的使用场景做出选择：

| 设置 | 效果 | 优点 | 风险 |
|------|------|------|------|
| `3600`（默认，推荐） | 1 小时无失败后自动清零计数 | 普通用户偶尔输错密码不会长期累积；后台定期清理僵尸追踪器释放内存 | 理论上慢速攻击者可利用衰减窗口（例如每 61 分钟试 4 次，永不触发 5 次锁定）。**但实际威胁极低**：这种攻击速度每天仅能尝试约 96 个密码，对强密码几乎无解 |
| `0`（关闭衰减） | 失败计数永不自动清零，只能靠重启插件或登录成功来重置 | 彻底杜绝慢速攻击者利用衰减窗口重置计数 | **普通用户会永久累积失败次数**。例如用户某天手误输错 4 次，3 个月后又输错 1 次 → 直接触发第 5 次锁定；再累积下去最终会触发永久封禁。除非重启插件，否则该 IP 的失败记录永远不会消失 |
| 较小值（如 `600`） | 10 分钟无失败即清零 | 对普通用户最友好，IP 被封禁的风险极低 | 慢速攻击者更容易利用衰减窗口，防护效果减弱 |

**为什么不把 `window=0` 时的永久累积当作 Bug 来修？**

这是有意保留的设计选择，而不是缺陷。原因：如果系统在 `window=0` 时仍自动清理，慢速暴力破解攻击者可以故意拉长尝试间隔来绕过阶梯锁定。对于需要最高安全级别的场景（例如暴露在公网的面板），`window=0` 保证攻击者的每一次尝试都会被永久记录。但对于大多数内网部署场景，默认值 `3600` 已足够。

**建议**：
- **内网/本地部署**：保持默认 `3600`，安全性和易用性平衡最好
- **公网暴露**：可适当调大（如 `86400` = 24 小时），既保持长期追踪又避免普通用户永久累积
- **最高安全要求**：设为 `0`，但需要接受普通用户也可能被误伤的风险；可搭配 `web_panel_protected_ips` 将管理员 IP 加入保护名单

### 日志管理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `web_panel_log_auto_clean` | bool | `false` | 自动清理过期访问日志 |
| `web_panel_log_retention_days` | int | `7` | 日志保留天数 |
| `web_panel_log_clean_interval_hours` | int | `24` | 清理检查间隔（小时） |

访问日志固定保存在插件数据目录的 `web_data/access_log.jsonl`，并按大小轮转为 `access_log.1.jsonl`、`access_log.2.jsonl`。自动清理只会处理这些固定命名的日志文件，不会通配删除其他文件；日志中的 IP、路径、方法和附注在写入与返回前都会做服务端文本清洗。请求频率窗口、暴力破解追踪器和过期 Web 会话也会由后台维护任务定期清理，避免长期运行时内存或会话记录持续堆积。

---

## 桌面端兼容

> v1.2.2-hotfix.1+ 新增。AstrBot 桌面端（Desktop Edition）使用 Tauri 托管后端进程，重启机制与标准版不同。详细说明见 [桌面端兼容文档](DESKTOP_COMPATIBILITY.md)。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `desktop_mode` | string | `"auto"` | 桌面端模式。`auto` = 自动检测（推荐），`force_desktop` = 强制桌面端模式，`force_standard` = 强制标准版模式 |
| `desktop_detected_env` | string | `""` | 🔒 **只读**。自动检测结果，由插件写入。格式示例：`env:ASTRBOT_DESKTOP_CLIENT=1`、`path:ASTRBOT_ROOT=~/.astrbot`、`none` |

**自动检测依据（按优先级）：**

1. 环境变量 `ASTRBOT_DESKTOP_CLIENT=1`（桌面端打包模式设置，最可靠）
2. `ASTRBOT_ROOT` 指向 `~/.astrbot`（桌面端默认数据目录）
3. `ASTRBOT_WEBUI_DIR` 包含 `resources` 路径（桌面端打包资源特征）
4. `PYTHONNOUSERSITE=1` + `ASTRBOT_ROOT` 同时存在（桌面端环境隔离特征）

**桌面端模式下的行为差异：**

- `gcp_reset` / `gcp_reset_here` / `gcp_clear_image_cache` 指令重启后，会附加桌面端提示
- Web 面板重启操作响应中包含 `is_desktop` 标识
- 日志中输出额外的桌面端进程管理警告

---

## 概率与决策系统

### 基础概率

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_probability` | float | `0.02` | 基础回复概率。每条消息有 2% 的概率通过第一层筛选。值越高，AI越活跃 |
| `after_reply_probability` | float | `0.8` | 传统模式下的回复后提升概率。仅在关闭 `enable_attention_mechanism` 时生效；AI刚成功回复后，会对整个群聊会话临时使用该概率，促进连续对话。该提升不区分用户，新的成功回复会刷新持续时间。若开启注意力机制，则这一项不会参与当前会话计算，而是由注意力机制按用户接管 |
| `probability_duration` | int | `120` | 传统模式下回复后提升的持续时间（秒）。这是按整个群聊会话生效的时间窗口，不是按单个用户计算；若配置异常，系统会自动矫正为安全值 |

### 概率硬限制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_probability_hard_limit` | bool | `false` | 强制将最终概率限制在 [min, max] 范围内。它是最终后置限制层，对传统模式、注意力模式以及其他概率增减结果都会生效 |
| `probability_min_limit` | float | `0.05` | 概率下限，确保即使多重衰减也不会低于此值 |
| `probability_max_limit` | float | `0.8` | 概率上限，防止叠加后概率过高 |

### 决策AI配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `decision_ai_provider_id` | string | `""` | 执行"读空气"判断的AI提供商ID。留空使用 AstrBot 默认提供商。同时也是主动对话判断AI和频率判断AI的提供商 |
| `decision_ai_fallback_provider_ids` | list | `[]` | 🔁 **备用AI提供商列表（三处共用）**。读空气AI(#1)、主动对话预判断AI(#3)、频率判断AI(#5)三处共享此列表。调用失败（超时/报错/返回空响应）时按列表顺序自动切换到下一个备用提供商重试，每个提供商单独计时（超时见 `decision_ai_timeout` 等各自配置）。留空=不启用备用机制 |
| `decision_ai_include_persona` | bool | `true` | 是否为读空气AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性判断任务执行，不额外注入人格 |
| `decision_ai_persona_name` | string | `""` | 仅在 `decision_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让读空气AI按该人格判断。若找不到则自动回退到当前会话人格 |
| `decision_ai_prompt_mode` | string | `”append”` | 决策提示词模式。`append`：在内置提示词后追加自定义内容；`override`：完全用自定义内容替换内置提示词。Smart 批次提示增强开启后，决策阶段会额外注入批次感知提示，告知读空气AI当前消息为判断主对象 |
| `decision_ai_extra_prompt` | string | `””` | 自定义决策提示词。可用于微调 AI 的判断标准。开启额外推理时，最终仍必须收敛到 yes/no。Smart 批次提示增强的决策提示独立注入，不会混淆此处的自定义内容 |
| `decision_ai_timeout` | int | `30` | 决策AI调用超时（秒）。超时后视为"不回复"。若遇到 `upstream_empty_output` / `empty output` 一类上游空响应，日志会优先标记为“上游模型返回空输出”，避免与普通限流混淆 |
| `enable_decision_ai_reasoning` | bool | `false` | 开启读空气AI额外推理模式。开启后AI必须先输出推理块，再在最后一行单独输出 yes/no；最终结论不得附带解释、前后缀或标点。推理块自动剥离不影响判定。解析失败默认不回复 |
| `decision_ai_reasoning_log` | bool | `false` | 开启后将读空气AI的推理相关内容输出到 AstrBot 日志，方便调试 |
| `decision_ai_reasoning_log_mode` | string | `"processed"` | 读空气AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |
| `judgment_reasoning_start_marker` | string | `"[[GCP_REASONING_START]]"` | 三个判断型AI（读空气、主动对话判断、频率判断）共用的推理起始符。此项在三处 Web 入口中会同步显示与同步生效 |
| `judgment_reasoning_end_marker` | string | `"[[GCP_REASONING_END]]"` | 三个判断型AI共用的推理截止符。此项在三处 Web 入口中会同步显示与同步生效 |

### 超时与并发

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `reply_timeout_warning_threshold` | int | `120` | 回复超过此时间（秒）发出警告日志 |
| `reply_generation_timeout_warning` | int | `60` | 回复生成超过此时间（秒）发出警告 |
| `concurrent_wait_max_loops` | int | `10` | 通用并发等待的最大检测轮数。总最大等待时间 = `concurrent_wait_max_loops × concurrent_wait_interval`。不仅影响普通消息并发等待，也会影响主动对话/冷群转正占用会话时普通链路在读空气前、回复前和缓存保存前的等待检测，以及冷群缓存自动转正判断会话是否仍忙碌时的等待逻辑。等待超时遇到主动/冷转正 owner 时会保守回退为缓存，不强行生成；若当前普通链路已有等待窗口令牌，同窗口缓冲消息也会同步转为普通缓存并保留原始时间戳 |
| `concurrent_wait_interval` | float | `1.0` | 通用并发等待的每轮检测间隔（秒）。例如默认 `10 × 1.0 = 最多等待 10 秒`。即使 `concurrent_mode=smart`，主动对话占用等待、普通链路的 owner 等待和冷群缓存自动转正等待仍复用这套通用轮询参数，而不是切换成 Smart 专属等待逻辑 |
| `concurrent_mode` | string | `"legacy"` | 并发模式。`legacy` = 传统逐条等待处理，是普通对话链路最基础、最兜底的并发保护方式；`smart` = 在普通对话主线上优先尝试按真实到达顺序合并批次，让决策AI/回复AI一起感知当前消息后紧接着到达的追加消息。Smart follower 使用专用批次快照保存完整消息，不进入普通缓存池或 GWW 窗口缓存池；上下文中看到的“追加消息”只是复用同一种展示格式，GWW 开关关闭时仍可展示 Smart 批次。Smart 模式下若同时开启了 GWW，同一 Smart 批次涉及多个等待窗口时会为这些窗口打运行时融合标记，后续上下文读取、窗口回落、Phase-2 保存与清理按同一融合组统一处理；未参与融合的窗口仍按 `sender_id + gww_token` 原逻辑精确隔离。Smart 吸收的 follower 会保留原始 @ 解析、@全体说明、戳一戳事件、发送者与环境元数据；纯戳一戳这类平台侧空正文组件会使用 `[ComponentType.Poke]` 占位保存。即使选择了 `smart`，传统并发等待/兜底保护也不会消失，主动对话/冷群转正 owner 占用检测、等待超时回退缓存、以及若干异常路径仍然复用传统轮询逻辑 |
| `enable_smart_batch_reply_hint` | bool | `true` | 仅在 `concurrent_mode=smart` 时生效。开启后，决策阶段和回复阶段分别动态提示 AI：决策阶段提示当前消息是判断主对象（追加消息仅作背景参考）；回复阶段提示当前触发对象仍是主要回复对象，但可以像真人一样自然顺带回应批次中的其他消息，不值得回的也可忽略。这些提示只存在于运行时，保存历史前会自动过滤 |
| `smart_concurrent_merge_wait` | float | `30.0` | Smart 模式下批次待合并超时时间（秒）。消息在待合并池中超过此时间未被吸收，将被自动清理并转为独立处理 |
| `smart_concurrent_max_batch_size` | int | `20` | Smart 模式单批次最多吸收的消息数。达到此数后停止吸收，剩余消息留在待合并池由下一批次处理。与合并超时时间同时生效，两者任一先触发即停止合并。建议范围 1-50 |
| `smart_concurrent_claim_delay` | float | `0.3` | Smart 模式快照前收拢延迟（秒）。anchor 在调用 claim_batch（一次性快照）前等待的极短时间，用于给几乎同时到达的消息挂载 payload 的机会。0=不等待，建议 0.1-0.5。不是收集窗口（不会持续收消息） |

---

## 消息格式与上下文

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `include_timestamp` | bool | `true` | 为每条消息添加时间戳（在冒号 `:` 之前的系统元数据区），格式：`[2026-03-13 周四 14:30:00]`。帮助AI理解时间关系 |
| `include_sender_info` | bool | `true` | **仅控制「冒号前系统元数据区」**：为每条消息在冒号 `:` 之前添加当前消息发送者的 `Name(ID:12345)` 信息，同时控制 `[系统提示]` 触发方式说明的注入。<br><br>**⚠️ 不受此开关控制、始终输出的发送者信息**：<br>① 引用消息内部的被引用者身份（`[引用 >>> Name(ID:xxx): ...]`）<br>② @消息标签中的被@者解析（`[At:ID\|昵称]`）<br>③ 戳一戳事件文本（`[戳一戳事件]…Name(ID:xxx)…`）<br>④ 戳一戳提示文本（`[戳一戳提示]…Name(ID:xxx)…`）<br><br>以上四类发送者信息在消息内容区硬编码，关闭本开关无法隐藏。 |
| `include_environment_info` | bool | `false` | **环境标注**：开启后在发送者元数据区附加当前聊天环境的名称和ID（格式：`张三(ID:123) [环境: 技术群(ID:456)]: 消息内容`）。需先开启 `include_sender_info`。<br><br>⚠️ **平台限制**：群名解析仅保证 QQ(aiocqhttp) 平台可用；其他平台群名将显示 `[未知群名]`。这是对发送者消息元数据的单次扩展注入，不是独立标签。 |

**环境标注效果示例**：
```
[2026-06-04 周四 14:30:00] 张三(ID:12345) [环境: 技术交流群(ID:987)]: 你好啊
```
| `max_context_messages` | int | `-1` | 传递给AI的最大历史消息条数。`-1` = 配置层不额外限制，但读取/传递给 AI 时仍受系统保护硬上限 500 条约束 |
| `single_at_message_reply_link_max_messages` | int | `8` | 单独的、不包含任何信息的 @ 消息可继续参考最近上下文的最大消息数窗口。系统会与时间窗口同时检查，两者都满足才保留这层关联。`0` = 关闭这一维限制，仅保留时间窗口。 |
| `single_at_message_reply_link_max_seconds` | int | `180` | 单独的、不包含任何信息的 @ 消息可继续参考最近上下文的最长时间窗口（秒）。系统会与消息数窗口同时检查，两者都满足才保留这层关联。`0` = 关闭这一维限制，仅保留消息数窗口。 |

**单独的、不包含任何信息的 @ 消息上下文强化（默认启用，窗口阈值可配置）**

当用户发送的是“只 @ AI、没有文字、图片、关键词等其他有效内容”的消息时：
- 系统会先完成前置过滤和读空气筛选
- 这里的“只 @ AI”是严格语义：允许重复多个 `@AI`，但不能混入 `@别人` 或 `@全体成员`
- 只有在最终决定回复后，才会在回复阶段动态追加一段中性的上下文提醒
- 会参考最近缓存消息摘要，以及“最近一次明确回复对象”是否与当前发送这条消息的人相同
- same-user 提醒与近期摘要都会同时受“时间窗口 + 消息数窗口”双限制约束，不是二选一
- 即使命中同一人，也只会提醒 AI 优先参考最近上下文，不会强制要求它续上文
- 如果不是同一个人，或任一窗口超限，则自动降级为更中性的自由判断提醒

另有一条更宽松的内部语义专用于”候选冷却/重新叫出 AI”判断：只要空消息里包含了 `@AI`，即使同时还 `@别人` 或 `@全体成员`，也会被视为”把 AI 叫了出来”，用于决定是否重新给予最低增长与解除候选冷却。

---

## 身份提示

向 AI 注入其当前环境中的账号信息（名称、ID）和可选的聊天环境信息（群名、群ID），帮助 AI 正确认知自己在当前平台上的身份标识。提示为一次性注入到 system_prompt，不会保存到对话历史。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_identity_prompt` | bool | `false` | **总开关**。开启后在系统提示词中注入 AI 当前的身份信息（名称和 ID）。提示使用 `[系统信息-自身身份]` 标记，仅注入一次、不保存到历史 |
| `identity_prompt_ai_targets` | string | `”all_four”` | **目标 AI 选择**。可选值：`decision_only`（仅读空气决策AI）、`reply_only`（仅回复生成AI）、`proactive_judge_only`（仅主动对话预判断AI）、`proactive_gen_only`（仅主动对话生成AI）、`decision_and_reply`（读空气+回复）、`decision_and_proactive`（读空气+主动对话）、`reply_and_proactive`（回复+主动对话）、`all_four`（全部四种AI，推荐） |
| `identity_prompt_include_group_info` | bool | `false` | **包含当前环境信息**。开启后额外注入当前环境（群聊等）的名称和ID。使用中性词汇「当前环境」描述，AI 会结合人格设定自行理解。<br><br>⚠️ **平台限制**：群名解析仅保证 QQ(aiocqhttp) 平台可用；Slack/Mattermost 次之；其他平台群名将被占位符 `[未知群名]` 替代，不影响功能。 |
| `identity_prompt_save_to_history` | bool | `false` | **保存回复时附加身份信息**。开启后，在保存 AI 的回复到对话历史时，会在回复内容最前面附加当前账号的名称和 ID 标识（如 `[账号: MyBot \| ID: 123456789]`）。这会让 AI 在回看历史时知道这条消息是哪个账号发出的。<br><br>需先开启「启用AI身份提示」总开关。适用于：普通回复、主动对话、回复后戳一戳、反戳一戳等所有 AI 消息的保存场景。 |
| `identity_prompt_save_group_mode` | string | `"identity_only"` | **保存附加信息的模式**。可选值：`identity_only`（仅附加账号名称和ID）、`with_group`（同时附加当前环境的名称和ID）。<br><br>⚠️ **平台限制**：环境信息（群名/群ID）的解析仅保证 QQ(aiocqhttp) 平台可用，其他平台群名将被占位符 `[未知群名]` 替代。需先开启「保存回复时附加身份信息」。 |
| `enable_group_role_display` | bool | `false` | **群身份标签显示**。开启后，在以下位置添加消息发送者或AI自身的群身份标签（群主/管理员/群成员）：<br><br>① **发送者元数据区**（格式：`张三(ID:12345)[群主]`）— 需同时开启 `include_sender_info`<br>② **AI身份提示块**（追加一行「当前环境中你的身份: 群主」）— 需同时开启 `enable_identity_prompt`<br>③ **@消息解析标签**（格式：`[At:ID\|昵称\|群主]`）— 与@解析并行生效<br>④ **保存回复前缀**（追加 `\| 身份: 群主`）— 需同时开启 `enable_identity_prompt` 和 `identity_prompt_save_to_history`<br><br>⚠️ **平台限制**：仅支持QQ平台(aiocqhttp)通过 `get_group_member_info` API 获取角色信息。其他平台或 API 调用失败时自动跳过，不影响已有功能。角色信息自动缓存5分钟以减少API调用。 |

**提示词注入格式示例**（开启 `enable_group_role_display` 后）：
```
[系统信息-自身身份]
当前环境中你使用的账号名称: MyBot
当前环境中你使用的账号ID: 123456789
当前环境中你的身份: 管理员
—— 以上为平台账号层面的标识信息。如果你当前拥有人格设定（persona），请以人格中定义的身份和名字为准；如果你没有人格设定，则将上述信息作为你在当前环境中的身份参考即可。

[系统信息-当前环境]（仅当开启「包含当前环境信息」时）
当前聊天环境的名称: 技术交流群
当前聊天环境的ID: 987654321
—— 以上为你当前所处环境的基本参考信息。如果你当前拥有人格设定（persona），请结合人格来理解此环境；如果你没有人格设定，则将上述信息作为当前对话场景的参考即可。
```

> **注意**：此提示词使用 `[系统信息-自身身份]` 和 `[系统信息-当前环境]` 标记，会被消息清理器在保存历史时自动过滤，不会污染对话历史。

**保存历史时附加身份信息的效果示例**：

开启「保存回复时附加身份信息」后，AI 回复在保存到对话历史时会变成：

```
[账号: MyBot | ID: 123456789]
大家好，今天天气真不错！

[账号: MyBot | ID: 123456789 | 环境: 技术交流群 (ID: 987654321)]
（开启「with_group」模式时的效果）

[账号: MyBot | ID: 123456789 | 身份: 管理员]
（开启「enable_group_role_display」后 identity_only 模式的效果）

[账号: MyBot | ID: 123456789 | 身份: 管理员 | 环境: 技术交流群 (ID: 987654321)]
（同时开启 role_display + with_group 模式的效果）
```

这样当 AI 回看历史时，能清楚知道每条回复是哪个账号发出的，以及（可选）是在哪个环境中发出的。

---

## 消息缓存

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `custom_storage_max_messages` | int | `500` | 自定义消息存储的最大条数。`0` = 禁用，`-1` = 不限制（系统硬上限10000条）。用于保存完整的群聊上下文 |
| `tool_call_max_args_length` | int | `5000` | 🔧 **工具调用参数最大保存长度（单次）**。保存工具调用记录到对话历史时，针对单个工具调用的参数部分的最大字符数限制。`0` = 完全省略参数（使用占位符 `(参数已省略)`）；正数 = 截断到该字符数并添加 `...`；`-1` = 完全不限制（真正无上限）。作用于每个独立的工具调用，非所有工具调用的总和。默认5000字符能覆盖大多数场景。某些工具会在参数中包含完整回复内容，提升此限制可避免重要信息被截断。设置为-1时无系统硬上限，极端情况下可能占用大量内存，请根据实际工具使用场景谨慎评估 |
| `tool_call_max_result_length` | int | `10000` | 🔧 **工具调用结果最大保存长度（单次）**。保存工具调用记录到对话历史时，针对单个工具调用的返回结果部分的最大字符数限制。`0` = 完全省略结果（使用占位符 `(结果已省略)`）；正数 = 截断到该字符数并添加 `...`；`-1` = 完全不限制（真正无上限）。作用于每个独立的工具调用，非所有工具调用的总和。默认10000字符（工具结果通常比参数更长）。工具返回结果包含AI后续回复所需信息，过度截断会影响对话质量。设置为-1时无系统硬上限，极端情况下（如工具返回巨大文件内容、完整数据库导出等）可能占用大量内存甚至引发内存不足，请根据实际工具返回内容谨慎评估 |
| `pending_cache_max_count` | int | `10` | 待处理消息池的最大条数。未通过概率筛选的消息暂存于此，下次回复时作为上下文合并 |
| `pending_cache_ttl_seconds` | int | `1800` | 待处理消息的过期时间（秒），超过后在下一条消息到来时自动清理 |
| `enable_idle_cache_flush` | bool | `false` | **冷群缓存自动转正**。开启后，当群聊静默超过 `idle_cache_flush_delay_seconds` 秒没有任何新消息时，自动将待处理池中的缓存消息转正写入自定义存储和 `platform_message_history` 表（可在 Web Chat UI 中查看），避免因过期被丢弃导致的上下文断裂。执行前会等待普通回复、主动对话、Smart pending 和已有会话 owner 释放；成功占用后普通新消息会等待，保存失败或占用冲突时只跳过本轮，不清缓存。冷群转正会同时处理普通缓存和遗留的窗口缓冲消息，并且缓存转正写入 `platform_message_history` 时会用稳定 checkpoint 跳过同一缓存消息的重复写入。每收到一条新消息都会重置计时器（滑动窗口）。**建议将 `idle_cache_flush_delay_seconds` 设置为小于等于 `pending_cache_ttl_seconds` 的值**，否则缓存会在触发转正前就因过期而被清除。 |
| `idle_cache_flush_delay_seconds` | int | `600` | 冷群转正触发延迟（秒）。群聊静默多久后触发一次自动转正。与 `pending_cache_ttl_seconds` 相互独立：此项控制转正时机，过期时间控制缓存丢弃时机。范围 60-7200 秒。需开启 `enable_idle_cache_flush` 后生效。实际保存还会受通用并发等待参数影响，若会话持续忙碌则保留缓存等待下一轮。 |

---

## 图片处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_image_processing` | bool | `false` | 启用图片处理功能。关闭时原始图片会被直接剥离；过滤后严格等于空字符串 `""` 的消息会被丢弃，纯空白字符串仍按有内容保留 |
| `image_to_text_scope` | string | `"mention_only"` | 图片处理范围：`all`（所有消息中的图片）、`mention_only`（@或关键词触发时）、`at_only`（仅@消息）、`keyword_only`（仅关键词触发时） |
| `image_to_text_provider_id` | string | `""` | 图片转文字的AI提供商ID。填写后走图片转文字；留空时走多模态直传，内联 `[图片: /path/to/image.png]` 标记（与视频/语音/文件格式一致）并通过 `image_urls` 传递原始图片数据给多模态 AI；单张图片路径提取失败时对应位置降级为 `[图片（识别失败）]` |
| `image_to_text_fallback_provider_ids` | list | `[]` | 🔁 **图片转文字备用提供商列表**。当主提供商 `image_to_text_provider_id` 非空且调用失败（超时/报错/返回空响应）时，按列表顺序自动切换到下一个备用提供商重试，每个提供商单独计时。注意：若 `image_to_text_provider_id` 为空则走多模态直传，即使配置了备用列表也不会激活 |
| `image_to_text_prompt` | string | `"请详细描述这张图片的内容"` | 发送给图片AI的提示语 |
| `image_to_text_timeout` | int | `60` | 图片处理API调用超时（秒）。图片转文字仍走独立的 `provider.text_chat()` 直连链路，不经过回复 Hook |
| `max_images_per_message` | int | `10` | 单条消息最大图片转文字数量（1-50）。仅限制调用图片转文字AI的图片数，不限制多模态直传图片数 |
| `enable_image_description_cache` | bool | `false` | 缓存图片描述结果，相同图片不重复调用API，节省费用 |
| `image_description_cache_max_entries` | int | `500` | 图片描述缓存的最大条目数。当前主缓存文件位于 `image_cache/descriptions.jsonl`；若检测到旧版残留路径 `image_description_cache.json`，Web 面板清理逻辑会兼容处理，但该旧路径不再是当前主实现 |
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

### 关键词匹配规则

**触发关键词和黑名单关键词使用相同的匹配引擎，规则如下：**

| 特性 | 说明 |
|------|------|
| **大小写** | **敏感**。关键词 `"Hello"` 不会匹配 `"hello"`，请按实际消息中的大小写填写 |
| **匹配方式** | **子串匹配**（`in` 运算符）。关键词 `"at"` 会匹配 `"attention"`、`"battle"` 等包含该子串的任意词。如需精确匹配，请使用更独特的关键词 |
| **匹配范围** | **消息链中的用户消息文本**。只匹配消息链中用户发送的消息内容（不含时间戳、发送者信息、`[系统提示]` 等后续注入的元数据）。注意：如果启用了转发消息解析，解析后的转发内容文本也作为消息文本的一部分参与匹配，转发内容中的关键词同样会触发响应 |
| **重复匹配** | **首次命中即停止**。遍历关键词列表，检测到任意一个关键词匹配即立即返回 `True`，不会继续检查剩余关键词，也不会对匹配到的关键词计数 |
| **空关键词** | 自动跳过空字符串关键词，不会报错 |

**不同关键词类型的匹配差异：**

| 关键词类型 | 大小写 | 匹配方式 | 计数方式 |
|-----------|--------|---------|---------|
| `trigger_keywords` | 敏感 | 子串匹配 | 首次命中即停止 |
| `blacklist_keywords` | 敏感 | 子串匹配 | 首次命中即停止 |
| `humanize_interest_keywords` | **不敏感** | 子串匹配（`.lower()`） | 首次命中即停止 |
| `attention_emotion_keywords` | 敏感 | 子串匹配（`.find()`） | 累加计数（每次出现都计分） |
| `mood_keywords` | 敏感 | 子串匹配（`.find()`） | 累加计数（每次出现都计分） |

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
| `enable_ignore_at_others` | bool | `false` | 忽略@其他用户的消息，避免插入他人的对话；此配置不影响@全体成员。关闭时，无论消息里是单个@他人、多个@他人、重复@同一人，还是 `@AI + @他人` 混合场景，都不会因为这项功能而被跳过。 |
| `ignore_at_others_mode` | string | `"strict"` | 过滤模式：`strict` 或 `allow_with_bot`；此配置不影响@全体成员。当前实现语义为：`strict` = 只要消息里存在@他人，且**没有同时@AI**，就跳过；`allow_with_bot` = 存在@他人但也同时@AI时允许继续处理。多人@、重复@同一人时按完整提及结构统一判断，不只看第一个@对象。 |
| `enable_ignore_at_all` | bool | `false` | 忽略@全体成员消息，避免群公告触发AI。开启后消息会被直接跳过——不缓存、不保存到历史、不触发本插件AI处理；同时会消费当前事件的 AstrBot 默认 LLM 兜底，避免平台在插件已忽略后又强制回复，但不主动阻断其他插件 handler |
| `at_all_message_mode` | string | `"skip_probability"` | `@全体成员` 专用处理模式：`normal`（按普通消息处理）、`skip_probability`（跳过概率筛选，保留读空气AI）、`skip_all`（跳过概率筛选和读空气AI，直接回复）、`probability_boost`（仅为当前这条@全体成员消息临时提升概率）。@全体解析说明会随消息元数据保留；窗口缓冲和 Smart follower 转正时也会通过结构化 @ 信息兜底注入说明。若消息最终只进入概率过滤缓存、决策不回复缓存或等待窗口缓存，插件会消费当前事件的默认 LLM 兜底，避免缓存后被平台再次处理 |
| `at_all_probability_boost_value` | float | `0.3` | 仅在 `at_all_message_mode="probability_boost"` 时生效。为当前这一条@全体成员消息临时增加的概率值，不影响后续消息 |

---

## 戳一戳系统

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poke_message_mode` | string | `”bot_only”` | 戳一戳响应模式：`ignore`（完全忽略）、`bot_only`（仅响应戳机器人）、`all`（响应所有戳一戳）。**只有当前模式允许本插件实际处理的真实 poke**，才会自动生成两层标注：`[戳一戳事件]`（持久化，注入到消息格式中冒号前的系统元数据区，随消息保存到历史）与 `[戳一戳提示]`（运行时，追加在上下文分隔符之外，仅当前轮 AI 可见，保存时由过滤规则自动移除）。平台侧只提供 Poke 组件且正文为空时，会使用 `[ComponentType.Poke]` 作为内容占位；被该模式提前忽略的 poke 不会进入这一步 |
| `poke_bot_skip_probability` | bool | `true` | 戳机器人时跳过概率检查，直接进入AI决策 |
| `poke_bot_probability_boost_reference` | float | `0.3` | 戳一戳概率提升参考值 |
| `poke_reverse_on_poke_probability` | float | `0.0` | 被戳后立即反戳的概率（0 = 不反戳）。若反戳动作真实成功，会先以用户视角保存发起者的戳一戳事件，再以 assistant 视角保存 AI 反戳动作，两条记录均写入官方存储和自定义存储，绑定当前会话 |
| `enable_poke_after_reply` | bool | `false` | 回复消息后戳用户一下。若动作真实成功，会额外单独保存一条 AI 视角的戳一戳历史事件 |
| `poke_after_reply_probability` | float | `0.1` | 回复后戳用户的概率 |
| `poke_after_reply_delay` | float | `0.5` | 回复后到戳之间的延迟（秒） |
| `enable_poke_trace_prompt` | bool | `false` | 追踪谁戳了机器人，并在提示词中告知AI |
| `poke_trace_max_tracked_users` | int | `5` | 最大追踪用户数。超过上限时会移除当前最早登记的记录 |
| `poke_trace_ttl_seconds` | int | `300` | 追踪记录保留时间（秒） |
| `poke_enabled_groups` | list | `[]` | 启用戳一戳功能的群列表（空=所有群） |

---

## 转发消息解析

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_forward_message_parsing` | bool | `false` | 启用 QQ / OneBot 合并转发解析。解析器会把转发内容整理成单条可读文本并继续参与后续上下文与 AI 流程，而不是拆成多条消息 |
| `forward_max_nesting_depth` | int | `3` | 嵌套转发的最大解析深度（0=不展开嵌套，仅保留占位式降级；最大10）。在深度范围内会递归展开子转发，并尽量保留发送者信息与时间戳格式 |

解析结果会尽量保留转发内部每条节点的原始顺序。文本、引用、@、图片、视频、语音、文件等消息段逐段输出，单个媒体段解析失败时只在该段所在位置写入对应占位，不会影响同一条消息中的其他段继续解析。常见媒体输出格式包括 `[图片: ...]`、`[视频: ...]`、`[语音: ...]`、`[文件: ...]`；无法识别时分别降级为 `[图片（识别失败）]`、`[视频（识别失败）]`、`[语音（识别失败）]`、`[文件（识别失败）]`。

转发内部的引用消息会继续解析其内联内容或通过消息 ID 回退获取；引用内容中如再包含图片、视频、语音、文件或嵌套转发，也沿用同一套逐段解析规则。嵌套转发超过深度限制、接口不可用或内容无法获取时，仅替换为对应的嵌套转发占位。表情包图片只有在平台返回 `sub_type=1`、`summary` 含表情/emoji/sticker，或 `image_type/type` 等字段标明 sticker/emoji 时才会追加 `[表情包图片]`；缺少这些字段时会按普通图片处理，避免误判。

---

## 欢迎消息解析

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_welcome_message_parsing` | bool | `false` | 检测群成员入群欢迎消息 |
| `welcome_message_mode` | string | `"skip_probability"` | 处理模式：`normal`（正常走完整流程）、`skip_probability`（跳过概率筛选，仍需AI决策）、`skip_all`（跳过概率和AI决策，直接回复）、`parse_only`（仅解析标记，不触发回复） |

---

## 群聊等待窗口

> **使用 GWW 前请先关闭平台的 `empty_mention_waiting`（只 @ 机器人是否触发等待）。** 平台的空 @ 等待是群级别拦截，会劫持任意用户的消息并人工插入 @bot 后重新入队，与本插件冲突且会导致认错发送者。GWW 按用户粒度隔离，不会劫持他人消息，功能更精细可控。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_group_wait_window` | bool | `false` | 启用等待窗口。收到消息后短暂等待，收集后续消息一起处理，避免逐条回复。开启前请先关闭平台的 `empty_mention_waiting` |
| `group_wait_window_timeout_ms` | int | `3000` | 等待超时（毫秒，200-30000）。越长越能收集到完整信息，但响应越慢 |
| `group_wait_window_max_extra_messages` | int | `3` | 最多额外收集的消息数量 |
| `group_wait_window_max_users` | int | `5` | 最多同时追踪的发送者数量 |
| `group_wait_window_attention_decay_per_msg` | float | `0.05` | 窗口内每收到一条消息时注意力衰减量 |
| `group_wait_window_at_mode` | string | `"force_close"` | @消息窗口行为模式（force_close/intercept/immediate/bypass）。这里的“@消息”核心上仍然是**@AI自己**的消息；普通 `@别人` / `@多个别人` 不应仅因为包含At就误触发窗口打断逻辑。窗口接管混合 @ 消息时只剥离 AI 自己的 At，其他 At 与 @全体结构继续通过 `mention_info` 保留。 |
| `group_wait_window_keyword_mode` | string | `"intercept"` | 关键词消息窗口行为模式（intercept/force_close/immediate/bypass）。所有模式（bypass 除外）下，同用户的窗口内关键词消息都会先被缓存进窗口（关键词标记打掉），再根据模式决定是否立即结束窗口，打断消息不会产生独立的第二条处理管道 |
| `group_wait_window_poke_mode` | string | `"bypass"` | 戳一戳窗口行为模式（bypass/force_close）。戳一戳消息本身不会被窗口缓存吸收；`force_close` 只用于结束已有窗口，不改变戳一戳自己的处理链路 |
| `group_wait_window_merge_at_list_mode` | string | `"whitelist"` | @消息窗口接管的用户过滤模式（在 `at_mode=intercept/immediate/force_close` 时生效）。命中后，窗口逻辑只会洗刷掉 **@AI 自己的 At 组件**，不会移除或折叠其他人的 At；其他人相关的原始 At 与解析结果仍需正常保留进缓存/转正/历史。 |
| `group_wait_window_merge_at_user_list` | list | `[]` | @消息窗口接管的用户ID列表（在 `at_mode=intercept/immediate/force_close` 时生效）。留空表示对所有用户生效；无论名单如何命中，窗口侧都只洗刷 AI 自己的 At，不洗刷他人的 At，不折叠重复的他人 At。 |

等待窗口吸收的消息如果本身被 AstrBot 视为唤醒消息（例如 `@AI` 或平台未忽略的 `@全体成员`），插件会在缓存后消费当前事件的默认 LLM 兜底，避免同一条消息被平台默认回复链再次处理。窗口消息的读取、回落、保存与清理仍只依赖 `sender_id + gww_token` 或显式的 Smart 融合组，不依赖这个事件标记，因此不会扩大窗口匹配范围。

### 窗口消息的回落机制

当窗口锚点消息经过读空气AI判定"不回复"后，插件会自动将当前窗口批次内的所有窗口缓冲消息（`window_buffered=True`）转为普通缓存。该机制通过窗口令牌（`gww_token`）精确绑定当前批次，具备三层隔离：

- **会话隔离**（`chat_id`）：不同群聊/私信之间互不影响
- **用户隔离**（`sender_id`）：仅转换当前窗口所属用户的消息，同群其他用户的窗口消息不受影响
- **窗口隔离**（`gww_token`）：同一用户先后或并发存在的多个窗口之间令牌不同，旧窗口的转换不会误伤新窗口的缓存消息

回落后的消息等同于普通缓存消息：参与 Phase-1 正式转正、冷群自动转正、按原始时间戳与其他普通消息统排顺序。这确保了下一次成功触发回复时上下文先后顺序始终正确，旧窗口消息不会再被 Phase-2 错误拼接。

窗口内消息会完整走普通缓存的图片/At/系统提示过滤链路。过滤后若内容严格等于空字符串 `""`，不会缓存、不会计入窗口数量，但会刷新窗口 deadline；若只剩空格、换行或制表符，则仍按有内容保留。读空气 AI、普通回复的上下文拼接、AI 回复的追加消息标记、Phase-2 转正与清理均按 `sender_id + gww_token` 精确处理；当 Smart 批次为多个窗口建立融合组时，上述读/转/存/清操作会改按该融合组统一处理，融合组只包含本批次显式标记的窗口，不会扫描其它窗口，也不会覆盖已有其它融合组。Smart 自身吸收的 follower 不经过窗口缓存过滤链路，不会因为“戳一戳不进入窗口缓存”或窗口空内容过滤而被漏掉；它们只是在给 AI 看时复用“追加消息”展示格式。主动对话生成流程不会读取尚未转正的窗口缓冲消息，也不会读取普通链路临时持有的 Smart 批次快照；它会在触发前等待已通过概率/强制触发的普通候选链路和活跃等待窗口。窗口消息的正式保存仍由普通回复 Phase-2 或冷群转正处理；若普通链路因主动/转正 owner 等待超时回退缓存，同窗口消息或同融合组窗口消息会移除 `window_buffered` 标记转为普通缓存并保留原始时间戳。融合后的大窗口不重新套用 `group_wait_window_max_extra_messages` 数量限制：各原窗口在进入融合前已按自身配置限制过，融合阶段只负责把这些已存在的窗口消息按时间线交给当前批次处理。

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
| `enable_attention_mechanism` | bool | `false` | 启用多用户注意力追踪。每个用户有 0-1 之间的连续注意力值。开启后会替代传统的 `after_reply_probability` 回复后临时提升模式，两者互斥 |
| `attention_increased_probability` | float | `0.9` | 注意力最大提升概率参考值，作为高注意力时的概率上限参考。实际概率 = 当前概率 + (参考值 − 当前概率) × 注意力分数 × 情绪因子，渐进式计算 |
| `attention_decreased_probability` | float | `0.1` | 注意力最低概率参考值，注意力很低或情绪负面时的概率保底下限 |
| `attention_duration` | int | `120` | 不活跃用户清理阈值基数。超过此值×3秒无交互记录的用户会被清理出追踪列表。后台衰减不受此值影响 |
| `attention_max_tracked_users` | int | `10` | 最大同时追踪用户数 |

### 衰减与变化

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `attention_decay_halflife` | int | `300` | 注意力指数衰减半衰期（秒）。公式：`新分数 = 旧分数 × 0.5^(经过时间/半衰期)`。衰减在每次访问档案时自动计算，同时后台每60秒对所有已追踪用户执行一次定期衰减，确保静默期间注意力仍持续平滑下降 |
| `attention_boost_step` | float | `0.4` | 回复用户时注意力提升步长（范围0-1）。此步长在指数衰减之后独立叠加，不参与衰减计算：`最终注意力 = 衰减后分数 + boost_step`（上限1.0） |
| `attention_decrease_step` | float | `0.1` | 回复某用户后，同群其他被追踪用户的注意力降低步长（范围0-1）。执行顺序：先衰减，再减此步长。与 `attention_decay_on_no_reply_step` 是独立配置 |
| `enable_attention_decay_on_no_reply` | bool | `true` | 是否启用”读空气未回复衰减”机制 |
| `attention_decay_on_no_reply_step` | float | `0.2` | 普通概率路径消息被读空气判定不回复时的单次注意力衰减幅度 |
| `attention_decay_on_no_reply_min_threshold` | float | `0.3` | 只有当前注意力高于此值时，未回复衰减才生效；低于此值跳过，防止过度惩罚 |

> **衰减机制重要说明**：
> - 所有衰减（注意力、情绪）都使用指数公式 `0.5^(elapsed/halflife)`，不是线性也不是固定时间清零
> - 后台每60秒对所有已追踪用户执行一次统一衰减，**不依赖消息事件触发**。静默期间注意力仍会持续下降并落盘保存
> - 后台衰减任务只在**群聊功能总开关 + 注意力机制**同时启用时才启动；关任意一个都不会运行
> - 衰减使用独立的 `last_decay_time` 基线追踪，与 `last_interaction`（交互时间）解耦，同一请求链路中多次访问不会重复衰减
> - 注意力提升/降低步长（boost/step）不参与衰减计算公式，始终在衰减之后独立加减

### 情绪检测

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_emotion_detection` | bool | `false` | 是否启用注意力机制的消息情感检测。开启后分析消息正负面情绪调整情绪值；关闭则所有回复视为正面交互 |
| `emotion_decay_halflife` | int | `600` | 情绪值（-1到+1）向中性值0衰减的半衰期（秒）。公式与注意力衰减相同 `0.5^(elapsed/halflife)`，共用同一套后台定期衰减机制 |
| `emotion_boost_step` | float | `0.1` | 被回复用户情绪基础提升幅度（范围0-1）。中性消息时的默认提升值 |
| `attention_enable_negation` | bool | `true` | 是否启用否定词检测。开启后"不讨厌"不会被误判为负面情绪 |
| `attention_positive_emotion_boost` | float | `0.1` | 检测到正面消息时在基础提升之上的额外情绪提升 |
| `attention_negative_emotion_decrease` | float | `0.15` | 检测到负面消息时的情绪降低幅度（替代基础提升） |

### 注意力溢出

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_spillover` | bool | `true` | 对一个用户的高注意力会"溢出"到同群其他用户 |
| `attention_spillover_ratio` | float | `0.35` | 溢出比例。其他用户可获得最高注意力用户此比例的溢出加成，基于衰减后活跃度计算 |
| `attention_spillover_decay_halflife` | int | `90` | 溢出效果衰减半衰期。溢出活跃度随时间指数衰减，与注意力衰减共用同一公式 |
| `attention_spillover_min_trigger` | float | `0.4` | 只有最高注意力分数超过此阈值才会产生溢出效果，避免冷淡对话时误触发 |

### 注意力冷却

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attention_cooldown` | bool | `true` | 启用注意力冷却。它是正式冷却总开关：开启后，普通概率路径消息 no-reply 会进入冷却链路；若同时开启待冷却保护层，则先进入待冷却再决定是否升级为正式冷却；若关闭待冷却保护层，则直接进入正式冷却 |
| `enable_cooldown_auto_release` | bool | `true` | 是否允许正式冷却在超时后自动解冻；关闭时只会在该用户最终被 AI 回复时解除 |
| `cooldown_max_duration` | int | `600` | 正式冷却的最大持续时间（秒） |
| `cooldown_trigger_threshold` | float | `0.3` | 触发冷却的注意力阈值 |
| `enable_pending_attention_cooldown` | bool | `true` | 启用未接续谈保护层。开启后先进入待冷却，再视同一用户后续消息决定是否升级为正式冷却；关闭后将直接进入正式冷却 |
| `pending_cooldown_grace_user_messages` | int | `1` | 未接续谈保护阶段最多观察同一用户后续多少条自己的消息 |
| `pending_cooldown_max_wait_seconds` | int | `60` | 未接续谈保护最长等待时间（秒），超时后自动失效 |
| `pending_cooldown_same_user_probability_floor` | float | `0.18` | 未接续谈保护期间给同一用户保留的最低概率保护 |

> **重要说明**：
> - 这套机制分为两段：**待冷却（未接续谈保护）** 和 **正式冷却**。待冷却是否启用由 `enable_pending_attention_cooldown` 单独控制；正式冷却则由 `enable_attention_cooldown` 总控。
> - “读空气未回复衰减”现在是独立机制：未开启冷却时，可直接对普通 no-reply 执行衰减；开启冷却后，只有在用户正式进入冷却时才执行该衰减，待冷却阶段不会衰减。
> - `enable_cooldown_auto_release` / `cooldown_max_duration` 只作用于**正式冷却**，不作用于待冷却阶段。
> - 正式冷却与待冷却都只保存在**运行态内存**中，插件或平台重启后会清空，不再作为长期文件持久化。
> - 只有仍在当前会话注意力追踪列表中的用户，待冷却/正式冷却才有意义；若用户已不在注意力追踪列表中，会被自动从冷却名单中移除。
> - 这套保护补丁只作用于**普通概率路径消息**（非@AI、非关键词触发）。关键词唤醒和@AI消息不走这套误伤保护逻辑；但一旦这些路径最终成功触发回复，仍会统一解除正式冷却。

### 冷却升级迁移说明

以下旧配置项已移除，不再建议继续保留在配置文件中：

- `attention_decrease_on_no_reply_step` → `attention_decay_on_no_reply_step`
- `attention_decrease_threshold` → `attention_decay_on_no_reply_min_threshold`
- `cooldown_attention_decrease` → `attention_decay_on_no_reply_step`
- `enable_attention_decay_on_confirmed_no_reply` → `enable_attention_decay_on_no_reply`
- `confirmed_no_reply_attention_decrease_step` → `attention_decay_on_no_reply_step`
- `pending_cooldown_at_cancel_active` → 无替代，统一改为“最终成功回复即解除正式冷却”
- `skip_no_reply_decay_during_pending_reconnect` → 无替代，统一改为“待冷却观察期内固定不衰减”

升级后如果检测到这些旧键，插件会在启动日志中输出迁移提示。

同时，旧版独立 `cooldown_data.json` 中的冷却数据会在启动后由后台任务自动迁入当前运行态内存，再安全清理旧冷却残留；注意力、情绪等长期状态文件不会因此被删除。


| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_conversation_fatigue` | bool | `false` | 启用对话疲劳。连续对话后逐渐降低回复意愿，模拟真人节奏 |
| `fatigue_reset_threshold` | int | `300` | 疲劳重置的沉默时间（秒），不说话这么久后疲劳清零 |
| `fatigue_threshold_light` | int | `3` | 轻度疲劳的消息数阈值 |
| `fatigue_threshold_medium` | int | `5` | 中度疲劳的消息数阈值 |
| `fatigue_threshold_heavy` | int | `8` | 重度疲劳的消息数阈值 |
| `fatigue_probability_decrease_light` | float | `0.1` | 轻度疲劳的概率衰减 |
| `fatigue_probability_decrease_medium` | float | `0.2` | 中度疲劳的概率衰减 |
| `fatigue_probability_decrease_heavy` | float | `0.35` | 重度疲劳的概率衰减 |
| `fatigue_closing_probability` | float | `0.3` | 中度/重度疲劳时 AI 发出结束语（如"我先忙了"）的概率。轻度疲劳不触发 |

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
| `proactive_normal_reply_cooldown` | int | `60` | 普通对话冷静期。AI 通过普通回复流程成功回复后，在该时间内主动对话不会触发，避免刚正常回完又立刻主动发言；设为 0 表示关闭这层冷静期 |
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
| `enable_proactive_ai_judge` | bool | `true` | 主动发言前由主动对话预判断AI判断当前是否适合说话 |
| `proactive_ai_judge_include_persona` | bool | `true` | 是否为主动对话预判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格；关闭时按中性时机判断执行 |
| `proactive_ai_judge_persona_name` | string | `""` | 仅在 `proactive_ai_judge_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让主动对话预判断AI按该人格判断当前是否适合开口。若找不到则自动回退 |
| `proactive_ai_judge_prompt` | string | `""` | 主动对话预判断提示词。留空使用默认提示词。Web 面板可展开查看完整默认内容；传统配置页面不会显示这段预览，如需查看建议到 Web 面板对应配置项处查看。开启额外推理时无需手动写入推理协议；若缺失，系统会自动补充并保留你的原始提示词正文 |
| `proactive_ai_judge_timeout` | int | `15` | 主动对话预判断超时（秒）。该判断链路仍使用独立的 `provider.text_chat()` 直连方式，与回复生成 Hook 链分离 |
| `enable_proactive_ai_reasoning` | bool | `false` | 开启主动对话判断AI额外推理模式。AI必须先输出推理块，再在最后一行单独输出 yes/no；最终结论不得附带解释、前后缀或标点。推理块自动剥离。解析失败默认不触发（不进入冷却） |
| `proactive_ai_reasoning_log` | bool | `false` | 开启后将主动对话判断AI的推理相关内容输出到 AstrBot 日志 |
| `proactive_ai_reasoning_log_mode` | string | `"processed"` | 主动对话判断AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |

> **🔁 备用提供商说明**：主动对话预判断AI(#3)使用上方的 `decision_ai_fallback_provider_ids`（与读空气AI、频率判断AI三处共用）。主动对话生成AI(#4)的备用提供商为 `proactive_gen_fallback_provider_ids`（list，默认 `[]`），在生成时平台默认回复AI返回错误/空内容后按列表顺序切换备用提供商；超时由平台自身管理。以上两项留空均=不启用备用机制。

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
| `frequency_ai_include_persona` | bool | `true` | 是否为频率判断AI自动注入判断专用人格。开启时默认跟随当前会话当前生效的人格，并按该人格在当前时段下应有的活跃倾向判断；关闭时按中性群聊参与强度判断 |
| `frequency_ai_persona_name` | string | `""` | 仅在 `frequency_ai_include_persona=true` 时生效。留空=使用当前会话当前生效的人格（推荐）；填写完整人格名=强制让频率判断AI按该人格判断“正常 / 过于频繁 / 过少”。若找不到则自动回退 |
| `frequency_check_interval` | int | `180` | 分析间隔（秒） |
| `frequency_analysis_timeout` | int | `20` | 分析超时 |
| `frequency_adjust_duration` | int | `360` | 调整效果持续时间 |
| `frequency_analysis_message_count` | int | `15` | 参与分析的消息数量 |
| `frequency_min_message_count` | int | `5` | 最少消息数才进行分析 |
| `frequency_decrease_factor` | float | `0.85` | 降低频率系数 |
| `frequency_increase_factor` | float | `1.1` | 提升频率系数 |
| `frequency_min_probability` | float | `0.03` | 调整后概率下限 |
| `frequency_max_probability` | float | `0.85` | 调整后概率上限 |
| `enable_frequency_ai_reasoning` | bool | `false` | 开启频率判断AI额外推理模式。AI必须先输出推理块，再在最后一行单独输出「正常/过于频繁/过少」之一；最终结论不得附带解释、前后缀或标点。推理块自动剥离。解析失败默认不调整概率 |
| `frequency_ai_reasoning_log` | bool | `false` | 开启后将频率判断AI的推理相关内容输出到 AstrBot 日志 |
| `frequency_ai_reasoning_log_mode` | string | `"processed"` | 频率判断AI推理日志输出模式。`processed` = 输出解析后的额外推理块；`raw` = 输出模型原始完整文本 |

> 说明：频率判断AI使用的推理起止标志符与读空气AI、主动对话判断AI共用，Web 面板会在三处入口同步显示同一套配置。

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
| `memory_plugin_mode` | string | `"auto"` | 记忆模式：`auto`（自动检测，优先 LivingMemory → 回退 Legacy → 都没有则跳过）、`legacy`（传统模式，稳定性高）、`livingmemory`（智能模式，混合检索+人格隔离）。auto 模式下两个插件都安装时优先使用 LivingMemory，都未安装时自动跳过记忆注入不会报错 |
| `memory_insertion_timing` | string | `"post_decision"` | 记忆注入时机：`pre_decision`（决策前，记忆影响"是否回复"）、`post_decision`（决策后，记忆只影响"回复内容"） |
| `livingmemory_version` | string | `"auto"` | LivingMemory 架构版本适配方式：`auto`（推荐，自动识别 v2/v1）、`v2`（2.x+ 新架构）、`v1`（1.x 旧架构） |
| `livingmemory_persona_compat_mode` | string | `"auto"` | LivingMemory 人格ID兼容模式：`auto`（推荐，自动尝试新版/旧版人格接口）、`resolver_only`、`legacy_only`、`off` |
| `livingmemory_top_k` | int | `5` | 召回的记忆条数，仅在 livingmemory 模式或 auto 检测到 LivingMemory 时有效 |

> Web 面板说明：以上 LivingMemory 相关配置已同步挂载到技术树的「记忆注入」节点，可在 Web 配置面板直接修改。

---

## 工具提示

> 兼容增强说明：`on_llm_request` 中的恢复逻辑现在不仅会优先重写 `system_prompt`，还会尝试安全吸收第三方插件提前写入的长期提示词：
> - `system_prompt`：继续优先复用旧版精确命中路径；若平台 persona 包装或空白有轻微变化，会自动尝试轻量兼容识别。
> - `prompt`：若第三方是在短消息前后追加长期说明 / 记忆文本，插件会按“安全增量”吸收到最终 full prompt 的固定兼容补充区。
> - `contexts`：若第三方注入的是结构稳定的长期记忆型 / fake tool call 型上下文，插件会尝试保留并追加回最终 contexts。
> - `extra_user_content_parts`：除严格识别为平台 GroupChatContext 重复历史块的内容外保持原样，不会被本插件清空；识别不确定时优先保留。
>
> 若仍无法高置信度识别或判定为不安全，插件会进入**保守回退模式**：优先保留当前 `req.system_prompt`，跳过可疑的 `prompt/contexts` 吸收，并输出 warning 日志，但不会阻断回复流程，也不会影响 `req.func_tool` / `req.image_urls` 的主语义恢复。
>
> 排查建议：
> - 想看本次走了哪条兼容路径、吸收了多少第三方补充，请开启 `enable_debug_log`
> - 若未开详细日志仍看到 warning，通常说明当前 AstrBot 或第三方插件的注入结构变化较大，插件已经优先选择“不断链、尽量保留安全内容”的保守模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_tools_reminder` | bool | `false` | 是否启用**工具提醒文本**。开启后，插件会在 `on_llm_request` 阶段基于**当前会话最终 `req.func_tool`**（已被其他插件如 maid_agent 过滤后的工具集）生成一段运行时提示词并追加到 `system_prompt` 末尾，告诉 AI 当前会话里有哪些工具可用；关闭后完全不注入任何工具提醒文本。**注意：此开关只影响提醒文本，不影响 AstrBot 原生工具调用能力，也不拦截 AI 实际调用工具。** |
| `tools_reminder_persona_filter` | bool | `false` | 是否在工具提醒层按当前会话人格过滤工具。仅在 `enable_tools_reminder=true` 时生效：开启后，先取当前会话最终可见工具（已被其他插件过滤），再按人格允许工具名单二次过滤后展示；关闭则展示当前会话最终可见的全部工具。**它只影响提醒展示文本，不拦截 AI 实际调用工具。** |

### 工具提醒的运行规则

- 工具提醒不再在群聊主流程前半段提前拼进 `final_message`，而是延后到 `on_llm_request` 阶段生成并追加到 `system_prompt` 末尾。
- 提醒文本的来源是**当前会话最终 `req.func_tool`**（已被其他插件如 maid_agent 过滤后的工具集），确保提醒内容与 AI 实际可调用工具一致，因此会自动兼容：
  - AstrBot 内置工具
  - 联网搜索工具
  - 知识库 / 数据库检索类工具（只要它们以 tool 形式进入当前会话）
  - sandbox / local runtime 工具
  - 第三方插件注册的工具（`@llm_tool` 装饰器）
  - 用户额外添加工具 / MCP 工具
- 工具集由 `reply_handler` 通过 `event.request_llm(tool_set=...)` 传递全平台工具集，`on_llm_request` 钩子**只读不写** `req.func_tool`，由其他插件（如 maid_agent）自由管控实际可用工具。
- 会话隔离优先于人格过滤：会先按当前会话最终可见工具集收口（已被其他插件过滤），再决定是否叠加人格过滤展示。
- 当 AstrBot 当前会话的 `provider_settings.tool_schema_mode=skills_like` 时，工具提醒会**自动降级为仅展示工具名称与功能描述**，不再展开参数列表，以避免干扰框架的两阶段工具 schema 暴露流程、减少跨工具参数串扰。
- 当 `tool_schema_mode=full` 或当前 AstrBot 版本/配置中无法识别该字段时，工具提醒保持原有完整展示（名称 + 描述 + 参数）。
- 若工具提醒生成失败、人格解析失败或当前会话工具获取失败，会自动降级为**跳过提醒**，但不会阻断回复流程，也不会清空实际工具集。

### 历史保存与过滤

- 以下一次性系统提示块属于**运行时 prompt 提示**，不应进入官方历史或自定义历史：
  - Skills 提示词：包裹在 `[系统-Skills开始]...[系统-Skills结束]` 中
  - 工具调用指引：包裹在 `[系统-工具调用指引开始]...[系统-工具调用指引结束]` 中
  - 工具列表提醒：包裹在 `[系统提示-工具提醒开始]...[系统提示-工具提醒结束]` 中
  - 情绪参考提示：包裹在 `[系统-情绪提示开始]...[系统-情绪提示结束]` 中
  - 第三方插件注入：包裹在 `[第三方插件补充信息]` / `[第三方插件注入上下文]` 及其逐插件具名变体中
- `MessageCleaner` 与 `ContextManager` 的清理逻辑已对上述所有标记做整块兜底过滤；即使异常混入保存链路，也会在保存前被清除。不成对的孤儿标记也会被单独清理。

---

## 内容过滤

内容过滤器用于在 AI 生成回复后，按用户配置的规则移除特定标记内容。**输出过滤**和**保存过滤**是两套完全独立的规则集，互不影响：

- **输出过滤**：控制"发给用户看的内容"，过滤发生在发送前的一刻
- **保存过滤**：控制"写入历史记录的内容"，过滤发生在保存前的一刻（保存时不包含错字模拟等装饰性修改）

> **📌 生效范围**：此开关一旦开启，对**普通回复**和**主动对话生成**两条路径同时生效，没有单独的路径开关。两条路径共享同一套过滤规则和同一个过滤器实例。输出过滤和保存过滤各自独立开关。
>
> 两套过滤作用在同一个 AI 原始输出上，各自独立执行，因此可以为输出和保存配置不同的规则。

### 配置项总览

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_output_content_filter` | bool | `false` | 在 AI 回复发送给用户前进行过滤 |
| `output_content_filter_rules` | list | `[]` | 输出过滤规则列表 |
| `enable_save_content_filter` | bool | `false` | 在保存到历史记录前进行过滤 |
| `save_content_filter_rules` | list | `[]` | 保存过滤规则列表 |

### 规则语法

每条规则由 **开始标记** + 通配符 `*` + **结束标记** 组成，支持三种模式：

#### 1. 范围过滤（Range）

```
<开始标记>*<结束标记>
```

移除两个标记之间的**所有内容（包含标记本身）**。会在整段文本中**循环匹配**，直到找不到为止。

**示例：**
```
规则: [思考]*[/思考]
原文: 你好 [思考] 让我想想怎么回 [/思考] 今天天气不错 [思考] 再看看 [/思考] 对吧
结果: 你好  今天天气不错  对吧
```

#### 2. 头部过滤（Head）

```
{{>*<结束标记>
```

从文本**开头**到结束标记（包含标记）全部移除。**只匹配第一次出现**，不循环。

**示例：**
```
规则: {{>*[系统指令结束]
原文: [系统指令] 你是一个AI助手 [系统指令结束] 好的，我来回答你的问题
结果:  好的，我来回答你的问题
```

#### 3. 尾部过滤（Tail）

```
<开始标记>*>}}
```

从开始标记（包含标记）到文本**末尾**全部移除。**只匹配第一次出现**，不循环。

**示例：**
```
规则: [内部标记]*>}}
原文: 这是我的回答 [内部标记] 下面是一些内部元信息不需要发出去
结果: 这是我的回答
```

### 执行行为（重要）

#### 规则按顺序逐条执行，后一条在前一条的结果上继续过滤

```python
# 伪代码
for rule in rules:
    content = apply_rule(content, rule)
```

这意味着规则列表中排在后面的规则看到的是前面规则已经过滤过的文本。**规则顺序会影响最终结果。**

**示例：规则顺序的影响**
```
规则1 (tail): [A]*>}}
规则2 (range): [A]*[B]

原文: 保留内容 [A] 垃圾 [B] 更多
→ 规则1 执行后: 保留内容         （[A] 及之后全部移除）
→ 规则2 执行后: 保留内容         （找不到 [A]*[B] 的匹配，无变化）

如果规则顺序反过来:
→ 规则2 先执行: 保留内容  垃圾       （[A] [B] 范围被移除，但 [B] 后面的 " 更多" 还在）
→ 规则1 再执行: 保留内容  垃圾       （此时文本中已无 [A]，Tail 规则不触发）
```

> **建议**：把范围最广的规则（如 Head/Tail）放在前面，精细的范围规则放在后面。

#### 三种模式内部的重复匹配行为不同

| 模式 | 内部行为 |
|------|----------|
| Range `A*B` | **循环匹配** — `while True` 反复查找删除，直到文本中再无匹配 |
| Head `{{>*B` | **单次匹配** — 只找第一个 `B` 标记，从开头砍到那里就停 |
| Tail `A*>}}` | **单次匹配** — 只找第一个 `A` 标记，从那里砍到末尾就停 |

**Head 不会帮你清理第二个同类标记：**
```
规则: {{>*[END]
原文: 垃圾 [END] 好内容 [END] 更多好内容
结果:  好内容 [END] 更多好内容
                ↑ 第二个 [END] 没有被处理
```

如果确实需要清理后面的 `[END]`，可以追加一条 Tail 规则 `[END]*>}}` 收尾。

#### 交错叠加不会出问题

三种模式可以自由组合。例如 Head 砍掉前半段 → Range 挖掉中间的标记块 → Tail 去掉末尾的元信息，每条规则在之前的结果上独立执行，系统不会崩溃或产生错误输出。

### 适用场景

| 场景 | 推荐模式 | 示例规则 |
|------|----------|----------|
| 移除 AI 的思考过程 | Range | `<thinking>*</thinking>` |
| 移除其他插件注入的提示词块 | Range | `[第三方提示]*[/第三方提示]` |
| 去掉 AI 回复开头的系统指令残留 | Head | `{{>*[指令结束]` |
| 去掉 AI 回复末尾的内部元信息 | Tail | `[内部]*>}}` |
| 同时清理多种标记 | 多规则组合 | 见上方示例 |

### 与 AI 思考链过滤的关系

本项目的过滤分为两层，各司其职：

| 过滤层 | 模块 | 作用对象 | 作用时机 |
|--------|------|----------|----------|
| **思考链过滤** | `AIResponseFilter` | 判断型 AI（读空气、主动对话预判断、频率调整） | 解析判断结果之前 |
| **内容过滤** | `ContentFilter`（本配置节） | 生成型 AI 的回复文本（普通回复、主动对话生成） | 发送前 / 保存前 |

两者互不重叠：思考链过滤处理 yes/no 等结构化判断输出中的 `<thinking>` 标签；内容过滤处理最终回复文本中的自定义标记。

---

## 回复生成

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `reply_ai_prompt_mode` | string | `"append"` | 回复提示词模式。`append`：追加到内置提示后；`override`：完全替换。无论哪种模式，这一层都属于**运行时生成回复用的提示词**，不会作为普通历史正文持久化保存；当 `concurrent_mode=smart` 且开启 `enable_smart_batch_reply_hint` 时，决策阶段和回复阶段分别动态插入 Smart 批次提示（决策阶段侧重判断对象、回复阶段侧重如何组织回复） |
| `reply_ai_extra_prompt` | string | `""` | 自定义回复提示词。用于约束「生成最终回复内容」的 AI；建议保持“直接生成要发出去的话”的职责边界，不要写成 yes/no 判断口吻，也不要继续强化“先判断再说”的内部取舍描述；同时不要要求模型把内心想法、思考过程、系统提示词、工具/搜索过程或其他元信息写进最终发言。留空时回退到代码内置默认提示词；该提示词本身属于运行时指令，不应被保存到历史中；若需查看默认提示词正文，建议到 Web 面板对应配置项处查看预览，传统配置页面不会显示这段默认提示词预览；Smart 批次提示增强生效时，决策阶段和回复阶段会分别注入可自动过滤的 Smart 提示 |

---

## 历史管理指令

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `plugin_gcp_reset_allowed_user_ids` | list | `[]` | 允许使用 `gcp_reset`（插件级全局重置）的用户ID列表 |
| `plugin_gcp_reset_here_allowed_user_ids` | list | `[]` | 允许使用 `gcp_reset_here`（当前会话重置）的用户ID列表 |
| `gcp_clear_image_cache_allowed_user_ids` | list | `[]` | 允许清除图片缓存的用户ID列表 |

> **行为边界说明**：
> - `gcp_reset` = 全局重置。清理插件维护的全局运行态与本地持久化缓存（如自定义 `chat_history` 历史目录、注意力/主动对话持久化文件等），并为所有已知会话设置 `history_cutoff.json` 历史截止时间戳。
> - `gcp_reset_here` = 单会话重置。完整清理当前会话全部运行态（20+ 项，Web 端「指令快捷操作→会话重置」与命令行使用完全相同的清理逻辑）、删除当前会话的自定义聊天记录文件，并设置历史截止时间戳，不应扩散到其他会话。
> - `gcp_clear_image_cache` = 仅清理图片描述缓存。当前主缓存文件为 `image_cache/descriptions.jsonl`；若检测到旧版残留路径 `image_description_cache.json` 也会兼容清理，但不会清理聊天记录、注意力、概率或主动对话状态。
> - **⚠️ 截止时间戳（`history_cutoff.json`）仅过滤 `platform_message_history` 表（SQLite）的读取路径**。`conversations` 表（LLM 对话上下文）需平台 `/reset` 清理；插件自定义 `chat_history/...` JSON 文件在 reset 时直接删除。若自定义 JSON 文件因异常残留（删除失败），可通过 Web 会话管理或文件管理器找到对应文件手动清空/删除。

---

## 私聊功能（开发中）

> **⚠️ 警告：私聊功能目前仍在开发测试阶段，请勿启用！当前版本的私聊模块尚未完善，开启可能导致异常行为。**

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_private_chat` | bool | `false` | **⚠️ 请保持 false！** 私聊处理总开关 |

私聊模块有独立的 30+ 个配置项（类似群聊的简化版），包含消息聚合、用户过滤、图片处理等功能。当前文档先补充两点关键链路说明：

- **私信回复生成**：与群聊回复生成保持同类调用方式，先通过 `event.request_llm()` 触发 Hook 链，再恢复完整上下文
- **私信主动对话生成**：与群聊主动对话保持同类调用方式，使用 `ProviderRequest + OnLLMRequestEvent` 兼容链路恢复完整 prompt

待正式发布后将补充完整文档。

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [消息工作流程 →](MESSAGE_WORKFLOW.md) | [项目结构 →](PROJECT_STRUCTURE.md) | [桌面端兼容 →](DESKTOP_COMPATIBILITY.md)
