"""
Testes de fluxo: merge da API, prioridade manual, transição de fase, nomes.
Executar:  python _test_flow.py
"""
from __future__ import annotations

import data_sources
import state
import tournament_data as td


# Amostra sintética no formato do scoreboard da ESPN (sem rede).
ESPN_SAMPLE = {
    "events": [
        {  # jogo de grupo concluído: México 2 x 1 África do Sul
            "competitions": [{
                "status": {"type": {"completed": True}},
                "competitors": [
                    {"homeAway": "home", "score": "2",
                     "team": {"abbreviation": "MEX", "displayName": "Mexico"}},
                    {"homeAway": "away", "score": "1",
                     "team": {"abbreviation": "RSA", "displayName": "South Africa"}},
                ],
            }],
        },
        {  # ainda não concluído -> ignorado
            "competitions": [{
                "status": {"type": {"completed": False}},
                "competitors": [
                    {"homeAway": "home", "score": "0",
                     "team": {"abbreviation": "BRA", "displayName": "Brazil"}},
                    {"homeAway": "away", "score": "0",
                     "team": {"abbreviation": "MAR", "displayName": "Morocco"}},
                ],
            }],
        },
        {  # times de grupos diferentes -> estágio 'ko'
            "competitions": [{
                "status": {"type": {"completed": True}},
                "competitors": [
                    {"homeAway": "home", "score": "3",
                     "team": {"abbreviation": "BRA", "displayName": "Brazil"}},
                    {"homeAway": "away", "score": "1",
                     "team": {"abbreviation": "ARG", "displayName": "Argentina"}},
                ],
            }],
        },
        {  # resolução por displayName quando a sigla é desconhecida (Bósnia)
            "competitions": [{
                "status": {"type": {"completed": True}},
                "competitors": [
                    {"homeAway": "home", "score": "1",
                     "team": {"abbreviation": "CAN", "displayName": "Canada"}},
                    {"homeAway": "away", "score": "1",
                     "team": {"abbreviation": "BHZ", "displayName": "Bosnia & Herzegovina"}},
                ],
            }],
        },
    ]
}


def test_parse_espn():
    recs = data_sources._parse_espn(ESPN_SAMPLE)
    assert len(recs) == 3, recs  # o jogo não concluído é ignorado
    by_pair = {frozenset((r["home"], r["away"])): r for r in recs}

    a1 = by_pair[frozenset(("MEX", "RSA"))]
    assert a1 == {"group": "A", "home": "MEX", "away": "RSA",
                  "hg": 2, "ag": 1, "stage": "group"}, a1

    ko = by_pair[frozenset(("BRA", "ARG"))]
    assert ko["stage"] == "ko", ko  # grupos diferentes

    bih = by_pair[frozenset(("CAN", "BIH"))]  # sigla 'BHZ' resolvida por nome
    assert bih["group"] == "B" and bih["stage"] == "group", bih
    print("ok  test_parse_espn")


def test_espn_feeds_import():
    results = state.empty_results()
    recs = data_sources._parse_espn(ESPN_SAMPLE)
    n = state.import_api_results(results, recs)  # só registros 'group' entram
    assert n == 2, n  # MEXxRSA e CANxBIH; BRAxARG é 'ko' e é ignorado
    assert results["groups"]["A1"] == {"hg": 2, "ag": 1, "source": "api"}
    print("ok  test_espn_feeds_import")


def test_fetch_results_uses_espn_without_keys():
    sample = [{"group": "C", "home": "BRA", "away": "MAR",
               "hg": 1, "ag": 0, "stage": "group"}]
    orig = data_sources.fetch_espn
    data_sources.fetch_espn = lambda *a, **k: sample  # evita rede
    try:
        res, msg = data_sources.fetch_results()  # sem nenhuma chave
        assert res == sample, res
        assert "ESPN" in msg, msg
    finally:
        data_sources.fetch_espn = orig
    # com ESPN desligado e sem chaves: nada, sem tocar a rede
    res, msg = data_sources.fetch_results(use_espn=False)
    assert res == [] and "manual" in msg, msg
    print("ok  test_fetch_results_uses_espn_without_keys")


def test_api_import_orientation_and_priority():
    results = state.empty_results()
    # A1 (semente) = MEX x RSA. A API traz invertido: RSA 2 x 1 MEX.
    rec = [{"group": "A", "home": "RSA", "away": "MEX", "hg": 2, "ag": 1, "stage": "group"}]
    n = state.import_api_results(results, rec)
    assert n == 1
    # placar deve ser reorientado para o mando da semente (MEX em casa) -> 1 x 2
    assert results["groups"]["A1"] == {"hg": 1, "ag": 2, "source": "api"}, results["groups"]["A1"]

    # edição manual tem prioridade e não é sobrescrita pela API
    state.set_group_result(results, "A1", 5, 0, source="manual")
    state.import_api_results(results, rec)
    assert results["groups"]["A1"]["hg"] == 5, "API sobrescreveu edição manual!"
    print("ok  test_api_import_orientation_and_priority")


def test_phase_transition():
    results = state.empty_results()
    gm = state.group_matches(results)
    assert state.compute_phase(gm) == "groups"
    # preenche TODOS os 72 jogos -> vira mata-mata
    for m in td.group_fixtures():
        state.set_group_result(results, m.id, 1, 0, source="manual")
    gm = state.group_matches(results)
    assert state.group_stage_complete(gm)
    assert state.compute_phase(gm) == "knockout"
    print("ok  test_phase_transition")


def test_code_from_resolution():
    assert data_sources.code_from("Brazil") == "BRA"
    assert data_sources.code_from("BRA") == "BRA"
    assert data_sources.code_from("Côte d'Ivoire") == "CIV"
    assert data_sources.code_from("DR Congo") == "COD"
    assert data_sources.code_from("Coreia do Sul") == "KOR"  # nome PT-BR
    assert data_sources.code_from("Inexistente") is None
    print("ok  test_code_from_resolution")


if __name__ == "__main__":
    test_parse_espn()
    test_espn_feeds_import()
    test_fetch_results_uses_espn_without_keys()
    test_api_import_orientation_and_priority()
    test_phase_transition()
    test_code_from_resolution()
    print("\nTESTES DE FLUXO OK")
