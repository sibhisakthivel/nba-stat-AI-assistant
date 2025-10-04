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


@app.post("/api/chat")
def answer(q: Q):
    print('Received question')
    qvec = ollama_embed(EMBED_MODEL, q.question)
    with eng.begin() as cx:
    #    rows = cx.execute(
    #         text(
    #             "SELECT game_id, game_timestamp, home_team_id, away_team_id, home_points, away_points "
    #             "FROM game_details ORDER BY game_embedding <-> :q LIMIT :k"
    #         ),
    #         {"q": qvec, "k": 5},
    #     ).mappings().all()
        rows = cx.execute(
            text(
                "SELECT game_id, game_timestamp, home_team_id, away_team_id, home_points, away_points "
                f"FROM game_details ORDER BY game_embedding <-> ARRAY{qvec}::vector LIMIT :k"
            ),
            {"k": 5},
        ).mappings().all()
    ctx = "\n".join([str(dict(r)) for r in rows])
    resp = ollama_generate(LLM_MODEL, f"Use context only:\n{ctx}\n\nQ:{q.question}\nA:")
    return {
            "answer": resp,
            "evidence": [{"table": "game_details", "id": int(r["game_id"])} for r in rows],
        }

@app.post("/api/chat")
def answer(q: Q):
    
    print('Received question')
    qvec = ollama_embed(EMBED_MODEL, q.question)
    with eng.begin() as cx:
        
        game_sql = cx.execute(
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
    
        player_sql = cx.execute(
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
    
