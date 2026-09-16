# Technical Feasibility Analysis

Ferramenta interativa para avaliar a viabilidade técnica de uma mudança solicitada
pelo Desenvolvedor a partir de uma base de código.

## Estado atual

O projeto está em implementação incremental. O fluxo e os contratos estão documentados
em [specs/001-technical-feasibility-analysis/](specs/001-technical-feasibility-analysis/).

## Como será utilizado

A aplicação será iniciada como um script Python interativo. O Desenvolvedor responderá
às perguntas com `input()`, sem argumentos ou flags de linha de comando:

```text
1. Analyze a change
2. Consult analysis history
3. Exit
```

Ao escolher a análise, a aplicação solicitará:

```text
Codebase path: <caminho da base de código>
Requested change: <mudança desejada>
Optional additional context: <contexto opcional>
Save report outside the codebase? <yes/no>
```

O relatório será apresentado em linguagem natural, com seções navegáveis e referências
explícitas para os achados. Cada evidência de código deverá indicar caminho relativo,
linhas, trecho, hash do arquivo e relevância.

## Princípios operacionais

- A base de código analisada é somente leitura.
- A aplicação não cria, altera ou remove arquivos dentro da base analisada.
- Relatórios e histórico SQLite são armazenados fora da base analisada por padrão.
- A IA apresenta fatos, interpretações, estimativas, sugestões, riscos e limitações
  separadamente.
- O Desenvolvedor revisa o resultado e mantém a decisão final.

## Ambiente

- Python 3.11 ou superior.
- Dependências e entry point definidos em [pyproject.toml](pyproject.toml).
- O diretório de dados pode ser configurado com `FEASIBILITY_DATA_DIR`.

## Validação

O fluxo de validação executável está descrito em
[quickstart.md](specs/001-technical-feasibility-analysis/quickstart.md). A implementação
não deve ser considerada completa enquanto as tarefas em
[tasks.md](specs/001-technical-feasibility-analysis/tasks.md) permanecerem pendentes.
