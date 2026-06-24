"""
Camada de dados externa (busca automática de resultados) — best-effort
----------------------------------------------------------------------
Adapters para APIs gratuitas de futebol. A fonte primária é a football-data.org
(competição ``WC``); a reserva é a API-Football (liga 1, season 2026). Ambas são
opcionais: sem chave/sem internet, as funções devolvem ``[]`` e o app segue
funcionando com a entrada manual.

As chaves ficam em ``st.secrets`` (nunca no código):

    [football_data]
    token = "sua-chave"

    [api_football]
    key = "sua-chave"

Cada função devolve uma lista de *resultados normalizados*:
    {"group": "C", "home": "BRA", "away": "MAR", "hg": 1, "ag": 1, "stage": "group"}
que ``state.import_api_results`` casa com os jogos-semente.
"""
from __future__ import annotations

import unicodedata

try:
    import requests
except Exception:  # pragma: no cover - requests faz parte do requirements
    requests = None

import tournament_data as td

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

# nomes em inglês / apelidos por código FIFA, para casar respostas de API
_EN_ALIASES = {
    "MEX": ["mexico"], "RSA": ["south africa"], "KOR": ["south korea", "korea republic", "korea"],
    "CZE": ["czechia", "czech republic"], "CAN": ["canada"], "SUI": ["switzerland"],
    "QAT": ["qatar"], "BIH": ["bosnia and herzegovina", "bosnia"], "BRA": ["brazil"],
    "MAR": ["morocco"], "SCO": ["scotland"], "HAI": ["haiti"], "USA": ["united states", "usa"],
    "PAR": ["paraguay"], "AUS": ["australia"], "TUR": ["turkiye", "turkey"], "GER": ["germany"],
    "ECU": ["ecuador"], "CIV": ["ivory coast", "cote d'ivoire", "cote divoire"], "CUW": ["curacao"],
    "NED": ["netherlands", "holland"], "JPN": ["japan"], "SWE": ["sweden"], "TUN": ["tunisia"],
    "BEL": ["belgium"], "EGY": ["egypt"], "IRN": ["iran", "ir iran"], "NZL": ["new zealand"],
    "ESP": ["spain"], "URU": ["uruguay"], "KSA": ["saudi arabia"], "CPV": ["cape verde", "cabo verde"],
    "FRA": ["france"], "SEN": ["senegal"], "NOR": ["norway"], "IRQ": ["iraq"], "ARG": ["argentina"],
    "AUT": ["austria"], "ALG": ["algeria"], "JOR": ["jordan"], "POR": ["portugal"], "COL": ["colombia"],
    "UZB": ["uzbekistan"], "COD": ["dr congo", "congo dr", "democratic republic of congo"],
    "ENG": ["england"], "CRO": ["croatia"], "GHA": ["ghana"], "PAN": ["panama"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


_ALIAS_TO_CODE: dict[str, str] = {}
for _code, _names in _EN_ALIASES.items():
    _ALIAS_TO_CODE[_norm(_code)] = _code
    for _n in _names:
        _ALIAS_TO_CODE[_norm(_n)] = _code
for _code, _t in td.TEAMS.items():  # também aceita o nome PT-BR
    _ALIAS_TO_CODE[_norm(_t.name)] = _code


def code_from(name_or_tla: str | None) -> str | None:
    """Tenta resolver um nome/código de time para o nosso código FIFA."""
    if not name_or_tla:
        return None
    key = _norm(name_or_tla)
    if key.upper() in td.TEAMS:
        return key.upper()
    return _ALIAS_TO_CODE.get(key)


def _group_letter(raw: str | None) -> str | None:
    """Extrai a letra do grupo de strings como 'GROUP_C' ou 'Group C'."""
    if not raw:
        return None
    raw = raw.strip().upper().replace("GROUP", "").replace("_", "").strip()
    return raw[-1] if raw and raw[-1] in "ABCDEFGHIJKL" else None


# --- football-data.org ------------------------------------------------------
def fetch_football_data(token: str, timeout: int = 12) -> list[dict]:
    if not requests or not token:
        return []
    url = f"{FOOTBALL_DATA_BASE}/competitions/WC/matches?season=2026"
    r = requests.get(url, headers={"X-Auth-Token": token}, timeout=timeout)
    r.raise_for_status()
    out: list[dict] = []
    for m in r.json().get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        ft = (m.get("score") or {}).get("fullTime") or {}
        hg, ag = ft.get("home"), ft.get("away")
        if hg is None or ag is None:
            continue
        ht = (m.get("homeTeam") or {})
        at = (m.get("awayTeam") or {})
        home = code_from(ht.get("tla")) or code_from(ht.get("name"))
        away = code_from(at.get("tla")) or code_from(at.get("name"))
        if not home or not away:
            continue
        out.append({
            "group": _group_letter(m.get("group")) or td.TEAMS[home].group,
            "home": home, "away": away, "hg": int(hg), "ag": int(ag),
            "stage": "group" if (m.get("stage") == "GROUP_STAGE") else "ko",
        })
    return out


# --- API-Football (api-sports.io) -------------------------------------------
def fetch_api_football(key: str, timeout: int = 12) -> list[dict]:
    if not requests or not key:
        return []
    url = f"{API_FOOTBALL_BASE}/fixtures?league=1&season=2026"
    r = requests.get(url, headers={"x-apisports-key": key}, timeout=timeout)
    r.raise_for_status()
    out: list[dict] = []
    for item in r.json().get("response", []):
        fx = item.get("fixture", {})
        if (fx.get("status") or {}).get("short") not in ("FT", "AET", "PEN"):
            continue
        goals = item.get("goals", {})
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue
        teams = item.get("teams", {})
        home = code_from((teams.get("home") or {}).get("name"))
        away = code_from((teams.get("away") or {}).get("name"))
        if not home or not away:
            continue
        rnd = (item.get("league") or {}).get("round", "")
        out.append({
            "group": _group_letter(rnd) or td.TEAMS[home].group,
            "home": home, "away": away, "hg": int(hg), "ag": int(ag),
            "stage": "group" if "group" in rnd.lower() else "ko",
        })
    return out


def fetch_results(fd_token: str | None = None,
                  af_key: str | None = None) -> tuple[list[dict], str]:
    """Tenta a fonte primária e depois a reserva.

    Returns:
        (resultados_normalizados, mensagem_de_status)
    """
    if fd_token:
        try:
            res = fetch_football_data(fd_token)
            if res:
                return res, f"football-data.org: {len(res)} resultados."
        except Exception as exc:  # noqa: BLE001
            primary_err = str(exc)
        else:
            primary_err = "sem resultados"
    else:
        primary_err = "sem chave"

    if af_key:
        try:
            res = fetch_api_football(af_key)
            if res:
                return res, f"API-Football: {len(res)} resultados."
        except Exception as exc:  # noqa: BLE001
            return [], f"Falha nas duas fontes (primária: {primary_err}; reserva: {exc})."

    return [], f"Sem dados automáticos (primária: {primary_err}). Use a entrada manual."
