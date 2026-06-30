"""
Testes da API REST (FastAPI)
----------------------------
Executar:  python _test_api.py

Usa o ``TestClient`` do Starlette (sem subir servidor de verdade) e redireciona
a persistência para um arquivo temporário, de modo a NÃO tocar em
``data/results.json``.
"""
from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient

import state

# Redireciona a persistência para um arquivo temporário ANTES de exercitar a API.
_TMP = os.path.join(tempfile.mkdtemp(), "results.json")
state.RESULTS_PATH = _TMP

import api  # noqa: E402  (precisa vir depois do redirecionamento de estado)

client = TestClient(api.app)


def _reset():
    state.save_results(state.empty_results())


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    assert r.json()["teams"] == 48


def test_root_redirects_to_docs():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/docs"


def test_teams_listing_and_filter():
    r = client.get("/api/teams")
    assert r.status_code == 200
    assert len(r.json()) == 48

    r = client.get("/api/teams", params={"group": "C"})
    codes = {t["code"] for t in r.json()}
    assert codes == {"BRA", "MAR", "SCO", "HAI"}

    assert client.get("/api/teams", params={"group": "Z"}).status_code == 404


def test_team_detail():
    r = client.get("/api/teams/bra")  # case-insensitive
    assert r.status_code == 200
    assert r.json()["name"] == "Brasil"
    assert client.get("/api/teams/XXX").status_code == 404


def test_groups():
    r = client.get("/api/groups")
    assert r.status_code == 200
    assert len(r.json()) == 12

    r = client.get("/api/groups/A")
    body = r.json()
    assert body["group"] == "A"
    assert len(body["teams"]) == 4
    assert len(body["standings"]) == 4
    assert body["complete"] is False  # sem placares

    assert client.get("/api/groups/Z").status_code == 404


def test_matches_and_filters():
    r = client.get("/api/matches")
    assert r.status_code == 200
    assert len(r.json()) == 72  # 12 grupos x 6 jogos

    r = client.get("/api/matches", params={"group": "C"})
    assert len(r.json()) == 6

    r = client.get("/api/matches", params={"matchday": 1})
    assert len(r.json()) == 24  # 2 jogos por grupo na rodada 1

    r = client.get("/api/matches", params={"team": "BRA"})
    assert len(r.json()) == 3
    assert all("BRA" in (m["home"], m["away"]) for m in r.json())

    r = client.get("/api/matches", params={"status": "finished"})
    assert r.json() == []


