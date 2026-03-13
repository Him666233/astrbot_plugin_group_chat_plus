/**
 * api.js - HTTP 客户端封装 (fetch + JWT)
 */

const Api = {
    _token: localStorage.getItem('gcp_token') || '',

    setToken(token) {
        this._token = token;
        localStorage.setItem('gcp_token', token);
        // 同时设置 Cookie，使浏览器页面跳转（如 /panel）也能携带 token
        document.cookie = `gcp_token=${encodeURIComponent(token)}; path=/; SameSite=Strict`;
    },

    clearToken() {
        this._token = '';
        localStorage.removeItem('gcp_token');
        document.cookie = 'gcp_token=; path=/; SameSite=Strict; max-age=0';
    },

    getToken() {
        return this._token;
    },

    /** 通用请求 */
    async request(method, path, body) {
        const headers = { 'Content-Type': 'application/json' };
        if (this._token) {
            headers['Authorization'] = `Bearer ${this._token}`;
        }
        const options = { method: method || 'GET', headers };
        if (body !== undefined) {
            options.body = JSON.stringify(body);
        }
        try {
            const resp = await fetch(path, options);

            // 暴力破解锁定
            if (resp.status === 429) {
                return await resp.json();
            }

            // IP 被封禁 → 直接跳转到独立错误页，避免暴露面板/登录页前端代码
            if (resp.status === 403) {
                let data;
                try { data = await resp.json(); } catch(e) { data = { ok: false, msg: '访问被拒绝' }; }
                if (data.blocked) {
                    window.location.href = '/error?code=blocked';
                    return data;
                }
                return data;
            }

            // 登录过期或 IP 变更
            if (resp.status === 401) {
                let data;
                try { data = await resp.json(); } catch(e) { data = { ok: false }; }
                // 登录接口的 401 直接返回数据，由调用方处理错误提示
                if (path === '/api/auth/login') {
                    return data;
                }
                this.clearToken();
                if (data.reason === 'ip_changed' && typeof Utils !== 'undefined') {
                    Utils.alert('您的 IP 地址已变更，为安全起见请重新登录').then(() => {
                        window.location.href = '/';
                    });
                } else if (data.reason === 'token_expired' && typeof Utils !== 'undefined') {
                    Utils.alert('登录已过期，请重新登录').then(() => {
                        window.location.href = '/';
                    });
                } else {
                    window.location.href = '/';
                }
                return data;
            }

            return await resp.json();
        } catch (e) {
            return { ok: false, msg: `网络错误: ${e.message}` };
        }
    },

    get(path)        { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body); },
    put(path, body)  { return this.request('PUT', path, body); },

    // ---- Auth ----
    login(password)          { return this.post('/api/auth/login', { password }); },
    authStatus()             { return this.get('/api/auth/status'); },
    changePassword(old_password, new_password) {
        return this.post('/api/auth/change-password', { old_password, new_password });
    },
    verify()                 { return this.get('/api/auth/verify'); },
    logout()                 { return this.post('/api/auth/logout', {}); },

    // ---- Config ----
    getConfig()              { return this.get('/api/config'); },
    putConfig(config)        { return this.put('/api/config', { config }); },
    reloadPlugin(config)     { return this.post('/api/config/reload', config ? { config } : {}); },

    // ---- Data ----
    dataSessions()           { return this.get('/api/data/sessions'); },
    dataAttention(session)   { return this.get(`/api/data/attention/${encodeURIComponent(session)}`); },
    dataMood(session)        { return this.get(`/api/data/mood/${encodeURIComponent(session)}`); },
    dataProbability(session) { return this.get(`/api/data/probability/${encodeURIComponent(session)}`); },
    dataProactive()          { return this.get('/api/data/proactive'); },
    dataOverview()           { return this.get('/api/data/overview'); },
    dataStatus()             { return this.get('/api/data/status'); },

    // ---- Session ----
    sessionList()            { return this.get('/api/session/list'); },
    sessionReset(session)    { return this.post(`/api/session/reset/${encodeURIComponent(session)}`); },
    clearImageCache()        { return this.post('/api/session/clear-image-cache'); },
    getChatHistory(session)  { return this.get(`/api/session/chat-history/${encodeURIComponent(session)}`); },
    putChatHistory(session, messages) {
        return this.put(`/api/session/chat-history/${encodeURIComponent(session)}`, { messages });
    },
    getImageCache()          { return this.get('/api/session/image-cache'); },

    // ---- Commands ----
    cmdReset(restart_mode)               { return this.post('/api/commands/reset', { restart_mode }); },
    cmdResetHere(session_id, restart_mode) { return this.post('/api/commands/reset-here', { session_id, restart_mode }); },
    cmdClearImageCache(restart_mode)     { return this.post('/api/commands/clear-image-cache', { restart_mode }); },

    // ---- Security ----
    getAccessLog(page, size) { return this.get(`/api/security/access-log?page=${page}&size=${size}`); },
    getBans()                { return this.get('/api/security/bans'); },
    banIp(ip, duration, reason) { return this.post('/api/security/ban', { ip, duration, reason }); },
    unbanIp(ip)              { return this.post('/api/security/unban', { ip }); },
    getIpConfig()            { return this.get('/api/security/ip-config'); },
    putIpConfig(config)      { return this.put('/api/security/ip-config', config); },

    // ---- Session Detail ----
    sessionDetail(session)   { return this.get(`/api/data/session-detail/${encodeURIComponent(session)}`); },

    // ---- Files ----
    fileList()               { return this.get('/api/files/list'); },
    fileRead(path)           { return this.get(`/api/files/read?path=${encodeURIComponent(path)}`); },
    fileSave(path, content)  { return this.put('/api/files/save', { path, content }); },
    fileDelete(path)         { return this.post('/api/files/delete', { path }); },
};
