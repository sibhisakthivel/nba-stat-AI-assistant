import os
import json
import sys
import sqlalchemy as sa
from sqlalchemy import text
from backend.config import DB_DSN, EMBED_MODEL, LLM_MODEL
from backend.utils import ollama_embed, ollama_generate

BASE_DIR = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "questions.json"))
ANSWERS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers.json"))
TEMPLATE_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "part1", "answers_template.json"))

def is_leader_question(question):
    """
    Flag if question asks to identify a stat leader.
    """
    q_lower = question.lower()
    
    # Phrases that indicate "leader" type question
    indicators = ["leading", "leader", "led", "most", "highest", "top", "who was the"]
    return any(phrase in q_lower for phrase in indicators)


def extract_requested_stats(question):
    """
    Identify which stats are mentioned in the question.
    """
    q = question.lower()
    
    # Minimum stats to include
    stats = ["points", "rebounds", "assists"]
    
    # Add if mentioned
    if "steal" in q:
        stats.append("steals")
    if "block" in q:
        stats.append("blocks")
    if "turnover" in q:
        stats.append("turnovers")
    
    return stats


def retrieve(cx, qvec, question):
    """
    Retrieve games_details and player_box_scores rows depending on question type.
    """
    # Determine if we need to retrieve addtional player_box_scores rows
    is_leader = is_leader_question(question)
    
    # Retrieve game_details rows
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
    
    game_rows = list(cx.execute(text(game_sql), {"q": qvec, "k": 3}).mappings())
    
    # Retrieve player_box_scores rows
    if is_leader and game_rows:
        
        game_ids = [g['game_id'] for g in game_rows[0:2]]    
        print(game_ids)
        
        # Get ALL players from the top 2 retrieved games if "leader"
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
        
        # Retrieve top 5 players by vector similarity
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
    Includes:
    - Game ID and date
    - Home/away teams and score
    """
    return (
        f"Game {r['game_id']} on {r['game_timestamp']}: "
        f"{r['home_city']} {r['home_name']} scored {r['home_points']} points, "
        f"{r['away_city']} {r['away_name']} scored {r['away_points']} points"
    )


def player_context(r, requested_stats):
    """
    Build player context with date and requested stats only. 
    Includes:
    - Game ID and date
    - Player name and recorded stats
    """
    # Context Base
    parts = [f"Game {r['game_id']} on {r.get('game_timestamp', 'unknown date')}: {r['first_name']} {r['last_name']} ({r['team_name']})"]
    
    # Build stat context depending on which stats were requested
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
    Wrapper function to combine game and player context.
    """
    context = []
    
    games = [r for r in rows if r["source"] == "game_details"]
    players = [r for r in rows if r["source"] == "player_box_scores"]
    
    players.sort(key=lambda x: (x.get('game_id', 0), -x.get('points', 0)))
    
    # Game Context
    for g in games:
        context.append(game_context(g))
    
    # Player Context
    for p in players:
        context.append(player_context(p, requested_stats))
    
    return "\n".join(context)


def answer(question, rows, requested_stats, question_id):
    """
    Generate answer using LLM.
    """
    ctx = build_context(rows, requested_stats)
    
    # Load answer template 
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = json.load(f)
    
    expected = template[question_id - 1]["result"]  # Retrieve `result` field of current question for LLM context

    # LLM Prompt with guidelines for response accuracy
    prompt = f"""Return ONLY the JSON result object matching this exact structure:
    {json.dumps(expected, indent=2)}

    Requirements:
    - Include only the fields shown above: {', '.join([k for k in expected.keys() if k != 'evidence']) if isinstance(expected, dict) else 'exactly as shown'}
    - Do not add 'evidence' field (will be added programmatically), or any other fields not shown above
    - All fields must be present (use null if data not found in context)
    - Use only information from the provided Context below
    - Use the exact name from context, convert all non-ASCII characters in player names to their ASCII equivalents (ie. Dončić -> Doncic)
    - Use full team names (e.g., "Denver Nuggets" not "DEN")
    - Date interpretations:
    - Convert holiday names to standard dates when referenced (ie. Halloween -> 10/31)
    - "4/9 in the 2023 NBA Season" = April 9, 2024 (seasons span Sept-June)
    - Match dates exactly - return null if referenced game not in context

    Context:
    {ctx}

    Question: {question}

    Return only the JSON object:"""
    
    return ollama_generate(LLM_MODEL, prompt)


