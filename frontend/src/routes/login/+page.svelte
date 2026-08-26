<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let username = $state('');
  let password = $state('');
  let error = $state('');
  let loading = $state(false);
  let showPassword = $state(false);
  let currentYear = $state(new Date().getFullYear());

  onMount(() => {
    if (localStorage.getItem('token')) goto('/admin/dashboard');
  });

  async function login() {
    if (!username.trim() || !password) {
      error = '请输入用户名和密码';
      return;
    }
    loading = true;
    error = '';
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '登录失败');
      localStorage.setItem('token', data.token);
      window.location.href = '/admin/dashboard';
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-700 p-4">
  <!-- 背景装饰：模糊光斑 -->
  <div class="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-sky-400/30 blur-3xl"></div>
  <div class="pointer-events-none absolute -bottom-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-blue-300/25 blur-3xl"></div>
  <div class="pointer-events-none absolute top-1/3 left-1/2 h-64 w-64 -translate-x-1/2 rounded-full bg-white/10 blur-2xl"></div>

  <!-- 品牌区（大屏左侧） -->
  <div class="relative z-10 hidden lg:flex flex-col justify-center max-w-md mr-16 text-white">
    <div class="flex items-center gap-3 mb-6">
      <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 backdrop-blur-md border border-white/25 shadow-lg">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 11v6m-3-3l3 3 3-3" />
        </svg>
      </div>
      <div>
        <h1 class="text-3xl font-bold tracking-tight">Git MCP Server</h1>
        <p class="text-blue-100/80 text-sm">Git 仓库管理服务</p>
      </div>
    </div>
    <p class="text-blue-50/90 text-lg leading-relaxed mb-8">
      基于 MCP (Model Context Protocol) 的 Git 仓库管理服务，让 AI 助手安全、可控地访问你的代码仓库。
    </p>
    <ul class="space-y-3 text-blue-50/85 text-sm">
      <li class="flex items-center gap-2">
        <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
        </span>
        Access Key 精准控制仓库访问权限
      </li>
      <li class="flex items-center gap-2">
        <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
        </span>
        仓库级 + 分支 + 路径细粒度权限
      </li>
      <li class="flex items-center gap-2">
        <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
        </span>
        完整审计日志与内置大模型分析
      </li>
    </ul>
  </div>

  <!-- 登录卡片 -->
  <div class="relative z-10 w-full max-w-md">
    <div class="rounded-3xl bg-[var(--c-surface-glass)] backdrop-blur-2xl shadow-2xl shadow-blue-900/20 border border-white/40 p-8 md:p-10">
      <!-- 移动端品牌 -->
      <div class="lg:hidden flex flex-col items-center mb-8">
        <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 11v6m-3-3l3 3 3-3" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-[var(--c-text)]">Git MCP Server 管理后台</h1>
      </div>

      <!-- 桌面端标题 -->
      <div class="hidden lg:block mb-8">
        <h2 class="text-2xl font-bold text-[var(--c-text)]">欢迎回来</h2>
        <p class="text-[var(--c-text-secondary)] text-sm mt-1">登录管理后台，继续你的工作</p>
      </div>

      {#if error}
        <div class="alert alert-error mb-5 rounded-xl py-2.5 text-sm shadow-sm">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span>{error}</span>
        </div>
      {/if}

      <div class="space-y-4">
        <label class="block">
          <span class="mb-1.5 block text-sm font-medium text-[var(--c-text-secondary)]">用户名</span>
          <div class="relative">
            <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[var(--c-text-secondary)]">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 20.25a7.5 7.5 0 0115 0" />
              </svg>
            </span>
            <input
              type="text"
              class="input input-bordered w-full rounded-xl bg-[var(--c-surface)] border-[var(--c-border)] pl-11 py-3 text-[var(--c-text)] placeholder:text-[var(--c-text-secondary)] focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 transition-all"
              placeholder="请输入用户名"
              bind:value={username}
              autocomplete="username"
            />
          </div>
        </label>

        <label class="block">
          <span class="mb-1.5 block text-sm font-medium text-[var(--c-text-secondary)]">密码</span>
          <div class="relative">
            <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[var(--c-text-secondary)]">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </span>
            <input
              type={showPassword ? 'text' : 'password'}
              class="input input-bordered w-full rounded-xl bg-[var(--c-surface)] border-[var(--c-border)] pl-11 pr-11 py-3 text-[var(--c-text)] placeholder:text-[var(--c-text-secondary)] focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 transition-all"
              placeholder="请输入密码"
              bind:value={password}
              autocomplete="current-password"
              onkeydown={(e) => e.key === 'Enter' && login()}
            />
            <button
              type="button"
              class="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--c-text-secondary)] hover:text-[var(--c-text)] transition-colors"
              onclick={() => (showPassword = !showPassword)}
              aria-label={showPassword ? '隐藏密码' : '显示密码'}
            >
              {#if showPassword}
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
              {:else}
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              {/if}
            </button>
          </div>
        </label>

        <button
          class="btn w-full rounded-xl border-0 bg-gradient-to-r from-blue-500 to-indigo-600 py-3 text-white shadow-lg shadow-blue-500/25 hover:from-blue-600 hover:to-indigo-700 hover:shadow-blue-600/30 active:scale-[0.98] transition-all disabled:opacity-60"
          onclick={login}
          disabled={loading}
        >
          {#if loading}
            <span class="loading loading-spinner loading-sm"></span>
            登录中...
          {:else}
            登 录
          {/if}
        </button>
      </div>

    </div>

    <p class="mt-6 text-center text-sm text-blue-100/70">@wangcw {currentYear > 2026 ? `2026-${currentYear}` : '2026'}</p>
  </div>
</div>
