// ================= 共享登录态管理（全站每个页面引入） =================
// 依赖后端：GET /api/me、POST /api/logout
// 用法：
//   Auth.refresh()                      -> 刷新登录态（自动在 DOMContentLoaded 时执行一次）
//   Auth.requireLogin('上传图片')        -> 未登录则引导去登录页，返回 false
//   document.addEventListener('auth:changed', fn)  -> 登录/退出后联动刷新 UI

const Auth = {
    user: null,      // 登录用户 { id, username, role }，未登录为 null
    ready: false,    // 登录态是否已拉取完成

    // 拉取当前登录态（游客 / 普通用户 / 管理员）
    async refresh() {
        try {
            const response = await fetch('/api/me', { credentials: 'same-origin' });
            const data = await response.json();
            // 后端约定：{ "user": {...} } 已登录，{ "user": null } 游客
            this.user = (data && data.user) ? data.user : null;
        } catch (error) {
            // 后端未启动或 file:// 直开时静默降级为游客
            this.user = null;
        }
        this.ready = true;
        this.renderNavAuth();
        document.dispatchEvent(new CustomEvent('auth:changed', { detail: { user: this.user } }));
        return this.user;
    },

    isAdmin() { return !!(this.user && this.user.role === 'admin'); },
    isLoggedIn() { return !!this.user; },

    // 需要登录才能做的操作：未登录时引导去登录页，回跳当前页面
    requireLogin(actionName) {
        if (this.user) return true;
        const next = encodeURIComponent(location.pathname + location.search);
        if (confirm((actionName || '该操作') + '需要登录，是否前往登录页面？')) {
            location.href = 'login.html?next=' + next;
        }
        return false;
    },

    async logout() {
        try {
            await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
        } catch (error) { /* 忽略网络错误，照常退出本地状态 */ }
        await this.refresh();
    },

    // 在导航栏右侧注入登录/用户区域（每个页面导航栏共用）
    renderNavAuth() {
        const navbar = document.querySelector('.navbar');
        if (!navbar || navbar.querySelector('.nav-auth')) return;

        const box = document.createElement('div');
        box.className = 'nav-auth';

        if (this.user) {
            const name = document.createElement('span');
            name.className = 'nav-username';
            name.textContent = this.user.username + (this.isAdmin() ? '（管理员）' : '');
            name.title = this.isAdmin() ? '管理员：拥有内容管理权限' : '普通用户：可浏览、AI 互动与上传';

            const btn = document.createElement('button');
            btn.className = 'nav-logout-btn';
            btn.textContent = '退出';
            btn.addEventListener('click', () => this.logout());

            box.appendChild(name);
            box.appendChild(btn);
        } else {
            const next = encodeURIComponent(location.pathname + location.search);
            const link = document.createElement('a');
            link.className = 'nav-login-link';
            link.href = 'login.html?next=' + next;
            link.textContent = '登录 / 注册';
            box.appendChild(link);
        }
        navbar.appendChild(box);
    }
};

document.addEventListener('DOMContentLoaded', () => Auth.refresh());
