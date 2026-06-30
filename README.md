# 🏆 Copa do Mundo 2026 — Painel & Simulador

Aplicação **Python + Streamlit** que substitui o painel HTML estático da Copa por
um sistema dinâmico: classificação calculada automaticamente, busca de resultados
por API e um **simulador "e-se"** que mostra o efeito de placares hipotéticos na
tabela dos grupos e no chaveamento do mata-mata.

## Como rodar

```bash
cd copa_2026
pip install -r requirements.txt
streamlit run app.py        # painel interativo
uvicorn api:app --reload    # API REST (http://localhost:8000)
```

O painel e a API compartilham o **mesmo estado** (`data/results.json`): o que
for salvo num lado aparece no outro.

## API REST

Camada HTTP/JSON (`api.py`, FastAPI) para consultar os resultados de fora do
painel. Sobe com `uvicorn api:app --reload` e traz documentação interativa
gerada automaticamente:

- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc
- **OpenAPI** → http://localhost:8000/openapi.json

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/health` | Disponibilidade da API. |
| `GET` | `/api/tournament` | Visão geral: fase, progresso e campeão. |
| `GET` | `/api/teams` · `/api/teams/{code}` | Seleções (filtro `?group=`) e detalhe. |
| `GET` | `/api/groups` · `/api/groups/{group}` | Grupos com seleções e classificação. |
| `GET` | `/api/matches` | Partidas da fase de grupos (filtros `group`, `matchday`, `status`, `team`). |
| `GET` | `/api/matches/{id}` | Detalhe de uma partida. |
| `GET` | `/api/standings` · `/api/standings/{group}` | Classificação de todos / de um grupo. |
| `GET` | `/api/standings/third-placed` | Ranking dos 3º colocados (8 melhores). |
| `GET` | `/api/knockout` | Mata-mata 73–104 (filtro `?stage=`). |
| `GET` | `/api/knockout/{no}` · `/api/knockout/champion` | Jogo do mata-mata / campeão. |
| `PUT` | `/api/matches/{id}/result` | Registra placar de grupo. |
| `PUT` | `/api/knockout/{no}/result` | Registra placar de mata-mata. |
| `DELETE` | `/api/matches/{id}/result` · `/api/knockout/{no}/result` | Limpa um placar. |
| `POST` | `/api/refresh` | Importa resultados das APIs externas (sem sobrescrever o manual). |
| `DELETE` | `/api/results` | Apaga todos os resultados. |
| `POST` | `/api/simulate` | Simulação "e-se": aplica placares hipotéticos **sem persistir** e devolve tabela + mata-mata projetados. |

```bash
# exemplos
curl localhost:8000/api/standings/C
curl localhost:8000/api/knockout?stage=R32
curl -X PUT localhost:8000/api/matches/C1/result -H 'Content-Type: application/json' \
     -d '{"home_goals": 2, "away_goals": 1}'
curl -X POST localhost:8000/api/simulate -H 'Content-Type: application/json' \
     -d '{"groups": [{"match_id": "C1", "home_goals": 3, "away_goals": 0}]}'
```

A importação automática (`POST /api/refresh`) funciona **sem chave** (usa a API
pública da ESPN). As variáveis de ambiente `FOOTBALL_DATA_TOKEN` e
`API_FOOTBALL_KEY`, se definidas, têm prioridade.

## As 5 abas

| Aba | O que faz |
|-----|-----------|
| 🏆 **Andamento** | Status da competição, resultados recentes e próximos confrontos. |
| 📊 **Classificação** | Tabela ao vivo dos 12 grupos (top-2 🟢, melhores 3º 🟡) + ranking dos 3º colocados. |
| 🔀 **Mata-mata** | Chaveamento dos dezesseis-avos à final, resolvido conforme os grupos terminam. |
| 🎮 **Simulador** | Simula jogos **ainda não disputados** e recalcula tabela + chaveamento. Sensível à fase. |
| ⚙️ **Dados/Admin** | Atualizar da API, editor manual de placares (grupos e mata-mata), limpar tudo. |

## Comportamento progressivo

O sistema se adapta à fase real do torneio:

- **Fase de grupos em andamento** → simulam-se os jogos de grupo restantes; o
  mata-mata aparece como **projeção**. Jogos já disputados ficam **travados**.
- **Fase de grupos concluída** → o chaveamento é semeado com os classificados
  **reais** e a simulação passa a ser do mata-mata (dezesseis-avos → final).

## Dados (camada híbrida)

1. **Semente real** — sorteio oficial de 05/12/2025 (48 seleções, 12 grupos A–L)
   e calendário/sedes aproximados, em `tournament_data.py`.
2. **API automática** — busca os placares e funciona **sem nenhuma chave**:
   a fonte padrão é a **API pública da ESPN** (`fifa.world`, keyless). Se você
   configurar `football-data.org` e/ou `API-Football` em `.streamlit/secrets.toml`
   (veja `secrets.toml.example`), elas têm prioridade. A ordem de tentativa é
   football-data.org → API-Football → ESPN.
3. **Override manual** — placares digitados no Admin têm **prioridade** e
   persistem em `data/results.json`.

## Tabela do Anexo C (3º colocados)

As 8 vagas dos melhores 3º colocados seguem a tabela oficial da FIFA (495
combinações), já gerada em `data/thirdplace_allocation.json`. Para regenerá-la:

```bash
python scripts/build_thirdplace_table.py
```

Sem o arquivo, o app usa um emparelhamento de reserva que respeita os grupos
candidatos de cada vaga.

## Estrutura

```
app.py            # interface Streamlit (5 abas)
api.py            # API REST (FastAPI) — consulta/escrita de resultados
api_schemas.py    # modelos Pydantic (contratos de entrada/saída da API)
data_model.py     # dataclasses Team / Match / StandingRow
tournament_data.py# semente real: grupos, fixtures, bracket, Anexo C clusters
standings.py      # tabela de grupo + desempates FIFA + ranking dos 3º
knockout.py       # monta dezesseis-avos e propaga até a final
data_sources.py   # adapters das APIs (normalização + resolução de nomes)
state.py          # estado canônico (semente ← API ← manual) + persistência
simulator.py      # overlay de simulação sobre o estado real
branding.py / tooltips.py
scripts/build_thirdplace_table.py   # gera a tabela do Anexo C
_test_logic.py / _test_flow.py / _test_ui.py / _test_api.py   # testes
```

## Testes

```bash
python _test_logic.py   # classificação, desempates, mata-mata, Anexo C
python _test_flow.py    # merge da API, prioridade manual, transição de fase
python _test_ui.py      # smoke test da interface (streamlit.testing)
python _test_api.py     # endpoints da API REST (TestClient, sem subir servidor)
```

## Limitações conhecidas

- **Fair-play** não é critério de desempate (as APIs gratuitas não trazem
  cartões); usa-se o ranking FIFA no lugar.
- **Ranking FIFA**, **datas** e **sedes** são aproximados e editáveis em
  `tournament_data.py`.
- As APIs gratuitas podem demorar a popular um torneio novo — por isso o
  override manual é o caminho confiável.
