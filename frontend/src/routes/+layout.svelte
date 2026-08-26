<script>
  import '../app.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let { children } = $props();
  let token = $state('');
  let user = $state(null);
  let checking = $state(true);
  let appVersion = $state('v0.1.0');

  // 主题切换（light / dark）
  let theme = $state('light');

  // 菜单折叠状态：默认折叠，点击后保持展开
  let menuCollapsed = $state(true);
  let manuallyToggled = $state(false);

  // 用户手动切换菜单状态
  function toggleMenu() {
    menuCollapsed = !menuCollapsed;
    manuallyToggled = true;
  }

  $effect(() => {
    theme = localStorage.getItem('theme') || 'light';
    document.documentElement.dataset.theme = theme;
  });

  // 获取版本号
  $effect(() => {
    fetch('/api/version')
      .then(r => r.json())
      .then(data => { appVersion = data.version; })
      .catch(() => {});
  });

  // 监听页面变化，非手动切换时恢复默认折叠状态
  $effect(() => {
    $page.url.pathname;
    if (!manuallyToggled) {
      menuCollapsed = true;
    }
  });

  function toggleTheme() {
    theme = theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', theme);
    document.documentElement.dataset.theme = theme;
  }

  // 修改密码弹窗状态
  let showChangePwd = $state(false);
  let pwdForm = $state({ old_password: '', new_password: '', confirm: '' });
  let pwdMsg = $state('');
  let pwdError = $state('');
  let pwdLoading = $state(false);

  // 登录页路由不参与鉴权布局，始终直接渲染表单
  const isLoginPage = $derived($page.url.pathname === '/admin/login');
  const initials = $derived((user?.username || '?').slice(0, 1).toUpperCase());

  // 当前页面标题（用于顶栏）
  const pageTitles = {
    '/admin/dashboard': '仪表盘',
    '/admin/repos': '仓库管理',
    '/admin/credentials': '凭据管理',
    '/admin/keys': 'Access Key',
    '/admin/permissions': '权限分配',
    '/admin/audit': '审计日志',
    '/admin/users': '用户管理',
    '/admin/llm': '大模型'
  };
  const pageTitle = $derived(pageTitles[$page.url.pathname] || 'Git MCP');

  // 菜单项
  const menuItems = [
    { path: '/admin/dashboard', icon: '📊', label: '仪表盘' },
    { path: '/admin/repos', icon: '📦', label: '仓库管理' },
    { path: '/admin/credentials', icon: '🔑', label: '凭据管理' },
    { path: '/admin/keys', icon: '🗝️', label: 'Access Key' },
    { path: '/admin/permissions', icon: '🔒', label: '权限分配' },
    { path: '/admin/audit', icon: '📋', label: '审计日志' },
    { path: '/admin/users', icon: '👥', label: '用户管理', adminOnly: true },
    { path: '/admin/llm', icon: '🤖', label: '大模型' }
  ];

  $effect(() => {
    token = localStorage.getItem('token') || '';
    if (token) {
      fetch('/api/auth/me', { headers: { Authorization: token } })
        .then((r) => (r.ok ? r.json() : null))
        .then((u) => {
          if (u) {
            user = u;
            checking = false;
          } else {
            localStorage.removeItem('token');
            token = '';
            checking = false;
          }
        })
        .catch(() => {
          user = null;
          token = '';
          checking = false;
        });
    } else {
      checking = false;
    }
  });

  function logout() {
    localStorage.removeItem('token');
    token = '';
    user = null;
    goto('/admin/login');
  }

  function openChangePwd() {
    pwdForm = { old_password: '', new_password: '', confirm: '' };
    pwdMsg = '';
    pwdError = '';
    showChangePwd = true;
  }

  async function changePassword() {
    pwdMsg = '';
    pwdError = '';
    if (!pwdForm.old_password || !pwdForm.new_password) {
      pwdError = '请填写完整';
      return;
    }
    if (pwdForm.new_password.length < 6) {
      pwdError = '新密码至少 6 位';
      return;
    }
    if (pwdForm.new_password !== pwdForm.confirm) {
      pwdError = '两次输入的新密码不一致';
      return;
    }
    pwdLoading = true;
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: token },
        body: JSON.stringify({ old_password: pwdForm.old_password, new_password: pwdForm.new_password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '修改失败');
      pwdMsg = '密码修改成功，下次登录请使用新密码';
      setTimeout(() => {
        showChangePwd = false;
      }, 1200);
    } catch (e) {
      pwdError = e.message;
    } finally {
      pwdLoading = false;
    }
  }
</script>

