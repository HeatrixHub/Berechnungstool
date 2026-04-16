"""Austauschlogik für portablen Isolierungs-Exporte und -Importe."""

from .export_service import (
    EXPORT_FILE_SUFFIX,
    EXPORT_FORMAT_NAME,
    EXPORT_FORMAT_VERSION,
    build_insulation_exchange_payload,
    export_insulations_to_file,
)
from .import_service import (
    ImportIssue,
    InsulationExchangeImportService,
    PreparedInsulationFamilyImport,
    PreparedInsulationImport,
    prepare_insulation_exchange_import_from_file,
)
from .matching_service import (
    FamilyMatchingResult,
    MatchingCandidate,
    PreparedInsulationImportMatchingAnalysis,
    PreparedInsulationImportMatchingService,
    VariantPerspective,
    analyze_prepared_insulation_import_matching,
)
from .decision_service import (
    ACTION_CREATE_NEW,
    ACTION_SELECT_CANDIDATE,
    ACTION_SKIP_IMPORT,
    ACTION_USE_EXACT_MATCH,
    FamilyDecisionInput,
    InsulationFamilyDecision,
    PreparedInsulationImportDecisionService,
    PreparedInsulationImportDecisions,
)
from .persistence_service import (
    FamilyPersistenceOutcome,
    PreparedInsulationImportPersistenceResult,
    PreparedInsulationImportPersistenceService,
)

from .normalization import (
    normalize_family_for_exchange,
    normalize_family_portable_for_compare,
    normalize_import_family_for_prepare,
    normalize_import_variant_for_prepare,
    normalize_variant_for_exchange,
    normalize_variant_portable_for_compare,
)

__all__ = [
    "EXPORT_FILE_SUFFIX",
    "EXPORT_FORMAT_NAME",
    "EXPORT_FORMAT_VERSION",
    "build_insulation_exchange_payload",
    "export_insulations_to_file",
    "ImportIssue",
    "InsulationExchangeImportService",
    "PreparedInsulationFamilyImport",
    "PreparedInsulationImport",
    "prepare_insulation_exchange_import_from_file",
    "FamilyMatchingResult",
    "MatchingCandidate",
    "PreparedInsulationImportMatchingAnalysis",
    "PreparedInsulationImportMatchingService",
    "VariantPerspective",
    "analyze_prepared_insulation_import_matching",
    "ACTION_CREATE_NEW",
    "ACTION_SELECT_CANDIDATE",
    "ACTION_SKIP_IMPORT",
    "ACTION_USE_EXACT_MATCH",
    "FamilyDecisionInput",
    "InsulationFamilyDecision",
    "PreparedInsulationImportDecisionService",
    "PreparedInsulationImportDecisions",
    "FamilyPersistenceOutcome",
    "PreparedInsulationImportPersistenceResult",
    "PreparedInsulationImportPersistenceService",
    "normalize_family_for_exchange",
    "normalize_family_portable_for_compare",
    "normalize_import_family_for_prepare",
    "normalize_import_variant_for_prepare",
    "normalize_variant_for_exchange",
    "normalize_variant_portable_for_compare",
]
