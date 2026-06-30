"""
Textos de ajuda centralizados (padrão do projeto Argus).
"""
from __future__ import annotations

HELP = {
    "atualizar_api": "Busca os resultados mais recentes e atualiza a fase de "
                     "grupos. Funciona SEM chave (usa a API pública da ESPN); "
                     "se você configurar football-data.org / API-Football, elas "
                     "têm prioridade. Edições manuais nunca são sobrescritas.",
    "editor_manual": "Digite os placares dos jogos. A classificação e o "
                     "chaveamento são recalculados automaticamente. Deixe em "
                     "branco para marcar como 'não disputado'.",
    "simulador_grupos": "Simule os placares dos jogos de grupo que ainda não "
                        "aconteceram e veja o efeito na classificação e na "
                        "projeção do mata-mata. Jogos já disputados ficam "
                        "travados.",
    "simulador_mata": "Com a fase de grupos encerrada, simule os confrontos do "
                      "mata-mata até a final. Em caso de empate, escolha quem "
                      "passa nos pênaltis.",
    "terceiros": "Os 8 melhores 3º colocados também avançam. O ranqueamento usa "
                 "pontos, saldo de gols, gols marcados e, por fim, o ranking FIFA.",
    "anexo_c": "A vaga de cada 3º colocado no chaveamento segue a tabela oficial "
               "do Anexo C da FIFA (495 combinações). Sem a tabela, usa-se um "
               "emparelhamento que respeita os grupos candidatos de cada vaga.",
    "fase": "O sistema se adapta à fase real: enquanto a fase de grupos não "
            "termina, o mata-mata é apenas uma projeção; ao terminar, o "
            "chaveamento passa a usar os classificados reais.",
}
