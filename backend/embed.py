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
    home_pts = int(r.home_pts)
    away_city = (r.away_city)
    away_name = (r.away_team_name)
    away_abbrev = (r.away_abbrev)
    away_pts = int(r.away_pts)
    
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
    name_ascii = ()
    ts = pd.to_datetime(r.game_timestamp, utc=True)
    date_long = ts.strftime('%B %d, %Y')
    date_slash =  ts.strftime('%m/%d/%Y')
    date_dash = ts.strftime('%Y-%m-%d')
    season = int(r.season)
    season_span = f"{season}-{str(season+1)[-2:]}"
    team_city = ()
    team_name = ()
    team_abbrev = ()
    opp_city = ()
    opp_name = ()
    opp_abbrev = ()
    home_abbrev = ()
    away_abbrev = ()
    pts = int()
    reb = int()
    ast = int()
    td = ()
    dd = ()
    
    return(f"{name} | {name_ascii} | "
           f"{date_long}| {date_slash} | {date_dash} | "
           f"{season} | {season_span} | "
           f"Team: {team_city} {team_name} ({team_abbrev}) | "
           f"Opponent: {opp_city} {opp_name} ({opp_abbrev}) | "
           f"Matchup: {away_abbrev}@{home_abbrev} | {team_city} {team_name} vs  {opp_city} {opp_name} | "
           f"Points: {pts} | Rebounds: {reb} | Assists: {ast} | "
           f"Triple-Double: {td} | Double-Double: {dd}")

def embed_games(cx):
    '''
    '''
    cx.execute(text("ALTER TABLE IF EXISTS game_details ADD COLUMN IF NOT EXISTS game_embedding vector(768);"))
    cx.execute(text("CREATE INDEX IF NOT EXISTS idx_game_details_embedding ON game_details USING hnsw (game_embedding vector_cosine_ops);"))
    
    df = pd.read_sql("""
        SELECT 
            g.game_id, g.season, g.game_timestamp, g.home_points, g.away_points, g.winning_team_id, 
            g.home_team_id, h.city AS home_city, h.name AS home_team_name, h.abbreviation AS home_abbrev,
            g.away_team_id, a.city AS away_city, a.name AS away_team_name, a.abbreviation AS away_abbrev
        FROM game_details g
        JOIN teams h ON g.home_team_id = h.team_id
        JOIN teams a ON g.away_team_id = a.team_id
    """, cx)
    
    for _, r in df.iterrows():
        vec = ollama_embed(EMBED_MODEL, row_text_game(r))
        cx.execute(text("""
            UPDATE game_details 
            SET game_embedding = :v 
            WHERE game_id = :gid
        """), {"v": vec, "gid": int(r.game_id)})
        
    print(f"Finished Game Embeddings: {len(df)} Rows Updated")

def embed_players(cx):
    '''
    '''
    cx.execute(text("ALTER TABLE IF EXISTS player_box_scores ADD COLUMN IF NOT EXISTS player_embedding vector(768);"))
    cx.execute(text("CREATE INDEX IF NOT EXISTS idx_player_box_scores_embedding ON player_box_scores USING hnsw (player_embedding vector_cosine_ops);"))
    
    df = pd.read_sql("""
        SELECT
        FROM player_box_scores
        JOIN             
    """, cx)
    
    for _, r in df.iterrows():
        vec = ollama_embed(EMBED_MODEL, row_text_player(r))
        cx.execute(text("""
            UPDATE player_box_scores 
            SET player_embedding = :v 
            WHERE game_id = :gid AND player_id = :pid
        """), {"v": vec, "gid": int(r.game_id), "pid": int(r.player_id)})
        
    print(f"Finished Player Embeddings: {len(df)} Rows Updated")
        

def main():
    print("Starting Embedding Process")
    eng = sa.create_engine(DB_DSN)
    with eng.begin() as cx:
        cx.execute(text('ALTER DATABASE nba REFRESH COLLATION VERSION'))
        embed_games(cx)
        embed_players(cx)
    print("Finished Embedding Process")


if __name__ == "__main__":
    main()