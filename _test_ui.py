"""
Smoke test da interface via streamlit.testing (sem navegador, sem rede).
Executar:  python _test_ui.py
"""
from __future__ import annotations

import os
import sys

from streamlit.testing.v1 import AppTest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _run():
    at = AppTest.from_file(os.path.join(HERE, "app.py"), default_timeout=30)
    at.run()
    return at


def test_app_runs_without_exception():
    at = _run()
    assert not at.exception, f"app levantou exceção: {at.exception}"
    # cabeçalho + 5 abas presentes
    assert len(at.tabs) == 5, f"esperava 5 abas, obtive {len(at.tabs)}"
    assert any("Copa do Mundo 2026" in m.value for m in at.markdown), "cabeçalho ausente"
    print("ok  test_app_runs_without_exception")


def test_metrics_present():
    at = _run()
    labels = [m.label for m in at.metric]
    assert "Fase atual" in labels, labels
    print(f"ok  test_metrics_present ({labels})")


if __name__ == "__main__":
    test_app_runs_without_exception()
    test_metrics_present()
    print("\nSMOKE TEST DA UI OK")
