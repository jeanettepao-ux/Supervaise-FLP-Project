@echo off
REM ============================================================
REM restart.bat — kill any running Streamlit and relaunch fresh.
REM Usage: double-click in File Explorer, or run from cmd in
REM        the project folder. Works whether or not anything is
REM        currently running on port 8501.
REM ============================================================

echo === Killing any process holding port 8501 ===
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>nul
    echo   killed PID %%a
)

echo.
echo === Starting Streamlit ===
.venv\Scripts\python.exe -m streamlit run app.py
