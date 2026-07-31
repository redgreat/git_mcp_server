// 内置 LLM 提供商目录（BaseUrl 与模型选项内置固定）
// 模型为各厂商 2026 年当前主推版本（经 OpenRouter / 官方文档核实），
// 每个提供商均支持选择「自定义…」手动填写最新模型名
export const LLM_PROVIDERS = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    desc: '深度求索',
    base_url: 'https://api.deepseek.com',
    models: ['deepseek-v4-pro', 'deepseek-v4-flash']
  },
  {
    id: 'qwen',
    name: '通义千问',
    desc: '阿里云百炼',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen3.5-max', 'qwen3.5-plus', 'qwen3.5-turbo', 'qwen3.5-flash']
  },
  {
    id: 'kimi',
    name: 'Kimi',
    desc: '月之暗面',
    base_url: 'https://api.moonshot.cn/v1',
    models: ['kimi-k3', 'kimi-k2']
  },
  {
    id: 'zhipu',
    name: '智谱 GLM',
    desc: '智谱AI',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-5.2', 'glm-5.1', 'glm-5-turbo']
  },
  {
    id: 'doubao',
    name: '豆包',
    desc: '火山方舟',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-seed-1-6', 'doubao-1-5-pro-32k']
  },
  {
    id: 'wenxin',
    name: '文心一言',
    desc: '百度千帆',
    base_url: 'https://qianfan.baidubce.com/v2',
    models: ['ernie-4.0-8k', 'ernie-4.0-turbo-8k']
  },
  {
    id: 'hunyuan',
    name: '腾讯混元',
    desc: '腾讯云',
    base_url: 'https://api.hunyuan.cloud.tencent.com/v1',
    models: ['hunyuan-pro', 'hunyuan-turbo']
  },
  {
    id: 'minimax',
    name: 'MiniMax',
    desc: 'MiniMax',
    base_url: 'https://api.minimax.chat/v1',
    models: ['MiniMax-M3', 'MiniMax-M2']
  }
];

// 自定义提供商（OpenAI 兼容接口）：BaseUrl / 模型名 / 提供商名称均可手动填写
export const CUSTOM_PROVIDER = {
  id: '__custom__',
  name: '自定义',
  desc: 'OpenAI 兼容接口',
  base_url: 'https://api.openai.com/v1',
  models: []
};

export const PROVIDER_OPTIONS = [...LLM_PROVIDERS, CUSTOM_PROVIDER];

// 模型下拉中「自定义…」选项的标记值
export const CUSTOM_MODEL_FLAG = '__custom_model__';

export function providerById(id) {
  return LLM_PROVIDERS.find((p) => p.id === id) || null;
}

export function providerLabel(id) {
  const p = providerById(id);
  return p ? `${p.name} (${p.desc})` : id || '未知';
}
