"""
Dados-semente reais da Copa do Mundo FIFA 2026
----------------------------------------------
48 seleções em 12 grupos (A–L), sorteio oficial de 05/12/2025 com as repescagens
de março/2026 já resolvidas. Inclui:

    * GROUPS / TEAMS  — seleções por grupo (ordem do sorteio, Pote 1 primeiro)
    * group_fixtures() — os 72 jogos da fase de grupos (turno único)
    * R32_DEF          — bracket dos dezesseis-avos (jogos 73–88) por posição
    * KO_TREE          — árvore de cruzamentos das oitavas à final (89–104)
    * THIRD_SLOTS / THIRD_CLUSTERS — vagas dos 8 melhores 3º colocados e seus
      grupos candidatos (Anexo C / FIFA)

Observações:
    * Ranking FIFA é APROXIMADO (junho/2026) e serve apenas como último critério
      de desempate — editável.
    * Datas e sedes são APROXIMADAS dentro das janelas oficiais de cada fase;
      ajuste fino conforme o calendário definitivo da FIFA.
"""
from __future__ import annotations

from datetime import date, timedelta

from data_model import Team, Match, GROUP

GROUP_ORDER = list("ABCDEFGHIJKL")

# (código, nome PT-BR, grupo, ranking FIFA aproximado) -----------------------
_TEAM_ROWS = [
    # Grupo A
    ("MEX", "México", "A", 14), ("RSA", "África do Sul", "A", 36),
    ("KOR", "Coreia do Sul", "A", 20), ("CZE", "Tchéquia", "A", 43),
    # Grupo B
    ("CAN", "Canadá", "B", 27), ("SUI", "Suíça", "B", 16),
    ("QAT", "Catar", "B", 30), ("BIH", "Bósnia e Herzegovina", "B", 42),
    # Grupo C
    ("BRA", "Brasil", "C", 5), ("MAR", "Marrocos", "C", 11),
    ("SCO", "Escócia", "C", 28), ("HAI", "Haiti", "C", 47),
    # Grupo D
    ("USA", "Estados Unidos", "D", 15), ("PAR", "Paraguai", "D", 31),
    ("AUS", "Austrália", "D", 23), ("TUR", "Turquia", "D", 41),
    # Grupo E
    ("GER", "Alemanha", "E", 9), ("ECU", "Equador", "E", 21),
    ("CIV", "Costa do Marfim", "E", 29), ("CUW", "Curaçao", "E", 46),
    # Grupo F
    ("NED", "Holanda", "F", 6), ("JPN", "Japão", "F", 17),
    ("SWE", "Suécia", "F", 24), ("TUN", "Tunísia", "F", 32),
    # Grupo G
    ("BEL", "Bélgica", "G", 8), ("EGY", "Egito", "G", 25),
    ("IRN", "Irã", "G", 19), ("NZL", "Nova Zelândia", "G", 38),
    # Grupo H
    ("ESP", "Espanha", "H", 2), ("URU", "Uruguai", "H", 13),
    ("KSA", "Arábia Saudita", "H", 34), ("CPV", "Cabo Verde", "H", 37),
    # Grupo I
    ("FRA", "França", "I", 3), ("SEN", "Senegal", "I", 18),
    ("NOR", "Noruega", "I", 26), ("IRQ", "Iraque", "I", 45),
    # Grupo J
    ("ARG", "Argentina", "J", 1), ("AUT", "Áustria", "J", 22),
    ("ALG", "Argélia", "J", 35), ("JOR", "Jordânia", "J", 40),
    # Grupo K
    ("POR", "Portugal", "K", 7), ("COL", "Colômbia", "K", 12),
    ("UZB", "Uzbequistão", "K", 33), ("COD", "RD Congo", "K", 39),
    # Grupo L
    ("ENG", "Inglaterra", "L", 4), ("CRO", "Croácia", "L", 10),
    ("GHA", "Gana", "L", 44), ("PAN", "Panamá", "L", 48),
]

TEAMS: dict[str, Team] = {
    code: Team(name=name, code=code, group=g, fifa_rank=rank)
    for (code, name, g, rank) in _TEAM_ROWS
}

# grupo -> lista de códigos na ordem do sorteio (Pote 1 primeiro)
GROUPS: dict[str, list[str]] = {g: [] for g in GROUP_ORDER}
for code, _name, g, _rank in _TEAM_ROWS:
    GROUPS[g].append(code)


def name_of(code: str) -> str:
    """Nome PT-BR de um código; devolve o próprio código se desconhecido."""
    t = TEAMS.get(code)
    return t.name if t else code


