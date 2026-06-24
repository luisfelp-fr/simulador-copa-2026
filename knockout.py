"""
Mata-mata — lógica pura (sem Streamlit)
---------------------------------------
Monta o chaveamento dos dezesseis-avos (jogos 73–88) a partir das tabelas dos
grupos e propaga os vencedores até a final (jogos 89–104).

A alocação dos 8 melhores 3º colocados segue a tabela oficial do Anexo C da FIFA
(495 combinações), carregada de ``data/thirdplace_allocation.json``. Se a tabela
não estiver disponível para uma combinação, recorre-se a um emparelhamento
determinístico que respeita os clusters de cada vaga (``THIRD_CLUSTERS``).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import tournament_data as td
from data_model import StandingRow, Team
from standings import best_third_placed, group_complete

_ALLOC_PATH = os.path.join(os.path.dirname(__file__), "data", "thirdplace_allocation.json")

# ordinal por dígito de posição
_ORD = {"1": "1º", "2": "2º", "3": "3º"}


@dataclass
class KOGame:
    """Um jogo do mata-mata, possivelmente com lados ainda não resolvidos."""
    no: int
    stage: str
    home_code: str | None
    away_code: str | None
    home_label: str
    away_label: str
    home_goals: int | None = None
    away_goals: int | None = None
    shootout_winner: str | None = None

    @property
    def played(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def resolved(self) -> bool:
        return self.home_code is not None and self.away_code is not None

    def winner_code(self) -> str | None:
        if not (self.played and self.resolved):
            return None
        if self.home_goals > self.away_goals:
            return self.home_code
        if self.away_goals > self.home_goals:
            return self.away_code
        return self.shootout_winner

    def loser_code(self) -> str | None:
        w = self.winner_code()
        if w is None:
            return None
        return self.away_code if w == self.home_code else self.home_code


def load_allocation_table(path: str = _ALLOC_PATH) -> dict[str, list[str]] | None:
    """Carrega a tabela do Anexo C (chave = 8 grupos ordenados; valor = 8 letras
    na ordem de ``THIRD_SLOTS``). Devolve ``None`` se o arquivo não existir."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _match_thirds(qualifying_groups: set[str]) -> dict[int, str]:
    """Emparelhamento de reserva: atribui cada grupo classificado a uma vaga de
    3º respeitando os clusters. Determinístico (busca em ordem alfabética)."""
    groups = sorted(qualifying_groups)
    slots = td.THIRD_SLOTS
    allowed = [sorted(set(td.THIRD_CLUSTERS[no]) & set(groups)) for no in slots]
    assign: dict[int, str] = {}
    used: set[str] = set()

    def bt(i: int) -> bool:
        if i == len(slots):
            return True
        for g in allowed[i]:
            if g not in used:
                used.add(g)
                assign[slots[i]] = g
                if bt(i + 1):
                    return True
                used.discard(g)
                assign.pop(slots[i], None)
        return False

    bt(0)
    return assign


def assign_thirds(qualifying_groups: set[str],
                  allocation: dict[str, list[str]] | None) -> dict[int, str]:
    """Mapeia cada vaga de 3º (número do jogo) ao GRUPO cujo 3º colocado a ocupa."""
    key = "".join(sorted(qualifying_groups))
    if allocation and key in allocation:
        letters = allocation[key]
        if len(letters) == len(td.THIRD_SLOTS):
            return dict(zip(td.THIRD_SLOTS, letters))
    return _match_thirds(qualifying_groups)


def compute_knockout(tables: dict[str, list[StandingRow]],
                     group_matches: list,
                     teams: dict[str, Team],
                     ko_results: dict[str, dict] | None = None,
                     allocation: dict[str, list[str]] | None = None
                     ) -> dict[int, KOGame]:
    """Calcula todos os jogos do mata-mata (73–104).

    Args:
        tables: tabelas ordenadas por grupo.
        group_matches: partidas da fase de grupos (para checar conclusão).
        teams: metadados das seleções.
        ko_results: resultados do mata-mata por número de jogo (str) →
            {"hg": int, "ag": int, "so": código_vencedor_penaltis}.
        allocation: tabela do Anexo C (ou None p/ reserva).

    Returns:
        dict número_do_jogo → KOGame (lados resolvidos quando possível).
    """
    ko_results = ko_results or {}

    # --- posições de grupo resolvidas (apenas grupos concluídos) ------------
    final_groups = {g for g in tables if group_complete(g, group_matches)}
    pos: dict[str, str] = {}
    for g in final_groups:
        for r in tables[g]:
            pos[f"{r.position}{g}"] = r.team

    # --- 3º colocados: só quando TODOS os grupos terminaram -----------------
    third_for_slot: dict[int, str] = {}
    if len(final_groups) == 12:
        _ranked, qualifying = best_third_placed(tables, teams)
        slot_group = assign_thirds(qualifying, allocation)
        for no, letter in slot_group.items():
            code = pos.get(f"3{letter}")
            if code:
                third_for_slot[no] = code

    games: dict[int, KOGame] = {}
    r32_def = {no: (h, a) for (no, h, a) in td.R32_DEF}

    def resolve_spec(spec: str, no: int) -> tuple[str | None, str]:
        """Resolve uma especificação de lado → (código_ou_None, rótulo)."""
        if spec[0] in _ORD and spec[1].isalpha():       # "1A", "2B"
            code = pos.get(spec)
            if code:
                return code, td.name_of(code)
            return None, f"{_ORD[spec[0]]} Grupo {spec[1]}"
        if spec.startswith("3:"):                       # vaga de 3º colocado
            code = third_for_slot.get(no)
            if code:
                return code, td.name_of(code)
            cluster = "/".join(list(spec[2:]))
            return None, f"3º ({cluster})"
        if spec.startswith("W") or spec.startswith("L"):
            ref = int(spec[1:])
            src = games.get(ref)
            code = (src.winner_code() if spec[0] == "W" else src.loser_code()) if src else None
            if code:
                return code, td.name_of(code)
            verb = "Vencedor" if spec[0] == "W" else "Perdedor"
            return None, f"{verb} {ref}"
        return None, spec

    for no in range(73, 105):
        if no in r32_def:
            hspec, aspec = r32_def[no]
        else:
            hspec, aspec = td.KO_TREE[no]
        hc, hl = resolve_spec(hspec, no)
        ac, al = resolve_spec(aspec, no)
        res = ko_results.get(str(no), {})
        games[no] = KOGame(
            no=no,
            stage=td.stage_of_match(no),
            home_code=hc, away_code=ac,
            home_label=hl, away_label=al,
            home_goals=res.get("hg"),
            away_goals=res.get("ag"),
            shootout_winner=res.get("so"),
        )
    return games


def champion(games: dict[int, KOGame]) -> str | None:
    """Código do campeão (vencedor do jogo 104), ou None."""
    final = games.get(104)
    return final.winner_code() if final else None
