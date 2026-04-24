"""
TasteTaggingService — orchestrates flavour normalisation and DB persistence.

Pipeline for one canonical bean:
  1. Load existing raw flavour_notes from canonical_beans
  2. Run rule-based normaliser (free, instant)
  3. Send unmatched notes to LLM (optional, gated on API key)
  4. Upsert results into bean_flavour_tags
  5. Return summary

Idempotent: re-running updates confidence/source if a better match is found,
but never deletes manually-reviewed tags.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.canonical_bean import CanonicalBean
from app.models.enums import ReviewStatus
from app.models.flavour import BeanFlavourTag, FlavourTaxonomy
from app.services.taste.llm_normaliser import LLMTagResult, normalise_notes_llm
from app.services.taste.normaliser import RuleMatch, match_notes, unmatched_notes
from app.services.taste.prompts.v1 import PROMPT_VERSION

log = logging.getLogger(__name__)


@dataclass
class TaggingResult:
    bean_id: uuid.UUID
    total_notes: int
    rule_matched: int
    llm_matched: int
    unmatched: int
    tags_upserted: int


class TasteTaggingService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def tag_bean(self, bean: CanonicalBean, use_llm: bool = True) -> TaggingResult:
        """
        Normalise all flavour_notes for a bean and persist tags.
        """
        raw_notes: list[str] = list(bean.flavour_notes or [])
        if not raw_notes:
            return TaggingResult(bean_id=bean.id, total_notes=0, rule_matched=0,
                                 llm_matched=0, unmatched=0, tags_upserted=0)

        # Load taxonomy slug → id map (cached for the session)
        taxonomy_map = await self._get_taxonomy_map()

        # Step 1: Rule-based matching
        rule_results: list[tuple[str, RuleMatch | None]] = match_notes(raw_notes)
        unmatched = [note for note, match in rule_results if match is None]

        # Step 2: LLM for unmatched notes
        llm_results: list[LLMTagResult] = []
        if unmatched and use_llm and settings.ANTHROPIC_API_KEY:
            try:
                llm_results = await normalise_notes_llm(unmatched, api_key=settings.ANTHROPIC_API_KEY)
            except Exception as exc:
                log.error("LLM normalisation failed for bean %s: %s", bean.id, exc)

        # Step 3: Upsert tags
        upserted = 0
        rule_matched_count = 0
        llm_matched_count = 0
        still_unmatched = 0

        # Process rule matches
        for raw_note, match in rule_results:
            if match is None:
                continue
            if match.slug not in taxonomy_map:
                log.warning("Slug '%s' from rule-match not in DB taxonomy", match.slug)
                continue
            tax_id = taxonomy_map[match.slug]
            await self._upsert_tag(
                bean_id=bean.id,
                taxonomy_id=tax_id,
                raw_note=raw_note,
                confidence=match.confidence,
                source="rule",
                llm_audit=None,
            )
            rule_matched_count += 1
            upserted += 1

        # Process LLM matches
        for llm_result in llm_results:
            if llm_result.slug is None:
                still_unmatched += 1
                continue
            if llm_result.slug not in taxonomy_map:
                log.warning("LLM returned slug '%s' not in DB taxonomy", llm_result.slug)
                still_unmatched += 1
                continue
            tax_id = taxonomy_map[llm_result.slug]
            await self._upsert_tag(
                bean_id=bean.id,
                taxonomy_id=tax_id,
                raw_note=llm_result.raw_note,
                confidence=llm_result.confidence,
                source="llm",
                llm_audit={
                    "slug": llm_result.slug,
                    "confidence": llm_result.confidence,
                    "reasoning": llm_result.reasoning,
                    "prompt_version": PROMPT_VERSION,
                },
                # LLM results below 0.7 go to pending for human review
                review_status=(
                    ReviewStatus.pending if llm_result.confidence < 0.70
                    else ReviewStatus.accepted
                ),
            )
            llm_matched_count += 1
            upserted += 1

        # Count truly unmatched (no rule, no LLM)
        if not llm_results:
            still_unmatched = len(unmatched)

        await self.session.flush()

        return TaggingResult(
            bean_id=bean.id,
            total_notes=len(raw_notes),
            rule_matched=rule_matched_count,
            llm_matched=llm_matched_count,
            unmatched=still_unmatched,
            tags_upserted=upserted,
        )

    async def tag_all_beans(self, use_llm: bool = True) -> list[TaggingResult]:
        """Tag every canonical bean that has flavour_notes but no tags yet."""
        beans = (await self.session.execute(
            select(CanonicalBean)
        )).scalars().all()

        results = []
        for bean in beans:
            if not bean.flavour_notes:
                continue
            result = await self.tag_bean(bean, use_llm=use_llm)
            results.append(result)

        await self.session.commit()
        return results

    async def _get_taxonomy_map(self) -> dict[str, uuid.UUID]:
        """Return slug → id for all taxonomy nodes."""
        rows = (await self.session.execute(select(FlavourTaxonomy))).scalars().all()
        return {node.slug: node.id for node in rows}

    async def _upsert_tag(
        self,
        bean_id: uuid.UUID,
        taxonomy_id: uuid.UUID,
        raw_note: str,
        confidence: float,
        source: str,
        llm_audit: dict | None,
        review_status: ReviewStatus = ReviewStatus.accepted,
    ) -> None:
        """Insert or update a bean_flavour_tags row."""
        existing = (await self.session.execute(
            select(BeanFlavourTag).where(
                BeanFlavourTag.bean_id == bean_id,
                BeanFlavourTag.taxonomy_id == taxonomy_id,
                BeanFlavourTag.raw_note == raw_note,
            )
        )).scalar_one_or_none()

        if existing is None:
            tag = BeanFlavourTag(
                bean_id=bean_id,
                taxonomy_id=taxonomy_id,
                raw_note=raw_note,
                confidence=confidence,
                source=source,
                llm_audit=llm_audit,
                review_status=review_status,
            )
            self.session.add(tag)
        else:
            # Only upgrade: don't overwrite manual reviews
            if existing.review_status == ReviewStatus.accepted and confidence > existing.confidence:
                existing.confidence = confidence
                existing.source = source
                if llm_audit:
                    existing.llm_audit = llm_audit
