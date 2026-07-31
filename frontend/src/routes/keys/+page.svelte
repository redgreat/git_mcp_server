<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';

  let keys = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let form = $state({ ak: '', description: '', enabled: true });

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    const res = await fetch('/api/admin/keys', { headers: { Authorization: token() } });
    if (res.ok) keys = await res.json();
    loading = false;
  }

  async function create() {
    const res = await fetch('/api/admin/keys', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify(form)
    });
    if (res.ok) {
      showForm = false;
      await load();
    }
  }

  async function toggle(id, enabled) {
    const k = keys.find(k => k.id === id);
    if (!k) return;
    await fetch(`/api/admin/keys/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify({ description: k.description, enabled })
    });
    await load();
  }

  async function remove(id) {
    if (!confirm('确定删除此 Key？相关权限和审计日志不受影响。')) return;
    await fetch(`/api/admin/keys/${id}`, { method: 'DELETE', headers: { Authorization: token() } });
    await load();
  }

  function copyAk(ak) {
    navigator.clipboard.writeText(ak);
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">🗝️ Access Key 管理</h1>
    <button class={btnPrimaryCls} onclick={() => { form = { ak: '', description: '', enabled: true }; showForm = true; }}>+ 创建 Key</button>
  </div>

  <!-- 创建 Access Key 弹窗 -->
  {#if showForm}
    <Modal
      title="创建 Access Key"
      subtitle="Key 用于 MCP 客户端身份认证，可配合 IP 白名单使用"
      width="max-w-md"
      onClose={() => (showForm = false)}
    >
      <FormField label="自定义 Key" hint="留空则自动生成随机 Key（推荐）">
        <input type="text" class={inputCls + ' font-mono'} bind:value={form.ak} placeholder="留空自动生成" />
      </FormField>
      <FormField label="描述">
        <input type="text" class={inputCls} bind:value={form.description} placeholder="如: 前端团队使用" />
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showForm = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={create}>创建</button>
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
            <th>描述</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each keys as k}
            <tr>
              <td>
                <div class="flex items-center gap-2">
                  <code class="text-xs bg-[var(--c-page-bg)] px-2 py-0.5 rounded text-[var(--c-text)]">{k.ak}</code>
                  <button class="btn btn-ghost btn-xs" onclick={() => copyAk(k.ak)} title="复制">📋</button>
                </div>
              </td>
              <td class="text-[var(--c-text-secondary)]">{k.description || '-'}</td>
              <td>
                <label class="label cursor-pointer gap-1 p-0">
                  <input type="checkbox" class="toggle toggle-sm" checked={k.enabled}
                         onchange={(e) => toggle(k.id, e.target.checked)} />
                  <span class="text-xs text-[var(--c-text-secondary)]">{k.enabled ? '启用' : '禁用'}</span>
                </label>
              </td>
              <td class="text-xs whitespace-nowrap text-[var(--c-text-secondary)]">{new Date(k.created_at).toLocaleString()}</td>
              <td>
                <button class="btn btn-xs btn-ghost text-error" onclick={() => remove(k.id)}>删除</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if keys.length === 0}
      <div class="text-center text-[var(--c-text-secondary)] py-8">暂无 Key，请创建</div>
    {/if}
  {/if}
</div>
