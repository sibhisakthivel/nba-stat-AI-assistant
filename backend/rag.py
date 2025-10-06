import os
import json
import sys
import sqlalchemy as sa
from sqlalchemy import text
from backend.config import DB_DSN, EMBED_MODEL, LLM_MODEL
from backend.utils import ollama_embed, ollama_generate

# Force 1b model
# LLM_MODEL = "llama3.2:1b"

BASE_DIR = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "questions.json"))
ANSWERS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers.json"))
TEMPLATE_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers_template.json"))


def is_leader_question(question):
    """
    Detect if this is a leader/comparison question.
    """
    q_lower = question.lower()
    indicators = [
        "leading", "leader", "led", "most", "highest", "top scorer",
        "who was the", "who had the most", "which player"
    ]
    return any(phrase in q_lower for phrase in indicators)


def extract_requested_stats(question):
    """
    Extract which stats are mentioned in the question.
    """
    q = question.lower()
    
    # Always include these
    stats = ["points", "rebounds", "assists"]
    
    # Add specific stats if mentioned
    if "steal" in q:
        stats.append("steals")
    if "block" in q:
        stats.append("blocks")
    if "turnover" in q:
        stats.append("turnovers")
    
    return stats


def retrieve(cx, qvec, question):
    """
    Retrieve games and players based on question type.
    """
    is_leader = is_leader_question(question)
    
    # Get games
    game_limit = 5
    
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
    
    game_rows = list(cx.execute(text(game_sql), {"q": qvec, "k": game_limit}).mappings())
    
    # Get players
    if is_leader and game_rows:
        # Get ALL players from the retrieved games
        game_ids = [g['game_id'] for g in game_rows]
        
        player_sql = """
        SELECT pbs.person_id, pbs.game_id, p.first_name, p.last_name, t.name AS team_name,
                pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists,
                pbs.steals, pbs.blocks, pbs.turnovers,
                g.game_timestamp,
                'player_box_scores' AS source
        FROM player_box_scores pbs
        JOIN players p ON pbs.person_id = p.player_id
        JOIN teams t ON pbs.team_id = t.team_id
        JOIN game_details g ON pbs.game_id = g.game_id
        WHERE pbs.game_id = ANY(:game_ids)
        ORDER BY pbs.game_id, pbs.points DESC
        """
        
        player_rows = list(cx.execute(text(player_sql), {"game_ids": game_ids}).mappings())
    else:
        # Regular retrieval - 5 players by vector similarity
        player_sql = """
        SELECT pbs.person_id, pbs.game_id, p.first_name, p.last_name, t.name AS team_name,
                pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists,
                pbs.steals, pbs.blocks, pbs.turnovers,
                g.game_timestamp,
                1 - (pbs.player_embedding <=> (:q)::vector) AS score, 'player_box_scores' AS source
        FROM player_box_scores pbs
        JOIN players p ON pbs.person_id = p.player_id
        JOIN teams t ON pbs.team_id = t.team_id
        JOIN game_details g ON pbs.game_id = g.game_id
        ORDER BY pbs.player_embedding <-> (:q)::vector
        LIMIT 5
        """
        
        player_rows = list(cx.execute(text(player_sql), {"q": qvec}).mappings())
    
    return game_rows + player_rows


def game_context(r):
    """
    Build game context.
    """
    return (
        f"Game {r['game_id']} on {r['game_timestamp']}: "
        f"{r['home_city']} {r['home_name']} scored {r['home_points']} points, "
        f"{r['away_city']} {r['away_name']} scored {r['away_points']} points"
    )


def player_context(r, requested_stats):
    """
    Build player context with date and requested stats only.
    """
    parts = [f"Game {r['game_id']} on {r.get('game_timestamp', 'unknown date')}: {r['first_name']} {r['last_name']} ({r['team_name']})"]
    
    stat_parts = []
    
    if "points" in requested_stats:
        stat_parts.append(f"{r.get('points', 0)} points")
    
    if "rebounds" in requested_stats:
        total_reb = r.get('oreb', 0) + r.get('dreb', 0)
        stat_parts.append(f"{total_reb} rebounds")
    
    if "assists" in requested_stats:
        stat_parts.append(f"{r.get('assists', 0)} assists")
    
    if "steals" in requested_stats and 'steals' in r:
        stat_parts.append(f"{r['steals']} steals")
    
    if "blocks" in requested_stats and 'blocks' in r:
        stat_parts.append(f"{r['blocks']} blocks")
    
    if "turnovers" in requested_stats and 'turnovers' in r:
        stat_parts.append(f"{r['turnovers']} turnovers")
    
    return parts[0] + " - " + ", ".join(stat_parts)


