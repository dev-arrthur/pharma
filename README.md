# Maximum Farmácia - Consulta e relatórios

Gerador local de **PDF e HTML** e painel de consulta para registros do MongoDB. O relatório apresenta os campos e as respostas de cada registro, incluindo itens dentro de listas. A leitura não altera os dados originais.

**O repositório contém o programa, não os registros da farmácia.** Para preencher os relatórios, escolha o banco que contém os dados ou um arquivo exportado. Nenhum valor de demonstração é inserido automaticamente.

## Gerar PDF e HTML no Windows

1. Baixe o projeto completo e extraia o ZIP.
2. Instale Python 3.10 ou superior, com a opção **Add Python to PATH**.
3. Abra **GERAR_PDF.cmd**.
4. Escolha a origem: **1 - MongoDB**, **2 - arquivo exportado** ou **3 - pasta de exportações**.
5. Aguarde a geração. O PDF e o HTML serão abertos e salvos na pasta **relatorios-gerados**.

Na opção MongoDB, configure `MONGODB_URI` e, de preferência, `MONGODB_DB` no `.env`. Se o arquivo ainda não existir, o inicializador cria uma cópia do modelo e abre o Bloco de Notas para preenchimento. Ele preserva um `.env` já existente. Use uma credencial com permissão de leitura e autorize o IP do computador no provedor do banco.

As opções de importação aceitam JSON, JSONL/NDJSON e CSV. Elas dispensam acesso à Vercel e não precisam de usuário ou senha do banco. A instalação inicial das dependências precisa de internet; depois, os arquivos exportados podem ser processados localmente.

Leia [LEIA-ME-RELATORIOS.md](LEIA-ME-RELATORIOS.md) para os formatos aceitos, exemplos de uso e interpretação do resultado.

### O que aparece nos relatórios

- Respostas e valores conforme a origem, inclusive `0` e `false`.
- Identificação de itens aninhados, com caminho e posição nas listas.
- Indicação explícita de campos vazios ou sem resposta registrada.
- Resumo da origem e das categorias lidas; falhas são identificadas como leitura parcial.
- Layout vinho e branco da Maximum, em PDF para compartilhar e HTML para consultar no navegador.

Credenciais reconhecidas são omitidas. Os demais dados pessoais podem permanecer no documento; isso não equivale a anonimização. A extração também não substitui um backup integral nem garante uma fotografia transacional do banco durante alterações simultâneas.

### Valores e vínculos

O programa não presume que todo campo `total` é um valor em reais. Para formatar moeda ou associar um identificador ao nome correspondente, configure os campos explicitamente a partir de [config-relatorio.example.json](config-relatorio.example.json) e execute com `--config config-relatorio.json`. Os nomes no exemplo precisam ser adaptados aos nomes reais da sua origem. Sem um mapeamento confirmado, números e identificadores são preservados.

### Terminal

```bash
python -m pip install -r requirements.txt

# MongoDB configurado no .env
python gerar_relatorio.py

# Arquivo exportado ou pasta de arquivos
python gerar_relatorio.py --entrada "entradas/compras.json"
python gerar_relatorio.py --entrada "entradas"

# Saída específica e configuração explícita
python gerar_relatorio.py "relatorios-gerados/Conferencia.pdf" --entrada "entradas" --config "config-relatorio.json"
```

O arquivo HTML usa o mesmo nome-base do PDF. Códigos de saída: `0` = leitura concluída, `2` = relatório parcial gerado, `1` = erro sem geração concluída, `3` = seleção cancelada. Um retorno de erro não abre arquivos antigos.

## Painel web Node.js

O painel web continua disponível separadamente. Ele consulta o MongoDB e não precisa estar em execução para usar o gerador Python.

1. Instale Node.js 20 ou superior.
2. Copie `.env.example` para `.env` e configure `MONGODB_URI`, `MONGODB_DB`, `ADMIN_USER` e `ADMIN_PASSWORD`.
3. Use uma senha administrativa de pelo menos 16 caracteres.
4. Execute `START.cmd`, ou `npm install` seguido de `npm start`.
5. Abra `http://localhost:3000`.

O painel oferece categorias, pesquisa textual, detalhes dos registros, CSV/JSON e exportação HTML. Sua autenticação administrativa é independente da credencial de leitura do MongoDB.

### Hospedagem do painel

Em um servidor Node.js, configure as variáveis no ambiente e execute `npm start`. Ajuste `HOST=0.0.0.0` quando o servidor exigir escuta externa, com HTTPS e controle de acesso. Uma implantação e a conexão com o banco precisam ser validadas no ambiente escolhido. Exportações grandes podem exceder limites de hospedagem; o gerador Python executado localmente evita depender da duração de uma função na Vercel.

## Arquivos de dados

Guarde exportações em `entradas/` e relatórios em `relatorios-gerados/`. Essas pastas, `.env`, `.venv`, PDFs e `config-relatorio.json` estão ignorados pelo Git. Não envie dados reais, credenciais ou relatórios pessoais para o repositório público.

Este projeto é uma reconstrução de consulta e recuperação. Ele não reproduz regras de negócio desconhecidas do sistema antigo.
