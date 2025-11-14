"""SQL queries for eligible titles from Sources of Truth (SOT)."""
from datetime import datetime, timedelta
from typing import List, Optional, Set


def get_eligible_titles_query(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sot_types: Optional[List[str]] = None,
) -> str:
    """
    Generate SQL query for fetching eligible titles from various SOTs.
    
    Args:
        start_date: Start date for the query window (defaults to 7 days ago)
        end_date: End date for the query window (defaults to today)
        sot_types: List of SOT types to include (defaults to all)
        
    Returns:
        SQL query string
    """
    # Default to rolling 7-day window
    if start_date is None:
        start_date = datetime.now() - timedelta(days=7)
    if end_date is None:
        end_date = datetime.now()
        
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Valid SOT types
    valid_sots = {
        "imdb", "rt", "award", "vibe", "narrative", 
        "most_liked", "leaving_soon", "just_added"
    }
    
    # Filter SOT types if specified
    if sot_types:
        selected_sots = set(sot_types) & valid_sots
    else:
        selected_sots = valid_sots
    
    # Build the query
    query = f"""
WITH params AS (
    SELECT '{start_str}'::date AS start_date,
           '{end_str}'::date AS end_date
)"""
    
    # Add leaving_soon CTE if needed
    if "leaving_soon" in selected_sots:
        query += """
, leaving_soon_sot AS (
    SELECT b.*
    FROM (
        SELECT DISTINCT 
            COALESCE(series_id, video_id) AS program_id,
            'leaving_soon' AS sot_name,
            end_ts::date AS window_end
        FROM content.content_availability
        WHERE to_date(date, 'yyyyMMdd') BETWEEN (SELECT start_date FROM params) 
              AND (SELECT end_date FROM params)
            AND active 
            AND contains_tubitv 
            AND policy
            AND country = 'US'
            AND datediff(end_ts::date, to_date(date, 'yyyyMMdd')) BETWEEN 0 AND 6
    ) b
    JOIN core_prod.dsa.dsac_program_info p
        ON b.program_id = p.program_id
    WHERE p.is_cms_shiny = 1
)"""
    
    # Add just_added CTE if needed
    if "just_added" in selected_sots:
        query += """
, just_added_sot AS (
    SELECT DISTINCT 
        program_id,
        'just_added' AS sot_name,
        window_start
    FROM core_prod.dsa.dsac_program_metadata
    WHERE ds BETWEEN (SELECT start_date FROM params) 
          AND (SELECT end_date FROM params)
        AND date_diff(ds, window_start) BETWEEN 0 AND 6
        AND country = 'US'
        AND is_cms_shiny = 1
)"""
    
    # Build the main query with UNIONs
    query += """
, sot_raw AS ("""
    
    unions = []
    
    if "imdb" in selected_sots:
        unions.append("""
    SELECT DISTINCT 
        x.tubi_video_id AS program_id,
        'imdb' AS sot_name
    FROM core_prod.imdb.imdb_title_essential_v2 imdb
    JOIN core_prod.universal_content_db.tubi_imdb_id_mapping x 
        ON x.imdb_id = imdb.titleId
    WHERE imdb.imdbRating.rating >= 8.0""")
    
    if "rt" in selected_sots:
        unions.append("""
    SELECT DISTINCT 
        program_id,
        'rt' AS sot_name
    FROM core_dev.dsa_stg.yixinc_rt_df
    WHERE rating >= 80""")
    
    if "award" in selected_sots:
        unions.append("""
    SELECT 
        program_id,
        'award' AS sot_name
    FROM core_dev.dsa.dsa_raw_yixinc_award_df""")
    
    if "vibe" in selected_sots:
        unions.append("""
    SELECT 
        id AS program_id,
        'vibe' AS sot_name
    FROM core_dev.dsa_stg.yixinc_vibe_df""")
    
    if "narrative" in selected_sots:
        unions.append("""
    SELECT 
        id AS program_id,
        'narrative' AS sot_name
    FROM core_dev.dsa_stg.yixinc_narrative_df""")
    
    if "most_liked" in selected_sots:
        unions.append("""
    SELECT 
        content_id_value AS program_id,
        'most_liked' AS sot_name
    FROM core_prod.tensor_cdc.container_items 
    WHERE container_pk = (
        SELECT id
        FROM core_prod.tensor_cdc.containers
        WHERE container_id = 'most_liked' 
            AND deployment = 'production'
    )""")
    
    if "leaving_soon" in selected_sots:
        unions.append("""
    SELECT program_id, sot_name FROM leaving_soon_sot""")
    
    if "just_added" in selected_sots:
        unions.append("""
    SELECT program_id, sot_name FROM just_added_sot""")
    
    # Join all unions
    query += "\n    UNION ALL\n".join(unions)
    
    query += """
)
SELECT * FROM sot_raw"""
    
    return query


def get_eligible_titles_with_content_query(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sot_types: Optional[List[str]] = None,
) -> str:
    """
    Get eligible titles joined with content_info for poster URLs.
    
    Returns query with program_id, sot_name, and poster_img_url.
    """
    base_query = get_eligible_titles_query(start_date, end_date, sot_types)
    
    # Wrap the base query and join with content_info
    return f"""
WITH eligible_titles AS (
{base_query}
)
SELECT DISTINCT 
    et.program_id,
    et.sot_name,
    ci.content_id,
    ci.content_name,
    ci.content_type,
    ci.poster_img_url
FROM eligible_titles et
JOIN core_prod.tubidw.content_info ci
    ON et.program_id = ci.content_id
WHERE ci.poster_img_url IS NOT NULL
    AND ci.active = true
ORDER BY et.sot_name, et.program_id"""


def get_eligible_titles_count_query(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> str:
    """Get count of eligible titles by SOT type."""
    base_query = get_eligible_titles_query(start_date, end_date)
    
    return f"""
WITH eligible_titles AS (
{base_query}
)
SELECT 
    sot_name,
    COUNT(DISTINCT program_id) AS title_count
FROM eligible_titles
GROUP BY sot_name
ORDER BY title_count DESC"""
