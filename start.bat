@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   Legal Vision - Web Frontend (localhost:8000)
echo ================================================
echo.

echo [1/3] Stopping any stale backend instances...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*backend.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul

echo [2/3] Starting the analysis engine...
powershell -NoProfile -Command "$p = Start-Process -FilePath '%~dp0.venv\Scripts\python.exe' -ArgumentList 'backend.py' -WorkingDirectory '%~dp0' -RedirectStandardOutput '%~dp0temp\backend.log' -RedirectStandardError '%~dp0temp\backend_err.log' -WindowStyle Hidden -PassThru; $p.Id" > "%~dp0temp\backend_pid.txt" 2>nul

echo [3/3] Waiting for the engine to come online...
set /a tries=0
:WaitLoop
set /a tries+=1
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; try { (Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/health -TimeoutSec 2).StatusCode } catch { 0 }" > "%~dp0temp\health.txt" 2>nul
set /p engine= < "%~dp0temp\health.txt"
del "%~dp0temp\health.txt" >nul 2>nul
if not "%engine%"=="200" (
    if %tries% GTR 90 (
        echo.
        echo The engine did not start in time.
        echo Check temp\backend.log and temp\backend_err.log for errors.
        pause
        exit /b 1
    )
    if %tries% EQU 1 echo   waiting for the engine...
    timeout /t 2 /nobreak >nul
    goto WaitLoop
)

echo Engine is up.
start "" "http://localhost:8000"
echo.
echo Done. The web frontend is open in your browser.
echo Backend logs are in temp\backend.log.
endlocal