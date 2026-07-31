<script>
  let logs = $state([]);
  let loading = $state(true);
  let filter = $state({ access_key: '', operation: '', status: '' });

  async function load() {
    const token = localStorage.getItem('token') || '';
    const params = new URLSearchParams();
    if (filter.access_key) params.set('access_key', filter.access_key);
    if (filter.operation) params.set('operation', filter.operation);
    if (filter.status) params.set('status', filter.status);
    params.set('limit', '100');
    const res = await fetch('/api/admin/audit-logs?' + params.toString(), {
      headers: { Authorization: token }
    });
    if (res.ok) logs = await res.json();
    loading = false;
  }
  $effect(() => { load(); });
</script>

<div>
  <h1 class="text-2xl font-bold mb-6">📋 审计日志</h1>

  <div class="flex gap-2 mb-4 flex-wrap">
    <input type="text" class="input input-bordered input-sm" placeholder="Access Key" bind:value={filter.access_key} oninput={() => load()} />
    <select class="select select-bordered select-sm" bind:value={filter.operation} onchange={() => load()}>
      <option value="">全部操作</option>
      <option value="read_file">read_file</option>
      <option value="list_tree">list_tree</option>
      <option value="git_log">git_log</option>
      <option value="git_show">git_show</option>
      <option value="git_diff">git_diff</option>
      <option value="git_blame">git_blame</option>
      <option value="git_grep">git_grep</option>
    </select>
    <select class="select select-bordered select-sm" bind:value={filter.status} onchange={() => load()}>
      <option value="">全部状态</option>
      <option value="success">成功</option>
      <option value="denied">拒绝</option>
      <option value="error">错误</option>
    </select>
  </div>

  {#if loading}
    <span class="loading loading-spinner"></span>
  {:else}
    <div class="overflow-x-auto bg-base-100 rounded-box shadow">
      <table class="table table-sm">
        <thead>
          <tr>
            <th>时间</th>
            <th>Access Key</th>
            <th>IP</th>
            <th>仓库</th>
            <th>操作</th>
            <th>目标</th>
            <th>耗时</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {#each logs as log}
            <tr>
              <td class="text-xs whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
              <td class="font-mono text-xs">{log.access_key?.slice(0, 12)}...</td>
              <td class="font-mono text-xs">{log.client_ip}</td>
              <td>{log.repo_name || log.repo_id}</td>
              <td>{log.operation}</td>
              <td class="max-w-40 truncate text-xs">{log.target}</td>
              <td class="text-xs">{log.duration_ms}ms</td>
              <td>
                <span class="badge {log.status === 'success' ? 'badge-success' : log.status === 'denied' ? 'badge-warning' : 'badge-error'} badge-xs">
                  {log.status}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if logs.length === 0}
      <div class="text-center text-gray-500 py-8">暂无审计日志</div>
    {/if}
  {/if}
</div>
