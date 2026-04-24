"""
Controlled vocabulary enums.

These are declared once here and reused across models and Alembic migrations.
Python-side enums drive both SQLAlchemy column types and application validation.
Raw source values are always stored alongside normalised values — never replaced.
"""

import enum


class RoastLevel(str, enum.Enum):
    light = "light"
    medium_light = "medium_light"
    medium = "medium"
    medium_dark = "medium_dark"
    dark = "dark"
    unknown = "unknown"


class GrindType(str, enum.Enum):
    whole_bean = "whole_bean"
    espresso = "espresso"
    filter = "filter"
    cafetiere = "cafetiere"
    moka = "moka"
    aeropress = "aeropress"
    pour_over = "pour_over"
    omni = "omni"
    unknown = "unknown"


class Process(str, enum.Enum):
    washed = "washed"
    natural = "natural"
    honey = "honey"
    anaerobic = "anaerobic"
    wet_hulled = "wet_hulled"
    carbonic_maceration = "carbonic_maceration"
    experimental = "experimental"
    unknown = "unknown"


class SourceType(str, enum.Enum):
    shopify = "shopify"
    html = "html"
    schema_org = "schema_org"
    dataset = "dataset"


class ParserStrategy(str, enum.Enum):
    shopify = "shopify"
    schema_org = "schema_org"
    html = "html"
    llm = "llm"
    unknown = "unknown"


class PageType(str, enum.Enum):
    listing = "listing"
    product = "product"
    feed = "feed"
    sitemap = "sitemap"
    homepage = "homepage"


class ExtractionMethod(str, enum.Enum):
    shopify_json = "shopify_json"
    schema_org = "schema_org"
    html_rules = "html_rules"
    llm = "llm"


class ValidationStatus(str, enum.Enum):
    valid = "valid"
    invalid = "invalid"
    partial = "partial"


class ListingStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class AvailabilityStatus(str, enum.Enum):
    in_stock = "in_stock"
    out_of_stock = "out_of_stock"
    preorder = "preorder"
    unknown = "unknown"


class MatchMethod(str, enum.Enum):
    exact = "exact"
    fuzzy = "fuzzy"
    embedding = "embedding"
    combined = "combined"
    manual = "manual"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    skipped = "skipped"


class MappingType(str, enum.Enum):
    grind = "grind"
    roast_level = "roast_level"
    process = "process"
    country = "country"
    region = "region"
    varietal = "varietal"


class RunType(str, enum.Enum):
    full = "full"
    incremental = "incremental"
    single_store = "single_store"
    single_page = "single_page"


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"
