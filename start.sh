#!/usr/bin/env bash
# StockAnalyzer 一键启动脚本 (macOS / Linux)
# 用法：
#   ./start.sh                 # 默认 127.0.0.1:8000
#   HOST=0.0.0.0 PORT=9000 ./start.sh
#   ./start.sh --reload        # 透传给 uvicorn 的参数

set -e

# 切换到脚本所在目录，保证从任意位置调用都正常
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# 1. 准备虚拟环境
if [ ! -d "$VENV_DIR" ]; then
  echo "[start] 未发现 $VENV_DIR，正在创建..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 2. 按需安装依赖（用 uvicorn 是否可导入作为快速判断）
if ! python -c "import uvicorn, fastapi" >/dev/null 2>&1; then
  echo "[start] 正在安装依赖..."
  python -m pip install --upgrade pip
  python -m pip install -e .
fi

# 3. 检查大模型配置
if [ ! -f "llm_config.json" ]; then
  if [ -f "llm_config.example.json" ]; then
    echo "[start] 未发现 llm_config.json，已从 llm_config.example.json 复制一份，请编辑后填入 API Key。"
    cp llm_config.example.json llm_config.json
  else
    echo "[start] 警告：未发现 llm_config.json，且没有示例文件。大模型调用会失败。"
  fi
fi

# 4. 启动服务
echo "[start] 启动 FastAPI 服务于 http://${HOST}:${PORT}"
exec python -m uvicorn api.main:app --host "$HOST" --port "$PORT" "$@"
