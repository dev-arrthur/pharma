# Como gerar os relatórios preenchidos

O gerador preenche cada item com as respostas que encontrar no banco ou nos arquivos selecionados. Ele precisa dessa origem para mostrar nomes, quantidades e valores reais. Um arquivo contendo apenas o código do programa não contém as respostas da farmácia.

## Caminho mais simples

Abra **GERAR_PDF.cmd** e escolha uma opção:

| Opção | Quando usar | O que é necessário |
| --- | --- | --- |
| **1 - MongoDB** | Os registros continuam no banco original. | Conexão `MONGODB_URI` e, preferencialmente, nome `MONGODB_DB` no `.env`. |
| **2 - Arquivo** | Você já exportou uma categoria. | Um arquivo JSON, JSONL/NDJSON ou CSV. O programa abre uma janela para escolhê-lo. |
| **3 - Pasta** | Você tem várias categorias exportadas. | Uma pasta contendo os arquivos. O programa abre uma janela para escolhê-la. |

Nas opções **2** e **3**, você não precisa informar senha do MongoDB, acessar a Vercel ou instalar o painel Node.js.

Ao terminar, serão salvos:

- **relatorios-gerados/Maximum-Farmacia-Relatorio.pdf**: documento para abrir, imprimir e compartilhar.
- **relatorios-gerados/Maximum-Farmacia-Relatorio.html**: versão para abrir no navegador, com os mesmos dados extraídos.

O HTML é independente do sistema e pode ser consultado sem conexão com o banco. O arquivo contém uma cópia dos dados no momento da geração; ele não se atualiza sozinho.

## Como os itens aparecem

Cada registro é identificado e seus campos são apresentados em sequência. Informações dentro de listas mantêm a posição do item. Por exemplo, uma resposta armazenada em `itens[2].resposta` aparece associada ao item correspondente, em vez de se misturar às respostas de outros itens.

O relatório distingue situações diferentes:

| Valor na origem | Interpretação |
| --- | --- |
| `0` | Zero registrado; não significa campo vazio. |
| `false` | Resposta negativa; não significa ausência de resposta. |
| `null` | Valor não informado na origem. |
| Texto vazio | Campo presente, mas sem texto preenchido. |
| Lista vazia | Nenhum item registrado naquela lista. |
| Campo ausente | O programa não inventa uma resposta para um campo inexistente. |

Campos que guardam credenciais reconhecidas são omitidos. Se a origem contém somente um identificador, o relatório preserva esse identificador até que exista um vínculo configurado com a categoria correta.

## Formatos de entrada

O gerador aceita:

- **JSON com uma lista de documentos**, como a exportação de uma coleção.
- **JSON com um único documento**.
- **JSONL ou NDJSON**, com um documento por linha.
- **CSV comum**, com cabeçalho e colunas.
- **CSV exportado pelo painel anterior**, com a coluna `documento_json`.
- **JSON consolidado**, com as propriedades `database` e `collections`; cada nome em `collections` contém uma lista de documentos.

Para uma pasta, prefira um arquivo por categoria, como `funcionarios.json`, `compras.json` e `itens.json`. Preserve os identificadores que relacionam esses arquivos. Arquivos de metadados do MongoDB (`*.metadata.json`) não são documentos da coleção.

Uma exportação de página da API, com `rows` e `total`, pode conter apenas parte dos registros. Quando o total declarado é maior que a quantidade fornecida, o resultado deve ser tratado como parcial. Para um relatório geral, use a exportação completa da categoria, e não apenas a página visível na tela.

Um arquivo ilegível ou uma leitura interrompida aparece como pendência. O programa não substitui esse conteúdo por números inventados.

## Moeda e identificação das pessoas ou itens

Campos diferentes podem ter nomes iguais e significados diferentes. Um `total` pode indicar quantidade de itens, valor em reais ou valor em centavos. Por isso, a conversão monetária exige uma configuração explícita.

1. Copie `config-relatorio.example.json` para `config-relatorio.json`.
2. Ajuste os nomes da categoria e dos campos para corresponder à sua origem.
3. Execute o comando abaixo na pasta do projeto:

```bash
python gerar_relatorio.py --entrada "entradas" --config "config-relatorio.json"
```

A seção `currency_fields` indica quais campos são monetários, sua unidade e o separador decimal. A seção `references` informa de qual categoria e campo deve vir o nome relacionado a um identificador. Os nomes de campos presentes no arquivo de exemplo são ilustrativos; não confirmam a estrutura do seu banco.

O menu padrão usa a leitura sem mapeamentos personalizados. Para aplicar seu arquivo de configuração, use o comando com `--config` acima. Valores não mapeados continuam preservados como registrados. O programa não soma campos de categorias diferentes como se representassem um único saldo a receber.

## O que fazer se houver pendências

| Mensagem ou situação | Próximo passo |
| --- | --- |
| Banco não configurado | Preencha `MONGODB_URI` no `.env` ou escolha um arquivo exportado. |
| Falha de conexão | Confira a credencial de leitura, o nome da base e a autorização do IP do computador. |
| Nenhum registro válido | Confirme que escolheu uma exportação dos dados, não arquivos do programa. |
| Relatório parcial | Leia os avisos no início do documento e repita a exportação da categoria afetada. |
| Resposta não informada | Confira o campo na origem. O gerador não tem como descobrir uma resposta que não foi registrada. |
| Aparece um identificador no lugar do nome | Forneça também a categoria de cadastro e configure o vínculo em `references`. |

Ao ocorrer um erro, o inicializador não abre um PDF de execução anterior como se fosse novo. Um resultado parcial é aberto com aviso para conferência.

## Compartilhar

Envie o PDF ou o HTML gerado à pessoa autorizada a conferir os registros. Não é necessário encaminhar o programa, o `.env` ou a conexão do banco. O relatório pode conter informações pessoais; omitir senhas não remove os demais dados do documento.
