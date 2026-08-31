#!/bin/bash
echo "=========================================="
echo "   PATRIMONIO PRO - Iniciando servidor"
echo "=========================================="
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
python app.py