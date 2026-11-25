# Maximum Farmácia — Recovery
Reconstrução independente, somente leitura. Não recria regras de negócio antigas desconhecidas.

## Windows
Instale Node.js 20 ou superior. Execute START.cmd, preencha .env e execute novamente. ADMIN_PASSWORD deve ter pelo menos 16 caracteres. Use um usuário MongoDB com papel read no banco original, não readWrite. Caso o usuário não possa listar bancos, informe MONGODB_DB. Autorize somente o IP necessário no Atlas. Não envie .env ao GitHub.

## Hospedagem
Node.js/Express: npm install e npm start. Configure as variáveis do .env.example no painel, HOST=0.0.0.0 se necessário e HTTPS obrigatório para Basic Auth. Para Vercel, importe o repositório e configure as variáveis; grandes exportações podem exceder limites serverless, prefira execução local. Não exponha o painel sem HTTPS. Dados de farmácia podem ser sensíveis: acesso restrito e armazenamento seguro dos arquivos exportados.

## Recursos
Descoberta de bancos e coleções autorizados, paginação, filtro textual por campo, detalhes JSON, exportação JSON Extended BSON e CSV (ID e documento JSON). Campos de credenciais comuns são ocultados por nome; isso não garante anonimização. O painel não altera registros. Para backup integral use mongodump com credenciais de leitura e proteja o arquivo. Exporte localmente para grandes volumes.
