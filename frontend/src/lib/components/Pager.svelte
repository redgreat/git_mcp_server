<script>
  let { page, total, pageSize = 15, ongo } = $props();

  let totalPages = $derived(Math.max(1, Math.ceil(total / pageSize)));
  let current = $derived(Math.min(page, totalPages));

  // 折叠页码：1 … 4 5 6 … 12
  let pageList = $derived.by(() => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const set = new Set([1, totalPages]);
    for (let p = current - 1; p <= current + 1; p++) {
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

{#if total > pageSize}
  <div class="flex flex-wrap items-center justify-between gap-2 mt-4">
    <div class="text-xs text-[var(--c-text-secondary)]">
      共 <span class="font-bold">{total}</span> 条 · 第 <span class="font-bold">{current}</span> / {totalPages} 页
    </div>
    <div class="join">
      <button class="join-item btn btn-sm" onclick={() => ongo(1)} disabled={current <= 1}>«</button>
      <button class="join-item btn btn-sm" onclick={() => ongo(current - 1)} disabled={current <= 1}>‹</button>
      {#each pageList as p}
        {#if p === '…'}
          <button class="join-item btn btn-sm btn-disabled">…</button>
        {:else}
          <button class="join-item btn btn-sm {p === current ? 'btn-primary' : ''}" onclick={() => ongo(p)}>{p}</button>
        {/if}
      {/each}
      <button class="join-item btn btn-sm" onclick={() => ongo(current + 1)} disabled={current >= totalPages}>›</button>
      <button class="join-item btn btn-sm" onclick={() => ongo(totalPages)} disabled={current >= totalPages}>»</button>
    </div>
  </div>
{/if}
