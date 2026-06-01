@echo off
chcp 65001 >nul
echo ========================================
echo   手机遥控电脑 - 环境初始化
echo ========================================

if not exist "venv" (
    echo 正在创建虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo 正在安装依赖...
pip install -r requirements.txt -q

echo.
echo 启动服务...
python server.py

pause
