@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   Legal Vision - Streamlit App (localhost:8501)
echo ================================================
echo.

echo [1/3] Stopping any stale streamlit instances...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*streamlit_app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul

echo [2/3] Starting Streamlit (new window shows logs)...
start "Legal Vision Streamlit" cmd /k "cd /d ""%~dp0"" && .venv\Scripts\python.exe -m streamlit run streamlit_app.py"

echo [3/3] Opening the browser...
timeout /t 6 /nobreak >nul
start "" "http://localhost:8501"

echo.
echo Done. If the page does not open, check the "Legal Vision Streamlit" window.
endlocal