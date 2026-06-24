"""
Estado canônico do torneio (semente + API + manual) e persistência
------------------------------------------------------------------
O estado vive num dicionário simples e é persistido em ``data/results.json``,
de modo que resultados digitados/importados sobrevivem a reinícios.

Camadas de prioridade ao montar o placar de um jogo:
    semente (calendário, sem placar) < API < manual

Estrutura do dicionário de resultados::

    {
      "groups": { "C3": {"hg": 1, "ag": 1, "source": "manual"}, ... },
      "ko":     { "73": {"hg": 2, "ag": 1, "so": null, "source": "manual"}, ... }
    }
"""
from __future__ import annotations

import json
import os

import tournament_data as td
from data_model import Match

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "data", "results.json")


# --- persistência -----------------------------------------------------------
def empty_results() -> dict:
    return {"groups": {}, "ko": {}}


def load_results(path: str = RESULTS_PATH) -> dict:
    if not os.path.exists(path):
        return empty_results()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("groups", {})
        data.setdefault("ko", {})
        return data
    except (OSError, ValueError):
        return empty_results()


def save_results(results: dict, path: str = RESULTS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)


# --- montagem das partidas de grupo ----------------------------------------
def group_matches(results: dict) -> list[Match]:
    """Jogos da fase de grupos (semente) com os placares aplicados."""
    fixtures = td.group_fixtures()
    gr = results.get("groups", {})
    for m in fixtures:
        rec = gr.get(m.id)
        if rec and rec.get("hg") is not None and rec.get("ag") is not None:
            m.home_goals = int(rec["hg"])
            m.away_goals = int(rec["ag"])
            m.status = "finished"
            m.source = rec.get("source", "manual")
    return fixtures


def _fixture_index() -> dict[tuple, str]:
    """(grupo, frozenset{home,away}) -> id do jogo-semente."""
    idx = {}
    for m in td.group_fixtures():
        idx[(m.group, frozenset({m.home, m.away}))] = (m.id, m.home, m.away)
    return idx


# --- edição manual ----------------------------------------------------------
def set_group_result(results: dict, match_id: str, hg, ag,
                     source: str = "manual") -> None:
    if hg is None or ag is None:
        results["groups"].pop(match_id, None)
        return
    results["groups"][match_id] = {"hg": int(hg), "ag": int(ag), "source": source}


def clear_group_result(results: dict, match_id: str) -> None:
    results["groups"].pop(match_id, None)


def set_ko_result(results: dict, no: int, hg, ag, so=None,
                  source: str = "manual") -> None:
    if hg is None or ag is None:
        results["ko"].pop(str(no), None)
        return
    results["ko"][str(no)] = {"hg": int(hg), "ag": int(ag),
                              "so": so, "source": source}


def clear_ko_result(results: dict, no: int) -> None:
    results["ko"].pop(str(no), None)


def ko_results(results: dict) -> dict[str, dict]:
    return results.get("ko", {})


# --- importação da API ------------------------------------------------------
def import_api_results(results: dict, records: list[dict]) -> int:
    """Aplica resultados vindos da API SEM sobrescrever edições manuais.

    Returns:
        número de jogos atualizados.
    """
    idx = _fixture_index()
    updated = 0
    for rec in records:
        if rec.get("stage") != "group":
            continue  # nesta versão a API alimenta só a fase de grupos
        key = (rec["group"], frozenset({rec["home"], rec["away"]}))
        hit = idx.get(key)
        if not hit:
            continue
        mid, fixt_home, _fixt_away = hit
        existing = results["groups"].get(mid)
        if existing and existing.get("source") == "manual":
            continue  # manual tem prioridade
        # orienta o placar conforme o mando do jogo-semente
        if rec["home"] == fixt_home:
            hg, ag = rec["hg"], rec["ag"]
        else:
            hg, ag = rec["ag"], rec["hg"]
        results["groups"][mid] = {"hg": hg, "ag": ag, "source": "api"}
        updated += 1
    return updated


# --- fase atual -------------------------------------------------------------
def group_stage_complete(gmatches: list[Match]) -> bool:
    return len(gmatches) >= 72 and all(m.played for m in gmatches)


def compute_phase(gmatches: list[Match]) -> str:
    """'groups' enquanto a fase de grupos não termina; senão 'knockout'."""
    return "knockout" if group_stage_complete(gmatches) else "groups"


def progress(gmatches: list[Match]) -> tuple[int, int]:
    """(jogos de grupo disputados, total)."""
    return sum(1 for m in gmatches if m.played), len(gmatches)
