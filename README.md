# 🏆 Copa do Mundo 2026 — Painel & Simulador

Aplicação **Python + Streamlit** que substitui o painel HTML estático da Copa por
um sistema dinâmico: classificação calculada automaticamente, busca de resultados
por API e um **simulador "e-se"** que mostra o efeito de placares hipotéticos na
tabela dos grupos e no chaveamento do mata-mata.

## Como rodar

```bash
cd copa_2026
pip install -r requirements.txt
streamlit run app.py
```

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
2. **API automática** (opcional) — `football-data.org` (primária) e `API-Football`
   (reserva). Configure as chaves em `.streamlit/secrets.toml`
   (veja `secrets.toml.example`). Sem chaves, o app funciona 100% no modo manual.
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
data_model.py     # dataclasses Team / Match / StandingRow
tournament_data.py# semente real: grupos, fixtures, bracket, Anexo C clusters
standings.py      # tabela de grupo + desempates FIFA + ranking dos 3º
knockout.py       # monta dezesseis-avos e propaga até a final
data_sources.py   # adapters das APIs (normalização + resolução de nomes)
state.py          # estado canônico (semente ← API ← manual) + persistência
simulator.py      # overlay de simulação sobre o estado real
branding.py / tooltips.py
scripts/build_thirdplace_table.py   # gera a tabela do Anexo C
_test_logic.py / _test_flow.py / _test_ui.py   # testes
```

## Testes

```bash
python _test_logic.py   # classificação, desempates, mata-mata, Anexo C
python _test_flow.py    # merge da API, prioridade manual, transição de fase
python _test_ui.py      # smoke test da interface (streamlit.testing)
```

## Limitações conhecidas

- **Fair-play** não é critério de desempate (as APIs gratuitas não trazem
  cartões); usa-se o ranking FIFA no lugar.
- **Ranking FIFA**, **datas** e **sedes** são aproximados e editáveis em
  `tournament_data.py`.
- As APIs gratuitas podem demorar a popular um torneio novo — por isso o
  override manual é o caminho confiável.
