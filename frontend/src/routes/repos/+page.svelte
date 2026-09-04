<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';
  import Pager from '$lib/components/Pager.svelte';
  import RefreshBtn from '$lib/components/RefreshBtn.svelte';

  let repos = $state([]);
  let loading = $state(true);
  let showForm = $state(false);
  let editingId = $state(null);
  let form = $state({ name: '', url: '', main_branch: 'main', credential_id: null, enabled: true, allow_write: false, allow_push: false, description: '' });
  let credentials = $state([]);
  // 拉取任务状态：{ [repoId]: { status, message, error } }
  let fetchTasks = $state({});
  let toast = $state(null); // { type: 'success'|'error', message: string }
  let toastTimer = null;
  // 轮询定时器
  let pollTimers = {};

  const token = () => localStorage.getItem('token') || '';

  // 客户端分页
  let page = $state(1);
  let pageSize = 10;
  let curPage = $derived(Math.min(page, Math.max(1, Math.ceil(repos.length / pageSize))));
  let shownRepos = $derived(repos.slice((curPage - 1) * pageSize, curPage * pageSize));
  function goPage(p) {
    const tp = Math.max(1, Math.ceil(repos.length / pageSize));
    if (p >= 1 && p <= tp) page = p;
  }

  function showToast(type, message) {
    toast = { type, message };
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast = null; }, 5000);
  }

  async function fetchRepo(r) {
    const task = fetchTasks[r.id];
    if (task && task.status === 'running') return; // 已在拉取中

    console.log(`[拉取] 提交拉取任务: ${r.name} (ID: ${r.id})`);
    try {
      const res = await fetch(`/api/admin/repos/${r.id}/fetch`, {
        method: 'POST', headers: { Authorization: token() }
      });
      // 先读文本，再尝试解析 JSON，避免非 JSON 响应（如代理 504 HTML）导致解析报错
      const text = await res.text();
      let data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (parseErr) {
        console.error(`[拉取] 响应不是 JSON (HTTP ${res.status}):`, text.slice(0, 500));
        throw new Error(`服务器返回异常 (HTTP ${res.status})，请检查后端日志。${text ? '响应片段: ' + text.slice(0, 120) : ''}`);
      }
      if (!res.ok) throw new Error(data.detail || '提交失败');
      console.log(`[拉取] 任务已提交: task_id=${data.task_id}`);

      // 立即更新为运行中状态
      fetchTasks[r.id] = { status: 'running', message: '拉取中...', error: null };
      fetchTasks = { ...fetchTasks }; // 触发响应式更新

      // 开始轮询
      startPolling(r.id);
    } catch (e) {
      console.error(`[拉取] 提交失败:`, e);
      showToast('error', `❌ ${r.name}：${e.message}`);
    }
  }

  function startPolling(repoId) {
    // 清除已有的轮询
    if (pollTimers[repoId]) clearInterval(pollTimers[repoId]);

    pollTimers[repoId] = setInterval(async () => {
      try {
        const res = await fetch(`/api/admin/repos/${repoId}/fetch/status`, {
          headers: { Authorization: token() }
        });
        if (!res.ok) {
          // 状态接口不可用（如服务重启/旧版本后端）：停止轮询避免死循环
          stopPolling(repoId);
          delete fetchTasks[repoId];
          fetchTasks = { ...fetchTasks };
          await load();
          return;
        }
        const text = await res.text();
        let status = {};
        try {
          status = text ? JSON.parse(text) : {};
        } catch (e) {
          stopPolling(repoId);
          return;
        }

        fetchTasks[repoId] = status;
        fetchTasks = { ...fetchTasks };

        // 完成 / 出错 / 任务丢失（服务重启后 idle）→ 停止轮询并刷新
        if (status.status === 'done' || status.status === 'error') {
          stopPolling(repoId);
          if (status.status === 'done') {
            showToast('success', `✅ ${status.repo_name}：${status.message}`);
          } else {
            showToast('error', `❌ ${status.repo_name}：${status.error || status.message}`);
          }
          await load(); // 刷新 last_fetched_at
        } else if (status.status === 'idle') {
          stopPolling(repoId);
          delete fetchTasks[repoId];
          fetchTasks = { ...fetchTasks };
          await load();
        }
      } catch (e) {
        // 网络异常：下次轮询继续
      }
    }, 2000); // 每 2 秒查询一次
  }

  function stopPolling(repoId) {
    if (pollTimers[repoId]) {
      clearInterval(pollTimers[repoId]);
      delete pollTimers[repoId];
    }
  }

  function getTaskStatus(r) {
    return fetchTasks[r.id] || null;
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
    try {
      const method = editingId ? 'PUT' : 'POST';
      const url = editingId ? `/api/admin/repos/${editingId}` : '/api/admin/repos';
      const res = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json', Authorization: token() },
        body: JSON.stringify(form)
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* 非 JSON 响应 */ }
      if (!res.ok) throw new Error(data.detail || `保存失败 (HTTP ${res.status})`);
      showToast('success', editingId ? `✅ 仓库「${form.name}」已更新` : `✅ 仓库「${form.name}」已创建`);
      showForm = false;
      await load();
    } catch (e) {
      console.error('[保存仓库] 失败:', e);
      showToast('error', `❌ ${form.name}：${e.message}`);
    }
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
    <div class="flex items-center gap-2">
      <span class="text-xs text-[var(--c-text-secondary)]">共 {repos.length} 个</span>
      <RefreshBtn onclick={load} />
      <button class={btnPrimaryCls} onclick={openCreate}>+ 添加仓库</button>
    </div>
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
          {#each shownRepos as r}
            {@const task = getTaskStatus(r)}
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
                {#if task && task.status === 'running'}
                  <span class="text-info">⏳ 拉取中...</span>
                {:else}
                  {r.last_fetched_at ? new Date(r.last_fetched_at).toLocaleString() : '从未拉取'}
                {/if}
              </td>
              <td>
                <div class="flex gap-1">
                  <button
                    class="btn btn-xs {task?.status === 'running' ? 'btn-ghost' : 'btn-outline'}"
                    onclick={() => fetchRepo(r)}
                    title="拉取最新代码"
                  >
                    {#if task?.status === 'running'}
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
    <Pager {page} total={repos.length} {pageSize} ongo={goPage} />
    {#if repos.length === 0}
      <div class="text-center text-[var(--c-text-secondary)] py-8">暂无仓库，点击右上角添加</div>
    {/if}
  {/if}
</div>