# --- Sedes (aproximadas) ----------------------------------------------------
HOST_CITIES = [
    "Cidade do México", "Guadalajara", "Monterrey",
    "Toronto", "Vancouver",
    "Atlanta", "Boston", "Dallas", "Houston", "Kansas City", "Los Angeles",
    "Miami", "Nova York/Nova Jersey", "Filadélfia", "São Francisco", "Seattle",
]


# --- Fixtures da fase de grupos --------------------------------------------
# Turno único entre os 4 times de cada grupo (6 jogos por grupo, 72 no total).
# Ordem de cruzamentos pelo método do círculo, com t1..t4 = ordem do sorteio.
_RR_PAIRS = [  # (rodada, índice_casa, índice_fora)
    (1, 0, 1), (1, 2, 3),
    (2, 0, 2), (2, 3, 1),
    (3, 0, 3), (3, 1, 2),
]


def group_fixtures() -> list[Match]:
    """Gera as 72 partidas da fase de grupos com datas/sedes aproximadas."""
    matches: list[Match] = []
    venue_i = 0
    for gi, g in enumerate(GROUP_ORDER):
        codes = GROUPS[g]
        for k, (md, hi, ai) in enumerate(_RR_PAIRS):
            if md == 1:
                d = date(2026, 6, 11) + timedelta(days=gi // 2)
            elif md == 2:
                d = date(2026, 6, 18) + timedelta(days=gi // 2)
            else:
                d = date(2026, 6, 24) + timedelta(days=gi // 3)
            matches.append(Match(
                id=f"{g}{k + 1}",
                stage=GROUP,
                group=g,
                matchday=md,
                home=codes[hi],
                away=codes[ai],
                date=d.isoformat(),
                venue=HOST_CITIES[venue_i % len(HOST_CITIES)],
                source="seed",
            ))
            venue_i += 1
    return matches


# --- Bracket dos dezesseis-avos (jogos 73–88) -------------------------------
# Especificações de posição:
#   "1A"/"2A"  -> 1º/2º colocado do grupo A
#   "3:ABCDF"  -> melhor 3º colocado vindo de um dos grupos do cluster
R32_DEF = [
    (73, "2A", "2B"),
    (74, "1E", "3:ABCDF"),
    (75, "1F", "2C"),
    (76, "1C", "2F"),
    (77, "1I", "3:CDFGH"),
    (78, "2E", "2I"),
    (79, "1A", "3:CEFHI"),
    (80, "1L", "3:EHIJK"),
    (81, "1D", "3:BEFIJ"),
    (82, "1G", "3:AEHIJ"),
    (83, "2K", "2L"),
    (84, "1H", "2J"),
    (85, "1B", "3:EFGIJ"),
    (86, "1J", "2H"),
    (87, "1K", "3:DEIJL"),
    (88, "2D", "2G"),
]

# Vagas que recebem um 3º colocado, na ordem canônica do Anexo C, e o cluster
# de grupos candidatos de cada vaga.
THIRD_SLOTS = [74, 77, 79, 80, 81, 82, 85, 87]
THIRD_CLUSTERS = {
    74: "ABCDF", 77: "CDFGH", 79: "CEFHI", 80: "EHIJK",
    81: "BEFIJ", 82: "AEHIJ", 85: "EFGIJ", 87: "DEIJL",
}

# --- Árvore das oitavas à final (89–104) ------------------------------------
# Cada jogo recebe os vencedores (W) ou perdedores (L) de jogos anteriores.
KO_TREE = {
    89: ("W74", "W77"),
    90: ("W73", "W75"),
    91: ("W76", "W78"),
    92: ("W79", "W80"),
    93: ("W83", "W84"),
    94: ("W81", "W82"),
    95: ("W86", "W88"),
    96: ("W85", "W87"),
    97: ("W89", "W90"),
    98: ("W93", "W94"),
    99: ("W91", "W92"),
    100: ("W95", "W96"),
    101: ("W97", "W98"),
    102: ("W99", "W100"),
    103: ("L101", "L102"),   # disputa de 3º lugar
    104: ("W101", "W102"),   # final
}


def stage_of_match(no: int) -> str:
    """Estágio de um número de jogo do mata-mata (73–104)."""
    from data_model import R32, R16, QF, SF, THIRD, FINAL
    if 73 <= no <= 88:
        return R32
    if 89 <= no <= 96:
        return R16
    if 97 <= no <= 100:
        return QF
    if no in (101, 102):
        return SF
    if no == 103:
        return THIRD
    if no == 104:
        return FINAL
    raise ValueError(f"número de jogo inválido: {no}")


# datas aproximadas por estágio do mata-mata (para exibição)
KO_STAGE_DATES = {
    "R32": "28/jun – 03/jul",
    "R16": "04/jul – 07/jul",
    "QF": "09/jul – 11/jul",
    "SF": "14/jul – 15/jul",
    "3RD": "18/jul",
    "FINAL": "19/jul",
}
