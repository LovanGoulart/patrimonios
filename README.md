# Patrimônio Pro

Sistema web mobile de gestão de patrimônio com Flask, SQLite, autenticação e PWA.

## Recursos
- Cadastro e login de usuários com senha armazenada em hash.
- Sessão protegida para o sistema e APIs.
- Cadastro, edição, manutenção, baixa, histórico e exportação de equipamentos.
- Leitor de código de barras pela câmera e entrada manual.
- PWA instalável em Android, iPhone/iPad e desktop compatível.
- Service Worker e manifest.

## Primeiro acesso
1. Execute `run.bat` no Windows ou `python app.py`.
2. Abra `http://localhost:5000`.
3. Clique em **Criar conta**.
4. Depois do cadastro, você entra automaticamente no sistema.

## PythonAnywhere
- Source code: `/home/patrimonios/patrimonios`
- Working directory: `/home/patrimonios/patrimonios`
- WSGI:
```python
import sys
project_home = '/home/patrimonios/patrimonios'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
from app import app as application
```
- Instale as dependências de `requirements.txt`.
- Use HTTPS para que a câmera possa ser acessada pelo navegador.

## Banco
O SQLite é criado no diretório do projeto como `patrimonio.db`. A tabela `usuario` é criada automaticamente pelo `db.create_all()`.

## PWA
O manifest está em `/manifest.webmanifest` e o Service Worker em `/service-worker.js`, permitindo que o aplicativo seja instalado e tenha o shell básico armazenado em cache.
