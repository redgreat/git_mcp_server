<script>
  import Modal from '$lib/components/Modal.svelte';
  import FormField from '$lib/components/FormField.svelte';
  import { inputCls, selectCls, btnPrimaryCls, btnGhostCls } from '$lib/ui.js';
  import {
    LLM_PROVIDERS, PROVIDER_OPTIONS, CUSTOM_PROVIDER, CUSTOM_MODEL_FLAG,
    providerById, providerLabel
  } from '$lib/llm-providers.js';

  let configs = $state([]);
  let logs = $state([]);
  let loading = $state(true);
  let showCreate = $state(false);
  let showEdit = $state(false);
  let editTarget = $state(null);
  let formError = $state('');

  // 新增/编辑共用表单
  // provider: 内置 id 或 '__custom__'（自定义）；custom_name: 自定义提供商名称
  // model_name: 下拉选中的模型（含 CUSTOM_MODEL_FLAG）；custom_model: 手动输入的模型名
  let form = $state({ provider: '', custom_name: '', base_url: '', api_key: '', model_name: '', custom_model: '' });

  const isCustomProvider = $derived(form.provider === CUSTOM_PROVIDER.id);
  // 编辑时若现有配置的提供商不在内置目录（openai/claude/自建）→ 按自定义模式处理
  const isUnknownProvider = $derived(!!form.provider && !providerById(form.provider) && !isCustomProvider);

  // 模型下拉选项：内置最新模型 + 当前已保存的历史模型 + 「自定义…」入口
  const modelOptions = $derived.by(() => {
    if (isCustomProvider) return [];
    const p = providerById(form.provider);
    const builtin = p ? [...p.models] : [];
    const saved = form.model_name && form.model_name !== CUSTOM_MODEL_FLAG && !builtin.includes(form.model_name)
      ? [form.model_name]
      : [];
    return [...builtin, ...saved];
  });

  // 正在手动输入自定义模型
  const showCustomModelInput = $derived(isCustomProvider || form.model_name === CUSTOM_MODEL_FLAG);

  const token = () => localStorage.getItem('token') || '';

  async function load() {
    const [cRes, lRes] = await Promise.all([
      fetch('/api/admin/llm-configs', { headers: { Authorization: token() } }),
      fetch('/api/admin/llm-logs?limit=50', { headers: { Authorization: token() } })
    ]);
    if (cRes.ok) configs = await cRes.json();
    if (lRes.ok) logs = await lRes.json();
    loading = false;
  }

  async function activate(id) {
    await fetch(`/api/admin/llm-configs/${id}/activate`, { method: 'POST', headers: { Authorization: token() } });
    await load();
  }

  // ===== 新增 =====
  function openCreate() {
    form = { provider: '', custom_name: '', base_url: '', api_key: '', model_name: '', custom_model: '' };
    formError = '';
    showCreate = true;
  }

  function onProviderChange() {
    if (form.provider === CUSTOM_PROVIDER.id) {
      form.base_url = CUSTOM_PROVIDER.base_url;
      form.model_name = '';
      form.custom_model = '';
    } else {
      const p = providerById(form.provider);
      if (p) {
        form.base_url = p.base_url;
        form.model_name = p.models[0];
      }
      form.custom_model = '';
    }
  }

  function resolveProvider() {
    return isCustomProvider ? form.custom_name.trim() : form.provider;
  }

  function resolveModel() {
    if (form.model_name === CUSTOM_MODEL_FLAG || isCustomProvider) {
      return form.custom_model.trim();
    }
    return form.model_name;
  }

  function validate(provider, model) {
    if (!provider) return '请选择模型提供商';
    if (isCustomProvider && !form.custom_name.trim()) return '请填写提供商名称（用于标识，如 my-openai）';
    if (!form.base_url.trim()) return '请填写 API Base URL';
    if (!model) return '请填写或选择模型';
    return '';
  }

  async function create() {
    formError = '';
    const provider = resolveProvider();
    const model = resolveModel();
    const err = validate(provider, model);
    if (err) { formError = err; return; }
    const res = await fetch('/api/admin/llm-configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify({ provider, base_url: form.base_url.trim(), api_key: form.api_key, model_name: model })
    });
    const data = await res.json();
    if (!res.ok) { formError = data.detail || '创建失败'; return; }
    showCreate = false;
    await load();
  }

  // ===== 编辑 =====
  function openEdit(c) {
    editTarget = c;
    const p = providerById(c.provider);
    if (p) {
      // 内置提供商：正常模式，模型下拉（含自定义…）
      form = {
        provider: c.provider, custom_name: '',
        base_url: c.base_url || p.base_url, api_key: '',
        model_name: c.model_name, custom_model: ''
      };
    } else {
      // 自定义 / 未知提供商（openai、claude、自建）：按自定义模式编辑
      form = {
        provider: CUSTOM_PROVIDER.id, custom_name: c.provider,
        base_url: c.base_url || CUSTOM_PROVIDER.base_url, api_key: '',
        model_name: CUSTOM_MODEL_FLAG, custom_model: c.model_name
      };
    }
    formError = '';
    showEdit = true;
  }

  async function saveEdit() {
    if (!editTarget) return;
    formError = '';
    const provider = resolveProvider();
    const model = resolveModel();
    const err = validate(provider, model);
    if (err) { formError = err; return; }
    const body = { provider, base_url: form.base_url.trim(), model_name: model };
    if (form.api_key) body.api_key = form.api_key;
    const res = await fetch(`/api/admin/llm-configs/${editTarget.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: token() },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) { formError = data.detail || '保存失败'; return; }
    showEdit = false;
    await load();
  }

  // ===== 删除 =====
  async function remove(c) {
    if (!confirm(`确定删除「${providerLabel(c.provider)}」配置？`)) return;
    const res = await fetch(`/api/admin/llm-configs/${c.id}`, { method: 'DELETE', headers: { Authorization: token() } });
    if (!res.ok) {
      const data = await res.json();
      alert(data.detail || '删除失败');
    }
    await load();
  }

  $effect(() => { load(); });
</script>

<div>
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold text-[var(--c-text)]">🤖 大模型配置</h1>
    <button class={btnPrimaryCls} onclick={openCreate}>+ 新增配置</button>
  </div>

  <!-- 新增配置弹窗 -->
  {#if showCreate}
    <Modal
      title="新增模型配置"
      subtitle="选择内置提供商自动填充，或使用自定义（OpenAI 兼容接口）"
      width="max-w-md"
      onClose={() => (showCreate = false)}
    >
      {#if formError}
        <div class="alert alert-error rounded-xl py-2.5 text-sm mb-4 shadow-sm">{formError}</div>
      {/if}
      <FormField label="模型提供商" required>
        <select class={selectCls} bind:value={form.provider} onchange={onProviderChange}>
          <option value="">-- 选择提供商 --</option>
          {#each PROVIDER_OPTIONS as p}
            <option value={p.id}>{p.name}（{p.desc}）</option>
          {/each}
        </select>
      </FormField>

      {#if isCustomProvider}
        <FormField label="提供商名称" required hint="用于在列表中标识，如 my-openai / ollama / azure-gpt">
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.custom_name} placeholder="如: my-openai" />
        </FormField>
      {/if}

      <FormField label="API Base URL" required hint={isCustomProvider ? 'OpenAI 规范兼容地址，可修改' : '内置固定，随提供商自动填充'}>
        <input
          type="text"
          class={inputCls + ' font-mono text-sm' + (isCustomProvider ? '' : ' bg-[var(--c-hover)]/40')}
          bind:value={form.base_url}
          readonly={!isCustomProvider}
          placeholder="https://api.openai.com/v1"
        />
      </FormField>

      {#if showCustomModelInput}
        <FormField label="模型名称" required hint="手动输入最新模型名，如 gpt-5.x / ollama 本地模型">
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.custom_model} placeholder="如: gpt-4.1-mini" />
        </FormField>
      {:else}
        <FormField label="模型" required>
          <select class={selectCls} bind:value={form.model_name} disabled={!form.provider}>
            <option value="">-- 选择模型 --</option>
            {#each modelOptions as m}
              <option value={m}>{m}</option>
            {/each}
            <option value={CUSTOM_MODEL_FLAG}>✏️ 自定义…（手动输入）</option>
          </select>
        </FormField>
      {/if}

      <FormField label="API Key" required hint="用于调用该提供商的接口，加密存储">
        <input type="password" class={inputCls + ' font-mono'} bind:value={form.api_key} placeholder="sk-..." autocomplete="new-password" />
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showCreate = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={create} disabled={!form.api_key}>创建</button>
      {/snippet}
    </Modal>
  {/if}

  <!-- 编辑配置弹窗 -->
  {#if showEdit}
    <Modal
      title={`编辑 ${providerLabel(editTarget?.provider)}`}
      subtitle="修改模型、Base URL 或 API Key"
      width="max-w-md"
      onClose={() => (showEdit = false)}
    >
      {#if formError}
        <div class="alert alert-error rounded-xl py-2.5 text-sm mb-4 shadow-sm">{formError}</div>
      {/if}
      <FormField label="模型提供商" required>
        <select class={selectCls} bind:value={form.provider} onchange={onProviderChange}>
          {#each PROVIDER_OPTIONS as p}
            <option value={p.id}>{p.name}（{p.desc}）</option>
          {/each}
        </select>
      </FormField>

      {#if isCustomProvider}
        <FormField label="提供商名称" required hint="用于在列表中标识">
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.custom_name} placeholder="如: my-openai" />
        </FormField>
      {/if}

      <FormField label="API Base URL" required hint={isCustomProvider ? 'OpenAI 规范兼容地址，可修改' : '内置固定，随提供商自动填充'}>
        <input
          type="text"
          class={inputCls + ' font-mono text-sm' + (isCustomProvider ? '' : ' bg-[var(--c-hover)]/40')}
          bind:value={form.base_url}
          readonly={!isCustomProvider}
          placeholder="https://api.openai.com/v1"
        />
      </FormField>

      {#if showCustomModelInput}
        <FormField label="模型名称" required>
          <input type="text" class={inputCls + ' font-mono text-sm'} bind:value={form.custom_model} placeholder="如: gpt-4.1-mini" />
        </FormField>
      {:else}
        <FormField label="模型" required>
          <select class={selectCls} bind:value={form.model_name} disabled={!form.provider}>
            {#each modelOptions as m}
              <option value={m}>{m}</option>
            {/each}
            <option value={CUSTOM_MODEL_FLAG}>✏️ 自定义…（手动输入）</option>
          </select>
        </FormField>
      {/if}

      <FormField label="API Key" hint="留空则保持原 Key 不变">
        <input type="password" class={inputCls + ' font-mono'} bind:value={form.api_key} placeholder="sk-...（留空不修改）" autocomplete="new-password" />
      </FormField>
      {#snippet footer()}
        <button class={btnGhostCls} onclick={() => (showEdit = false)}>取消</button>
        <button class={btnPrimaryCls} onclick={saveEdit}>保存</button>
      {/snippet}
    </Modal>
  {/if}

  {#if loading}
    <div class="flex justify-center py-16"><span class="loading loading-spinner loading-lg"></span></div>
  {:else}
    <!-- LLM 配置表 -->
    <div class="bg-[var(--c-surface)] rounded-xl shadow border border-[var(--c-border)] mb-6">
      <div class="px-6 py-4 border-b border-[var(--c-border)]">
        <h2 class="font-bold text-[var(--c-text)]">提供商配置</h2>
        <p class="text-xs text-[var(--c-text-secondary)] mt-0.5">已内置 DeepSeek、通义千问、Kimi、智谱 GLM、豆包、文心一言、腾讯混元、MiniMax 最新模型；内置提供商模型可选「自定义…」，也支持添加任意 OpenAI 兼容接口的自定义提供商</p>
      </div>
      <div class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>提供商</th>
              <th>模型</th>
              <th>Base URL</th>
              <th>API Key</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {#each configs as c}
              {@const p = providerById(c.provider)}
              <tr>
                <td>
                  <div class="flex flex-col">
                    <span class="font-bold text-[var(--c-text)]">{p ? p.name : c.provider}</span>
                    <span class="text-xs text-[var(--c-text-secondary)]">{p ? p.desc : '自定义提供商'}</span>
                  </div>
                </td>
                <td class="font-mono text-xs text-[var(--c-text)]">{c.model_name}</td>
                <td class="font-mono text-xs max-w-48 truncate text-[var(--c-text-secondary)]" title={c.base_url}>{c.base_url || '-'}</td>
                <td><span class="badge {c.has_api_key ? 'badge-success' : 'badge-warning'} badge-xs">{c.has_api_key ? '已配置' : '未配置'}</span></td>
                <td><span class="badge {c.is_active ? 'badge-primary' : 'badge-ghost'} badge-xs">{c.is_active ? '激活' : '休眠'}</span></td>
                <td>
                  <div class="flex gap-1">
                    <button class="btn btn-xs btn-ghost" onclick={() => openEdit(c)}>编辑</button>
                    {#if !c.is_active}
                      <button class="btn btn-xs btn-primary" onclick={() => activate(c.id)}>激活</button>
                    {:else}
                      <span class="text-xs text-success font-bold self-center">当前使用</span>
                    {/if}
                    <button class="btn btn-xs btn-ghost text-error" onclick={() => remove(c)}>删除</button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if configs.length === 0}
        <div class="text-center text-[var(--c-text-secondary)] py-8">暂无配置，点击右上角新增</div>
      {/if}
    </div>

    <!-- Token 消耗日志 -->
    <div class="bg-[var(--c-surface)] rounded-xl shadow border border-[var(--c-border)]">
      <div class="px-6 py-4 border-b border-[var(--c-border)]">
        <h2 class="font-bold text-[var(--c-text)]">最近调用日志</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="table table-sm">
          <thead>
            <tr><th>时间</th><th>Key</th><th>工具</th><th>模型</th><th>输入Token</th><th>输出Token</th><th>耗时</th><th>状态</th></tr>
          </thead>
          <tbody>
            {#each logs as log}
              <tr>
                <td class="text-xs whitespace-nowrap text-[var(--c-text-secondary)]">{new Date(log.timestamp).toLocaleString()}</td>
                <td class="font-mono text-xs text-[var(--c-text-secondary)]">{log.access_key?.slice(0, 12) || '-'}...</td>
                <td class="text-[var(--c-text)]">{log.tool_name}</td>
                <td class="text-xs text-[var(--c-text-secondary)]">{log.model_name}</td>
                <td>{log.prompt_tokens}</td>
                <td>{log.completion_tokens}</td>
                <td class="text-xs text-[var(--c-text-secondary)]">{log.duration_ms}ms</td>
                <td><span class="badge {log.status === 'success' ? 'badge-success' : 'badge-error'} badge-xs">{log.status}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if logs.length === 0}
        <div class="text-center text-[var(--c-text-secondary)] py-4">暂无调用记录</div>
      {/if}
    </div>
  {/if}
</div>
