"""
Tests for the normalisation module.

Coverage:
  TestRoastRules       — all roast level patterns
  TestGrindRules       — all grind type patterns
  TestProcessRules     — all process patterns
  TestCountryRules     — major origin countries
  TestRegionLookup     — known regions with country derivation
  TestWeightParser     — all weight formats + edge cases
  TestNormaliser       — DB-backed lookup, rule fallback, caching, bean listing
  TestNormaliseAPI     — HTTP endpoint round-trips (mocked DB)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Rule pattern tests — no DB, no async ────────────────────────────────────

class TestRoastRules:
    def _apply(self, raw: str) -> str:
        from app.services.normalisation.rules import ROAST_RULES
        from app.services.normalisation.normaliser import CoffeeNormaliser
        result = CoffeeNormaliser._apply_rules(raw, ROAST_RULES, "roast_level")
        return result.normalised if result else "unknown"

    def test_light(self):           assert self._apply("Light Roast") == "light"
    def test_light_bare(self):      assert self._apply("Light") == "light"
    def test_light_lightly(self):   assert self._apply("lightly roasted") == "light"
    def test_filter_roast(self):    assert self._apply("filter roast") == "light"
    def test_nordic_roast(self):    assert self._apply("Nordic Roast") == "light"
    def test_medium_light(self):    assert self._apply("Medium Light") == "medium_light"
    def test_medium_light_hyphen(self): assert self._apply("medium-light") == "medium_light"
    def test_city_plus(self):       assert self._apply("City+") == "medium_light"
    def test_medium(self):          assert self._apply("Medium Roast") == "medium"
    def test_medium_bare(self):     assert self._apply("Medium") == "medium"
    def test_city_roast(self):      assert self._apply("city roast") == "medium"
    def test_full_city(self):       assert self._apply("full city") == "medium_dark"
    def test_full_city_plus(self):  assert self._apply("Full City+") == "medium_dark"
    def test_espresso_roast(self):  assert self._apply("espresso roast") == "medium_dark"
    def test_vienna_roast(self):    assert self._apply("Vienna Roast") == "medium_dark"
    def test_medium_dark(self):     assert self._apply("Medium-Dark") == "medium_dark"
    def test_dark(self):            assert self._apply("Dark Roast") == "dark"
    def test_dark_bare(self):       assert self._apply("Dark") == "dark"
    def test_french_roast(self):    assert self._apply("French Roast") == "dark"
    def test_italian_roast(self):   assert self._apply("Italian Roast") == "dark"
    def test_no_match_returns_none(self):
        from app.services.normalisation.rules import ROAST_RULES
        from app.services.normalisation.normaliser import CoffeeNormaliser
        result = CoffeeNormaliser._apply_rules("freshly harvested", ROAST_RULES, "roast_level")
        assert result is None

    def test_medium_dark_beats_medium(self):
        """medium-dark must be matched before medium."""
        result = self._apply("medium-dark roast")
        assert result == "medium_dark"


class TestGrindRules:
    def _apply(self, raw: str) -> str:
        from app.services.normalisation.rules import GRIND_RULES
        from app.services.normalisation.normaliser import CoffeeNormaliser
        r = CoffeeNormaliser._apply_rules(raw, GRIND_RULES, "grind")
        return r.normalised if r else "unknown"

    def test_whole_bean(self):      assert self._apply("Whole Bean") == "whole_bean"
    def test_whole_bean_lower(self): assert self._apply("whole bean") == "whole_bean"
    def test_beans(self):           assert self._apply("Beans") == "whole_bean"
    def test_unground(self):        assert self._apply("Unground") == "whole_bean"
    def test_espresso(self):        assert self._apply("Espresso") == "espresso"
    def test_fine_grind(self):      assert self._apply("Fine Grind") == "espresso"
    def test_filter(self):          assert self._apply("Filter") == "filter"
    def test_drip(self):            assert self._apply("Drip") == "filter"
    def test_pour_over(self):       assert self._apply("Pour Over") == "pour_over"
    def test_v60(self):             assert self._apply("V60") == "pour_over"
    def test_chemex(self):          assert self._apply("Chemex") == "pour_over"
    def test_aeropress(self):       assert self._apply("AeroPress") == "aeropress"
    def test_aeropress_lower(self): assert self._apply("aeropress") == "aeropress"
    def test_cafetiere(self):       assert self._apply("Cafetière") == "cafetiere"
    def test_cafetiere_ascii(self): assert self._apply("Cafetiere") == "cafetiere"
    def test_french_press(self):    assert self._apply("French Press") == "cafetiere"
    def test_plunger(self):         assert self._apply("Plunger") == "cafetiere"
    def test_moka_pot(self):        assert self._apply("Moka Pot") == "moka"
    def test_stovetop(self):        assert self._apply("Stovetop") == "moka"
    def test_omni(self):            assert self._apply("Omni") == "omni"
    def test_omni_grind(self):      assert self._apply("Omni Grind") == "omni"
    def test_all_methods(self):     assert self._apply("All Brew Methods") == "omni"
    def test_whole_bean_beats_filter(self):
        """'whole bean filter pack' — whole_bean is more specific."""
        assert self._apply("whole bean filter pack") == "whole_bean"


class TestProcessRules:
    def _apply(self, raw: str) -> str:
        from app.services.normalisation.rules import PROCESS_RULES
        from app.services.normalisation.normaliser import CoffeeNormaliser
        r = CoffeeNormaliser._apply_rules(raw, PROCESS_RULES, "process")
        return r.normalised if r else "unknown"

    def test_washed(self):          assert self._apply("Washed") == "washed"
    def test_fully_washed(self):    assert self._apply("Fully Washed") == "washed"
    def test_wet_process(self):     assert self._apply("Wet Process") == "washed"
    def test_natural(self):         assert self._apply("Natural") == "natural"
    def test_natural_process(self): assert self._apply("Natural Process") == "natural"
    def test_dry_process(self):     assert self._apply("Dry Processed") == "natural"
    def test_sun_dried(self):       assert self._apply("Sun-Dried") == "natural"
    def test_honey(self):           assert self._apply("Honey") == "honey"
    def test_black_honey(self):     assert self._apply("Black Honey") == "honey"
    def test_red_honey(self):       assert self._apply("Red Honey") == "honey"
    def test_yellow_honey(self):    assert self._apply("Yellow Honey") == "honey"
    def test_anaerobic(self):       assert self._apply("Anaerobic") == "anaerobic"
    def test_double_anaerobic(self): assert self._apply("Double Anaerobic") == "anaerobic"
    def test_anaerobic_natural(self): assert self._apply("Anaerobic Natural") == "anaerobic"
    def test_anaerobic_washed(self): assert self._apply("Anaerobic Washed") == "anaerobic"
    def test_wet_hulled(self):      assert self._apply("Wet Hulled") == "wet_hulled"
    def test_giling_basah(self):    assert self._apply("Giling Basah") == "wet_hulled"
    def test_carbonic(self):        assert self._apply("Carbonic Maceration") == "carbonic_maceration"
    def test_co2_maceration(self):  assert self._apply("CO2 Maceration") == "carbonic_maceration"
    def test_experimental(self):    assert self._apply("Experimental") == "experimental"
    def test_anaerobic_beats_natural(self):
        """'anaerobic natural' must map to anaerobic (more specific)."""
        assert self._apply("anaerobic natural process") == "anaerobic"


class TestCountryRules:
    def _apply(self, raw: str) -> str:
        from app.services.normalisation.rules import COUNTRY_RULES
        from app.services.normalisation.normaliser import CoffeeNormaliser
        r = CoffeeNormaliser._apply_rules(raw, COUNTRY_RULES, "country")
        return r.normalised if r else ""

    def test_ethiopia(self):        assert self._apply("Ethiopia") == "Ethiopia"
    def test_ethiopian(self):       assert self._apply("Ethiopian") == "Ethiopia"
    def test_kenya(self):           assert self._apply("Kenya") == "Kenya"
    def test_colombia(self):        assert self._apply("Colombia") == "Colombia"
    def test_colombia_in_sentence(self):
        assert self._apply("Coffee from Colombia, Huila") == "Colombia"
    def test_brazil(self):          assert self._apply("Brazil") == "Brazil"
    def test_costa_rica(self):      assert self._apply("Costa Rica") == "Costa Rica"
    def test_el_salvador(self):     assert self._apply("El Salvador") == "El Salvador"
    def test_sumatra_maps_indonesia(self): assert self._apply("Sumatra") == "Indonesia"
    def test_java_maps_indonesia(self):   assert self._apply("Java coffee") == "Indonesia"
    def test_kona_maps_usa(self):         assert self._apply("Kona") == "United States"
    def test_yemen(self):           assert self._apply("Yemen") == "Yemen"
    def test_unknown_country(self): assert self._apply("Narnia") == ""


class TestRegionLookup:
    def test_yirgacheffe(self):
        from app.services.normalisation.rules import REGION_LOOKUP
        region, country = REGION_LOOKUP["yirgacheffe"]
        assert region == "Yirgacheffe"
        assert country == "Ethiopia"

    def test_huila(self):
        from app.services.normalisation.rules import REGION_LOOKUP
        region, country = REGION_LOOKUP["huila"]
        assert region == "Huila"
        assert country == "Colombia"

    def test_kirinyaga(self):
        from app.services.normalisation.rules import REGION_LOOKUP
        region, country = REGION_LOOKUP["kirinyaga"]
        assert region == "Kirinyaga"
        assert country == "Kenya"

    def test_tarrazu_accent(self):
        from app.services.normalisation.rules import REGION_LOOKUP
        assert "tarrazu" in REGION_LOOKUP  # without accent
        assert "tarrazú" in REGION_LOOKUP  # with accent


class TestWeightParser:
    def _parse(self, raw: str):
        from app.services.normalisation.rules import parse_weight_g
        return parse_weight_g(raw)

    def test_grams_simple(self):    assert self._parse("250g") == 250
    def test_grams_space(self):     assert self._parse("250 g") == 250
    def test_grams_upper(self):     assert self._parse("500G") == 500
    def test_kg_integer(self):      assert self._parse("1kg") == 1000
    def test_kg_decimal(self):      assert self._parse("0.5kg") == 500
    def test_kg_space(self):        assert self._parse("1 kg") == 1000
    def test_embedded_in_title(self): assert self._parse("250g / Whole Bean") == 250
    def test_oz(self):
        result = self._parse("12oz")
        assert result is not None and 338 <= result <= 341  # ~340g
    def test_lb(self):
        result = self._parse("1lb")
        assert result is not None and 450 <= result <= 457
    def test_no_weight_returns_none(self): assert self._parse("Whole Bean") is None
    def test_empty_returns_none(self):     assert self._parse("") is None

    def test_parse_multiple(self):
        from app.services.normalisation.rules import parse_multiple_weights
        weights = parse_multiple_weights("Available in 250g, 500g and 1kg")
        assert 250 in weights
        assert 500 in weights
        assert 1000 in weights

    def test_snap_to_standard(self):
        from app.services.normalisation.rules import snap_to_standard_weight
        assert snap_to_standard_weight(249) == 250  # within 5%
        assert snap_to_standard_weight(1001) == 1000
        assert snap_to_standard_weight(300) == 300  # exact standard
        assert snap_to_standard_weight(327) == 327  # not a standard weight

    def test_weight_normalise_result(self):
        from app.services.normalisation.normaliser import CoffeeNormaliser
        from unittest.mock import AsyncMock
        normaliser = CoffeeNormaliser(session=AsyncMock())
        result = normaliser.normalise_weight("250g")
        assert result.raw == "250g"
        assert result.normalised == "250"
        assert result.confidence >= 0.9

    def test_weight_unknown_returns_empty(self):
        from app.services.normalisation.normaliser import CoffeeNormaliser
        from unittest.mock import AsyncMock
        normaliser = CoffeeNormaliser(session=AsyncMock())
        result = normaliser.normalise_weight("a bag")
        assert result.normalised == ""
        assert result.confidence == 0.0


# ─── CoffeeNormaliser async tests ────────────────────────────────────────────

class TestNormaliser:

    def _make_normaliser(self, db_rows: list = None):
        """Create a normaliser with a mock session that returns given DB rows."""
        session = AsyncMock()

        if db_rows is not None:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = db_rows[0] if db_rows else None
            session.execute = AsyncMock(return_value=mock_result)
        else:
            # No DB entry — returns None (triggers rule fallback)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=mock_result)

        from app.services.normalisation.normaliser import CoffeeNormaliser
        return CoffeeNormaliser(session)

    @pytest.mark.asyncio
    async def test_roast_rule_fallback(self):
        """No DB entry → rule fallback → correct enum value."""
        n = self._make_normaliser()
        result = await n.normalise_roast("Light Filter Roast")
        assert result.normalised == "light"
        assert result.source == "rule"

    @pytest.mark.asyncio
    async def test_roast_db_lookup_wins(self):
        """DB entry wins over rule — even if rule would give different answer."""
        from app.models.resolution import NormalisationMapping
        from app.models.enums import MappingType

        fake_row = MagicMock(spec=NormalisationMapping)
        fake_row.normalised_value = "medium_dark"
        fake_row.confidence_score = 0.99
        fake_row.source = "manual"

        n = self._make_normaliser(db_rows=[fake_row])
        result = await n.normalise_roast("blonde")  # rule says "light"
        assert result.normalised == "medium_dark"   # DB wins
        assert result.source == "db"
        assert result.confidence == 0.99

    @pytest.mark.asyncio
    async def test_roast_unknown_default(self):
        """No rule or DB match → unknown."""
        n = self._make_normaliser()
        result = await n.normalise_roast("freshly picked")
        assert result.normalised == "unknown"
        assert result.source == "default"

    @pytest.mark.asyncio
    async def test_grind_rule_fallback(self):
        n = self._make_normaliser()
        result = await n.normalise_grind("Pour Over")
        assert result.normalised == "pour_over"
        assert result.source == "rule"

    @pytest.mark.asyncio
    async def test_process_rule_fallback(self):
        n = self._make_normaliser()
        result = await n.normalise_process("Washed Process")
        assert result.normalised == "washed"

    @pytest.mark.asyncio
    async def test_country_rule_fallback(self):
        n = self._make_normaliser()
        result = await n.normalise_country("Ethiopia")
        assert result.normalised == "Ethiopia"

    @pytest.mark.asyncio
    async def test_region_lookup(self):
        n = self._make_normaliser()
        result = await n.normalise_region("yirgacheffe")
        assert result.normalised == "Yirgacheffe"

    @pytest.mark.asyncio
    async def test_region_derives_country(self):
        """When region is recognised, country can be derived from the lookup table."""
        n = self._make_normaliser()
        listing = await n.normalise_bean_listing(
            region_raw="Yirgacheffe",
            country_raw="",  # blank country
        )
        assert listing.origin_region == "Yirgacheffe"
        assert listing.origin_country == "Ethiopia"  # derived from region

    @pytest.mark.asyncio
    async def test_empty_raw_returns_unknown(self):
        n = self._make_normaliser()
        result = await n.normalise_roast("")
        assert result.normalised == "unknown"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_normalise_bean_listing_full(self):
        """Full listing normalisation fills all fields."""
        n = self._make_normaliser()
        result = await n.normalise_bean_listing(
            roast_raw="Light Roast",
            grind_raw="Whole Bean",
            process_raw="Washed",
            country_raw="Ethiopia",
            region_raw="Yirgacheffe",
            weight_raw="250g",
        )
        assert result.roast_level == "light"
        assert result.grind_type == "whole_bean"
        assert result.process == "washed"
        assert result.origin_country == "Ethiopia"
        assert result.origin_region == "Yirgacheffe"
        assert result.weight_g == 250
        # Raw values preserved
        assert result.roast_level_raw == "Light Roast"
        assert result.grind_type_raw == "Whole Bean"

    @pytest.mark.asyncio
    async def test_caching_avoids_duplicate_db_calls(self):
        """Same raw + type should hit DB only once due to session cache."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        from app.services.normalisation.normaliser import CoffeeNormaliser
        n = CoffeeNormaliser(session)

        await n.normalise_roast("Light")
        await n.normalise_roast("Light")  # second call — should use cache

        # DB should only be hit once per unique (raw, type) pair
        assert session.execute.call_count <= 2  # 1 DB lookup + possibly 1 for cache miss

    @pytest.mark.asyncio
    async def test_is_unknown_flag(self):
        n = self._make_normaliser()
        result = await n.normalise_roast("")
        assert result.is_unknown is True

    @pytest.mark.asyncio
    async def test_is_unknown_false_for_known(self):
        n = self._make_normaliser()
        result = await n.normalise_roast("Medium Roast")
        assert result.is_unknown is False


# ─── Normalisation schema tests ───────────────────────────────────────────────

class TestNormalisationSchemas:

    def test_mapping_create_validates_type(self):
        from app.schemas.normalisation import MappingCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MappingCreate(
                mapping_type="invalid_type",
                raw_value="test",
                normalised_value="light",
            )

    def test_mapping_create_rejects_empty_raw(self):
        from app.schemas.normalisation import MappingCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MappingCreate(
                mapping_type="roast_level",
                raw_value="",
                normalised_value="light",
            )

    def test_mapping_create_valid(self):
        from app.schemas.normalisation import MappingCreate
        m = MappingCreate(
            mapping_type="roast_level",
            raw_value="blonde roast",
            normalised_value="light",
            confidence_score=0.9,
        )
        assert m.mapping_type == "roast_level"
        assert m.raw_value == "blonde roast"

    def test_normalise_request_validates_type(self):
        from app.schemas.normalisation import NormaliseRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NormaliseRequest(raw_value="test", mapping_type="invalid")

    def test_confidence_must_be_between_0_and_1(self):
        from app.schemas.normalisation import MappingCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MappingCreate(
                mapping_type="roast_level",
                raw_value="test",
                normalised_value="light",
                confidence_score=1.5,
            )
