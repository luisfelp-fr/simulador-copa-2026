"""
Gera data/thirdplace_allocation.json a partir da tabela oficial do Anexo C
--------------------------------------------------------------------------
Baixa o template renderizado da Wikipédia
(``Template:2026 FIFA World Cup third-place table``), localiza as 8 colunas das
vagas de 3º colocado (1A, 1B, 1D, 1E, 1G, 1I, 1K, 1L → jogos 79, 85, 81, 74, 82,
77, 87, 80) e grava, para cada combinação de 8 grupos classificados, a letra do
grupo cujo 3º colocado ocupa cada vaga (na ordem de ``THIRD_SLOTS``).

Uso:  python scripts/build_thirdplace_table.py

É um passo OPCIONAL/único: sem este arquivo, o app usa o emparelhamento de
reserva (que respeita os clusters de cada vaga).
"""
from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser

import requests

# permite importar tournament_data ao rodar de qualquer lugar
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tournament_data as td  # noqa: E402

URL = ("https://en.wikipedia.org/w/index.php"
       "?title=Template:2026_FIFA_World_Cup_third-place_table&action=render")

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "thirdplace_allocation.json")

# As 8 ÚLTIMAS células de cada linha são as vagas de 3º, nesta ordem de coluna
# (cabeçalho da Wikipédia: "1A vs", "1B vs", ...). Cada célula é tipo "3E".
COL_WINNERS = ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]
# rótulo do vencedor -> número do jogo da vaga de 3º
WINNER_TO_SLOT = {"1E": 74, "1I": 77, "1A": 79, "1L": 80,
                  "1D": 81, "1G": 82, "1B": 85, "1K": 87}
_CELL_RE = re.compile(r"^3\s*[A-L]$")


class _TableParser(HTMLParser):
    """Extrai as linhas (listas de células de texto) das tabelas wikitable."""

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "table" and "wikitable" in (ad.get("class") or ""):
            self._in_table = True
            self.tables.append([])
        elif tag == "tr" and self._in_table:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._in_table = False
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _letter(cell: str) -> str | None:
    found = re.findall(r"[A-L]", cell.upper())
    return found[-1] if found else None


def main() -> int:
    print(f"Baixando {URL} ...")
    resp = requests.get(URL, timeout=20, headers={"User-Agent": "copa2026-build/1.0"})
    resp.raise_for_status()

    parser = _TableParser()
    parser.feed(resp.text)
    if not parser.tables:
        print("ERRO: nenhuma wikitable encontrada.")
        return 2

    table = max(parser.tables, key=len)  # a maior é a das 495 linhas

    slot_order = td.THIRD_SLOTS  # [74,77,79,80,81,82,85,87]
    allocation: dict[str, list[str]] = {}
    bad = 0
    for row in table:
        if len(row) < 8:
            continue
        cells = [c.strip() for c in row[-8:]]            # 8 últimas células = vagas
        if not all(_CELL_RE.match(c) for c in cells):    # ignora cabeçalhos/sub-linhas
            continue
        letters = [_letter(c) for c in cells]
        if len(set(letters)) != 8:
            continue
        # coluna i corresponde ao vencedor COL_WINNERS[i] -> vaga (nº de jogo)
        slot_letter = {WINNER_TO_SLOT[COL_WINNERS[i]]: letters[i] for i in range(8)}
        for no, lt in slot_letter.items():
            if lt not in td.THIRD_CLUSTERS[no]:
                bad += 1
        key = "".join(sorted(letters))
        allocation[key] = [slot_letter[no] for no in slot_order]

    print(f"Linhas válidas: {len(allocation)} (esperado 495). Violações de cluster: {bad}.")
    if len(allocation) < 400:
        print("AVISO: poucas linhas — o app continuará usando a reserva onde faltar.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(allocation, fh, ensure_ascii=False)
    print(f"Gravado: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
