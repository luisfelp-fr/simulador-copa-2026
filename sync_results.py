#!/usr/bin/env python3
"""
sync_results.py — traz os resultados REAIS da Copa para o app (sem chave)
=========================================================================
Busca os jogos já disputados numa API pública (ESPN, *sem chave*) e grava em
``data/results.json`` — de onde o painel (``app.py``) e a API (``api.py``) leem.

Rode na SUA máquina (precisa de internet aberta para ``site.api.espn.com``):

    python sync_results.py            # diagnóstico: o que a API trouxe e o que casou
    python sync_results.py --save     # grava os resultados em data/results.json
    python sync_results.py --raw      # lista TODOS os confrontos retornados pela API
                                      # (use para comparar com o seed do código)

Importante:
    * NÃO exige nenhuma chave de API.
    * Sem internet, ou sem jogos disputados, o script EXPLICA o que houve —
      nunca inventa placares.
    * Se a ESPN devolver seleções que não existem no seed (``tournament_data.py``),
      o script avisa: é o sinal de que o sorteio do código não bate com a Copa
      real e precisa ser corrigido (nenhuma API consegue popular a tabela nesse
      caso).
"""
from __future__ import annotations

import argparse
import sys

import data_sources
import state


def _diagnose(group_records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separa os registros de grupo entre os que casam com o calendário-semente
    e os que não casam."""
    idx = state._fixture_index()
    matched, unmatched = [], []
    for rec in group_records:
        key = (rec["group"], frozenset({rec["home"], rec["away"]}))
        (matched if key in idx else unmatched).append(rec)
    return matched, unmatched


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Sincroniza resultados reais da Copa 2026 (API pública, sem chave)."
    )
    p.add_argument("--save", action="store_true",
                   help="grava os resultados em data/results.json")
    p.add_argument("--raw", action="store_true",
                   help="lista todos os confrontos retornados pela API")
    args = p.parse_args(argv)

    print("Buscando resultados na ESPN (API pública, sem chave)...\n")
    try:
        games = data_sources.fetch_espn_games()
    except Exception as exc:  # noqa: BLE001
        print(f"✖ Não foi possível acessar a API: {exc}\n")
        print("  • Confirme que a máquina tem internet e alcança site.api.espn.com")
        print("  • Atrás de proxy/firewall corporativo? A porta 443 precisa estar liberada.")
        return 2

    completed = [g for g in games if g["completed"]]
    print(f"A API retornou {len(games)} jogo(s) — {len(completed)} concluído(s).")

    if args.raw:
        print("\nConfrontos retornados (nome da fonte -> [código no seed]):")
        for g in games:
            mark = "✔" if g["completed"] else "·"
            hs = g["hg"] if g["hg"] is not None else "-"
            as_ = g["ag"] if g["ag"] is not None else "-"
            hc, ac = g["home"] or "??", g["away"] or "??"
            print(f"  {mark} {g['home_name']} [{hc}] {hs} x {as_} {g['away_name']} [{ac}]")
        print("\n  [??] = a ESPN traz uma seleção que NÃO existe no seu seed "
              "(tournament_data.py).")

    records = data_sources._normalize_games(games)
    group_recs = [r for r in records if r["stage"] == "group"]
    ko_recs = [r for r in records if r["stage"] != "group"]
    matched, unmatched = _diagnose(group_recs)

    print(f"\nReconhecidos e concluídos: {len(records)} "
          f"(grupos: {len(group_recs)}, mata-mata: {len(ko_recs)}).")
    print(f"Casaram com o calendário do app: {len(matched)} de {len(group_recs)}.")

    unresolved = [g for g in completed if not g["home"] or not g["away"]]
    if unresolved:
        print(f"\n⚠ {len(unresolved)} jogo(s) concluído(s) com seleção NÃO reconhecida "
              "no seed:")
        for g in unresolved[:30]:
            print(f"    {g['home_name']}  x  {g['away_name']}")
        print("  → Provável divergência entre tournament_data.py e a Copa real,")
        print("    ou nome a acrescentar nos aliases de data_sources.py.")

    if unmatched:
        print(f"\nℹ {len(unmatched)} jogo(s) de grupo reconhecido(s) mas fora do "
              "calendário-semente (confronto/grupo diferente do esperado):")
        for r in unmatched[:30]:
            print(f"    Grupo {r['group']}: {r['home']} {r['hg']} x {r['ag']} {r['away']}")

    if not records:
        print("\nNenhum resultado disponível ainda — ou os jogos não foram disputados,")
        print("ou a competição ainda não está populada nesta fonte.")

    if args.save:
        results = state.load_results()
        n = state.import_api_results(results, records)
        state.save_results(results)
        print(f"\n💾 {n} resultado(s) gravado(s) em {state.RESULTS_PATH}.")
        print("   Veja no painel (streamlit run app.py) ou na API (uvicorn api:app).")
    else:
        print("\n(Somente diagnóstico — rode com --save para gravar em data/results.json.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
