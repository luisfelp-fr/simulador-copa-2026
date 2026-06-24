"""
Testes de lógica pura (classificação + mata-mata)
-------------------------------------------------
Executar:  python _test_logic.py
Não depende de Streamlit nem de rede.
"""
from __future__ import annotations

import tournament_data as td
from data_model import Match, Team
import standings
import knockout


def _gm(group, h, a, hg, ag, md=1):
    return Match(id=f"{group}-{h}-{a}", stage="group", group=group, matchday=md,
                 home=h, away=a, home_goals=hg, away_goals=ag, status="finished")


# --- helpers de simulação determinística ------------------------------------
def _result(home, away):
    """Time de melhor ranking FIFA (menor número) vence por 2x0."""
    rh = td.TEAMS[home].fifa_rank
    ra = td.TEAMS[away].fifa_rank
    return (2, 0) if rh < ra else (0, 2)


def _simulate_full():
    matches = td.group_fixtures()
    for m in matches:
        m.home_goals, m.away_goals = _result(m.home, m.away)
        m.status = "finished"
    tables = standings.compute_all_tables(matches, td.TEAMS)
    return matches, tables


def test_group_order_by_rank():
    _matches, tables = _simulate_full()
    for g, rows in tables.items():
        ranks = [td.TEAMS[r.team].fifa_rank for r in rows]
        assert ranks == sorted(ranks), f"grupo {g} fora de ordem: {ranks}"
    print("ok  test_group_order_by_rank")


def test_head_to_head_tiebreak():
    teams = {
        "T1": Team("T1", "T1", "X", 1), "T2": Team("T2", "T2", "X", 2),
        "T3": Team("T3", "T3", "X", 3), "T4": Team("T4", "T4", "X", 4),
    }
    # ciclo de confronto direto entre T1,T2,T3 (todos 6 pts); separado por saldo geral
    ms = [
        _gm("X", "T1", "T2", 1, 0), _gm("X", "T2", "T3", 1, 0), _gm("X", "T3", "T1", 1, 0),
        _gm("X", "T1", "T4", 3, 0), _gm("X", "T2", "T4", 2, 0), _gm("X", "T3", "T4", 1, 0),
    ]
    rows = standings.compute_group_table("X", ms, teams)
    order = [r.team for r in rows]
    assert order == ["T1", "T2", "T3", "T4"], order
    print("ok  test_head_to_head_tiebreak")


def test_direct_h2h_separates():
    teams = {"A": Team("A", "A", "Y", 9), "B": Team("B", "B", "Y", 1),
             "C": Team("C", "C", "Y", 2), "D": Team("D", "D", "Y", 3)}
    # A e B empatam em pontos (6); A venceu B no confronto direto e fica à frente
    # APESAR de B ter ranking FIFA melhor (1 vs 9).
    ms = [
        _gm("Y", "A", "B", 1, 0), _gm("Y", "C", "A", 1, 0),
        _gm("Y", "A", "D", 1, 0), _gm("Y", "B", "C", 1, 0),
        _gm("Y", "B", "D", 1, 0), _gm("Y", "D", "C", 1, 0),
    ]
    rows = standings.compute_group_table("Y", ms, teams)
    pos = {r.team: r.position for r in rows}
    assert pos["A"] == 1 and pos["B"] == 2, rows  # A à frente de B pelo confronto direto
    print("ok  test_direct_h2h_separates")


def test_third_allocation_respects_clusters():
    # qualquer combinação de 8 grupos deve render uma atribuição válida
    qualifying = set("ABCDEFGH")
    assign = knockout.assign_thirds(qualifying, None)  # via reserva (clusters)
    assert len(assign) == 8, assign
    assert len(set(assign.values())) == 8, "grupos repetidos"
    for no, letter in assign.items():
        assert letter in td.THIRD_CLUSTERS[no], f"vaga {no} recebeu {letter} fora do cluster"
        assert letter in qualifying
    print("ok  test_third_allocation_respects_clusters")


def test_full_knockout_and_champion():
    matches, tables = _simulate_full()
    alloc = knockout.load_allocation_table()  # pode ser None -> usa reserva
    ko_results: dict[str, dict] = {}
    for _ in range(7):  # passes suficientes p/ propagar 73 -> 104
        games = knockout.compute_knockout(tables, matches, td.TEAMS, ko_results, alloc)
        for no, gmt in games.items():
            if gmt.resolved and str(no) not in ko_results:
                hg, ag = _result(gmt.home_code, gmt.away_code)
                ko_results[str(no)] = {"hg": hg, "ag": ag}

    games = knockout.compute_knockout(tables, matches, td.TEAMS, ko_results, alloc)

    # 32 times distintos nos dezesseis-avos
    r32_teams = set()
    for no in range(73, 89):
        g = games[no]
        assert g.resolved, f"jogo {no} não resolvido"
        r32_teams.add(g.home_code)
        r32_teams.add(g.away_code)
    assert len(r32_teams) == 32, f"esperava 32 times no R32, obtive {len(r32_teams)}"

    champ = knockout.champion(games)
    assert champ == "ARG", f"campeão esperado ARG (rank 1), obtido {champ}"
    print(f"ok  test_full_knockout_and_champion (campeão = {td.name_of(champ)})")


def test_bracket_tree_consistency():
    # cada jogo 73..102 é fonte (W/L) de exatamente um jogo posterior
    refs: list[int] = []
    for no, (h, a) in td.KO_TREE.items():
        for spec in (h, a):
            if spec[0] in ("W", "L"):
                refs.append(int(spec[1:]))
    # 101 e 102 aparecem 2x (vencedor->final, perdedor->disputa 3º)
    expected = list(range(73, 101)) + [101, 101, 102, 102]
    assert sorted(refs) == sorted(expected), sorted(refs)
    print("ok  test_bracket_tree_consistency")


if __name__ == "__main__":
    test_group_order_by_rank()
    test_head_to_head_tiebreak()
    test_direct_h2h_separates()
    test_third_allocation_respects_clusters()
    test_bracket_tree_consistency()
    test_full_knockout_and_champion()
    print("\nTODOS OS TESTES PASSARAM")
