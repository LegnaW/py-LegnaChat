@echo off
echo ========================================
echo installing...
echo ========================================

echo.
echo [1/3] create virtual-env...
python -m venv venv

echo.
echo [2/3] activate virtual-env...
call venv\Scripts\activate.bat

echo.
echo [3/3] installing...
pip install -r requirements.txt

echo.
echo ========================================
echo finished!
echo ========================================
pause
