/**
 * app.js - 面板主界面初始化、全局状态
 * 只在 /panel 页面加载，此时已通过服务端 JWT 验证
 */

const App = {
    _currentView: 'tech-tree',
    _initialized: false,

    /** 应用入口（面板页面加载时调用） */
    async start() {
        // 面板页已由服务端验证 token，这里做一次客户端 token 检查
        if (!Api._token) {
            window.location.href = '/';
            return;
        }

        // 验证 token 有效性
        const verify = await Api.verify();
        if (!verify.ok) {
            Api.clearToken();
            window.location.href = '/';
            return;
        }

        // 进入主界面
        this.showPage('main');
        await this._initMain();
    },

    /** 显示指定页面，隐藏其他 */
    showPage(name) {
        document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
        const page = document.getElementById(`page-${name}`);
        if (page) page.classList.remove('hidden');
    },

    /** 切换主界面视图 */
    showView(name) {
        this._currentView = name;
        document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
        const view = document.getElementById(`view-${name}`);
        if (view) view.classList.remove('hidden');

        // 更新导航高亮
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        const nav = document.querySelector(`.nav-item[data-view="${name}"]`);
        if (nav) nav.classList.add('active');

        // 按需初始化视图
        this._activateView(name);
    },

    /** 激活视图时加载数据 */
    async _activateView(name) {
        // 切换视图时销毁需要清理的模块
        if (name !== 'charts') Charts.destroy();
        if (name !== 'sessions') SessionMgr.destroy();
        if (name !== 'tech-tree' && typeof TechTree !== 'undefined') TechTree.closeAllFloaters();

        switch (name) {
            case 'tech-tree':
                if (!this._initialized) {
                    await TechTree.init();
                    this._initialized = true;
                }
                break;
            case 'charts':
                await Charts.init();
                break;
            case 'sessions':
                await SessionMgr.init();
                break;
            case 'commands':
                this._renderCommands();
                break;
            case 'access-log':
                this._renderAccessLog();
                break;
            case 'settings':
                this._renderSettings();
                break;
            case 'files':
                this._renderFileBrowser();
                break;
        }
    },

    /** 初始化主界面 */
    async _initMain() {
        // 侧边栏导航
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const view = item.dataset.view;
                if (view) this.showView(view);
            });
        });

        // 退出登录
        const btnLogout = document.getElementById('btn-logout');
        if (btnLogout) {
            btnLogout.addEventListener('click', async () => {
                await Api.logout();
                Api.clearToken();
                window.location.href = '/';
            });
        }

        // 反馈BUG
        const btnFeedback = document.getElementById('btn-feedback');
        if (btnFeedback) {
            btnFeedback.addEventListener('click', async () => {
                const action = await Utils.feedbackDialog();
                if (action === 'github') {
                    window.open('https://github.com/Him666233/astrbot_plugin_group_chat_plus/issues', '_blank');
                } else if (action === 'group') {
                    Utils.alert('测试群聊号码：QQ群 1021544792');
                }
                // 如果action是'cancel'，则什么都不做
            });
        }

        // 初始化主题切换
        const themeBtn = document.getElementById('btn-theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('gcp_theme', newTheme);
                themeBtn.textContent = newTheme === 'light' ? '🌙 切换深色' : '☀️ 切换浅色';
                window.dispatchEvent(new Event('themeChanged'));
            });
            // 初始按钮文本
            const savedTheme = localStorage.getItem('gcp_theme') || 'dark';
            themeBtn.textContent = savedTheme === 'light' ? '🌙 切换深色' : '☀️ 切换浅色';
        }

        // 初始化默认视图
        await this._activateView(this._currentView);
    },

    // ===================== 指令执行视图 =====================

    /** 渲染指令执行视图 */
    async _renderCommands() {
        const container = document.getElementById('commands-container');
        if (!container) return;
        container.innerHTML = '';
        container.style.cssText = 'padding:24px;display:flex;flex-direction:column;gap:16px;overflow-y:auto;';

        // 加载会话列表（供 reset-here 使用）
        const sessRes = await Api.sessionList();
        const sessions = sessRes.ok ? Object.keys(sessRes.sessions || {}) : [];

        const commands = [
            {
                id: 'reset',
                name: '全局重置 (gcp_reset)',
                desc: '重置所有插件数据（注意力、情绪、概率等运行时状态）。不影响聊天记录和配置文件。',
                icon: '🔄',
                color: 'orange',
                exec: async (mode) => {
                    const ok = await Utils.confirm('确认重置所有插件运行时数据？');
                    if (!ok) return;
                    return await Api.cmdReset(mode);
                }
            },
            {
                id: 'reset-here',
                name: '会话重置 (gcp_reset_here)',
                desc: '重置指定会话的插件数据和聊天记录。选择要重置的会话后执行。',
                icon: '🎯',
                color: 'blue',
                needSession: true,
                exec: async (mode, sessionId) => {
                    if (!sessionId) { Utils.toast('请选择要重置的会话', 'warning'); return; }
                    const ok = await Utils.confirm(`确认重置会话「${sessionId}」的数据？`);
                    if (!ok) return;
                    return await Api.cmdResetHere(sessionId, mode);
                }
            },
            {
                id: 'clear-cache',
                name: '清除图片缓存 (gcp_clear_image_cache)',
                desc: '清除所有图片描述的本地缓存。下次遇到相同图片时会重新调用 AI 生成描述。',
                icon: '🗑️',
                color: 'red',
                exec: async (mode) => {
                    const ok = await Utils.confirm('确认清除所有图片描述缓存？');
                    if (!ok) return;
                    return await Api.cmdClearImageCache(mode);
                }
            }
        ];

        commands.forEach(cmd => {
            const card = document.createElement('div');
            card.className = 'cmd-card';

            let sessionSelect = '';
            if (cmd.needSession) {
                const opts = sessions.map(s =>
                    `<option value="${Utils.escapeHtml(s)}">${Utils.escapeHtml(s)}</option>`
                ).join('');
                sessionSelect = `
                    <div class="cmd-field">
                        <label>选择会话</label>
                        <select id="cmd-session-${cmd.id}" class="select-sm" style="width:100%;">
                            <option value="">请选择...</option>
                            ${opts}
                        </select>
                    </div>`;
            }

            card.innerHTML = `
                <div class="cmd-card-header">
                    <span class="cmd-icon">${cmd.icon}</span>
                    <span class="cmd-name">${cmd.name}</span>
                </div>
                <p class="cmd-desc">${cmd.desc}</p>
                ${sessionSelect}
                <div class="cmd-actions">
                    <div class="cmd-field">
                        <label>重启模式</label>
                        <select id="cmd-mode-${cmd.id}" class="select-sm">
                            <option value="reload">仅重载插件</option>
                            <option value="restart">重启整个 AstrBot</option>
                        </select>
                    </div>
                    <button class="btn btn-primary btn-sm" id="cmd-exec-${cmd.id}">执行</button>
                </div>`;

            container.appendChild(card);

            // 绑定执行按钮
            const execBtn = document.getElementById(`cmd-exec-${cmd.id}`);
            execBtn.addEventListener('click', async () => {
                const mode = document.getElementById(`cmd-mode-${cmd.id}`).value;
                const sessionId = cmd.needSession
                    ? document.getElementById(`cmd-session-${cmd.id}`).value
                    : null;
                execBtn.disabled = true;
                execBtn.textContent = '执行中...';
                try {
                    const res = await cmd.exec(mode, sessionId);
                    if (res) {
                        if (res.ok) {
                            Utils.toast(res.msg || '执行成功', 'success');
                        } else {
                            Utils.toast(res.msg || '执行失败', 'error');
                        }
                    }
                } catch (e) {
                    Utils.toast(`执行异常: ${e.message}`, 'error');
                }
                execBtn.disabled = false;
                execBtn.textContent = '执行';
            });
        });
    },

    // ===================== 访问日志视图 =====================

    _accessLogPage: 1,
    _accessLogSize: 50,

    /** 渲染访问日志视图 */
    async _renderAccessLog() {
        const container = document.getElementById('access-log-container');
        if (!container) return;
        container.innerHTML = '';
        container.style.cssText = 'padding:24px;overflow-y:auto;display:flex;flex-direction:column;gap:16px;';

        // 封禁管理区
        const banSection = document.createElement('div');
        banSection.className = 'log-section';
        banSection.innerHTML = `
            <div class="log-section-header">
                <h3>IP 封禁管理</h3>
                <button class="btn btn-sm btn-danger" id="btn-ban-new">封禁 IP</button>
            </div>
            <div id="ban-list-container"></div>`;
        container.appendChild(banSection);

        // 访问日志区
        const logSection = document.createElement('div');
        logSection.className = 'log-section';
        logSection.style.flex = '1';
        logSection.innerHTML = `
            <div class="log-section-header">
                <h3>访问日志</h3>
                <button class="btn btn-sm" id="btn-refresh-log">刷新</button>
            </div>
            <div id="log-table-container"></div>
            <div id="log-pagination"></div>`;
        container.appendChild(logSection);

        // 绑定事件
        document.getElementById('btn-ban-new').addEventListener('click', () => this._showBanDialog());
        document.getElementById('btn-refresh-log').addEventListener('click', () => this._loadAccessLog());

        // 加载数据
        await Promise.all([this._loadBanList(), this._loadAccessLog()]);
    },

    /** 加载封禁列表 */
    async _loadBanList() {
        const container = document.getElementById('ban-list-container');
        if (!container) return;
        const res = await Api.getBans();
        if (!res.ok) {
            container.innerHTML = '<div class="chart-empty">加载失败</div>';
            return;
        }
        const bans = res.bans || [];
        if (!bans.length) {
            container.innerHTML = '<div class="chart-empty" style="padding:12px;">暂无封禁记录</div>';
            return;
        }
        container.innerHTML = '';
        const table = document.createElement('table');
        table.className = 'log-table';
        table.innerHTML = `<thead><tr>
            <th>IP</th><th>来源</th><th>原因</th><th>封禁时间</th><th>剩余时间</th><th>操作</th>
        </tr></thead>`;
        const tbody = document.createElement('tbody');
        bans.forEach(ban => {
            const tr = document.createElement('tr');
            const remaining = ban.remaining_seconds === null
                ? '永久' : Utils.formatDuration(ban.remaining_seconds);
            // 判断封禁来源（防爬虫自动 / 手动）
            const isSpider = ban.reason && ban.reason.startsWith('[防爬虫]');
            const sourceBadge = isSpider
                ? '<span style="font-size:11px;background:rgba(224,32,32,0.15);color:var(--accent-red);border:1px solid rgba(224,32,32,0.35);border-radius:3px;padding:1px 5px;">🕷️ 自动</span>'
                : '<span style="font-size:11px;background:var(--glass-bg-hover);color:var(--text-secondary);border:1px solid var(--glass-border);border-radius:3px;padding:1px 5px;">👤 手动</span>';
            const displayReason = Utils.escapeHtml(ban.reason || '');
            tr.innerHTML = `
                <td style="font-family:monospace;">${Utils.escapeHtml(ban.ip)}</td>
                <td>${sourceBadge}</td>
                <td title="${displayReason}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${displayReason}</td>
                <td>${Utils.formatTime(ban.banned_at)}</td>
                <td>${remaining}</td>
                <td><button class="btn btn-sm" data-unban="${Utils.escapeHtml(ban.ip)}">解封</button></td>`;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        container.appendChild(table);

        // 解封按钮事件
        container.querySelectorAll('[data-unban]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const ip = btn.dataset.unban;
                const ok = await Utils.confirm(`确认解封 IP: ${ip}？`);
                if (!ok) return;
                const res = await Api.unbanIp(ip);
                if (res.ok) {
                    Utils.toast(res.msg || '已解封', 'success');
                    await this._loadBanList();
                } else {
                    Utils.toast(res.msg || '解封失败', 'error');
                }
            });
        });
    },

    /** 加载访问日志 */
    async _loadAccessLog() {
        const container = document.getElementById('log-table-container');
        if (!container) return;
        container.innerHTML = '<div class="chart-empty">加载中...</div>';

        const res = await Api.getAccessLog(this._accessLogPage, this._accessLogSize);
        if (!res.ok) {
            container.innerHTML = '<div class="chart-empty">加载失败</div>';
            return;
        }

        const logs = res.logs || [];
        const total = res.total || 0;

        if (!logs.length) {
            container.innerHTML = '<div class="chart-empty">暂无访问记录</div>';
            this._renderPagination(0, 0);
            return;
        }

        container.innerHTML = '';
        const table = document.createElement('table');
        table.className = 'log-table';
        table.innerHTML = `<thead><tr>
            <th>时间</th><th>IP</th><th>方法</th><th>路径</th><th>状态</th><th>附注</th><th>操作</th>
        </tr></thead>`;
        const tbody = document.createElement('tbody');
        logs.forEach(log => {
            const tr = document.createElement('tr');
            const statusClass = log.status >= 400 ? 'status-error' :
                                log.status >= 300 ? 'status-warn' : 'status-ok';

            // 附注渲染：防爬虫自动封禁事件使用橙色高亮标签
            let noteHtml = '';
            if (log.note) {
                if (log.note.includes('[防爬虫自动封禁]')) {
                    noteHtml = `<span class="log-note-spider" title="${Utils.escapeHtml(log.note)}"
                        style="font-size:11px;background:rgba(224,32,32,0.15);color:var(--accent-red);
                        border:1px solid rgba(224,32,32,0.35);border-radius:3px;padding:2px 6px;
                        white-space:nowrap;display:inline-block;">
                        🕷️ ${Utils.escapeHtml(log.note.slice(0, 40))}${log.note.length > 40 ? '…' : ''}
                    </span>`;
                } else {
                    noteHtml = `<span class="log-note" title="${Utils.escapeHtml(log.note)}">${Utils.escapeHtml(log.note.slice(0, 30))}${log.note.length > 30 ? '…' : ''}</span>`;
                }
            }

            tr.innerHTML = `
                <td>${Utils.formatTime(log.timestamp)}</td>
                <td style="font-family:monospace;">${Utils.escapeHtml(log.ip)}</td>
                <td>${Utils.escapeHtml(log.method)}</td>
                <td class="log-path">${Utils.escapeHtml(log.path)}</td>
                <td><span class="status-badge ${statusClass}">${log.status}</span></td>
                <td>${noteHtml}</td>
                <td><button class="btn btn-sm btn-danger" data-ban-ip="${Utils.escapeHtml(log.ip)}">封禁</button></td>`;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        container.appendChild(table);

        // 封禁按钮事件
        container.querySelectorAll('[data-ban-ip]').forEach(btn => {
            btn.addEventListener('click', () => this._showBanDialog(btn.dataset.banIp));
        });

        this._renderPagination(total, this._accessLogPage);
    },

    /** 渲染分页控件 */
    _renderPagination(total, currentPage) {
        const container = document.getElementById('log-pagination');
        if (!container) return;
        const totalPages = Math.ceil(total / this._accessLogSize);
        if (totalPages <= 1) { container.innerHTML = ''; return; }

        container.innerHTML = '';
        container.className = 'log-pagination';

        const info = document.createElement('span');
        info.className = 'page-info';
        info.textContent = `第 ${currentPage}/${totalPages} 页 (共 ${total} 条)`;
        container.appendChild(info);

        const actions = document.createElement('div');
        actions.style.cssText = 'display:flex;gap:4px;';

        if (currentPage > 1) {
            const prev = document.createElement('button');
            prev.className = 'btn btn-sm';
            prev.textContent = '上一页';
            prev.addEventListener('click', () => {
                this._accessLogPage--;
                this._loadAccessLog();
            });
            actions.appendChild(prev);
        }
        if (currentPage < totalPages) {
            const next = document.createElement('button');
            next.className = 'btn btn-sm';
            next.textContent = '下一页';
            next.addEventListener('click', () => {
                this._accessLogPage++;
                this._loadAccessLog();
            });
            actions.appendChild(next);
        }
        container.appendChild(actions);
    },

    /** 显示封禁 IP 弹窗 */
    _showBanDialog(ip = '') {
        const overlay = document.createElement('div');
        overlay.className = 'confirm-overlay';
        overlay.innerHTML = `
            <div class="confirm-box" style="width:360px;">
                <h3 style="margin-bottom:12px;">封禁 IP</h3>
                <div style="display:flex;flex-direction:column;gap:8px;">
                    <input type="text" id="ban-ip-input" placeholder="IP 地址" value="${Utils.escapeHtml(ip)}">
                    <input type="text" id="ban-reason-input" placeholder="封禁原因（可选）" value="手动封禁">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <label style="white-space:nowrap;font-size:13px;">封禁时长</label>
                        <select id="ban-duration-select" style="flex:1;">
                            <option value="">永久</option>
                            <option value="300">5 分钟</option>
                            <option value="3600">1 小时</option>
                            <option value="86400">1 天</option>
                            <option value="604800">7 天</option>
                            <option value="custom">自定义（秒）</option>
                        </select>
                    </div>
                    <input type="number" id="ban-custom-duration" class="hidden" placeholder="自定义秒数" min="1">
                </div>
                <div class="confirm-actions" style="margin-top:12px;">
                    <button class="btn" data-action="cancel">取消</button>
                    <button class="btn btn-danger" data-action="ban">确认封禁</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const durationSelect = document.getElementById('ban-duration-select');
        const customInput = document.getElementById('ban-custom-duration');
        durationSelect.addEventListener('change', () => {
            customInput.classList.toggle('hidden', durationSelect.value !== 'custom');
        });

        overlay.addEventListener('click', async (e) => {
            const action = e.target.dataset.action;
            if (action === 'cancel') { overlay.remove(); return; }
            if (action === 'ban') {
                const banIp = document.getElementById('ban-ip-input').value.trim();
                const reason = document.getElementById('ban-reason-input').value.trim() || '手动封禁';
                let duration = null;
                const durVal = durationSelect.value;
                if (durVal === 'custom') {
                    duration = parseInt(customInput.value);
                    if (!duration || duration <= 0) {
                        Utils.toast('请输入有效的封禁秒数', 'warning');
                        return;
                    }
                } else if (durVal) {
                    duration = parseInt(durVal);
                }
                if (!banIp) { Utils.toast('请输入 IP 地址', 'warning'); return; }

                // 检查是否为受保护 IP 或白名单 IP
                const ipConfigRes = await Api.getIpConfig();
                if (ipConfigRes.ok) {
                    const protectedList = ipConfigRes.protected_ips || [];
                    if (protectedList.includes(banIp)) {
                        Utils.alert(
                            `⚠️ 无法封禁受保护 IP：${banIp}\n\n` +
                            `此 IP 在"受保护 IP"名单中，任何封禁操作对其均无效。\n` +
                            `受保护 IP 拥有最高优先级，不受封禁、黑白名单、防爬虫等任何安全机制限制。\n\n` +
                            `如需调整受保护 IP 名单，请在 AstrBot 插件配置页修改。`
                        );
                        return;
                    }
                    // 检查是否为白名单 IP（白名单模式下封禁无效）
                    const ipMode = ipConfigRes.ip_mode;
                    const ipList = ipConfigRes.ip_list || [];
                    if (ipMode === 'whitelist' && ipList.includes(banIp)) {
                        Utils.alert(
                            `⚠️ 封禁操作对白名单 IP 无效：${banIp}\n\n` +
                            `当前处于「白名单模式」，此 IP 在白名单中，访问时会在黑白名单检查阶段直接放行，\n` +
                            `不会再经过封禁列表检查，因此封禁对白名单 IP 无效。\n\n` +
                            `如需阻止此 IP 访问，请先将其从白名单中移除。`
                        );
                        return;
                    }
                }

                const res = await Api.banIp(banIp, duration, reason);
                if (res.ok) {
                    Utils.toast(res.msg || '已封禁', 'success');
                    overlay.remove();
                    await this._loadBanList();
                } else {
                    // 服务端也会拒绝受保护 IP，直接显示原因
                    Utils.toast(res.msg || '封禁失败', 'error');
                }
            }
        });
    },

    // ===================== 面板设置视图 =====================

    /** 渲染面板设置页 */
    _renderSettings() {
        const container = document.getElementById('settings-container');
        if (!container) return;
        container.innerHTML = '';
        container.style.cssText = 'padding:24px;overflow-y:auto;display:flex;flex-direction:column;gap:24px;';

        // ---- 安全敏感只读区 ----
        const secSection = document.createElement('div');
        secSection.className = 'settings-section';
        secSection.innerHTML = `
            <h3>🔒 安全敏感配置（只读）</h3>
            <div class="security-readonly-banner" style="margin-bottom:12px;">
                <span class="security-readonly-banner-icon">🔒</span>
                <span class="security-readonly-banner-text">
                    以下配置属于安全敏感项，出于安全考虑不允许在 Web 端修改。<br>
                    如需调整，请前往 <strong>AstrBot 平台 → 插件配置</strong> 中对应的传统配置项进行修改。
                </span>
            </div>
            <div id="sec-readonly-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="sec-readonly-content" class="hidden" style="display:flex;flex-direction:column;gap:8px;"></div>`;
        container.appendChild(secSection);
        this._loadSecReadonly();

        // ---- 修改密码区 ----
        const pwSection = document.createElement('div');
        pwSection.className = 'settings-section';
        pwSection.innerHTML = `
            <h3>修改密码</h3>
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 10px;line-height:1.7;">
                密码要求：<strong>6 ~ 128 位</strong>，支持任意可打印字符（字母、数字、符号均可）。<br>
                建议使用包含大小写字母、数字和符号的强密码，避免使用生日、连续数字等易猜内容。<br>
                修改成功后原登录会话将会过期。
            </p>
            <div style="display:flex;flex-direction:column;gap:8px;max-width:300px;">
                <input type="password" id="settings-old-pw" placeholder="当前密码" autocomplete="current-password" maxlength="128">
                <input type="password" id="settings-new-pw" placeholder="新密码（6 ~ 128 位）" autocomplete="new-password" maxlength="128">
                <input type="password" id="settings-confirm-pw" placeholder="确认新密码" autocomplete="new-password" maxlength="128">
                <button class="btn btn-primary btn-sm" id="btn-settings-change-pw">修改密码</button>
                <div id="settings-pw-error" class="error-msg hidden"></div>
            </div>`;
        container.appendChild(pwSection);

        // 绑定修改密码事件
        const btn = document.getElementById('btn-settings-change-pw');
        if (btn) {
            btn.addEventListener('click', async () => {
                const oldPw = document.getElementById('settings-old-pw').value;
                const newPw = document.getElementById('settings-new-pw').value;
                const confirmPw = document.getElementById('settings-confirm-pw').value;
                const errEl = document.getElementById('settings-pw-error');

                if (!oldPw || !newPw) {
                    errEl.textContent = '请填写所有字段';
                    errEl.classList.remove('hidden');
                    return;
                }
                if (newPw.length < 6) {
                    errEl.textContent = '新密码至少 6 位';
                    errEl.classList.remove('hidden');
                    return;
                }
                if (newPw.length > 128) {
                    errEl.textContent = '新密码不能超过 128 位';
                    errEl.classList.remove('hidden');
                    return;
                }
                if (newPw !== confirmPw) {
                    errEl.textContent = '两次密码不一致';
                    errEl.classList.remove('hidden');
                    return;
                }

                const res = await Api.changePassword(oldPw, newPw);
                if (res.ok) {
                    Utils.toast('密码修改成功，请重新登录', 'success');
                    errEl.classList.add('hidden');
                    Api.clearToken();
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    errEl.textContent = res.msg || '修改失败';
                    errEl.classList.remove('hidden');
                }
            });
        }

        // ---- IP 访问控制管理 ----
        const ipSection = document.createElement('div');
        ipSection.className = 'settings-section';
        ipSection.innerHTML = `
            <h3>🔒 IP 访问控制</h3>
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:14px;line-height:1.7;background:rgba(224,32,32,0.05);border:1px solid rgba(224,32,32,0.15);border-radius:8px;padding:12px;">
                <strong style="color:var(--text-primary);display:block;margin-bottom:6px;">IP 访问控制流程</strong>
                <pre style="font-family:monospace;font-size:11px;color:var(--text-secondary);line-height:1.6;margin:0;white-space:pre-wrap;">
请求进入
   │
   ▼
① 受保护 IP？──是──→ ✅ 永远放行（最高优先级）
   │ 否
   ▼
② 黑名单模式且命中？──是──→ ❌ 拒绝访问
   │ 否（disabled / blacklist未命中）
   │ 白名单模式且命中？──是──→ ✅ 放行（跳过封禁检查）
   │ 否（不在白名单内）──→ ❌ 拒绝访问
   ▼（disabled 或 blacklist 未命中）
③ 封禁列表检查（手动封禁 + 防爬虫自动封禁）──命中──→ ❌ 拒绝
   │ 未命中
   ▼
④ 防爬虫实时检测──触发──→ 写入封禁列表 → ❌ 拒绝
   │ 未触发
   ▼
⑤ JWT 登录认证 → ✅ 正常处理</pre>
                <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(224,32,32,0.15);">
                    ⚠️ <strong>重要：</strong>白名单模式下，白名单中的 IP 在②步直接放行，
                    不再检查封禁列表，因此手动封禁或防爬虫自动封禁对白名单 IP <strong>无效</strong>。
                </div>
                <div style="margin-top:6px;">
                    📌 修改后需点击「<strong>保存并重启插件</strong>」，重启完成后生效（与传统配置项行为一致）。
                </div>
            </div>
            <div id="ip-config-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="ip-config-content" class="hidden">
                <div style="display:flex;flex-direction:column;gap:12px;max-width:500px;">
                    <div>
                        <label style="font-size:13px;font-weight:600;margin-bottom:4px;display:block;">访问模式</label>
                        <select id="ip-mode-select" style="width:100%;">
                            <option value="disabled">关闭（不过滤，所有 IP 均可访问）</option>
                            <option value="whitelist">白名单模式（仅允许列表中的 IP 访问）</option>
                            <option value="blacklist">黑名单模式（阻止列表中的 IP 访问）</option>
                        </select>
                    </div>
                    <div id="ip-list-section">
                        <label style="font-size:13px;font-weight:600;margin-bottom:4px;display:block;">
                            <span id="ip-list-label">IP 名单</span>
                            <span style="font-weight:normal;color:var(--text-secondary);">（每行一个 IP 地址）</span>
                        </label>
                        <textarea id="ip-list-textarea" rows="5" style="width:100%;font-family:monospace;font-size:13px;" placeholder="每行一个 IP 地址"></textarea>
                    </div>
                    <div>
                        <label style="font-size:13px;font-weight:600;margin-bottom:4px;display:block;">
                            受保护 IP
                            <span style="font-weight:normal;color:var(--text-muted);"> （只读，仅可通过 AstrBot 传统配置修改）</span>
                        </label>
                        <div id="protected-ips-display" style="font-family:monospace;font-size:13px;padding:8px;background:var(--bg-input);border:1px solid var(--border-color);border-radius:var(--radius-sm);min-height:48px;color:var(--text-secondary);white-space:pre-wrap;"></div>
                        <div style="font-size:11px;color:var(--accent-red);margin-top:4px;">
                            ⚠️ 受保护 IP 是底线安全配置（最高优先级，不受任何机制影响），防止 Web 面板被攻破后攻击者篡改。
                            如需修改，请在 AstrBot 插件配置页修改 <code>web_panel_protected_ips</code>。
                        </div>
                    </div>
                    <div>
                        <label style="font-size:13px;font-weight:600;margin-bottom:4px;display:block;">
                            登录 IP 绑定校验（防劫持）
                            <span style="font-weight:normal;color:var(--text-muted);"> （只读，仅可通过 AstrBot 传统配置修改）</span>
                        </label>
                        <div id="ip-bind-check-display" style="font-family:monospace;font-size:13px;padding:8px;background:var(--bg-input);border:1px solid var(--border-color);border-radius:var(--radius-sm);color:var(--text-secondary);"></div>
                        <div style="font-size:11px;color:var(--text-secondary);margin-top:4px;">
                            开启后，登录时将 IP 绑定到令牌中，IP 变化时令牌立即失效并要求重新登录。可防止令牌被劫持后在其他网络使用。
                            若您的网络 IP 经常变化（移动网络、动态代理等），可在 AstrBot 插件配置页将 <code>web_panel_ip_bind_check</code> 设为关闭。
                        </div>
                    </div>
                    <div style="display:flex;gap:8px;align-items:center;">
                        <button class="btn btn-primary btn-sm" id="btn-save-ip-config">保存并重启插件</button>
                        <span id="ip-config-status" style="font-size:12px;color:var(--text-secondary);"></span>
                    </div>
                </div>
            </div>`;
        container.appendChild(ipSection);

        // 加载 IP 配置
        this._loadIpConfig();

        // 模式切换时更新标签文字
        const modeSelect = document.getElementById('ip-mode-select');
        if (modeSelect) {
            modeSelect.addEventListener('change', () => {
                this._updateIpListLabel(modeSelect.value);
            });
        }

        // 保存并重启按钮：先写入配置，再触发插件重载
        const saveIpBtn = document.getElementById('btn-save-ip-config');
        if (saveIpBtn) {
            saveIpBtn.addEventListener('click', async () => {
                const mode = document.getElementById('ip-mode-select').value;
                const ipListRaw = document.getElementById('ip-list-textarea').value;
                const statusEl = document.getElementById('ip-config-status');

                const ipList = ipListRaw.split('\n').map(s => s.trim()).filter(Boolean);

                saveIpBtn.disabled = true;
                saveIpBtn.textContent = '保存中...';
                statusEl.textContent = '';

                // 先写入配置文件
                const saveRes = await Api.putIpConfig({
                    ip_mode: mode,
                    ip_list: ipList,
                });

                if (!saveRes.ok) {
                    saveIpBtn.disabled = false;
                    saveIpBtn.textContent = '保存并重启插件';
                    Utils.toast(saveRes.msg || '保存失败', 'error');
                    statusEl.textContent = '保存失败';
                    statusEl.style.color = 'var(--danger)';
                    return;
                }

                // 配置写入成功，触发插件重载（保持登录态）
                saveIpBtn.textContent = '重启中...';
                statusEl.textContent = '正在重启插件...';
                const reloadRes = await Api.reloadPlugin();
                saveIpBtn.disabled = false;
                saveIpBtn.textContent = '保存并重启插件';
                if (reloadRes && reloadRes.ok) {
                    Utils.toast('IP 配置已保存，插件正在重启，请稍后刷新页面...', 'success');
                    statusEl.textContent = '重启中...';
                    statusEl.style.color = 'var(--accent)';
                } else {
                    Utils.toast('配置已保存，但触发重启失败，请手动重启插件', 'warning');
                    statusEl.textContent = '请手动重启';
                    statusEl.style.color = 'var(--accent-orange)';
                }
            });
        }

        // ---- Web 面板可调配置区 ----
        const webCfgSection = document.createElement('div');
        webCfgSection.className = 'settings-section';
        webCfgSection.innerHTML = `
            <h3>Web 面板运行配置</h3>
            <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;">
                以下配置修改后需 <strong>保存并重启插件</strong> 才能生效。
            </p>
            <div id="webcfg-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="webcfg-content" class="hidden" style="display:flex;flex-direction:column;gap:16px;max-width:500px;"></div>`;
        container.appendChild(webCfgSection);
        this._loadWebCfg();

        // ---- 说明区 ----
        const infoSection = document.createElement('div');
        infoSection.className = 'settings-section';
        infoSection.innerHTML = `
            <h3>安全配置说明</h3>
            <p style="font-size:13px;color:var(--text-secondary);line-height:1.8;">
                <strong>IP 访问控制（黑白名单）</strong>修改后需点击「保存并重启插件」，重启完成后生效，与传统配置项行为一致。<br>
                <br>
                - <strong>关闭模式</strong>：不做 IP 过滤，任何 IP 均可访问<br>
                - <strong>白名单模式</strong>：仅名单中的 IP 可访问面板（白名单 IP 直接放行，不受封禁影响）<br>
                - <strong>黑名单模式</strong>：名单中的 IP 被阻止访问（未在黑名单内的 IP 仍受封禁检查约束）<br>
                - <strong>受保护 IP</strong>：优先级最高，永远放行，不受任何机制影响。<strong>只能通过 AstrBot 传统配置修改</strong>，防止面板被攻破后遭篡改<br>
                <br>
                <strong>总开关 / 端口 / 监听地址 / 密码重置</strong>：这些配置出于安全考虑只能通过 AstrBot 插件配置页修改，上方「安全敏感配置」区展示了其当前值供参考。<br>
                <br>
                <strong>日志清理 / 防爬虫 / 信任反向代理</strong>：在「Web 面板运行配置」区可直接修改，修改后需保存并重启插件。
            </p>`;
        container.appendChild(infoSection);
    },

    /** 加载安全敏感只读项（总开关/端口/监听地址/密码重置） */
    async _loadSecReadonly() {
        const loading = document.getElementById('sec-readonly-loading');
        const content = document.getElementById('sec-readonly-content');
        if (!loading || !content) return;

        const res = await Api.getConfig();
        if (!res.ok) {
            loading.textContent = '加载失败';
            return;
        }

        loading.classList.add('hidden');
        content.classList.remove('hidden');
        content.style.display = 'flex';

        const cfg = res.config || {};
        const schema = res.schema || {};

        const readonlyKeys = [
            'enable_web_panel',
            'web_panel_port',
            'web_panel_host',
            'web_panel_reset_password',
        ];

        readonlyKeys.forEach(key => {
            const s = schema[key];
            if (!s) return;
            const row = document.createElement('div');
            row.className = 'config-field config-field-readonly';
            row.style.maxWidth = '500px';
            const val = key in cfg ? cfg[key] : (s.default !== undefined ? s.default : '—');
            const displayVal = typeof val === 'boolean'
                ? (val ? '已开启' : '已关闭')
                : (val === '' ? '（空）' : String(val));
            const desc = (s.description || key).replace(/^[^\s]+\s/, '');
            row.innerHTML = `
                <div class="config-field-label">🔒 ${desc}</div>
                <div class="config-field-readonly-value">当前值：${displayVal}</div>
                <div class="config-field-readonly-note">⚠️ 此项为安全敏感配置，请在 AstrBot 平台插件配置页修改</div>`;
            content.appendChild(row);
        });
    },

    /** 加载 Web 面板可调配置（日志清理、防爬虫、信任代理） */
    async _loadWebCfg() {
        const loading = document.getElementById('webcfg-loading');
        const content = document.getElementById('webcfg-content');
        if (!loading || !content) return;

        const res = await Api.getConfig();
        if (!res.ok) {
            loading.textContent = '加载失败';
            return;
        }

        loading.classList.add('hidden');
        content.classList.remove('hidden');

        const cfg = res.config || {};
        const schema = res.schema || {};

        // 可调项定义（key → 覆盖标签，留空则用 schema.description）
        const editableKeys = [
            'web_panel_trust_proxy',
            'web_panel_log_auto_clean',
            'web_panel_log_retention_days',
            'web_panel_log_clean_interval_hours',
            'web_panel_anti_spider',
            'web_panel_anti_spider_rate_limit',
            'web_panel_anti_spider_ban_duration',
        ];

        const pending = {};

        editableKeys.forEach(key => {
            const s = schema[key];
            if (!s) return;
            let val = key in cfg ? cfg[key] : (s.default !== undefined ? s.default : null);

            const row = document.createElement('div');
            row.className = 'config-field';
            row.style.paddingBottom = '12px';
            row.style.borderBottom = '1px solid var(--border-color)';

            const desc = (s.description || key).replace(/^[^\s]+\s/, '');
            const label = document.createElement('div');
            label.className = 'config-field-label';
            label.textContent = desc;
            row.appendChild(label);

            if (s.hint) {
                const hint = document.createElement('div');
                hint.className = 'config-field-hint';
                hint.textContent = s.hint;
                row.appendChild(hint);
                requestAnimationFrame(() => {
                    const lh = parseFloat(getComputedStyle(hint).lineHeight) || 16;
                    if (hint.scrollHeight <= lh * 4 + 4) {
                        hint.classList.add('short');
                    } else {
                        hint.classList.add('collapsible');
                        const fullHeight = hint.scrollHeight;
                        const btn = document.createElement('span');
                        btn.className = 'collapse-toggle';
                        btn.textContent = '▼ 展开';
                        hint.parentNode.insertBefore(btn, hint.nextSibling);
                        btn.addEventListener('click', () => {
                            if (hint.classList.contains('expanded')) {
                                hint.style.maxHeight = hint.scrollHeight + 'px';
                                hint.getBoundingClientRect();
                                hint.classList.remove('expanded');
                                hint.style.maxHeight = '';
                                btn.textContent = '▼ 展开';
                            } else {
                                hint.classList.add('expanded');
                                hint.style.maxHeight = fullHeight + 'px';
                                btn.textContent = '▲ 收起';
                            }
                        });
                        hint.addEventListener('click', () => btn.click());
                    }
                });
            }

            // 控件
            if (s.type === 'bool') {
                const wrap = document.createElement('div');
                wrap.className = 'toggle-wrap';
                const lbl = document.createElement('label');
                lbl.className = 'toggle';
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = !!val;
                input.addEventListener('change', () => { pending[key] = input.checked; });
                const slider = document.createElement('span');
                slider.className = 'toggle-slider';
                lbl.appendChild(input);
                lbl.appendChild(slider);
                wrap.appendChild(lbl);
                row.appendChild(wrap);
            } else if (s.type === 'int' || s.type === 'float') {
                const wrap = document.createElement('div');
                wrap.className = 'number-input-wrap';
                const input = document.createElement('input');
                input.type = 'number';
                input.value = val !== null ? val : '';
                if (s.type === 'float') input.step = '0.01';
                input.addEventListener('change', () => {
                    const v = s.type === 'int' ? parseInt(input.value) : parseFloat(input.value);
                    if (!isNaN(v)) pending[key] = v;
                });
                wrap.appendChild(input);
                row.appendChild(wrap);
            }

            const def = document.createElement('div');
            def.className = 'config-field-default';
            def.textContent = `默认: ${s.default}`;
            row.appendChild(def);

            content.appendChild(row);
        });

        // 保存按钮
        const saveRow = document.createElement('div');
        saveRow.style.cssText = 'display:flex;gap:8px;align-items:center;margin-top:4px;';
        saveRow.innerHTML = `
            <button class="btn btn-primary btn-sm" id="btn-save-webcfg">保存并重启插件</button>
            <span id="webcfg-status" style="font-size:12px;color:var(--text-secondary);"></span>`;
        content.appendChild(saveRow);

        document.getElementById('btn-save-webcfg').addEventListener('click', async () => {
            if (!Object.keys(pending).length) {
                Utils.toast('没有修改任何配置', 'warning');
                return;
            }
            const saveBtn = document.getElementById('btn-save-webcfg');
            const statusEl = document.getElementById('webcfg-status');
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
            statusEl.textContent = '';

            const merged = { ...cfg, ...pending };
            const res = await Api.reloadPlugin(merged);
            saveBtn.disabled = false;
            saveBtn.textContent = '保存并重启插件';

            if (res.ok) {
                Utils.toast('已保存，插件重启成功', 'success');
                statusEl.textContent = '已保存';
                Object.assign(cfg, pending);
                Object.keys(pending).forEach(k => delete pending[k]);
            } else {
                Utils.toast(res.msg || '保存失败', 'error');
                statusEl.textContent = '保存失败';
            }
        });
    },

    /** 加载 IP 访问控制配置 */
    async _loadIpConfig() {
        const loading = document.getElementById('ip-config-loading');
        const content = document.getElementById('ip-config-content');
        if (!loading || !content) return;

        const res = await Api.getIpConfig();
        if (!res.ok) {
            loading.textContent = '加载 IP 配置失败';
            return;
        }

        loading.classList.add('hidden');
        content.classList.remove('hidden');

        const modeSelect = document.getElementById('ip-mode-select');
        modeSelect.value = res.ip_mode || 'disabled';
        this._updateIpListLabel(modeSelect.value);

        document.getElementById('ip-list-textarea').value =
            (res.ip_list || []).join('\n');
        const protectedDisplay = document.getElementById('protected-ips-display');
        if (protectedDisplay) {
            const list = res.protected_ips || [];
            protectedDisplay.textContent = list.length ? list.join('\n') : '（未配置）';
        }
        const ipBindDisplay = document.getElementById('ip-bind-check-display');
        if (ipBindDisplay) {
            const enabled = res.ip_bind_check !== false;
            ipBindDisplay.textContent = enabled ? '已开启（IP 变化时令牌失效）' : '已关闭（允许 IP 变化）';
            ipBindDisplay.style.color = enabled ? 'var(--accent-green, #22c55e)' : 'var(--accent-orange, #f59e0b)';
        }
    },

    // ===================== 文件浏览器视图 =====================

    _fileEditorDirty: false,
    _currentFilePath: null,

    /** 渲染文件浏览器 */
    async _renderFileBrowser() {
        const container = document.getElementById('files-container');
        if (!container) return;
        container.innerHTML = '';
        container.style.cssText = 'padding:24px;display:flex;gap:16px;height:100%;overflow:hidden;';

        // 左侧：文件列表
        const listPanel = document.createElement('div');
        listPanel.className = 'file-list-panel';
        listPanel.innerHTML = `
            <div class="file-list-header">
                <h3 style="margin:0;font-size:14px;">数据文件</h3>
                <button class="btn btn-sm" id="btn-refresh-files">刷新</button>
            </div>
            <div id="file-tree" class="file-tree"></div>`;
        container.appendChild(listPanel);

        // 右侧：文件内容编辑器
        const editorPanel = document.createElement('div');
        editorPanel.className = 'file-editor-panel';
        editorPanel.innerHTML = `
            <div class="file-editor-header">
                <span id="file-editor-title" style="font-size:14px;font-weight:600;">选择文件查看内容</span>
                <div id="file-editor-actions" class="hidden" style="display:flex;gap:6px;">
                    <span id="file-editor-size" style="font-size:12px;color:var(--text-secondary);align-self:center;"></span>
                    <button class="btn btn-sm btn-primary" id="btn-save-file">保存</button>
                    <button class="btn btn-sm btn-danger" id="btn-delete-file">删除</button>
                </div>
            </div>
            <div id="file-editor-content" class="file-editor-content">
                <div class="chart-empty" style="margin:auto;">选择左侧文件查看内容</div>
            </div>`;
        container.appendChild(editorPanel);

        // 事件绑定
        document.getElementById('btn-refresh-files').addEventListener('click', () => this._loadFileList());
        document.getElementById('btn-save-file').addEventListener('click', () => this._saveCurrentFile());
        document.getElementById('btn-delete-file').addEventListener('click', () => this._deleteCurrentFile());

        await this._loadFileList();
    },

    /** 加载文件列表 */
    async _loadFileList() {
        const tree = document.getElementById('file-tree');
        if (!tree) return;
        tree.innerHTML = '<div class="chart-empty" style="padding:12px;">加载中...</div>';

        const res = await Api.fileList();
        if (!res.ok) {
            tree.innerHTML = '<div class="chart-empty" style="padding:12px;">加载失败</div>';
            return;
        }

        const files = res.files || [];
        if (!files.length) {
            tree.innerHTML = '<div class="chart-empty" style="padding:12px;">暂无数据文件</div>';
            return;
        }

        // 按目录分组
        const groups = {};
        files.forEach(f => {
            const dir = f.directory || '根目录';
            if (!groups[dir]) groups[dir] = [];
            groups[dir].push(f);
        });

        tree.innerHTML = '';
        const sortedDirs = Object.keys(groups).sort();
        sortedDirs.forEach(dir => {
            const dirEl = document.createElement('div');
            dirEl.className = 'file-group';

            const dirHeader = document.createElement('div');
            dirHeader.className = 'file-group-header';
            dirHeader.textContent = dir === '根目录' ? '/' : dir + '/';
            dirHeader.addEventListener('click', () => {
                dirEl.classList.toggle('collapsed');
            });
            dirEl.appendChild(dirHeader);

            const filesList = document.createElement('div');
            filesList.className = 'file-group-items';
            groups[dir].sort((a, b) => a.name.localeCompare(b.name)).forEach(f => {
                const item = document.createElement('div');
                item.className = 'file-item';
                if (f.protected) item.classList.add('file-protected');
                if (this._currentFilePath === f.path) item.classList.add('active');
                const icon = f.protected ? '🔒' : f.is_json ? '{}' : '📄';
                item.innerHTML = `
                    <span class="file-icon">${icon}</span>
                    <span class="file-name" title="${Utils.escapeHtml(f.path)}">${Utils.escapeHtml(f.name)}</span>
                    <span class="file-size">${Utils.formatSize(f.size)}</span>`;
                item.addEventListener('click', () => this._openFile(f.path, f.protected));
                filesList.appendChild(item);
            });
            dirEl.appendChild(filesList);
            tree.appendChild(dirEl);
        });
    },

    /** 打开文件 */
    async _openFile(path, isProtected) {
        if (this._fileEditorDirty) {
            const ok = await Utils.confirm('当前文件有未保存的修改，确定放弃？');
            if (!ok) return;
        }

        this._currentFilePath = path;
        this._fileEditorDirty = false;
        const content = document.getElementById('file-editor-content');
        const title = document.getElementById('file-editor-title');
        const actions = document.getElementById('file-editor-actions');
        const sizeEl = document.getElementById('file-editor-size');

        title.textContent = path;

        // 高亮当前文件
        document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.file-item').forEach(el => {
            if (el.querySelector('.file-name')?.title === path) {
                el.classList.add('active');
            }
        });

        // 敏感文件：不请求内容，直接显示提示
        if (isProtected) {
            actions.classList.add('hidden');
            content.innerHTML = `<div class="chart-empty" style="margin:auto;text-align:center;line-height:1.8;">
                <div style="font-size:32px;margin-bottom:8px;">🔒</div>
                <div style="font-weight:600;">此文件包含敏感凭据信息</div>
                <div style="color:var(--text-secondary);font-size:13px;">出于安全考虑，不支持在线查看、编辑或删除。<br>如需查看，请前往服务器本地对应目录手动打开。</div>
            </div>`;
            return;
        }

        content.innerHTML = '<div class="chart-empty" style="margin:auto;">加载中...</div>';

        const res = await Api.fileRead(path);
        if (!res.ok) {
            content.innerHTML = `<div class="chart-empty" style="margin:auto;">${Utils.escapeHtml(res.msg || '读取失败')}</div>`;
            actions.classList.add('hidden');
            return;
        }

        actions.classList.remove('hidden');
        actions.style.display = 'flex';
        sizeEl.textContent = Utils.formatSize(res.content.length);

        // 判断是否可编辑（JSON 文件）
        const isEditable = res.is_json;
        const saveBtn = document.getElementById('btn-save-file');
        saveBtn.classList.toggle('hidden', !isEditable);

        content.innerHTML = '';
        const textarea = document.createElement('textarea');
        textarea.className = 'file-textarea';
        textarea.spellcheck = false;
        textarea.readOnly = !isEditable;

        // JSON 文件格式化显示
        if (res.is_json && res.parsed !== null) {
            textarea.value = JSON.stringify(res.parsed, null, 2);
        } else {
            textarea.value = res.content;
        }

        textarea.addEventListener('input', () => {
            this._fileEditorDirty = true;
            title.textContent = path + ' (已修改)';
        });
        content.appendChild(textarea);
    },

    /** 保存当前文件 */
    async _saveCurrentFile() {
        if (!this._currentFilePath) return;
        const textarea = document.querySelector('.file-textarea');
        if (!textarea) return;

        const saveBtn = document.getElementById('btn-save-file');
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';

        const res = await Api.fileSave(this._currentFilePath, textarea.value);
        saveBtn.disabled = false;
        saveBtn.textContent = '保存';

        if (res.ok) {
            Utils.toast(res.msg || '保存成功', 'success');
            this._fileEditorDirty = false;
            document.getElementById('file-editor-title').textContent = this._currentFilePath;
        } else {
            Utils.toast(res.msg || '保存失败', 'error');
        }
    },

    /** 删除当前文件 */
    async _deleteCurrentFile() {
        if (!this._currentFilePath) return;
        const ok = await Utils.confirm(`确认删除文件 "${this._currentFilePath}"？此操作不可恢复。`);
        if (!ok) return;

        const res = await Api.fileDelete(this._currentFilePath);
        if (res.ok) {
            Utils.toast(res.msg || '已删除', 'success');
            this._currentFilePath = null;
            this._fileEditorDirty = false;
            document.getElementById('file-editor-title').textContent = '选择文件查看内容';
            document.getElementById('file-editor-content').innerHTML =
                '<div class="chart-empty" style="margin:auto;">文件已删除</div>';
            document.getElementById('file-editor-actions').classList.add('hidden');
            await this._loadFileList();
        } else {
            Utils.toast(res.msg || '删除失败', 'error');
        }
    },

    /** 更新 IP 名单标签文字 */
    _updateIpListLabel(mode) {
        const label = document.getElementById('ip-list-label');
        const section = document.getElementById('ip-list-section');
        if (!label || !section) return;
        if (mode === 'disabled') {
            section.style.opacity = '0.5';
            label.textContent = 'IP 名单（当前模式下不生效）';
        } else if (mode === 'whitelist') {
            section.style.opacity = '1';
            label.textContent = '白名单 IP';
        } else {
            section.style.opacity = '1';
            label.textContent = '黑名单 IP';
        }
    }
};

// 启动应用
document.addEventListener('DOMContentLoaded', () => App.start());
