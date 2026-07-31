<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, textareaCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';

  let items = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let form = $state({ name: '', auth_type: 'https', username: '', password: '', ssh_key: '', description: '' });
  let editingId = $state(null);

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    const res = await fetch('/api/admin/credentials', { headers: { Authorization: token() } });
    if (res.ok) items = await res.json();
    loading = false;
  }

  function openCreate() {
    editingId = null;
    form = { name: '', auth_type: 'https', username: '', password: '', ssh_key: '', description: '' };
    showForm = true;
  }

  async function save() {
    const method = editingId ? 'PUT' : 'POST';
    const url = editingId ? `/api/admin/credentials/${editingId}` : '/api/admin/credentials';
    const body = { ...form, ssh_key: form.auth_type === 'ssh' ? form.ssh_key : '' };
    await fetch(url, { method, headers: { 'Content-Type': 'application/json', Authorization: token() }, body: JSON.stringify(body) });
    showForm = false;
    await load();
  }

  async function remove(id) {
    if (!confirm('确定删除此凭据？关联的仓库将无法认证。')) return;
    await fetch(`/api/admin/credentials/${id}`, { method: 'DELETE', headers: { Authorization: token() } });
    await load();
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">🔑 凭据管理</h1>
    <button class={btnPrimaryCls} onclick={openCreate}>+ 添加凭据</button>
  </div>

  <!-- 添加凭据弹窗 -->
  {#if showForm}
    <Modal
      title={editingId ? '编辑凭据' : '添加 Git 凭据'}
      subtitle="凭据将加密存储，用于仓库克隆与推送认证"
      width="max-w-lg"
      onClose={() => (showForm = false)}
    >
      <FormField label="名称" required hint="如: github-pat、gitlab-admin">
        <input type="text" class={inputCls} bind:value={form.name} placeholder="如: github-pat" />
      </FormField>
      <FormField label="认证方式">
        <select class={selectCls} bind:value={form.auth_type}>
          <option value="https">HTTPS（用户名 + 密码/Token）</option>
          <option value="ssh">SSH（私钥）</option>
        </select>
      </FormField>
      {#if form.auth_type === 'https'}
        <FormField label="用户名">
          <input type="text" class={inputCls} bind:value={form.username} placeholder="GitLab / GitHub 用户名" />
        </FormField>
        <FormField label="密码 / Personal Access Token" hint="编辑时留空则不修改已保存的密码">
          <input type="password" class={inputCls + ' font-mono'} bind:value={form.password} placeholder="密码或 Token" autocomplete="new-password" />
        </FormField>
      {:else}
        <FormField label="SSH 私钥" hint="粘贴 PEM 格式私钥内容（-----BEGIN ... PRIVATE KEY-----）">
          <textarea class={textareaCls + ' h-28 text-xs'} bind:value={form.ssh_key} placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"></textarea>
        </FormField>
      {/if}
      <FormField label="描述">
        <input type="text" class={inputCls} bind:value={form.description} placeholder="用途说明（可选）" />
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showForm = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={save} disabled={!form.name}>保存</button>
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
            <th>类型</th>
            <th>用户名</th>
            <th>密码/Token</th>
            <th>SSH Key</th>
            <th>描述</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each items as c}
            <tr>
              <td class="font-bold text-[var(--c-text)]">{c.name}</td>
              <td><span class="badge badge-outline badge-sm">{c.auth_type}</span></td>
              <td><span class="badge {c.has_username ? 'badge-success' : 'badge-ghost'} badge-xs">{c.has_username ? '已设置' : '无'}</span></td>
              <td><span class="badge {c.has_password ? 'badge-success' : 'badge-ghost'} badge-xs">{c.has_password ? '已设置' : '无'}</span></td>
              <td><span class="badge {c.has_ssh_key ? 'badge-success' : 'badge-ghost'} badge-xs">{c.has_ssh_key ? '已设置' : '无'}</span></td>
              <td class="text-xs text-[var(--c-text-secondary)]">{c.description || '-'}</td>
              <td>
                <button class="btn btn-xs btn-ghost text-error" onclick={() => remove(c.id)}>删除</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="text-sm text-[var(--c-text-secondary)] mt-2 p-2">
      ⚠️ 凭据已加密存储，编辑需重新输入密码/Token
    </div>
  {/if}
</div>
