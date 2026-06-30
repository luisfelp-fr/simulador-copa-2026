"""
API REST da Copa do Mundo 2026 (FastAPI)
----------------------------------------
Expõe, por HTTP/JSON, tudo o que o painel calcula: seleções, grupos, partidas,
classificação, ranking dos 3º colocados, chaveamento do mata-mata e um endpoint
de simulação "e-se". Também oferece endpoints de escrita para registrar placares
e importar resultados das APIs externas de futebol.

Toda a lógica é reaproveitada dos módulos puros (``standings.py``,
``knockout.py``, ``simulator.py``) e o estado é o MESMO arquivo
``data/results.json`` usado pelo app Streamlit — ou seja, API e painel ficam
sempre em sincronia.

Executar::

    uvicorn api:app --reload

Documentação interativa (gerada automaticamente):

    * Swagger UI  -> http://localhost:8000/docs
    * ReDoc       -> http://localhost:8000/redoc
    * OpenAPI     -> http://localhost:8000/openapi.json

Importação automática (opcional) lê as chaves das variáveis de ambiente
``FOOTBALL_DATA_TOKEN`` e ``API_FOOTBALL_KEY``.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import api_schemas as sc
import data_model as dm
import data_sources
import knockout
import simulator
import standings
import state
import tournament_data as td

API_VERSION = "1.0.0"
NAME = td.name_of
KO_RANGE = range(73, 105)

# Tabela do Anexo C (3º colocados) é estática: carrega uma vez.
ALLOC = knockout.load_allocation_table()

app = FastAPI(
    title="Copa do Mundo 2026 — API",
    version=API_VERSION,
    description=(
        "API para consultar resultados, classificação, mata-mata e simulações "
        "da Copa do Mundo FIFA 2026. Os dados refletem o mesmo estado do painel "
        "(`data/results.json`)."
    ),
)

# Libera consumo a partir de um front-end no navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Conversores dataclass interno -> schema de saída
# --------------------------------------------------------------------------- #
def _team_out(t: td.Team) -> sc.TeamOut:
    return sc.TeamOut(code=t.code, name=t.name, group=t.group, fifa_rank=t.fifa_rank)


def _match_out(m: dm.Match) -> sc.MatchOut:
    return sc.MatchOut(
        id=m.id, stage=m.stage, group=m.group, matchday=m.matchday,
        home=m.home, away=m.away, home_name=NAME(m.home), away_name=NAME(m.away),
        home_goals=m.home_goals, away_goals=m.away_goals, status=m.status,
        date=m.date, venue=m.venue, source=m.source,
        played=m.played, winner=m.winner(),
    )


def _row_out(r: dm.StandingRow) -> sc.StandingRowOut:
    return sc.StandingRowOut(
        group=r.group, position=r.position, team=r.team, team_name=NAME(r.team),
        played=r.played, won=r.won, draw=r.draw, lost=r.lost,
        gf=r.gf, ga=r.ga, gd=r.gd, points=r.points, qualified=r.qualified,
    )


def _ko_out(g: knockout.KOGame) -> sc.KnockoutGameOut:
    return sc.KnockoutGameOut(
        no=g.no, stage=g.stage, stage_label=dm.STAGE_LABELS[g.stage],
        home_code=g.home_code, away_code=g.away_code,
        home_label=g.home_label, away_label=g.away_label,
        home_goals=g.home_goals, away_goals=g.away_goals,
        shootout_winner=g.shootout_winner,
        played=g.played, resolved=g.resolved,
        winner=g.winner_code(), loser=g.loser_code(),
    )


def _third_out(i: int, r: dm.StandingRow, n: int = 8) -> sc.ThirdPlacedOut:
    return sc.ThirdPlacedOut(
        rank=i + 1, group=r.group, team=r.team, team_name=NAME(r.team),
        points=r.points, gd=r.gd, gf=r.gf, qualified=i < n,
    )


# --------------------------------------------------------------------------- #
# Montagem do estado a cada requisição (sempre lê do disco -> sincroniza com o app)
# --------------------------------------------------------------------------- #
def _load_state():
    """Carrega resultados do disco e devolve (results, gmatches, tables)."""
    results = state.load_results()
    gmatches = state.group_matches(results)
    tables = standings.compute_all_tables(gmatches, td.TEAMS)
    return results, gmatches, tables


# --------------------------------------------------------------------------- #
# Raiz e saúde
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health", response_model=sc.HealthOut, tags=["meta"])
def health():
    """Verificação simples de disponibilidade."""
    return sc.HealthOut(status="ok", teams=len(td.TEAMS), version=API_VERSION)


@app.get("/api/tournament", response_model=sc.TournamentOut, tags=["meta"])
def tournament():
    """Visão geral: fase atual, progresso e campeão (se já houver)."""
    results, gmatches, tables = _load_state()
    phase = state.compute_phase(gmatches)
    played, total = state.progress(gmatches)
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), ALLOC)
    champ = knockout.champion(games)
    return sc.TournamentOut(
        name="Copa do Mundo FIFA 2026",
        phase=phase,
        phase_label="Fase de Grupos" if phase == "groups" else "Mata-mata",
        matches_played=played, matches_total=total,
        group_stage_complete=state.group_stage_complete(gmatches),
        champion=champ, champion_name=NAME(champ) if champ else None,
        third_place_table="official" if ALLOC else "fallback",
    )


# --------------------------------------------------------------------------- #
# Seleções
# --------------------------------------------------------------------------- #
@app.get("/api/teams", response_model=list[sc.TeamOut], tags=["seleções"])
def list_teams(group: str | None = Query(None, description="Filtra por grupo (A–L)")):
    """Lista todas as seleções (opcionalmente filtradas por grupo)."""
    teams = td.TEAMS.values()
    if group is not None:
        g = group.upper()
        if g not in td.GROUP_ORDER:
            raise HTTPException(404, f"Grupo inválido: {group}")
        teams = [t for t in teams if t.group == g]
    return [_team_out(t) for t in sorted(teams, key=lambda t: (t.group, t.fifa_rank))]


@app.get("/api/teams/{code}", response_model=sc.TeamOut, tags=["seleções"])
def get_team(code: str):
    """Detalha uma seleção pelo código FIFA (ex.: ``BRA``)."""
    t = td.TEAMS.get(code.upper())
    if not t:
        raise HTTPException(404, f"Seleção não encontrada: {code}")
    return _team_out(t)


# --------------------------------------------------------------------------- #
# Grupos
# --------------------------------------------------------------------------- #
@app.get("/api/groups", response_model=list[sc.GroupOut], tags=["grupos"])
def list_groups():
    """Lista os 12 grupos com suas seleções e a classificação atual."""
    _results, gmatches, tables = _load_state()
    out = []
    for g in td.GROUP_ORDER:
        teams = [td.TEAMS[c] for c in td.GROUPS[g]]
        out.append(sc.GroupOut(
            group=g,
            complete=standings.group_complete(g, gmatches),
            teams=[_team_out(t) for t in teams],
            standings=[_row_out(r) for r in tables[g]],
        ))
    return out


@app.get("/api/groups/{group}", response_model=sc.GroupOut, tags=["grupos"])
def get_group(group: str):
    """Detalha um grupo (seleções + classificação)."""
    g = group.upper()
    if g not in td.GROUP_ORDER:
        raise HTTPException(404, f"Grupo inválido: {group}")
    _results, gmatches, tables = _load_state()
    teams = [td.TEAMS[c] for c in td.GROUPS[g]]
    return sc.GroupOut(
        group=g,
        complete=standings.group_complete(g, gmatches),
        teams=[_team_out(t) for t in teams],
        standings=[_row_out(r) for r in tables[g]],
    )


# --------------------------------------------------------------------------- #
# Partidas (fase de grupos)
# --------------------------------------------------------------------------- #
@app.get("/api/matches", response_model=list[sc.MatchOut], tags=["partidas"])
def list_matches(
    group: str | None = Query(None, description="Filtra por grupo (A–L)"),
    matchday: int | None = Query(None, ge=1, le=3, description="Rodada (1–3)"),
    status: str | None = Query(None, description="'scheduled' ou 'finished'"),
    team: str | None = Query(None, description="Código FIFA de uma das seleções"),
):
    """Lista as partidas da fase de grupos, com filtros opcionais."""
    _results, gmatches, _tables = _load_state()
    matches = gmatches
    if group is not None:
        g = group.upper()
        if g not in td.GROUP_ORDER:
            raise HTTPException(404, f"Grupo inválido: {group}")
        matches = [m for m in matches if m.group == g]
    if matchday is not None:
        matches = [m for m in matches if m.matchday == matchday]
    if status is not None:
        if status not in ("scheduled", "finished"):
            raise HTTPException(422, "status deve ser 'scheduled' ou 'finished'")
        matches = [m for m in matches if m.status == status]
    if team is not None:
        code = team.upper()
        matches = [m for m in matches if code in (m.home, m.away)]
    matches = sorted(matches, key=lambda m: (m.date, m.id))
    return [_match_out(m) for m in matches]


@app.get("/api/matches/{match_id}", response_model=sc.MatchOut, tags=["partidas"])
def get_match(match_id: str):
    """Detalha uma partida da fase de grupos pelo id (ex.: ``C3``)."""
    _results, gmatches, _tables = _load_state()
    for m in gmatches:
        if m.id == match_id:
            return _match_out(m)
    raise HTTPException(404, f"Partida não encontrada: {match_id}")


# --------------------------------------------------------------------------- #
# Classificação
# --------------------------------------------------------------------------- #
@app.get("/api/standings", response_model=dict[str, list[sc.StandingRowOut]], tags=["classificação"])
def all_standings():
    """Tabela de classificação de todos os grupos."""
    _results, _gmatches, tables = _load_state()
    return {g: [_row_out(r) for r in rows] for g, rows in tables.items()}


@app.get("/api/standings/third-placed", response_model=list[sc.ThirdPlacedOut], tags=["classificação"])
def third_placed():
    """Ranking dos 3º colocados (os 8 melhores avançam ao mata-mata)."""
    _results, _gmatches, tables = _load_state()
    ranked, _qualifying = standings.best_third_placed(tables, td.TEAMS)
    return [_third_out(i, r) for i, r in enumerate(ranked)]


@app.get("/api/standings/{group}", response_model=list[sc.StandingRowOut], tags=["classificação"])
def group_standings(group: str):
    """Tabela de classificação de um grupo específico."""
    g = group.upper()
    if g not in td.GROUP_ORDER:
        raise HTTPException(404, f"Grupo inválido: {group}")
    _results, _gmatches, tables = _load_state()
    return [_row_out(r) for r in tables[g]]


# --------------------------------------------------------------------------- #
# Mata-mata
# --------------------------------------------------------------------------- #
@app.get("/api/knockout", response_model=list[sc.KnockoutGameOut], tags=["mata-mata"])
def list_knockout(
    stage: str | None = Query(None, description="R32 | R16 | QF | SF | 3RD | FINAL"),
):
    """Lista os jogos do mata-mata (73–104), com lados resolvidos quando possível."""
    results, gmatches, tables = _load_state()
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), ALLOC)
    out = [_ko_out(games[no]) for no in sorted(games)]
    if stage is not None:
        st = stage.upper()
        if st not in dm.STAGE_LABELS:
            raise HTTPException(422, f"Fase inválida: {stage}")
        out = [g for g in out if g.stage == st]
    return out


@app.get("/api/knockout/champion", response_model=sc.MessageOut, tags=["mata-mata"])
def knockout_champion():
    """Campeão do torneio (vencedor do jogo 104), se já definido."""
    results, gmatches, tables = _load_state()
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), ALLOC)
    champ = knockout.champion(games)
    if not champ:
        raise HTTPException(404, "Campeão ainda não definido.")
    return sc.MessageOut(detail=NAME(champ))


@app.get("/api/knockout/{no}", response_model=sc.KnockoutGameOut, tags=["mata-mata"])
def get_knockout(no: int):
    """Detalha um jogo do mata-mata pelo número (73–104)."""
    if no not in KO_RANGE:
        raise HTTPException(404, f"Número de jogo inválido: {no}")
    results, gmatches, tables = _load_state()
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), ALLOC)
    return _ko_out(games[no])


# --------------------------------------------------------------------------- #
# Escrita — registro de placares
# --------------------------------------------------------------------------- #
@app.put("/api/matches/{match_id}/result", response_model=sc.MatchOut, tags=["partidas"])
def set_match_result(match_id: str, body: sc.GroupResultIn):
    """Registra/atualiza o placar de uma partida da fase de grupos (origem manual)."""
    results = state.load_results()
    valid_ids = {m.id for m in td.group_fixtures()}
    if match_id not in valid_ids:
        raise HTTPException(404, f"Partida não encontrada: {match_id}")
    state.set_group_result(results, match_id, body.home_goals, body.away_goals,
                           source="manual")
    state.save_results(results)
    for m in state.group_matches(results):
        if m.id == match_id:
            return _match_out(m)
    raise HTTPException(500, "Falha ao salvar o placar.")  # pragma: no cover


@app.delete("/api/matches/{match_id}/result", response_model=sc.MessageOut, tags=["partidas"])
def clear_match_result(match_id: str):
    """Remove o placar registrado de uma partida da fase de grupos."""
    results = state.load_results()
    state.clear_group_result(results, match_id)
    state.save_results(results)
    return sc.MessageOut(detail=f"Placar de {match_id} removido.")


@app.put("/api/knockout/{no}/result", response_model=sc.KnockoutGameOut, tags=["mata-mata"])
def set_knockout_result(no: int, body: sc.KnockoutResultIn):
    """Registra/atualiza o placar de um jogo do mata-mata (origem manual)."""
    if no not in KO_RANGE:
        raise HTTPException(404, f"Número de jogo inválido: {no}")
    if body.home_goals == body.away_goals and not body.shootout_winner:
        raise HTTPException(422, "Empate no mata-mata exige 'shootout_winner'.")
    results = state.load_results()
    state.set_ko_result(results, no, body.home_goals, body.away_goals,
                        so=body.shootout_winner, source="manual")
    state.save_results(results)
    _r2, gmatches, tables = _load_state()
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), ALLOC)
    return _ko_out(games[no])


@app.delete("/api/knockout/{no}/result", response_model=sc.MessageOut, tags=["mata-mata"])
def clear_knockout_result(no: int):
    """Remove o placar registrado de um jogo do mata-mata."""
    if no not in KO_RANGE:
        raise HTTPException(404, f"Número de jogo inválido: {no}")
    results = state.load_results()
    state.clear_ko_result(results, no)
    state.save_results(results)
    return sc.MessageOut(detail=f"Placar do jogo {no} removido.")


@app.delete("/api/results", response_model=sc.MessageOut, tags=["admin"])
def clear_all_results():
    """Apaga TODOS os resultados (grupos e mata-mata)."""
    state.save_results(state.empty_results())
    return sc.MessageOut(detail="Todos os resultados foram apagados.")


@app.post("/api/refresh", response_model=sc.RefreshOut, tags=["admin"])
def refresh_from_api():
    """Importa resultados das APIs externas de futebol (sem sobrescrever placares
    manuais). Lê as chaves de ``FOOTBALL_DATA_TOKEN`` e ``API_FOOTBALL_KEY``."""
    fd_token = os.environ.get("FOOTBALL_DATA_TOKEN")
    af_key = os.environ.get("API_FOOTBALL_KEY")
    records, msg = data_sources.fetch_results(fd_token, af_key)
    results = state.load_results()
    updated = state.import_api_results(results, records)
    state.save_results(results)
    return sc.RefreshOut(detail=msg, updated=updated)


# --------------------------------------------------------------------------- #
# Simulação "e-se"
# --------------------------------------------------------------------------- #
@app.post("/api/simulate", response_model=sc.SimulateOut, tags=["simulação"])
def simulate(body: sc.SimulateIn):
    """Aplica placares hipotéticos SOBRE o estado real (sem persistir) e devolve
    a classificação, o ranking dos 3º e o chaveamento projetados.

    Jogos reais já disputados são imutáveis: palpites sobre eles são ignorados.
    """
    results = state.load_results()
    canonical = state.group_matches(results)

    group_ov = {s.match_id: (s.home_goals, s.away_goals) for s in body.groups}
    sim_tables, eff = simulator.simulate_groups(canonical, group_ov, td.TEAMS)
    ranked, _qualifying = standings.best_third_placed(sim_tables, td.TEAMS)

    real_ko = state.ko_results(results)
    ko_ov = {s.no: (s.home_goals, s.away_goals, s.shootout_winner)
             for s in body.knockout}
    eff_ko = simulator.effective_ko_results(real_ko, ko_ov)
    games = knockout.compute_knockout(sim_tables, eff, td.TEAMS, eff_ko, ALLOC)
    champ = knockout.champion(games)

    return sc.SimulateOut(
        phase=state.compute_phase(eff),
        standings={g: [_row_out(r) for r in rows] for g, rows in sim_tables.items()},
        third_placed=[_third_out(i, r) for i, r in enumerate(ranked)],
        knockout=[_ko_out(games[no]) for no in sorted(games)],
        champion=champ, champion_name=NAME(champ) if champ else None,
    )
