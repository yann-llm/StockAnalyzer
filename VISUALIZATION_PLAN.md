# Eastmoney 简化可视化界面完成计划

## 目标

基于新版 `index.html` 简化设计图，完成一个本地可用的股票分析可视化界面。第一版聚焦单屏工作流：输入股票代码，检查本地数据，必要时触发分析，最后展示结构化结论。

本阶段不做复杂多页面工作台、登录权限、部署系统和行业专题页，先把核心分析入口做稳。

## 新版设计图结构

`index.html` 当前定义的是一个轻量股票分析 Workbench：

- 顶部栏：品牌标识、说明文案、本地服务/API 连接状态。
- 输入区：股票代码输入框、开始分析按钮、已缓存股票快捷入口。
- 执行步骤：等待输入、检查本地抓取数据、调用大模型分析、分析完成。
- 结果区：股票名称、代码、分析时间、数据源、模型状态、缓存标记。
- 结果正文：投资结论、财务质量、行业与资金、估值位置、主要风险。
- 底部状态：数据目录、缓存股票数量、最近命中、构建环境。

## 完成范围

### 必须完成

- 界面可以真实读取本地 `data/<stock_code>/` 数据。
- 输入 6 位 A 股代码后能返回分析状态。
- 命中缓存时直接展示结果，并标明“缓存命中”。
- 未命中缓存时可以触发后端分析流程，并展示执行中/失败/完成状态。
- 结果区从真实聚合数据生成，避免只保留静态 mock。
- 复制结果、重新分析、快捷股票按钮可用。
- 移动端和桌面端布局不重叠、不溢出。

### 暂不完成

- 多页面 Dashboard。
- 独立行业专题页。
- 用户系统和权限。
- 云端部署。
- 报告库、历史报告管理和导出系统。

## 技术路线

### 后端

使用 `FastAPI` 作为本地 API 层，直接复用现有 Python 模块。

建议新增目录：

```text
api/
  main.py
  schemas.py
  services/
    data_store.py
    analysis_runner.py
```

核心职责：

- `data_store.py`：读取 `cache_manifest.json` 和 `cleaned/*.json`。
- `analysis_runner.py`：包装 `main.py` 里的股票分析入口，处理任务状态。
- `main.py`：暴露健康检查、股票摘要、分析触发接口。

### 前端

第一版保留 `index.html` 的单文件设计风格，优先接真实 API。

原因：

- 当前设计已经完整表达了第一版交互。
- 单文件接 API 改动小，能快速验证数据闭环。
- 等交互和数据模型稳定后，再决定是否迁移到 React/Next.js。

## API 设计

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务健康检查，返回本地服务状态 |
| `GET` | `/api/stocks` | 列出已有缓存股票 |
| `GET` | `/api/stocks/{stock_code}/summary` | 返回界面所需的聚合摘要 |
| `POST` | `/api/stocks/{stock_code}/analyze` | 触发股票分析 |
| `GET` | `/api/jobs/{job_id}` | 查询分析任务状态 |

`summary` 建议返回稳定视图模型：

```json
{
  "stock_code": "000157",
  "stock_name": "中联重科",
  "market_code": "000157.SZ",
  "generated_at": "2026-05-20 08:52",
  "cache_hit": true,
  "data_source": "data/000157/cleaned/",
  "modules": {
    "financial": {"status": "success"},
    "industry": {"status": "success"},
    "notice_risk": {"status": "success"},
    "stockcomment": {"status": "success"},
    "valuation": {"status": "success"}
  },
  "sections": [
    {"key": "thesis", "title": "投资结论", "body": "..."},
    {"key": "financial", "title": "财务质量", "body": "..."},
    {"key": "industry", "title": "行业与资金", "body": "..."},
    {"key": "valuation", "title": "估值位置", "body": "..."},
    {"key": "risk", "title": "主要风险", "body": "..."}
  ]
}
```

## 前端状态设计

### 初始状态

- 输入框为空。
- 步骤停留在“等待输入”。
- 结果区显示默认缓存股票或空状态。
- 快捷入口展示 `/api/stocks` 返回的缓存股票。

### 缓存命中

- 输入股票代码后请求 `/api/stocks/{stock_code}/summary`。
- 若存在完整摘要：
  - 步骤 1 到 4 全部完成。
  - meta 显示“缓存命中”。
  - 结果区直接渲染真实摘要。

### 缓存缺失

