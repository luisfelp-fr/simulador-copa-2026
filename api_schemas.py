"""
Schemas (Pydantic) da API REST da Copa do Mundo 2026
----------------------------------------------------
Modelos de entrada e saída da API HTTP (``api.py``). Servem para validação
automática, serialização JSON e geração da documentação OpenAPI/Swagger.

Mantidos separados da lógica de negócio (``standings.py``, ``knockout.py``) e
dos dataclasses internos (``data_model.py``): aqui vivem apenas os contratos
expostos publicamente pela API.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# --- Saídas (responses) -----------------------------------------------------
class TeamOut(BaseModel):
    """Uma seleção participante."""
    code: str = Field(description="Código FIFA de 3 letras, ex.: 'BRA'")
    name: str = Field(description="Nome em português, ex.: 'Brasil'")
    group: str = Field(description="Letra do grupo (A–L)")
    fifa_rank: int = Field(description="Posição no ranking FIFA (menor = melhor)")


class MatchOut(BaseModel):
    """Uma partida da fase de grupos."""
    id: str
    stage: str
    group: str | None
    matchday: int | None
    home: str = Field(description="Código FIFA do mandante")
    away: str = Field(description="Código FIFA do visitante")
    home_name: str
    away_name: str
    home_goals: int | None
    away_goals: int | None
    status: str = Field(description="'scheduled' | 'finished'")
    date: str = Field(description="Data ISO AAAA-MM-DD")
    venue: str
    source: str = Field(description="'seed' | 'api' | 'manual'")
    played: bool
    winner: str | None = Field(description="Código do vencedor, ou null em empate/não disputado")


class StandingRowOut(BaseModel):
    """Uma linha da tabela de classificação de um grupo."""
    group: str
    position: int = Field(description="Posição no grupo (1–4)")
    team: str = Field(description="Código FIFA")
    team_name: str
    played: int
    won: int
    draw: int
    lost: int
    gf: int = Field(description="Gols pró")
    ga: int = Field(description="Gols contra")
    gd: int = Field(description="Saldo de gols")
    points: int
    qualified: str = Field(description="Situação de classificação (texto)")


class GroupOut(BaseModel):
    """Um grupo, com suas seleções e a classificação atual."""
    group: str
    complete: bool = Field(description="True se as 6 partidas do grupo já foram disputadas")
    teams: list[TeamOut]
    standings: list[StandingRowOut]


class ThirdPlacedOut(BaseModel):
    """Uma linha do ranking dos 3º colocados."""
    rank: int = Field(description="Posição no ranking dos 3º colocados (1 = melhor)")
    group: str
    team: str
    team_name: str
    points: int
    gd: int
    gf: int
    qualified: bool = Field(description="True se está entre os 8 melhores (zona de classificação)")


class KnockoutGameOut(BaseModel):
    """Um jogo do mata-mata (jogos 73–104)."""
    no: int = Field(description="Número do jogo (73–104)")
    stage: str = Field(description="R32 | R16 | QF | SF | 3RD | FINAL")
    stage_label: str
    home_code: str | None = Field(description="Código do mandante, ou null se ainda não resolvido")
    away_code: str | None
    home_label: str = Field(description="Rótulo legível (nome ou placeholder, ex.: '1º Grupo A')")
    away_label: str
    home_goals: int | None
    away_goals: int | None
    shootout_winner: str | None = Field(description="Código do vencedor nos pênaltis (se houve)")
    played: bool
    resolved: bool = Field(description="True se ambos os lados já estão definidos")
    winner: str | None
    loser: str | None


class TournamentOut(BaseModel):
    """Visão geral do estado do torneio."""
    name: str
    phase: str = Field(description="'groups' | 'knockout'")
    phase_label: str
    matches_played: int
    matches_total: int
    group_stage_complete: bool
    champion: str | None
    champion_name: str | None
    third_place_table: str = Field(description="'official' (Anexo C) | 'fallback' (clusters)")


class HealthOut(BaseModel):
    status: str
    teams: int
    version: str


class MessageOut(BaseModel):
    detail: str


class RefreshOut(BaseModel):
    detail: str
    updated: int = Field(description="Número de jogos atualizados a partir da API externa")


# --- Entradas (requests) ----------------------------------------------------
class GroupResultIn(BaseModel):
    """Placar de uma partida da fase de grupos."""
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


class KnockoutResultIn(BaseModel):
    """Placar de um jogo do mata-mata."""
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    shootout_winner: str | None = Field(
        default=None,
        description="Código do vencedor nos pênaltis; obrigatório se o jogo terminar empatado",
    )


class SimulateGroupScore(BaseModel):
    match_id: str = Field(description="Id do jogo de grupo (ex.: 'C3')")
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


class SimulateKnockoutScore(BaseModel):
    no: int = Field(ge=73, le=104, description="Número do jogo do mata-mata")
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    shootout_winner: str | None = None


class SimulateIn(BaseModel):
    """Conjunto de placares hipotéticos a sobrepor ao estado real."""
    groups: list[SimulateGroupScore] = Field(
        default_factory=list,
        description="Placares hipotéticos de jogos de grupo ainda não disputados",
    )
    knockout: list[SimulateKnockoutScore] = Field(
        default_factory=list,
        description="Placares hipotéticos de jogos do mata-mata",
    )


class SimulateOut(BaseModel):
    """Resultado de uma simulação 'e-se'."""
    phase: str
    standings: dict[str, list[StandingRowOut]]
    third_placed: list[ThirdPlacedOut]
    knockout: list[KnockoutGameOut]
    champion: str | None
    champion_name: str | None
