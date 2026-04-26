import os
from typing import Dict, List, Union
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from app.schemas.response_schema import RecommendationItem
from app.utils.logger import get_logger

logger = get_logger(__name__)

backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(backend_dir / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_recommendations(_: Dict[str, Union[float, str]]) -> List[RecommendationItem]:
    logger.info("Fetching real recommendations from PostgreSQL.")
    
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not found, returning mock data.")
        return _get_mock_recommendations()

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        query = """
            SELECT r.origin, r.destination, tm.name as route, rm.cost_per_unit as cost, rm.estimated_time_hours as delay_factor
            FROM route_metrics rm
            JOIN route_options ro ON rm.route_option_id = ro.id
            JOIN routes r ON ro.route_id = r.id
            JOIN transport_modes tm ON ro.transport_mode_id = tm.id
            WHERE rm.condition_type = 'current'
            ORDER BY rm.cost_per_unit ASC
            LIMIT 4;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        recommendations = []
        for row in rows:
            route_val = str(row[2]).title() if row[2] else "Unknown"
            if route_val == "Air":
                route_val = "Air Freight"
                
            recommendations.append(RecommendationItem(
                route=route_val,
                cost=float(row[3]),
                delay_factor=float(row[4])
            ))
            
        cursor.close()
        conn.close()
        
        if not recommendations:
            return _get_mock_recommendations()
            
        return recommendations

    except Exception as e:
        logger.error(f"Error querying database: {e}")
        return _get_mock_recommendations()


def _get_mock_recommendations() -> List[RecommendationItem]:
    return [
        RecommendationItem(route="Route A", cost=100.0, delay_factor=0.8),
        RecommendationItem(route="Route B", cost=120.0, delay_factor=0.6),
        RecommendationItem(route="Air Freight", cost=300.0, delay_factor=0.4),
        RecommendationItem(route="Rail", cost=150.0, delay_factor=0.7),
    ]
