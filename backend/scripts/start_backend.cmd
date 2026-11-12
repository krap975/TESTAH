@echo off
setlocal
rem Run in an ordinary authorized terminal; this script never elevates privileges.
if "%CODEX_SANDBOX_NETWORK_DISABLED%"=="1" (
    echo This shell carries a network-disabled marker. Verify actual API access with the development provider check before generation.
)
if /i "%CODEX_SANDBOX_NETWORK_DISABLED%"=="true" (
    echo This shell carries a network-disabled marker. Verify actual API access with the development provider check before generation.
)
pushd "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Backend virtual environment is missing. Follow README setup.
    popd
    exit /b 1
)
rem No reload: file edits must not cancel active generation. Settings load once.
".venv\Scripts\python.exe" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
set "testahExit=%errorlevel%"
popd
exit /b %testahExit%
