<script>
  let dashboard = $state(null);
  let loading = $state(true);

  async function load() {
    try {
      const token = localStorage.getItem('token') || '';
      const res = await fetch('/api/admin/dashboard', {
        headers: { Authorization: token }
      });
      if (res.ok) dashboard = await res.json();
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });
</script>

<div>
  <h1 class="text-2xl font-bold mb-6">📊 仪表盘</h1>

  {#if loading}
    <div class="flex justify-center"><span class="loading loading-spinner loading-lg"></span></div>
  {:else if dashboard}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div class="stat bg-base-100 rounded-box shadow p-4">
        <div class="stat-title">Access Key 总数</div>
        <div class="stat-value text-primary">{dashboard.total_keys}</div>
      </div>
      <div class="stat bg-base-100 rounded-box shadow p-4">
        <div class="stat-title">Git 仓库总数</div>
        <div class="stat-value text-secondary">{dashboard.total_repos}</div>
      </div>
      <div class="stat bg-base-100 rounded-box shadow p-4">
        <div class="stat-title">用户总数</div>
        <div class="stat-value text-accent">{dashboard.total_users}</div>
      </div>
    </div>

    <div class="card bg-base-100 shadow">
      <div class="card-body">
        <h2 class="card-title">最近操作</h2>
        <div class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>时间</th>
                <th>Access Key</th>
                <th>操作</th>
                <th>目标</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {#each dashboard.recent_operations || [] as op}
                <tr>
                  <td class="text-xs">{new Date(op.timestamp).toLocaleString()}</td>
                  <td class="font-mono text-xs">{op.access_key?.slice(0, 16)}...</td>
                  <td>{op.operation}</td>
                  <td class="max-w-40 truncate">{op.target}</td>
                  <td>
                    <span class="badge {op.status === 'success' ? 'badge-success' : 'badge-error'} badge-xs">
                      {op.status}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {:else}
    <div class="alert alert-warning">加载失败</div>
  {/if}
</div>