def test_set_and_clear_group_result():
    _reset()
    # descobre um jogo do grupo C
    matches = client.get("/api/matches", params={"group": "C"}).json()
    mid = matches[0]["id"]

    r = client.put(f"/api/matches/{mid}/result", json={"home_goals": 3, "away_goals": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["played"] is True
    assert body["status"] == "finished"
    assert body["home_goals"] == 3 and body["away_goals"] == 1
    assert body["source"] == "manual"

    # a partida agora aparece como 'finished' na listagem
    fin = client.get("/api/matches", params={"status": "finished"}).json()
    assert any(m["id"] == mid for m in fin)

    # placar inválido (negativo) é rejeitado pela validação
    assert client.put(f"/api/matches/{mid}/result",
                      json={"home_goals": -1, "away_goals": 0}).status_code == 422
    # id inexistente -> 404
    assert client.put("/api/matches/ZZ9/result",
                      json={"home_goals": 1, "away_goals": 0}).status_code == 404

    r = client.delete(f"/api/matches/{mid}/result")
    assert r.status_code == 200
    assert client.get(f"/api/matches/{mid}").json()["played"] is False


def test_standings_reflect_results():
    _reset()
    matches = client.get("/api/matches", params={"group": "C"}).json()
    mid, home, away = matches[0]["id"], matches[0]["home"], matches[0]["away"]
    client.put(f"/api/matches/{mid}/result", json={"home_goals": 2, "away_goals": 0})

    rows = client.get("/api/standings/C").json()
    leader = next(r for r in rows if r["team"] == home)
    assert leader["points"] == 3
    assert leader["gf"] == 2 and leader["ga"] == 0
    loser = next(r for r in rows if r["team"] == away)
    assert loser["points"] == 0
    _reset()


def test_third_placed_endpoint():
    r = client.get("/api/standings/third-placed")
    assert r.status_code == 200
    assert len(r.json()) == 12  # um 3º por grupo
    assert sum(1 for x in r.json() if x["qualified"]) == 8


def test_knockout_listing():
    r = client.get("/api/knockout")
    assert r.status_code == 200
    assert len(r.json()) == 32  # jogos 73..104

    r = client.get("/api/knockout", params={"stage": "FINAL"})
    assert len(r.json()) == 1
    assert r.json()[0]["no"] == 104

    assert client.get("/api/knockout/104").json()["stage"] == "FINAL"
    assert client.get("/api/knockout/999").status_code == 404
    # com grupos vazios não há campeão
    assert client.get("/api/knockout/champion").status_code == 404


def test_tournament_overview():
    _reset()
    r = client.get("/api/tournament")
    body = r.json()
    assert body["phase"] == "groups"
    assert body["matches_total"] == 72
    assert body["matches_played"] == 0
    assert body["group_stage_complete"] is False
    assert body["champion"] is None


def test_simulate_does_not_persist():
    _reset()
    matches = client.get("/api/matches", params={"group": "C"}).json()
    mid, home = matches[0]["id"], matches[0]["home"]

    payload = {"groups": [{"match_id": mid, "home_goals": 5, "away_goals": 0}]}
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    leader = next(x for x in body["standings"]["C"] if x["team"] == home)
    assert leader["points"] == 3
    assert leader["gf"] == 5

    # a simulação NÃO grava: o estado real continua sem placares
    assert client.get(f"/api/matches/{mid}").json()["played"] is False


def _simulate_full_groups():
    """Preenche os 72 jogos: melhor ranking FIFA vence por 2x0."""
    import tournament_data as td
    payload = {"groups": []}
    for m in client.get("/api/matches").json():
        rh = td.TEAMS[m["home"]].fifa_rank
        ra = td.TEAMS[m["away"]].fifa_rank
        hg, ag = (2, 0) if rh < ra else (0, 2)
        payload["groups"].append({"match_id": m["id"], "home_goals": hg, "away_goals": ag})
    return payload


def test_simulate_full_groups_resolves_knockout():
    _reset()
    payload = _simulate_full_groups()
    body = client.post("/api/simulate", json=payload).json()
    assert body["phase"] == "knockout"
    # com todos os grupos concluídos, os dezesseis-avos ficam resolvidos
    r32 = [g for g in body["knockout"] if g["stage"] == "R32"]
    assert len(r32) == 16
    assert all(g["resolved"] for g in r32)


def test_knockout_result_requires_shootout_on_tie():
    _reset()
    # 73 não está resolvido sem grupos, mas a validação de empate é independente
    r = client.put("/api/knockout/73/result",
                   json={"home_goals": 1, "away_goals": 1})
    assert r.status_code == 422
    r = client.put("/api/knockout/73/result",
                   json={"home_goals": 2, "away_goals": 1})
    assert r.status_code == 200
    client.delete("/api/knockout/73/result")
    _reset()


def test_clear_all_results():
    matches = client.get("/api/matches", params={"group": "C"}).json()
    mid = matches[0]["id"]
    client.put(f"/api/matches/{mid}/result", json={"home_goals": 1, "away_goals": 0})
    r = client.delete("/api/results")
    assert r.status_code == 200
    assert client.get("/api/matches", params={"status": "finished"}).json() == []


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
        passed += 1
    print(f"\n{passed} testes da API OK.")


if __name__ == "__main__":
    _run_all()
