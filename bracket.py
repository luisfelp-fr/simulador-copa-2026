"""
Chaveamento visual do mata-mata (HTML/CSS) com bandeiras
--------------------------------------------------------
Gera um "esquema de chaveamento" em colunas (Dezesseis-avos → Final), com a
bandeira de cada seleção, o placar e o vencedor destacado. Renderizado no app
via ``st.markdown(..., unsafe_allow_html=True)``.

Recebe o dicionário ``{nº: KOGame}`` produzido por ``knockout.compute_knockout``
e não depende de Streamlit (lógica pura de montagem de string).
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


def _match_card(g) -> str:
    win = g.winner_code() if (g.played and g.resolved) else None
    home = _team_row(g.home_code, g.home_label, g.home_goals,
                     win is not None and win == g.home_code)
    away = _team_row(g.away_code, g.away_label, g.away_goals,
                     win is not None and win == g.away_code)
    extra = ""
    if g.played and g.home_goals == g.away_goals and g.shootout_winner:
        extra = (f'<div class="so">pênaltis: '
                 f'{html.escape(td.name_of(g.shootout_winner))}</div>')
    return f'<div class="mt"><span class="no">{g.no}</span>{home}{away}{extra}</div>'


def _css() -> str:
    p, pd = COLORS["primary"], COLORS["primary_dark"]
    sec = COLORS["secondary"]
    return f"""
<style>
.bk-wrap {{ overflow-x:auto; padding:6px 2px 14px; }}
.bk {{ display:flex; gap:18px; align-items:stretch; min-width:max-content; }}
.bk .rd {{ display:flex; flex-direction:column; justify-content:space-around;
          gap:10px; min-width:188px; }}
.bk .rt {{ font-weight:700; font-size:.82rem; color:{p}; text-align:center;
          text-transform:uppercase; letter-spacing:.04em; margin-bottom:2px; }}
.bk .mt {{ position:relative; background:#fff; border:1px solid #e2e8f0;
          border-radius:10px; padding:6px 8px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.bk .no {{ position:absolute; top:-8px; left:8px; background:{p}; color:#fff;
          font-size:.62rem; font-weight:700; padding:1px 6px; border-radius:8px; }}
.bk .tm {{ display:flex; align-items:center; gap:7px; padding:3px 2px; }}
.bk .tm + .tm {{ border-top:1px dashed #eef2f7; }}
.bk .fl {{ width:22px; height:15px; object-fit:cover; border-radius:2px;
          box-shadow:0 0 0 1px rgba(0,0,0,.08); flex:0 0 auto; }}
.bk .fl.ph {{ background:#e2e8f0; }}
.bk .nm {{ flex:1 1 auto; font-size:.82rem; color:{COLORS['dark']};
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.bk .sc {{ font-weight:700; font-size:.85rem; color:{p}; min-width:14px;
          text-align:right; }}
.bk .win .nm {{ font-weight:800; color:{pd}; }}
.bk .win {{ background:linear-gradient(90deg,{sec}22,transparent); border-radius:6px; }}
.bk .so {{ font-size:.66rem; color:{COLORS['gray']}; text-align:right;
          margin-top:2px; }}
.bk-third {{ margin-top:14px; max-width:210px; }}
</style>"""


def bracket_html(games: dict) -> str:
    """HTML completo do chaveamento (colunas + disputa de 3º lugar)."""
    cols = []
    for stage in _STAGES:
        nos = sorted(n for n, g in games.items() if g.stage == stage)
        cards = "".join(_match_card(games[n]) for n in nos)
        cols.append(f'<div class="rd"><div class="rt">{_STAGE_TITLES[stage]}</div>{cards}</div>')

    third = games.get(103)
    third_html = ""
    if third is not None:
        third_html = (
            f'<div class="bk bk-third"><div class="rd">'
            f'<div class="rt">Disputa de 3º lugar</div>{_match_card(third)}'
            f'</div></div>'
        )

    return (f'{_css()}<div class="bk-wrap"><div class="bk">{"".join(cols)}</div>'
            f'{third_html}</div>')
