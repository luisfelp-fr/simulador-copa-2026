"""
Testes de fluxo: merge da API, prioridade manual, transição de fase, nomes.
Executar:  python _test_flow.py
"""
from __future__ import annotations

import data_sources
import state
import tournament_data as td


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
    test_api_import_orientation_and_priority()
    test_phase_transition()
    test_code_from_resolution()
    print("\nTESTES DE FLUXO OK")
