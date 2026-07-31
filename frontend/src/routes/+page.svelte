<svelte:head>
  <meta http-equiv="refresh" content="0;url=/admin/login" />
</svelte:head>

<script>
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  onMount(() => {
    const token = localStorage.getItem('token');
    if (token) {
      goto('/admin/dashboard');
    } else {
      goto('/admin/login');
    }
  });
</script>

<div class="min-h-screen flex items-center justify-center bg-base-200">
  <span class="loading loading-spinner loading-lg"></span>
</div>
