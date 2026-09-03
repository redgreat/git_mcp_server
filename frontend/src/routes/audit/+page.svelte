<script>
  import { tick } from 'svelte';

  let logs = $state([]);
  let loading = $state(true);
  let total = $state(0);
  let page = $state(1);
  let totalPages = $state(1);
  let pageSize = $state(15); // 自适应：按屏幕高度算出一屏能放几行
  let filter = $state({ access_key: '', operation: '', status: '' });
  let expandedRow = $state(null); // 点击展开查看完整错误

  let areaEl = $state(null); // 表格可视区域（用于测量）
  let rowH = $state(0);      // 实测单行高度(px)
  let areaH = $state(0);     // 表格可视区域高度(px)
  let headerH = $state(37);  // 表头高度(px)

  const token = () => localStorage.getItem('token') || '';

  // 每页条数 = 可视高度能放下的行数（去掉表头与留白）
  function computePageSize() {
    if (!rowH || !areaH) return;
    const fit = Math.max(5, Math.min(60, Math.floor((areaH - headerH - 8) / rowH)));
    if (fit !== pageSize) {
      pageSize = fit;
      page = 1; // pageSize/page 变化会触发 $effect 重新加载
    }
  }

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
        if (page > totalPages) { page = totalPages; return; }
      }
    } finally {
      loading = false;
      expandedRow = null;
      await tick();        // 等 DOM 渲染完
      measureLayout();     // 实测行高 → 校准每页条数
    }
  }

  // 实测表头高度 + 首行高度
  function measureLayout() {
    if (!areaEl) return;
    const th = areaEl.querySelector('thead');
    const tr = areaEl.querySelector('tbody tr.main-row');
    headerH = th ? th.getBoundingClientRect().height : 37;
    rowH = tr ? tr.getBoundingClientRect().height : 44;
    computePageSize();
  }

  function onFilterChange() {
    page = 1;
  }

  function goPage(p) {
    if (p < 1 || p > totalPages || p === page) return;
    page = p;
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

  // 过滤器 / 页码 / 每页条数 任一变化 → 重新加载
  $effect(() => {
    void filter.access_key; void filter.operation; void filter.status;
    void page; void pageSize;
    load();
  });

  // 监听表格可视区域尺寸变化（窗口缩放、侧栏折叠等）→ 重算每页条数
  $effect(() => {
    const el = areaEl;
    if (!el) return;
    const measure = () => {
      areaH = el.clientHeight;
      computePageSize();
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  });
</script>

<div class="flex flex-col" style="height: calc(100vh - 7rem); min-height: 460px;">
  <!-- 标题行 -->
  <div class="flex items-center justify-between mb-3 shrink-0">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">📋 审计日志</h1>
    <span class="text-xs text-[var(--c-text-secondary)]">共 {total} 条 · 每页 {pageSize} 条</span>
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

  <!-- 表格：占满剩余高度（一屏），页内不滚动 -->
  <div
    bind:this={areaEl}
    class="flex-1 min-h-0 rounded-xl shadow border border-[var(--c-border)] bg-[var(--c-surface)] overflow-y-auto"
  >
    {#if loading}
      <div class="flex items-center justify-center py-20"><span class="loading loading-spinner loading-lg"></span></div>
    {:else if logs.length === 0}
      <div class="flex items-center justify-center py-20 text-[var(--c-text-secondary)]">暂无审计日志</div>
    {:else}
      <table class="table">
        <thead class="sticky top-0 bg-[var(--c-surface)] z-10">
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
            {@const expanded = expandedRow === log.id}
            <tr class="main-row h-11 hover:bg-[var(--c-hover)] {hasDetail && expanded ? 'bg-error/10' : ''}">
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
