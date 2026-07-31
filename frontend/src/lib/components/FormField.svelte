<script>
  let { label, required = false, hint = '', children } = $props();
</script>

<label class="block mb-4 last:mb-0">
  <span class="mb-1.5 block text-sm font-medium text-[var(--c-text)]">
    {label}
    {#if required}
      <span class="text-error ml-0.5">*</span>
    {/if}
  </span>
  {@render children()}
  {#if hint}
    <span class="mt-1 block text-xs text-[var(--c-text-secondary)]">{hint}</span>
  {/if}
</label>
