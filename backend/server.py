from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlalchemy as sa
from backend.config import DB_DSN, EMBED_MODEL, LLM_MODEL
from backend.utils import ollama_embed, ollama_generate
from sqlalchemy import text

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
eng = sa.create_engine(DB_DSN)


class Q(BaseModel):
    question: str


# @app.post("/api/chat")
# def answer(q: Q):
#     print('Received question')
#     qvec = ollama_embed(EMBED_MODEL, q.question)
#     with eng.begin() as cx:
#     #    rows = cx.execute(
#     #         text(
#     #             "SELECT game_id, game_timestamp, home_team_id, away_team_id, home_points, away_points "
#     #             "FROM game_details ORDER BY game_embedding <-> :q LIMIT :k"
#     #         ),
#     #         {"q": qvec, "k": 5},
#     #     ).mappings().all()
#         rows = cx.execute(
#             text(
#                 "SELECT game_id, game_timestamp, home_team_id, away_team_id, home_points, away_points "
#                 f"FROM game_details ORDER BY game_embedding <-> ARRAY{qvec}::vector LIMIT :k"
#             ),
#             {"k": 5},
#         ).mappings().all()
#     ctx = "\n".join([str(dict(r)) for r in rows])
#     resp = ollama_generate(LLM_MODEL, f"Use context only:\n{ctx}\n\nQ:{q.question}\nA:")
#     return {
#             "answer": resp,
#             "evidence": [{"table": "game_details", "id": int(r["game_id"])} for r in rows],
#         }


def game_context(r):
    '''
    '''
    return(
        f"Game record: Game {r['game_id']} on {r['game_timestamp']}, {r['season']} season "
        f"{r['home_city']} {r['home_name']} ({r['home_abbrev']}) {r['home_points']} - {r['away_points']} {r['away_city']} {r['away_name']} ({r['away_abbrev']}) " 
    )


def player_context(r):
    '''
    '''
    return(
        f"Player record: Game {r['game_id']}, {r['first_name']} {r['last_name']} scored "
        f"{r['points']} points, {r['oreb']} offensive rebounds, {r['dreb']} defensive rebounds, "
        f"{r['assists']} assists, played {r['seconds']} seconds, {r['fg2_made']} 2-point field goals made, " 
        f"{r['fg2_attempted']} 2-point field goals attempted, {r['fg3_made']} 3 pointers made, "
        f"{r['fg3_attempted']} 3 pointers attempted, {r['ft_made']} free throws made, "
        f"{r['ft_attempted']} free throws attempted, {r['steals']} steals, {r['blocks']} blocks, "
        f"{r['turnovers']} turnovers, {r['defensive_fouls']} defensive fouls, {r['offensive_fouls']} offensive fouls"
    )


@app.post("/api/chat")
def answer(q: Q):
    
    print('Received question')
    qvec = ollama_embed(EMBED_MODEL, q.question)
    with eng.begin() as cx:
        
        game_rows = cx.execute(
            text(
                "SELECT g.game_id, g.season, g.game_timestamp, "
                        "h.name AS home_name, h.city AS home_city, h.abbreviation AS home_abbrev, g.home_points, "
                        "a.name AS away_name, a.city AS away_city, a.abbreviation AS away_abbrev, g.away_points, "
                        "1 - (g.game_embedding <=> (:q)::vector) AS score, 'game_details' AS source "
                "FROM game_details g "
                "JOIN teams h ON g.home_team_id = h.team_id "
                "JOIN teams a ON g.away_team_id = a.team_id "
                f"ORDER BY g.game_embedding <-> ARRAY{qvec}::vector "
                f"LIMIT :k"
            ),
            {"k": 5}, 
        ).mappings().all()
    
        player_rows = cx.execute(
            text(
                "SELECT pbs.person_id, pbs.game_id, p.first_name, p.last_name, t.name AS team_name, t.city AS team_city, "
                    "pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists, "
                    "pbs.seconds, pbs.fg2_made, pbs.fg2_attempted, pbs.fg3_made, pbs.fg3_attempted, "
                    "pbs.ft_attempted, pbs.ft_made, pbs.steals, pbs.blocks, pbs.turnovers, "
                    "pbs.defensive_fouls, pbs.offensive_fouls, "
                    "1 - (pbs.player_embedding <=> (:q)::vector) AS score, 'player_box_scores' AS source "
                "FROM player_box_scores pbs "
                "JOIN players p ON pbs.person_id = p.player_id "
                "JOIN teams t ON pbs.team_id = t.team_id "
                f"ORDER BY pbs.player_embedding <-> ARRAY{qvec}::vector "
                f"LIMIT :k"
            ),
            {"k": 5}, 
        ).mappings().all()
    
    game_ctx = "\n".join([game_context(r) for r in game_rows])
    player_ctx = "\n".join([player_context(r) for r in player_rows])
    ctx = f"=== Games ===\n{game_ctx}\n\n=== Players ===\n{player_ctx}"
    
    prompt = (
        f"Use context only:\n{ctx}\n\nQ:{q.question}\nA:")
    resp = ollama_generate(LLM_MODEL, prompt)
    
    ev = []
    for r in game_rows:
        ev.append({
            "table": "game_details",
            "id": int(r["game_id"])
        })
    for r in player_rows:
        ev.append({
            "table": "player_box_scores", 
            "id": f"{int(r['person_id'])}_{int(r['game_id'])}"
        })
        
    return {
            "answer": resp,
            "evidence": ev,
        }
    