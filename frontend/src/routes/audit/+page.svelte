<script>
  import { onMount } from 'svelte';

  let logs = $state([]);
  let loading = $state(true);
  let total = $state(0);
  let page = $state(1);
  let pageSize = $state(20); // 固定每页条数
  let totalPages = $state(1);
  let filter = $state({ access_key: '', operation: '', status: '' });
  let expandedRow = $state(null); // 点击展开查看完整错误

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    loading = true;
    const params = new URLSearchParams();
    if (filter.access_key) params.set('access_key', filter.access_key);
    if (filter.operation) params.set('operation', filter.operation);
    if (filter.status) params.set('status', filter.status);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    try {
      const res = await fetch('/api/admin/audit-logs?' + params.toString(), {
        headers: { Authorization: token() }
      });
      if (res.ok) {
        const data = await res.json();
        logs = data.items || [];
        total = data.total || 0;
        totalPages = Math.max(1, Math.ceil(total / pageSize));
        if (page > totalPages) {
          page = totalPages;
          await load(); // 越界时回到最后一页重新加载
          return;
        }
      }
    } finally {
      loading = false;
      expandedRow = null;
    }
  }

  // 首次加载（只在挂载时触发一次，避免与手动 load 重复）
  onMount(() => { load(); });

  function onFilterChange() {
    page = 1;
    load();
  }

  function changePageSize() {
    page = 1;
    load();
  }

  function goPage(p) {
    if (p < 1 || p > totalPages || p === page) return;
    page = p;
    load();
  }

  function toggleExpand(logId) {
    expandedRow = expandedRow === logId ? null : logId;
  }

  // 折叠页码：1 … 4 5 6 … 12
  let pageList = $derived.by(() => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const set = new Set([1, totalPages]);
    for (let p = page - 1; p <= page + 1; p++) {
      if (p >= 1 && p <= totalPages) set.add(p);
    }
    const arr = [...set].sort((a, b) => a - b);
    const out = [];
    let prev = 0;
    for (const p of arr) {
      if (prev && p - prev > 1) out.push('…');
      out.push(p);
      prev = p;
    }
    return out;
  });
</script>

<div>
  <div class="flex items-center justify-between mb-4">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">📋 审计日志</h1>
    <span class="text-xs text-[var(--c-text-secondary)]">共 {total} 条</span>
  </div>

  <!-- 工具栏 -->
  <div class="flex flex-wrap gap-2 mb-4 items-center">
    <input type="text" class="input input-bordered input-sm w-44" placeholder="Access Key" bind:value={filter.access_key} oninput={onFilterChange} />
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
  </div>

  {#if loading}
    <div class="flex justify-center py-16"><span class="loading loading-spinner loading-lg"></span></div>
  {:else}
    <div class="overflow-x-auto bg-[var(--c-surface)] rounded-xl shadow border border-[var(--c-border)]">
      <table class="table">
        <thead>
          <tr>
            <th class="text-xs">时间</th>
            <th class="text-xs">Access Key</th>
            <th class="text-xs">IP</th>
            <th class="text-xs">仓库</th>
            <th class="text-xs">操作</th>
            <th class="text-xs">目标</th>
            <th class="text-xs">耗时</th>
            <th class="text-xs">状态</th>
          </tr>
        </thead>
        <tbody>
          {#each logs as log}
            {@const hasDetail = (log.status === 'error' || log.status === 'denied') && log.error_message}
            {@const expanded = expandedRow === log.id}
            <tr class="hover:bg-[var(--c-hover)] {hasDetail && expanded ? 'bg-error/10' : ''}">
              <td class="text-xs whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
              <td class="font-mono text-xs">{log.access_key?.slice(0, 12)}...</td>
              <td class="font-mono text-xs">{log.client_ip}</td>
              <td class="text-xs">{log.repo_name || log.repo_id || '-'}</td>
              <td><span class="badge badge-outline badge-xs font-mono">{log.operation}</span></td>
              <td class="max-w-40 truncate text-xs" title={log.target}>{log.target}</td>
              <td class="text-xs">{log.duration_ms}ms</td>
              <td>
                {#if hasDetail}
                  <button
                    class="badge {log.status === 'denied' ? 'badge-warning' : 'badge-error'} badge-xs gap-0.5 cursor-pointer hover:opacity-80"
                    onclick={() => toggleExpand(log.id)}
                    title="点击查看原因"
                  >
                    {log.status} ⚠
                  </button>
                {:else}
                  <span class="badge {log.status === 'success' ? 'badge-success' : 'badge-error'} badge-xs">{log.status}</span>
                {/if}
              </td>
            </tr>
            {#if expanded}
              <tr>
                <td colspan="8" class="p-0">
                  <div class="bg-error/10 border-t border-error/20 px-4 py-2.5">
                    <div class="flex items-start gap-2">
                      <span class="font-bold text-xs shrink-0 {log.status === 'denied' ? 'text-warning' : 'text-error'}">
                        {log.status === 'denied' ? '⛔ 拒绝原因' : '❌ 错误详情'}
                      </span>
                      <span class="text-xs font-mono {log.status === 'denied' ? 'text-warning/90' : 'text-error/90'} break-all whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {log.error_message}
                      </span>
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
      <div class="text-center text-[var(--c-text-secondary)] py-8">暂无审计日志</div>
    {/if}

    <!-- 分页 -->
    {#if totalPages > 1}
      <div class="flex flex-wrap items-center justify-between gap-2 mt-4">
        <div class="text-xs text-[var(--c-text-secondary)]">
          共 <span class="font-bold">{total}</span> 条 · 第 <span class="font-bold">{page}</span> / {totalPages} 页
        </div>
        <div class="join">
          <button class="join-item btn btn-sm" onclick={() => goPage(1)} disabled={page <= 1}>«</button>
          <button class="join-item btn btn-sm" onclick={() => goPage(page - 1)} disabled={page <= 1}>‹</button>
          {#each pageList as p}
            {#if p === '…'}
              <button class="join-item btn btn-sm btn-disabled">…</button>
            {:else}
              <button class="join-item btn btn-sm {p === page ? 'btn-primary' : ''}" onclick={() => goPage(p)}>{p}</button>
            {/if}
          {/each}
          <button class="join-item btn btn-sm" onclick={() => goPage(page + 1)} disabled={page >= totalPages}>›</button>
          <button class="join-item btn btn-sm" onclick={() => goPage(totalPages)} disabled={page >= totalPages}>»</button>
        </div>
        <select class="select select-bordered select-sm" bind:value={pageSize} onchange={changePageSize}>
          <option value={20}>20 条/页</option>
          <option value={50}>50 条/页</option>
          <option value={100}>100 条/页</option>
        </select>
      </div>
    {/if}
  {/if}
</div>
