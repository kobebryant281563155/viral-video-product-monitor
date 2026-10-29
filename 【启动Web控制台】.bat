@echo off
title 全网爆款监控与选品Web中控台 (端口 8768)
chcp 936 >nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Jackie-Zhang\anaconda3\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo [1/1] 启动 8768 Web 服务...
"%PYTHON_EXE%" web/server.py
pause
