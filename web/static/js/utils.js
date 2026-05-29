/**
 * utils.js - 工具函数
 */

// Polyfill: CanvasRenderingContext2D.roundRect()
// Supported natively since Chrome 99, Firefox 112, Safari 15.4.
// Older browsers get a path-fallback that produces identical visual results.
if (typeof CanvasRenderingContext2D !== 'undefined' && !CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
        if (typeof r === 'number') r = { tl: r, tr: r, br: r, bl: r };
        var tl = r.tl || 0, tr = r.tr || 0, br = r.br || 0, bl = r.bl || 0;
        this.beginPath();
        this.moveTo(x + tl, y);
        this.lineTo(x + w - tr, y);
        this.arcTo(x + w, y, x + w, y + tr, tr);
        this.lineTo(x + w, y + h - br);
        this.arcTo(x + w, y + h, x + w - br, y + h, br);
        this.lineTo(x + bl, y + h);
        this.arcTo(x, y + h, x, y + h - bl, bl);
        this.lineTo(x, y + tl);
        this.arcTo(x, y, x + tl, y, tl);
        this.closePath();
    };
}

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

    /** 支持作者弹窗 */
    supportAuthorDialog() {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-overlay';
            overlay.innerHTML = `
                <div class="confirm-box support-author-dialog">
                    <h3>❤️ 支持作者</h3>
                    <p>即将跳转至爱发电进行捐赠。</p>
                    <div class="support-author-dialog__note">
                        <p>如果这个插件帮到了你，欢迎通过爱发电支持作者持续维护与更新。</p>
                        <p>你的支持可以帮助作者投入更多时间优化功能、修复问题，并持续提供免费开源版本。</p>
                    </div>
                    <div class="confirm-actions">
                        <button class="btn" data-action="cancel">取消</button>
                        <button class="btn btn-primary" data-action="ok">确认跳转</button>
                    </div>
                </div>`;
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

    /** 文本输入弹窗，返回用户输入的字符串或 null。maxLength 可选，设置后显示字数限制提示 */
    prompt(title, defaultValue = '', maxLength = 0) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-overlay';
            const maxAttr = maxLength > 0 ? ` maxlength="${maxLength}"` : '';
            const hintHtml = maxLength > 0
                ? `<div id="prompt-char-hint" style="font-size:10px;color:var(--text-muted);margin-top:2px;text-align:right;">0 / ${maxLength}</div>`
                : '';
            overlay.innerHTML = `
                <div class="confirm-box" style="width:360px;">
                    <h3 style="margin-bottom:12px;">${Utils.escapeHtml(title)}</h3>
                    <textarea id="prompt-input" rows="3" style="width:100%;resize:vertical;"${maxAttr}>${Utils.escapeHtml(defaultValue)}</textarea>
                    ${hintHtml}
                    <div class="confirm-actions" style="margin-top:12px;">
                        <button class="btn" data-action="cancel">取消</button>
                        <button class="btn btn-primary" data-action="ok">确认</button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            const input = document.getElementById('prompt-input');
            const hint = document.getElementById('prompt-char-hint');
            const updateHint = () => {
                if (hint) hint.textContent = `${input.value.length} / ${maxLength}`;
            };
            if (hint) {
                updateHint();
                input.addEventListener('input', updateHint);
            }
            input.focus();
            overlay.addEventListener('click', e => {
                const action = e.target.dataset.action;
                if (action === 'cancel') { overlay.remove(); resolve(null); }
                if (action === 'ok') {
                    const val = input.value.trim();
                    overlay.remove();
                    resolve(val || '');
                }
            });
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const val = input.value.trim();
                    overlay.remove();
                    resolve(val || '');
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
