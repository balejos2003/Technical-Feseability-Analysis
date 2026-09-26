# Technical Feasibility Analysis

Ferramenta interativa para avaliar a viabilidade técnica de uma mudança solicitada
pelo Desenvolvedor a partir de uma base de código.

## Estado atual

O projeto está em implementação incremental. O fluxo e os contratos estão documentados
em [specs/001-technical-feasibility-analysis/](specs/001-technical-feasibility-analysis/).

## Como utilizar

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

Depois de gerar o relatório, o Desenvolvedor deve confirmar que o revisou e que entende
que o resultado é consultivo. Em seguida, pode escolher se deseja manter o resultado no
histórico. A cópia Markdown só é salva quando a opção de salvar relatório externo e a
retenção do resultado são confirmadas.

Para consultar análises mantidas, escolha `2. Consult analysis history`:

```text
1. List recent analyses
2. Search analyses
3. Open an analysis by identifier
4. Return to main menu
```

A listagem e a busca mostram somente avaliações concluídas do principal atual. Um
identificador inexistente ou pertencente a outro principal é apresentado como
indisponível, sem revelar se o registro existe. O histórico não possui operação de
exclusão pela interface ou pela camada de armazenamento.

## Dados externos

O diretório de dados da aplicação é configurado por `FEASIBILITY_DATA_DIR`. Quando a
variável não é definida, o caminho padrão no macOS é:

```text
~/Library/Application Support/technical-feasibility-analysis/
```

Nesse diretório ficam:

```text
history.sqlite3
reports/<assessment-id>.md
```

O banco e os relatórios devem permanecer fora da base de código analisada. A aplicação
valida essa condição antes da descoberta e rejeita caminhos de saída que estejam dentro
do repositório avaliado.

## Limites de entrada

- A entrada deve ser um diretório; um arquivo individual não é aceito como raiz.
- São analisados arquivos de texto UTF-8 legíveis. Arquivos binários ou não decodificáveis
  são registrados como problemas de descoberta.
- Links simbólicos são ignorados por padrão.
- Arquivos acima de 1 MB são excluídos por padrão.
- `.git`, `.hg`, `.svn`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist` e `build`
  são excluídos por padrão. O diretório `.specify` não é excluído e pode fazer parte do
  contexto analisado.
- O contexto enviado à IA é limitado a 100.000 caracteres por análise. Arquivos que não
  couberem nesse limite são marcados como truncados e não devem ser citados como se
  estivessem integralmente disponíveis.
- A IA interpreta a estrutura diretamente a partir do texto fornecido; a ferramenta não
  exige tree-sitter nem outro parser específico de linguagem.

## Formato do relatório

O relatório é Markdown e contém seções estáveis para navegação:

```text
# Technical Feasibility Assessment
## Request
## Conclusion
## Evaluated Scope
## Findings
## Estimates
## Suggestions
## Risks and Limitations
## Assumptions
## Unresolved Questions
## Developer Review
```

Cada achado material deve apontar para evidência verificável. Para código, a referência
inclui caminho relativo, intervalo inclusivo de linhas, trecho delimitado, hash SHA-256,
tipo de evidência e relevância. Evidências não baseadas em código identificam se são
contexto do usuário, suposição, limitação ou conflito e explicam por que não há trecho
de fonte.

Estimativas são separadas de fatos e interpretações e precisam de rótulo, valor e base.
Uma estimativa incompleta é omitida e sua ausência aparece como limitação; uma lista
vazia de estimativas é válida. Sugestões, riscos, limitações e perguntas não resolvidas
também permanecem separados no relatório.

## Princípios operacionais

- A base de código analisada é somente leitura.
- A aplicação não cria, altera ou remove arquivos dentro da base analisada.
- Relatórios e histórico SQLite são armazenados fora da base analisada por padrão.
- A IA apresenta fatos, interpretações, estimativas, sugestões, riscos e limitações
  separadamente.
- O Desenvolvedor revisa o resultado e mantém a decisão final.
- Nenhuma análise aplica alterações na base de código.

## Ambiente

- Python 3.11 ou superior.
- Dependências e entry point definidos em [pyproject.toml](pyproject.toml).
- O diretório de dados pode ser configurado com `FEASIBILITY_DATA_DIR`.
- A análise real usa `OPENAI_API_KEY`; opcionalmente, `OPENAI_MODEL` define o modelo
  usado, com `gpt-4o-mini` como padrão.

Antes de iniciar uma análise, configure a credencial no ambiente:

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_MODEL="gpt-4o-mini"
PYTHONPATH=src python -m feasibility
```

Sem `OPENAI_API_KEY`, o programa preserva a base analisada e informa que o provider
não está configurado, sem criar um relatório ou registro incompleto.

## Validação

O fluxo de validação executável está descrito em
[quickstart.md](specs/001-technical-feasibility-analysis/quickstart.md). A implementação
não deve ser considerada completa enquanto as tarefas em
[tasks.md](specs/001-technical-feasibility-analysis/tasks.md) permanecerem pendentes.
