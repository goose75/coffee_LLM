"""Pydantic v2 schemas for the normalisation mappings API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_MAPPING_TYPES = {"roast_level", "grind", "process", "country", "region", "varietal"}

VALID_NORMALISED_VALUES: dict[str, set[str]] = {
    "roast_level": {"light", "medium_light", "medium", "medium_dark", "dark", "unknown"},
    "grind": {"whole_bean", "espresso", "filter", "cafetiere", "moka", "aeropress", "pour_over", "omni", "unknown"},
    "process": {"washed", "natural", "honey", "anaerobic", "wet_hulled", "carbonic_maceration", "experimental", "unknown"},
    "country": set(),   # open vocabulary
    "region": set(),    # open vocabulary
    "varietal": set(),  # open vocabulary
}


class MappingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mapping_type: str
    raw_value: str
    normalised_value: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "manual"

    @field_validator("mapping_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_MAPPING_TYPES:
            raise ValueError(f"mapping_type must be one of {sorted(VALID_MAPPING_TYPES)}")
        return v

    @field_validator("raw_value")
    @classmethod
    def non_empty_raw(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_value must not be empty")
        return v.strip()

    @field_validator("normalised_value")
    @classmethod
    def non_empty_normalised(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("normalised_value must not be empty")
        return v.strip()


class MappingCreate(MappingBase):
    """Request body for creating a new mapping."""
    pass


class MappingUpdate(BaseModel):
    """Request body for updating an existing mapping (partial)."""
    normalised_value: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = None


class MappingItem(MappingBase):
    """Full mapping response with DB metadata."""
    id: UUID
    created_at: datetime
    updated_at: datetime


class PaginatedMappings(BaseModel):
    data: list[MappingItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class NormaliseRequest(BaseModel):
    """Request body for the /admin/mappings/normalise endpoint."""
    raw_value: str
    mapping_type: str

    @field_validator("mapping_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_MAPPING_TYPES:
            raise ValueError(f"mapping_type must be one of {sorted(VALID_MAPPING_TYPES)}")
        return v


class NormaliseResponse(BaseModel):
    """Response from the normalise endpoint."""
    raw_value: str
    mapping_type: str
    normalised_value: str
    confidence: float
    source: str       # "db" | "rule" | "default"
    is_unknown: bool


class BulkNormaliseRequest(BaseModel):
    """Normalise multiple values at once."""
    items: list[NormaliseRequest]


class VocabSummary(BaseModel):
    """Summary of mappings per type, for the admin UI header."""
    mapping_type: str
    count: int
    valid_values: list[str]
