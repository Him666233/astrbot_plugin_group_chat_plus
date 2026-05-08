# AstrBot 桌面端兼容说明

> 本文档说明 **Group Chat Plus 插件** 在 AstrBot 桌面端（Desktop Edition）与标准版之间的差异，以及已知的兼容性问题与解决方案。

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考](CONFIG_REFERENCE.md) | [消息工作流程](MESSAGE_WORKFLOW.md) | [项目结构](PROJECT_STRUCTURE.md)

---

## 目录

1. [桌面端 vs 标准版概览](#桌面端-vs-标准版概览)
2. [路径差异](#路径差异)
3. [重启机制差异（核心兼容问题）](#重启机制差异)
4. [环境变量差异](#环境变量差异)
5. [Web 面板注意事项](#web-面板注意事项)
6. [插件安装与更新](#插件安装与更新)
7. [故障排除](#故障排除)

---

## 桌面端 vs 标准版概览

| 对比项 | 标准版 | 桌面端 |
|--------|--------|--------|
| **运行方式** | `python main.py` 或 Docker/systemd | Tauri 桌面应用托管 Python 子进程 |
| **进程管理** | 用户自行管理（手动/容器/守护进程） | Tauri 自动管理后端生命周期 |
| **数据根目录** | 当前工作目录 或 `$ASTRBOT_ROOT` | 默认 `~/.astrbot`（由 Tauri 设置） |
| **Python 环境** | 用户自行安装的 Python | 桌面端内置 CPython 3.12（打包模式） |
| **WebUI** | 需单独安装或指定路径 | 内置打包，自动加载 |
| **更新机制** | 手动 / pip / uv | 内置 Tauri Updater（支持 stable/nightly） |
| **网络绑定** | 用户可配置任意地址 | 默认 `127.0.0.1:6185`（仅本地） |
| **日志** | 单一后端日志 | 分离为 `desktop.log` + `backend.log` |
| **桌面端标识** | 无 | 环境变量 `ASTRBOT_DESKTOP_CLIENT=1` |

---

## 路径差异

### 标准版路径结构

```
<AstrBot 源码目录>/          （通常是 git clone 的位置）
├── main.py
├── astrbot/
└── data/
    ├── cmd_config.json
    ├── plugins/              ← 插件源码
    ├── plugin_data/          ← 插件数据
    ├── config/
    ├── temp/
    └── site-packages/
```

工作目录 = AstrBot 源码根目录，所有 `data/` 路径都相对于此。

### 桌面端路径结构

```
~/.astrbot/                   （ASTRBOT_ROOT，由 Tauri 设置）
├── data/
│   ├── cmd_config.json
│   ├── plugins/              ← 插件源码
│   │   └── astrbot_plugin_group_chat_plus/
│   ├── plugin_data/          ← 插件数据
│   │   └── astrbot_plugin_group_chat_plus/
│   ├── config/
│   ├── temp/
│   └── site-packages/
└── logs/
    ├── desktop.log           ← Tauri 桌面端日志
    └── backend.log           ← AstrBot 后端日志
```

桌面端源码位于打包目录中（不可直接编辑）：
```
<Tauri 安装目录>/resources/backend/app/    ← AstrBot 后端源码
<Tauri 安装目录>/resources/backend/python/ ← 内置 CPython 3.12
```

### 对本插件的影响

本插件使用 `StarTools.get_data_dir()` 获取数据目录，**两种部署方式下均能正确获取路径**，无需额外处理。

| 路径类型 | 获取方式 | 标准版 | 桌面端 |
|----------|----------|--------|--------|
| 插件数据目录 | `StarTools.get_data_dir()` | `<cwd>/data/plugin_data/astrbot_plugin_group_chat_plus/` | `~/.astrbot/data/plugin_data/astrbot_plugin_group_chat_plus/` |
| 插件源码目录 | `Path(__file__).parent` | `<cwd>/data/plugins/astrbot_plugin_group_chat_plus/` | `~/.astrbot/data/plugins/astrbot_plugin_group_chat_plus/` |
| Web 面板静态文件 | `Path(__file__).parent / "web/static"` | 同上相对路径 | 同上相对路径 |

**注意**：如需手动查找插件文件（排查问题），桌面端用户请前往 `~/.astrbot/data/plugins/` 目录。

---

## 重启机制差异

> **这是桌面端最核心的兼容性差异。**

### 标准版重启流程

```
插件调用 POST /api/stat/restart-core
  → AstrBot 后端收到请求
  → 终止所有子进程
  → 调用 os.execv() 替换当前进程（原地重启）
  → 新进程启动，加载插件
  → 插件 on_platform_loaded() 发送"重启完成"通知
```

`os.execv()` 在 Linux/macOS 上是原子的进程替换，非常可靠。

### 桌面端重启流程

桌面端由 Tauri 管理后端进程，实现了三种重启策略：

| 策略 | 条件 | 行为 |
|------|------|------|
| **ManagedSkipGraceful** | Windows + 打包模式 + 托管子进程 | 跳过 HTTP API，直接 force-kill → relaunch |
| **ManagedWithGracefulFallback** | 非 Windows + 托管子进程 | 先尝试 HTTP API → 超时则 force-kill → relaunch |
| **UnmanagedWithGracefulProbe** | 非托管后端 | 仅尝试 HTTP API → 失败则报错 |

### 潜在问题：插件直接调用重启 API

当本插件通过 `gcp_reset` / `gcp_reset_here` / `gcp_clear_image_cache` 指令或 Web 面板触发重启时，流程如下：

```
插件 → POST /api/stat/restart-core
  → AstrBot 后端调用 os.execv()
  → 【问题点】在 Windows 上，os.execv() 实际是「新建进程 + 退出当前进程」
  → Tauri 丢失对子进程的跟踪（子进程 PID 变了）
  → Tauri 可能误判为「后端崩溃」
  → 可能出现：桌面端显示后端离线 / 自动重启导致双进程 / 无响应
```

### 插件的兼容处理

本插件（v1.2.2+）已添加完整的桌面端检测与适配机制。详细配置项说明见 [配置项参考 → 桌面端兼容](CONFIG_REFERENCE.md#桌面端兼容)。

#### 检测模式（`desktop_mode` 配置项）

| 模式 | 说明 |
|------|------|
| `auto`（默认，推荐） | 多重策略自动检测，首次成功后将检测依据写入 `desktop_detected_env` 配置项 |
| `force_desktop` | 手动强制桌面端模式，适用于自动检测失败但确实在使用桌面端的情况 |
| `force_standard` | 手动强制标准版模式，关闭所有桌面端兼容提示 |

#### 自动检测依据（按优先级）

```
①  环境变量 ASTRBOT_DESKTOP_CLIENT=1         ← 最可靠，桌面端打包模式必设
②  ASTRBOT_ROOT 指向 ~/.astrbot               ← 桌面端默认数据目录
③  ASTRBOT_WEBUI_DIR 路径包含 resources       ← 桌面端打包资源特征
④  PYTHONNOUSERSITE=1 + ASTRBOT_ROOT 同时存在  ← 桌面端环境隔离特征
```

检测结果自动写入 `desktop_detected_env` 配置项（只读），可在 AstrBot 配置界面或 Web 面板查看。

#### 桌面端模式下的行为

1. **日志警告**：桌面端触发重启时，日志中记录额外警告信息
2. **用户提示**：重启指令执行后，向聊天发送桌面端专属提示：
   > ⚠️ 桌面端提示：重启由 Tauri 托管进程管理，如重启后无响应，请通过桌面端托盘菜单手动重启后端。
3. **Web 面板**：API 响应中包含 `is_desktop` 和 `desktop_info` 字段，前端可据此展示提示

### 桌面端用户操作建议

| 场景 | 建议操作 |
|------|----------|
| 执行 `gcp_reset` / `gcp_reset_here` 后无响应 | 桌面端托盘图标 → 右键 → **Restart Backend** |
| 执行 `gcp_clear_image_cache` 后无响应 | 同上 |
| Web 面板「保存并重启」后面板断连 | 等待 10-15 秒，刷新页面；如仍无法访问则手动重启 |
| 后端状态显示「离线」但插件仍运行 | 桌面端可能丢失了进程跟踪，手动重启即可 |

---

## 环境变量差异

### 桌面端专属环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `ASTRBOT_DESKTOP_CLIENT` | `1` | 标识桌面端环境（仅打包模式设置） |
| `ASTRBOT_ROOT` | `~/.astrbot` | 数据根目录 |
| `ASTRBOT_WEBUI_DIR` | `<安装目录>/resources/webui` | WebUI 静态文件路径 |
| `DASHBOARD_HOST` | `127.0.0.1` | 仪表盘绑定地址（默认仅本地） |
| `DASHBOARD_PORT` | `6185` | 仪表盘端口 |
| `PYTHONNOUSERSITE` | `1` | 隔离 Python 环境，不加载用户 site-packages |
| `PYTHONUNBUFFERED` | `1` | 无缓冲输出（保证日志实时性） |
| `PYTHONUTF8` | `1` | UTF-8 模式 |

### 对插件的影响

- **`DASHBOARD_PORT`**：本插件使用此环境变量获取仪表盘端口（优先级高于配置文件），两种模式均兼容
- **`PYTHONNOUSERSITE`**：桌面端隔离了 Python 环境，插件的依赖必须安装在 AstrBot 的 `site-packages` 目录中
- **`ASTRBOT_DESKTOP_CLIENT`**：本插件用此变量检测桌面端模式

---

## Web 面板注意事项

### 端口冲突

- AstrBot 仪表盘默认端口：`6185`
- 本插件 Web 面板默认端口：`1451`

两者端口不同，正常情况下不会冲突。但需注意：

1. **桌面端绑定地址**：AstrBot 仪表盘默认绑定 `127.0.0.1`，本插件 Web 面板默认绑定 `0.0.0.0`
2. **防火墙**：桌面端环境可能有更严格的防火墙设置
3. **访问方式**：桌面端用户通常从本机访问，地址为 `http://127.0.0.1:1451`

### HTTPS / 代理

桌面端不自带反向代理。如需通过外网访问 Web 面板，用户需自行配置 Nginx/Caddy 等反代。

补充说明：

- 如果反代与 Web 面板部署在**同一台机器**，即使未开启 `web_panel_trust_proxy`，只要后端看到的连接来源是 `127.0.0.1 / ::1`，系统也会自动读取 `X-Real-IP / X-Forwarded-For` 获取真实客户端 IP
- 如果反代**不在本机**，则需要显式开启 `web_panel_trust_proxy` 才会信任代理头
- `web_panel_trust_proxy` 已归类为**安全边界配置**，现在只能通过 AstrBot 传统配置界面修改，Web 面板只读显示

---

## 插件安装与更新

### 标准版

```
# 方式 1：通过 AstrBot 仪表盘「插件市场」安装
# 方式 2：手动 clone
cd <AstrBot目录>/data/plugins/
git clone https://github.com/Him666233/astrbot_plugin_group_chat_plus.git
```

### 桌面端

```
# 方式 1：通过桌面端内置的仪表盘「插件市场」安装（推荐）
# 方式 2：手动 clone
cd ~/.astrbot/data/plugins/
git clone https://github.com/Him666233/astrbot_plugin_group_chat_plus.git
```

**桌面端注意事项：**
- 插件目录位于 `~/.astrbot/data/plugins/`，不在桌面端安装目录中
- 安装后需通过桌面端重启后端使插件生效
- 桌面端内置 Python 环境隔离（`PYTHONNOUSERSITE=1`），插件依赖会自动安装到 `~/.astrbot/data/site-packages/`

---

## 故障排除

### Q: 桌面端执行 gcp_reset 后 AstrBot 无响应

**原因**：桌面端（Windows）的重启策略是 `ManagedSkipGraceful`，插件通过 HTTP API 触发的 `os.execv()` 重启可能导致 Tauri 丢失子进程跟踪。

**解决**：
1. 右键桌面端系统托盘图标
2. 点击 **Restart Backend**（重启后端）
3. 等待后端重新启动

### Q: 桌面端找不到插件配置文件在哪里

**路径**：`~/.astrbot/data/plugin_data/astrbot_plugin_group_chat_plus/`

- Windows：`C:\Users\<用户名>\.astrbot\data\plugin_data\astrbot_plugin_group_chat_plus\`
- macOS：`/Users/<用户名>/.astrbot/data/plugin_data/astrbot_plugin_group_chat_plus/`
- Linux：`/home/<用户名>/.astrbot/data/plugin_data/astrbot_plugin_group_chat_plus/`

### Q: 桌面端 Web 面板无法访问

1. 确认插件配置中 `enable_web_panel` 已开启
2. 确认 `web_panel_port`（默认 1451）未被占用
3. 桌面端环境下，使用 `http://127.0.0.1:1451` 访问
4. 检查日志：`~/.astrbot/logs/backend.log`

### Q: 桌面端安装插件依赖失败

桌面端使用内置 Python 且设置了 `PYTHONNOUSERSITE=1`，依赖安装路径为 `~/.astrbot/data/site-packages/`。

如遇到依赖问题：
1. 打开终端/命令行
2. 使用桌面端内置 Python 手动安装：
   ```bash
   # Windows 示例（具体 Python 路径取决于桌面端安装位置）
   ~/.astrbot/data/site-packages/  # 检查此目录是否存在
   ```
3. 或卸载后重新安装插件，让 AstrBot 自动处理依赖

### Q: 标准版和桌面端的数据能否互通

可以，但需要手动迁移数据目录。两种版本使用相同的数据格式：

1. 将标准版 `data/plugin_data/astrbot_plugin_group_chat_plus/` 复制到桌面端 `~/.astrbot/data/plugin_data/astrbot_plugin_group_chat_plus/`
2. 重启桌面端后端

### Q: 如何判断当前运行在哪种模式下

**方法 1**：查看插件日志启动信息：
- 自动检测成功：`🖥️ [桌面端] 自动检测到桌面端环境（依据：env:ASTRBOT_DESKTOP_CLIENT=1）`
- 手动强制桌面端：`🖥️ [桌面端] 用户强制配置为桌面端模式（desktop_mode=force_desktop）`
- 标准版：`🖥️ [桌面端] 自动检测：未检测到桌面端环境` 或无相关日志

**方法 2**：在 AstrBot 配置界面查看 `desktop_detected_env` 配置项的值

**方法 3**：在 Web 面板 API 中检查 `/api/config` 响应的 `desktop_info` 字段

### Q: 自动检测不准确怎么办

`desktop_mode` 配置项支持手动覆盖（见 [配置项参考 → 桌面端兼容](CONFIG_REFERENCE.md#桌面端兼容)）：
- 如果自动检测误判为桌面端 → 设为 `force_standard`
- 如果自动检测未能识别桌面端 → 设为 `force_desktop`
- 修改后需重启插件生效

---

## 版本兼容性

| 插件版本 | 标准版兼容 | 桌面端兼容 | 说明 |
|----------|-----------|-----------|------|
| < v1.2.2 | ✅ | ⚠️ 部分兼容 | 重启指令可能导致桌面端异常，无桌面端提示 |
| >= v1.2.2 | ✅ | ✅ | 添加桌面端检测、重启警告、路径兼容 |

**AstrBot 版本要求**：`>= 4.11.0`（metadata.yaml 中声明）

---

[← 返回 README](../README.md) | [深度指南与常见问题](ARCHITECTURE.md) | [配置项参考 →](CONFIG_REFERENCE.md) | [消息工作流程 →](MESSAGE_WORKFLOW.md) | [项目结构 →](PROJECT_STRUCTURE.md)
