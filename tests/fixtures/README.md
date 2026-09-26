# Test Fixtures

- `mixed-repo/`: arquivos Python, JavaScript e TypeScript legíveis, caso de sintaxe ambígua, diretório `node_modules/` excluído e sentinela para verificações de leitura.
- `unsupported-repo/`: arquivo Python legível e arquivo `.xyz` fora do escopo quando `allowed_extensions=("py",)` é usado.
- Arquivos binários com bytes NUL devem ser criados pelo teste ou cenário que exercita a classificação `unreadable`, pois não são representados como texto neste conjunto versionado.
