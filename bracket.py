"""
Chaveamento visual do mata-mata (HTML/CSS) com bandeiras
--------------------------------------------------------
Gera um "esquema de chaveamento" em árvore (Dezesseis-avos → Final), com a
bandeira de cada seleção, o placar, o vencedor destacado e **linhas conectoras**
ligando cada confronto ao da fase seguinte — no estilo de uma tabela oficial.
Renderizado no app via ``st.markdown(..., unsafe_allow_html=True)``.

Geometria dos conectores (CSS puro): cada coluna ocupa a MESMA altura e cada
jogo é um "slot" que preenche a coluna por igual (``flex:1``). Assim, o centro
de um jogo na fase N+1 cai exatamente no meio do par que o alimenta na fase N,
e a linha vertical que une o par tem altura = distância centro-a-centro
(``height:100%`` do slot). Recebe o dicionário ``{nº: KOGame}`` de
``knockout.compute_knockout`` e não depende de Streamlit.
"""
from __future__ import annotations

import html

import data_model as dm
import tournament_data as td
from branding import COLORS

# ordem das colunas do chaveamento principal (a disputa de 3º vai à parte)
_STAGES = [dm.R32, dm.R16, dm.QF, dm.SF, dm.FINAL]
_STAGE_TITLES = {
    dm.R32: "Dezesseis-avos",
    dm.R16: "Oitavas",
    dm.QF: "Quartas",
    dm.SF: "Semifinais",
    dm.FINAL: "Final",
}

_GAP = 26  # espaço horizontal (px) entre colunas — onde moram os conectores


def _flag(code: str | None) -> str:
    url = td.flag_url(code, 40)
    if url:
        return f'<img class="fl" src="{url}" alt="" loading="lazy">'
    return '<span class="fl ph"></span>'


def _team_row(code: str | None, label: str, goals, winner: bool) -> str:
    name = html.escape(label or "—")
    score = "" if goals is None else f'<span class="sc">{goals}</span>'
    cls = "tm win" if winner else "tm"
    return f'<div class="{cls}">{_flag(code)}<span class="nm">{name}</span>{score}</div>'


def _match(g) -> str:
    win = g.winner_code() if (g.played and g.resolved) else None
    home = _team_row(g.home_code, g.home_label, g.home_goals,
                     win is not None and win == g.home_code)
    away = _team_row(g.away_code, g.away_label, g.away_goals,
                     win is not None and win == g.away_code)
    extra = ""
    if g.played and g.home_goals == g.away_goals and g.shootout_winner:
        extra = (f'<div class="so">pênaltis: '
                 f'{html.escape(td.name_of(g.shootout_winner))}</div>')
    return (f'<div class="mt"><div class="card">'
            f'<span class="no">{g.no}</span>{home}{away}{extra}</div></div>')


def _css() -> str:
    p, pdk = COLORS["primary"], COLORS["primary_dark"]
    sec, line = COLORS["secondary"], "#cbd5e1"
    g = _GAP
    return f"""
<style>
.bk-wrap {{ overflow-x:auto; padding:10px 4px 18px; }}
.bk {{ display:flex; align-items:stretch; min-width:max-content; }}
.bk .rd {{ display:flex; flex-direction:column; width:190px; flex:0 0 190px; }}
.bk .rd:not(:last-child) {{ margin-right:{g}px; }}
.bk .rt {{ font-weight:700; font-size:.78rem; color:{p}; text-align:center;
          text-transform:uppercase; letter-spacing:.04em; padding-bottom:6px; }}
.bk .matches {{ flex:1; display:flex; flex-direction:column; }}
.bk .mt {{ flex:1; display:flex; flex-direction:column; justify-content:center;
          position:relative; }}
.bk .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:10px;
          margin:5px 0; padding:6px 8px; box-shadow:0 1px 3px rgba(0,0,0,.06);
          position:relative; }}
.bk .no {{ position:absolute; top:-8px; left:8px; background:{p}; color:#fff;
          font-size:.6rem; font-weight:700; padding:1px 6px; border-radius:8px; }}
.bk .tm {{ display:flex; align-items:center; gap:7px; padding:3px 2px; }}
.bk .tm + .tm {{ border-top:1px dashed #eef2f7; }}
.bk .fl {{ width:22px; height:15px; object-fit:cover; border-radius:2px;
          box-shadow:0 0 0 1px rgba(0,0,0,.08); flex:0 0 auto; }}
.bk .fl.ph {{ background:#e2e8f0; }}
.bk .nm {{ flex:1 1 auto; font-size:.8rem; color:{COLORS['dark']};
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.bk .sc {{ font-weight:700; font-size:.84rem; color:{p}; min-width:14px;
          text-align:right; }}
.bk .win .nm {{ font-weight:800; color:{pdk}; }}
.bk .win {{ background:linear-gradient(90deg,{sec}22,transparent); border-radius:6px; }}
.bk .so {{ font-size:.64rem; color:{COLORS['gray']}; text-align:right; margin-top:2px; }}
/* conectores: linha horizontal de cada jogo + vertical unindo o par ------ */
.bk .rd:not(:last-child) .mt::after {{ content:""; position:absolute; left:100%;
          top:50%; width:{g}px; height:2px; background:{line}; }}
.bk .rd:not(:last-child) .mt:nth-of-type(odd)::before {{ content:""; position:absolute;
          left:calc(100% + {g}px); top:50%; width:2px; height:100%; background:{line}; }}
.bk-third {{ margin-top:16px; }}
.bk-third .card {{ max-width:200px; }}
</style>"""


def _column(stage: str, games: dict) -> str:
    nos = sorted(n for n, gm in games.items() if gm.stage == stage)
    cards = "".join(_match(games[n]) for n in nos)
    return (f'<div class="rd"><div class="rt">{_STAGE_TITLES[stage]}</div>'
            f'<div class="matches">{cards}</div></div>')


def bracket_html(games: dict) -> str:
    """HTML completo do chaveamento (colunas conectadas + disputa de 3º lugar)."""
    cols = "".join(_column(stage, games) for stage in _STAGES)

    third = games.get(103)
    third_html = ""
    if third is not None:
        third_html = (
            f'<div class="bk bk-third"><div class="rd">'
            f'<div class="rt">Disputa de 3º lugar</div>'
            f'<div class="matches">{_match(third)}</div></div></div>'
        )

    return (f'{_css()}<div class="bk-wrap"><div class="bk">{cols}</div>'
            f'{third_html}</div>')
