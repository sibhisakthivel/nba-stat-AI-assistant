import os
import json
import sqlalchemy as sa
from sqlalchemy import text
from backend.config import DB_DSN, EMBED_MODEL, LLM_MODEL
from backend.utils import ollama_embed, ollama_generate

BASE_DIR = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "questions.json"))
ANSWERS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers.json"))
TEMPLATE_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers_template.json"))


# def retrieve(cx, qvec, k=5):
#     sql = (
#        "SELECT game_id, game_timestamp, home_team_id, away_team_id, home_points, away_points, "
#         "1 - (embedding <=> (:q)::vector) AS score FROM game_details ORDER BY embedding <-> (:q)::vector LIMIT :k"
#     )
#     return cx.execute(text(sql), {"q": qvec, "k": k}).mappings().all()


def retrieve(cx, qvec, k=5):
    '''
    '''
    game_sql = """
    SELECT g.game_id, g.season, g.game_timestamp,
            h.name AS home_name, h.city AS home_city, h.abbreviation AS home_abbrev, g.home_points, 
            a.name AS away_name, a.city AS away_city, a.abbreviation AS away_abbrev, g.away_points, 
            1 - (g.game_embedding <=> (:q)::vector) AS score, 'game_details' AS source
    FROM game_details g
    JOIN teams h ON g.home_team_id = h.team_id
    JOIN teams a ON g.away_team_id = a.team_id
    ORDER BY g.game_embedding <-> (:q)::vector
    LIMIT :k
    """
    
    player_sql = """
    SELECT pbs.person_id, pbs.game_id, p.first_name, p.last_name, t.name AS team_name, t.city AS team_city,
            pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists,
            pbs.seconds, pbs.fg2_made, pbs.fg2_attempted, pbs.fg3_made, pbs.fg3_attempted,
            pbs.ft_attempted, pbs.ft_made, pbs.steals, pbs.blocks, pbs.turnovers, 
            pbs.defensive_fouls, pbs.offensive_fouls,
            1 - (pbs.player_embedding <=> (:q)::vector) AS score, 'player_box_scores' AS source
    FROM player_box_scores pbs
    JOIN players p ON pbs.person_id = p.player_id
    JOIN teams t ON pbs.team_id = t.team_id
    ORDER BY pbs.player_embedding <-> (:q)::vector
    LIMIT :k
    """
        
    game_rows = cx.execute(text(game_sql), {"q": qvec, "k": k}).mappings().all()
    player_rows = cx.execute(text(player_sql), {"q": qvec, "k": k}).mappings().all()
    
    rows = game_rows + player_rows
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


# def build_context(rows):
#     return "\n".join(
#         [
#             f"{r['game_id']} {r['game_timestamp']} {r['home_team_id']} vs {r['away_team_id']} {r['home_points']}-{r['away_points']}"
#             for r in rows
#         ]
#     )
    

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


def build_context(rows):
    '''
    '''
    context = []
    for r in rows:
        if r["source"] == "game_details":
            context.append(game_context(r))
            
        else:
            context.append(player_context(r))
            
    return "\n".join(context)


# Feel free to edit this prompt, but ensure it still uses context directly from the embeddings
def answer(question, rows, result_format):
    # # Use answers template in the response
    # with open(TEMPLATE_PATH, encoding="utf-8") as f:
    #     answers_template = json.load(f)
    ctx = build_context(rows)
    schema_json = json.dumps(result_format, ensure_ascii=False)
    # prompt = (
    #     f"Use this format to answer the questions:\n{json.dumps(answers_template)}\n"
    #     f"Answer using only this context. Cite game_ids used.\n"
    #     f"Context:\n{ctx}\n\nQ: {question}\nA:"
    # )
    prompt = (
        f"Return ONLY a JSON object matching this schema (no extra keys, no prose):\n{schema_json}\n"
        f"Only use the information provided below in 'Context', don't use outside knowledge.\n"
        f"If a field cannot be determined, set it to null (do not guess).\n"
        f"Output must be valid JSON only (no extra text).\n"
        f"Context:\n{ctx}\n\nQ: {question}\nA:"
    )
    return ollama_generate(LLM_MODEL, prompt)


if __name__ == "__main__":
    eng = sa.create_engine(DB_DSN)
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        qs = json.load(f)
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        answers_template = json.load(f)
    outs = []
    with eng.begin() as cx:
        for id, q in enumerate(qs, start=1):
            qvec = ollama_embed(EMBED_MODEL, q["question"])
            rows = retrieve(cx, qvec, 5)
            result_format = answers_template[id - 1]["result"]
            ans = answer(q["question"], rows, result_format)
            result = json.loads(ans)
            
            ev = []
            for r in rows:
                if r["source"] == "game_details":
                    ev.append({
                        "table": "game_details",
                        "id": int(r["game_id"])
                    })
                elif r["source"] == "player_box_scores":
                    ev.append({
                        "table": "player_box_scores",
                        "id": f"{int(r['person_id'])}_{int(r['game_id'])}"
                    })

            outs.append({
                "id": id,
                "result": result,
                "evidence": ev,
            })
            
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        json.dump(outs, f, ensure_ascii=False, indent=2)
