/**
 * auth.js - 登录页 & 密码修改逻辑
 */

const Auth = {
    init() {
        const btnLogin = document.getElementById('btn-login');
        if (btnLogin) btnLogin.addEventListener('click', () => this.doLogin());
        const loginPw = document.getElementById('login-password');
        if (loginPw) loginPw.addEventListener('keydown', e => {
            if (e.key === 'Enter') this.doLogin();
        });
        const btnChangePw = document.getElementById('btn-change-pw');
        if (btnChangePw) btnChangePw.addEventListener('click', () => this.doChangePassword());
        const confirmPw = document.getElementById('confirm-password');
        if (confirmPw) confirmPw.addEventListener('keydown', e => {
            if (e.key === 'Enter') this.doChangePassword();
        });
    },

    async doLogin() {
        const pw = document.getElementById('login-password').value.trim();
        if (!pw) return this._showError('login-error', '请输入密码');

        const res = await Api.login(pw);

        // 暴力破解锁定
        if (res.locked) {
            return this._showError('login-error',
                `密码错误次数过多，请等待 ${res.wait_seconds} 秒后再试`);
        }

        if (!res.ok) return this._showError('login-error', res.msg);

        Api.setToken(res.token);
        document.getElementById('login-password').value = '';
        this._hideError('login-error');

        if (!res.password_changed) {
            App.showPage('password-change');
        } else {
            App.showPage('main');
            App._initMain();
        }
    },

    async doChangePassword() {
        const oldPw = document.getElementById('old-password').value.trim();
        const newPw = document.getElementById('new-password').value.trim();
        const confirmPw = document.getElementById('confirm-password').value.trim();

        if (!oldPw || !newPw) return this._showError('pw-change-error', '请填写所有字段');
        if (newPw.length < 6) return this._showError('pw-change-error', '新密码至少6位');
        if (newPw !== confirmPw) return this._showError('pw-change-error', '两次密码不一致');

        const res = await Api.changePassword(oldPw, newPw);
        if (!res.ok) return this._showError('pw-change-error', res.msg);

        Api.setToken(res.token);
        this._hideError('pw-change-error');
        Utils.toast('密码修改成功', 'success');
        App.showPage('main');
        App._initMain();
    },

    logout() {
        Api.clearToken();
        App.showPage('login');
    },

    _showError(id, msg) {
        const el = document.getElementById(id);
        el.textContent = msg;
        el.classList.remove('hidden');
    },

    _hideError(id) {
        document.getElementById(id).classList.add('hidden');
    }
};
