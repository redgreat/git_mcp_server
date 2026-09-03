<script>
  let logs = $state([]);
  let loading = $state(true);
  let total = $state(0);
  let page = $state(1);
  let pageSize = $state(20);
  let totalPages = $state(1);
  let filter = $state({ access_key: '', operation: '', status: '' });
  let expandedRow = $state(null); // 展开的行ID，用于显示完整错误详情

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    loading = true;
    const params = new URLSearchParams();
    if (filter.access_key) params.set('access_key', filter.access_key);
    if (filter.operation) params.set('operation', filter.operation);
    if (filter.status) params.set('status', filter.status);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    const res = await fetch('/api/admin/audit-logs?' + params.toString(), {
      headers: { Authorization: token() }
    });
    if (res.ok) {
      const data = await res.json();
      logs = data.items || [];
      total = data.total || 0;
      totalPages = Math.max(1, Math.ceil(total / pageSize));
    }
    loading = false;
    expandedRow = null; // 重置展开状态
  }
  $effect(() => { load(); });

  // 过滤器变化时回到第一页
  function onFilterChange() {
    page = 1;
    load();
  }

  function goPage(p) {
    if (p < 1 || p > totalPages) return;
    page = p;
    load();
  }

  function toggleExpand(logId) {
    expandedRow = expandedRow === logId ? null : logId;
  }

  // 简洁显示错误：状态为 error/denied 时，第一行截断展示原因
  function shortError(msg) {
    if (!msg) return '';
    const oneLine = msg.replace(/\s+/g, ' ').trim();
    return oneLine.length > 120 ? oneLine.slice(0, 120) + '…' : oneLine;
  }
</script>

<div>
  <h1 class="text-2xl font-bold mb-6">📋 审计日志</h1>

  <div class="flex gap-2 mb-4 flex-wrap items-center">
    <input type="text" class="input input-bordered input-sm" placeholder="Access Key" bind:value={filter.access_key} oninput={onFilterChange} />
    <select class="select select-bordered select-sm" bind:value={filter.operation} onchange={onFilterChange}>
      <option value="">全部操作</option>
      <option value="list_repos">list_repos</option>
      <option value="list_branches">list_branches</option>
      <option value="list_tags">list_tags</option>
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
    <select class="select select-bordered select-sm" bind:value={filter.status} onchange={onFilterChange}>
      <option value="">全部状态</option>
      <option value="success">成功</option>
      <option value="denied">拒绝</option>
      <option value="error">错误</option>
    </select>
    <span class="text-xs text-gray-500 ml-auto">共 {total} 条</span>
  </div>

  {#if loading}
    <div class="flex justify-center py-16"><span class="loading loading-spinner loading-lg"></span></div>
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
            {@const hasDetail = (log.status === 'error' || log.status === 'denied') && log.error_message}
            <tr class="{hasDetail ? 'bg-error/5 hover:bg-error/10' : ''}">
              <td class="text-xs whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
              <td class="font-mono text-xs">{log.access_key?.slice(0, 12)}...</td>
              <td class="font-mono text-xs">{log.client_ip}</td>
              <td>{log.repo_name || log.repo_id || '-'}</td>
              <td><span class="badge badge-outline badge-sm">{log.operation}</span></td>
              <td class="max-w-40 truncate text-xs" title={log.target}>{log.target}</td>
              <td class="text-xs">{log.duration_ms}ms</td>
              <td>
                <span class="badge {log.status === 'success' ? 'badge-success' : log.status === 'denied' ? 'badge-warning' : 'badge-error'} badge-xs">
                  {log.status}
                </span>
              </td>
            </tr>
            {#if hasDetail}
              <tr class="cursor-pointer" onclick={() => toggleExpand(log.id)}>
                <td colspan="8" class="p-0">
                  <div class="pl-14 pr-3 pb-1 text-xs">
                    <span class="font-bold {log.status === 'denied' ? 'text-warning' : 'text-error'}">
                      {log.status === 'denied' ? '⛔ 拒绝原因' : '❌ 错误原因'}:
                    </span>
                    <span class="font-mono text-error/90 break-all">
                      {expandedRow === log.id ? log.error_message : shortError(log.error_message)}
                    </span>
                    {#if expandedRow !== log.id && shortError(log.error_message).length >= 120}
                      <span class="text-info">（点击查看完整）</span>
                    {/if}
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

    <!-- 分页 -->
    {#if totalPages > 1}
      <div class="flex items-center justify-center gap-2 mt-4">
        <button
          class="btn btn-xs {page <= 1 ? 'btn-disabled' : 'btn-outline'}"
          onclick={() => goPage(1)}
          disabled={page <= 1}
        >« 首页</button>
        <button
          class="btn btn-xs {page <= 1 ? 'btn-disabled' : 'btn-outline'}"
          onclick={() => goPage(page - 1)}
          disabled={page <= 1}
        >‹ 上一页</button>
        <span class="text-xs text-gray-500 mx-2">第 {page} / {totalPages} 页</span>
        <button
          class="btn btn-xs {page >= totalPages ? 'btn-disabled' : 'btn-outline'}"
          onclick={() => goPage(page + 1)}
          disabled={page >= totalPages}
        >下一页 ›</button>
        <button
          class="btn btn-xs {page >= totalPages ? 'btn-disabled' : 'btn-outline'}"
          onclick={() => goPage(totalPages)}
          disabled={page >= totalPages}
        >末页 »</button>
        <select
          class="select select-bordered select-xs ml-2"
          bind:value={pageSize}
          onchange={() => { page = 1; load(); }}
        >
          <option value={20}>20/页</option>
          <option value={50}>50/页</option>
          <option value={100}>100/页</option>
        </select>
      </div>
    {/if}
  {/if}
</div>
