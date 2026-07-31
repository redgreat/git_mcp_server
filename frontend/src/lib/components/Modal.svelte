<script>
  let { title, subtitle = '', width = 'max-w-md', onClose, children, footer } = $props();
</script>

<div class="modal modal-open">
  <div
    class="modal-box rounded-2xl {width} p-0 overflow-hidden bg-[var(--c-surface)] border border-[var(--c-border)] shadow-2xl"
  >
    <!-- 弹窗头部 -->
    <div class="flex items-start justify-between gap-4 px-6 py-4 border-b border-[var(--c-border)]">
      <div class="min-w-0">
        <h3 class="font-bold text-lg text-[var(--c-text)] leading-snug">{title}</h3>
        {#if subtitle}
          <p class="text-xs text-[var(--c-text-secondary)] mt-0.5">{subtitle}</p>
        {/if}
      </div>
      <button
        class="btn btn-ghost btn-sm btn-circle shrink-0 text-[var(--c-text-secondary)] hover:bg-[var(--c-hover)]"
        onclick={onClose}
        aria-label="关闭"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- 弹窗内容 -->
    <div class="px-6 py-5 max-h-[70vh] overflow-y-auto">
      {@render children()}
    </div>

    <!-- 弹窗底部按钮区 -->
    {#if footer}
      <div class="flex justify-end gap-2 px-6 py-4 border-t border-[var(--c-border)] bg-[var(--c-hover)]/30 rounded-b-2xl">
        {@render footer()}
      </div>
    {/if}
  </div>
  <div class="modal-backdrop" onclick={onClose}></div>
</div>
