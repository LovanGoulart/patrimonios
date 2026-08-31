# Patrimônio Pro

Sistema web/mobile de gestão de patrimônio com Flask, SQLite, autenticação e PWA.

## ✨ Recursos
- 🔐 Cadastro e login de usuários com senha em hash
- 📦 Cadastro, edição, manutenção, baixa e histórico de equipamentos
- 📷 Leitor de código de barras pela câmera + entrada manual
- 📊 Dashboard com estatísticas e atividades recentes
- 📱 PWA instalável em Android, iPhone e desktop
- 📋 Exportação CSV de equipamentos
- 🎨 Interface responsiva com menu rodapé mobile

## 🚀 Primeiro Acesso

### Windows
```
run.bat
```

### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra `http://localhost:5000` e clique em **Criar conta**.

## 📁 Estrutura
```
patrimonio_pro/
├── app.py                  # Backend Flask
├── requirements.txt        # Dependências
├── templates/
│   ├── auth.html          # Login/Cadastro (toggle)
│   └── base.html          # Sistema principal + menu rodapé
├── static/
│   ├── js/app.js          # Lógica frontend
│   ├── manifest.webmanifest
│   ├── service-worker.js
│   └── icons/
│       ├── icon-192.png
│       └── icon-512.png
└── patrimonio.db          # Banco SQLite (gerado automaticamente)
```

## 🌐 Deploy (PythonAnywhere)
- Working directory: `/home/seuusuario/patrimonio_pro`
- WSGI:
```python
import sys
project_home = '/home/seuusuario/patrimonio_pro'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
from app import app as application
```
- Use HTTPS para a câmera funcionar no navegador.

## 📝 Licença
Uso livre para fins comerciais e pessoais.
