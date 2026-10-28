@echo off
title 哈尼族非遗文化网站 - 后端服务
cd /d %~dp0

set "LOGFILE=backend\startup.log"
set "PYTHONIOENCODING=utf-8"
echo [%date% %time%] ===== 启动脚本开始 ===== > "%LOGFILE%"

echo ============================================================
echo   哈尼族非遗文化网站 - 后端启动器
echo   本窗口关闭 = 停止服务
echo   日志: %LOGFILE%
echo ============================================================
echo.

REM ---------- 1. 虚拟环境 ----------
echo [1/5] 检查 Python 虚拟环境...
if not exist "backend\venv\Scripts\python.exe" (
    echo   [错误] 未找到 backend\venv\Scripts\python.exe
    echo   请先创建: python -m venv backend\venv
    pause
    exit /b 1
)
call "backend\venv\Scripts\activate.bat" >> "%LOGFILE%" 2>&1
echo   OK: 已激活 backend\venv
echo.

REM ---------- 2. API 配置 ----------
echo [2/5] 检查 API 配置...
if exist "backend\.env" (
    echo   OK: 已找到 backend\.env，LLM_API_KEY 将自动加载
) else (
    echo   未找到 backend\.env，将使用默认配置
)
echo.

REM ---------- 3. 依赖 ----------
echo [3/5] 检查 Python 依赖...
python -c "import flask, flask_cors, openai, dotenv" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo   检测到依赖缺失，正在自动安装...
    pip install -r backend\requirements.txt >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo   [错误] 依赖安装失败，详见: %LOGFILE%
        pause
        exit /b 1
    )
) else (
    echo   OK: 依赖已就绪
)
echo.

REM ---------- 4. 端口 5000：被占用则自动释放 ----------
echo [4/5] 检查端口 5000...
set "OLD_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do set "OLD_PID=%%a"
if defined OLD_PID (
    echo   端口被进程 PID=%OLD_PID% 占用，尝试释放...
    taskkill /PID %OLD_PID% /F >> "%LOGFILE%" 2>&1
    timeout /t 2 /nobreak >nul
    echo   已处理，继续启动
) else (
    echo   OK: 端口 5000 可用
)
echo.

REM ---------- 5. 启动 ----------
echo [5/5] 正在启动后端服务...
echo   首页: http://localhost:5000/
echo   AI 对话: http://localhost:5000/ai-assistant.html
echo   约 5 秒后自动打开浏览器；关闭本窗口即停止服务。
echo.

start "" /b cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:5000/"

python backend\app.py >> "%LOGFILE%" 2>&1

echo.
echo ============================================================
echo   服务已停止。若启动失败，请打开 %LOGFILE% 查看错误并发给我。
echo ============================================================
pause
