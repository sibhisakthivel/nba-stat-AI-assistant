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

    
def game_context(r):
    """
    Build game context in a readable format.
    """
    return (
        f"Game {r['game_id']} on {r['game_timestamp']}: "
        f"{r['home_city']} {r['home_name']} scored {r['home_points']} points, "
        f"{r['away_city']} {r['away_name']} scored {r['away_points']} points"
    )


def player_context(r):
    """
    Build player context with key stats.
    """
    total_reb = r.get('oreb', 0) + r.get('dreb', 0)
    return (
        f"Player record: Game {r['game_id']} - {r['first_name']} {r['last_name']} ({r['team_name']}) "
        f"scored {r['points']} points, {total_reb} rebounds, {r['assists']} assists"
    )


@app.post("/api/chat")
def answer(q: Q):
    print('Received question')
    qvec = ollama_embed(EMBED_MODEL, q.question)
    
    with eng.begin() as cx:
        # Query games with team information
        game_rows = list(cx.execute(
            text(
                "SELECT g.game_id, g.season, g.game_timestamp, "
                "h.name AS home_name, h.city AS home_city, h.abbreviation AS home_abbrev, g.home_points, "
                "a.name AS away_name, a.city AS away_city, a.abbreviation AS away_abbrev, g.away_points, "
                "1 - (g.game_embedding <=> (:q)::vector) AS score, 'game_details' AS source "
                "FROM game_details g "
                "JOIN teams h ON g.home_team_id = h.team_id "
                "JOIN teams a ON g.away_team_id = a.team_id "
                # "ORDER BY g.game_embedding <-> :q::vector "
                f"ORDER BY game_embedding <-> ARRAY{qvec}::vector "
                "LIMIT :k"
            ),
            {"q": qvec, "k": 5}

        ).mappings())
        
        # Query players with team information
        player_rows = list(cx.execute(
            text(
                "SELECT pbs.person_id, pbs.game_id, p.first_name, p.last_name, t.name AS team_name, "
                "pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists, "
                "pbs.steals, pbs.blocks, pbs.turnovers, "
                "1 - (pbs.player_embedding <=> (:q)::vector) AS score, 'player_box_scores' AS source "
                "FROM player_box_scores pbs "
                "JOIN players p ON pbs.person_id = p.player_id "
                "JOIN teams t ON pbs.team_id = t.team_id "
                # "ORDER BY pbs.player_embedding <-> :q::vector "
                f"ORDER BY player_embedding <-> ARRAY{qvec}::vector "
                "LIMIT :k"
            ),
            {"q": qvec, "k": 5}
        ).mappings())
    
    # Build context
    game_ctx = "\n".join([game_context(r) for r in game_rows])
    player_ctx = "\n".join([player_context(r) for r in player_rows])
    
    # Format context for LLM
    if game_ctx and player_ctx:
        ctx = f"=== Games ===\n{game_ctx}\n\n=== Players ===\n{player_ctx}"
    elif game_ctx:
        ctx = f"=== Games ===\n{game_ctx}"
    elif player_ctx:
        ctx = f"=== Players ===\n{player_ctx}"
    else:
        ctx = "No relevant data found."
    
    # Generate response
    prompt = f"Use context only:\n{ctx}\n\nQ:{q.question}\nA:"
    resp = ollama_generate(LLM_MODEL, prompt)
    
    # Build evidence array
    evidence = []
    for r in game_rows:
        evidence.append({
            "table": "game_details",
            "id": int(r["game_id"])
        })
    for r in player_rows:
        evidence.append({
            "table": "player_box_scores",
            "id": f"{int(r['person_id'])}_{int(r['game_id'])}"
        })
    
    return {
        "answer": resp,
        "evidence": evidence
    }
