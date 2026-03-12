@echo off
echo ========================================
echo starting py-legnatest Agent(Webui Mode)
echo ========================================

echo.
echo activating venv...
call venv\Scripts\activate.bat

echo.
echo starting webui...
python webui.py

pause
