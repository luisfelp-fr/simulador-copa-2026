"""
Simulador "e-se" — sobrepõe placares hipotéticos ao estado real
---------------------------------------------------------------
O overlay de simulação NUNCA grava em ``results.json``: ele apenas combina os
resultados reais (imutáveis) com os palpites do usuário e recalcula tabelas e
chaveamento.

Regras (comportamento progressivo):
    * Jogos reais já disputados são imutáveis (não entram como editáveis).
    * Fase de grupos em andamento  -> simulam-se os jogos de grupo restantes;
      o mata-mata aparece como PROJEÇÃO.
    * Fase de grupos concluída     -> grupos travados; simula-se o mata-mata.
"""
from __future__ import annotations

from dataclasses import replace

import standings
import knockout
from data_model import Match


# --- fase de grupos ---------------------------------------------------------
def editable_group_matches(canonical: list[Match]) -> list[Match]:
    """Jogos de grupo ainda NÃO disputados (os únicos simuláveis)."""
    return [m for m in canonical if not m.played]


def effective_group_matches(canonical: list[Match],
                            overrides: dict[str, tuple]) -> list[Match]:
    """Combina jogos reais (mantidos) com placares simulados dos jogos futuros."""
    eff: list[Match] = []
    for m in canonical:
        if m.played:
            eff.append(m)
            continue
        ov = overrides.get(m.id)
        if ov and ov[0] is not None and ov[1] is not None:
            eff.append(replace(m, home_goals=int(ov[0]), away_goals=int(ov[1]),
                               status="finished", source="sim"))
        else:
            eff.append(replace(m))  # cópia, sem placar
    return eff


def simulate_groups(canonical: list[Match], overrides: dict[str, tuple], teams):
    """Recalcula tabelas com o overlay aplicado.

    Returns:
        (tables, effective_matches)
    """
    eff = effective_group_matches(canonical, overrides)
    tables = standings.compute_all_tables(eff, teams)
    return tables, eff


# --- mata-mata --------------------------------------------------------------
def effective_ko_results(real_ko: dict[str, dict],
                         overrides: dict[str, tuple]) -> dict[str, dict]:
    """Combina resultados reais do mata-mata com palpites (sem sobrescrever reais)."""
    merged = dict(real_ko)
    for no, ov in overrides.items():
        if str(no) in real_ko:
            continue  # jogo real é imutável
        if ov and ov[0] is not None and ov[1] is not None:
            merged[str(no)] = {"hg": int(ov[0]), "ag": int(ov[1]),
                               "so": ov[2] if len(ov) > 2 else None, "source": "sim"}
    return merged


def project_knockout(tables, group_matches, teams, ko_results, allocation):
    """Atalho para ``knockout.compute_knockout`` (mantém a UI enxuta)."""
    return knockout.compute_knockout(tables, group_matches, teams,
                                     ko_results, allocation)


# --- comparação real x simulado ---------------------------------------------
def qualifiers(tables) -> dict[str, list[str]]:
    """Top-2 de cada grupo (códigos), a partir de um conjunto de tabelas."""
    return {g: [r.team for r in rows[:2]] for g, rows in tables.items()}
