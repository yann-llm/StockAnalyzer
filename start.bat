@echo off
REM StockAnalyzer 一键启动脚本 (Windows)
REM 用法：
REM   start.bat
REM   set HOST=0.0.0.0 ^&^& set PORT=9000 ^&^& start.bat

setlocal

cd /d "%~dp0"

if "%PYTHON_BIN%"=="" set PYTHON_BIN=python
if "%HOST%"=="" set HOST=127.0.0.1
if "%PORT%"=="" set PORT=8000
set VENV_DIR=.venv

REM 1. 准备虚拟环境
if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo [start] 未发现 %VENV_DIR%，正在创建...
  %PYTHON_BIN% -m venv %VENV_DIR%
  if errorlevel 1 goto :error
)

call "%VENV_DIR%\Scripts\activate.bat"

REM 2. 按需安装依赖
python -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 (
  echo [start] 正在安装依赖...
  python -m pip install --upgrade pip
  python -m pip install -e .
  if errorlevel 1 goto :error
)

REM 3. 检查大模型配置
if not exist "llm_config.json" (
  if exist "llm_config.example.json" (
    echo [start] 未发现 llm_config.json，已从 llm_config.example.json 复制一份，请编辑后填入 API Key。
    copy /Y llm_config.example.json llm_config.json >nul
  ) else (
    echo [start] 警告：未发现 llm_config.json，且没有示例文件。大模型调用会失败。
  )
)

REM 4. 启动服务
echo [start] 启动 FastAPI 服务于 http://%HOST%:%PORT%
python -m uvicorn api.main:app --host %HOST% --port %PORT% %*
goto :eof

:error
echo [start] 启动失败，请查看上面的错误信息。
exit /b 1