- summary 返回未找到或模块不完整。
- 点击开始分析后调用 `/api/stocks/{stock_code}/analyze`。
- 步骤依次显示：
  - 已接收代码。
  - 正在检查本地数据。
  - 正在运行数据抓取/清洗/模型分析。
  - 完成后重新请求 summary。

### 失败状态

- 后端返回模块失败、任务失败或读取异常时：
  - stepper 显示失败所在步骤。
  - meta 显示错误摘要。
  - 结果区保留已有旧结果或显示可恢复空状态。
  - 允许重新分析。

## 实施里程碑

### Milestone 1：真实数据读取

任务：

- 新增 `api/services/data_store.py`。
- 实现缓存股票扫描。
- 实现 manifest 和 cleaned JSON 读取。
- 将各模块状态聚合成 summary。
- 补充基础测试，覆盖存在、不存在、模块缺失三种情况。

验收：

- `GET /api/stocks` 能返回本地缓存股票。
- `GET /api/stocks/000157/summary` 能返回可供前端渲染的 JSON。

### Milestone 2：本地 API 服务

任务：

- 新增 `api/main.py`。
- 暴露 `/api/health`、`/api/stocks`、`/api/stocks/{stock_code}/summary`。
- 加入统一错误结构。
- 配置 CORS，允许本地 HTML 调用。

验收：

- 浏览器或命令行可以访问 API。
- 股票不存在时返回清晰错误，而不是 Python traceback。

### Milestone 3：接入新版 HTML

任务：

- 将 `index.html` 中的 mock 数据替换为 API 请求。
- 快捷股票按钮由 `/api/stocks` 动态生成。
- 输入校验限制为 6 位数字。
- 渲染真实 stepper、result header、result sections。
- 保留复制结果和重新分析按钮。

验收：

- 打开页面输入 `000157` 可以展示真实数据摘要。
- 切换缓存股票后页面内容同步更新。
- 网络/API 失败时页面有明确反馈。

### Milestone 4：分析任务触发

任务：

- 新增 `api/services/analysis_runner.py`。
- 新增 `POST /api/stocks/{stock_code}/analyze`。
- 第一版可用内存任务表记录状态。
- 前端轮询 `/api/jobs/{job_id}`。
- 任务完成后自动刷新 summary。

验收：

- 输入未缓存股票后可以触发分析。
- 分析过程中 stepper 显示进行中状态。
- 完成后结果区自动刷新。

### Milestone 5：视觉与交互打磨

任务：

- 检查桌面、平板、手机宽度下的文本换行。
- 优化按钮 loading、disabled、error 状态。
- 统一成功、警告、失败的颜色语义。
- 检查结果正文长文本不会撑破容器。
- 用浏览器实际截图验证首屏和结果区。

验收：

- 1366px、1024px、390px 宽度下没有重叠和横向溢出。
- 所有按钮状态清晰。
- 首屏能明确表达“输入股票代码，开始分析”。

## 开发顺序建议

1. 先做 `data_store.py`，确定真实数据能被稳定读出。
2. 再做 FastAPI，只暴露只读 summary。
3. 接 `index.html`，把静态 mock 改成真实接口。
4. 最后加分析任务触发，避免一开始把数据读取和任务执行耦合。
5. 完成后做响应式与错误状态验证。

## 风险与注意事项

- `run_stock_analysis` 是同步分析流程，不能直接阻塞 API 请求太久；第一版用后台任务包装。
- 东方财富抓取依赖网络，页面不要自动触发抓取，必须由用户点击开始。
- 本地数据字段可能不稳定，前端应依赖后端 summary，不直接读取原始 cleaned JSON。
- `reviews/` 是验证资料，不进入界面展示。
- 如果 LLM 结果尚未落盘，summary 应先给出模块级摘要，后续再接完整报告生成。

## 下一步

## 当前进度

- Milestone 1：真实数据读取已完成。
- Milestone 2：本地 API 服务已完成。
- Milestone 3：新版 HTML 已接入真实 API。
- Milestone 4：分析任务触发已完成，支持强制刷新、任务去重、任务查询和前端轮询。
- Milestone 5：已完成第一轮交互打磨，新增最近任务面板和模块状态可视化。

## 后续建议

下一步进入更细的可视化增强：把 `metrics` 和 `risk_flags` 独立展示成紧凑指标条、风险列表和行业/估值小图表，而不是只放在长文本摘要里。
