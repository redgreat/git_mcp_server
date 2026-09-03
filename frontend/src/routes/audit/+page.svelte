<script>
  import { onMount, tick } from 'svelte';
  import Modal from '$lib/components/Modal.svelte';

  let logs = $state([]);
  let loading = $state(true);
  let total = $state(0);
  let page = $state(1);
  let pageSize = 10; // 固定 10 行/页（恰好一屏）
  let totalPages = $state(1);
  let filter = $state({ access_key: '', operation: '', status: '' });
  let showErrorLog = $state(null); // 错误详情弹窗

  // 行高自适应：让 10 行恰好填满表格可视区
  let bodyEl = $state(null);
  let rowHpx = $state(64);

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
          await load();
          return;
        }
      }
    } finally {
      loading = false;
      await tick();
      computeRowHeight();
    }
  }

  // 行高 = (可视区高 - 表头高 - 各行分隔线) / 行数，让表格恰好占满
  function computeRowHeight() {
    if (!bodyEl) return;
    const th = bodyEl.querySelector('thead');
    const theadH = th ? th.getBoundingClientRect().height : 36;
    const rowCount = bodyEl.querySelectorAll('tbody tr').length || 10;
    const avail = bodyEl.clientHeight - theadH - rowCount; // 减去每行 1px 分隔线
    rowHpx = Math.min(110, Math.max(42, avail / rowCount));
  }

  // 首次加载
  onMount(() => { load(); });

  // 监听表格区尺寸变化（窗口缩放/侧栏折叠）→ 重算行高
  $effect(() => {
    const el = bodyEl;
    if (!el) return;
    const ro = new ResizeObserver(() => computeRowHeight());
    ro.observe(el);
    return () => ro.disconnect();
  });

  function refresh() { load(); }

  function onFilterChange() {
    page = 1;
    load();
  }

  function goPage(p) {
    if (p < 1 || p > totalPages || p === page) return;
    page = p;
    load();
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

<div class="flex flex-col" style="height: calc(100vh - 6.5rem); min-height: 460px;">
  <!-- 标题行 -->
  <div class="flex items-center justify-between mb-3 shrink-0">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">📋 审计日志</h1>
    <div class="flex items-center gap-3">
      <span class="text-xs text-[var(--c-text-secondary)]">共 {total} 条</span>
      <button class="btn btn-outline btn-sm" onclick={refresh} title="刷新当前页数据">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
    </div>
  </div>

  <!-- 工具栏 -->
  <div class="flex flex-wrap gap-2 mb-3 shrink-0 items-center">
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

  <!-- 表格区：恰好一屏，不滚动 -->
  <div
    bind:this={bodyEl}
    class="flex-1 min-h-0 rounded-xl shadow border border-[var(--c-border)] bg-[var(--c-surface)] overflow-y-auto"
  >
    {#if loading}
      <div class="flex items-center justify-center h-full"><span class="loading loading-spinner loading-lg"></span></div>
    {:else if logs.length === 0}
      <div class="flex items-center justify-center h-full text-[var(--c-text-secondary)]">暂无审计日志</div>
    {:else}
      <table class="table">
        <thead>
          <tr class="border-b border-[var(--c-border)]">
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
            <tr class="main-row align-middle border-b border-[var(--c-border)]/50 hover:bg-[var(--c-hover)]" style="height: {rowHpx}px;">
              <td class="text-sm whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
              <td class="font-mono text-sm">{log.access_key?.slice(0, 12)}...</td>
              <td class="font-mono text-sm">{log.client_ip}</td>
              <td class="text-sm">{log.repo_name || log.repo_id || '-'}</td>
              <td><span class="badge badge-outline badge-sm font-mono">{log.operation}</span></td>
              <td class="max-w-44 truncate text-sm" title={log.target}>{log.target}</td>
              <td class="text-sm">{log.duration_ms}ms</td>
              <td>
                {#if hasDetail}
                  <button
                    class="btn btn-xs {log.status === 'denied' ? 'btn-warning' : 'btn-error'} btn-outline gap-1"
                    onclick={() => (showErrorLog = log)}
                  >
                    {log.status}
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </button>
                {:else}
                  <span class="badge {log.status === 'success' ? 'badge-success' : 'badge-error'} badge-sm">{log.status}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- 分页（固定底部） -->
  {#if !loading && totalPages > 1}
    <div class="flex flex-wrap items-center justify-between gap-2 mt-3 shrink-0">
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
    </div>
  {/if}
</div>

<!-- 错误详情弹窗 -->
{#if showErrorLog}
  <Modal
    title="{showErrorLog.operation} · {showErrorLog.status === 'denied' ? '拒绝' : '失败'}"
    subtitle="{showErrorLog.repo_name || ('repo#' + showErrorLog.repo_id)} · {new Date(showErrorLog.timestamp).toLocaleString()}"
    width="max-w-2xl"
    onClose={() => (showErrorLog = null)}
  >
    <div class="grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm mb-5">
      <div><span class="text-[var(--c-text-secondary)]">Access Key：</span><span class="font-mono">{showErrorLog.access_key}</span></div>
      <div><span class="text-[var(--c-text-secondary)]">客户端 IP：</span><span class="font-mono">{showErrorLog.client_ip}</span></div>
      <div><span class="text-[var(--c-text-secondary)]">目标：</span><span class="font-mono break-all">{showErrorLog.target || '-'}</span></div>
      <div><span class="text-[var(--c-text-secondary)]">耗时：</span>{showErrorLog.duration_ms}ms</div>
    </div>
    <div class="rounded-xl border {showErrorLog.status === 'denied' ? 'border-warning/30 bg-warning/5' : 'border-error/30 bg-error/5'} p-4">
      <div class="text-sm font-bold {showErrorLog.status === 'denied' ? 'text-warning' : 'text-error'} mb-2">
        {showErrorLog.status === 'denied' ? '⛔ 拒绝原因' : '❌ 错误详情'}
      </div>
      <pre class="text-sm font-mono text-[var(--c-text)] whitespace-pre-wrap break-all leading-relaxed">{showErrorLog.error_message}</pre>
    </div>
    {#snippet footer()}
      <button class="btn btn-primary btn-sm" onclick={() => (showErrorLog = null)}>关闭</button>
    {/snippet}
  </Modal>
{/if}
