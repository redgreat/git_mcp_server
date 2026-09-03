<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';
  import Pager from '$lib/components/Pager.svelte';
  import RefreshBtn from '$lib/components/RefreshBtn.svelte';

  let perms = $state([]);
  let keys = $state([]);
  let repos = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let editingId = $state(null);
  let form = $state({ key_id: null, repo_id: null, access_level: 'read_only', branch_pattern: '.*', path_pattern: '.*' });

  const token = () => localStorage.getItem('token') || '';

  // 客户端分页
  let page = $state(1);
  let pageSize = 15;
  let curPage = $derived(Math.min(page, Math.max(1, Math.ceil(perms.length / pageSize))));
  let shownPerms = $derived(perms.slice((curPage - 1) * pageSize, curPage * pageSize));
  function goPage(p) {
    const tp = Math.max(1, Math.ceil(perms.length / pageSize));
    if (p >= 1 && p <= tp) page = p;
  }

  async function load() {
    const [pRes, kRes, rRes] = await Promise.all([
      fetch('/api/admin/permissions', { headers: { Authorization: token() } }),
      fetch('/api/admin/keys', { headers: { Authorization: token() } }),
      fetch('/api/admin/repos', { headers: { Authorization: token() } })
    ]);
    if (pRes.ok) perms = await pRes.json();
    if (kRes.ok) keys = await kRes.json();
    if (rRes.ok) repos = await rRes.json();
    loading = false;
  }

  function openGrant() {
    editingId = null;
    form = { key_id: null, repo_id: null, access_level: 'read_only', branch_pattern: '.*', path_pattern: '.*' };
    showForm = true;
  }

  function openEdit(p) {
    editingId = p.id;
    form = {
      key_id: p.key_id,
      repo_id: p.repo_id,
      access_level: p.access_level,
      branch_pattern: p.branch_pattern,
      path_pattern: p.path_pattern
    };
    showForm = true;
  }

  async function save() {
    if (!form.key_id || !form.repo_id) return;
    let res;
    if (editingId) {
      res = await fetch(`/api/admin/permissions/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: token() },
        body: JSON.stringify({
          key_id: form.key_id,
          repo_id: form.repo_id,
          access_level: form.access_level,
          branch_pattern: form.branch_pattern,
          path_pattern: form.path_pattern
        })
      });
    } else {
      res = await fetch('/api/admin/permissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: token() },
        body: JSON.stringify(form)
      });
    }
    if (res.ok) {
      showForm = false;
      await load();
    } else {
      const data = await res.json();
      alert(data.detail || '保存失败');
    }
  }

  async function revoke(id) {
    if (!confirm('确定撤销此权限？')) return;
    await fetch(`/api/admin/permissions/${id}`, { method: 'DELETE', headers: { Authorization: token() } });
    await load();
  }

  function keyLabel(id) {
    const k = keys.find(k => k.id === id);
    return k ? `${k.ak.slice(0, 16)}...` : `Key#${id}`;
  }
  function repoLabel(id) {
    const r = repos.find(r => r.id === id);
    return r ? r.name : `Repo#${id}`;
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">🔒 权限分配</h1>
    <div class="flex items-center gap-2">
      <span class="text-xs text-[var(--c-text-secondary)]">共 {perms.length} 条</span>
      <RefreshBtn onclick={load} />
      <button class={btnPrimaryCls} onclick={openGrant}>+ 授权仓库</button>
    </div>
  </div>

  <!-- 授权/编辑弹窗 -->
  {#if showForm}
    <Modal
      title={editingId ? '编辑权限' : '授权 Key 访问仓库'}
      subtitle="按仓库 + 分支 + 路径正则精确控制访问范围"
      width="max-w-md"
      onClose={() => (showForm = false)}
    >
      <FormField label="Access Key" required>
        <select class={selectCls} bind:value={form.key_id} disabled={editingId}>
          <option value={null}>-- 选择 Key --</option>
          {#each keys.filter(k => k.enabled) as k}
            <option value={k.id}>{k.ak.slice(0, 20)}... {k.description}</option>
          {/each}
        </select>
      </FormField>
      <FormField label="Git 仓库" required>
        <select class={selectCls} bind:value={form.repo_id} disabled={editingId}>
          <option value={null}>-- 选择仓库 --</option>
          {#each repos.filter(r => r.enabled) as r}
            <option value={r.id}>{r.name}</option>
          {/each}
        </select>
      </FormField>
      <FormField label="访问级别">
        <select class={selectCls} bind:value={form.access_level}>
          <option value="read_only">只读 (read_only)</option>
          <option value="read_write">读写 (read_write)</option>
          <option value="admin">管理员 (admin)</option>
        </select>
      </FormField>
      <div class="grid grid-cols-2 gap-3">
        <FormField label="分支正则" hint="留空（.*）允许全部分支">
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.branch_pattern} placeholder=".*" />
        </FormField>
        <FormField label="路径正则" hint="留空（.*）允许全部路径">
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.path_pattern} placeholder=".*" />
        </FormField>
      </div>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showForm = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={save} disabled={!form.key_id || !form.repo_id}>保存</button>
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
            <th>Access Key</th>
            <th>仓库</th>
            <th>级别</th>
            <th>分支正则</th>
            <th>路径正则</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each shownPerms as p}
            <tr>
              <td class="font-mono text-xs text-[var(--c-text-secondary)]">{keyLabel(p.key_id)}</td>
              <td class="font-bold text-[var(--c-text)]">{repoLabel(p.repo_id)}</td>
              <td>
                <span class="badge {p.access_level === 'admin' ? 'badge-error' : p.access_level === 'read_write' ? 'badge-warning' : 'badge-info'} badge-sm">
                  {p.access_level}
                </span>
              </td>
              <td><code class="text-xs bg-[var(--c-page-bg)] px-1 rounded text-[var(--c-text)]">{p.branch_pattern}</code></td>
              <td><code class="text-xs bg-[var(--c-page-bg)] px-1 rounded max-w-32 truncate block text-[var(--c-text)]">{p.path_pattern}</code></td>
              <td class="flex gap-1">
                <button class="btn btn-xs btn-ghost" onclick={() => openEdit(p)}>编辑</button>
                <button class="btn btn-xs btn-ghost text-error" onclick={() => revoke(p.id)}>撤销</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pager {page} total={perms.length} {pageSize} ongo={goPage} />
    {#if perms.length === 0}
      <div class="text-center text-[var(--c-text-secondary)] py-8">暂无权限分配，请先创建 Key 和仓库后授权</div>
    {/if}
  {/if}
</div>
