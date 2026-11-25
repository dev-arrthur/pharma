# Maximum Farmácia — Recovery
Reconstrução independente, somente leitura. Não recria regras de negócio antigas desconhecidas.

## Windows
Instale Node.js 20 ou superior. Execute START.cmd, preencha .env e execute novamente. ADMIN_PASSWORD deve ter pelo menos 16 caracteres. Use um usuário MongoDB com papel read no banco original, não readWrite. Caso o usuário não possa listar bancos, informe MONGODB_DB. Autorize somente o IP necessário no Atlas. Não envie .env ao GitHub.

## Hospedagem
Node.js/Express: npm install e npm start. Configure as variáveis do .env.example no painel, HOST=0.0.0.0 se necessário e HTTPS obrigatório para Basic Auth. Para Vercel, importe o repositório e configure as variáveis; grandes exportações podem exceder limites serverless, prefira execução local. Não exponha o painel sem HTTPS. Dados de farmácia podem ser sensíveis: acesso restrito e armazenamento seguro dos arquivos exportados.

## Recursos
Descoberta de bancos e coleções autorizados, paginação, filtro textual por campo, detalhes JSON, exportação JSON Extended BSON e CSV (ID e documento JSON). Campos de credenciais comuns são ocultados por nome; isso não garante anonimização. O painel não altera registros. Para backup integral use mongodump com credenciais de leitura e proteja o arquivo. Exporte localmente para grandes volumes.

## PDF em Python
Execute GERAR_PDF.cmd no Windows (Python 3 instalado). Ou rode `python -m pip install -r requirements.txt` e `python gerar_relatorio.py`. O PDF consulta os registros reais, sem valores fictícios, com identidade visual vinho da Maximum, resumo por coleção e detalhes. Configure MONGODB_DB para restringir a base e use credencial somente leitura. A execução é local; não publique os PDFs. Campos monetários reconhecidos são formatados em reais, sem somar categorias de significado desconhecido. Grandes bases podem exigir muita memória.
