"""
Painel & Simulador da Copa do Mundo 2026 — aplicação Streamlit
--------------------------------------------------------------
Cinco abas: Andamento, Classificação, Mata-mata, Simulador e Dados/Admin.
A lógica de classificação/chaveamento fica em módulos puros (``standings.py``,
``knockout.py``); aqui ficam apenas a interface e a orquestração de estado.

Executar:  streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

import branding
import bracket
import data_model as dm
import data_sources
import knockout
import standings
import state
import simulator
import tooltips
import tournament_data as td

st.set_page_config(page_title="Copa do Mundo 2026", page_icon="🏆", layout="wide")

NAME = td.name_of
KO_STAGE_ORDER = [dm.R32, dm.R16, dm.QF, dm.SF, dm.THIRD, dm.FINAL]

AUTO_SYNC_MINUTES = 15  # re-busca a API no máximo a cada N minutos


# --------------------------------------------------------------------------- #
# Atualização automática a partir da API
# --------------------------------------------------------------------------- #
def read_api_keys() -> tuple[str | None, str | None]:
    """Chaves das fontes (secrets ou variáveis de ambiente). Tolera a ausência
    total de secrets — caso do usuário keyless (só ESPN)."""
    fd = af = None
    try:
        fd = st.secrets.get("football_data", {}).get("token")
    except Exception:  # noqa: BLE001 - sem arquivo de secrets
        fd = None
    try:
        af = st.secrets.get("api_football", {}).get("key")
    except Exception:  # noqa: BLE001
        af = None
    return (fd or os.environ.get("FOOTBALL_DATA_TOKEN"),
            af or os.environ.get("API_FOOTBALL_KEY"))


def minutes_since_sync(results: dict) -> float:
    """Minutos desde a última atualização automática (inf se nunca)."""
    ts = results.get("synced_at")
    if not ts:
        return float("inf")
    try:
        return (datetime.now() - datetime.fromisoformat(ts)).total_seconds() / 60
    except ValueError:
        return float("inf")


def run_api_sync(results: dict, fd_token, af_key) -> str:
    """Busca da API, importa (sem sobrescrever edições manuais) e carimba o
    horário da sincronização. Devolve a mensagem de status."""
    records, msg = data_sources.fetch_results(fd_token, af_key)
    n = state.import_api_results(results, records)
    results["synced_at"] = datetime.now().isoformat(timespec="seconds")
    state.save_results(results)
    return f"{msg} ({n} jogos atualizados)"


# --------------------------------------------------------------------------- #
# Helpers de exibição
# --------------------------------------------------------------------------- #
def fmt_date(iso: str) -> str:
    if not iso or len(iso) < 10:
        return ""
    return f"{iso[8:10]}/{iso[5:7]}"


def group_table_df(rows, qualifying_groups: set[str]) -> pd.DataFrame:
    data = []
    for r in rows:
        if r.position <= 2:
            mark = "🟢"
        elif r.position == 3 and r.group in qualifying_groups:
            mark = "🟡"
        else:
            mark = "⚪"
        data.append({
            "": mark, "#": r.position, "Seleção": NAME(r.team),
            "P": r.points, "J": r.played, "V": r.won, "E": r.draw, "D": r.lost,
            "GP": r.gf, "GC": r.ga, "SG": f"{r.gd:+d}",
        })
    return pd.DataFrame(data)


def game_line(g) -> str:
    """Linha em markdown de um jogo do mata-mata, com vencedor em negrito."""
    hl, al = g.home_label, g.away_label
    if g.played:
        win = g.winner_code()
        h = f"**{hl} {g.home_goals}**" if win and win == g.home_code else f"{hl} {g.home_goals}"
        a = f"**{g.away_goals} {al}**" if win and win == g.away_code else f"{g.away_goals} {al}"
        so = ""
        if g.home_goals == g.away_goals and g.shootout_winner:
            so = f"  _(pên.: {NAME(g.shootout_winner)})_"
        return f"`{g.no:>3}`  {h}  ×  {a}{so}"
    return f"`{g.no:>3}`  {hl}  ×  {al}"


# --------------------------------------------------------------------------- #
# Estado canônico
# --------------------------------------------------------------------------- #
if "results" not in st.session_state:
    st.session_state.results = state.load_results()
results = st.session_state.results

fd_token, af_key = read_api_keys()

# --- Atualização automática ao abrir o site (e a cada AUTO_SYNC_MINUTES) -----
# Busca apenas quando faz sentido: ao iniciar a sessão ou quando os dados
# passam de AUTO_SYNC_MINUTES — nunca em cada interação. Falhas de rede são
# silenciosas (fetch_results trata e o app segue com o que já tem).
auto_on = st.session_state.get("auto_sync_enabled", True)
_autosync_off = os.environ.get("COPA_DISABLE_AUTOSYNC") == "1"
_mins = minutes_since_sync(results)
_new_session = not st.session_state.get("_session_synced")
if auto_on and not _autosync_off and (
        _mins >= AUTO_SYNC_MINUTES or (_new_session and _mins >= 1.0)):
    with st.spinner("Buscando resultados mais recentes da API..."):
        st.session_state._auto_sync_msg = run_api_sync(results, fd_token, af_key)
    st.session_state._session_synced = True

gmatches = state.group_matches(results)
tables = standings.compute_all_tables(gmatches, td.TEAMS)
ranked_thirds, qualifying_groups = standings.best_third_placed(tables, td.TEAMS)
alloc = knockout.load_allocation_table()
phase = state.compute_phase(gmatches)
played, total = state.progress(gmatches)

st.markdown(branding.header_html(), unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Jogos de grupo disputados", f"{played}/{total}")
c2.metric("Fase atual", "Fase de Grupos" if phase == "groups" else "Mata-mata")
c3.metric("Tabela 3º colocados (Anexo C)", "carregada" if alloc else "reserva (clusters)")

# Atualização da API direto na página inicial.
_cinfo, _cbtn = st.columns([4, 1])
with _cinfo:
    _synced = results.get("synced_at")
    _auto_msg = st.session_state.get("_auto_sync_msg")
    if _synced:
        _line = f"🔄 Última atualização: {_synced.replace('T', ' ')}"
        if _auto_msg:
            _line += f"  ·  {_auto_msg}"
        st.caption(_line)
    else:
        st.caption("🔄 Atualização automática ligada — ao abrir o site os "
                   "resultados são buscados na API.")
with _cbtn:
    if st.button("🔄 Atualizar agora", width="stretch"):
        with st.spinner("Buscando resultados..."):
            st.session_state._auto_sync_msg = run_api_sync(results, fd_token, af_key)
        st.rerun()

tab_and, tab_cla, tab_sim = st.tabs(
    ["🏆 Andamento", "📊 Classificação", "🎮 Simulador"]
)


# --------------------------------------------------------------------------- #
# Aba 1 — Andamento
# --------------------------------------------------------------------------- #
with tab_and:
    st.markdown(branding.section_title("Andamento da Competição"), unsafe_allow_html=True)
    st.caption(tooltips.HELP["fase"])

    finished = sorted([m for m in gmatches if m.played], key=lambda m: m.date, reverse=True)
    upcoming = sorted([m for m in gmatches if not m.played], key=lambda m: m.date)

    ca, cb = st.columns(2)
    with ca:
        st.markdown(branding.section_title("Resultados Recentes"), unsafe_allow_html=True)
        if finished:
            df = pd.DataFrame([{
                "Data": fmt_date(m.date), "Grupo": m.group,
                "Confronto": f"{NAME(m.home)} {m.home_goals} x {m.away_goals} {NAME(m.away)}",
                "Local": m.venue,
            } for m in finished[:10]])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.info("Nenhum jogo disputado ainda. Importe da API ou use o editor manual.")
    with cb:
        st.markdown(branding.section_title("Próximos Confrontos"), unsafe_allow_html=True)
        if upcoming:
            df = pd.DataFrame([{
                "Data": fmt_date(m.date), "Grupo": m.group,
                "Partida": f"{NAME(m.home)} x {NAME(m.away)}", "Local": m.venue,
            } for m in upcoming[:10]])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.success("Fase de grupos encerrada — confira o chaveamento abaixo!")

    # ---- Chaveamento do mata-mata (visual, com bandeiras) ------------------ #
    st.markdown(branding.section_title("Chaveamento do Mata-mata"), unsafe_allow_html=True)
    games = knockout.compute_knockout(tables, gmatches, td.TEAMS,
                                      state.ko_results(results), alloc)
    champ = knockout.champion(games)
    if champ:
        st.success(f"🏆 Campeão: **{NAME(champ)}**")
    if phase == "groups":
        st.caption("A fase de grupos ainda não terminou — os confrontos são "
                   "*projeções* (posições/3º colocados) até os 12 grupos se "
                   "encerrarem. Use o **Simulador** para testar cenários.")
    st.markdown(bracket.bracket_html(games), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Aba 2 — Classificação
# --------------------------------------------------------------------------- #
with tab_cla:
    st.markdown(branding.section_title("Classificação dos Grupos"), unsafe_allow_html=True)
    st.caption("🟢 classificado (top 2) · 🟡 3º colocado em zona de classificação · ⚪ eliminado/fora")

    cols = st.columns(3)
    for i, g in enumerate(td.GROUP_ORDER):
        with cols[i % 3]:
            st.markdown(f"**Grupo {g}**")
            st.dataframe(group_table_df(tables[g], qualifying_groups),
                         hide_index=True, width="stretch")

    st.markdown(branding.section_title("Ranking dos 3º Colocados"), unsafe_allow_html=True)
    st.caption(tooltips.HELP["terceiros"] + ("" if phase != "groups" else "  ⚠️ Parcial (fase de grupos em andamento)."))
    tdf = pd.DataFrame([{
        "Pos": i + 1, "Grupo": r.group, "Seleção": NAME(r.team),
        "P": r.points, "SG": f"{r.gd:+d}", "GP": r.gf,
        "Situação": "✅ Classificado" if i < 8 else "❌ Eliminado",
    } for i, r in enumerate(ranked_thirds)])
    st.dataframe(tdf, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# Aba 3 — Simulador
# --------------------------------------------------------------------------- #
with tab_sim:
    st.markdown(branding.section_title("Simulador 'e-se'"), unsafe_allow_html=True)

    if st.button("♻️ Resetar simulação"):
        for k in list(st.session_state.keys()):
            if k.startswith("sim_"):
                del st.session_state[k]
        st.rerun()

    if phase == "groups":
        # ---- Simulação da fase de grupos -------------------------------- #
        st.caption(tooltips.HELP["simulador_grupos"])
        editable = simulator.editable_group_matches(gmatches)
        base = pd.DataFrame([{
            "id": m.id, "Grupo": m.group, "Casa": NAME(m.home), "Fora": NAME(m.away),
            "Gols Casa": None, "Gols Fora": None,
        } for m in editable])

        edited = st.data_editor(
            base, hide_index=True, width="stretch", key="sim_groups_editor",
            disabled=["id", "Grupo", "Casa", "Fora"],
            column_config={
                "id": None,
                "Gols Casa": st.column_config.NumberColumn(min_value=0, step=1),
                "Gols Fora": st.column_config.NumberColumn(min_value=0, step=1),
            },
        )
        overrides = {}
        for _, row in edited.iterrows():
            hg, ag = row["Gols Casa"], row["Gols Fora"]
            if pd.notna(hg) and pd.notna(ag):
                overrides[row["id"]] = (int(hg), int(ag))

        sim_tables, eff = simulator.simulate_groups(gmatches, overrides, td.TEAMS)
        sim_thirds, sim_qualifying = standings.best_third_placed(sim_tables, td.TEAMS)

        st.markdown(branding.section_title("Classificação simulada"), unsafe_allow_html=True)
        scols = st.columns(3)
        real_q = simulator.qualifiers(tables)
        for i, g in enumerate(td.GROUP_ORDER):
            with scols[i % 3]:
                changed = simulator.qualifiers(sim_tables)[g] != real_q[g]
                st.markdown(f"**Grupo {g}** {'🔁' if changed else ''}")
                st.dataframe(group_table_df(sim_tables[g], sim_qualifying),
                             hide_index=True, width="stretch")

        st.markdown(branding.section_title("Projeção do mata-mata"), unsafe_allow_html=True)
        sim_games = knockout.compute_knockout(sim_tables, eff, td.TEAMS, {}, alloc)
        if all(standings.group_complete(g, eff) for g in td.GROUP_ORDER):
            st.markdown(bracket.bracket_html(sim_games), unsafe_allow_html=True)
        else:
            st.info("Preencha **todos** os jogos de grupo restantes para projetar o chaveamento completo.")

    else:
        # ---- Simulação do mata-mata ------------------------------------- #
        st.caption(tooltips.HELP["simulador_mata"])
        real_ko = state.ko_results(results)

        # lê palpites já existentes do session_state e recalcula iterativamente
        def collect_overrides():
            ov = {}
            for no in range(73, 105):
                h = st.session_state.get(f"sim_ko_{no}_h")
                a = st.session_state.get(f"sim_ko_{no}_a")
                so = st.session_state.get(f"sim_ko_{no}_so")
                if h is not None and a is not None:
                    ov[no] = (h, a, so if so not in (None, "—") else None)
            return ov

        overrides = collect_overrides()
        eff_ko = simulator.effective_ko_results(real_ko, overrides)
        sim_games = knockout.compute_knockout(tables, gmatches, td.TEAMS, eff_ko, alloc)

        champ = knockout.champion(sim_games)
        if champ:
            st.success(f"🏆 Campeão simulado: **{NAME(champ)}**")

        # chaveamento visual refletindo os palpites atuais
        st.markdown(bracket.bracket_html(sim_games), unsafe_allow_html=True)

        st.markdown(branding.section_title("Preencha os confrontos"), unsafe_allow_html=True)
        for stage in KO_STAGE_ORDER:
            st.markdown(f"**{dm.STAGE_LABELS[stage]}**")
            for no in sorted(g.no for g in sim_games.values() if g.stage == stage):
                g = sim_games[no]
                if str(no) in real_ko:
                    st.markdown(game_line(g) + "  ·  _resultado real_")
                    continue
                if not g.resolved:
                    st.markdown(game_line(g))
                    continue
                cc = st.columns([3, 1, 1, 2])
                cc[0].markdown(f"`{no}` {g.home_label} × {g.away_label}")
                cc[1].number_input("Casa", min_value=0, step=1, value=None,
                                   key=f"sim_ko_{no}_h", label_visibility="collapsed")
                cc[2].number_input("Fora", min_value=0, step=1, value=None,
                                   key=f"sim_ko_{no}_a", label_visibility="collapsed")
                h = st.session_state.get(f"sim_ko_{no}_h")
                a = st.session_state.get(f"sim_ko_{no}_a")
                if h is not None and a is not None and h == a:
                    cc[3].selectbox("Pênaltis", ["—", g.home_label, g.away_label],
                                    key=f"sim_ko_{no}_so_label", label_visibility="collapsed")
                    lbl = st.session_state.get(f"sim_ko_{no}_so_label")
                    st.session_state[f"sim_ko_{no}_so"] = (
                        g.home_code if lbl == g.home_label
                        else g.away_code if lbl == g.away_label else None)
