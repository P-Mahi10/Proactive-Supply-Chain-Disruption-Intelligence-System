import os
from typing import List, Dict

import psycopg2
from psycopg2.extras import RealDictCursor

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def fetch_best_routes(limit: int = 5) -> List[Dict]:
    query = """
        SELECT r.origin, r.destination, tm.name,
               rm.cost_per_unit, rm.estimated_time_hours
        FROM route_metrics rm
        JOIN route_options ro ON rm.route_option_id = ro.id
        JOIN routes r ON ro.route_id = r.id
        JOIN transport_modes tm ON ro.transport_mode_id = tm.id
        WHERE rm.condition_type = 'current'
        ORDER BY rm.cost_per_unit ASC
        LIMIT %s;
    """

    try:
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Failed to fetch routes: %s", exc)
        return []
