"""
Smoke test da interface via streamlit.testing (sem navegador, sem rede).
Executar:  python _test_ui.py
"""
from __future__ import annotations

import os
import sys

# Desliga a auto-atualização da API durante o smoke test (sem rede).
os.environ["COPA_DISABLE_AUTOSYNC"] = "1"

from streamlit.testing.v1 import AppTest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _run():
    at = AppTest.from_file(os.path.join(HERE, "app.py"), default_timeout=30)
    at.run()
    return at


def test_app_runs_without_exception():
    at = _run()
    assert not at.exception, f"app levantou exceção: {at.exception}"
    # cabeçalho + 3 abas (Andamento, Classificação, Simulador)
    assert len(at.tabs) == 3, f"esperava 3 abas, obtive {len(at.tabs)}"
    assert any("Copa do Mundo 2026" in m.value for m in at.markdown), "cabeçalho ausente"
    print("ok  test_app_runs_without_exception")


def test_bracket_and_update_button_present():
    at = _run()
    # chaveamento visual (bandeiras via flagcdn) embutido no Andamento
    assert any("Chaveamento do Mata-mata" in m.value for m in at.markdown), \
        "seção do chaveamento ausente no Andamento"
    assert any('class="bk"' in m.value for m in at.markdown), "HTML do bracket ausente"
    # botão de atualizar API na página inicial
    assert any("Atualizar agora" in b.label for b in at.button), "botão de atualizar ausente"
    print("ok  test_bracket_and_update_button_present")


def test_metrics_present():
    at = _run()
    labels = [m.label for m in at.metric]
    assert "Fase atual" in labels, labels
    print(f"ok  test_metrics_present ({labels})")


if __name__ == "__main__":
    test_app_runs_without_exception()
    test_bracket_and_update_button_present()
    test_metrics_present()
    print("\nSMOKE TEST DA UI OK")
