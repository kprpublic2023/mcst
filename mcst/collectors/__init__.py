"""플랫폼별 수집기 모듈."""
from .base import BaseCollector, CollectResult
from .youtube import YouTubeCollector
from .instagram import InstagramCollector
from .x import XCollector
from .facebook import FacebookCollector
from .blog import BlogCollector

REGISTRY: dict[str, type[BaseCollector]] = {
    "youtube": YouTubeCollector,
    "instagram": InstagramCollector,
    "x": XCollector,
    "facebook": FacebookCollector,
    "blog": BlogCollector,
}

__all__ = ["BaseCollector", "CollectResult", "REGISTRY"]
