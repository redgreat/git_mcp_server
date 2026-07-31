<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, btnPrimaryCls, btnGhostCls, btnDangerCls } from '$lib/ui.js';

  let users = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let showResetPwd = $state(false);
  let resetTarget = $state(null);
  let form = $state({ username: '', password: '', email: '', role: 'user' });
  let resetForm = $state({ new_password: '' });

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    const res = await fetch('/api/admin/users', { headers: { Authorization: token() } });
    if (res.ok) users = await res.json();
    loading = false;
  }

  async function createUser() {
    const res = await fetch('/api/admin/users', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify(form)
    });
    if (res.ok) { showForm = false; await load(); }
  }

  async function toggleUser(id, isActive) {
    await fetch(`/api/admin/users/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify({ is_active: isActive })
    });
    await load();
  }

  async function toggleRole(id, currentRole) {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    await fetch(`/api/admin/users/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify({ role: newRole })
    });
    await load();
  }

  function openResetPwd(user) {
    resetTarget = user;
    resetForm = { new_password: '' };
    showResetPwd = true;
  }

  async function resetPassword() {
    if (!resetTarget || !resetForm.new_password) return;
    await fetch(`/api/admin/users/${resetTarget.id}/reset-password`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify({ new_password: resetForm.new_password })
    });
    showResetPwd = false;
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">👥 用户管理</h1>
    <button class={btnPrimaryCls} onclick={() => { form = { username: '', password: '', email: '', role: 'user' }; showForm = true; }}>+ 添加用户</button>
  </div>

  <!-- 添加用户弹窗 -->
  {#if showForm}
    <Modal
      title="添加用户"
      subtitle="创建后台登录账号并分配角色"
      width="max-w-md"
      onClose={() => (showForm = false)}
    >
      <FormField label="用户名" required>
        <input type="text" class={inputCls} bind:value={form.username} placeholder="登录用户名" autocomplete="off" />
      </FormField>
      <FormField label="密码" required hint="至少 6 位">
        <input type="password" class={inputCls} bind:value={form.password} placeholder="初始密码" autocomplete="new-password" />
      </FormField>
      <FormField label="邮箱">
        <input type="email" class={inputCls} bind:value={form.email} placeholder="user@example.com" />
      </FormField>
      <FormField label="角色">
        <select class={selectCls} bind:value={form.role}>
          <option value="user">普通用户</option>
          <option value="admin">管理员</option>
        </select>
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showForm = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={createUser} disabled={!form.username || !form.password}>创建</button>
      {/snippet}
    </Modal>
  {/if}

  <!-- 重置密码弹窗 -->
  {#if showResetPwd}
    <Modal
      title={`重置密码 - ${resetTarget?.username}`}
      subtitle="重置后该用户将使用新密码登录"
      width="max-w-sm"
      onClose={() => (showResetPwd = false)}
    >
      <FormField label="新密码" required hint="至少 6 位">
        <input type="password" class={inputCls} bind:value={resetForm.new_password} placeholder="新密码" autocomplete="new-password" />
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showResetPwd = false)}>取消</button>
        <button class={btnDangerCls} onclick={resetPassword} disabled={!resetForm.new_password}>重置</button>
      {/snippet}
    </Modal>
  {/if}

  {#if loading}
    <div class="flex justify-center py-16"><span class="loading loading-spinner loading-lg"></span></div>
  {:else}
    <div class="overflow-x-auto bg-[var(--c-surface)] rounded-xl shadow border border-[var(--c-border)]">
      <table class="table">
        <thead>
          <tr><th>用户名</th><th>邮箱</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          {#each users as u}
            <tr>
              <td class="font-bold text-[var(--c-text)]">{u.username}</td>
              <td class="text-xs text-[var(--c-text-secondary)]">{u.email || '-'}</td>
              <td>
                <button class="badge {u.role === 'admin' ? 'badge-primary' : 'badge-ghost'} badge-sm cursor-pointer"
                        onclick={() => toggleRole(u.id, u.role)}>{u.role}</button>
              </td>
              <td>
                <label class="label cursor-pointer gap-1 p-0">
                  <input type="checkbox" class="toggle toggle-sm" checked={u.is_active}
                         onchange={(e) => toggleUser(u.id, e.target.checked)} />
                  <span class="text-xs text-[var(--c-text-secondary)]">{u.is_active ? '启用' : '禁用'}</span>
                </label>
              </td>
              <td class="text-xs text-[var(--c-text-secondary)]">{new Date(u.created_at).toLocaleString()}</td>
              <td>
                <button class="btn btn-xs btn-ghost" onclick={() => openResetPwd(u)}>重置密码</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
