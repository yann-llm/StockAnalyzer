# StockAnalyzer

StockAnalyzer 是一个基于东方财富公开数据的本地证券分析工作台。项目会按证券类型（A 股个股或 ETF 基金）抓取并清洗对应数据，再调用大模型生成结构化分析结果，最后通过本地前端页面展示投资结论、千股千评、财务、行业、估值、公告风险或 ETF 五维分析等模块。

## 示例截图

![StockAnalyzer 前端界面示例](https://img.ylaizxx.cn/df89425d-25ac-45ae-bfbb-b5b46ec9e68b.avif)

## 主要功能

- 自动按 6 位代码识别证券类型（A 股个股或 ETF 基金），选择对应分析模块集合。
- 抓取东方财富数据：A 股覆盖财务报表、行业数据、估值、公告风险和千股千评；ETF 覆盖产品与指数定位、收益表现、风险与波动、持仓与行业暴露、规模与流动性五个维度。
- 对各模块数据进行清洗和结构化整理。
- 可通过配置选择 OpenAI SDK 或 Anthropic SDK 调用大模型。
- 每个子模块都有独立的大模型分析脚本，便于维护提示词。
- 支持并行执行五个子模块分析，提高整体分析速度。
- 五个子模块完成后，再由最终评估分析器汇总成投资结论、综合评分、判断依据和风险提示。
- 大模型提示词要求专业术语（专业名词 / Professional Term）附中文解释，输出对非专业用户更友好。
- 对东方财富域名做了带范围限定的 TLS 证书容错，证书链问题时自动降级重试，避免本地环境抓取被卡住。
- 健壮的 JSON 解析：兼容大模型输出含未转义双引号、Markdown 代码块包裹等情况，避免子模块评分丢失。
- 提供 FastAPI 本地接口和静态 HTML 前端页面。
- 前端支持任务进度展示，执行分析时会显示各子模块抓取、清洗、大模型分析的实时状态。

## 项目结构

```text
api/                          FastAPI 接口、任务状态服务和分析编排
financial/                    财务数据抓取、清洗和大模型分析（个股）
industry/                     行业数据抓取、清洗和大模型分析（个股）
notice_risk/                  公告风险数据抓取、清洗和大模型分析（个股）
stockcomment/                 千股千评数据抓取、清洗和大模型分析（个股 / ETF 共用）
valuation/                    估值数据抓取、清洗和大模型分析（个股）
etf_fund/                     ETF 基金数据抓取、清洗和五维大模型分析
final_evaluation_llm_analyzer.py  汇总各子模块结果生成最终投资结论
security_profile.py           按代码前缀识别 ETF / 个股的证券类型解析器
eastmoney_http.py             东方财富 HTTP/HTTPS 请求封装（含 TLS 证书容错）
llm.py                        通用大模型调用模块（OpenAI / Anthropic）
main.py                       完整分析主流程
index.html                    本地前端页面
data/                         本地缓存数据目录，默认不提交到 Git
```

## 环境要求

- Python 3.11+
- 可访问东方财富公开接口的网络环境
- 可访问 OpenAI 兼容服务或 Anthropic API

## 安装依赖

依赖统一在 `pyproject.toml` 中声明，安装命令：

```bash
pip install .
```

如果需要在本地以可编辑模式（editable install）调试源码，使用：

```bash
pip install -e .
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

页面会连接本地 API，输入 6 位证券代码（A 股个股或 ETF 基金）后可以查看缓存摘要或重新执行完整分析。系统会按代码前缀自动判定类型并选择对应分析模块集合。

默认证券代码在 `main.py` 中配置为 `000157`。完整分析会将原始数据、清洗数据和大模型分析结果写入 `data/<stock_code>/` 目录。

## 分析流程

1. 检查本地缓存，并通过 `security_profile.py` 识别该代码属于 A 股个股还是 ETF 基金。
2. 按证券类型并行执行对应的五个子模块：
   - A 股个股：千股千评、财务、行业、公告风险、估值。
   - ETF 基金：产品与指数定位、收益表现、风险与波动、持仓与行业暴露、规模与流动性。
3. 每个模块依次完成数据抓取、数据清洗和大模型分析。
4. 大模型分析成功后写入 `analysis` 目录。
5. 大模型分析失败时会标注失败，并写入错误文件。
6. 五个子模块完成后，调用最终评估分析器（`final_evaluation_llm_analyzer.py`）综合各模块结论。
7. 前端根据 API 聚合结果展示结论、综合评分、判断依据和风险提示。

## 注意事项
- 如果前端提示 API 未连接，请先确认 FastAPI 服务已经启动。
