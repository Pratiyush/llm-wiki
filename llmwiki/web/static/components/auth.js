/* Authentication component — login modal, token management */

const Auth = {
  user: null,

  init() {
    this.modal = document.getElementById('login-modal');
    this.loginForm = document.getElementById('login-form');
    this.loginBtn = document.getElementById('nav-login-btn');
    this.userInfo = document.getElementById('nav-user-info');
    this.usernameDisplay = document.getElementById('nav-username');
    this.logoutBtn = document.getElementById('nav-logout-btn');

    // Restore session
    var token = localStorage.getItem('llmwiki-token');
    if (token) {
      this._loadUser(token, true);
    }

    // Login button click
    this.loginBtn.addEventListener('click', function() { Auth.showModal(); });
    this.logoutBtn.addEventListener('click', function() { Auth.logout(); });

    // Login form submit
    this.loginForm.addEventListener('submit', function(e) {
      e.preventDefault();
      Auth.doLogin();
    });

    // Close modal
    document.getElementById('login-close').addEventListener('click', function() { Auth.hideModal(); });

    // Switch forms
    document.getElementById('switch-to-register').addEventListener('click', function(e) {
      e.preventDefault();
      document.getElementById('login-form').style.display = 'none';
      document.getElementById('register-form').style.display = 'block';
      document.querySelector('.modal-header span').textContent = '注册';
    });
    document.getElementById('switch-to-login').addEventListener('click', function(e) {
      e.preventDefault();
      document.getElementById('register-form').style.display = 'none';
      document.getElementById('login-form').style.display = 'block';
      document.querySelector('.modal-header span').textContent = '登录';
    });

    // Register form submit
    document.getElementById('register-form').addEventListener('submit', function(e) {
      e.preventDefault();
      Auth.doRegister();
    });

    this._updateUI();
    // If not logged in after init, clear chat
    if (!this.user && typeof QA !== 'undefined') {
      QA.clearChat();
    }
    console.log('[Auth] initialized, user:', this.user ? this.user.username : 'none');
  },

  getToken() {
    return localStorage.getItem('llmwiki-token') || '';
  },

  isLoggedIn() {
    return !!this.user;
  },

  isLeader() {
    return this.user && (this.user.role === 'leader' || this.user.role === 'admin');
  },

  isAdmin() {
    return this.user && this.user.role === 'admin';
  },

  showModal() {
    this.modal.style.display = 'flex';
  },

  hideModal() {
    this.modal.style.display = 'none';
  },

  async doLogin() {
    var username = document.getElementById('login-username').value.trim();
    var password = document.getElementById('login-password').value;
    var errorEl = document.getElementById('login-error');

    if (!username || !password) {
      errorEl.textContent = '请输入用户名和密码';
      return;
    }

    try {
      var resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password }),
      });
      var data = await resp.json();
      if (!resp.ok) {
        errorEl.textContent = data.detail || '登录失败';
        return;
      }

      localStorage.setItem('llmwiki-token', data.token);
      this.user = data.user;
      this.hideModal();
      this._updateUI();

      if (typeof QA !== 'undefined') QA.loadHistory();
      if (typeof Manager !== 'undefined' && Manager.loadApprovals) {
        Manager.loadApprovals();
      }
    } catch (e) {
      errorEl.textContent = '网络错误';
    }
  },

  async _loadUser(token, loadHistory) {
    try {
      var resp = await fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      if (resp.ok) {
        this.user = await resp.json();
        this._updateUI();
        if (loadHistory && typeof QA !== 'undefined') QA.loadHistory();
      } else {
        localStorage.removeItem('llmwiki-token');
        this.user = null;
        this._updateUI();
        if (typeof QA !== 'undefined') QA.clearChat();
      }
    } catch (e) {
      this.user = null;
      this._updateUI();
      if (typeof QA !== 'undefined') QA.clearChat();
    }
  },

  logout() {
    localStorage.removeItem('llmwiki-token');
    this.user = null;
    this._updateUI();
    if (typeof QA !== 'undefined') QA.clearChat();
  },

  async doRegister() {
    var username = document.getElementById('reg-username').value.trim();
    var password = document.getElementById('reg-password').value;
    var fullName = document.getElementById('reg-fullname').value.trim();
    var department = document.getElementById('reg-department').value.trim();
    var errorEl = document.getElementById('register-error');

    if (!username || !password) {
      errorEl.textContent = '请输入用户名和密码';
      return;
    }

    try {
      var resp = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password, full_name: fullName, department: department }),
      });
      var data = await resp.json();
      if (!resp.ok) {
        errorEl.textContent = data.detail || '注册失败';
        return;
      }

      localStorage.setItem('llmwiki-token', data.token);
      this.user = data.user;
      this.hideModal();
      this._updateUI();

      if (typeof QA !== 'undefined') QA.clearChat();
      if (typeof Manager !== 'undefined' && Manager.loadApprovals) {
        Manager.loadApprovals();
      }
    } catch (e) {
      errorEl.textContent = '网络错误';
    }
  },

  _updateUI() {
    if (this.user) {
      this.loginBtn.style.display = 'none';
      this.userInfo.style.display = 'flex';
      this.usernameDisplay.textContent = (this.user.full_name || this.user.username) + ' | ' + this.user.department;
    } else {
      this.loginBtn.style.display = 'inline-block';
      this.userInfo.style.display = 'none';
    }
  }
};