<svelte:head>
  <title>{pageTitle} - Git MCP Server</title>
  {#if !checking && !token && !isLoginPage}
    <meta http-equiv="refresh" content="0;url=/admin/login" />
  {/if}
</svelte:head>

{#if checking}
  <div class="min-h-screen flex items-center justify-center bg-base-200">
    <span class="loading loading-spinner loading-lg"></span>
  </div>
{:else if !token && !isLoginPage}
  <div class="min-h-screen flex items-center justify-center bg-base-200">
    <div class="text-center">
      <span class="loading loading-spinner loading-lg"></span>
      <p class="text-[var(--c-text-secondary)] mt-4">正在跳转到登录页...</p>
    </div>
  </div>
{:else if !token && isLoginPage}
  {@render children()}
{:else}
  <div class="drawer lg:drawer-open">
    <input id="drawer" type="checkbox" class="drawer-toggle" />
    <div class="drawer-content flex flex-col min-h-screen">
      <!-- 顶栏 -->
      <div class="navbar sticky top-0 z-30 h-16 px-3 md:px-6 backdrop-blur-md border-b shadow-sm bg-[var(--c-surface-glass)] border-[var(--c-border)]">
        <!-- 移动端汉堡按钮 -->
        <div class="flex-none lg:hidden">
          <label for="drawer" class="btn btn-square btn-ghost">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </label>
        </div>
        <!-- 左侧：Logo + 页面标题（桌面端） -->
        <div class="flex-1 flex items-center gap-3">
          <div class="hidden lg:flex items-center gap-2 text-[var(--c-text-secondary)]">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span class="text-sm font-medium">{pageTitle}</span>
          </div>
          <span class="lg:hidden text-lg font-bold text-[var(--c-text)]">{pageTitle}</span>
        </div>
        <!-- 右侧：主题切换 + 用户下拉菜单 -->
        <div class="flex-none flex items-center gap-1">
          <!-- 主题切换 -->
          <button
            class="btn btn-ghost btn-circle hover:bg-[var(--c-hover)]"
            onclick={toggleTheme}
            aria-label="切换主题"
            title={theme === 'light' ? '切换到深色模式' : '切换到浅色模式'}
          >
            {#if theme === 'light'}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-[var(--c-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
              </svg>
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-[var(--c-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
              </svg>
            {/if}
          </button>

          <!-- 用户下拉菜单 -->
          <div class="dropdown dropdown-end">
            <button tabindex="0" class="btn btn-ghost gap-2 px-2 normal-case hover:bg-[var(--c-hover)] rounded-full">
              <div class="avatar placeholder">
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-sm font-bold flex items-center justify-center">
                  {initials}
                </div>
              </div>
              <span class="hidden sm:inline text-sm font-medium text-[var(--c-text)]">{user?.username}</span>
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-[var(--c-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            <ul tabindex="0" class="dropdown-content menu bg-[var(--c-surface)] rounded-xl z-50 mt-2 w-56 p-2 shadow-xl border border-[var(--c-border)]">
              <li class="menu-title pointer-events-none">
                <span class="flex flex-col items-start">
                  <span class="font-semibold text-[var(--c-text)]">{user?.username}</span>
                  <span class="text-xs font-normal text-[var(--c-text-secondary)]">{user?.role === 'admin' ? '管理员' : '普通用户'}</span>
                </span>
              </li>
              <li><button onclick={openChangePwd} class="gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
                修改密码
              </button></li>
              <li><button onclick={logout} class="gap-2 text-error">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
                </svg>
                退出登录
              </button></li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Page Content -->
      <main class="flex-1 p-4 md:p-6 bg-[var(--c-page-bg)]">
        {@render children()}
      </main>
    </div>

    <!-- Sidebar -->
    <div class="drawer-side z-40">
      <label for="drawer" class="drawer-overlay"></label>
      <aside class="bg-[var(--c-surface)] min-h-full flex flex-col border-r border-[var(--c-border)] transition-all duration-300" class:w-64={!menuCollapsed} class:w-16={menuCollapsed}>
        <!-- 品牌 Logo -->
        <a href="/admin/dashboard" class="flex items-center gap-3 px-4 py-4 border-b border-[var(--c-border)]">
          <svg viewBox="0 0 64 64" class="h-10 w-10 shrink-0 drop-shadow-md" aria-label="Git MCP">
            <defs>
              <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#3b82f6" />
                <stop offset="1" stop-color="#4f46e5" />
              </linearGradient>
            </defs>
            <rect width="64" height="64" rx="14" fill="url(#logo-g)" />
            <g stroke="#ffffff" stroke-width="5" stroke-linecap="round" fill="none">
              <path d="M20 26v14" />
              <path d="M20 33l24 13" />
            </g>
            <circle cx="20" cy="19" r="6" fill="#ffffff" />
            <circle cx="20" cy="46" r="6" fill="#ffffff" />
            <circle cx="46" cy="46" r="6" fill="#ffffff" />
          </svg>
          {#if !menuCollapsed}
            <div>
              <div class="text-lg font-bold text-[var(--c-text)] leading-tight">Git MCP Server</div>
              <div class="text-xs text-[var(--c-text-secondary)] mt-0.5">v{appVersion.replace('v', '')}</div>
            </div>
          {/if}
        </a>

        <!-- 菜单折叠按钮 -->
        <button
          class="flex items-center justify-center py-2 text-[var(--c-text-secondary)] hover:text-[var(--c-text)] hover:bg-[var(--c-hover)] transition-colors border-b border-[var(--c-border)]"
          onclick={toggleMenu}
          title={menuCollapsed ? '展开菜单' : '折叠菜单'}
        >
          {#if menuCollapsed}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          {/if}
        </button>

        <!-- 菜单列表 -->
        <nav class="flex-1 overflow-y-auto py-2">
          <ul class="space-y-1" class:px-2={!menuCollapsed} class:px-1={menuCollapsed}>
            {#each menuItems as item}
              {#if !item.adminOnly || user?.role === 'admin'}
                <li>
                  <a
                    href={item.path}
                    class="flex items-center rounded-lg transition-all duration-200 group"
                    class:gap-3={!menuCollapsed}
                    class:justify-center={menuCollapsed}
                    class:px-3={!menuCollapsed}
                    class:px-2={menuCollapsed}
                    class:py-2.5={true}
                    class:bg-gradient-to-r={$page.url.pathname === item.path}
                    class:from-blue-500={$page.url.pathname === item.path}
                    class:to-indigo-600={$page.url.pathname === item.path}
                    class:text-white={$page.url.pathname === item.path}
                    class:text-[var(--c-text)]={$page.url.pathname !== item.path}
                    class:hover:bg-[var(--c-hover)]={$page.url.pathname !== item.path}
                    title={menuCollapsed ? item.label : ''}
                  >
                    <span class="text-lg">{item.icon}</span>
                    {#if !menuCollapsed}
                      <span class="text-sm font-medium truncate">{item.label}</span>
                    {/if}
                  </a>
                </li>
              {/if}
            {/each}
          </ul>
        </nav>

        <!-- 底部版权信息 -->
        <div class="border-t border-[var(--c-border)] py-3 text-center">
          {#if !menuCollapsed}
            <div class="px-4 text-xs text-[var(--c-text-secondary)]">
              @wangcw {(new Date().getFullYear()) > 2026 ? `2026-${new Date().getFullYear()}` : '2026'}
            </div>
          {:else}
            <div class="text-xs text-[var(--c-text-secondary)]">
              @{(new Date().getFullYear())}
            </div>
          {/if}
        </div>
      </aside>
    </div>
  </div>

  <!-- 修改密码弹窗 -->
  {#if showChangePwd}
    <div class="modal modal-open">
      <div class="modal-box rounded-2xl max-w-md">
        <h3 class="font-bold text-lg mb-1">🔒 修改密码</h3>
        <p class="text-sm text-[var(--c-text-secondary)] mb-4">修改后下次登录请使用新密码</p>

        {#if pwdMsg}
          <div class="alert alert-info rounded-xl py-2.5 text-sm mb-4 shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            <span>{pwdMsg}</span>
          </div>
        {/if}
        {#if pwdError}
          <div class="alert alert-error rounded-xl py-2.5 text-sm mb-4 shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <span>{pwdError}</span>
          </div>
        {/if}

        <label class="block mb-3">
          <span class="mb-1.5 block text-sm font-medium text-[var(--c-text-secondary)]">旧密码</span>
          <input
            type="password"
            class="input input-bordered w-full rounded-xl focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 transition-all"
            placeholder="请输入旧密码"
            bind:value={pwdForm.old_password}
            autocomplete="current-password"
          />
        </label>
        <label class="block mb-3">
          <span class="mb-1.5 block text-sm font-medium text-[var(--c-text-secondary)]">新密码</span>
          <input
            type="password"
            class="input input-bordered w-full rounded-xl focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 transition-all"
            placeholder="至少 6 位"
            bind:value={pwdForm.new_password}
            autocomplete="new-password"
          />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-sm font-medium text-[var(--c-text-secondary)]">确认新密码</span>
          <input
            type="password"
            class="input input-bordered w-full rounded-xl focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 transition-all"
            placeholder="再次输入新密码"
            bind:value={pwdForm.confirm}
            autocomplete="new-password"
            onkeydown={(e) => e.key === 'Enter' && changePassword()}
          />
        </label>

        <div class="modal-action">
          <button class="btn btn-ghost rounded-xl" onclick={() => (showChangePwd = false)}>取消</button>
          <button
            class="btn rounded-xl border-0 bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-md shadow-blue-500/25 hover:from-blue-600 hover:to-indigo-700"
            onclick={changePassword}
            disabled={pwdLoading}
          >
            {#if pwdLoading}
              <span class="loading loading-spinner loading-sm"></span>
              提交中...
            {:else}
              确认修改
            {/if}
          </button>
        </div>
      </div>
      <div class="modal-backdrop" onclick={() => (showChangePwd = false)}></div>
    </div>
  {/if}
{/if}
