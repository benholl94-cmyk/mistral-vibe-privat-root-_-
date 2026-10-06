"""
Realtime Module - Echtzeit-Datenabruf und Live-Informationen

Dieses Modul ermöglicht:
- Echtzeit-Websuchen
- Live-Datenabruf von APIs
- RSS-Feed-Verarbeitung
- Caching von Ergebnisse
"""

from vibe.core.realtime.search import RealTimeSearch
from vibe.core.realtime.fetcher import DataFetcher
from vibe.core.realtime.cache import ResponseCache
from vibe.core.realtime.models import (
    SearchQuery,
    SearchResult,
    FetchRequest,
    FetchResponse,
)

__all__ = [
    "RealTimeSearch",
    "DataFetcher", 
    "ResponseCache",
    "SearchQuery",
    "SearchResult",
    "FetchRequest",
    "FetchResponse",
    "get_realtime_search",
    "get_data_fetcher",
]

_realtime_search: RealTimeSearch | None = None
_data_fetcher: DataFetcher | None = None


def get_realtime_search() -> RealTimeSearch:
    """Holt die globale Echtzeit-Suchinstanz"""
    global _realtime_search
    if _realtime_search is None:
        _realtime_search = RealTimeSearch()
    return _realtime_search


def get_data_fetcher() -> DataFetcher:
    """Holt die globale DataFetcher-Instanz"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher
