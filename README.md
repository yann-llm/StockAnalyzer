# StockAnalyzer

StockAnalyzer 是一个基于东方财富公开数据的本地股票分析工作台。项目会抓取并清洗 A 股个股相关数据，再调用大模型生成结构化分析结果，最后通过本地前端页面展示投资结论、千股千评、财务、行业、估值和公告风险等模块。

## 主要功能

- 抓取东方财富个股数据，包括财务报表、行业数据、估值、公告风险和千股千评。
- 对各模块数据进行清洗和结构化整理。
- 可通过配置选择 OpenAI SDK 或 Anthropic SDK 调用大模型。
- 每个子模块都有独立的大模型分析脚本，便于维护提示词。
- 支持并行执行五个子模块分析，提高整体分析速度。
- 提供 FastAPI 本地接口和静态 HTML 前端页面。
- 前端支持任务进度展示，执行分析时会显示各子模块抓取、清洗、大模型分析的实时状态。

## 项目结构

```text
api/                  FastAPI 接口和任务状态服务
financial/            财务数据抓取、清洗和大模型分析
industry/             行业数据抓取、清洗和大模型分析
notice_risk/          公告风险数据抓取、清洗和大模型分析
stockcomment/         千股千评数据抓取、清洗和大模型分析
valuation/            估值数据抓取、清洗和大模型分析
llm.py                通用大模型调用模块
main.py               股票完整分析主流程
index.html            本地前端页面
data/                 本地缓存数据目录，默认不提交到 Git
```

## 环境要求

- Python 3.11+
- 可访问东方财富公开接口的网络环境
- 可访问 OpenAI 兼容服务或 Anthropic API

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置大模型

推荐复制 `llm_config.example.json` 为 `llm_config.json`，再按需选择 SDK：

```json
{
  "provider": "anthropic",
  "timeout": 300,
  "max_retries": 0,
  "providers": {
    "anthropic": {
      "model": "claude-sonnet-4-5",
      "api_key": "你的 Anthropic API Key",
      "base_url": null
    }
  }
}
```

`provider` 可选：

- `openai`：使用 OpenAI SDK，支持 OpenAI 官方或兼容 OpenAI Chat Completions 的服务。
- `anthropic`：使用 Anthropic SDK，调用 Anthropic Messages API。

`llm_config.json` 已加入 `.gitignore`，避免提交密钥。也可以通过 `LLM_CONFIG_PATH` 指定其他配置文件路径。

仍然兼容原有环境变量：

```bash
set MY_API_KEY=你的 API Key
set MY_BASE_URL=你的 OpenAI 兼容接口地址
```

PowerShell 示例：

```powershell
$env:MY_API_KEY="你的 API Key"
$env:MY_BASE_URL="你的 OpenAI 兼容接口地址"
```

Anthropic 环境变量示例：

```powershell
$env:LLM_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="你的 Anthropic API Key"
$env:LLM_MODEL="claude-sonnet-4-5"
```

## 启动后端 API

在项目根目录运行：

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可以访问：

- `http://127.0.0.1:8000/`

## 打开前端页面

页面会连接本地 API，输入 6 位股票代码后可以查看缓存摘要或重新执行完整分析。

默认股票代码在 `main.py` 中配置为 `000157`。完整分析会将原始数据、清洗数据和大模型分析结果写入 `data/<stock_code>/` 目录。

## 分析流程

1. 检查本地缓存。
2. 并行执行千股千评、财务、行业、公告风险和估值五个子模块。
3. 每个模块依次完成数据抓取、数据清洗和大模型分析。
4. 大模型分析成功后写入 `analysis` 目录。
5. 大模型分析失败时会标注失败，并写入错误文件。
6. 前端根据 API 聚合结果展示结论、综合评分、判断依据和风险提示。

## 注意事项
- 如果前端提示 API 未连接，请先确认 FastAPI 服务已经启动。
