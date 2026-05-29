/**
 * session-mgr.js - 会话管理 UI（增强版）
 * 统一会话列表（内存+文件）、分页详情、自动刷新、聊天记录编辑
 */

const SessionMgr = {
    _sessions: [],
    _currentSession: null,
    _detailPoller: null,
    _listPoller: null,
    _prevDetail: null, // 上一次的详情数据，用于变化高亮
    _autoRefresh: true,
    _listAutoRefresh: true,

    /** 初始化会话管理视图 */
    async init() {
        this._currentSession = null;
        if (this._detailPoller) { this._detailPoller.stop(); this._detailPoller = null; }
        if (this._listPoller) { this._listPoller.stop(); this._listPoller = null; }
        document.getElementById('session-detail').classList.add('hidden');
        document.getElementById('session-list-container').classList.remove('hidden');
        await this._loadSessions();
        this._startListAutoRefresh();
    },

    /** 销毁（切换视图时调用） */
    destroy() {
        if (this._detailPoller) { this._detailPoller.stop(); this._detailPoller = null; }
        if (this._listPoller) { this._listPoller.stop(); this._listPoller = null; }
    },

    /** 启动列表自动刷新 */
    _startListAutoRefresh() {
        if (this._listPoller) this._listPoller.stop();
        if (this._listAutoRefresh) {
            this._listPoller = Utils.createPoller(() => this._refreshListData(), 3000);
            this._listPoller.start();
        }
    },

    /** 停止列表自动刷新 */
    _stopListAutoRefresh() {
        if (this._listPoller) { this._listPoller.stop(); this._listPoller = null; }
    },

    /** 仅刷新列表数据（自动刷新用，不重建头部控件） */
    async _refreshListData() {
        const res = await Api.sessionList();
        if (!res.ok) return;
        const sessionsObj = res.sessions || {};
        this._sessions = Object.entries(sessionsObj).map(([id, meta]) => ({
            id,
            message_count: meta.message_count || 0,
            last_active: meta.last_modified || 0,
            file_size: meta.file_size || 0,
            error: meta.error || false,
            has_file: meta.has_file !== false,
            has_runtime_data: meta.has_runtime_data || false,
        }));
        this._sessions.sort((a, b) => {
            if (a.has_runtime_data !== b.has_runtime_data) return b.has_runtime_data ? 1 : -1;
            if (a.last_active !== b.last_active) return b.last_active - a.last_active;
            return a.id.localeCompare(b.id);
        });
        // 更新计数
        const countEl = document.getElementById('session-list-count');
        if (countEl) countEl.textContent = `共 ${this._sessions.length} 个会话`;
        // 更新清理按钮
        const cleanupWrap = document.getElementById('session-cleanup-wrap');
        if (cleanupWrap) {
            const ghostCount = this._sessions.filter(s => !s.has_runtime_data && s.has_file).length;
            cleanupWrap.innerHTML = '';
            if (ghostCount > 0) {
                const cleanupBtn = document.createElement('button');
                cleanupBtn.className = 'btn btn-sm btn-danger';
                cleanupBtn.textContent = `清理孤立记录 (${ghostCount})`;
                cleanupBtn.title = '删除没有对应运行时状态的会话文件';
                cleanupBtn.addEventListener('click', () => this._cleanupGhostSessions());
                cleanupWrap.appendChild(cleanupBtn);
            }
        }
        // 更新列表项
        const itemsContainer = document.getElementById('session-list-items');
        if (itemsContainer) this._renderListItems(itemsContainer);
    },

    /** 加载会话列表（合并内存+文件） */
    async _loadSessions() {
        const container = document.getElementById('session-list-container');
        if (!container) return;
        container.innerHTML = '<div class="chart-empty">加载中...</div>';

        const res = await Api.sessionList();
        if (!res.ok) {
            container.innerHTML = '<div class="chart-empty">加载失败</div>';
            return;
        }

        const sessionsObj = res.sessions || {};
        this._sessions = Object.entries(sessionsObj).map(([id, meta]) => ({
            id,
            message_count: meta.message_count || 0,
            last_active: meta.last_modified || 0,
            file_size: meta.file_size || 0,
            error: meta.error || false,
            has_file: meta.has_file !== false,
            has_runtime_data: meta.has_runtime_data || false,
        }));

        // 排序：有运行时数据的优先，然后按最后活跃时间降序
        this._sessions.sort((a, b) => {
            if (a.has_runtime_data !== b.has_runtime_data) return b.has_runtime_data ? 1 : -1;
            if (a.last_active !== b.last_active) return b.last_active - a.last_active;
            return a.id.localeCompare(b.id);
        });

        this._renderList(container);
    },

    /** 渲染会话列表 */
    _renderList(container) {
        container.innerHTML = '';

        // 列表头部：自动刷新 + 按钮组
        const header = document.createElement('div');
        header.style.cssText = 'display:flex;flex-direction:column;gap:8px;padding:16px 24px 8px;';

        const headerTop = document.createElement('div');
        headerTop.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;';

        // 左侧：自动刷新开关
        const leftGroup = document.createElement('div');
        leftGroup.style.cssText = 'display:flex;align-items:center;gap:8px;';
        const refreshToggle = document.createElement('label');
        refreshToggle.className = 'auto-refresh-toggle';
        refreshToggle.innerHTML = `
            <span class="dot ${this._listAutoRefresh ? 'active' : ''}" id="list-refresh-dot"></span>
            <input type="checkbox" ${this._listAutoRefresh ? 'checked' : ''} id="list-auto-refresh">
            <span>自动刷新（3秒）</span>`;
        refreshToggle.querySelector('#list-auto-refresh').addEventListener('change', (e) => {
            this._listAutoRefresh = e.target.checked;
            const dot = document.getElementById('list-refresh-dot');
            if (dot) dot.className = 'dot' + (this._listAutoRefresh ? ' active' : '');
            if (this._listAutoRefresh) {
                this._startListAutoRefresh();
            } else {
                this._stopListAutoRefresh();
            }
        });
        leftGroup.appendChild(refreshToggle);

        // 清理孤立记录按钮占位
        const cleanupWrap = document.createElement('span');
        cleanupWrap.id = 'session-cleanup-wrap';
        cleanupWrap.style.cssText = 'display:contents;';
        leftGroup.appendChild(cleanupWrap);

        // 计数
        const countSpan = document.createElement('span');
        countSpan.id = 'session-list-count';
        countSpan.style.cssText = 'font-size:13px;color:var(--text-muted);';
        countSpan.textContent = `共 ${this._sessions.length} 个会话`;

        headerTop.appendChild(leftGroup);

        // 右侧：计数 + 刷新列表按钮
        const btnGroup = document.createElement('div');
        btnGroup.style.cssText = 'display:flex;align-items:center;gap:8px;';

        btnGroup.appendChild(countSpan);

        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'btn btn-sm';
        refreshBtn.textContent = '刷新列表';
        refreshBtn.addEventListener('click', () => this._loadSessions());
        btnGroup.appendChild(refreshBtn);
        headerTop.appendChild(btnGroup);

        header.appendChild(headerTop);

        const storageHint = document.createElement('div');
        storageHint.style.cssText = 'font-size:12px;color:var(--text-secondary);line-height:1.7;';
        storageHint.innerHTML = '同一批真实会话的两种表示：<strong>聊天记录文件</strong>来自 <code>chat_history/...</code>，<strong>运行时状态</strong>来自当前内存。「重置」按钮仅清除运行时状态（注意力、情绪、概率等），<strong>不会删除聊天记录文件</strong>；重置后插件自动重载使清理生效。「清理孤立记录」仅删除没有对应运行时状态的残留文件。';
        header.appendChild(storageHint);
        container.appendChild(header);

        // 清理按钮初始渲染
        const ghostCount = this._sessions.filter(s => !s.has_runtime_data && s.has_file).length;
        if (ghostCount > 0) {
            const cleanupBtn = document.createElement('button');
            cleanupBtn.className = 'btn btn-sm btn-danger';
            cleanupBtn.textContent = `清理孤立记录 (${ghostCount})`;
            cleanupBtn.title = '删除没有对应运行时状态的会话文件';
            cleanupBtn.addEventListener('click', () => this._cleanupGhostSessions());
            cleanupWrap.appendChild(cleanupBtn);
        }

        // 列表项容器
        const listWrap = document.createElement('div');
        listWrap.id = 'session-list-items';
        listWrap.style.cssText = 'padding:0 24px 24px;';
        container.appendChild(listWrap);

        if (!this._sessions.length) {
            listWrap.innerHTML = '<div class="chart-empty" style="padding:40px;">暂无会话数据</div>';
            return;
        }

        this._renderListItems(listWrap);
    },

    /** 仅渲染会话卡片列表（首次加载和自动刷新复用） */
    _renderListItems(container) {
        container.innerHTML = '';
        if (!this._sessions.length) {
            container.innerHTML = '<div class="chart-empty" style="padding:40px;">暂无会话数据</div>';
            return;
        }

        this._sessions.forEach(s => {
            const card = document.createElement('div');
            card.className = 'session-card';

            const info = document.createElement('div');
            info.className = 'session-card-info';

            let metaParts = [];
            if (s.message_count) metaParts.push(`${s.message_count} 条消息`);
            if (s.file_size) metaParts.push(Utils.formatSize(s.file_size));
            if (s.last_active) metaParts.push(Utils.formatTime(s.last_active));

            info.innerHTML = `
                <span class="session-card-id">${Utils.escapeHtml(s.id)}</span>
                <span class="session-card-meta">${metaParts.join(' · ') || '无文件数据'}</span>
                <div class="session-card-badges">
                    ${s.has_runtime_data ? '<span class="session-badge badge-runtime">运行中</span>' : ''}
                    ${s.has_file ? '<span class="session-badge badge-file">有记录</span>' : ''}
                    ${s.error ? '<span class="session-badge" style="background:rgba(231,76,60,0.15);color:var(--accent-red);">错误</span>' : ''}
                </div>`;

            const actions = document.createElement('div');
            actions.className = 'session-card-actions';

            const viewBtn = document.createElement('button');
            viewBtn.className = 'btn btn-sm';
            viewBtn.textContent = '查看';
            viewBtn.addEventListener('click', e => {
                e.stopPropagation();
                this._showDetail(s.id);
            });

            const resetBtn = document.createElement('button');
            resetBtn.className = 'btn btn-sm btn-danger';
            resetBtn.textContent = '重置';
            resetBtn.addEventListener('click', async e => {
                e.stopPropagation();
                await this._resetSession(s.id);
            });

            actions.appendChild(viewBtn);
            actions.appendChild(resetBtn);
            card.appendChild(info);
            card.appendChild(actions);

            card.addEventListener('click', () => this._showDetail(s.id));
            container.appendChild(card);
        });
    },

    /** 显示会话详情（分页视图） */
    async _showDetail(sessionId) {
        this._currentSession = sessionId;
        this._prevDetail = null;
        // 暂停列表自动刷新
        this._stopListAutoRefresh();
        const detail = document.getElementById('session-detail');
        const listContainer = document.getElementById('session-list-container');
        detail.classList.remove('hidden');
        listContainer.classList.add('hidden');

        detail.innerHTML = '<div class="chart-empty">加载中...</div>';
        const loadOk = await this._refreshDetail(sessionId);

        if (!loadOk) {
            detail.innerHTML = `<div style="padding:24px;">
                <div class="chart-empty" style="margin-bottom:16px;">加载会话数据失败</div>
                <div style="display:flex;gap:8px;justify-content:center;">
                    <button class="btn btn-sm" id="detail-retry-btn">重试</button>
                    <button class="btn btn-sm" id="detail-back-btn">← 返回</button>
                </div></div>`;
            document.getElementById('detail-retry-btn')?.addEventListener(
                'click', () => this._showDetail(sessionId)
            );
            document.getElementById('detail-back-btn')?.addEventListener(
                'click', () => this._backToList()
            );
            return;
        }

        // 启动自动刷新
        if (this._detailPoller) this._detailPoller.stop();
        if (this._autoRefresh) {
            this._detailPoller = Utils.createPoller(
                () => this._refreshDetail(sessionId, { autoRefresh: true }), 3000
            );
            this._detailPoller.start();
        }
    },

    /** 刷新详情数据，返回是否成功 */
    async _refreshDetail(sessionId, options = {}) {
        if (this._currentSession !== sessionId) return false;

        try {
            const res = await Api.sessionDetail(sessionId, options);
            if (!res.ok || !res.detail) {
                // 自动刷新静默跳过（插件重启等场景），手动刷新由调用方处理反馈
                if (!options.autoRefresh) console.error('SessionMgr: sessionDetail failed', res);
                return false;
            }
            const d = res.detail;

            const detail = document.getElementById('session-detail');
            const prevData = this._prevDetail;
            this._prevDetail = d;

            // 如果是首次渲染，构建完整 DOM
            if (!prevData) {
                this._buildDetailDOM(detail, d, sessionId);
            } else {
                this._updateDetailData(detail, d, prevData);
            }
            return true;
        } catch (e) {
            console.error('SessionMgr: refreshDetail error', e);
            return false;
        }
    },

    /** 构建详情 DOM */
    _buildDetailDOM(container, d, sessionId) {
        container.innerHTML = '';
        container.style.cssText = 'padding:24px;overflow-y:auto;display:flex;flex-direction:column;min-height:0;height:100%;';

        // 头部
        const header = document.createElement('div');
        header.className = 'detail-header';
        header.innerHTML = `<h3>${Utils.escapeHtml(sessionId)}</h3>`;

        const headerActions = document.createElement('div');
        headerActions.className = 'detail-header-actions';

        // 自动刷新开关
        const refreshToggle = document.createElement('label');
        refreshToggle.className = 'auto-refresh-toggle';
        refreshToggle.innerHTML = `
            <span class="dot ${this._autoRefresh ? 'active' : ''}" id="refresh-dot"></span>
            <input type="checkbox" ${this._autoRefresh ? 'checked' : ''} id="auto-refresh-cb">
            <span>自动刷新（3秒）</span>`;
        refreshToggle.querySelector('#auto-refresh-cb').addEventListener('change', (e) => {
            this._autoRefresh = e.target.checked;
            document.getElementById('refresh-dot').className = 'dot' + (this._autoRefresh ? ' active' : '');
            if (this._autoRefresh) {
                if (this._detailPoller) this._detailPoller.stop();
                this._detailPoller = Utils.createPoller(
                    () => this._refreshDetail(sessionId, { autoRefresh: true }), 3000
                );
                this._detailPoller.start();
            } else {
                if (this._detailPoller) { this._detailPoller.stop(); this._detailPoller = null; }
            }
        });

        const manualRefresh = document.createElement('button');
        manualRefresh.className = 'btn btn-sm';
        manualRefresh.textContent = '刷新';
        manualRefresh.addEventListener('click', async () => {
            manualRefresh.disabled = true;
            manualRefresh.textContent = '刷新中...';
            const ok = await this._refreshDetail(sessionId);
            // 手动刷新时强制全量重载聊天记录（编辑模式下跳过）
            const historyTab = document.getElementById('tab-history');
            if (this._historyLoaded && historyTab && !historyTab.querySelector('.file-editor--history')) {
                this._loadChatHistory(sessionId);
            }
            manualRefresh.disabled = false;
            manualRefresh.textContent = '刷新';
            if (ok) {
                Utils.toast('会话数据已刷新', 'success', 2000);
            } else {
                Utils.toast('刷新失败', 'error', 3000);
            }
        });

        const backBtn = document.createElement('button');
        backBtn.className = 'btn btn-sm';
        backBtn.textContent = '\u2190 返回';
        backBtn.addEventListener('click', () => this._backToList());

        headerActions.appendChild(refreshToggle);
        headerActions.appendChild(manualRefresh);
        headerActions.appendChild(backBtn);
        header.appendChild(headerActions);
        container.appendChild(header);

        // 详情头部说明
        const storageHint = document.createElement('div');
        storageHint.style.cssText = 'font-size:12px;color:var(--text-secondary);line-height:1.7;margin-bottom:12px;';
        storageHint.innerHTML = '本页会把<strong>插件自定义聊天记录文件</strong>与<strong>当前运行时状态</strong>合并展示；官方存储仍会同步写入，并在部分场景作为历史读取回退，因此正常情况下这些信息应属于同一个会话。';
        container.appendChild(storageHint);

        // 概览卡片
        const cards = document.createElement('div');
        cards.className = 'detail-cards';
        cards.id = 'detail-overview-cards';
        this._renderOverviewCards(cards, d);
        container.appendChild(cards);

        // Tab 栏
        const tabBar = document.createElement('div');
        tabBar.className = 'tab-bar';
        const tabs = [
            { id: 'attention', label: '注意力' },
            { id: 'probability', label: '概率' },
            { id: 'proactive', label: '主动对话' },
            { id: 'runtime', label: '运行时状态' },
            { id: 'history', label: '聊天记录' },
        ];
        tabs.forEach((t, i) => {
            const tab = document.createElement('div');
            tab.className = 'tab-item' + (i === 0 ? ' active' : '');
            tab.textContent = t.label;
            tab.dataset.tab = t.id;
            tab.addEventListener('click', () => {
                tabBar.querySelectorAll('.tab-item').forEach(ti => ti.classList.remove('active'));
                tab.classList.add('active');
                container.querySelectorAll('.tab-content').forEach(tc => tc.classList.add('hidden'));
                document.getElementById(`tab-${t.id}`).classList.remove('hidden');
                if (t.id === 'history' && !this._historyLoaded) {
                    this._loadChatHistory(sessionId);
                }
            });
            tabBar.appendChild(tab);
        });
        container.appendChild(tabBar);

        // Tab 内容
        const tabAttention = document.createElement('div');
        tabAttention.className = 'tab-content';
        tabAttention.id = 'tab-attention';
        this._renderAttentionTab(tabAttention, d);
        container.appendChild(tabAttention);

        const tabProb = document.createElement('div');
        tabProb.className = 'tab-content hidden';
        tabProb.id = 'tab-probability';
        this._renderProbabilityTab(tabProb, d);
        container.appendChild(tabProb);

        const tabProactive = document.createElement('div');
        tabProactive.className = 'tab-content hidden';
        tabProactive.id = 'tab-proactive';
        this._renderProactiveTab(tabProactive, d);
        container.appendChild(tabProactive);

        const tabRuntime = document.createElement('div');
        tabRuntime.className = 'tab-content hidden';
        tabRuntime.id = 'tab-runtime';
        this._renderRuntimeTab(tabRuntime, d);
        container.appendChild(tabRuntime);

        const tabHistory = document.createElement('div');
        tabHistory.className = 'tab-content hidden';
        tabHistory.id = 'tab-history';
        tabHistory.innerHTML = '<div class="chart-empty">点击此标签加载聊天记录</div>';
        this._historyLoaded = false;
        container.appendChild(tabHistory);
    },

    /** 渲染概览卡片 */
    _renderOverviewCards(container, d) {
        const mood = d.mood || {};
        const density = d.reply_density || {};
        const activity = d.conversation_activity || {};
        const items = [
            { label: '追踪用户', value: d.attention?.user_count || 0, id: 'ov-users' },
            { label: '当前情绪', value: mood.current_mood || '无', id: 'ov-mood' },
            { label: '情绪强度', value: typeof mood.intensity === 'number' ? mood.intensity.toFixed(2) : '-', id: 'ov-intensity' },
            { label: '消息缓存', value: d.message_cache_count || 0, id: 'ov-cache' },
            { label: '处理中', value: d.is_processing ? '是' : '否', id: 'ov-processing' },
            { label: '主动处理', value: d.proactive_processing ? '是' : '否', id: 'ov-pro-proc' },
            { label: '等待窗口', value: (d.wait_windows || []).length, id: 'ov-wait' },
            { label: '正式冷却', value: (d.cooldowns || []).length, id: 'ov-cooldown' },
            { label: '待冷却', value: (d.pending_cooldowns || []).length, id: 'ov-pending-cooldown' },
            { label: '疲劳锁定', value: (d.fatigue_blocks || []).length, id: 'ov-fatigue' },
            { label: '回复密度', value: density.reply_count !== undefined ? `${density.reply_count}/${density.max_replies || '-'}` : '-', id: 'ov-density' },
            { label: '活跃度', value: typeof activity.activity_score === 'number' ? activity.activity_score.toFixed(2) : '-', id: 'ov-activity' },
            { label: '记录文件', value: d.chat_history_file?.exists ? Utils.formatSize(d.chat_history_file.file_size || 0) : '无', id: 'ov-file' },
        ];
        container.innerHTML = '';
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'detail-card';
            card.id = item.id;
            card.innerHTML = `<div class="stat-value">${Utils.escapeHtml(String(item.value))}</div>
                <div class="stat-label">${item.label}</div>`;
            container.appendChild(card);
        });
    },

    /** 渲染注意力标签页 */
    _renderAttentionTab(container, d) {
        const users = d.attention?.users || [];
        container.innerHTML = '';
        if (!users.length) {
            container.innerHTML = '<div class="chart-empty">暂无注意力数据</div>';
            return;
        }
        const table = document.createElement('table');
        table.className = 'data-table';
        table.id = 'attention-table';
        table.innerHTML = `<thead><tr>
            <th>用户</th><th>注意力</th><th>情感</th><th>交互次</th><th>空闲</th><th>最近消息</th>
        </tr></thead>`;
        const tbody = document.createElement('tbody');
        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.dataset.uid = u.user_id;
            const pct = Math.min(100, Math.round((u.attention_score || 0) * 100));
            tr.innerHTML = `
                <td style="font-family:monospace;font-size:11px;">${Utils.escapeHtml(u.user_id)}</td>
                <td><div class="gauge-bar" style="width:80px;"><div class="gauge-bar-fill" style="width:${pct}%"></div></div>
                    <span style="font-size:10px;margin-left:4px;">${(u.attention_score||0).toFixed(2)}</span></td>
                <td>${(u.emotion||0).toFixed(2)}</td>
                <td>${u.interaction_count||0}</td>
                <td>${Utils.formatDuration(u.idle_seconds||0)}</td>
                <td><span style="display:block;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${Utils.escapeHtml(Utils.truncate(u.preview||'', 40))}</span></td>`;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        container.appendChild(table);
    },

    /** 渲染概率标签页 */
    _renderProbabilityTab(container, d) {
        const p = d.probability || {};
        container.innerHTML = '';

        const isTraditional = (p.mode || 'traditional') === 'traditional';
        const modeLabel = isTraditional ? '传统模式' : '注意力模式';

        const items = [
            { label: '基础概率', value: p.initial_probability, color: '' },
        ];
        if (isTraditional) {
            items.push({ label: '回复后概率', value: p.after_reply_probability, color: 'green' });
        }
        if (p.frequency_adjusted_probability !== undefined) {
            items.push({ label: '频率调整后', value: p.frequency_adjusted_probability, color: 'orange' });
        }
        if (p.temp_boost) {
            items.push({
                label: `临时提升 (${p.temp_boost.remaining_seconds}s)`,
                value: p.temp_boost.value, color: 'purple'
            });
        }

        const note = document.createElement('div');
        note.style.cssText = 'font-size:12px;color:var(--text-secondary);margin-bottom:10px;line-height:1.6;';
        note.innerHTML = isTraditional
            ? `当前为<strong>${modeLabel}</strong>：成功回复后会在 <strong>${p.probability_duration || 0}s</strong> 内为整个会话临时提高概率；该提升不区分用户，并且再次成功回复会刷新计时。`
            : `当前为<strong>${modeLabel}</strong>：回复后概率提升已由注意力机制接管，<strong>after_reply_probability</strong> 不再参与当前会话计算。`;
        container.appendChild(note);

        const grid = document.createElement('div');
        grid.id = 'prob-grid';
        grid.style.cssText = 'display:flex;flex-direction:column;gap:12px;';
        items.forEach(item => {
            const row = document.createElement('div');
            const pct = Math.min(100, Math.round((item.value || 0) * 100));
            row.innerHTML = `
                <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
                    <span>${item.label}</span>
                    <span style="font-weight:600;">${pct}%</span>
                </div>
                <div class="gauge-bar" style="height:12px;">
                    <div class="gauge-bar-fill ${item.color}" style="width:${pct}%"></div>
                </div>`;
            grid.appendChild(row);
        });
        container.appendChild(grid);
    },

    /** 渲染主动对话标签页 */
    _renderProactiveTab(container, d) {
        const p = d.proactive || {};
        container.innerHTML = '';

        if (!Object.keys(p).length) {
            container.innerHTML = '<div class="chart-empty">暂无主动对话数据</div>';
            return;
        }

        const isActive = p.proactive_active || false;
        const cooldown = p.cooldown_remaining || 0;
        const totalSuccess = p.successful_interactions || 0;
        const totalFailure = p.failed_interactions || 0;
        const total = totalSuccess + totalFailure;
        const rate = total > 0 ? ((totalSuccess / total) * 100).toFixed(1) : '0.0';
        const score = typeof p.interaction_score === 'number' ? p.interaction_score.toFixed(1) : '-';

        const wrap = document.createElement('div');
        wrap.id = 'proactive-data';
        wrap.innerHTML = `
            <div class="detail-cards" style="margin-bottom:16px;">
                <div class="detail-card">
                    <div class="stat-value">${isActive ? '<span style="color:var(--accent-green);">活跃</span>' : '<span style="color:var(--text-muted);">不活跃</span>'}</div>
                    <div class="stat-label">状态</div>
                </div>
                <div class="detail-card">
                    <div class="stat-value">${cooldown > 0 ? Utils.formatDuration(cooldown) : '无'}</div>
                    <div class="stat-label">冷却剩余</div>
                </div>
                <div class="detail-card">
                    <div class="stat-value">${totalSuccess}</div>
                    <div class="stat-label">成功次数</div>
                </div>
                <div class="detail-card">
                    <div class="stat-value">${totalFailure}</div>
                    <div class="stat-label">失败次数</div>
                </div>
                <div class="detail-card">
                    <div class="stat-value">${rate}%</div>
                    <div class="stat-label">成功率</div>
                </div>
                <div class="detail-card">
                    <div class="stat-value">${score}</div>
                    <div class="stat-label">交互评分</div>
                </div>
            </div>`;
        container.appendChild(wrap);
    },

    /** 渲染运行时状态标签页 */
    _renderRuntimeTab(container, d) {
        container.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.id = 'runtime-data';
        wrap.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

        // 消息缓存
        const cacheSection = document.createElement('div');
        const cacheMessages = d.message_cache || [];
        cacheSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">消息缓存 (${cacheMessages.length})</h4>`;
        if (cacheMessages.length) {
            const cacheList = document.createElement('div');
            cacheList.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
            cacheMessages.forEach(m => {
                const item = document.createElement('div');
                item.style.cssText = 'padding:6px 10px;background:var(--bg-tertiary);border-radius:6px;font-size:12px;';
                const time = m.timestamp ? Utils.formatTime(m.timestamp) : '';
                item.innerHTML = `<span style="color:var(--accent-red);margin-right:8px;">${Utils.escapeHtml(m.sender_name || m.role || '?')}</span>` +
                    `<span>${Utils.escapeHtml(m.content || '')}</span>` +
                    (time ? `<span style="float:right;color:var(--text-muted);font-size:10px;">${time}</span>` : '');
                cacheList.appendChild(item);
            });
            cacheSection.appendChild(cacheList);
        } else {
            cacheSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无待处理缓存消息</div>';
        }
        wrap.appendChild(cacheSection);

        // 等待窗口
        const waitWindows = d.wait_windows || [];
        const waitSection = document.createElement('div');
        waitSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">等待窗口 (${waitWindows.length})</h4>`;
        if (waitWindows.length) {
            const waitList = document.createElement('div');
            waitList.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
            waitWindows.forEach(w => {
                const item = document.createElement('div');
                item.style.cssText = 'padding:6px 10px;background:var(--bg-tertiary);border-radius:6px;font-size:12px;display:flex;justify-content:space-between;';
                item.innerHTML = `<span>用户: ${Utils.escapeHtml(w.user_id)}</span>` +
                    `<span>额外消息: ${w.extra_count}</span>` +
                    `<span>剩余: ${w.remaining}s</span>`;
                waitList.appendChild(item);
            });
            waitSection.appendChild(waitList);
        } else {
            waitSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无活跃等待窗口</div>';
        }
        wrap.appendChild(waitSection);

        // 正式冷却 / 待冷却
        const cooldowns = d.cooldowns || [];
        const pendingCooldowns = d.pending_cooldowns || [];
        const coolSection = document.createElement('div');
        coolSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">正式冷却用户 (${cooldowns.length})</h4>`;
        coolSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">正式冷却会冻结该用户的注意力增长；若用户已不在注意力追踪列表中，会被自动移出冷却名单。</div>';
        if (cooldowns.length) {
            const table = document.createElement('table');
            table.className = 'data-table';
            table.innerHTML = `<thead><tr><th>用户</th><th>名称</th><th>剩余</th><th>原因</th></tr></thead>`;
            const tbody = document.createElement('tbody');
            cooldowns.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td style="font-family:monospace;font-size:11px;">${Utils.escapeHtml(c.user_id)}</td>` +
                    `<td>${Utils.escapeHtml(c.user_name || '-')}</td>` +
                    `<td>${Utils.formatDuration(c.remaining || 0)}</td>` +
                    `<td>${Utils.escapeHtml(c.reason || '-')}</td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            coolSection.appendChild(table);
        } else {
            coolSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无正式冷却用户</div>';
        }
        wrap.appendChild(coolSection);

        const pendingSection = document.createElement('div');
        pendingSection.innerHTML = `<h4 style="margin:12px 0 8px;font-size:13px;color:var(--text-secondary);">待冷却用户 (${pendingCooldowns.length})</h4>`;
        pendingSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">待冷却只观察同一用户自己的后续消息；如果该用户已经不在注意力追踪列表中，会直接从待冷却名单移除，不再推进到正式冷却。</div>';
        if (pendingCooldowns.length) {
            const table = document.createElement('table');
            table.className = 'data-table';
            table.innerHTML = `<thead><tr><th>用户</th><th>名称</th><th>剩余</th><th>观察</th><th>原因</th></tr></thead>`;
            const tbody = document.createElement('tbody');
            pendingCooldowns.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td style="font-family:monospace;font-size:11px;">${Utils.escapeHtml(c.user_id)}</td>` +
                    `<td>${Utils.escapeHtml(c.user_name || '-')}</td>` +
                    `<td>${Utils.formatDuration(c.remaining || 0)}</td>` +
                    `<td>${Utils.escapeHtml(`${c.consumed_user_messages || 0}/${c.grace_message_budget || 0}`)}</td>` +
                    `<td>${Utils.escapeHtml(c.reason || '-')}</td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            pendingSection.appendChild(table);
        } else {
            pendingSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无待冷却用户</div>';
        }
        wrap.appendChild(pendingSection);

        // 疲劳锁定
        const fatigueBlocks = d.fatigue_blocks || [];
        const fatigueSection = document.createElement('div');
        fatigueSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">疲劳锁定 (${fatigueBlocks.length})</h4>`;
        if (fatigueBlocks.length) {
            const table = document.createElement('table');
            table.className = 'data-table';
            table.innerHTML = `<thead><tr><th>用户</th><th>疲劳等级</th><th>锁定时间</th></tr></thead>`;
            const tbody = document.createElement('tbody');
            fatigueBlocks.forEach(f => {
                const tr = document.createElement('tr');
                const levelColor = f.fatigue_level === 'heavy' ? 'var(--accent-red)' :
                    f.fatigue_level === 'medium' ? 'var(--accent-orange)' : 'var(--text-muted)';
                tr.innerHTML = `<td style="font-family:monospace;font-size:11px;">${Utils.escapeHtml(f.user_id)}</td>` +
                    `<td><span style="color:${levelColor};">${Utils.escapeHtml(f.fatigue_level || '-')}</span></td>` +
                    `<td>${f.blocked_at ? Utils.formatTime(f.blocked_at) : '-'}</td>`;
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            fatigueSection.appendChild(table);
        } else {
            fatigueSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无疲劳锁定</div>';
        }
        wrap.appendChild(fatigueSection);

        // 回复密度
        const density = d.reply_density || {};
        const densitySection = document.createElement('div');
        densitySection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">回复密度</h4>`;
        if (Object.keys(density).length) {
            const ratio = density.density_ratio || 0;
            const pct = Math.min(100, Math.round(ratio * 100));
            densitySection.innerHTML += `
                <div style="display:flex;gap:16px;font-size:12px;margin-bottom:8px;">
                    <span>窗口回复: ${density.reply_count || 0} / ${density.max_replies || '-'}</span>
                    <span>窗口: ${density.window_minutes || '-'} 分钟</span>
                    <span>密度: ${(ratio * 100).toFixed(1)}%</span>
                </div>
                <div class="gauge-bar" style="height:10px;">
                    <div class="gauge-bar-fill ${pct > 80 ? 'red' : pct > 50 ? 'orange' : ''}" style="width:${pct}%"></div>
                </div>`;
        } else {
            densitySection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无回复密度数据</div>';
        }
        wrap.appendChild(densitySection);

        // 会话活跃度
        const activity = d.conversation_activity || {};
        const actSection = document.createElement('div');
        actSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">会话活跃度</h4>`;
        if (Object.keys(activity).length) {
            actSection.innerHTML += `
                <div class="detail-cards" style="margin:0;">
                    <div class="detail-card">
                        <div class="stat-value">${(activity.activity_score || 0).toFixed(2)}</div>
                        <div class="stat-label">活跃度</div>
                    </div>
                    <div class="detail-card">
                        <div class="stat-value">${Utils.escapeHtml(activity.peak_user_name || activity.peak_user_id || '-')}</div>
                        <div class="stat-label">最高注意力用户</div>
                    </div>
                    <div class="detail-card">
                        <div class="stat-value">${(activity.peak_attention || 0).toFixed(2)}</div>
                        <div class="stat-label">最高注意力</div>
                    </div>
                    <div class="detail-card">
                        <div class="stat-value">${activity.last_bot_reply ? Utils.formatTime(activity.last_bot_reply) : '-'}</div>
                        <div class="stat-label">最后回复</div>
                    </div>
                </div>`;
        } else {
            actSection.innerHTML += '<div style="font-size:12px;color:var(--text-muted);">无活跃度数据</div>';
        }
        wrap.appendChild(actSection);

        // 最近回复缓存
        const recentCount = d.recent_replies_count || 0;
        const recentSection = document.createElement('div');
        recentSection.innerHTML = `<h4 style="margin:0 0 8px;font-size:13px;color:var(--text-secondary);">其他状态</h4>`;
        recentSection.innerHTML += `<div style="font-size:12px;color:var(--text-muted);">最近回复缓存: ${recentCount} 条</div>`;
        wrap.appendChild(recentSection);

        container.appendChild(wrap);
    },

    /** 加载聊天记录 */
    async _loadChatHistory(sessionId) {
        const container = document.getElementById('tab-history');
        if (!container) return;
        container.innerHTML = '<div class="chart-empty">加载中...</div>';

        const res = await Api.getChatHistory(sessionId);
        if (!res.ok) {
            container.innerHTML = `<div class="chart-empty">${Utils.escapeHtml(res.msg || '加载失败')}</div>`;
            this._historyLoaded = false;
            return;
        }
        const messages = res.messages || [];
        this._historyLoaded = true;
        this._prevChatMessages = messages;

        container.innerHTML = '';

        // 操作按钮
        const actionBar = document.createElement('div');
        actionBar.style.cssText = 'display:flex;gap:8px;margin-bottom:12px;';

        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm';
        editBtn.textContent = '编辑 JSON';
        editBtn.addEventListener('click', () => this._openHistoryEditor(sessionId, messages));

        actionBar.appendChild(editBtn);
        container.appendChild(actionBar);

        // 消息列表
        this._renderChatHistory(container, messages);
    },

    /** 渲染聊天记录 */
    _renderChatHistory(container, messages) {
        // 手动刷新提示
        const refreshHint = document.createElement('div');
        refreshHint.style.cssText = 'font-size:11px;color:var(--text-muted);margin-bottom:6px;line-height:1.5;';
        refreshHint.textContent = '提示：聊天记录自动刷新为优化体验做了取舍，不一定能实时反映变化。如发现数据未更新，请点击右上角「刷新」按钮强制刷新。';
        container.appendChild(refreshHint);

        const viewer = document.createElement('div');
        viewer.className = 'chat-history-viewer';

        if (!messages.length) {
            viewer.innerHTML = '<div class="chart-empty">暂无聊天记录</div>';
        } else {
            messages.forEach(msg => {
                const el = document.createElement('div');
                el.className = 'chat-msg';
                const role = msg.role || msg.sender?.nickname || 'unknown';
                const content = msg.content || msg.message_str || '';
                el.innerHTML = `<span class="chat-msg-role">${Utils.escapeHtml(role)}</span>
                    <span class="chat-msg-content">${Utils.escapeHtml(Utils.truncate(content, 200))}</span>`;
                viewer.appendChild(el);
            });
        }
        container.appendChild(viewer);

        const info = document.createElement('div');
        info.className = 'chat-history-info';
        info.style.cssText = 'font-size:12px;color:var(--text-muted);margin-top:8px;';
        info.textContent = `共 ${messages.length} 条消息`;
        container.appendChild(info);
    },

    /** 增量更新聊天记录，不重建 DOM，保持滚动位置。
     *  自动刷新和手动刷新均通过此方法，确保聊天记录随数据变化同步更新。 */
    async _updateChatHistoryInline(sessionId) {
        const container = document.getElementById('tab-history');
        if (!container) return;
        const viewer = container.querySelector('.chat-history-viewer');
        if (!viewer) {
            if (this._historyLoaded) this._loadChatHistory(sessionId);
            return;
        }
        if (!this._prevChatMessages) {
            this._loadChatHistory(sessionId);
            return;
        }

        const res = await Api.getChatHistory(sessionId);
        if (!res.ok || !res.messages) return;

        const newMessages = res.messages || [];
        const prevMessages = this._prevChatMessages;
        this._prevChatMessages = newMessages;

        // 保存滚动位置
        const scrollTop = viewer.scrollTop;
        const scrollHeight = viewer.scrollHeight;
        const clientHeight = viewer.clientHeight;
        const wasAtBottom = (scrollTop + clientHeight >= scrollHeight - 10);

        // 用最后一条消息的标识判断是否有变化（而非仅靠条数）
        const lastNew = newMessages[newMessages.length - 1];
        const lastPrev = prevMessages[prevMessages.length - 1];
        const lastNewKey = lastNew ? (lastNew.message_id || `${lastNew.timestamp || ''}|${lastNew.message_str || ''}`) : '';
        const lastPrevKey = lastPrev ? (lastPrev.message_id || `${lastPrev.timestamp || ''}|${lastPrev.message_str || ''}`) : '';

        if (lastNewKey === lastPrevKey && newMessages.length === prevMessages.length) return;

        // 仅追加新增消息（新消息比旧消息多且前缀一致）
        if (newMessages.length > prevMessages.length && this._messagesPrefixMatch(prevMessages, newMessages)) {
            const newCount = newMessages.length - prevMessages.length;
            const appended = newMessages.slice(-newCount);
            const infoEl = container.querySelector('.chat-history-info');
            appended.forEach(msg => {
                const el = document.createElement('div');
                el.className = 'chat-msg';
                const role = msg.role || msg.sender?.nickname || 'unknown';
                const content = msg.content || msg.message_str || '';
                el.innerHTML = `<span class="chat-msg-role">${Utils.escapeHtml(role)}</span>
                    <span class="chat-msg-content">${Utils.escapeHtml(Utils.truncate(content, 200))}</span>`;
                viewer.appendChild(el);
            });
            if (infoEl) {
                infoEl.textContent = `共 ${newMessages.length} 条消息`;
            }
        } else {
            // 消息结构变化，全量重建但保持滚动位
            const savedScroll = viewer.scrollTop;
            this._loadChatHistory(sessionId).then(() => {
                const newViewer = document.querySelector('#tab-history .chat-history-viewer');
                if (newViewer) {
                    newViewer.scrollTop = Math.min(savedScroll, newViewer.scrollHeight);
                }
            });
            return;
        }

        // 恢复滚动位置
        if (wasAtBottom) {
            viewer.scrollTop = viewer.scrollHeight;
        } else {
            viewer.scrollTop = scrollTop;
        }
    },

    /** 判断新消息数组的前缀是否与旧消息完全一致（用于确认只是追加而非替换） */
    _messagesPrefixMatch(prev, next) {
        if (prev.length === 0) return true;
        const len = Math.min(prev.length, next.length);
        for (let i = 0; i < len; i++) {
            const pk = prev[i].message_id || `${prev[i].timestamp || ''}|${prev[i].message_str || ''}`;
            const nk = next[i].message_id || `${next[i].timestamp || ''}|${next[i].message_str || ''}`;
            if (pk !== nk) return false;
        }
        return true;
    },

    /** 打开聊天记录 JSON 编辑器 */
    _openHistoryEditor(sessionId, messages) {
        // 进入编辑模式，暂停自动刷新轮询
        if (this._detailPoller) { this._detailPoller.stop(); }

        const container = document.getElementById('tab-history');
        container.innerHTML = '';

        const editor = document.createElement('div');
        editor.className = 'file-editor file-editor--history';

        const editorHeader = document.createElement('div');
        editorHeader.className = 'file-editor-header';
        editorHeader.innerHTML = `<span style="font-size:13px;font-weight:600;">编辑聊天记录 JSON</span>`;

        const btnGroup = document.createElement('div');
        btnGroup.style.cssText = 'display:flex;gap:8px;';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-sm btn-primary';
        saveBtn.textContent = '保存';
        saveBtn.addEventListener('click', async () => {
            try {
                const parsed = JSON.parse(textarea.value);
                if (!Array.isArray(parsed)) {
                    Utils.toast('JSON 必须是数组格式', 'warning');
                    return;
                }
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
                const res = await Api.putChatHistory(sessionId, parsed);
                if (res.ok) {
                    Utils.toast(res.msg || '保存成功', 'success');
                    this._loadChatHistory(sessionId);
                    // 保存后恢复自动刷新
                    if (this._autoRefresh) {
                        if (this._detailPoller) this._detailPoller.stop();
                        this._detailPoller = Utils.createPoller(
                            () => this._refreshDetail(sessionId, { autoRefresh: true }), 3000
                        );
                        this._detailPoller.start();
                    }
                } else {
                    Utils.toast(res.msg || '保存失败', 'error');
                }
            } catch (e) {
                Utils.toast(`JSON 格式错误: ${e.message}`, 'error');
            }
            saveBtn.disabled = false;
            saveBtn.textContent = '保存';
        });

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn btn-sm';
        cancelBtn.textContent = '取消';
        cancelBtn.addEventListener('click', () => {
            this._loadChatHistory(sessionId);
            // 取消编辑后恢复自动刷新
            if (this._autoRefresh) {
                if (this._detailPoller) this._detailPoller.stop();
                this._detailPoller = Utils.createPoller(
                    () => this._refreshDetail(sessionId, { autoRefresh: true }), 3000
                );
                this._detailPoller.start();
            }
        });

        btnGroup.appendChild(saveBtn);
        btnGroup.appendChild(cancelBtn);
        editorHeader.appendChild(btnGroup);
        editor.appendChild(editorHeader);

        const textarea = document.createElement('textarea');
        textarea.className = 'file-editor-textarea';
        textarea.style.cssText = 'font-family:monospace;font-size:12px;width:100%;margin-top:8px;';
        textarea.value = JSON.stringify(messages, null, 2);

        const ensureVisibleOnMobile = () => {
            if (window.innerWidth >= 768) return;
            requestAnimationFrame(() => {
                textarea.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
            });
        };

        textarea.addEventListener('focus', ensureVisibleOnMobile);
        textarea.addEventListener('click', ensureVisibleOnMobile);

        editor.appendChild(textarea);
        container.appendChild(editor);
    },

    /** 更新详情数据（增量更新 + 高亮变化） */
    _updateDetailData(container, d, prev) {
        // 更新概览卡片
        const density = d.reply_density || {};
        const prevDensity = prev.reply_density || {};
        const activity = d.conversation_activity || {};
        const prevActivity = prev.conversation_activity || {};
        const updates = [
            ['ov-users', d.attention?.user_count || 0, prev.attention?.user_count || 0],
            ['ov-mood', d.mood?.current_mood || '无', prev.mood?.current_mood || '无'],
            ['ov-intensity', typeof d.mood?.intensity === 'number' ? d.mood.intensity.toFixed(2) : '-',
             typeof prev.mood?.intensity === 'number' ? prev.mood.intensity.toFixed(2) : '-'],
            ['ov-cache', d.message_cache_count || 0, prev.message_cache_count || 0],
            ['ov-processing', d.is_processing ? '是' : '否', prev.is_processing ? '是' : '否'],
            ['ov-pro-proc', d.proactive_processing ? '是' : '否', prev.proactive_processing ? '是' : '否'],
            ['ov-wait', (d.wait_windows || []).length, (prev.wait_windows || []).length],
            ['ov-cooldown', (d.cooldowns || []).length, (prev.cooldowns || []).length],
            ['ov-pending-cooldown', (d.pending_cooldowns || []).length, (prev.pending_cooldowns || []).length],
            ['ov-fatigue', (d.fatigue_blocks || []).length, (prev.fatigue_blocks || []).length],
            ['ov-density', density.reply_count !== undefined ? `${density.reply_count}/${density.max_replies || '-'}` : '-',
             prevDensity.reply_count !== undefined ? `${prevDensity.reply_count}/${prevDensity.max_replies || '-'}` : '-'],
            ['ov-activity', typeof activity.activity_score === 'number' ? activity.activity_score.toFixed(2) : '-',
             typeof prevActivity.activity_score === 'number' ? prevActivity.activity_score.toFixed(2) : '-'],
        ];
        updates.forEach(([id, newVal, oldVal]) => {
            const el = document.getElementById(id);
            if (el && String(newVal) !== String(oldVal)) {
                el.querySelector('.stat-value').textContent = String(newVal);
                Utils.highlightChange(el);
            }
        });

        // 更新注意力表格
        const attnTab = document.getElementById('tab-attention');
        if (attnTab && !attnTab.classList.contains('hidden')) {
            this._renderAttentionTab(attnTab, d);
        }
        // 更新概率
        const probTab = document.getElementById('tab-probability');
        if (probTab && !probTab.classList.contains('hidden')) {
            this._renderProbabilityTab(probTab, d);
        }
        // 更新主动对话
        const proactiveTab = document.getElementById('tab-proactive');
        if (proactiveTab && !proactiveTab.classList.contains('hidden')) {
            this._renderProactiveTab(proactiveTab, d);
        }
        // 更新运行时状态
        const runtimeTab = document.getElementById('tab-runtime');
        if (runtimeTab && !runtimeTab.classList.contains('hidden')) {
            this._renderRuntimeTab(runtimeTab, d);
        }
        // 聊天记录：如果已加载、当前 Tab 可见、且不在编辑模式，增量更新
        const historyTab = document.getElementById('tab-history');
        if (this._historyLoaded && historyTab && !historyTab.classList.contains('hidden')
            && !historyTab.querySelector('.file-editor--history')) {
            this._updateChatHistoryInline(this._currentSession);
        }
    },

    /** 返回会话列表 */
    _backToList() {
        this._currentSession = null;
        this._prevDetail = null;
        if (this._detailPoller) { this._detailPoller.stop(); this._detailPoller = null; }
        document.getElementById('session-detail').classList.add('hidden');
        document.getElementById('session-list-container').classList.remove('hidden');
        this._loadSessions();
        // 返回列表后恢复列表自动刷新
        this._startListAutoRefresh();
    },

    /** 清理孤立会话文件 */
    async _cleanupGhostSessions() {
        const ghostCount = this._sessions.filter(s => !s.has_runtime_data && s.has_file).length;
        if (ghostCount === 0) {
            Utils.toast('没有需要清理的孤立会话记录', 'info');
            return;
        }
        const ok = await Utils.confirm(
            `确认清理 ${ghostCount} 个孤立会话的文件记录？\n\n这些会话没有对应的运行时状态，可能是旧版留下的残留文件。\n清理后无法恢复，请确认是否继续。`
        );
        if (!ok) return;
        const res = await Api.sessionCleanGhosts();
        if (res.ok) {
            Utils.toast(res.msg || '清理完成', 'success');
            this._loadSessions();
        } else {
            Utils.toast(res.msg || '清理失败', 'error');
        }
    },

    /** 重置会话数据，随后触发插件重载使清理完全生效。 */
    async _resetSession(sessionId) {
        const ok = await Utils.confirm(`确认重置会话「${sessionId}」的插件数据？\n将清除注意力、情绪、概率等运行时状态，重置后插件会自动重载。`);
        if (!ok) return;
        const res = await Api.sessionReset(sessionId);
        if (res.ok) {
            Utils.toast(res.msg || '会话已重置，插件重载中...', 'success');
            // 轮询重载状态，成功后仅重新加载数据（不触发整页刷新，避免命中速率限制）
            if (typeof App !== 'undefined' && App._pollRestartStatus) {
                await App._pollRestartStatus('reload');
            }
            // 隐藏详情视图（如果打开），回到列表，重新加载
            const detailEl = document.getElementById('session-detail');
            if (detailEl) detailEl.classList.add('hidden');
            const listContainer = document.getElementById('session-list-container');
            if (listContainer) listContainer.classList.remove('hidden');
            this._loadSessions();
            this._startListAutoRefresh();
        } else {
            Utils.toast(res.msg || '重置失败', 'error');
        }
    },

};
