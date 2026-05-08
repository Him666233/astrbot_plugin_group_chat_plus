/**
 * api.js - HTTP 客户端封装 (cookie session + auth events)
 */

const Api = {
    _authListeners: new Set(),
    _inflightHeartbeat: null,

    init() {
        try {
            localStorage.removeItem('gcp_token');
        } catch (e) {
            console.warn('清理旧 token 失败:', e);
        }
    },

    onAuthEvent(listener) {
        this._authListeners.add(listener);
        return () => this._authListeners.delete(listener);
    },

    emitAuthEvent(type, detail = {}) {
        this._authListeners.forEach((listener) => {
            try {
                listener({ type, ...detail });
            } catch (error) {
                console.error('Auth listener failed:', error);
            }
        });
    },

    clearToken() {
        try {
            localStorage.removeItem('gcp_token');
        } catch (e) {
            console.warn('清理旧 token 失败:', e);
        }
        document.cookie = 'gcp_token=; path=/; SameSite=Strict; max-age=0';
    },

    async request(method, path, body, options = {}) {
        const headers = { 'Content-Type': 'application/json' };
        const fetchOptions = {
            method: method || 'GET',
            headers,
            credentials: 'same-origin',
            ...options,
        };
        if (body !== undefined) {
            fetchOptions.body = JSON.stringify(body);
        }
        try {
            const resp = await fetch(path, fetchOptions);

            if (resp.status === 429) {
                return await resp.json();
            }

            if (resp.status === 403) {
                let data;
                try { data = await resp.json(); } catch (e) { data = { ok: false, msg: '访问被拒绝' }; }
                if (data.blocked) {
                    this.emitAuthEvent('blocked', data);
                    window.location.href = '/error?code=blocked';
                }
                return data;
            }

            if (resp.status === 401) {
                let data;
                try { data = await resp.json(); } catch (e) { data = { ok: false, reason: 'expired', msg: '登录已失效，请重新登录' }; }
                if (path === '/api/auth/login') {
                    return data;
                }
                this.clearToken();
                this.emitAuthEvent('unauthorized', data);
                return data;
            }

            return await resp.json();
        } catch (e) {
            return { ok: false, network_error: true, msg: `网络错误: ${e.message}` };
        }
    },

    get(path, options)        { return this.request('GET', path, undefined, options); },
    post(path, body, options) { return this.request('POST', path, body, options); },
    put(path, body, options)  { return this.request('PUT', path, body, options); },

    login(password)          { return this.post('/api/auth/login', { password }); },
    authStatus()             { return this.get('/api/auth/status'); },
    changePassword(old_password, new_password) {
        return this.post('/api/auth/change-password', { old_password, new_password });
    },
    verify()                 { return this.get('/api/auth/verify'); },
    heartbeat() {
        if (this._inflightHeartbeat) return this._inflightHeartbeat;
        this._inflightHeartbeat = this.get('/api/auth/heartbeat').finally(() => {
            this._inflightHeartbeat = null;
        });
        return this._inflightHeartbeat;
    },
    logout()                 { return this.post('/api/auth/logout', {}); },

    getConfig()              { return this.get('/api/config'); },
    putConfig(config)        { return this.put('/api/config', { config }); },
    reloadPlugin(config)     { return this.post('/api/config/reload', config ? { config } : {}); },

    dataSessions()           { return this.get('/api/data/sessions'); },
    dataAttention(session)   { return this.get(`/api/data/attention/${encodeURIComponent(session)}`); },
    dataMood(session)        { return this.get(`/api/data/mood/${encodeURIComponent(session)}`); },
    dataProbability(session) { return this.get(`/api/data/probability/${encodeURIComponent(session)}`); },
    dataProactive()          { return this.get('/api/data/proactive'); },
    dataOverview()           { return this.get('/api/data/overview'); },
    dataStatus()             { return this.get('/api/data/status'); },

    sessionList()            { return this.get('/api/session/list'); },
    sessionReset(session)    { return this.post(`/api/session/reset/${encodeURIComponent(session)}`); },
    clearImageCache()        { return this.post('/api/session/clear-image-cache'); },
    getChatHistory(session)  { return this.get(`/api/session/chat-history/${encodeURIComponent(session)}`); },
    putChatHistory(session, messages) {
        return this.put(`/api/session/chat-history/${encodeURIComponent(session)}`, { messages });
    },
    getImageCache()          { return this.get('/api/session/image-cache'); },

    cmdReset(restart_mode)               { return this.post('/api/commands/reset', { restart_mode }); },
    cmdResetHere(session_id, restart_mode) { return this.post('/api/commands/reset-here', { session_id, restart_mode }); },
    cmdClearImageCache(restart_mode)     { return this.post('/api/commands/clear-image-cache', { restart_mode }); },

    getAccessLog(page, size) { return this.get(`/api/security/access-log?page=${page}&size=${size}`); },
    getBans()                { return this.get('/api/security/bans'); },
    banIp(ip, duration, reason) { return this.post('/api/security/ban', { ip, duration, reason }); },
    unbanIp(ip)              { return this.post('/api/security/unban', { ip }); },
    getIpConfig()            { return this.get('/api/security/ip-config'); },
    putIpConfig(config)      { return this.put('/api/security/ip-config', config); },

    sessionDetail(session)   { return this.get(`/api/data/session-detail/${encodeURIComponent(session)}`); },

    fileList()               { return this.get('/api/files/list'); },
    fileRead(path)           { return this.get(`/api/files/read?path=${encodeURIComponent(path)}`); },
    fileSave(path, content)  { return this.put('/api/files/save', { path, content }); },
    fileDelete(path)         { return this.post('/api/files/delete', { path }); },
};

Api.init();
