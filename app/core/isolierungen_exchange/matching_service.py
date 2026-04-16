"""Matching-Analyse für vorbereitete Isolierungsimporte gegen lokale DB (read-only)."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Literal

from app.core.isolierungen_db.logic import get_family_by_id, list_families

from .import_service import PreparedInsulationImport
from .normalization import normalize_family_portable_for_compare

MatchingStatus = Literal["exact_match", "candidate_conflict", "no_match"]


@dataclass(frozen=True)
class VariantPerspective:
    exact_variant_names: list[str]
    missing_local_variant_names: list[str]
    conflicting_variant_names: list[str]
    additional_local_variant_names: list[str]


@dataclass(frozen=True)
class MatchingCandidate:
    family_id: int
    family_name: str
    priority: int
    reasons: list[str]
    variant_hints: VariantPerspective


@dataclass(frozen=True)
class FamilyMatchingResult:
    import_index: int
    import_family_name: str
    status: MatchingStatus
    exact_family_id: int | None
    candidates: list[MatchingCandidate]
    variant_analysis: VariantPerspective
    notes: list[str]


@dataclass(frozen=True)
class PreparedInsulationImportMatchingAnalysis:
    source_path: Path
    results: list[FamilyMatchingResult]
    summary: dict[str, int]
    warnings: list[str]


class PreparedInsulationImportMatchingService:
    """Vergleicht vorbereitete Importfamilien algorithmisch mit lokaler DB."""

    def __init__(
        self,
        *,
        local_family_provider: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._local_family_provider = local_family_provider or self._load_local_families

    def analyze(self, prepared: PreparedInsulationImport) -> PreparedInsulationImportMatchingAnalysis:
        local_families = self._local_family_provider()
        warnings = self._derive_global_warnings(prepared, local_families)

        results: list[FamilyMatchingResult] = []
        summary = {
            "exact_match": 0,
            "candidate_conflict": 0,
            "no_match": 0,
        }

        for family_import in prepared.families:
            result = self._analyze_family(family_import, local_families, prepared)
            summary[result.status] = summary.get(result.status, 0) + 1
            results.append(result)

        return PreparedInsulationImportMatchingAnalysis(
            source_path=prepared.source_path,
            results=results,
            summary=summary,
            warnings=warnings,
        )

    def _derive_global_warnings(
        self,
        prepared: PreparedInsulationImport,
        local_families: list[dict[str, Any]],
    ) -> list[str]:
        warnings: list[str] = []
        issue_count = len(prepared.issues)
        if issue_count:
            warnings.append(
                "PreparedInsulationImport enthält "
                f"{issue_count} Hinweis(e)/Warnung(en); Matching wird defensiv ohne automatische Entscheidung erstellt."
            )
        if not local_families:
            warnings.append("Lokale Isolierungsdatenbank enthält keine verwertbaren Familien.")
        return warnings

    def _analyze_family(
        self,
        family_import: Any,
        local_families: list[dict[str, Any]],
        prepared: PreparedInsulationImport,
    ) -> FamilyMatchingResult:
        imported_family = family_import.family
        imported_name = str(imported_family.get("name", "")).strip()
        imported_core = self._portable_family_core(imported_family)

        exact_row: dict[str, Any] | None = None
        candidates: list[MatchingCandidate] = []

        fallback_variant_analysis = VariantPerspective([], [], [], [])

        for local in local_families:
            local_portable = local["portable"]
            variant_analysis = self._analyze_variants(
                imported_variants=imported_family.get("variants", []),
                local_variants=local_portable.get("variants", []),
            )

            if self._portable_family_core(local_portable) == imported_core and self._is_variant_exact(variant_analysis):
                exact_row = local
                fallback_variant_analysis = variant_analysis
                break

            candidate = self._build_candidate(
                imported_name=imported_name,
                imported_core=imported_core,
                imported_variants=imported_family.get("variants", []),
                local=local,
                variant_analysis=variant_analysis,
                source_local=family_import.source_local,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda c: c.priority, reverse=True)

        family_issue_notes = [
            issue.message
            for issue in prepared.issues
            if issue.path and issue.path.startswith(f"isolierungen[{family_import.index}]")
        ]

        if exact_row is not None:
            return FamilyMatchingResult(
                import_index=family_import.index,
                import_family_name=imported_name,
                status="exact_match",
                exact_family_id=int(exact_row["id"]),
                candidates=[],
                variant_analysis=fallback_variant_analysis,
                notes=family_issue_notes,
            )

        status: MatchingStatus = "candidate_conflict" if candidates else "no_match"
        leading_variant = candidates[0].variant_hints if candidates else VariantPerspective([], [], [], [])

        return FamilyMatchingResult(
            import_index=family_import.index,
            import_family_name=imported_name,
            status=status,
            exact_family_id=None,
            candidates=candidates,
            variant_analysis=leading_variant,
            notes=family_issue_notes,
        )

    def _build_candidate(
        self,
        *,
        imported_name: str,
        imported_core: dict[str, Any],
        imported_variants: list[dict[str, Any]],
        local: dict[str, Any],
        variant_analysis: VariantPerspective,
        source_local: dict[str, Any] | None,
    ) -> MatchingCandidate | None:
        reasons: list[str] = []
        priority = 0

        local_portable = local["portable"]
        local_name = str(local_portable.get("name", "")).strip()

        same_name = imported_name.casefold() == local_name.casefold() if imported_name and local_name else False
        if same_name:
            reasons.append("same_family_name")
            priority += 70

        name_similarity = self._similarity(imported_name, local_name)
        if name_similarity >= 0.75 and not same_name:
            reasons.append(f"similar_family_name:{name_similarity:.2f}")
            priority += int(name_similarity * 20)

        if self._portable_family_core(local_portable) == imported_core:
            reasons.append("same_family_core_values")
            priority += 85

        overlap = self._variant_overlap_ratio(imported_variants, local_portable.get("variants", []))
        if overlap > 0:
            reasons.append(f"variant_name_overlap:{overlap:.2f}")
            priority += int(overlap * 15)

        hinted_local_id = None
        if isinstance(source_local, dict):
            hinted_local_id = source_local.get("family_id")
        try:
            if hinted_local_id is not None and int(hinted_local_id) == int(local["id"]):
                reasons.append("source_local_family_id_hint")
                priority += 12
        except (TypeError, ValueError):
            pass

        if not reasons:
            return None

        return MatchingCandidate(
            family_id=int(local["id"]),
            family_name=local_name,
            priority=priority,
            reasons=reasons,
            variant_hints=variant_analysis,
        )

    def _analyze_variants(
        self,
        *,
        imported_variants: list[dict[str, Any]],
        local_variants: list[dict[str, Any]],
    ) -> VariantPerspective:
        imported_by_name = {
            str(variant.get("name", "")).strip().casefold(): variant
            for variant in imported_variants
            if isinstance(variant, dict)
        }
        local_by_name = {
            str(variant.get("name", "")).strip().casefold(): variant
            for variant in local_variants
            if isinstance(variant, dict)
        }

        exact_names: list[str] = []
        missing_names: list[str] = []
        conflicting_names: list[str] = []
        additional_names: list[str] = []

        for name_key, imported_variant in imported_by_name.items():
            local_variant = local_by_name.get(name_key)
            canonical_name = str(imported_variant.get("name", "")).strip()
            if local_variant is None:
                missing_names.append(canonical_name)
                continue
            if imported_variant == local_variant:
                exact_names.append(canonical_name)
            else:
                conflicting_names.append(canonical_name)

        for name_key, local_variant in local_by_name.items():
            if name_key not in imported_by_name:
                additional_names.append(str(local_variant.get("name", "")).strip())

        exact_names.sort(key=str.casefold)
        missing_names.sort(key=str.casefold)
        conflicting_names.sort(key=str.casefold)
        additional_names.sort(key=str.casefold)

        return VariantPerspective(
            exact_variant_names=exact_names,
            missing_local_variant_names=missing_names,
            conflicting_variant_names=conflicting_names,
            additional_local_variant_names=additional_names,
        )

    @staticmethod
    def _is_variant_exact(variant_analysis: VariantPerspective) -> bool:
        return (
            not variant_analysis.missing_local_variant_names
            and not variant_analysis.conflicting_variant_names
            and not variant_analysis.additional_local_variant_names
        )

    @staticmethod
    def _portable_family_core(family: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": family.get("name"),
            "classification_temp": family.get("classification_temp"),
            "max_temp": family.get("max_temp"),
            "density": family.get("density"),
            "temps": family.get("temps"),
            "ks": family.get("ks"),
        }

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(a=left.casefold(), b=right.casefold()).ratio()

    def _variant_overlap_ratio(
        self,
        imported_variants: list[dict[str, Any]],
        local_variants: list[dict[str, Any]],
    ) -> float:
        imported_names = {
            str(variant.get("name", "")).strip().casefold()
            for variant in imported_variants
            if isinstance(variant, dict) and str(variant.get("name", "")).strip()
        }
        local_names = {
            str(variant.get("name", "")).strip().casefold()
            for variant in local_variants
            if isinstance(variant, dict) and str(variant.get("name", "")).strip()
        }
        if not imported_names or not local_names:
            return 0.0
        overlap = len(imported_names.intersection(local_names))
        return overlap / max(len(imported_names), len(local_names))

    def _load_local_families(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for family_summary in list_families():
            if not isinstance(family_summary, dict):
                continue
            family_id = family_summary.get("id")
            try:
                family = get_family_by_id(int(family_id))
            except Exception:
                continue
            try:
                portable = normalize_family_portable_for_compare(family)
            except ValueError:
                continue
            rows.append({"id": int(family["id"]), "portable": portable})
        return rows


def analyze_prepared_insulation_import_matching(
    prepared: PreparedInsulationImport,
) -> PreparedInsulationImportMatchingAnalysis:
    """Funktionaler Einstiegspunkt für read-only Matching-Analyse."""

    service = PreparedInsulationImportMatchingService()
    return service.analyze(prepared)