def build_context(rows, requested_stats):
    """
    Build context with games first, then players grouped by game.
    """
    context = []
    
    # Separate games and players
    games = [r for r in rows if r["source"] == "game_details"]
    players = [r for r in rows if r["source"] == "player_box_scores"]
    
    # Sort players by game_id and points for better organization
    players.sort(key=lambda x: (x.get('game_id', 0), -x.get('points', 0)))
    
    # Add games
    for g in games:
        context.append(game_context(g))
    
    # Add players
    for p in players:
        context.append(player_context(p, requested_stats))
    
    return "\n".join(context)


def answer(question, rows, requested_stats, question_id):
    """
    Generate answer using LLM.
    """
    ctx = build_context(rows, requested_stats)
    
    # Load template to understand structure
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = json.load(f)
    
    expected = template[question_id - 1]["result"]
    
    prompt = f"""Return ONLY the JSON result object that matches this structure:
{json.dumps(expected, indent=2)}

Rules:
1. Use ONLY data from the Context below
2. Return ONLY the result object (no 'id' or 'evidence' fields)
3. All fields must be present (use null if not found)
4. For 'score': format as "HOME_POINTS-AWAY_POINTS" (e.g., "120-114")
5. Christmas Day = December 25, New Year's Eve = December 31
6. "4/9 in the 2023 NBA Season" means April 9, 2024 (seasons run Sept-June)
7. For leading scorer: find the player with HIGHEST points from the SPECIFIC game mentioned
9. Use full team names (e.g., "Denver Nuggets" not "DEN")
10. Match dates exactly - if the specific game isn't in context, return null

Context:
{ctx}

Question: {question}

JSON result only:"""
    
    return ollama_generate(LLM_MODEL, prompt)


def process_question(question_id):
    """
    Process a single question by ID.
    """
    print(f"\n{'='*60}")
    print(f"Processing Question {question_id}")
    print(f"Model: {LLM_MODEL}")
    print('='*60)
    
    # Load questions
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    
    if question_id < 1 or question_id > len(questions):
        print(f"Error: Question {question_id} not found")
        return
    
    q = questions[question_id - 1]
    print(f"Question: {q['question'][:70]}...")
    
    # Load existing answers or create new
    if os.path.exists(ANSWERS_PATH):
        with open(ANSWERS_PATH, encoding="utf-8") as f:
            answers = json.load(f)
    else:
        answers = []
    
    # Ensure list is long enough
    while len(answers) < len(questions):
        answers.append({"id": len(answers) + 1, "result": None, "evidence": []})
    
    eng = sa.create_engine(DB_DSN)
    
    with eng.begin() as cx:
        # Analyze question
        is_leader = is_leader_question(q["question"])
        requested_stats = extract_requested_stats(q["question"])
        
        print(f"  Type: {'Leader' if is_leader else 'Regular'}")
        print(f"  Stats: {requested_stats}")
        
        # Retrieve
        qvec = ollama_embed(EMBED_MODEL, q["question"])
        rows = retrieve(cx, qvec, q["question"])
        
        games = [r for r in rows if r["source"] == "game_details"]
        players = [r for r in rows if r["source"] == "player_box_scores"]
        
        print(f"  Retrieved: {len(games)} games, {len(players)} players")
        
        # Generate answer
        ans = answer(q["question"], rows, requested_stats, question_id)
        
        try:
            result = json.loads(ans)
            print(f"  Result: {result}")
        except json.JSONDecodeError as e:
            print(f"  JSON Error: {e}")
            # Try to extract JSON
            import re
            match = re.search(r'\{.*\}', ans, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                    print(f"  Recovered: {result}")
                except:
                    result = None
            else:
                result = None
        
        # Build evidence
        evidence = []
        for r in rows[:10]:
            if r["source"] == "game_details":
                evidence.append({
                    "table": "game_details",
                    "id": int(r["game_id"])
                })
            elif r["source"] == "player_box_scores":
                evidence.append({
                    "table": "player_box_scores",
                    "id": f"{int(r['person_id'])}_{int(r['game_id'])}"
                })
        
        print(evidence)
        
        # Update answer
        answers[question_id - 1] = {
            "id": question_id,
            "result": result,
            "evidence": evidence
        }
    
    # Save
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=2)
    
    print(f"\n✅ Updated answers.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        # Process all questions
        print("Processing all questions...")
        with open(QUESTIONS_PATH, encoding="utf-8") as f:
            questions = json.load(f)
        
        for i in range(1, len(questions) + 1):
            process_question(i)
    else:
        # Process single question
        try:
            qid = int(sys.argv[1])
            process_question(qid)
        except ValueError:
            print("Usage: python -m backend.rag [question_number]")
            print("Or: python -m backend.rag  (to run all)")
            sys.exit(1)
            