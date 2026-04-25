from typing import Dict, List, Union

from app.schemas.response_schema import RecommendationItem
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_alternative_routes() -> List[RecommendationItem]:
    # TODO: Replace with actual DB queries once schema is finalized.
    return [
        RecommendationItem(route="Route A", cost=100, delay_factor=0.8),
        RecommendationItem(route="Route B", cost=120, delay_factor=0.6),
    ]


def get_transport_modes() -> List[RecommendationItem]:
    # TODO: Replace with actual DB queries once schema is finalized.
    return [
        RecommendationItem(route="Air Freight", cost=300, delay_factor=0.4),
        RecommendationItem(route="Rail", cost=150, delay_factor=0.7),
    ]


def get_recommendations(_: Dict[str, Union[float, str]]) -> List[RecommendationItem]:
    logger.info("Fetching mock recommendations.")
    recommendations = get_alternative_routes() + get_transport_modes()
    return recommendations
