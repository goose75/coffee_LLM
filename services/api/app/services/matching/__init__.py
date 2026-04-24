from app.services.matching.service import CanonicalMatchingService, MatchDecision
from app.services.matching.signals import MatchSignals, build_signals, score_exact_fields, score_fuzzy_title, score_embeddings, score_harvest_year, combine_signals
from app.services.matching.embeddings import build_embedding_text, generate_embedding

__all__ = [
    "CanonicalMatchingService",
    "MatchDecision",
    "MatchSignals",
    "build_signals",
    "score_exact_fields",
    "score_fuzzy_title",
    "score_embeddings",
    "score_harvest_year",
    "combine_signals",
    "build_embedding_text",
    "generate_embedding",
]
