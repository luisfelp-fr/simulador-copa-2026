"""
Cálculo de classificação — lógica pura (sem Streamlit)
------------------------------------------------------
Monta a tabela de cada grupo a partir das partidas e aplica os critérios de
desempate oficiais da FIFA 2026, e ranqueia os 3º colocados para definir os 8
melhores que avançam.

Ordem de desempate dentro de um grupo (entre times empatados em PONTOS):
    1. Confronto direto: pontos
    2. Confronto direto: saldo de gols
    3. Confronto direto: gols marcados
    4. Saldo de gols geral
    5. Gols marcados geral
    6. (fair-play — OMITIDO: sem dados de cartões nas fontes gratuitas)
    7. Ranking FIFA (menor = melhor)

Quando o confronto direto separa apenas parte do grupo, os critérios são
reaplicados recursivamente ao subconjunto ainda empatado (regra oficial).

Para os 3º colocados (de grupos distintos, sem confronto direto):
    pontos -> saldo -> gols -> ranking FIFA
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby

from data_model import Match, StandingRow, Team


@dataclass
class _Acc:
    """Acumulador de estatísticas de um time num conjunto de partidas."""
    played: int = 0
    won: int = 0
    draw: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @property
    def points(self) -> int:
        return self.won * 3 + self.draw


def _accumulate(codes: list[str], matches: list[Match]) -> dict[str, _Acc]:
    """Estatísticas de cada código considerando apenas partidas JOGADAS cujos
    dois times estão em ``codes``."""
    cset = set(codes)
    acc = {c: _Acc() for c in codes}
    for m in matches:
        if not m.played or m.home not in cset or m.away not in cset:
            continue
        h, a = acc[m.home], acc[m.away]
        h.played += 1
        a.played += 1
        h.gf += m.home_goals
        h.ga += m.away_goals
        a.gf += m.away_goals
        a.ga += m.home_goals
        if m.home_goals > m.away_goals:
            h.won += 1
            a.lost += 1
        elif m.away_goals > m.home_goals:
            a.won += 1
            h.lost += 1
        else:
            h.draw += 1
            a.draw += 1
    return acc


def _resolve_tie(codes: list[str], matches: list[Match],
                 overall: dict[str, _Acc], teams: dict[str, Team]) -> list[str]:
    """Ordena um conjunto de times empatados em PONTOS aplicando confronto
    direto recursivamente, depois saldo/gols geral e ranking FIFA."""
    if len(codes) == 1:
        return list(codes)

    h2h = _accumulate(codes, matches)

    def hkey(c: str):
        h = h2h[c]
        return (-h.points, -h.gd, -h.gf)

    codes_sorted = sorted(codes, key=hkey)
    result: list[str] = []
    for _k, grp_iter in groupby(codes_sorted, key=hkey):
        grp = list(grp_iter)
        if len(grp) == 1:
            result.extend(grp)
        elif len(grp) == len(codes):
            # confronto direto não separou ninguém -> saldo/gols geral, ranking
            def okey(c: str):
                s = overall[c]
                return (-s.gd, -s.gf, teams[c].fifa_rank if c in teams else 999)
            result.extend(sorted(grp, key=okey))
        else:
            # parte foi separada; reaplica recursivamente ao subgrupo restante
            result.extend(_resolve_tie(grp, matches, overall, teams))
    return result


def order_group(codes: list[str], matches: list[Match],
                teams: dict[str, Team]) -> list[str]:
    """Devolve os códigos do grupo ordenados do 1º ao último colocado."""
    overall = _accumulate(codes, matches)

    # ordena por pontos; empates em pontos vão para o desempate
    by_points = sorted(codes, key=lambda c: -overall[c].points)
    result: list[str] = []
    for _pts, grp_iter in groupby(by_points, key=lambda c: overall[c].points):
        grp = list(grp_iter)
        if len(grp) == 1:
            result.extend(grp)
        else:
            result.extend(_resolve_tie(grp, matches, overall, teams))
    return result


def compute_group_table(group: str, matches: list[Match],
                        teams: dict[str, Team]) -> list[StandingRow]:
    """Tabela ordenada (1º..4º) de um grupo. ``matches`` deve conter (ao menos)
    as partidas desse grupo; outras são ignoradas."""
    codes = [c for c in teams if teams[c].group == group]
    # garante ordem estável inicial pela ordem do sorteio, se disponível
    grp_matches = [m for m in matches if m.group == group]
    overall = _accumulate(codes, grp_matches)
    ordered = order_group(codes, grp_matches, teams)

    rows: list[StandingRow] = []
    for pos, c in enumerate(ordered, start=1):
        s = overall[c]
        rows.append(StandingRow(
            group=group, position=pos, team=c,
            played=s.played, won=s.won, draw=s.draw, lost=s.lost,
            gf=s.gf, ga=s.ga, gd=s.gd, points=s.points,
            qualified=("1º" if pos == 1 else "2º" if pos == 2 else ""),
        ))
    return rows


def compute_all_tables(matches: list[Match],
                       teams: dict[str, Team]) -> dict[str, list[StandingRow]]:
    """Tabelas de todos os grupos presentes em ``teams``."""
    groups = sorted({t.group for t in teams.values()})
    return {g: compute_group_table(g, matches, teams) for g in groups}


def group_complete(group: str, matches: list[Match]) -> bool:
    """True se todas as 6 partidas do grupo já foram disputadas."""
    grp = [m for m in matches if m.group == group]
    return len(grp) >= 6 and all(m.played for m in grp)


def best_third_placed(tables: dict[str, list[StandingRow]],
                      teams: dict[str, Team], n: int = 8
                      ) -> tuple[list[StandingRow], set[str]]:
    """Ranqueia os 3º colocados de todos os grupos e devolve
    ``(lista_ordenada, grupos_classificados)``.

    Marca cada 3º como classificado/eliminado no campo ``qualified``.
    Só faz sentido quando todos os grupos estão completos, mas funciona com
    dados parciais (usa o que houver).
    """
    thirds = [rows[2] for rows in tables.values() if len(rows) >= 3]

    def key(r: StandingRow):
        return (-r.points, -r.gd, -r.gf,
                teams[r.team].fifa_rank if r.team in teams else 999)

    ranked = sorted(thirds, key=key)
    qualifying = {r.group for r in ranked[:n]}
    for i, r in enumerate(ranked):
        if i < n:
            r.qualified = "3º (classificado)"
        else:
            r.qualified = "3º (eliminado)"
    return ranked, qualifying
