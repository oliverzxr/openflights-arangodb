# Catálogo AQL

Execute as consultas de leitura em `openflights`. Na Web UI, use **Queries**, cole o arquivo e insira os parâmetros como JSON. A CLI escolhe os parâmetros padrão. Use `python -m openflights_graph query 03_two_hops_only` como exemplo.

| Nível e arquivo | Objetivo e como funciona | Resultado esperado e interpretação |
|---|---|---|
| 1 · [01_brazil_airports](../queries/analysis/01_brazil_airports.aql) | `FILTER` por país e limite inferior para IATA. Ordena e limita a 10 entradas | Aeroportos com código começando a partir de S na ordem do índice. Isola a busca documental antes das travessias |
| 2 · [02_direct_destinations](../queries/analysis/02_direct_destinations.aql) | Travessia `OUTBOUND` de uma aresta e agrupamento por aeroporto | Sete destinos de MCZ. `carrierEdges` mede listagens por companhia para o par dirigido |
| 3 · [03_two_hops_only](../queries/analysis/03_two_hops_only.aql) | Caminhos simples de exatamente duas arestas. Exclui destinos diretos e conta intermediários únicos | 114 destinos adicionais. LIS, CNF, FOR e NAT aparecem com seis intermediários. A contagem descreve alternativas estruturais |
| 3 · [04_top_hubs](../queries/analysis/04_top_hubs.aql) | Primeiro agrupa por par ordenado, depois conta destinos por origem | FRA, CDG e AMS nas três primeiras posições. Mede diversidade de destinos, independente do número de companhias por par |
| 4 · [05_shortest_path](../queries/analysis/05_shortest_path.aql) | Busca um caminho dirigido sem pesos entre MCZ e LIS | Três vértices e duas arestas. O intermediário pode variar em caso de empate. O custo é o número de trechos |
| 4 · [06_integrity](../queries/analysis/06_integrity.aql) | Conta documentos e procura extremos ausentes, referências inválidas, laços e identidades repetidas | 7.698 aeroportos, 6.161 companhias, 66.759 rotas. Zero violações após a carga |

| Consulta | Bind variables |
|---|---|
| 01 | `{"country":"Brazil","iata_min":"S"}` |
| 02, 03 | `{"origin":"airports/2590"}` |
| 05 | `{"origin":"airports/2590","destination":"airports/1638"}` |
| 04, 06 | `{}` |

## Execução no ArangoDB 3.12.13

| Consulta | Resultado observado |
|---|---|
| 01 | 10 linhas. As três primeiras foram SDU, SFK e SJK. Com um país inexistente, a resposta foi `[]` |
| 02 | AJU (1), BSB (3), GIG (2), GRU (3), REC (1), SSA (2) e VCP (1). Os números entre parênteses contam arestas de companhia |
| 03 | 114 linhas. LIS, CNF, FOR e NAT aparecem com seis intermediários distintos cada |
| 04 | 10 origens. FRA (239), CDG (237) e AMS (232) lideraram |
| 05 | MCZ, VCP e LIS, nessa ordem. O resultado prova um caminho de duas arestas no recorte |
| 06 | 7.698 aeroportos, 6.161 companhias e 66.759 rotas. Zero rotas inválidas e zero identidades duplicadas |

O registro guarda totais e amostras identificadas. Para salvar todas as linhas de uma nova execução, rode `python -m openflights_graph check-queries --output data/aql-results.json`. [Saída da rodada](evidence.json).

## CRUD no banco de ensaio

A amostra de `openflights_demo` contém MCZ e GRU, as rotas reais entre os dois e seus documentos de companhia disponíveis. As consultas de escrita usam chaves reservadas para a sessão. Os comandos passam por uma sequência de comparação e auditoria do estado final.

| Arquivo | Operação e propósito | Resposta esperada |
|---|---|---|
| [01_create](../queries/crud/01_create.aql) | Confere os dois aeroportos reais. Insere um terminal marcado e uma aresta de GRU ao terminal | Os dois documentos novos com `demo: true` |
| [02_read](../queries/crud/02_read.aql) | Percorre a aresta a partir de GRU e filtra pela marca e chaves | Nome, estágio e chave de aresta. Uma linha enquanto o par existir |
| [03_update](../queries/crud/03_update.aql) | Altera nome e estágio com a revisão do documento usada na escrita | Nome anterior, nome revisado e estágio `updated` |
| [04_delete](../queries/crud/04_delete.aql) | Confere vínculo e revisões. Remove a aresta e o terminal na mesma consulta | Chaves de aeroporto e aresta removidas |
| [05_verify](../queries/crud/05_verify.aql) | Busca as chaves de ensaio e os dois aeroportos originais | Dois nulos e as siglas MCZ e GRU |

A amostra efetivamente carregada teve dois aeroportos, três companhias e seis rotas. O CRUD retornou a criação dos dois registros, o estágio inicial nulo, o estágio `updated`, as chaves removidas e a confirmação final. A CLI e a Web UI executaram as cinco consultas com sucesso no banco de ensaio. [Saídas registradas](evidence.json).
