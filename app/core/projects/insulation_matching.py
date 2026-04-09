"""Matching-Engine für eingebettete Import-Isolierungen gegen lokale DB."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.core.isolierungen_db.logic import list_families

from .isolierung_embedding import (
    normalize_family_core_for_compare,
    normalize_family_for_compare,
    normalize_resolution_entry,
    normalize_variant_for_compare,
)

STATUS_EXACT_MATCH = "exact_match"
STATUS_CANDIDATE_CONFLICT = "candidate_conflict"
STATUS_NO_MATCH = "no_match"
STATUS_INVALID_REFERENCE = "invalid_reference"


@dataclass(frozen=True, slots=True)
class InsulationMatchingAnalysis:
    """Maschinenlesbares Analyse-Ergebnis für den Importfluss."""

    annotated_insulation_resolution: dict[str, Any]
    summary: dict[str, int]
    warnings: list[str]
    errors: list[str]


class InsulationImportMatchingService:
    """Analysiert importierte, tatsächlich verwendete Isolierungen."""

    def analyze(
        self,
        *,
        embedded_isolierungen: dict[str, Any],
        insulation_resolution: dict[str, Any],
    ) -> InsulationMatchingAnalysis:
        families_by_family_key, variants_by_variant_key, warnings = self._index_embedded(embedded_isolierungen)
        local_rows = self._load_local_rows()

        entries = insulation_resolution.get("entries", [])
        if not isinstance(entries, list):
            entries = []

        annotated_entries: list[dict[str, Any]] = []
        summary = {
            STATUS_EXACT_MATCH: 0,
            STATUS_CANDIDATE_CONFLICT: 0,
            STATUS_NO_MATCH: 0,
            STATUS_INVALID_REFERENCE: 0,
        }
        errors: list[str] = []

        for index, raw_entry in enumerate(entries):
            entry = normalize_resolution_entry(raw_entry if isinstance(raw_entry, dict) else {})
            status, family_id, variant_id, candidates, issues = self._match_entry(
                entry=entry,
                local_rows=local_rows,
                families_by_family_key=families_by_family_key,
                variants_by_variant_key=variants_by_variant_key,
            )
            summary[status] = summary.get(status, 0) + 1
            for issue in issues:
                errors.append(f"Entry {index}: {issue}")

            local_db = entry.get("local_db", {})
            if not isinstance(local_db, dict):
                local_db = {}
            local_db.update(
                {
                    "family_id": family_id,
                    "variant_id": variant_id,
                    "origin": local_db.get("origin"),
                    "match_status": status,
                    "candidates": candidates,
                }
            )
            entry["local_db"] = local_db
            # Sicherheitsanforderung: Kein stilles Umschalten.
            entry["active_source"] = "embedded"
            annotated_entries.append(entry)

        return InsulationMatchingAnalysis(
            annotated_insulation_resolution={"entries": annotated_entries},
            summary=summary,
            warnings=warnings,
            errors=errors,
        )

    def _index_embedded(
        self,
        embedded_isolierungen: dict[str, Any],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
        families = embedded_isolierungen.get("families", [])
        if not isinstance(families, list):
            return {}, {}, ["embedded_isolierungen.families ist keine Liste."]

        families_by_key: dict[str, dict[str, Any]] = {}
        variants_by_key: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for family in families:
            if not isinstance(family, dict):
                continue
            family_key = str(family.get("project_family_key", "")).strip()
            family_norm = normalize_family_for_compare(family)
            if family_key:
                if family_key in families_by_key:
                    warnings.append(f"Doppelter family_key in embedded_isolierungen: {family_key!r}.")
                families_by_key[family_key] = family_norm
            else:
                warnings.append("Familie ohne project_family_key in embedded_isolierungen gefunden.")
            variants = family.get("variants", [])
            if not isinstance(variants, list):
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_key = str(variant.get("project_variant_key", "")).strip()
                if not variant_key:
                    warnings.append(f"Variante ohne project_variant_key in Familie {family_key or '?'} gefunden.")
                    continue
                if variant_key in variants_by_key:
                    warnings.append(f"Doppelter variant_key in embedded_isolierungen: {variant_key!r}.")
                variants_by_key[variant_key] = {
                    "family": family_norm,
                    "variant": normalize_variant_for_compare(variant),
                }
        return families_by_key, variants_by_key, warnings

    def _load_local_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for family in list_families():
            if not isinstance(family, dict):
                continue
            family_norm = normalize_family_for_compare(family)
            family_core = normalize_family_core_for_compare(family)
            rows.append(
                {
                    "family_id": family_norm.get("id"),
                    "variant_id": None,
                    "family": family_norm,
                    "family_core": family_core,
                    "variant": None,
                }
            )
            for variant in family_norm.get("variants", []):
                rows.append(
                    {
                        "family_id": family_norm.get("id"),
                        "variant_id": variant.get("id"),
                        "family": family_norm,
                        "family_core": family_core,
                        "variant": variant,
                    }
                )
        return rows

    def _match_entry(
        self,
        *,
        entry: dict[str, Any],
        local_rows: list[dict[str, Any]],
        families_by_family_key: dict[str, dict[str, Any]],
        variants_by_variant_key: dict[str, dict[str, Any]],
    ) -> tuple[str, int | None, int | None, list[dict[str, Any]], list[str]]:
        issues: list[str] = []
        embedded_target = self._resolve_embedded_target(entry, families_by_family_key, variants_by_variant_key)
        project_key = str(entry.get("project_insulation_key", "")).strip()
        variant_key = entry.get("variant_key")
        family_key = str(entry.get("family_key", "")).strip()
        expected_key = variant_key if isinstance(variant_key, str) and variant_key.strip() else family_key
        if project_key and expected_key and project_key != expected_key:
            issues.append(
                "project_insulation_key ist inkonsistent zur Family-/Variant-Referenz "
                f"(project={project_key!r}, expected={expected_key!r})."
            )
        if embedded_target is None:
            issues.append(
                "Referenz aus insulation_resolution nicht in embedded_isolierungen gefunden "
                f"(family_key={entry.get('family_key')!r}, variant_key={entry.get('variant_key')!r})."
            )
            return STATUS_INVALID_REFERENCE, None, None, [], issues

        exact = self._find_exact_match(embedded_target, local_rows)
        if exact is not None:
            return STATUS_EXACT_MATCH, exact["family_id"], exact["variant_id"], [], issues

        candidates = self._find_candidates(embedded_target, local_rows)
        if candidates:
            return STATUS_CANDIDATE_CONFLICT, None, None, candidates, issues
        return STATUS_NO_MATCH, None, None, [], issues

    def _resolve_embedded_target(
        self,
        entry: dict[str, Any],
        families_by_family_key: dict[str, dict[str, Any]],
        variants_by_variant_key: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        variant_key = entry.get("variant_key")
        if isinstance(variant_key, str) and variant_key.strip():
            return variants_by_variant_key.get(variant_key.strip())
        family_key = str(entry.get("family_key", "")).strip()
        family = families_by_family_key.get(family_key)
        if family is None:
            return None
        return {"family": family, "variant": None}

    def _find_exact_match(
        self,
        embedded_target: dict[str, Any],
        local_rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        embedded_family_core = normalize_family_core_for_compare(embedded_target["family"])
        embedded_variant = embedded_target.get("variant")
        for row in local_rows:
            if row["family_core"] != embedded_family_core:
                continue
            if embedded_variant is None and row["variant"] is None:
                return row
            if embedded_variant is not None and row["variant"] == embedded_variant:
                return row
        return None

    def _find_candidates(
        self,
        embedded_target: dict[str, Any],
        local_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        family_name = str(embedded_target["family"].get("name", "")).strip()
        variant = embedded_target.get("variant")
        variant_name = str(variant.get("name", "")).strip() if isinstance(variant, dict) else ""
        is_variant_target = isinstance(variant, dict)
        candidates: list[dict[str, Any]] = []

        for row in local_rows:
            if is_variant_target and row["variant"] is None:
                continue
            if not is_variant_target and row["variant"] is not None:
                continue

            local_family_name = str(row["family"].get("name", "")).strip()
            local_variant_name = ""
            if isinstance(row["variant"], dict):
                local_variant_name = str(row["variant"].get("name", "")).strip()

            family_ratio = self._similarity(family_name, local_family_name)
            variant_ratio = self._similarity(variant_name, local_variant_name) if is_variant_target else 0.0
            same_family_name = family_name.casefold() and family_name.casefold() == local_family_name.casefold()
            same_variant_name = (
                is_variant_target
                and variant_name.casefold()
                and variant_name.casefold() == local_variant_name.casefold()
            )

            reason: str | None = None
            score = max(family_ratio, variant_ratio)
            if same_family_name and (not is_variant_target or same_variant_name):
                reason = "name_match_but_values_differ"
                score = max(score, 0.95)
            elif same_family_name:
                reason = "family_name_match"
                score = max(score, 0.85)
            elif is_variant_target and same_variant_name:
                reason = "variant_name_match"
                score = max(score, 0.8)
            elif score >= 0.72:
                reason = "name_similarity"

            if reason is None:
                continue
            candidates.append(
                {
                    "family_id": row["family_id"],
                    "variant_id": row["variant_id"],
                    "reason": reason,
                    "score": round(score, 4),
                }
            )

        candidates.sort(key=lambda item: (item.get("score") or 0.0), reverse=True)
        return candidates[:5]

    def _similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(a=left.casefold(), b=right.casefold()).ratio()
