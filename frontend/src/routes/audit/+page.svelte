<script>
  let logs = $state([]);
  let loading = $state(true);
  let filter = $state({ access_key: '', operation: '', status: '' });
  let expandedRow = $state(null); // 展开的行ID，用于显示错误详情

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
    expandedRow = null; // 重置展开状态
  }
  $effect(() => { load(); });

  function toggleExpand(logId) {
    expandedRow = expandedRow === logId ? null : logId;
  }
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
      <option value="analyze_code">analyze_code</option>
      <option value="review_diff">review_diff</option>
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
            {@const hasError = log.status === 'error' && log.error_message}
            <tr class="{hasError ? 'bg-error/5' : ''}">
              <td class="text-xs whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
              <td class="font-mono text-xs">{log.access_key?.slice(0, 12)}...</td>
              <td class="font-mono text-xs">{log.client_ip}</td>
              <td>{log.repo_name || log.repo_id}</td>
              <td><span class="badge badge-outline badge-sm">{log.operation}</span></td>
              <td class="max-w-40 truncate text-xs" title={log.target}>{log.target}</td>
              <td class="text-xs">{log.duration_ms}ms</td>
              <td>
                <button
                  class="badge {log.status === 'success' ? 'badge-success' : log.status === 'denied' ? 'badge-warning' : 'badge-error'} badge-xs cursor-pointer hover:opacity-80"
                  onclick={() => hasError && toggleExpand(log.id)}
                >
                  {log.status}
                  {if hasError} ⚠{/if}
                </button>
              </td>
            </tr>
            {#if expandedRow === log.id && hasError}
              <tr>
                <td colspan="8" class="p-0">
                  <div class="bg-error/10 border-t border-error/20 p-3">
                    <div class="text-xs text-error font-mono whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                      {log.error_message}
                    </div>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
    {#if logs.length === 0}
      <div class="text-center text-gray-500 py-8">暂无审计日志</div>
    {/if}
  {/if}
</div>
