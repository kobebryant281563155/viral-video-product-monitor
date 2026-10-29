@echo off
title 爆款视频监控与无水印下载
chcp 936 >nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Jackie-Zhang\anaconda3\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo =========================================================
echo   国内外 4 大平台 (抖音/小红书/TikTok/Instagram) 爆款监控
echo =========================================================
echo.
echo [1/2] 正在启动视频巡检程序，请稍候...
"%PYTHON_EXE%" main.py --mode once

echo.
echo [2/2] 巡检流程执行完毕!
if exist "%~dp0materials\viral_competitors" (
    echo 正在为你打开素材文件夹...
    explorer "%~dp0materials\viral_competitors"
)
echo.
pause
