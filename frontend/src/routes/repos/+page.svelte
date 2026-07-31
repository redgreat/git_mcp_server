<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';

  let repos = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let editingId = $state(null);
  let form = $state({ name: '', url: '', main_branch: 'main', credential_id: null, enabled: true, allow_write: false, allow_push: false, description: '' });
  let credentials = $state([]);
  // 拉取状态
  let fetchingId = $state(null);
  let toast = $state(null); // { type: 'success'|'error', message: string }
  let toastTimer = null;

  const token = () => localStorage.getItem('token') || '';

  function showToast(type, message) {
    toast = { type, message };
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast = null; }, 3500);
  }

  async function fetchRepo(r) {
    if (fetchingId) return;
    fetchingId = r.id;
    try {
      const res = await fetch(`/api/admin/repos/${r.id}/fetch`, {
        method: 'POST', headers: { Authorization: token() }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '拉取失败');
      showToast('success', `✅ ${r.name}：${data.message}`);
      await load(); // 刷新 last_fetched_at
    } catch (e) {
      showToast('error', `❌ ${r.name}：${e.message}`);
    } finally {
      fetchingId = null;
    }
  }

  async function load() {
    const res = await fetch('/api/admin/repos', { headers: { Authorization: token() } });
    if (res.ok) repos = await res.json();
    loading = false;
  }

  async function loadCredentials() {
    const res = await fetch('/api/admin/credentials', { headers: { Authorization: token() } });
    if (res.ok) credentials = await res.json();
  }

  function openCreate() {
    editingId = null;
    form = { name: '', url: '', main_branch: 'main', credential_id: null, enabled: true, allow_write: false, allow_push: false, description: '' };
    showForm = true;
    loadCredentials();
  }

  function openEdit(r) {
    editingId = r.id;
    form = { name: r.name, url: r.url, main_branch: r.main_branch, credential_id: r.credential_id, enabled: r.enabled, allow_write: r.allow_write, allow_push: r.allow_push, description: r.description || '' };
    showForm = true;
    loadCredentials();
  }

  async function save() {
    const method = editingId ? 'PUT' : 'POST';
    const url = editingId ? `/api/admin/repos/${editingId}` : '/api/admin/repos';
    await fetch(url, {
      method, headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify(form)
    });
    showForm = false;
    await load();
  }

  async function remove(id) {
    if (!confirm('确定删除此仓库？')) return;
    await fetch(`/api/admin/repos/${id}`, { method: 'DELETE', headers: { Authorization: token() } });
    await load();
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">📦 仓库管理</h1>
    <button class={btnPrimaryCls} onclick={openCreate}>+ 添加仓库</button>
  </div>

  <!-- 操作结果提示 -->
  {#if toast}
    <div class="fixed top-20 right-4 z-50 max-w-sm">
      <div class="alert {toast.type === 'success' ? 'alert-info' : 'alert-error'} rounded-xl shadow-2xl border border-[var(--c-border)]">
        <span class="text-sm break-all">{toast.message}</span>
      </div>
    </div>
  {/if}

  <!-- 添加/编辑仓库弹窗 -->
  {#if showForm}
    <Modal
      title={editingId ? '编辑仓库' : '添加仓库'}
      subtitle="配置 Git 仓库的克隆地址、认证凭据与权限开关"
      width="max-w-lg"
      onClose={() => (showForm = false)}
    >
      <FormField label="仓库名称" required hint="仓库在系统中的唯一标识，如 my-project-backend">
        <input type="text" class={inputCls} bind:value={form.name} placeholder="如: my-project-backend" />
      </FormField>
      <FormField label="Git Clone URL" required>
        <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.url} placeholder="https://github.com/user/repo.git" />
      </FormField>
      <div class="grid grid-cols-2 gap-3">
        <FormField label="主分支">
          <input type="text" class={inputCls} bind:value={form.main_branch} placeholder="main" />
        </FormField>
        <FormField label="Git 凭据">
          <select class={selectCls} bind:value={form.credential_id}>
            <option value={null}>无（公开仓库）</option>
            {#each credentials as c}
              <option value={c.id}>{c.name} ({c.auth_type})</option>
            {/each}
          </select>
        </FormField>
      </div>
      <FormField label="描述">
        <input type="text" class={inputCls} bind:value={form.description} placeholder="仓库用途说明（可选）" />
      </FormField>
      <div class="flex flex-wrap gap-5 mb-2">
        <label class="label cursor-pointer gap-2">
          <input type="checkbox" class="toggle toggle-sm" bind:checked={form.enabled} />
          <span class="label-text text-sm text-[var(--c-text)]">启用</span>
        </label>
        <label class="label cursor-pointer gap-2">
          <input type="checkbox" class="toggle toggle-sm" bind:checked={form.allow_write} />
          <span class="label-text text-sm text-[var(--c-text)]">允许写入</span>
        </label>
        <label class="label cursor-pointer gap-2">
          <input type="checkbox" class="toggle toggle-sm" bind:checked={form.allow_push} />
          <span class="label-text text-sm text-[var(--c-text)]">允许推送</span>
        </label>
      </div>
      <div class="alert alert-info rounded-xl py-2.5 text-xs shadow-sm">
        ⚠️ 允许写入/推送会开放仓库修改权限，请谨慎开启
      </div>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showForm = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={save} disabled={!form.name || !form.url}>保存</button>
      {/snippet}
    </Modal>
  {/if}

  {#if loading}
    <div class="flex justify-center py-16"><span class="loading loading-spinner loading-lg"></span></div>
  {:else}
    <div class="overflow-x-auto bg-[var(--c-surface)] rounded-xl shadow border border-[var(--c-border)]">
      <table class="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>URL</th>
            <th>主分支</th>
            <th>写/推送</th>
            <th>状态</th>
            <th>最近拉取</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each repos as r}
            <tr>
              <td class="font-bold text-[var(--c-text)]">{r.name}</td>
              <td class="text-xs font-mono max-w-60 truncate text-[var(--c-text-secondary)]">{r.url}</td>
              <td><span class="badge badge-outline badge-sm">{r.main_branch}</span></td>
              <td>
                <span class="badge {r.allow_write ? 'badge-warning' : 'badge-ghost'} badge-xs mr-1">写:{r.allow_write ? '✓' : '✗'}</span>
                <span class="badge {r.allow_push ? 'badge-error' : 'badge-ghost'} badge-xs">推:{r.allow_push ? '✓' : '✗'}</span>
              </td>
              <td><span class="badge {r.enabled ? 'badge-success' : 'badge-ghost'} badge-xs">{r.enabled ? '启用' : '停用'}</span></td>
              <td class="text-xs whitespace-nowrap text-[var(--c-text-secondary)]">
                {r.last_fetched_at ? new Date(r.last_fetched_at).toLocaleString() : '从未拉取'}
              </td>
              <td>
                <div class="flex gap-1">
                  <button
                    class="btn btn-xs {fetchingId === r.id ? 'btn-ghost' : 'btn-outline'}"
                    onclick={() => fetchRepo(r)}
                    disabled={fetchingId !== null}
                    title="拉取最新代码"
                  >
                    {#if fetchingId === r.id}
                      <span class="loading loading-spinner loading-xs"></span>
                      拉取中...
                    {:else}
                      ⬇️ 拉取
                    {/if}
                  </button>
                  <button class="btn btn-xs btn-ghost" onclick={() => openEdit(r)}>编辑</button>
                  <button class="btn btn-xs btn-ghost text-error" onclick={() => remove(r.id)}>删除</button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if repos.length === 0}
      <div class="text-center text-[var(--c-text-secondary)] py-8">暂无仓库，点击右上角添加</div>
    {/if}
  {/if}
</div>
