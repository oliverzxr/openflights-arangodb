# KDD da malha histórica

## Seleção e transformação

A pergunta parte de Maceió e combina alcance em dois trechos com a concentração do grau de saída. Selecionamos aeroportos, companhias e rotas do OpenFlights para representar aeroportos como vértices e ofertas de rota como arestas dirigidas. A documentação da fonte descreve um catálogo de aeroportos e companhias e uma base de rotas, com fornecedor de rotas descontinuado em junho de 2014. As três tabelas da revisão fixa podem representar momentos diferentes. [OpenFlights](https://openflights.org/data).

O ETL confere o SHA-256, lê CSV respeitando aspas e UTF-8, transforma marcadores de ausência em nulos e usa os IDs de aeroporto da fonte. Rotas com aeroportos ausentes ou desconhecidos são excluídas sem preenchimento por IATA. Mantêm-se apenas rotas de zero paradas com extremos distintos. O catálogo de companhias enriquece as arestas quando há identificação correspondente. O valor de companhia da fonte permanece representado mesmo quando a referência auxiliar fica nula.

| Entrada | Registros originais | Retidos | Conciliação |
|---|---:|---:|---|
| Aeroportos | 7.698 | 7.698 | Nenhuma exclusão |
| Companhias | 6.162 | 6.161 | 1 ID não positivo |
| Rotas | 67.663 | 66.759 | 423 IDs de aeroporto ausentes, 469 fora do catálogo, 11 fora do filtro de zero paradas, 1 laço |

As categorias de descarte são mutuamente exclusivas pela ordem das regras no código. Foram 904 exclusões de rota, cerca de 1,34%. O ETL admite fusão de duplicatas por origem, destino e companhia, mas contou zero fusões nessa revisão. Há 455 arestas sem vínculo com documento de companhia.

## Exploração e interpretação

| Métrica | Resultado do Python |
|---|---:|
| Vértices e arestas | 7.698 e 66.759 |
| Aeroportos com pelo menos uma aresta incidente | 3.214 |
| Aeroportos isolados no recorte | 4.484 |
| Pares ordenados distintos | 36.906 |
| Pares ordenados com múltiplas companhias | 16.275 |
| Pares ordenados cuja direção inversa também existe | 36.096 |
| Arestas somente com codeshare | 14.474 |
| Arestas somente sem codeshare | 52.285 |

A correspondência entre catálogo e rotas explica por que o número de vértices excede o de aeroportos conectados. Uma exclusão de dados também pode afetar a existência de caminhos. Grau de saída conta aeroportos de destino distintos, então uma conexão com várias companhias conta uma vez. O topo medido foi FRA (239), CDG (237), AMS (232), ISL (224) e ATL (217). O código ISL é o da tabela auxiliar para o vértice histórico, que tem ID 1701. O ranking segue o ID persistente e a grafia atual do CSV, sujeitos à diferença temporal entre as tabelas.

A partir de MCZ, AJU, BSB, GIG, GRU, REC, SSA e VCP aparecem em um trecho. Há 114 destinos adicionais em dois trechos, excluídos o próprio MCZ e os destinos diretos. Lisboa (LIS), Belo Horizonte (CNF), Fortaleza (FOR) e Natal (NAT) têm seis aeroportos intermediários distintos cada. Contar aeroportos intermediários reduz a supercontagem causada por arestas paralelas. O filtro usa conectividade da rede e ignora compatibilidade de horários e venda conjunta.

As consultas AQL confirmaram os resultados em ArangoDB. A busca retornou MCZ, VCP e LIS como um caminho mínimo. A auditoria AQL encontrou zero rotas inválidas e zero identidades duplicadas. [Evidência de execução](evidence.json).

## Reexecução

`python -m openflights_graph analyze --output data/analysis.json` calcula estas medidas. A análise em Python opera sobre o snapshot e confere as consultas AQL em um caminho independente de execução. [Saída integral do Python](python-results.json) · [Consultas e parâmetros](queries.md).
