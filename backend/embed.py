import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text
from backend.config import DB_DSN, EMBED_MODEL
from backend.utils import ollama_embed

# Example of a row embedding for the game_details table
# TODO: Customize this
def row_text(r):
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date = ts.strftime('%Y-%m-%d')
    home = int(r.home_team_id)
    away = int(r.away_team_id)
    hp = int(r.home_points)
    ap = int(r.away_points)

    return (
        "game | "
        f"season:{int(r.season)} | "
        f"date:{date} | "
        f"home_team_id:{home} | "
        f"away_team_id:{away} | "
        f"home_points:{hp} | "
        f"away_points:{ap} | "
    )

# def main():
#     print("Starting Embedding Process")
#     eng = sa.create_engine(DB_DSN)
#     with eng.begin() as cx:
#         cx.execute(text('ALTER DATABASE nba REFRESH COLLATION VERSION'))
#         # TODO: Try with different embeddings, feel free to try different index type/distance functions as well
#         cx.execute(text("ALTER TABLE IF EXISTS game_details ADD COLUMN IF NOT EXISTS embedding vector(768);"))
#         cx.execute(text("CREATE INDEX IF NOT EXISTS idx_game_details_embedding ON game_details USING hnsw (embedding vector_cosine_ops);"))
#         df = pd.read_sql(
#             "SELECT game_id, season, game_timestamp, home_team_id, away_team_id, home_points, away_points FROM game_details ORDER BY game_timestamp DESC, game_id DESC",
#             cx,
#         )
#         for _, r in df.iterrows():
#             vec = ollama_embed(EMBED_MODEL, row_text(r))
#             cx.execute(text("UPDATE game_details SET embedding = :v WHERE game_id = :gid"), {"v": vec, "gid": int(r.game_id)})
#     print(f"Finished Embeddings: {len(df)} Rows Updated")


# if __name__ == "__main__":
#     main()

def row_text_game(r):
    '''
    '''
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date_long = ts.strftime('%B %d, %Y')
    date_slash =  ts.strftime('%m/%d/%Y')
    date_dash = ts.strftime('%Y-%m-%d')
    season = int(r.season)
    season_span = f"{season}-{str(season+1)[-2:]}"
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
    
    return(f"{date_long} | {date_slash} | {date_dash} | "
           f"{season} | {season_span} | "
           f"Home: {home_city} {home_name} ({home_abbrev}) | "
           f"Away: {away_city} {away_name} ({away_abbrev}) | "
           f"Matchup: {away_abbrev}@{home_abbrev} | "
           f"Score: {home_city} {home_name} {home_pts} - {away_pts} {away_city} {away_name} | "
           f"Winner: {winner} victory")


def row_text_player(r):
    '''
    '''
    name = f"{r.first_name} {r.last_name}"
    name_ascii = name.encode("ascii", "ignore").decode()
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date_long = ts.strftime('%B %d, %Y')
    date_slash =  ts.strftime('%m/%d/%Y')
    date_dash = ts.strftime('%Y-%m-%d')
    season = int(r.season)
    season_span = f"{season}-{str(season+1)[-2:]}"
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
           f"{date_long}| {date_slash} | {date_dash} | "
           f"{season} | {season_span} | "
           f"Team: {team_city} {team_name} ({team_abbrev}) | "
           f"Opponent: {opp_city} {opp_name} ({opp_abbrev}) | "
           f"Matchup: {away_abbrev}@{home_abbrev} | {team_city} {team_name} vs  {opp_city} {opp_name} | "
           f"Points: {pts} | Rebounds: {reb} | Assists: {ast} | {td} | {dd}")

def embed_games(cx):
    '''
    '''
    # cx.execute(text("ALTER TABLE IF EXISTS game_details ADD COLUMN IF NOT EXISTS game_embedding vector(768);"))
    # cx.execute(text("CREATE INDEX IF NOT EXISTS idx_game_details_game_embedding ON game_details USING hnsw (game_embedding vector_cosine_ops);"))
    
    df = pd.read_sql("""
        SELECT 
            g.game_id, g.season, g.game_timestamp, g.home_points, g.away_points, g.winning_team_id, 
            g.home_team_id, h.city AS home_city, h.name AS home_team_name, h.abbreviation AS home_abbrev,
            g.away_team_id, a.city AS away_city, a.name AS away_team_name, a.abbreviation AS away_abbrev
        FROM game_details g
        JOIN teams h ON g.home_team_id = h.team_id
        JOIN teams a ON g.away_team_id = a.team_id
        WHERE g.game_embedding IS NULL
        LIMIT 5
    """, cx)
    
    for _, r in df.iterrows():
        vec = ollama_embed(EMBED_MODEL, row_text_game(r))
        cx.execute(text("""
            UPDATE game_details 
            SET game_embedding = :v 
            WHERE game_id = :gid AND game_embedding IS NULL
        """), {"v": vec, "gid": int(r.game_id)})
        
    print(f"Finished Game Embeddings: {len(df)} Rows Updated")

def embed_players(cx):
    '''
    '''
    print("starting embed_players")
    # cx.execute(text("ALTER TABLE IF EXISTS player_box_scores ADD COLUMN IF NOT EXISTS player_embedding vector(768);"))
    # cx.execute(text("CREATE INDEX IF NOT EXISTS idx_player_box_scores_player_embedding ON player_box_scores USING hnsw (player_embedding vector_cosine_ops);"))
    
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
        WHERE pbs.player_embedding IS NULL
    """, cx)
    
    total = len(df)
    print(f"{total} player rows need embedding")
    
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        vec = ollama_embed(EMBED_MODEL, row_text_player(r))
        cx.execute(text("""
            UPDATE player_box_scores 
            SET player_embedding = :v 
            WHERE game_id = :gid AND person_id = :pid AND player_embedding IS NULL
        """), {"v": vec, "gid": int(r.game_id), "pid": int(r.person_id)})
        
        if i % 50 == 0 or i == total:  # adjust 50 to whatever interval you like
            print(f"Progress: {i}/{total} rows embedded ({total - i} remaining)")
            
    print(f"Finished Player Embeddings: {len(df)} Rows Updated")
        

def main():
    print("Starting Embedding Process")
    eng = sa.create_engine(DB_DSN)
    with eng.begin() as cx:
        cx.execute(text('ALTER DATABASE nba REFRESH COLLATION VERSION'))
        # embed_games(cx)
        embed_players(cx)
    print("Finished Embedding Process")


if __name__ == "__main__":
    main()