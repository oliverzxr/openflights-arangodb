# Instalação e reprodução

Use Python 3.10+ no computador que executa a carga e o ArangoDB Community 3.12.13 em uma única instância. O Python usa apenas a biblioteca padrão. Os comandos foram escritos para PowerShell. Em Bash, use `export VAR=valor` onde o exemplo usar `$env:VAR` e o nome local do Python, em geral `python3`.

## Windows com Docker Desktop já disponível

1. Inicie o Docker Desktop em modo de contêineres Linux. Na raiz do projeto, confira `python --version`, `docker version` e `docker compose version`.
2. Crie uma credencial local com o comando abaixo. Ele falha se `.env` já existir. Consulte `.env.example` para as chaves aceitas e leia a senha local apenas para fazer login.

   ```powershell
   python -c "from pathlib import Path; import secrets; p=Path('.env'); p.open('x',encoding='utf-8').write('ARANGO_ROOT_PASSWORD='+secrets.token_hex(24)+'\nARANGO_PORT=8529\n')"
   docker compose config --quiet
   docker compose up -d --wait
   python -m openflights_graph version
   ```

3. Abra [a Web UI local](http://localhost:8529), faça login com `root` e selecione `_system` antes da carga. Depois da carga, selecione `openflights`. O Compose publica apenas em `127.0.0.1`. Se ajustar `ARANGO_PORT`, use a porta configurada no navegador.
4. A carga cria o banco, suas três coleções, os índices e o grafo. Execute os comandos na ordem abaixo.

   ```powershell
   python -m openflights_graph download
   python -m openflights_graph prepare
   python -m openflights_graph import
   python -m openflights_graph verify
   python -m openflights_graph analyze
   python -m openflights_graph check-queries --output data/aql-results.json
   python -m unittest discover -s tests -v
   $env:ARANGO_INTEGRATION='1'
   python -m unittest discover -s tests -v
   Remove-Item Env:ARANGO_INTEGRATION
   ```

5. Prepare e execute a demonstração. A execução completa compara o estado final do banco de ensaio com a amostra de entrada.

   ```powershell
   python -m openflights_graph demo-seed
   python -m openflights_graph demo --output data/crud-results.json
   ```

No editor **Queries** da Web UI, cole o conteúdo de um arquivo em `queries/analysis`, informe os parâmetros do [catálogo](queries.md) e use **Execute**. Em **Graphs**, selecione `flight_network`. Para pesquisar pela CLI use, por exemplo, `python -m openflights_graph query 02_direct_destinations`. O [catálogo de consultas](queries.md#crud-no-banco-de-ensaio) descreve as operações de escrita no banco `openflights_demo`.

## Alternativa sem Docker

O fornecedor disponibiliza pacotes para Linux `x86_64` e `ARM64`. A série 3.12 não tem instalador nativo para Windows. Use um Linux existente, como um computador da equipe, uma VM já disponível ou um WSL já configurado. O tutorial de Linux serve tanto para executar a carga dentro desse ambiente quanto para configurar a instância que o Windows acessará. [Downloads do fabricante](https://arango.ai/downloads/) · [Plataformas e requisitos](https://docs.arango.ai/arangodb/3.12/operations/installation/).

1. Selecione o pacote oficial 3.12.13 para o Linux e a arquitetura disponíveis. Instale-o segundo as instruções do fornecedor e configure uma senha root. Em Debian ou Ubuntu compatível, o comando para um pacote local oficial é `sudo apt install ./<arquivo-baixado>.deb`. Se o instalador não iniciar o serviço, use `sudo systemctl start arangodb3` em um ambiente que já usa systemd. Confirme o serviço com `systemctl status arangodb3`.
2. Preserve a autenticação e o bind local `tcp://127.0.0.1:8529`. No repositório, configure `.env` com a senha real desse servidor. Para uma instância Linux em outra máquina com SSH configurado, abra um túnel `ssh -N -L 8529:127.0.0.1:8529 usuario@servidor` e execute os comandos de carga em outro terminal.
3. O cliente aceita `ARANGO_URL`, `ARANGO_USER` e `ARANGO_PASSWORD` para um servidor configurado. HTTP é aceito em loopback. Use HTTPS com certificado válido fora de loopback. A criação inicial requer uma conta autorizada a criar banco, coleções e índices. Para uso recorrente, uma conta com acesso somente de leitura a `openflights` basta para rodar as análises.

## Backup lógico e restauração

Use estes comandos a partir do Compose (ou chame os mesmos binários diretamente no servidor Linux). Os binários pedem a senha interativamente. Feche operações de escrita durante a verificação e use um diretório de dump e um banco de destino novos. O exemplo inclui `_graphs` para preservar a definição do grafo.

```powershell
docker compose exec arangodb arangodump --server.database openflights --server.username root --output-directory /tmp/openflights-dump --include-system-collections true
New-Item -ItemType Directory -Force backups | Out-Null
docker compose cp arangodb:/tmp/openflights-dump ./backups/
docker compose exec arangodb arangorestore --server.database openflights_restore_check --server.username root --input-directory /tmp/openflights-dump --include-system-collections true --create-database true --overwrite false
python -m openflights_graph verify --database openflights_restore_check
```

Confira na Web UI do banco restaurado a presença de `flight_network` e execute `02_direct_destinations.aql` com `origin = airports/2590`. Para mover um dump a outra instância, copie a pasta inteira e execute `arangorestore` perto do servidor de destino. Se uma restauração falhar no meio, investigue o erro antes de repetir em outro banco novo. Dumps contêm dados e metadados. Controle o acesso a eles e verifique a restauração antes de depender de uma cópia. [arangodump](https://docs.arango.ai/arangodb/3.12/components/tools/arangodump/examples/) · [arangorestore](https://docs.arango.ai/arangodb/3.12/components/tools/arangorestore/examples/).

## Falhas comuns

| Sintoma | Diagnóstico e recuperação |
|---|---|
| Engine Docker indisponível | Confira `docker version`, o modo Linux e `docker compose logs arangodb`. Com uma instalação Linux existente, use a alternativa acima. |
| Porta 8529 ocupada | Ajuste `ARANGO_PORT` em `.env` e use a mesma porta na UI e no cliente. |
| 401 após trocar o arquivo de configuração | Use a senha configurada no volume durante seu primeiro boot. A variável de inicialização não altera por si só a senha persistida. |
| Download bloqueado ou SHA-256 divergente | Baixe os três arquivos da revisão fixa em outra rede, guarde em `data/raw/` e rode `download` para validá-los. Separe o arquivo incorreto antes de repetir. |
| Erro parcial na carga | Corrija a causa e execute `import` novamente. Cada lote tem seu próprio resultado. A verificação do conteúdo detecta divergências em registros já existentes. Investigue qualquer diferença antes de modificar a base. |
| AQL retorna vazio | Confira banco, bind variables, identificador completo e direção. O filtro inexistente é um caso automatizado. |
| Ensaio anterior incompleto | Se o par de ensaio existir, rode `demo-step 04_delete` no banco de ensaio e depois `demo-step 05_verify`. Se apenas um documento existir, inspecione sua origem e integridade pela UI antes de removê-lo. |

Para interromper temporariamente use `docker compose stop`. Para remover os contêineres e a rede do projeto mantendo o volume, use `docker compose down`. Em Linux, encerre apenas a instância separada usada no exercício, conforme a forma de instalação.
