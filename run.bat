@echo off
echo ==========================================
echo    PATRIMONIO PRO - Iniciando servidor
echo ==========================================
if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
pause