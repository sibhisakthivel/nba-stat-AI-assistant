import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text
from backend.config import DB_DSN, EMBED_MODEL
from backend.utils import ollama_embed

def row_text_game(r):
    '''
    Generate a string from a game_details row summarizing date, season, teams, score, and winner for embedding.
    '''
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date_long = ts.strftime('%B %d, %Y')
    date_slash =  ts.strftime('%m/%d/%Y')
    date_dash = ts.strftime('%Y-%m-%d')
    season = int(r.season)
    season_span = f"{season}-{str(season+1)[-2:]}"
    date_in_season = f"{ts.month}/{ts.day} in the {season} NBA Season"
    home_city = (r.home_city)
    home_name = (r.home_team_name)
    home_abbrev = (r.home_abbrev)
    home_pts = int(r.home_points)
    away_city = (r.away_city)
    away_name = (r.away_team_name)
    away_abbrev = (r.away_abbrev)
    away_pts = int(r.away_points)
    
    if (r.winning_team_id == r.home_team_id):
        winner = f"{r.home_city} {r.home_team_name} ({r.home_abbrev})"
    else:
        winner = f"{r.away_city} {r.away_team_name} ({r.away_abbrev})"
    
    return(f"{date_in_season} | {date_long}| {date_slash} | {date_dash} | "
           f"{season} NBA season | {season_span} NBA season | "
           f"Home: {home_city} {home_name} ({home_abbrev}) | "
           f"Away: {away_city} {away_name} ({away_abbrev}) | "
           f"Matchup: {away_abbrev}@{home_abbrev} | "
           f"Score: {home_city} {home_name} {home_pts} - {away_pts} {away_city} {away_name} | "
           f"Winner: {winner} victory")


def row_text_player(r):
    '''
    Generate a string from a player_box_scores row summarizing date, season, teams, player, and recorded stats for embedding.
    '''
    name = f"{r.first_name} {r.last_name}"
    name_ascii = name.encode("ascii", "ignore").decode()
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date_long = ts.strftime('%B %d, %Y')
    date_slash =  ts.strftime('%m/%d/%Y')
    date_dash = ts.strftime('%Y-%m-%d')
    season = int(r.season)
    season_span = f"{season}-{str(season+1)[-2:]}"
    date_in_season = f"{ts.month}/{ts.day} in the {season} NBA Season"
    team_city = (r.team_city)
    team_name = (r.team_name)
    team_abbrev = (r.team_abbrev)
    opp_city = (r.opp_city)
    opp_name = (r.opp_name)
    opp_abbrev = (r.opp_abbrev)
    home_abbrev = (r.home_abbrev)
    away_abbrev = (r.away_abbrev)
    pts = int(r.points)
    reb = int(r.oreb + r.dreb)
    ast = int(r.assists)
    td = ("Triple-Double" if sum([pts >= 10, reb >= 10, ast >= 10]) >= 3 else "") 
    dd = ("Double-Double" if sum([pts >= 10, reb >= 10, ast >= 10]) == 2 else "")
    
    return(f"{name} | {name_ascii} | "
           f"{date_in_season} | {date_long}| {date_slash} | {date_dash} | "
           f"{season} NBA season | {season_span} NBA season | "
           f"Team: {team_city} {team_name} ({team_abbrev}) | "
           f"Opponent: {opp_city} {opp_name} ({opp_abbrev}) | "
           f"Matchup: {away_abbrev}@{home_abbrev} | {team_city} {team_name} vs  {opp_city} {opp_name} | "
           f"Points: {pts} | Rebounds: {reb} | Assists: {ast} | {td} | {dd}")


def embed_games(eng):
    '''
    Embed every row in game_details.
    '''
    with eng.begin() as cx:
        cx.execute(text("ALTER TABLE IF EXISTS game_details ADD COLUMN IF NOT EXISTS game_embedding vector(768);"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_game_details_game_embedding ON game_details USING hnsw (game_embedding vector_cosine_ops);"))
    
    # Include relevant details from other tables in embedding
    df = pd.read_sql("""
        SELECT 
            g.game_id, g.season, g.game_timestamp, g.home_points, g.away_points, g.winning_team_id, 
            g.home_team_id, h.city AS home_city, h.name AS home_team_name, h.abbreviation AS home_abbrev,
            g.away_team_id, a.city AS away_city, a.name AS away_team_name, a.abbreviation AS away_abbrev
        FROM game_details g
        JOIN teams h ON g.home_team_id = h.team_id
        JOIN teams a ON g.away_team_id = a.team_id
    """, eng)
    
    total = len(df)
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        print(f"Embedding game row {i}/{total}")
        vec = ollama_embed(EMBED_MODEL, row_text_game(r))
        with eng.begin() as cx:
            cx.execute(text("""
                UPDATE game_details 
                SET game_embedding = :v 
                WHERE game_id = :gid
            """), {"v": vec, "gid": int(r.game_id)})

    print(f"Finished Game Embeddings: {total} Rows Updated")


def embed_players(eng):
    '''
    Embed every row in player_box_scores.
    '''
    with eng.begin() as cx:
        cx.execute(text("ALTER TABLE IF EXISTS player_box_scores ADD COLUMN IF NOT EXISTS player_embedding vector(768);"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_player_box_scores_player_embedding ON player_box_scores USING hnsw (player_embedding vector_cosine_ops);"))

    # Include relevant details from other tables in embedding
    df = pd.read_sql("""
        SELECT 
            pbs.game_id, g.game_timestamp, g.season, p.first_name, p.last_name, pbs.person_id, 
            t.city AS team_city, t.name AS team_name, t.abbreviation AS team_abbrev,
            opp.city AS opp_city, opp.name AS opp_name, opp.abbreviation AS opp_abbrev,
            g.home_team_id, g.away_team_id, h.abbreviation AS home_abbrev, a.abbreviation AS away_abbrev,
            pbs.points, pbs.offensive_reb AS oreb, pbs.defensive_reb AS dreb, pbs.assists
        FROM player_box_scores pbs
        JOIN players p ON pbs.person_id = p.player_id
        JOIN game_details g ON pbs.game_id = g.game_id
        JOIN teams t ON pbs.team_id = t.team_id
        JOIN teams opp ON (
            (g.home_team_id = opp.team_id AND pbs.team_id != g.home_team_id) OR
            (g.away_team_id = opp.team_id AND pbs.team_id != g.away_team_id)
        )
        JOIN teams h ON g.home_team_id = h.team_id
        JOIN teams a ON g.away_team_id = a.team_id
    """, eng)
    
    # Note: 7,224 player_box_scores rows (across 232 missing players) were skipped from embedding due to missing player metadata
    total = len(df)     # ~36k total player_box_scores rows but condensed down to ~29k
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        print(f"Embedding player row {i}/{total}")
        vec = ollama_embed(EMBED_MODEL, row_text_player(r))
        with eng.begin() as cx:
            cx.execute(text("""
                UPDATE player_box_scores 
                SET player_embedding = :v 
                WHERE game_id = :gid AND person_id = :pid 
            """), {"v": vec, "gid": int(r.game_id), "pid": int(r.person_id)})

    print(f"Finished Player Embeddings: {total} Rows Updated")  


def main():
    print("Starting Embedding Process")
    eng = sa.create_engine(DB_DSN)
    embed_games(eng)
    embed_players(eng)
    print("Finished Embedding Process")


if __name__ == "__main__":
    main()
    