"""
Modelos de dados do Painel da Copa do Mundo 2026
-------------------------------------------------
Estruturas puras (``@dataclass``) compartilhadas por toda a aplicação. Nenhuma
dependência de Streamlit aqui — assim os módulos de lógica (``standings.py``,
``knockout.py``) permanecem testáveis isoladamente.

Convenções:
    * Times são identificados por um código FIFA de 3 letras (ex.: ``"BRA"``).
    * Partidas de grupo têm ``stage == "group"`` e ``group`` preenchido.
    * Partidas de mata-mata usam ``home``/``away`` que podem ser *placeholders*
      de posição (ex.: ``"1A"``, ``"W74"``) até serem resolvidos.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- Estágios do torneio (ordem cronológica) --------------------------------
GROUP = "group"
R32 = "R32"
R16 = "R16"
QF = "QF"
SF = "SF"
THIRD = "3RD"
FINAL = "FINAL"

STAGES = [GROUP, R32, R16, QF, SF, THIRD, FINAL]

STAGE_LABELS = {
    GROUP: "Fase de Grupos",
    R32: "Dezesseis-avos de Final",
    R16: "Oitavas de Final",
    QF: "Quartas de Final",
    SF: "Semifinais",
    THIRD: "Disputa de 3º Lugar",
    FINAL: "Final",
}


@dataclass
class Team:
    """Uma seleção participante."""
    name: str            # nome em português, ex.: "Brasil"
    code: str            # código FIFA de 3 letras, ex.: "BRA"
    group: str           # letra do grupo, ex.: "C"
    fifa_rank: int = 999  # posição no ranking FIFA (menor = melhor); desempate


@dataclass
class Match:
    """Uma partida (de grupo ou mata-mata).

    Para o mata-mata, ``home``/``away`` podem ser *placeholders* (ex.: ``"1A"``,
    ``"3:ABCDF"``, ``"W74"``) enquanto os classificados ainda não foram definidos.
    """
    id: str                       # id estável; grupos "A1".."L6", mata-mata "73".."104"
    stage: str                    # um de STAGES
    group: str | None             # letra do grupo (só para fase de grupos)
    matchday: int | None          # rodada 1..3 (só fase de grupos)
    home: str                     # código do time OU placeholder
    away: str
    home_goals: int | None = None
    away_goals: int | None = None
    status: str = "scheduled"     # "scheduled" | "finished"
    date: str = ""                # ISO "AAAA-MM-DD"
    venue: str = ""               # cidade-sede (aproximada)
    source: str = "seed"          # "seed" | "api" | "manual" | "sim"
    shootout_winner: str | None = None  # código do vencedor nos pênaltis (mata-mata empatado)

    @property
    def played(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    def winner(self) -> str | None:
        """Código do vencedor, ou ``None`` se empate/não disputado.

        Em jogo de mata-mata empatado, retorna ``shootout_winner`` (que pode ser
        ``None`` se ainda não definido).
        """
        if not self.played:
            return None
        if self.home_goals > self.away_goals:
            return self.home
        if self.away_goals > self.home_goals:
            return self.away
        return self.shootout_winner

    def loser(self) -> str | None:
        w = self.winner()
        if w is None:
            return None
        return self.away if w == self.home else self.home


@dataclass
class StandingRow:
    """Uma linha da tabela de classificação de um grupo."""
    group: str
    position: int      # 1..4 dentro do grupo
    team: str          # código FIFA
    played: int
    won: int
    draw: int
    lost: int
    gf: int            # gols pró
    ga: int            # gols contra
    gd: int            # saldo
    points: int
    qualified: str = ""   # "" | "1º" | "2º" | "3º (candidato)" | "3º (classificado)" | "3º (eliminado)"
