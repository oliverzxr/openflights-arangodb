# Validação da rodada de 24/11/2026

A aplicação foi testada em Windows com Python 3.14.6, contra um ArangoDB 3.12.13 `SINGLE` em Linux x86-64 temporário no QEMU. A VM iniciou os binários e o entrypoint da imagem oficial `arangodb:3.12.13`. A consulta de versão identifica o binário como `enterprise`. O endpoint de licença reportou limite de 100 GiB e nenhuma chave comercial aplicada, o que confirma a execução em modo Community. [Documentação do estado da licença](https://docs.arango.ai/arangodb/3.12/operations/administration/license-management/).

| Verificação | Resultado |
|---|---|
| Download em diretório vazio | Três arquivos baixados. SHA-256 conforme a revisão fixa |
| Preparação | 7.698 aeroportos, 6.161 companhias e 66.759 rotas após o tratamento |
| Carga inicial e reexecução | 80.618 documentos criados na carga inicial. Na segunda, zero novos e todos os 80.618 ignorados por chave. Comparação integral após ambas |
| AQL | Seis consultas executadas e confrontadas com a expectativa. Travessias, grau e verificações descritos no [catálogo](queries.md) |
| Índices | `EXPLAIN` do filtro de aeroportos usou o índice persistente `[country, iata]`. A API rejeitou uma aresta com identidade de negócio duplicada |
| Integridade | Zero extremos inválidos, laços ou identidades duplicadas na carga. A API gerenciada rejeitou referência a vértice inexistente |
| CRUD | As cinco etapas executaram pela CLI e pelo editor da Web UI no Edge. A amostra original e o banco principal passaram na comparação de conteúdo |
| Testes | 10 aprovados, incluindo oito unitários e dois de integração contra o servidor real. Incluem ausência de arquivo, duplicata, extremo inválido, erro de lote e consulta vazia |
| Backup | Dump e restauração em `openflights_restore_check` com 11 coleções, incluindo as de sistema. Conteúdo dos dados, os dois índices, o grafo e seus sete destinos de MCZ conferidos |
| Compose | Configuração aceita por `docker compose config --quiet` com Compose v5.8.0. O Docker Engine não estava disponível neste Windows |

O [registro em JSON](evidence.json) preserva resultados da execução e amostras identificadas. O [relatório do Python](python-results.json) traz as medidas calculadas na transformação. A carga gerada, os CSV e o dump ficam fora do Git.
