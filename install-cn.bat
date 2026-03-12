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
echo [3/3] installing(for CN users)...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo ========================================
echo finished!
echo ========================================
pause
