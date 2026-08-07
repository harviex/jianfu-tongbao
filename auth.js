// ========== 统一密码认证模块 ==========
// 保护所有 https://harviex.github.io/jianfu-tongbao/* 页面
// 默认密码 SHA-256: 0139ac6fa1fb1ec90bc15fe5eb13421f32579bce849ab697aa3ef3b77823ae17 (原文: 1357924680)
// 密码哈希存储在 localStorage.jianfu_password_hash，可通过后台管理修改

(function () {
  'use strict';

  const AUTH_KEY = 'jianfu_auth_token';
  const AUTH_EXPIRY_KEY = 'jianfu_auth_expiry';
  const PASSWORD_HASH_KEY = 'jianfu_password_hash';
  const SESSION_DURATION = 24 * 60 * 60 * 1000; // 24小时
  const DEFAULT_PASSWORD_HASH = '0139ac6fa1fb1ec90bc15fe5eb13421f32579bce849ab697aa3ef3b77823ae17';

  // 首次初始化：若 localStorage 无哈希，写入默认值
  function initPasswordHash() {
    if (!localStorage.getItem(PASSWORD_HASH_KEY)) {
      localStorage.setItem(PASSWORD_HASH_KEY, DEFAULT_PASSWORD_HASH);
    }
  }

  // 获取当前密码哈希
  function getPasswordHash() {
    return localStorage.getItem(PASSWORD_HASH_KEY) || DEFAULT_PASSWORD_HASH;
  }

  // 修改密码（供后台管理调用）
  // 返回 Promise，resolve(true) 成功，resolve(false) 失败
  window.changePassword = async function (oldPwd, newPwd) {
    const currentHash = getPasswordHash();
    const oldHash = await sha256(oldPwd);
    if (oldHash !== currentHash) {
      return false; // 旧密码错误
    }
    const newHash = await sha256(newPwd);
    localStorage.setItem(PASSWORD_HASH_KEY, newHash);
    // 修改密码后使当前会话失效，需重新登录
    sessionStorage.removeItem(AUTH_KEY);
    sessionStorage.removeItem(AUTH_EXPIRY_KEY);
    return true;
  };

  // 简单的 SHA-256 实现
  async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  // 检查是否已认证
  function checkAuth() {
    const token = sessionStorage.getItem(AUTH_KEY);
    const expiry = sessionStorage.getItem(AUTH_EXPIRY_KEY);
    if (token && expiry && Date.now() < parseInt(expiry, 10)) {
      return token === getPasswordHash();
    }
    sessionStorage.removeItem(AUTH_KEY);
    sessionStorage.removeItem(AUTH_EXPIRY_KEY);
    return false;
  }

  // 创建密码输入模态框
  function createAuthModal() {
    // 1. 把现有页面内容包装在一个容器里，只对容器加模糊
    let contentWrapper = document.getElementById('auth-content-wrapper');
    if (!contentWrapper) {
      contentWrapper = document.createElement('div');
      contentWrapper.id = 'auth-content-wrapper';
      // 把 body 里除 script 和 将来的 modal 外的所有节点移进 wrapper
      const childrenToMove = [];
      for (const child of document.body.childNodes) {
        if (child.nodeType === Node.ELEMENT_NODE) {
          if (child.tagName !== 'SCRIPT' && child.id !== 'auth-modal') {
            childrenToMove.push(child);
          }
        } else if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
          childrenToMove.push(child);
        }
      }
      childrenToMove.forEach(child => contentWrapper.appendChild(child));
      document.body.insertBefore(contentWrapper, document.body.firstChild);
    }
    // 对内容容器加毛玻璃
    contentWrapper.style.filter = 'blur(8px)';
    contentWrapper.style.pointerEvents = 'none';
    contentWrapper.style.userSelect = 'none';

    // 2. 创建模态框，作为 body 直接子元素（与 wrapper 同级），不受模糊影响
    const modal = document.createElement('div');
    modal.id = 'auth-modal';
    modal.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center;
      z-index: 99999; font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    `;
    modal.innerHTML = `
      <div style="
        background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        width: 100%; max-width: 360px; text-align: center;
      ">
        <div style="font-size: 48px; margin-bottom: 16px;">🔐</div>
        <h2 style="margin: 0 0 8px; color: #1a1a2e; font-size: 22px;">整治形式主义为基层减负信息平台</h2>
        <p style="margin: 0 0 24px; color: #666; font-size: 14px;">请输入访问密码</p>
        <input type="password" id="auth-password" placeholder="请输入密码" style="
          width: 100%; padding: 14px 16px; font-size: 16px; border: 1px solid #ddd;
          border-radius: 8px; box-sizing: border-box; outline: none;
          transition: border-color 0.2s;
        ">
        <p id="auth-error" style="color: #c41e3a; font-size: 13px; margin: 12px 0 0; min-height: 18px; display: none;"></p>
        <button id="auth-submit" style="
          width: 100%; margin-top: 20px; padding: 14px; font-size: 16px; font-weight: 600;
          color: #fff; background: linear-gradient(180deg, #c41e3a 0%, #a01830 100%);
          border: none; border-radius: 8px; cursor: pointer; transition: opacity 0.2s;
        ">进入系统</button>
      </div>
    `;
    document.body.appendChild(modal);

    const input = modal.querySelector('#auth-password');
    const errorEl = modal.querySelector('#auth-error');
    const submitBtn = modal.querySelector('#auth-submit');

    setTimeout(() => input.focus(), 100);

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitBtn.click();
    });

    submitBtn.addEventListener('click', async () => {
      const pwd = input.value.trim();
      if (!pwd) {
        errorEl.textContent = '请输入密码';
        errorEl.style.display = 'block';
        input.focus();
        return;
      }
      submitBtn.disabled = true;
      submitBtn.textContent = '验证中...';
      submitBtn.style.opacity = '0.7';

      try {
        const hash = await sha256(pwd);
        if (hash === getPasswordHash()) {
          sessionStorage.setItem(AUTH_KEY, hash);
          sessionStorage.setItem(AUTH_EXPIRY_KEY, String(Date.now() + SESSION_DURATION));
          document.body.removeChild(modal);
          // 恢复页面显示
          const wrapper = document.getElementById('auth-content-wrapper');
          if (wrapper) {
            wrapper.style.filter = '';
            wrapper.style.pointerEvents = '';
            wrapper.style.userSelect = '';
          }
          if (typeof window.onAuthSuccess === 'function') {
            window.onAuthSuccess();
          }
        } else {
          errorEl.textContent = '密码错误，请重试';
          errorEl.style.display = 'block';
          input.value = '';
          input.focus();
        }
      } catch (err) {
        errorEl.textContent = '验证失败，请刷新重试';
        errorEl.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '进入系统';
        submitBtn.style.opacity = '1';
      }
    });
  }

  // 启动认证检查
  function initAuth() {
    initPasswordHash();
    if (!checkAuth()) {
      createAuthModal();
    }
  }

  // DOM 就绪后执行
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
  } else {
    initAuth();
  }
})();