def process_question(question_id):
    """
    Answer a single question by ID.
    """
    print(f"\n{'='*60}")
    print(f"Processing Question {question_id}")
    print(f"Model: {LLM_MODEL}")
    print('='*60)
    
    # Load questions
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    
    # Input Error Handling
    if question_id < 1 or question_id > len(questions):
        print(f"Error: Question {question_id} not found")
        return
    
    q = questions[question_id - 1]
    print(f"Question: {q['question']}")
    
    # Load existing answers or create new
    if os.path.exists(ANSWERS_PATH):
        with open(ANSWERS_PATH, encoding="utf-8") as f:
            answers = json.load(f)
    else:
        answers = []
    
    # Ensure list is long enough
    while len(answers) < len(questions):
        answers.append({"id": len(answers) + 1, "result": None, "evidence": []})
    
    # Start processing 
    eng = sa.create_engine(DB_DSN)
    with eng.begin() as cx:
        # Analyze question
        is_leader = is_leader_question(q["question"])
        requested_stats = extract_requested_stats(q["question"])
        
        print(f"  Type: {'Leader' if is_leader else 'Regular'}")
        print(f"  Stats: {requested_stats}")
        
        # Embed question and retrieve rows
        qvec = ollama_embed(EMBED_MODEL, q["question"])
        rows = retrieve(cx, qvec, q["question"])
        
        games = [r for r in rows if r["source"] == "game_details"]
        players = [r for r in rows if r["source"] == "player_box_scores"]
        
        print(f"  Retrieved: {len(games)} games, {len(players)} players")
        
        # Generate answer
        ans = answer(q["question"], rows, requested_stats, question_id)
        
        # Parse LLM response as JSON, attempting regex extraction if not found
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
        for r in rows:  
            
            if r["source"] == "game_details":
                evidence.append({
                    "table": "game_details",
                    "id": int(r["game_id"])
                })
                
            elif r["source"] == "player_box_scores":
                evidence.append({
                    "table": "player_box_score",                            # Note: template shows "player_box_score" (singular) not "player_box_scores"
                    "id": f"{int(r['person_id'])}_{int(r['game_id'])}"      # Include both player ID and game ID (player ID alone isn't a primary key)
                })                                                          # Formatted as: "playerid_gameid"

        # Add evidence to the result 
        if result:
            result["evidence"] = evidence
        else:
            result = {"evidence": evidence}

        print(f"  Evidence: {len(evidence)} rows")

        # Update answer with question id and result (which contains evidence)
        answers[question_id - 1] = {
            "id": question_id,
            "result": result
        }
    
    # Save answers
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        f.write('[\n') 
        for i, ans in enumerate(answers):  
            if i > 0:
                f.write(',\n')
            f.write(json.dumps(ans, separators=(',', ':')))
        f.write('\n]')
    
    print(f"\n✅ Updated answers.json")


if __name__ == "__main__":
    
    # 1 arg provided => answer all questions
    if len(sys.argv) != 2:
        print("Processing all questions...")
        with open(QUESTIONS_PATH, encoding="utf-8") as f:
            questions = json.load(f)
        
        for i in range(1, len(questions) + 1):
            process_question(i)
            
    # 2 args provided => answer given question only
    else:
        try:
            qid = int(sys.argv[1])
            process_question(qid)
        except ValueError:
            print("Usage: python -m backend.rag [question_number]")
            print("Or: python -m backend.rag  (to run all)")
            sys.exit(1)
            