@echo off
title 6大电商爆款监控与素材抓取
chcp 936 >nul
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Jackie-Zhang\anaconda3\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo =========================================================
echo   国内外 6 大电商 (拼多多/淘宝/抖音电商+TikTok/Amazon/Temu)
echo =========================================================
echo.
echo [1/2] 正在启动电商爆款监控程序，请稍候...
"%PYTHON_EXE%" main_ecommerce.py

echo.
echo [2/2] 电商采集流程执行完毕!
if exist "%~dp0materials\ecommerce_products" (
    echo 正在为你打开电商素材文件夹...
    explorer "%~dp0materials\ecommerce_products"
)
if exist "%~dp0materials\ecommerce_products\爆款选品汇总.xlsx" (
    echo 正在为你打开选品 Excel 表格...
    start "" "%~dp0materials\ecommerce_products\爆款选品汇总.xlsx"
)
echo.
pause
