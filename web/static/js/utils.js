/**
 * utils.js - 工具函数
 */

const Utils = {
    /** 防抖 */
    debounce(fn, ms = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        };
    },

    /** 格式化时间戳 */
    formatTime(ts) {
        if (!ts) return '-';
        const d = new Date(ts * 1000);
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },

    /** 格式化秒数为可读时间 */
    formatDuration(seconds) {
        if (!seconds || seconds < 0) return '-';
        if (seconds < 60) return `${Math.round(seconds)}秒`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}分${Math.round(seconds%60)}秒`;
        return `${Math.floor(seconds/3600)}时${Math.floor((seconds%3600)/60)}分`;
    },

    /** 格式化文件大小 */
    formatSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
        return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
    },

    /** 显示 Toast 通知 */
    toast(msg, type = 'info', duration = 3000) {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = msg;
        container.appendChild(el);
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transform = 'translateX(20px)';
            el.style.transition = '0.3s ease';
            setTimeout(() => el.remove(), 300);
        }, duration);
    },

    /** 确认弹窗 */
    confirm(msg) {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-overlay';
            overlay.innerHTML =
                '<div class="confirm-box">' +
                    '<p class="confirm-msg"></p>' +
                    '<div class="confirm-actions">' +
                        '<button class="btn" data-action="cancel">取消</button>' +
                        '<button class="btn btn-danger" data-action="ok">确认</button>' +
                    '</div>' +
                '</div>';
            overlay.querySelector('.confirm-msg').textContent = msg;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', e => {
                const action = e.target.dataset.action;
                if (action) {
                    overlay.remove();
                    resolve(action === 'ok');
                }
            });
        });
    },

    /** 提示弹窗（单按钮：确定） */
    alert(msg) {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-overlay';
            overlay.innerHTML =
                '<div class="confirm-box">' +
                    '<p class="confirm-msg"></p>' +
                    '<div class="confirm-actions">' +
                        '<button class="btn btn-primary" data-action="ok">确定</button>' +
                    '</div>' +
                '</div>';
            overlay.querySelector('.confirm-msg').textContent = msg;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', e => {
                if (e.target.dataset.action === 'ok') {
                    overlay.remove();
                    resolve();
                }
            });
        });
    },

    /** 反馈对话框：选择GitHub反馈或加入群聊 */
    feedbackDialog() {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-overlay';
            overlay.innerHTML = `
                <div class="confirm-box">
                    <h3>🐛 反馈BUG</h3>
                    <p>请选择反馈方式：</p>
                    <div class="confirm-actions">
                        <button class="btn btn-primary" data-action="github">GitHub反馈</button>
                        <button class="btn" data-action="group">加入群聊</button>
                        <button class="btn" data-action="cancel">取消</button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', e => {
                const action = e.target.dataset.action;
                if (action) {
                    overlay.remove();
                    resolve(action);
                }
            });
        });
    },

    /** 安全 HTML 转义 */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /** 截断字符串 */
    truncate(str, len = 50) {
        if (!str) return '';
        return str.length > len ? str.slice(0, len) + '...' : str;
    },

    /** 创建轮询器 */
    createPoller(fn, intervalMs = 5000) {
        let timer = null;
        return {
            start() {
                if (timer) return;
                fn();
                timer = setInterval(fn, intervalMs);
            },
            stop() {
                if (timer) { clearInterval(timer); timer = null; }
            },
            isActive() { return timer !== null; }
        };
    },

    /** 高亮变化的 DOM 元素 */
    highlightChange(el) {
        if (!el) return;
        el.classList.remove('highlight-change');
        void el.offsetWidth; // 强制回流以重新触发动画
        el.classList.add('highlight-change');
    },

    /** 对比两个值，如果不同则高亮对应的 DOM 元素 */
    diffHighlight(el, oldVal, newVal) {
        if (el && oldVal !== undefined && oldVal !== newVal) {
            this.highlightChange(el);
        }
    }
};
