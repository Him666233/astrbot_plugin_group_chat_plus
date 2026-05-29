/**
 * app.js - 面板主界面初始化、全局状态
 * 只在 /panel 页面加载，此时已通过服务端 JWT 验证
 */

const App = {
    _currentView: 'tech-tree',
    _initialized: false,
    _authMonitor: null,
    _configFileName: '',
    _configPanelOpen: false,

    /** 应用入口（面板页面加载时调用） */
    async start() {
        const configMeta = await Api.getConfig();
        if (configMeta && configMeta.ok) {
            this._configFileName = configMeta.config_file_name || '';
        }

        const heartbeatConfig = this._buildHeartbeatConfig(
            configMeta && configMeta.ok ? (configMeta.config || {}) : {}
        );
        this._installAuthMonitor(heartbeatConfig);

        const verify = await Api.verify();
        if (!verify.ok) {
            this._redirectToLogin(verify.reason || 'expired', verify.msg || '登录已失效，请重新登录');
            return;
        }

        this._authMonitor?.markAuthenticated?.(verify);
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

        this._updateConfigBadgeVisibility();

        // 缩放按钮仅在流程图页面显示
        const zoomCtrl = document.getElementById('zoom-ctrl');
        if (zoomCtrl) zoomCtrl.classList.toggle('hidden', name !== 'tech-tree');

        // 按需初始化视图
        this._activateView(name);
    },

    /** 激活视图时加载数据 */
    async _activateView(name) {
        // 切换视图时销毁需要清理的模块
        if (name !== 'charts') Charts.destroy();
        if (name !== 'sessions') SessionMgr.destroy();
        if (name !== 'tech-tree' && typeof TechTree !== 'undefined') TechTree.closeAllFloaters();
        if (name !== 'tech-tree') this.setConfigPanelOpen(false);

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

        this._ensureConfigBadge();
        this._updateConfigBadgeVisibility();

        // 退出登录
        const btnLogout = document.getElementById('btn-logout');
        if (btnLogout) {
            btnLogout.addEventListener('click', async () => {
                await Api.logout();
                this._authMonitor?.broadcast?.('logout');
                this._redirectToLogin('logout', '您已退出登录', { showAlert: false });
            });
        }

        // 支持作者
        const btnSupportAuthor = document.getElementById('btn-support-author');
        if (btnSupportAuthor) {
            btnSupportAuthor.addEventListener('click', async () => {
                const ok = await Utils.supportAuthorDialog();
                if (ok) {
                    window.open('https://afdian.com/a/chat_plus', '_blank');
                }
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

        // 若上次是核心设置页保存并重启触发的刷新，恢复到之前的视图
        let _restored = false;
        try {
            const restoreView = sessionStorage.getItem('gcp_restore_view');
            if (restoreView) {
                sessionStorage.removeItem('gcp_restore_view');
                this.showView(restoreView);
                _restored = true;
            }
        } catch (_e) {}

        if (!_restored) {
            // 无恢复标记：初始化默认视图
            await this._activateView(this._currentView);
        }

        // 全局点击：工具提示外部点击时关闭（移动端）
        document.addEventListener('click', (e) => {
            if (this._logTooltip && !e.target.closest('[data-tooltip]')) {
                this._hideLogTooltip();
            }
        });
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
                desc: '重置所有插件数据（注意力、情绪、概率等运行时状态）并清除所有会话的聊天记录缓存。不影响配置文件。',
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
                            if (mode === 'restart' || mode === 'reload') {
                                App._pollRestartStatus(mode);
                            }
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
        // 每次进入视图都重置到第一页，确保最新日志可见
        this._accessLogPage = 1;

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
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="log-refresh-hint">本页无自动刷新，有新日志产生时请手动点击刷新按钮获取最新信息</span>
                    <button class="btn btn-sm" id="btn-refresh-log">刷新</button>
                </div>
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

        if (window.innerWidth <= 1023) {
            const list = document.createElement('div');
            list.className = 'log-card-list';
            bans.forEach(ban => {
                const remaining = ban.remaining_seconds === null
                    ? '永久' : Utils.formatDuration(ban.remaining_seconds);
                const isSpider = ban.reason && ban.reason.startsWith('[防爬虫]');
                const sourceBadge = isSpider
                    ? '<span class="status-badge status-warn">🕷️ 自动</span>'
                    : '<span class="status-badge">👤 手动</span>';
                const card = document.createElement('div');
                card.className = 'log-card';
                card.innerHTML = `
                    <div class="log-card-header">
                        <span class="log-card-ip">${Utils.escapeHtml(ban.ip)}</span>
                        ${sourceBadge}
                    </div>
                    <div class="log-card-row"><strong>原因</strong><span style="word-break:break-word;">${Utils.escapeHtml(ban.reason || '')}</span></div>
                    <div class="log-card-row"><strong>封禁时间</strong><span>${Utils.formatTime(ban.banned_at)}</span></div>
                    <div class="log-card-row"><strong>剩余时间</strong><span>${remaining}</span></div>
                    <div class="log-card-actions">
                        <button class="btn btn-sm" data-edit-ban="${Utils.escapeHtml(ban.ip)}">编辑备注</button>
                        <button class="btn btn-sm" data-unban="${Utils.escapeHtml(ban.ip)}">解封</button>
                    </div>`;
                list.appendChild(card);
            });
            container.appendChild(list);
        } else {
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
                const isSpider = ban.reason && ban.reason.startsWith('[防爬虫]');
                const sourceBadge = isSpider
                    ? '<span style="font-size:11px;background:rgba(224,32,32,0.15);color:var(--accent-red);border:1px solid rgba(224,32,32,0.35);border-radius:3px;padding:1px 5px;white-space:nowrap;">🕷️ 自动</span>'
                    : '<span style="font-size:11px;background:var(--glass-bg-hover);color:var(--text-secondary);border:1px solid var(--glass-border);border-radius:3px;padding:1px 5px;white-space:nowrap;">👤 手动</span>';
                const displayReason = Utils.escapeHtml(ban.reason || '');
                tr.innerHTML = `
                    <td style="font-family:monospace;white-space:nowrap;">${Utils.escapeHtml(ban.ip)}</td>
                    <td style="white-space:nowrap;">${sourceBadge}</td>
                    <td><span title="${displayReason}" style="display:block;word-break:break-word;line-height:1.5;">${displayReason}</span></td>
                    <td style="white-space:nowrap;">${Utils.formatTime(ban.banned_at)}</td>
                    <td style="white-space:nowrap;">${remaining}</td>
                    <td style="white-space:nowrap;">
                        <button class="btn btn-sm" data-edit-ban="${Utils.escapeHtml(ban.ip)}">编辑备注</button>
                        <button class="btn btn-sm" data-unban="${Utils.escapeHtml(ban.ip)}">解封</button>
                    </td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            container.appendChild(table);
        }

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

        container.querySelectorAll('[data-edit-ban]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const ip = btn.dataset.editBan;
                const ban = bans.find(b => b.ip === ip);
                const currentReason = ban ? (ban.reason || '') : '';
                const newReason = await Utils.prompt(`编辑 ${ip} 的封禁备注`, currentReason, 128);
                if (newReason === null) return;
                const res = await Api.updateBanNote(ip, newReason);
                if (res.ok) {
                    Utils.toast('备注已更新', 'success');
                    await this._loadBanList();
                } else {
                    Utils.toast(res.msg || '更新失败', 'error');
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

        if (window.innerWidth <= 1023) {
            const list = document.createElement('div');
            list.className = 'log-card-list';
            logs.forEach((log, idx) => {
                const statusClass = log.status >= 400 ? 'status-error' :
                    (log.status >= 300 ? 'status-warn' : 'status-ok');
                // 移动端完整显示附注（不截断），允许自动换行
                let noteHtml = '<span class="log-card-note-empty">—</span>';
                if (log.note) {
                    const safeNote = Utils.escapeHtml(log.note);
                    noteHtml = log.note.includes('[防爬虫自动封禁]')
                        ? `<span class="status-badge status-warn log-card-note-full" data-tooltip="${safeNote}">🕷️ ${safeNote}</span>`
                        : log.note.includes('登录失败')
                            ? `<span class="status-badge status-warn log-card-note-full" data-tooltip="${safeNote}">🔑 ${safeNote}</span>`
                            : `<span class="log-card-note-full" data-tooltip="${safeNote}">${safeNote}</span>`;
                }
                const card = document.createElement('div');
                card.className = 'log-card';
                card.innerHTML = `
                    <div class="log-card-header">
                        <span class="log-card-ip">${Utils.escapeHtml(log.ip)}</span>
                        <span class="status-badge ${statusClass}">${log.status}</span>
                    </div>
                    <div class="log-card-row"><strong>时间</strong><span>${Utils.formatTime(log.timestamp)}</span></div>
                    <div class="log-card-row"><strong>方法</strong><span>${Utils.escapeHtml(log.method)}</span></div>
                    <div class="log-card-row"><strong>路径</strong><span class="log-card-path">${Utils.escapeHtml(log.path)}</span></div>
                    <div class="log-card-row"><strong>附注</strong>${noteHtml}</div>
                    <div class="log-card-actions">
                        <button class="btn btn-sm btn-danger" data-ban-ip="${Utils.escapeHtml(log.ip)}" data-log-idx="${idx}">封禁</button>
                    </div>`;
                list.appendChild(card);
            });
            container.appendChild(list);
        } else {
            const table = document.createElement('table');
            table.className = 'log-table';
            table.innerHTML = `<thead><tr>
                <th>时间</th><th>IP</th><th>方法</th><th>路径</th><th>状态</th><th>附注</th><th>操作</th>
            </tr></thead>`;
            const tbody = document.createElement('tbody');
            logs.forEach((log, idx) => {
                const tr = document.createElement('tr');
                const statusClass = log.status >= 400 ? 'status-error' :
                                    log.status >= 300 ? 'status-warn' : 'status-ok';

                let noteHtml = '';
                if (log.note) {
                    // 桌面端放宽截断限制（从 30 改为 80 字符），附注列会自然占满剩余空间
                    const safeNote = Utils.escapeHtml(log.note);
                    const displayText = log.note.length > 80
                        ? Utils.escapeHtml(log.note.slice(0, 80)) + '…'
                        : safeNote;
                    if (log.note.includes('[防爬虫自动封禁]')) {
                        noteHtml = `<span class="log-note-spider" data-tooltip="${safeNote}"
                            style="font-size:11px;background:rgba(224,32,32,0.15);color:var(--accent-red);
                            border:1px solid rgba(224,32,32,0.35);border-radius:3px;padding:2px 6px;
                            white-space:nowrap;display:inline-block;max-width:100%;overflow:hidden;text-overflow:ellipsis;">
                            🕷️ ${displayText}
                        </span>`;
                    } else if (log.note.includes('登录失败')) {
                        noteHtml = `<span class="log-note-brute" data-tooltip="${safeNote}">🔑 ${displayText}</span>`;
                    } else {
                        noteHtml = `<span class="log-note" data-tooltip="${safeNote}">${displayText}</span>`;
                    }
                }

                tr.innerHTML = `
                    <td>${Utils.formatTime(log.timestamp)}</td>
                    <td style="font-family:monospace;">${Utils.escapeHtml(log.ip)}</td>
                    <td>${Utils.escapeHtml(log.method)}</td>
                    <td class="log-path">${Utils.escapeHtml(log.path)}</td>
                    <td><span class="status-badge ${statusClass}">${log.status}</span></td>
                    <td class="log-note-cell">${noteHtml}</td>
                    <td><button class="btn btn-sm btn-danger" data-ban-ip="${Utils.escapeHtml(log.ip)}" data-log-idx="${idx}">封禁</button></td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            container.appendChild(table);
        }

        container.querySelectorAll('[data-ban-ip]').forEach(btn => {
            btn.addEventListener('click', () => {
                const logIdx = btn.dataset.logIdx;
                const logEntry = (logIdx !== undefined && logs[parseInt(logIdx)]) ? logs[parseInt(logIdx)] : null;
                this._showBanDialog(btn.dataset.banIp, logEntry);
            });
        });

        this._bindLogTooltips(container);

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
        actions.style.cssText = 'display:flex;gap:8px;';

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

    /** 为访问日志附注元素绑定自定义工具提示事件 */
    _bindLogTooltips(container) {
        const notes = container.querySelectorAll('[data-tooltip]');
        notes.forEach(el => {
            el.addEventListener('mouseenter', (e) => {
                this._showLogTooltip(e, el.dataset.tooltip);
            });
            el.addEventListener('mouseleave', () => {
                this._hideLogTooltip();
            });
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this._toggleLogTooltip(e, el.dataset.tooltip);
            });
        });
    },

    /** 在光标附近显示工具提示 */
    _showLogTooltip(event, text) {
        this._hideLogTooltip();
        const tip = document.createElement('div');
        tip.className = 'log-tooltip';
        tip.textContent = text;
        document.body.appendChild(tip);
        // 强制重排后添加 show 类以触发过渡动画
        void tip.offsetWidth;
        tip.classList.add('show');
        this._logTooltip = tip;
        this._positionLogTooltip(event);
    },

    /** 定位工具提示，确保不超出视口 */
    _positionLogTooltip(event) {
        if (!this._logTooltip) return;
        const tip = this._logTooltip;
        const rect = tip.getBoundingClientRect();
        let left = event.clientX + 14;
        let top = event.clientY + 14;
        if (left + rect.width > window.innerWidth - 10) {
            left = window.innerWidth - rect.width - 10;
        }
        if (top + rect.height > window.innerHeight - 10) {
            top = window.innerHeight - rect.height - 10;
        }
        if (left < 10) left = 10;
        if (top < 10) top = 10;
        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
    },

    /** 隐藏并移除工具提示 */
    _hideLogTooltip() {
        if (this._logTooltip) {
            this._logTooltip.classList.remove('show');
            const tip = this._logTooltip;
            this._logTooltip = null;
            setTimeout(() => { if (tip.parentNode) tip.remove(); }, 160);
        }
    },

    /** 切换工具提示（移动端点击行为） */
    _toggleLogTooltip(event, text) {
        if (this._logTooltip && this._logTooltip.classList.contains('show')) {
            this._hideLogTooltip();
        } else {
            this._showLogTooltip(event, text);
        }
    },

    /** 显示封禁 IP 弹窗，entry 为可选的访问日志条目（用于预填原因） */
    _showBanDialog(ip = '', entry = null) {
        const initialReason = entry && entry.note ? entry.note : '';
        const overlay = document.createElement('div');
        overlay.className = 'confirm-overlay';
        overlay.innerHTML = `
            <div class="confirm-box" style="width:360px;">
                <h3 style="margin-bottom:12px;">封禁 IP</h3>
                <div style="display:flex;flex-direction:column;gap:8px;">
                    <input type="text" id="ban-ip-input" placeholder="IPv4 / IPv6 地址" value="${Utils.escapeHtml(ip)}">
                    <div style="font-size:10px;color:var(--text-muted);margin-top:-4px;">支持 IPv4（如 192.168.1.100）和 IPv6（如 2001:db8::1）</div>
                    <input type="text" id="ban-reason-input" placeholder="封禁原因（可选）" maxlength="128" value="${Utils.escapeHtml(initialReason)}">
                    <div style="font-size:10px;color:var(--text-muted);margin-top:-2px;">最多 128 个字符</div>
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
                    其中也包括心跳探测频率/重试策略，这些参数会直接影响会话失效探测与防护行为。<br>
                    如需调整，请前往 <strong>AstrBot 平台 → 插件配置</strong> 中对应的传统配置项进行修改。
                </span>
            </div>
            <div id="sec-readonly-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="sec-readonly-content" class="hidden" style="display:flex;flex-direction:column;gap:8px;"></div>`;
        container.appendChild(secSection);
        this._loadSecReadonly();

        // ---- 会话心跳状态区 ----
        const heartbeatSection = document.createElement('div');
        heartbeatSection.className = 'settings-section';
        heartbeatSection.innerHTML = `
            <div class="settings-section-header">
                <h3>💓 会话心跳状态</h3>
                <div class="settings-section-header-right">
                    <button id="btn-refresh-heartbeat" class="btn btn-sm" title="手动刷新心跳状态">🔄 刷新</button>
                    <label class="auto-refresh-toggle">
                        <span class="dot active" id="heartbeat-refresh-dot"></span>
                        <input type="checkbox" checked id="heartbeat-auto-refresh">
                        <span>自动刷新</span>
                    </label>
                </div>
            </div>
            <div id="heartbeat-status-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="heartbeat-status-content" class="hidden" style="display:flex;flex-direction:column;gap:8px;"></div>`;
        container.appendChild(heartbeatSection);
        this._loadHeartbeatStatus();


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
                            <span style="font-weight:normal;color:var(--text-secondary);">（每行一个，支持 IPv4 / IPv6）</span>
                        </label>
                        <textarea id="ip-list-textarea" rows="5" style="width:100%;font-family:monospace;font-size:13px;" placeholder="每行一个 IP 地址&#10;例如：192.168.1.100&#10;　　　2001:db8::1"></textarea>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;line-height:1.6;">
                            📌 仅支持<strong>单个 IP 精确匹配</strong>，不支持 CIDR 网段（如 192.168.0.0/16）、IP 段或域名。<br>
                            📌 <code>0.0.0.0</code> 和 <code>::</code> 为未指定地址，<strong>不会匹配任何实际客户端 IP</strong>：白名单模式下将导致全员无法访问，黑名单模式下无实际拦截效果。<br>
                            📌 IPv6 地址支持任意格式（压缩/半压缩/完整展开），系统会自动统一规范化为标准形式进行匹配。
                        </div>
                    </div>
                    <div>
                        <label style="font-size:13px;font-weight:600;margin-bottom:4px;display:block;">
                            受保护 IP（永不封禁）
                            <span style="font-weight:normal;color:var(--text-muted);"> （只读，仅可通过 AstrBot 传统配置修改）</span>
                        </label>
                        <div id="protected-ips-display" style="font-family:monospace;font-size:13px;padding:8px;background:var(--bg-input);border:1px solid var(--border-color);border-radius:var(--radius-sm);min-height:48px;color:var(--text-secondary);white-space:pre-wrap;"></div>
                        <div style="font-size:11px;color:var(--accent-red);margin-top:4px;">
                            ⚠️ 受保护 IP 是底线安全配置（最高优先级，不受封禁/黑白名单/防爬虫/暴力破解等任何机制影响）。支持 IPv4 和 IPv6 地址。
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
                saveIpBtn.disabled = true;
                statusEl.textContent = '正在重启插件，完成后将自动刷新...';
                statusEl.style.color = 'var(--accent)';
                const reloadRes = await Api.reloadPlugin();
                // 无论服务器返回什么（包括网络错误），都尝试等待服务器恢复后自动刷新。
                // 若服务器未真正重启，轮询会立刻成功并刷新页面，结果等价。
                if (reloadRes && !reloadRes.ok && !reloadRes.network_error) {
                    // 服务器返回了明确的业务错误（非网络问题），说明配置有问题
                    saveIpBtn.disabled = false;
                    saveIpBtn.textContent = '保存并重启插件';
                    statusEl.textContent = '重启失败';
                    statusEl.style.color = 'var(--danger)';
                    Utils.toast(reloadRes.msg || '重启失败，请检查配置', 'error');
                    return;
                }
                this._waitForServerAndRefresh();
            });
        }

        // ---- 桌面端兼容区 ----
        const desktopSection = document.createElement('div');
        desktopSection.className = 'settings-section';
        desktopSection.innerHTML = `
            <h3>🖥️ 桌面端兼容</h3>
            <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;line-height:1.7;">
                AstrBot 桌面端（Desktop Edition）使用 Tauri 托管后端进程，重启机制与标准版不同。<br>
                插件支持自动检测运行环境，也可手动指定。修改后需 <strong>保存并重启插件</strong> 生效。
            </p>
            <div id="desktop-loading" class="chart-empty" style="padding:12px;">加载中...</div>
            <div id="desktop-content" class="hidden" style="display:flex;flex-direction:column;gap:12px;max-width:500px;"></div>`;
        container.appendChild(desktopSection);
        this._loadDesktopConfig();

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
                <strong>IP 访问控制（黑白名单）</strong>修改后需点击「保存并重启插件」，重启完成后生效，与传统配置项行为一致。所有 IP 名单均支持 IPv4 和 IPv6 地址，仅做精确地址匹配（不支持 CIDR 网段/子网）。<br>
                <br>
                - <strong>关闭模式</strong>：不做 IP 过滤，任何 IP 均可访问<br>
                - <strong>白名单模式</strong>：仅名单中的 IP 可访问面板（白名单 IP 直接放行，不受封禁影响）<br>
                - <strong>黑名单模式</strong>：名单中的 IP 被阻止访问（未在黑名单内的 IP 仍受封禁检查约束）<br>
                - <strong>受保护 IP</strong>：优先级最高，永远放行，不受任何机制影响。支持 IPv4 / IPv6。<strong>只能通过 AstrBot 传统配置修改</strong>，防止面板被攻破后遭篡改<br>
                <br>
                <strong>总开关 / 端口 / 监听地址 / 密码重置 / 信任代理 / IP 绑定 / 心跳频率</strong>：这些配置出于安全考虑只能通过 AstrBot 插件配置页修改，上方「安全敏感配置」区展示了其当前值供参考。监听地址设为 <code>0.0.0.0</code> 或 <code>::</code> 时自动启用双栈（同时监听 IPv4 + IPv6）。<br>
                <br>
                <strong>日志清理 / 防爬虫 / 已登录请求限速</strong>：在「Web 面板运行配置」区可直接修改，修改后需保存并重启插件。
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
            'web_panel_trust_proxy',
            'web_panel_ip_bind_check',
            'web_panel_heartbeat_visible_interval_seconds',
            'web_panel_heartbeat_hidden_interval_seconds',
            'web_panel_heartbeat_retry_base_seconds',
            'web_panel_heartbeat_retry_max_seconds',
            'web_panel_brute_force_window',
            'web_panel_brute_force_rate_window',
            'web_panel_brute_force_rate_count',
            'web_panel_brute_force_tiers',
            'web_panel_brute_force_ban_duration',
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
            const readonlyNote = (key.startsWith('web_panel_heartbeat_') || key === 'web_panel_ip_bind_check' || key === 'web_panel_trust_proxy')
                ? '⚠️ 此项属于 Web 安全敏感配置，请在 AstrBot 平台插件配置页修改'
                : '⚠️ 此项为安全敏感配置，请在 AstrBot 平台插件配置页修改';
            row.innerHTML = `
                <div class="config-field-label">🔒 ${desc}</div>
                <div class="config-field-readonly-value">当前值：${displayVal}</div>
                <div class="config-field-readonly-note">${readonlyNote}</div>`;
            content.appendChild(row);
        });
    },



    /** 加载桌面端兼容配置 */
    async _loadDesktopConfig() {
        const loading = document.getElementById('desktop-loading');
        const content = document.getElementById('desktop-content');
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
        const desktopInfo = res.desktop_info || {};

        // 当前检测状态指示
        const statusRow = document.createElement('div');
        statusRow.style.cssText = 'padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.6;';
        if (desktopInfo.is_desktop) {
            statusRow.style.background = 'rgba(59,130,246,0.08)';
            statusRow.style.border = '1px solid rgba(59,130,246,0.25)';
            statusRow.innerHTML = `
                <strong>🖥️ 当前环境：桌面端</strong><br>
                <span style="font-size:12px;color:var(--text-secondary);">
                    检测模式：${desktopInfo.mode_setting || 'auto'}<br>
                    检测依据：${desktopInfo.detected_env || '—'}
                </span>`;
        } else {
            statusRow.style.background = 'rgba(34,197,94,0.08)';
            statusRow.style.border = '1px solid rgba(34,197,94,0.25)';
            statusRow.innerHTML = `
                <strong>📦 当前环境：标准版</strong><br>
                <span style="font-size:12px;color:var(--text-secondary);">
                    检测模式：${desktopInfo.mode_setting || 'auto'}<br>
                    检测结果：未检测到桌面端特征
                </span>`;
        }
        content.appendChild(statusRow);

        // desktop_mode 可编辑选择
        const modeSchema = schema['desktop_mode'];
        if (modeSchema) {
            const modeRow = document.createElement('div');
            modeRow.className = 'config-field';
            modeRow.style.maxWidth = '500px';
            const currentMode = cfg['desktop_mode'] || 'auto';
            const modeLabels = {
                'auto': 'auto — 自动检测（推荐）',
                'force_desktop': 'force_desktop — 强制桌面端模式',
                'force_standard': 'force_standard — 强制标准版模式'
            };
            const label = document.createElement('div');
            label.className = 'config-field-label';
            label.textContent = '桌面端模式';
            modeRow.appendChild(label);

            const hint = document.createElement('div');
            hint.className = 'config-field-hint';
            hint.textContent = '控制插件如何识别运行环境。auto=多重策略自动检测，force_desktop=强制桌面端，force_standard=强制标准版';
            modeRow.appendChild(hint);

            const select = document.createElement('select');
            select.className = 'config-select';
            select.style.marginTop = '6px';
            (modeSchema.options || ['auto', 'force_desktop', 'force_standard']).forEach(opt => {
                const o = document.createElement('option');
                o.value = opt;
                o.textContent = modeLabels[opt] || opt;
                if (opt === currentMode) o.selected = true;
                select.appendChild(o);
            });
            modeRow.appendChild(select);
            content.appendChild(modeRow);

            // desktop_detected_env 只读
            const detectedRow = document.createElement('div');
            detectedRow.className = 'config-field config-field-readonly';
            detectedRow.style.maxWidth = '500px';
            const detectedVal = cfg['desktop_detected_env'] || '（未检测）';
            detectedRow.innerHTML = `
                <div class="config-field-label">🔒 自动检测结果</div>
                <div class="config-field-readonly-value">当前值：${detectedVal}</div>
                <div class="config-field-readonly-note">此项由插件自动检测并写入，无需手动修改</div>`;
            content.appendChild(detectedRow);

            // 保存按钮
            const saveRow = document.createElement('div');
            saveRow.style.cssText = 'display:flex;gap:8px;align-items:center;margin-top:4px;';
            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-primary btn-sm';
            saveBtn.textContent = '保存并重启插件';
            const statusEl = document.createElement('span');
            statusEl.style.cssText = 'font-size:12px;color:var(--text-secondary);';
            saveRow.appendChild(saveBtn);
            saveRow.appendChild(statusEl);
            content.appendChild(saveRow);

            saveBtn.addEventListener('click', async () => {
                const newMode = select.value;
                saveBtn.disabled = true;
                statusEl.textContent = '保存中...';
                const saveRes = await Api.putConfig({ desktop_mode: newMode });
                if (!saveRes.ok) {
                    Utils.toast('保存失败：' + (saveRes.msg || '未知错误'), 'error');
                    statusEl.textContent = '保存失败';
                    saveBtn.disabled = false;
                    return;
                }
                statusEl.textContent = '正在重启，完成后将自动刷新...';
                statusEl.style.color = 'var(--accent)';
                const reloadRes = await Api.reloadPlugin();
                if (reloadRes && !reloadRes.ok && !reloadRes.network_error) {
                    saveBtn.disabled = false;
                    statusEl.textContent = '重启失败';
                    statusEl.style.color = 'var(--danger)';
                    Utils.toast(reloadRes.msg || '重启失败，请检查配置', 'error');
                    return;
                }
                this._waitForServerAndRefresh();
            });
        }
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
            'web_panel_log_auto_clean',
            'web_panel_log_retention_days',
            'web_panel_log_clean_interval_hours',
            'web_panel_anti_spider',
            'web_panel_anti_spider_rate_limit',
            'web_panel_anti_spider_ban_duration',
            'web_panel_authenticated_rate_limit',
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
            saveBtn.textContent = '重启中...';
            statusEl.textContent = '正在重启，完成后将自动刷新...';
            statusEl.style.color = 'var(--accent)';

            const res = await Api.reloadPlugin(pending);
            if (res && !res.ok && !res.network_error) {
                saveBtn.disabled = false;
                saveBtn.textContent = '保存并重启插件';
                statusEl.textContent = '重启失败';
                statusEl.style.color = 'var(--danger)';
                Utils.toast(res.msg || '重启失败', 'error');
                return;
            }
            // 无论成功或网络错误，等待服务器恢复后自动刷新
            Object.assign(cfg, pending);
            Object.keys(pending).forEach(k => delete pending[k]);
            this._waitForServerAndRefresh();
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
    _currentFileMeta: null,

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
            <div class="file-refresh-notice">
                ⚠️ 文件数据可能已被外部更新，请及时点击右侧"刷新"按钮获取最新文件列表和内容。本页面不提供自动刷新功能。
            </div>
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
                <div id="file-editor-actions" class="file-editor-actions hidden">
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
        document.getElementById('btn-refresh-files').addEventListener('click', () => this._refreshFileBrowser());
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

        const statusMeta = {
            protected: { label: '受保护', className: 'file-status--protected' },
            editable: { label: '可编辑', className: 'file-status--editable' },
            delete_only: { label: '仅删除', className: 'file-status--readonly' },
        };

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
                const icon = f.protected ? '🔒' : f.is_json ? '{}' : (f.is_text ? '📝' : '📄');
                const meta = statusMeta[f.status] || statusMeta.delete_only;
                item.innerHTML = `
                    <span class="file-icon">${icon}</span>
                    <div class="file-item-main">
                        <span class="file-name" title="${Utils.escapeHtml(f.path)}">${Utils.escapeHtml(f.name)}</span>
                        <div class="file-item-subline">
                            <span class="file-size">${Utils.formatSize(f.size)}</span>
                            <span class="file-status ${meta.className}">${meta.label}</span>
                        </div>
                    </div>`;
                item.addEventListener('click', () => this._openFile(f));
                filesList.appendChild(item);
            });
            dirEl.appendChild(filesList);
            tree.appendChild(dirEl);
        });
    },

    /** 刷新文件浏览器：刷新文件列表 + 重新读取当前打开的文件 */
    async _refreshFileBrowser() {
        // 如果有未保存的修改，先确认
        if (this._fileEditorDirty) {
            const ok = await Utils.confirm('当前文件有未保存的修改，刷新将丢失修改，是否继续？');
            if (!ok) return;
        }

        await this._loadFileList();

        // 如果有当前打开的文件，重新读取内容
        if (this._currentFilePath && this._currentFileMeta) {
            this._fileEditorDirty = false;
            await this._openFile(this._currentFileMeta);
        }

        Utils.toast('文件列表已刷新', 'success', 2000);
    },

    /** 打开文件 */
    async _openFile(fileMeta) {
        const path = fileMeta?.path;
        if (!path) return;
        if (this._fileEditorDirty) {
            const ok = await Utils.confirm('当前文件有未保存的修改，确定放弃？');
            if (!ok) return;
        }

        this._currentFilePath = path;
        this._currentFileMeta = fileMeta;
        this._fileEditorDirty = false;
        const content = document.getElementById('file-editor-content');
        const title = document.getElementById('file-editor-title');
        const actions = document.getElementById('file-editor-actions');
        const sizeEl = document.getElementById('file-editor-size');
        const saveBtn = document.getElementById('btn-save-file');
        const deleteBtn = document.getElementById('btn-delete-file');

        title.textContent = path;

        document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.file-item').forEach(el => {
            if (el.querySelector('.file-name')?.title === path) {
                el.classList.add('active');
            }
        });

        if (fileMeta.protected) {
            actions.classList.add('hidden');
            content.innerHTML = `<div class="chart-empty" style="margin:auto;text-align:center;line-height:1.8;">
                <div style="font-size:32px;margin-bottom:8px;">🔒</div>
                <div style="font-weight:600;">此文件受保护</div>
                <div style="color:var(--text-secondary);font-size:13px;">出于安全考虑，不支持在线查看、编辑或删除。<br>如需处理，请前往服务器本地对应目录手动操作。</div>
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

        this._currentFileMeta = { ...fileMeta, ...res };
        actions.classList.remove('hidden');
        actions.style.display = 'flex';
        sizeEl.textContent = Utils.formatSize(res.content.length);
        saveBtn.classList.toggle('hidden', !res.can_edit);
        deleteBtn.classList.toggle('hidden', !res.can_delete);

        content.innerHTML = '';
        const textarea = document.createElement('textarea');
        textarea.className = 'file-textarea';
        textarea.spellcheck = false;
        textarea.readOnly = !res.can_edit;

        if (res.is_json && res.parsed !== null) {
            textarea.value = JSON.stringify(res.parsed, null, 2);
        } else {
            textarea.value = res.content;
        }

        if (!res.can_edit) {
            const readonlyHint = document.createElement('div');
            readonlyHint.className = 'file-editor-hint';
            readonlyHint.textContent = '该文件可查看，但当前不支持在线编辑。';
            content.appendChild(readonlyHint);
        }

        textarea.addEventListener('input', () => {
            if (!res.can_edit) return;
            this._fileEditorDirty = true;
            title.textContent = path + ' (已修改)';
        });
        content.appendChild(textarea);
    },

    /** 保存当前文件 */
    async _saveCurrentFile() {
        if (!this._currentFilePath || !this._currentFileMeta?.can_edit) return;
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
            this._currentFileMeta = { ...this._currentFileMeta, ...res };
            document.getElementById('file-editor-title').textContent = this._currentFilePath;
        } else {
            if (res.msg && (res.msg.includes('不存在') || res.msg.includes('已删除'))) {
                this._currentFileMeta = null;
                this._fileEditorDirty = false;
                document.getElementById('file-editor-title').textContent = '选择文件查看内容';
                document.getElementById('file-editor-content').innerHTML =
                    '<div class="chart-empty" style="margin:auto;">文件已不存在，请刷新列表后重新打开</div>';
                document.getElementById('file-editor-actions').classList.add('hidden');
                await this._loadFileList();
            }
            Utils.toast(res.msg || '保存失败', 'error');
        }
    },

    /** 删除当前文件 */
    async _deleteCurrentFile() {
        if (!this._currentFilePath || !this._currentFileMeta?.can_delete) return;
        const ok = await Utils.confirm(`确认删除文件 "${this._currentFilePath}"？此操作不可恢复。`);
        if (!ok) return;

        const res = await Api.fileDelete(this._currentFilePath);
        if (res.ok) {
            Utils.toast(res.msg || '已删除', 'success');
            this._currentFilePath = null;
            this._currentFileMeta = null;
            this._fileEditorDirty = false;
            document.getElementById('file-editor-title').textContent = '选择文件查看内容';
            document.getElementById('file-editor-content').innerHTML =
                '<div class="chart-empty" style="margin:auto;">文件已删除</div>';
            document.getElementById('file-editor-actions').classList.add('hidden');
            await this._loadFileList();
        } else {
            if (res.msg && (res.msg.includes('不存在') || res.msg.includes('已删除'))) {
                this._currentFilePath = null;
                this._currentFileMeta = null;
                this._fileEditorDirty = false;
                document.getElementById('file-editor-title').textContent = '选择文件查看内容';
                document.getElementById('file-editor-content').innerHTML =
                    '<div class="chart-empty" style="margin:auto;">文件已不存在，请刷新列表后重试</div>';
                document.getElementById('file-editor-actions').classList.add('hidden');
                await this._loadFileList();
            }
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
    },

    /** 等待服务器重启完成后刷新当前页面（回到当前所在视图）。
     *  每 intervalMs 毫秒探测一次服务器是否恢复，恢复后自动 reload。
     *  探测使用 /api/auth/status（公开路由，不触发防爬虫速率限制）。
     *  最长等待 maxWaitMs 毫秒，超时后提示手动刷新。 */
    async _waitForServerAndRefresh(maxWaitMs = 35000, intervalMs = 3000) {
        const startedAt = Date.now();
        // 记住当前所在视图，刷新后恢复（而不是回到默认的流程图页）
        try { sessionStorage.setItem('gcp_restore_view', this._currentView); } catch (_e) {}
        // 先等一小段时间让旧服务器完全停止
        await new Promise(r => setTimeout(r, 1500));

        const poll = async () => {
            if (Date.now() - startedAt >= maxWaitMs) {
                try { sessionStorage.removeItem('gcp_restore_view'); } catch (_e) {}
                Utils.toast('插件重启耗时较长，请手动刷新页面（F5）确认最新配置已生效', 'warning', 8000);
                return;
            }
            try {
                const resp = await fetch('/api/auth/status', { method: 'GET', cache: 'no-store' });
                if (resp.ok) {
                    // 服务器已恢复，保留 restore_view 标记供初始化时使用，然后刷新
                    Utils.toast('插件已重启，正在刷新页面...', 'success', 2000);
                    setTimeout(() => { window.location.reload(); }, 800);
                    return;
                }
            } catch (_e) {
                // 网络错误 = 服务器尚未恢复，继续轮询
            }
            setTimeout(poll, intervalMs);
        };
        poll();
    },

    /** 轮询重启/重载状态，在右上角弹出结果提示。 */
    async _pollRestartStatus(operation, maxWaitMs = 30000, intervalMs = 2500) {
        const startedAt = Date.now();
        const label = operation === 'restart' ? 'AstrBot 重启' : '插件重载';

        return new Promise((resolve) => {
            const poll = async () => {
                if (Date.now() - startedAt >= maxWaitMs) {
                    Utils.toast(`${label}操作超时，请检查服务器日志`, 'warning', 5000);
                    resolve('timeout');
                    return;
                }
                try {
                    const res = await Api.restartStatus();
                    if (res && res.ok && res.status) {
                        if (res.status === 'success') {
                            Utils.toast(`${label}成功`, 'success', 4000);
                            resolve('success');
                            return;
                        }
                        if (res.status === 'failed') {
                            const errMsg = res.error || '未知错误';
                            Utils.toast(`${label}失败: ${errMsg}`, 'error', 6000);
                            resolve('failed');
                            return;
                        }
                    }
                } catch (_e) {
                    // 连接断开在重启过程中是正常现象，继续轮询
                }
                setTimeout(poll, intervalMs);
            };
            setTimeout(poll, 1500);
        });
    },

    _ensureConfigBadge() {
        if (document.getElementById('config-file-badge')) return;
        const badge = document.createElement('div');
        badge.id = 'config-file-badge';
        badge.className = 'config-file-badge hidden';
        badge.innerHTML = `
            <div class="config-file-badge__row">
                <span class="config-file-badge__label">配置文件</span>
                <span class="config-file-badge__value"></span>
            </div>
            <button class="config-file-badge__download" title="点击下载配置文件" aria-label="下载配置文件">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
            </button>`;
        document.body.appendChild(badge);

        // 绑定下载事件
        const downloadBtn = badge.querySelector('.config-file-badge__download');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this._downloadCurrentConfig();
            });
        }
    },

    _updateConfigBadgeVisibility() {
        const badge = document.getElementById('config-file-badge');
        if (!badge) return;
        const visibleViews = new Set(['tech-tree', 'settings']);
        const shouldShow = visibleViews.has(this._currentView) && !!this._configFileName && !this._configPanelOpen;
        badge.classList.toggle('hidden', !shouldShow);
        const valueEl = badge.querySelector('.config-file-badge__value');
        if (valueEl) valueEl.textContent = this._configFileName || '—';
        // 隐藏状态下禁用下载按钮
        const downloadBtn = badge.querySelector('.config-file-badge__download');
        if (downloadBtn) {
            downloadBtn.disabled = !shouldShow;
        }
    },

    /** 下载当前配置文件（安全加固：不暴露服务器路径）
     *
     *  一次 fetch 完成预检 + 获取内容，由前端构建 Blob 触发下载。
     *  服务端返回纯 JSON（不含 Content-Disposition），
     *  避免 Content-Disposition: attachment 在 fetch 阶段干扰浏览器。
     */
    async _downloadCurrentConfig() {
        const downloadBtn = document.querySelector('.config-file-badge__download');
        const resetBtn = () => {
            if (downloadBtn) {
                downloadBtn.disabled = false;
                downloadBtn.classList.remove('config-file-badge__download--loading');
            }
        };

        if (downloadBtn) {
            downloadBtn.disabled = true;
            downloadBtn.classList.add('config-file-badge__download--loading');
        }

        let resp;
        try {
            resp = await fetch('/api/config/download?_=' + Date.now(), {
                method: 'GET',
                credentials: 'same-origin',
            });
        } catch (e) {
            resetBtn();
            Utils.alert(
                '下载失败\n\n' +
                '网络错误：无法连接到服务器（' + (e.message || '未知错误') + '）\n\n' +
                '可能原因：\n' +
                '- 网络连接异常，请检查服务器是否在线、端口是否可达\n' +
                '- 服务器暂时不可用或正在重启中\n' +
                '- 若使用了反向代理，请确认未拦截 /api/config/download 路径\n' +
                '- 浏览器插件或防火墙拦截了请求\n' +
                '- 若使用 Docker 部署，请确认容器端口映射正确'
            );
            return;
        }

        if (!resp.ok) {
            let errMsg = 'HTTP ' + resp.status;
            try { const body = await resp.json(); errMsg = body.msg || errMsg; } catch (_) {}
            if (resp.status === 401) {
                Api.clearToken();
                Api.emitAuthEvent('unauthorized', { msg: errMsg });
            }
            resetBtn();
            // 根据状态码给出针对性排查建议
            let hint = '';
            if (resp.status === 401) {
                hint = '会话已过期或密码已修改，请刷新页面重新登录';
            } else if (resp.status === 403) {
                hint = '服务端拒绝了下载请求（文件名校验不通过或权限不足），请检查 AstrBot 日志';
            } else if (resp.status === 404) {
                hint = '配置文件尚未生成，请确认插件已完全启动并完成首次配置加载';
            } else if (resp.status >= 500) {
                hint = '服务端内部错误，请查看 AstrBot 日志排查具体异常';
            } else {
                hint = '请查看 Web 面板访问日志获取详细错误信息';
            }
            Utils.alert(
                '下载失败\n\n' +
                errMsg + '\n\n' +
                '错误说明：' + hint + '\n\n' +
                '排查步骤：\n' +
                '1. 检查 AstrBot 控制台日志中是否有相关错误输出\n' +
                '2. 在 Web 面板「访问日志」页面查看下载请求的状态和附注\n' +
                '3. 确认当前登录会话有效（可尝试刷新页面重新登录）\n' +
                '4. 若使用反向代理，确认 /api/config/download 路径已被正确转发\n' +
                '5. 若问题持续，请在 GitHub Issues 反馈并附上相关日志'
            );
            return;
        }

        // 解析服务端返回的 JSON 中的文件内容，由前端构建 Blob 下载
        let data;
        try {
            data = await resp.json();
        } catch (e) {
            resetBtn();
            Utils.alert(
                '下载失败\n\n' +
                '服务端返回了无效的数据格式，JSON 解析失败\n\n' +
                '可能原因：\n' +
                '- 服务端响应被中间设备（代理/防火墙）篡改\n' +
                '- 配置文件包含非标准字符导致编码异常\n' +
                '- 服务端内部异常导致返回了非 JSON 内容\n\n' +
                '请检查 AstrBot 日志和 Web 面板访问日志获取详细错误信息'
            );
            return;
        }

        if (!data || !data.ok || !data.content) {
            resetBtn();
            Utils.alert(
                '下载失败\n\n' +
                (data && data.msg ? data.msg : '服务端返回了不完整的响应数据') + '\n\n' +
                '可能原因：\n' +
                '- 配置文件内容为空（刚初始化尚未写入配置）\n' +
                '- 服务端读取配置文件时发生 I/O 异常\n' +
                '- 配置文件被外部进程锁定无法读取\n\n' +
                '请检查 AstrBot 日志和 Web 面板访问日志获取详细错误信息'
            );
            return;
        }

        // 构建 Blob 并触发浏览器下载
        const blob = new Blob([data.content], { type: 'application/json; charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename || this._configFileName || 'config.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        resetBtn();
    },

    setConfigPanelOpen(isOpen) {
        this._configPanelOpen = !!isOpen;
        document.body.classList.toggle('config-panel-open', this._configPanelOpen);
        this._updateConfigBadgeVisibility();
    },

    _normalizeHeartbeatSeconds(value, fallback, minValue) {
        const num = Number(value);
        if (!Number.isFinite(num) || num < minValue) return fallback * 1000;
        return Math.round(num) * 1000;
    },

    _buildHeartbeatConfig(config) {
        return {
            visibleIntervalMs: this._normalizeHeartbeatSeconds(
                config.web_panel_heartbeat_visible_interval_seconds,
                300,
                30,
            ),
            hiddenIntervalMs: this._normalizeHeartbeatSeconds(
                config.web_panel_heartbeat_hidden_interval_seconds,
                1200,
                60,
            ),
            retryBaseIntervalMs: this._normalizeHeartbeatSeconds(
                config.web_panel_heartbeat_retry_base_seconds,
                15,
                5,
            ),
            retryMaxIntervalMs: this._normalizeHeartbeatSeconds(
                config.web_panel_heartbeat_retry_max_seconds,
                120,
                15,
            ),
        };
    },

    _createHeartbeatReadonlyRows(cfg, schema) {
        const readonlyKeys = [
            'web_panel_heartbeat_visible_interval_seconds',
            'web_panel_heartbeat_hidden_interval_seconds',
            'web_panel_heartbeat_retry_base_seconds',
            'web_panel_heartbeat_retry_max_seconds',
        ];
        const rows = [];
        readonlyKeys.forEach((key) => {
            const s = schema[key];
            if (!s) return;
            const val = key in cfg ? cfg[key] : (s.default !== undefined ? s.default : '—');
            const displayVal = val === '' ? '（空）' : String(val);
            const desc = (s.description || key).replace(/^[^\s]+\s/, '');
            rows.push(`
                <div class="config-field config-field-readonly" style="max-width:500px;">
                    <div class="config-field-label">🔒 ${desc}</div>
                    <div class="config-field-readonly-value">当前值：${displayVal}</div>
                    <div class="config-field-readonly-note">⚠️ 心跳探测频率属于安全敏感配置，请在 AstrBot 平台插件配置页修改</div>
                </div>`);
        });
        return rows.join('');
    },

    async _loadHeartbeatStatus(isAutoRefresh = false) {
        const loading = document.getElementById('heartbeat-status-loading');
        const content = document.getElementById('heartbeat-status-content');
        if (!loading || !content) return;

        const isFirstLoad = content.classList.contains('hidden');

        const verify = await Api.verify(isAutoRefresh ? { autoRefresh: true } : undefined);
        if (!verify.ok) {
            if (isFirstLoad) loading.textContent = '加载失败';
            return;
        }

        const cfgRes = await Api.getConfig();
        const cfg = cfgRes && cfgRes.ok ? (cfgRes.config || {}) : {};
        const heartbeatCfg = this._buildHeartbeatConfig(cfg);

        // verify 本身就是一次会话有效性确认，成功后同步更新心跳成功时间
        if (verify.ok && this._authMonitor) {
            this._authMonitor.lastHeartbeatSuccessAt = Date.now();
            this._authMonitor.lastHeartbeatStatus = 'ok';
        }

        if (isFirstLoad) loading.classList.add('hidden');

        // 首次渲染：构建完整 DOM
        if (isFirstLoad) {
            content.classList.remove('hidden');
            content.style.display = 'flex';
            this._buildHeartbeatDOM(content, verify, heartbeatCfg);
            // 启动自动刷新
            this._startHeartbeatAutoRefresh(heartbeatCfg);
            // 绑定控件事件
            this._bindHeartbeatControls(heartbeatCfg);
        } else {
            // 增量更新：仅修改变化的 DOM 值
            this._updateHeartbeatDOM(content, verify, heartbeatCfg);
        }

        // 保存上一次数据用于下次对比
        this._heartbeatPrevData = { verify, heartbeatCfg };
    },

    /** 构建心跳状态 DOM（首次渲染） */
    _buildHeartbeatDOM(content, verify, heartbeatCfg) {
        const statusBadgeMap = {
            idle: '<span class="heartbeat-status-badge heartbeat-status-badge--idle">idle（尚未开始）</span>',
            ok: '<span class="heartbeat-status-badge heartbeat-status-badge--ok">ok（正常）</span>',
            retrying: '<span class="heartbeat-status-badge heartbeat-status-badge--retrying">retrying（重试中）</span>',
            invalid: '<span class="heartbeat-status-badge heartbeat-status-badge--invalid">invalid（会话失效）</span>',
            stopped: '<span class="heartbeat-status-badge heartbeat-status-badge--stopped">stopped（已停止）</span>',
        };

        const rows = [
            ['当前会话 ID', verify.session_id || '—', 'hb-sid'],
            ['当前设备 ID', verify.device_id || '—', 'hb-did'],
            ['前台心跳间隔', `${Math.round(heartbeatCfg.visibleIntervalMs / 1000)} 秒`, 'hb-vis-int'],
            ['后台心跳间隔', `${Math.round(heartbeatCfg.hiddenIntervalMs / 1000)} 秒`, 'hb-hid-int'],
            ['失败重试基准', `${Math.round(heartbeatCfg.retryBaseIntervalMs / 1000)} 秒`, 'hb-retry-base'],
            ['失败重试上限', `${Math.round(heartbeatCfg.retryMaxIntervalMs / 1000)} 秒`, 'hb-retry-max'],
            ['当前标签页角色', this._authMonitor?.leader ? '<span class="heartbeat-status-badge heartbeat-status-badge--ok">Leader（负责发心跳）</span>' : '<span class="heartbeat-status-badge heartbeat-status-badge--idle">Follower（仅监听广播）</span>', 'hb-role'],
            ['当前心跳状态', statusBadgeMap[this._authMonitor?.lastHeartbeatStatus || 'idle'] || statusBadgeMap.idle, 'hb-status'],
            ['最近一次心跳成功', this._authMonitor?.lastHeartbeatSuccessAt ? new Date(this._authMonitor.lastHeartbeatSuccessAt).toLocaleString() : '尚未成功', 'hb-last-ok'],
            ['缓冲重试期', (this._authMonitor?.consecutiveNetworkFailures || 0) > 0 ? `<span class="heartbeat-status-badge heartbeat-status-badge--retrying">是（连续失败 ${this._authMonitor.consecutiveNetworkFailures} 次）</span>` : '<span class="heartbeat-status-badge heartbeat-status-badge--ok">否</span>', 'hb-retry'],
            ['会话剩余时间', verify.ttl_seconds != null ? `${verify.ttl_seconds} 秒` : '—', 'hb-ttl'],
        ];

        content.innerHTML = rows.map(([label, value, id]) => `
            <div class="config-field config-field-readonly" style="max-width:500px;" id="${id}">
                <div class="config-field-label">${label}</div>
                <div class="config-field-readonly-value heartbeat-status-value">${value}</div>
            </div>`).join('');
    },

    /** 增量更新心跳状态 DOM */
    _updateHeartbeatDOM(content, verify, heartbeatCfg) {
        const statusBadgeMap = {
            idle: '<span class="heartbeat-status-badge heartbeat-status-badge--idle">idle（尚未开始）</span>',
            ok: '<span class="heartbeat-status-badge heartbeat-status-badge--ok">ok（正常）</span>',
            retrying: '<span class="heartbeat-status-badge heartbeat-status-badge--retrying">retrying（重试中）</span>',
            invalid: '<span class="heartbeat-status-badge heartbeat-status-badge--invalid">invalid（会话失效）</span>',
            stopped: '<span class="heartbeat-status-badge heartbeat-status-badge--stopped">stopped（已停止）</span>',
        };

        const leaderLabel = this._authMonitor?.leader ? '<span class="heartbeat-status-badge heartbeat-status-badge--ok">Leader（负责发心跳）</span>' : '<span class="heartbeat-status-badge heartbeat-status-badge--idle">Follower（仅监听广播）</span>';
        const statusLabel = statusBadgeMap[this._authMonitor?.lastHeartbeatStatus || 'idle'] || statusBadgeMap.idle;
        const lastOk = this._authMonitor?.lastHeartbeatSuccessAt ? new Date(this._authMonitor.lastHeartbeatSuccessAt).toLocaleString() : '尚未成功';
        const retryLabel = (this._authMonitor?.consecutiveNetworkFailures || 0) > 0 ? `<span class="heartbeat-status-badge heartbeat-status-badge--retrying">是（连续失败 ${this._authMonitor.consecutiveNetworkFailures} 次）</span>` : '<span class="heartbeat-status-badge heartbeat-status-badge--ok">否</span>';

        const updates = [
            ['hb-sid', verify.session_id || '—'],
            ['hb-did', verify.device_id || '—'],
            ['hb-vis-int', `${Math.round(heartbeatCfg.visibleIntervalMs / 1000)} 秒`],
            ['hb-hid-int', `${Math.round(heartbeatCfg.hiddenIntervalMs / 1000)} 秒`],
            ['hb-retry-base', `${Math.round(heartbeatCfg.retryBaseIntervalMs / 1000)} 秒`],
            ['hb-retry-max', `${Math.round(heartbeatCfg.retryMaxIntervalMs / 1000)} 秒`],
            ['hb-role', leaderLabel],
            ['hb-status', statusLabel],
            ['hb-last-ok', lastOk],
            ['hb-retry', retryLabel],
            ['hb-ttl', verify.ttl_seconds != null ? `${verify.ttl_seconds} 秒` : '—'],
        ];

        updates.forEach(([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            const valEl = el.querySelector('.heartbeat-status-value');
            if (!valEl) return;
            if (valEl.innerHTML !== val) {
                valEl.innerHTML = val;
                Utils.highlightChange(el);
            }
        });
    },

    /** 启动心跳状态自动刷新定时器（仅首次创建，之后只设标志位）。
     *  定时器一旦创建永不停止——心跳计时必须与配置保持同步，
     *  开关仅控制是否更新 DOM，不清除定时器以免节奏偏移。 */
    _startHeartbeatAutoRefresh(heartbeatCfg) {
        this._heartbeatAutoRefresh = true;
        if (this._heartbeatRefreshTimer) return;
        const intervalMs = Math.max(5000, Math.round(heartbeatCfg.visibleIntervalMs / 2));
        const intervalSec = Math.round(intervalMs / 1000);
        const labelSpan = document.querySelector('#heartbeat-auto-refresh + span');
        if (labelSpan) labelSpan.textContent = `自动刷新（${intervalSec}秒）`;
        this._heartbeatRefreshTimer = setInterval(() => {
            // 每次循环确保标签显示最新间隔（防止 DOM 重建后丢失）
            const span = document.querySelector('#heartbeat-auto-refresh + span');
            if (span) span.textContent = `自动刷新（${intervalSec}秒）`;
            if (this._currentView === 'settings' && this._heartbeatAutoRefresh) {
                this._loadHeartbeatStatus(true);
            }
        }, intervalMs);
    },

    /** 关闭心跳状态自动刷新（仅设标志位，定时器不停） */
    _stopHeartbeatAutoRefresh() {
        this._heartbeatAutoRefresh = false;
    },

    /** 绑定心跳状态控件事件 */
    _bindHeartbeatControls(heartbeatCfg) {
        const manualBtn = document.getElementById('btn-refresh-heartbeat');
        const autoToggle = document.getElementById('heartbeat-auto-refresh');
        const dot = document.getElementById('heartbeat-refresh-dot');

        if (manualBtn && !manualBtn._hbBound) {
            manualBtn._hbBound = true;
            manualBtn.addEventListener('click', async () => {
                manualBtn.disabled = true;
                manualBtn.textContent = '刷新中...';
                try {
                    await this._loadHeartbeatStatus();
                    Utils.toast('心跳状态已刷新', 'success', 2000);
                } catch (e) {
                    Utils.toast('刷新失败', 'error', 3000);
                } finally {
                    manualBtn.disabled = false;
                    manualBtn.textContent = '🔄 刷新';
                }
            });
        }

        if (autoToggle && !autoToggle._hbBound) {
            autoToggle._hbBound = true;
            autoToggle.addEventListener('change', (e) => {
                // 定时器永不停止，仅切换标志位控制 DOM 是否更新
                this._heartbeatAutoRefresh = e.target.checked;
                if (dot) dot.className = 'dot' + (this._heartbeatAutoRefresh ? ' active' : '');
            });
        }
    },

    _redirectToLogin(reason, message, options = {}) {
        Api.clearToken();
        this._authMonitor?.stop?.();
        const { showAlert = true } = options;
        const redirect = () => {
            window.location.href = '/';
        };
        if (!showAlert || !message || typeof Utils === 'undefined') {
            redirect();
            return;
        }
        Utils.alert(message).then(redirect).catch(redirect);
    },

    _installAuthMonitor(config = {}) {
        if (this._authMonitor) return;
        const channelName = 'gcp-auth';
        const tabId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const leaderKey = 'gcp_auth_leader';
        const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(channelName) : null;
        const heartbeatConfig = {
            visibleIntervalMs: config.visibleIntervalMs || 5 * 60 * 1000,
            hiddenIntervalMs: config.hiddenIntervalMs || 20 * 60 * 1000,
            retryBaseIntervalMs: config.retryBaseIntervalMs || 15 * 1000,
            retryMaxIntervalMs: config.retryMaxIntervalMs || 2 * 60 * 1000,
        };
        const monitor = {
            timer: null,
            leaderTimer: null,
            leader: false,
            running: false,
            authenticated: false,
            inFlight: false,
            lastHeartbeatSuccessAt: 0,
            lastHeartbeatStatus: 'idle',
            // 正常巡检频率允许由传统配置项控制；这里只负责应用当前生效值。
            visibleInterval: heartbeatConfig.visibleIntervalMs,
            hiddenInterval: heartbeatConfig.hiddenIntervalMs,
            jitter: 30 * 1000,
            // 网络异常时启用短周期重试，避免一次超时就误判断线。
            retryBaseInterval: heartbeatConfig.retryBaseIntervalMs,
            retryMaxInterval: heartbeatConfig.retryMaxIntervalMs,
            consecutiveNetworkFailures: 0,
            broadcast(type, detail = {}) {
                const payload = { type, detail, tabId, ts: Date.now() };
                if (channel) channel.postMessage(payload);
                try {
                    localStorage.setItem('gcp_auth_event', JSON.stringify(payload));
                } catch (e) {
                    console.warn('广播会话事件失败:', e);
                }
            },
            // 只有 leader 标签页会真正发起心跳；其余标签页只监听结果广播，
            // 避免同一浏览器多标签重复探活、重复重试。
            schedule(immediate = false) {
                clearTimeout(this.timer);
                if (!this.running || !this.leader || !this.authenticated) return;
                let delay;
                if (immediate) {
                    delay = 0;
                } else if (this.consecutiveNetworkFailures > 0) {
                    const retryDelay = this.retryBaseInterval * Math.pow(2, this.consecutiveNetworkFailures - 1);
                    delay = Math.min(retryDelay, this.retryMaxInterval);
                } else {
                    const base = document.visibilityState === 'visible' ? this.visibleInterval : this.hiddenInterval;
                    const jitter = Math.floor(Math.random() * this.jitter);
                    delay = base + jitter;
                }
                this.timer = setTimeout(() => this.ping(), delay);
            },
            startLeaderElection() {
                const renew = () => {
                    const lease = { tabId, expiresAt: Date.now() + 90 * 1000 };
                    try {
                        const raw = localStorage.getItem(leaderKey);
                        const current = raw ? JSON.parse(raw) : null;
                        if (!current || current.expiresAt < Date.now() || current.tabId === tabId) {
                            localStorage.setItem(leaderKey, JSON.stringify(lease));
                            this.becomeLeader();
                        } else if (this.leader) {
                            this.becomeFollower();
                        }
                    } catch (e) {
                        this.becomeLeader();
                    }
                };
                renew();
                this.leaderTimer = setInterval(renew, 30 * 1000);
            },
            becomeLeader() {
                if (this.leader) return;
                this.leader = true;
                this.schedule(true);
            },
            becomeFollower() {
                this.leader = false;
                clearTimeout(this.timer);
            },
            // 心跳失败分两类：
            // 1) 401/会话失效：立即广播并跳登录；
            // 2) 网络/超时：进入缓冲期，按 15s/30s/60s/120s 退避重试，不直接登出。
            async ping() {
                if (!this.running || !this.leader || !this.authenticated || this.inFlight) return;
                this.inFlight = true;
                try {
                    const res = await Api.heartbeat();
                    if (res && res.network_error) {
                        throw new Error(res.msg || 'network_error');
                    }
                    if (!res.ok) {
                        this.lastHeartbeatStatus = 'invalid';
                        this.broadcast('session-invalid', res);
                        App._redirectToLogin(res.reason || 'expired', res.msg || '登录已失效，请重新登录');
                        return;
                    }
                    this.consecutiveNetworkFailures = 0;
                    this.lastHeartbeatSuccessAt = Date.now();
                    this.lastHeartbeatStatus = 'ok';
                    this.broadcast('session-ok', res);
                } catch (error) {
                    this.consecutiveNetworkFailures += 1;
                    this.lastHeartbeatStatus = 'retrying';
                    if (navigator.onLine === false) {
                        Utils.toast('网络已离线，稍后会自动重试', 'warning', 2500);
                    } else if (this.consecutiveNetworkFailures <= 2) {
                        Utils.toast('与服务器连接异常，正在重试', 'warning', 2500);
                    } else if (this.consecutiveNetworkFailures === 3) {
                        Utils.toast('心跳连续失败，已进入缓冲重试期', 'warning', 3000);
                    }
                } finally {
                    this.inFlight = false;
                    this.schedule();
                }
            },
            handleExternalEvent(payload) {
                if (!payload || payload.tabId === tabId) return;
                if (payload.type === 'session-invalid') {
                    const detail = payload.detail || {};
                    App._redirectToLogin(detail.reason || 'expired', detail.msg || '登录已失效，请重新登录');
                }
                if (payload.type === 'logout') {
                    App._redirectToLogin('logout', '您已退出登录', { showAlert: false });
                }
                // Leader 心跳成功后同步状态到 Follower 标签页
                if (payload.type === 'session-ok') {
                    this.lastHeartbeatSuccessAt = Date.now();
                    this.lastHeartbeatStatus = 'ok';
                    this.consecutiveNetworkFailures = 0;
                }
            },
            markAuthenticated() {
                this.authenticated = true;
                this.running = true;
                this.lastHeartbeatStatus = 'ok';
                this.startLeaderElection();
            },
            stop() {
                this.running = false;
                this.authenticated = false;
                this.lastHeartbeatStatus = 'stopped';
                clearTimeout(this.timer);
                clearInterval(this.leaderTimer);
                if (this.leader) {
                    try {
                        const raw = localStorage.getItem(leaderKey);
                        const current = raw ? JSON.parse(raw) : null;
                        if (current && current.tabId === tabId) {
                            localStorage.removeItem(leaderKey);
                        }
                    } catch (e) {
                        console.warn('清理 leader 租约失败:', e);
                    }
                }
                this.leader = false;
            },
        };

        Api.onAuthEvent((event) => {
            if (event.type === 'unauthorized') {
                monitor.broadcast('session-invalid', event);
                App._redirectToLogin(event.reason || 'expired', event.msg || '登录已失效，请重新登录');
            }
        });

        if (channel) {
            channel.onmessage = (event) => monitor.handleExternalEvent(event.data);
        }
        window.addEventListener('storage', (event) => {
            if (event.key === 'gcp_auth_event' && event.newValue) {
                try {
                    monitor.handleExternalEvent(JSON.parse(event.newValue));
                } catch (e) {
                    console.warn('解析跨标签认证事件失败:', e);
                }
            }
            if (event.key === leaderKey && event.newValue) {
                try {
                    const current = JSON.parse(event.newValue);
                    if (current.tabId !== tabId && monitor.leader) {
                        monitor.becomeFollower();
                    }
                } catch (e) {
                    console.warn('解析 leader 租约失败:', e);
                }
            }
        });
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && monitor.leader && monitor.authenticated) {
                monitor.schedule(true);
            }
        });
        window.addEventListener('online', () => {
            if (monitor.leader && monitor.authenticated) {
                monitor.schedule(true);
            }
        });
        window.addEventListener('beforeunload', () => {
            if (monitor.authenticated) {
                monitor.broadcast('tab-leave');
            }
        });
        this._authMonitor = monitor;
    }
};

// 启动应用
document.addEventListener('DOMContentLoaded', () => App.start());

// 移动端：虚拟键盘弹出时确保焦点元素可见
(function() {
    if (!window.visualViewport) return;

    let pendingScroll = null;
    window.visualViewport.addEventListener('resize', () => {
        if (window.innerWidth >= 768) return;
        const active = document.activeElement;
        if (!active) return;
        const tag = active.tagName.toLowerCase();
        if (tag !== 'textarea' && tag !== 'input') return;

        clearTimeout(pendingScroll);
        pendingScroll = setTimeout(() => {
            const vpH = window.visualViewport.height;
            const rect = active.getBoundingClientRect();
            if (rect.bottom > vpH * 0.9 || rect.top > vpH * 0.35) {
                active.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
            }
        }, 200);
    });
})();
