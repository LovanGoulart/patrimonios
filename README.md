# Patrimônio Pro — sistema mobile com SQLite

Sistema simples de patrimônio baseado no layout enviado, agora com backend Flask + banco SQLite real.

## Recursos
- Dashboard, equipamentos, manutenções e baixados.
- Cadastro por código de barras/patrimônio.
- Leitura pela câmera com `html5-qrcode`.
- Busca manual como alternativa.
- SQLite persistente (`patrimonio.db`).
- Edição, manutenção, baixa e histórico.
- Exportação CSV.
- Interface responsiva para celular.

## Executar no Windows
1. Instale Python 3.11+.
2. Execute `run.bat`.
3. Abra **http://localhost:5000**.

### Câmera
A câmera do navegador só funciona em contexto seguro. No computador, `http://localhost:5000` é considerado seguro para esse fim. No celular acessando o IP do computador via HTTP, o navegador pode bloquear a câmera; para uso pela rede no celular, publique com HTTPS (por exemplo, servidor com certificado) ou use a entrada manual.

O leitor tenta usar a câmera traseira e, se a permissão falhar, informa o motivo e mantém a entrada manual disponível.
