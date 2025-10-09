from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlalchemy as sa
from backend.config import DB_DSN, EMBED_MODEL, LLM_MODEL
from backend.utils import ollama_embed, ollama_generate
from sqlalchemy import text
import re
from datetime import datetime

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
eng = sa.create_engine(DB_DSN)


@app.get("/")
def root():
    return {"status": "ok", "message": "NBA Stats API is running"}


class Q(BaseModel):
    question: str

    
def game_context(r):
    """
    Build game context in a readable format.
    """
    return (
        f"Game ID {r['game_id']} on {r['game_timestamp']}: "
        f"{r['home_city']} {r['home_name']} scored {r['home_points']} points, "
        f"{r['away_city']} {r['away_name']} scored {r['away_points']} points"
    )


def player_context(r):
    """
    Build player context with key stats.
    """
    total_reb = r.get('oreb', 0) + r.get('dreb', 0)
    return (
        f"Game ID {r['game_id']} on {r['game_timestamp']}: "
        f"{r['first_name']} {r['last_name']} (Player ID {r['person_id']}) ({r['team_name']}) "
        f"scored {r['points']} points, {total_reb} rebounds, {r['assists']} assists"
    )


@app.post("/api/chat")
def answer(q: Q):
    '''
    Process a user question by retrieving relevant game and player data, generating an LLM-based answer, and returning evidence. 
    The evidence algorithm extracts cited rows from the model output or falls back to top-ranked game and player rows when no explicit citation is found.
    Evidence is used to visualize data associated with the question and answer in the UI.
    '''
    # Embed question
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
                "pbs.steals, pbs.blocks, pbs.turnovers, g.game_id, g.game_timestamp, "
                "1 - (pbs.player_embedding <=> (:q)::vector) AS score, 'player_box_scores' AS source "
                "FROM player_box_scores pbs "
                "JOIN players p ON pbs.person_id = p.player_id "
                "JOIN teams t ON pbs.team_id = t.team_id "
                "JOIN game_details g ON g.game_id = pbs.game_id "
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

    # LLM Prompt 
    prompt = f"""Use context only:
    {ctx}

    Answer the question based on the context above. 

    IMPORTANT: Only add an evidence tag if you found relevant information to answer the question.
    If the information is NOT in the context, do NOT add any evidence tag.

    If you DO find the answer, add this at the VERY END on a new line:
    |||EVIDENCE:table_name:actual_id|||

    Examples:
    - If you used Game 22300634: |||EVIDENCE:game_details:22300634|||
    - If you used Luka Dončić (player 203081) in game 22300634: |||EVIDENCE:player_box_scores:203081_22300634|||
    
    DO NOT write "gameid" or "playerid" - use the ACTUAL NUMBERS from the context.
    If you are using player data context to answer the question, cite both the player id and game id in the specified format, don't forget to include both.
    
    Answer in 1-2 full sentences, feel free to restate game related details mentioned in the question, but don't include anything extra that wasn't requested.
    
    Question: {q.question}
    Answer:"""

    resp = ollama_generate(LLM_MODEL, prompt)
    print(resp)
    
    # Extract the evidence tag 
    evidence_pattern = r'\|\|\|EVIDENCE:([^:]+):([^\|]+)\|\|\|'
    evidence_match = re.search(evidence_pattern, resp)
    
    # Remove the evidence tag from the visible answer
    clean_answer = re.sub(evidence_pattern, '', resp).strip()
    
    # Find the specific evidence that was used
    used_evidence = []
    if evidence_match:
        table_name = evidence_match.group(1).strip()
        row_id = evidence_match.group(2).strip()
        
        # For player questions, we want BOTH the game and player evidence
        if table_name == "player_box_scores":
            # Parse the player_game IDs
            player_id, game_id = row_id.split('_') if '_' in row_id else (row_id, None)
            
            # Add game evidence
            for r in game_rows:
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                if str(r["game_id"]) == game_id:
                    used_evidence.append({
                        "table": "game_details",
                        "id": int(r["game_id"]),
                        "home_team": f"{r['home_city']} {r['home_name']}",
                        "away_team": f"{r['away_city']} {r['away_name']}",
                        "home_points": r["home_points"],
                        "away_points": r["away_points"],
                        "game_date": {formatted_date},
                        "display_name": f"{r['away_abbrev']}@{r['home_abbrev']} {formatted_date}"
                    })
                    break
            
            # Add player evidence
            for r in player_rows:
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                if str(r['person_id']) == player_id and str(r['game_id']) == game_id:
                    used_evidence.append({
                        "table": "player_box_scores",
                        "id": f"{int(r['person_id'])}_{int(r['game_id'])}",
                        "player_name": f"{r['first_name']} {r['last_name']}",
                        "team": r["team_name"],
                        "points": r["points"],
                        "rebounds": r['oreb'] + r['dreb'],
                        "assists": r['assists'],
                        "game_id": int(r["game_id"]),
                        "display_name": f"{r['first_name']} {r['last_name']} {formatted_date}"
                    })
                    break
                    
        # For game questions, we only want game evidence
        elif table_name == "game_details":
            for r in game_rows:
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                if str(r["game_id"]) == row_id:
                    used_evidence.append({
                        "table": "game_details",
                        "id": int(r["game_id"]),
                        "home_team": f"{r['home_city']} {r['home_name']}",
                        "away_team": f"{r['away_city']} {r['away_name']}",
                        "home_points": r["home_points"],
                        "away_points": r["away_points"],
                        "game_date": {formatted_date},
                        "display_name": f"{r['away_abbrev']}@{r['home_abbrev']} {formatted_date}"
                    })
                    break

    # If no evidence found, use top results as fallback
    if not used_evidence:
        question_lower = q.question.lower()
        
        if any(word in question_lower for word in ['scored', 'points', 'player', 'who']):
            
            # Add top game and player rows as evidence for player-related questions
            if game_rows:
                r = game_rows[0]
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                used_evidence.append({
                    "table": "game_details",
                    "id": int(r["game_id"]),
                    "home_team": f"{r['home_city']} {r['home_name']}",
                    "away_team": f"{r['away_city']} {r['away_name']}",
                    "home_points": r["home_points"],
                    "away_points": r["away_points"],
                    "game_date": {formatted_date},
                    "display_name": f"{r['away_abbrev']}@{r['home_abbrev']} {formatted_date}"
                })
                
            if player_rows:
                r = player_rows[0]
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                used_evidence.append({
                    "table": "player_box_scores",
                    "id": f"{int(r['person_id'])}_{int(r['game_id'])}",
                    "player_name": f"{r['first_name']} {r['last_name']}",
                    "team": r["team_name"],
                    "points": r["points"],
                    "rebounds": r['oreb'] + r['dreb'],
                    "assists": r['assists'],
                    "game_id": int(r["game_id"]),
                   "display_name": f"{r['first_name']} {r['last_name']} {formatted_date}"
                })
        
        # Add top game only as game evidence        
        else:
            if game_rows:
                r = game_rows[0]
                game_date_str = str(r['game_timestamp']).split()[0]  
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d')
                formatted_date = game_date.strftime('%m/%d/%y')
                used_evidence.append({
                    "table": "game_details",
                    "id": int(r["game_id"]),
                    "home_team": f"{r['home_city']} {r['home_name']}",
                    "away_team": f"{r['away_city']} {r['away_name']}",
                    "home_points": r["home_points"],
                    "away_points": r["away_points"],
                    "game_date": {formatted_date},
                    "display_name": f"{r['away_abbrev']}@{r['home_abbrev']} {formatted_date}"
                })
            
    return {
        "answer": clean_answer,
        "evidence": used_evidence
    }
    