@echo off
setlocal enabledelayedexpansion

chcp 65001 >nul

echo ============================================
echo   WebLogic Health Monitor - Launcher
echo ============================================
echo.

REM --- Find WLST ---------------------------------------------------
set WLST=

REM 1. Check MW_HOME environment variable
if defined MW_HOME (
    if exist "%MW_HOME%\oracle_common\common\bin\wlst.cmd" (
        set WLST=%MW_HOME%\oracle_common\common\bin\wlst.cmd
    )
)

REM 2. Check common installation paths
if not defined WLST (
    for %%p in (
        "C:\Oracle\Middleware\Oracle_Home"
        "C:\Oracle\Middleware\wlserver_12.2"
        "C:\Oracle\Middleware\wlserver_12.1"
        "C:\Program Files\Oracle\Middleware"
        "C:\Oracle\Middleware"
    ) do (
        if exist "%%~p\oracle_common\common\bin\wlst.cmd" (
            set WLST=%%~p\oracle_common\common\bin\wlst.cmd
            goto :found
        )
    )
)

:found
if not defined WLST (
    echo [ERROR] Could not find wlst.cmd
    echo.
    echo Make sure WebLogic is installed, then set the MW_HOME variable:
    echo   set MW_HOME=C:\Oracle\Middleware\Oracle_Home
    echo.
    echo Or edit this batch file and set WLST_PATH manually.
    pause
    exit /b 1
)

echo [OK] Found WLST: %WLST%
echo.

REM --- Run ----------------------------------------------------------
set USER_MEM_ARGS=-Xms256m -Xmx1024m
set WL_SCRIPT_DIR=%~dp0

REM --- Check .env ---------------------------------------------------
if not exist "%WL_SCRIPT_DIR%.env" (
    echo [INFO] No .env file found. Creating from .env.example ...
    if exist "%WL_SCRIPT_DIR%.env.example" (
        copy "%WL_SCRIPT_DIR%.env.example" "%WL_SCRIPT_DIR%.env" >nul
        echo.
        echo [ACTION REQUIRED] Edit .env with your credentials:
        echo    notepad "%WL_SCRIPT_DIR%.env"
        echo.
        pause
        exit /b 1
    ) else (
        echo [ERROR] .env.example not found. Re-download the repo.
        pause
        exit /b 1
    )
)

echo [OK] Starting WLST ...
echo.

"%WLST%" "%WL_SCRIPT_DIR%weblogic_monitor.py" %*

echo.
echo ============================================
pause
