"""
Camada de dados externa (busca automática de resultados) — best-effort
----------------------------------------------------------------------
Adapters para APIs de futebol. Três fontes, tentadas nesta ordem:

    1. football-data.org  (competição ``WC``)        — requer chave gratuita
    2. API-Football       (liga 1, season 2026)      — requer chave gratuita
    3. ESPN               (``fifa.world`` scoreboard) — *SEM CHAVE*

A fonte da ESPN é pública e **não exige cadastro nem chave**: por isso o botão
"Atualizar da API" funciona mesmo sem nenhuma chave configurada. As chaves das
duas primeiras continuam opcionais (melhoram a confiabilidade) e ficam em
``st.secrets`` (nunca no código):

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

# ESPN — API pública e sem chave. Slug "fifa.world" = Copa do Mundo FIFA.
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_LEAGUE = "fifa.world"
# janela do torneio (para varrer todas as datas de uma vez)
WC_START, WC_END = "20260611", "20260719"

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
    # formas adicionais usadas pela ESPN
    "BIH": ["bosnia & herzegovina", "bosnia and herzegovina"],
    "KOR": ["republic of korea"], "IRN": ["islamic republic of iran"],
    "CIV": ["cote d'ivoire"],
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


# --- ESPN (sem chave) -------------------------------------------------------
def _parse_espn(payload: dict) -> list[dict]:
    """Normaliza a resposta do scoreboard da ESPN para o formato interno.

    Considera apenas jogos concluídos. O estágio ('group' ou 'ko') é inferido
    pelos grupos-semente dos dois times — mais robusto do que depender dos
    rótulos da fonte: se ambos pertencem ao mesmo grupo, é jogo de grupo.
    """
    out: list[dict] = []
    for ev in payload.get("events", []) or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        stype = (comp.get("status") or ev.get("status") or {}).get("type") or {}
        if not stype.get("completed"):
            continue
        home = away = None
        hg = ag = None
        for c in comp.get("competitors") or []:
            team = c.get("team") or {}
            code = (code_from(team.get("abbreviation"))
                    or code_from(team.get("displayName"))
                    or code_from(team.get("name"))
                    or code_from(team.get("shortDisplayName")))
            try:
                score = int(c.get("score"))
            except (TypeError, ValueError):
                score = None
            if c.get("homeAway") == "home":
                home, hg = code, score
            elif c.get("homeAway") == "away":
                away, ag = code, score
        if not home or not away or hg is None or ag is None:
            continue
        g_home = td.TEAMS[home].group
        g_away = td.TEAMS[away].group
        out.append({
            "group": g_home,
            "home": home, "away": away, "hg": hg, "ag": ag,
            "stage": "group" if g_home == g_away else "ko",
        })
    return out


def fetch_espn(timeout: int = 12, start: str = WC_START, end: str = WC_END) -> list[dict]:
    """Busca resultados na API pública da ESPN (não requer chave)."""
    if not requests:
        return []
    url = f"{ESPN_BASE}/{ESPN_LEAGUE}/scoreboard"
    params = {"dates": f"{start}-{end}", "limit": 400}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return _parse_espn(r.json())


def fetch_results(fd_token: str | None = None,
                  af_key: str | None = None,
                  use_espn: bool = True) -> tuple[list[dict], str]:
    """Tenta as fontes em ordem e devolve a primeira que trouxer resultados.

    Ordem: football-data.org (se houver chave) -> API-Football (se houver chave)
    -> ESPN (sem chave). A ESPN garante que a atualização automática funcione
    mesmo sem nenhuma chave configurada.

    Returns:
        (resultados_normalizados, mensagem_de_status)
    """
    attempts: list[str] = []

    if fd_token:
        try:
            res = fetch_football_data(fd_token)
            if res:
                return res, f"football-data.org: {len(res)} resultados."
            attempts.append("football-data.org: sem resultados")
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"football-data.org: {exc}")

    if af_key:
        try:
            res = fetch_api_football(af_key)
            if res:
                return res, f"API-Football: {len(res)} resultados."
            attempts.append("API-Football: sem resultados")
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"API-Football: {exc}")

    if use_espn:
        try:
            res = fetch_espn()
            if res:
                return res, f"ESPN (sem chave): {len(res)} resultados."
            attempts.append("ESPN: sem resultados")
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"ESPN: {exc}")

    detail = "; ".join(attempts) if attempts else "nenhuma fonte disponível"
    return [], f"Sem dados automáticos ({detail}). Use a entrada manual."
