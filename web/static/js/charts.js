/**
 * charts.js - 数据可视化（Canvas 2D 绘图）
 * 注意力分布、概率状态、主动对话统计 + 自动刷新 & 变化高亮
 * 刷新策略：首次/会话切换时重建 DOM，后续自动刷新时原地更新数据（无闪烁）
 */

const Charts = {
    _session: '',
    _refreshTimer: null,
    _autoRefresh: true,
    _prevData: {},  // 上一次各图表数据，用于变化检测
    _initialized: false, // 当前 grid 是否已渲染过结构

    /** 初始化图表视图 */
    async init() {
        this._prevData = {};
        this._session = '';
        this._initialized = false;
        await this._loadSessions();
        this._bindEvents();
        this._setupAutoRefresh();
        await this._loadCharts(true);
    },

    /** 销毁（切换视图时调用） */
    destroy() {
        if (this._refreshTimer) { clearInterval(this._refreshTimer); this._refreshTimer = null; }
        this._initialized = false;
    },

    /** 设置自动刷新 */
    _setupAutoRefresh() {
        if (this._refreshTimer) clearInterval(this._refreshTimer);
        if (this._autoRefresh) {
            this._refreshTimer = setInterval(() => {
                if (this._session) this._loadCharts(false);
            }, 10000);
        }
    },

    /** 加载会话列表到下拉框 */
    async _loadSessions() {
        const select = document.getElementById('chart-session-select');
        if (!select) return;
        const res = await Api.dataSessions();
        const prevVal = this._session;
        select.innerHTML = '<option value="">选择会话...</option>';
        if (res.ok && res.sessions) {
            res.sessions.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                select.appendChild(opt);
            });
        }
        // 恢复之前的选择（若仍在列表中）
        if (prevVal && select.querySelector(`option[value="${CSS.escape(prevVal)}"]`)) {
            select.value = prevVal;
            this._session = prevVal;
        } else {
            this._session = '';
        }
    },

    /** 绑定事件 */
    _bindEvents() {
        const select = document.getElementById('chart-session-select');
        if (select && !select._chartsBound) {
            select._chartsBound = true;
            select.addEventListener('change', () => {
                this._session = select.value;
                this._prevData = {};
                this._initialized = false;
                this._loadCharts(true);
            });
        }

        // 自动刷新开关
        const toggle = document.getElementById('charts-auto-refresh');
        if (toggle && !toggle._bound) {
            toggle._bound = true;
            toggle.addEventListener('change', (e) => {
                this._autoRefresh = e.target.checked;
                const dot = document.getElementById('charts-refresh-dot');
                if (dot) dot.className = 'dot' + (this._autoRefresh ? ' active' : '');
                this._setupAutoRefresh();
            });
        }
    },

    /**
     * 加载所有图表数据
     * @param {boolean} rebuild - true=重建DOM结构（首次/会话切换），false=原地更新数值（自动刷新）
     */
    async _loadCharts(rebuild = false) {
        const grid = document.getElementById('charts-grid');
        if (!grid) return;

        // 首次或会话切换：重建整个 DOM 结构
        if (rebuild || !this._initialized) {
            grid.innerHTML = '<div class="chart-empty" style="grid-column:1/-1;padding:40px;">加载中...</div>';

            if (!this._session) {
                grid.innerHTML = '';
                await this._buildOverview(grid);
                grid.innerHTML += '<div class="chart-empty" style="grid-column:1/-1;padding:40px;">请选择一个会话查看详细数据</div>';
                this._initialized = true;
                return;
            }

            const [overviewRes, attentionRes, probRes, moodRes, proactiveRes, detailRes] = await Promise.allSettled([
                Api.dataOverview(),
                Api.dataAttention(this._session),
                Api.dataProbability(this._session),
                Api.dataMood(this._session),
                Api.dataProactive(),
                Api.sessionDetail(this._session),
            ]);

            grid.innerHTML = '';
            await this._buildOverview(grid, overviewRes.value, detailRes.value, attentionRes.value);
            await this._buildAttention(grid, attentionRes.value);
            await this._buildProbability(grid, probRes.value);
            await this._buildMood(grid, moodRes.value);
            await this._buildProactive(grid, proactiveRes.value);
            this._initialized = true;
            return;
        }

        // 自动刷新：原地更新，不重建 DOM，不产生闪烁
        const [overviewRes, attentionRes, probRes, moodRes, proactiveRes, detailRes] = await Promise.allSettled([
            Api.dataOverview(),
            Api.dataAttention(this._session),
            Api.dataProbability(this._session),
            Api.dataMood(this._session),
            Api.dataProactive(),
            this._session ? Api.sessionDetail(this._session) : Promise.resolve(null),
        ]);

        this._updateOverview(overviewRes.value, detailRes.value, attentionRes.value);
        this._updateAttention(attentionRes.value);
        this._updateProbability(probRes.value);
        this._updateMood(moodRes.value);
        this._updateProactive(proactiveRes.value);
    },

    // ==================== 构建（首次渲染）====================

    /** 总览卡片（构建） */
    async _buildOverview(grid, res, detailRes, attentionRes) {
        try {
            if (!res) res = await Api.dataOverview();
            if (!res || !res.ok) return;
            const d = res.overview || {};
            const sd = (detailRes && detailRes.ok) ? (detailRes.detail || {}) : {};
            // 用注意力端点数据作为追踪用户数的后备来源
            const attUsers = (attentionRes && attentionRes.ok) ? (attentionRes.users || []) : [];
            const trackedUsers = sd.attention?.user_count ?? (attUsers.length || d.total_tracked_users) ?? 0;

            const overview = document.createElement('div');
            overview.className = 'overview-grid';
            overview.id = 'overview-grid';
            overview.style.gridColumn = '1 / -1';

            const cards = [
                { label: '活跃会话', value: d.total_sessions || 0, id: 'ov-total-sessions' },
                { label: '追踪用户', value: trackedUsers, id: 'ov-total-users' },
                { label: '处理中', value: sd.is_processing !== undefined ? (sd.is_processing ? '是' : '否') : (d.active_processing || 0), id: 'ov-processing' },
                { label: '主动对话', value: d.proactive_active_count || 0, id: 'ov-proactive' },
                { label: '缓存消息', value: sd.message_cache_count ?? d.total_cached_messages ?? 0, id: 'ov-cached-msgs' },
                { label: '等待窗口', value: sd.wait_windows ? sd.wait_windows.length : (d.active_wait_windows || 0), id: 'ov-wait-wins' },
                { label: '冷却用户', value: sd.cooldowns ? sd.cooldowns.length : (d.cooldown_users || 0), id: 'ov-cooldown-users' },
                { label: '主动处理', value: sd.proactive_processing !== undefined ? (sd.proactive_processing ? '是' : '否') : (d.proactive_processing || 0), id: 'ov-pro-processing' },
            ];

            cards.forEach(c => {
                const card = document.createElement('div');
                card.className = 'overview-card';
                card.id = c.id;
                card.innerHTML = `<div class="stat-value" id="${c.id}-val">${c.value}</div>
                    <div class="stat-label">${c.label}</div>`;
                this._prevData[c.id] = c.value;
                overview.appendChild(card);
            });

            grid.appendChild(overview);
        } catch (e) {
            console.error('Charts: overview build failed', e);
        }
    },

    /** 注意力分布（构建） */
    async _buildAttention(grid, res) {
        try {
            if (!res) res = await Api.dataAttention(this._session);
            const { card, canvas, wrap } = this._createCard(
                '注意力分布', { cls: 'live', text: '实时' }, grid, 'chart-attention'
            );

            const users = res && res.ok ? (res.users || []) : [];
            if (!users.length) {
                wrap.innerHTML = '<div class="chart-empty">暂无注意力数据</div>';
                return;
            }

            const data = users.sort((a, b) => (b.attention_score || 0) - (a.attention_score || 0)).slice(0, 10);
            this._drawBarChart(canvas, data.map(d => d.user_id || 'unknown'),
                data.map(d => d.attention_score || 0), 'var(--accent-red)');

            const stats = document.createElement('div');
            stats.className = 'stats-row';
            stats.id = 'stats-attention';
            stats.innerHTML = `
                <div class="stat-item"><div class="stat-value" id="att-count">${data.length}</div><div class="stat-label">追踪用户</div></div>
                <div class="stat-item"><div class="stat-value" id="att-max">${data.length ? (data[0].attention_score || 0).toFixed(1) : 0}</div><div class="stat-label">最高分</div></div>`;
            card.appendChild(stats);

            this._prevData['att-data'] = data.map(d => d.attention_score || 0).join(',');
        } catch (e) {
            console.error('Charts: attention build failed', e);
        }
    },

    /** 概率状态（构建） */
    async _buildProbability(grid, res) {
        try {
            if (!res) res = await Api.dataProbability(this._session);
            const { card, canvas, wrap } = this._createCard(
                '概率状态', { cls: 'live', text: '实时' }, grid, 'chart-probability'
            );

            const d = res && res.ok ? (res.probability || {}) : {};
            if (!Object.keys(d).length) {
                wrap.innerHTML = '<div class="chart-empty">暂无概率数据</div>';
                return;
            }

            const { labels, values } = this._probLabelsValues(d);
            this._drawBarChart(canvas, labels, values, 'var(--text-primary)');

            const stats = document.createElement('div');
            stats.className = 'stats-row';
            stats.id = 'stats-probability';
            stats.innerHTML = `
                <div class="stat-item"><div class="stat-value" id="prob-init">${((d.initial_probability || 0) * 100).toFixed(1)}%</div><div class="stat-label">基础概率</div></div>
                <div class="stat-item"><div class="stat-value" id="prob-reply">${((d.after_reply_probability || 0) * 100).toFixed(1)}%</div><div class="stat-label">回复后概率</div></div>`;
            card.appendChild(stats);

            this._prevData['prob-data'] = values.join(',');
        } catch (e) {
            console.error('Charts: probability build failed', e);
        }
    },

    /** 情绪状态（构建） */
    async _buildMood(grid, res) {
        try {
            if (!res) res = await Api.dataMood(this._session);
            const { card, canvas, wrap } = this._createCard(
                '情绪状态', { cls: 'live', text: '实时' }, grid, 'chart-mood'
            );

            const mood = res && res.ok ? (res.mood || {}) : {};
            if (!Object.keys(mood).length) {
                wrap.innerHTML = '<div class="chart-empty">暂无情绪数据</div>';
                return;
            }

            this._drawBarChart(canvas, [mood.current_mood || '平静'], [mood.intensity || 0], '#cc3333');

            const stats = document.createElement('div');
            stats.className = 'stats-row';
            stats.id = 'stats-mood';
            stats.innerHTML = `
                <div class="stat-item"><div class="stat-value" id="mood-name">${mood.current_mood || '平静'}</div><div class="stat-label">当前情绪</div></div>
                <div class="stat-item"><div class="stat-value" id="mood-intensity">${(mood.intensity || 0).toFixed(2)}</div><div class="stat-label">强度</div></div>`;
            card.appendChild(stats);

            this._prevData['mood-name'] = mood.current_mood || '平静';
            this._prevData['mood-intensity'] = mood.intensity || 0;
        } catch (e) {
            console.error('Charts: mood build failed', e);
        }
    },

    /** 主动对话统计（构建） */
    async _buildProactive(grid, res) {
        try {
            if (!res) res = await Api.dataProactive();
            const { card, canvas, wrap } = this._createCard(
                '主动对话统计', { cls: 'persist', text: '持久' }, grid, 'chart-proactive'
            );

            const proactive = res && res.ok ? (res.proactive || {}) : {};
            if (!Object.keys(proactive).length) {
                wrap.innerHTML = '<div class="chart-empty">暂无主动对话数据</div>';
                return;
            }

            const { totalSuccess, totalFailure, totalCooldown, rate, avgScore } = this._calcProactive(proactive);
            this._drawBarChart(canvas, ['成功', '失败', '冷却中'], [totalSuccess, totalFailure, totalCooldown], 'var(--accent-green)');

            const stats = document.createElement('div');
            stats.className = 'stats-row';
            stats.id = 'stats-proactive';
            stats.innerHTML = `
                <div class="stat-item"><div class="stat-value" id="pro-total">${totalSuccess + totalFailure}</div><div class="stat-label">总次数</div></div>
                <div class="stat-item"><div class="stat-value" id="pro-rate">${rate}%</div><div class="stat-label">成功率</div></div>
                <div class="stat-item"><div class="stat-value" id="pro-score">${avgScore}</div><div class="stat-label">平均交互评分</div></div>`;
            card.appendChild(stats);

            this._prevData['pro-data'] = `${totalSuccess},${totalFailure},${totalCooldown}`;
        } catch (e) {
            console.error('Charts: proactive build failed', e);
        }
    },

    // ==================== 原地更新（自动刷新）====================

    /** 总览更新（只改数字，触发变化高亮） */
    _updateOverview(res, detailRes, attentionRes) {
        if (!res || !res.ok) return;
        const d = res.overview || {};
        const sd = (detailRes && detailRes.ok) ? (detailRes.detail || {}) : {};
        const attUsers = (attentionRes && attentionRes.ok) ? (attentionRes.users || []) : [];
        const trackedUsers = sd.attention?.user_count ?? (attUsers.length || d.total_tracked_users) ?? 0;
        const map = {
            'ov-total-sessions': d.total_sessions || 0,
            'ov-total-users': trackedUsers,
            'ov-processing': sd.is_processing !== undefined ? (sd.is_processing ? '是' : '否') : (d.active_processing || 0),
            'ov-proactive': d.proactive_active_count || 0,
            'ov-cached-msgs': sd.message_cache_count ?? d.total_cached_messages ?? 0,
            'ov-wait-wins': sd.wait_windows ? sd.wait_windows.length : (d.active_wait_windows || 0),
            'ov-cooldown-users': sd.cooldowns ? sd.cooldowns.length : (d.cooldown_users || 0),
            'ov-pro-processing': sd.proactive_processing !== undefined ? (sd.proactive_processing ? '是' : '否') : (d.proactive_processing || 0),
        };
        for (const [id, val] of Object.entries(map)) {
            const valEl = document.getElementById(`${id}-val`);
            if (!valEl) continue;
            if (this._prevData[id] !== val) {
                valEl.textContent = val;
                Utils.highlightChange(document.getElementById(id));
                this._prevData[id] = val;
            }
        }
    },

    /** 注意力更新 */
    _updateAttention(res) {
        try {
            const users = res && res.ok ? (res.users || []) : [];
            const data = users.sort((a, b) => (b.attention_score || 0) - (a.attention_score || 0)).slice(0, 10);
            const key = data.map(d => d.attention_score || 0).join(',');

            const canvas = document.querySelector('#chart-attention canvas');
            if (canvas && key !== this._prevData['att-data']) {
                this._drawBarChart(canvas, data.map(d => d.user_id || 'unknown'),
                    data.map(d => d.attention_score || 0), 'var(--accent-red)');
                this._prevData['att-data'] = key;
            }

            this._setTextIfChanged('att-count', data.length);
            this._setTextIfChanged('att-max',
                data.length ? (data[0].attention_score || 0).toFixed(1) : 0);
        } catch (e) { console.error('Charts: attention update failed', e); }
    },

    /** 概率更新 */
    _updateProbability(res) {
        try {
            const d = res && res.ok ? (res.probability || {}) : {};
            if (!Object.keys(d).length) return;

            const { labels, values } = this._probLabelsValues(d);
            const key = values.join(',');
            const canvas = document.querySelector('#chart-probability canvas');
            if (canvas && key !== this._prevData['prob-data']) {
                this._drawBarChart(canvas, labels, values, 'var(--text-primary)');
                this._prevData['prob-data'] = key;
            }

            const initVal = ((d.initial_probability || 0) * 100).toFixed(1) + '%';
            const replyVal = ((d.after_reply_probability || 0) * 100).toFixed(1) + '%';
            this._setTextIfChanged('prob-init', initVal);
            this._setTextIfChanged('prob-reply', replyVal);
        } catch (e) { console.error('Charts: probability update failed', e); }
    },

    /** 情绪更新 */
    _updateMood(res) {
        try {
            const mood = res && res.ok ? (res.mood || {}) : {};
            if (!Object.keys(mood).length) return;

            const moodName = mood.current_mood || '平静';
            const intensity = mood.intensity || 0;

            const canvas = document.querySelector('#chart-mood canvas');
            if (canvas && (moodName !== this._prevData['mood-name'] || intensity !== this._prevData['mood-intensity'])) {
                this._drawBarChart(canvas, [moodName], [intensity], '#cc3333');
            }

            this._setTextIfChanged('mood-name', moodName);
            this._setTextIfChanged('mood-intensity', intensity.toFixed(2));

            this._prevData['mood-name'] = moodName;
            this._prevData['mood-intensity'] = intensity;
        } catch (e) { console.error('Charts: mood update failed', e); }
    },

    /** 主动对话更新 */
    _updateProactive(res) {
        try {
            const proactive = res && res.ok ? (res.proactive || {}) : {};
            if (!Object.keys(proactive).length) return;

            const { totalSuccess, totalFailure, totalCooldown, rate, avgScore } = this._calcProactive(proactive);
            const key = `${totalSuccess},${totalFailure},${totalCooldown}`;

            const canvas = document.querySelector('#chart-proactive canvas');
            if (canvas && key !== this._prevData['pro-data']) {
                this._drawBarChart(canvas, ['成功', '失败', '冷却中'], [totalSuccess, totalFailure, totalCooldown], 'var(--accent-green)');
                this._prevData['pro-data'] = key;
            }

            this._setTextIfChanged('pro-total', totalSuccess + totalFailure);
            this._setTextIfChanged('pro-rate', rate + '%');
            this._setTextIfChanged('pro-score', avgScore);
        } catch (e) { console.error('Charts: proactive update failed', e); }
    },

    // ==================== 辅助方法 ====================

    /** 更新文字（有变化时高亮） */
    _setTextIfChanged(id, newVal) {
        const el = document.getElementById(id);
        if (!el) return;
        const newStr = String(newVal);
        if (el.textContent !== newStr) {
            el.textContent = newStr;
            Utils.highlightChange(el.closest('.stat-item') || el);
        }
    },

    /** 提取概率图的 labels/values */
    _probLabelsValues(d) {
        const labels = ['基础概率', '回复后概率'];
        const values = [d.initial_probability || 0, d.after_reply_probability || 0];
        if (d.frequency_adjusted_probability !== undefined) {
            labels.push('频率调整');
            values.push(d.frequency_adjusted_probability || 0);
        }
        if (d.temp_boost) {
            labels.push('临时提升');
            values.push(d.temp_boost.value || 0);
        }
        return { labels, values };
    },

    /** 计算主动对话汇总 */
    _calcProactive(proactive) {
        let totalSuccess = 0, totalFailure = 0, totalCooldown = 0, totalScore = 0, sessionCount = 0;
        for (const state of Object.values(proactive)) {
            totalSuccess += state.total_successes || 0;
            totalFailure += state.total_failures || 0;
            if (state.cooldown_until > Date.now() / 1000) totalCooldown++;
            totalScore += state.interaction_score || 0;
            sessionCount++;
        }
        const total = totalSuccess + totalFailure;
        const rate = total > 0 ? ((totalSuccess / total) * 100).toFixed(1) : '0.0';
        const avgScore = sessionCount > 0 ? (totalScore / sessionCount).toFixed(1) : '-';
        return { totalSuccess, totalFailure, totalCooldown, rate, avgScore };
    },

    /** 创建图表卡片骨架，cardId 用于原地更新时定位 canvas */
    _createCard(title, badge, grid, cardId) {
        const card = document.createElement('div');
        card.className = 'chart-card';
        if (cardId) card.id = cardId;
        const header = document.createElement('div');
        header.className = 'chart-card-header';
        header.innerHTML = `<span class="chart-card-title">${title}</span>
            <span class="chart-card-badge ${badge.cls}">${badge.text}</span>`;
        card.appendChild(header);

        const wrap = document.createElement('div');
        wrap.className = 'chart-canvas-wrap';
        const canvas = document.createElement('canvas');
        wrap.appendChild(canvas);
        card.appendChild(wrap);

        grid.appendChild(card);
        return { card, canvas, wrap };
    },

    /** Canvas 柱状图绘制 */
    _drawBarChart(canvas, labels, values, color) {
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        canvas.style.width = rect.width + 'px';
        canvas.style.height = rect.height + 'px';

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        const w = rect.width, h = rect.height;
        const pad = { top: 10, right: 10, bottom: 40, left: 50 };
        const chartW = w - pad.left - pad.right;
        const chartH = h - pad.top - pad.bottom;

        if (!values.length) return;
        const max = Math.max(...values, 0.01);

        const style = getComputedStyle(document.documentElement);
        const resolveColor = c => {
            if (c.startsWith('var(')) {
                const varName = c.slice(4, -1).trim();
                return style.getPropertyValue(varName).trim() || '#e02020';
            }
            return c;
        };
        const barColor = resolveColor(color);
        const textMuted = style.getPropertyValue('--text-muted').trim() || '#555555';
        const textPrimary = style.getPropertyValue('--text-primary').trim() || '#f0f0f0';
        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        const gridLineColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.08)';

        // 网格线
        ctx.strokeStyle = gridLineColor;
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = pad.top + chartH * (1 - i / 4);
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(pad.left + chartW, y);
            ctx.stroke();

            ctx.fillStyle = textMuted;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'right';
            const label = (max * i / 4).toFixed(max < 1 ? 2 : 0);
            ctx.fillText(label, pad.left - 6, y + 3);
        }

        // 柱子
        const barW = Math.min(40, chartW / labels.length * 0.6);
        const gap = chartW / labels.length;

        labels.forEach((label, i) => {
            const x = pad.left + gap * i + (gap - barW) / 2;
            const barH = (values[i] / max) * chartH;
            const y = pad.top + chartH - barH;

            ctx.fillStyle = barColor;
            ctx.globalAlpha = 0.85;
            ctx.beginPath();
            ctx.roundRect(x, y, barW, barH, [3, 3, 0, 0]);
            ctx.fill();
            ctx.globalAlpha = 1;

            // X 轴标签
            ctx.fillStyle = textMuted;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            const tl = label.length > 6 ? label.slice(0, 6) + '..' : label;
            ctx.fillText(tl, pad.left + gap * i + gap / 2, h - pad.bottom + 16);

            // 值标签
            ctx.fillStyle = textPrimary;
            ctx.font = '11px sans-serif';
            const vt = values[i] < 1 ? values[i].toFixed(2) : String(Math.round(values[i]));
            ctx.fillText(vt, pad.left + gap * i + gap / 2, y - 4);
        });
    }
};
