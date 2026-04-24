"""
Import all models here so SQLAlchemy's metadata and Alembic's
autogenerate can discover every table in one import.
"""

from app.models.store import Store
from app.models.source_page import SourcePage
from app.models.raw_extraction import RawExtraction
from app.models.canonical_bean import CanonicalBean
from app.models.bean_listing import BeanListing
from app.models.pricing import ListingVariant, PriceHistory
from app.models.resolution import CanonicalMatch, NormalisationMapping
from app.models.ingestion_run import IngestionRun
from app.models.flavour import FlavourTaxonomy, BeanFlavourTag
from app.models.assistant import AssistantLog

__all__ = [
    "Store",
    "SourcePage",
    "RawExtraction",
    "CanonicalBean",
    "BeanListing",
    "ListingVariant",
    "PriceHistory",
    "CanonicalMatch",
    "NormalisationMapping",
    "IngestionRun",
    "FlavourTaxonomy",
    "BeanFlavourTag",
    "AssistantLog",
]
