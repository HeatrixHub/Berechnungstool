import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def _install_gui_stubs() -> None:
    if "PySide6" not in sys.modules:
        class _Dummy:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __getattr__(self, _name: str):
                return _Dummy()

            def __call__(self, *args, **kwargs):
                return _Dummy()

        class _DummyMessageBox:
            information = warning = critical = staticmethod(lambda *_a, **_k: None)

        class _DummyFileDialog:
            @staticmethod
            def getOpenFileName(*_args, **_kwargs):
                return ("", "")

        class _QtWidgetsModule(types.ModuleType):
            def __getattr__(self, name: str):
                if name == "QMessageBox":
                    return _DummyMessageBox
                if name == "QFileDialog":
                    return _DummyFileDialog
                return _Dummy

        class _QtCoreModule(types.ModuleType):
            def __getattr__(self, _name: str):
                if _name == "Qt":
                    class _Qt:
                        AlignRight = 0x0002
                        AlignLeft = 0x0001
                        AlignHCenter = 0x0004
                        AlignVCenter = 0x0080
                        CaseInsensitive = 0
                        DisplayRole = 0
                        EditRole = 1
                        Horizontal = 1
                        Vertical = 2
                        Alignment = int

                    return _Qt
                return _Dummy

        qtwidgets = _QtWidgetsModule("PySide6.QtWidgets")
        qtcore = _QtCoreModule("PySide6.QtCore")
        class _QtGuiModule(types.ModuleType):
            def __getattr__(self, _name: str):
                return _Dummy

        qtgui = _QtGuiModule("PySide6.QtGui")
        pyside6 = types.ModuleType("PySide6")
        pyside6.__path__ = []
        pyside6.QtWidgets = qtwidgets
        pyside6.QtCore = qtcore
        pyside6.QtGui = qtgui
        qtsvg = _QtGuiModule("PySide6.QtSvg")
        qtsvgwidgets = _QtGuiModule("PySide6.QtSvgWidgets")
        pyside6.QtSvg = qtsvg
        pyside6.QtSvgWidgets = qtsvgwidgets
        sys.modules["PySide6"] = pyside6
        sys.modules["PySide6.QtWidgets"] = qtwidgets
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules["PySide6.QtGui"] = qtgui
        sys.modules["PySide6.QtSvg"] = qtsvg
        sys.modules["PySide6.QtSvgWidgets"] = qtsvgwidgets

    if "matplotlib" not in sys.modules:
        mpl = types.ModuleType("matplotlib")
        backends = types.ModuleType("matplotlib.backends")
        backend_qtagg = types.ModuleType("matplotlib.backends.backend_qtagg")
        backend_qtagg.FigureCanvasQTAgg = object
        figure_module = types.ModuleType("matplotlib.figure")
        figure_module.Figure = object
        mpl.backends = backends
        sys.modules["matplotlib"] = mpl
        sys.modules["matplotlib.backends"] = backends
        sys.modules["matplotlib.backends.backend_qtagg"] = backend_qtagg
        sys.modules["matplotlib.figure"] = figure_module


_install_gui_stubs()

from app.core.isolierungen_exchange.decision_service import InsulationFamilyDecision, PreparedInsulationImportDecisions
from app.core.isolierungen_exchange.persistence_service import (
    FamilyPersistenceOutcome,
    PreparedInsulationImportPersistenceResult,
)
from app.ui_qt.global_tabs.isolierungen_db import IsolierungenDbTab


class IsolierungenImportUiFlowTests(unittest.TestCase):
    def _tab_stub(self, decisions: PreparedInsulationImportDecisions | None = None) -> IsolierungenDbTab:
        tab = IsolierungenDbTab.__new__(IsolierungenDbTab)
        tab.widget = object()
        tab.refresh_table = Mock()
        tab._run_import_decision_dialog = Mock(return_value=decisions)
        return tab

    def _decisions(self, entries: list[tuple[int, str, str]]) -> PreparedInsulationImportDecisions:
        return PreparedInsulationImportDecisions(
            source_path=Path("import.hpxins.json"),
            summary={"exact_match": 0, "candidate_conflict": 0, "no_match": 0},
            warnings=[],
            family_decisions=[
                InsulationFamilyDecision(
                    import_index=index,
                    import_family_name=name,
                    matching_status=status,
                    action="create_new",
                    selected_candidate_id=None,
                    exact_family_id=None,
                )
                for index, name, status in entries
            ],
        )

    def _result(
        self,
        *,
        success: bool,
        outcomes: list[FamilyPersistenceOutcome],
        errors: list[str] | None = None,
    ) -> PreparedInsulationImportPersistenceResult:
        summary = {
            "created": 0,
            "skipped": 0,
            "exact_match_confirmed": 0,
            "candidate_confirmed_noop": 0,
            "candidate_rejected": 0,
            "rolled_back": 0,
            "errors": len(errors or []),
            "total": len(outcomes),
        }
        for outcome in outcomes:
            if outcome.status in summary:
                summary[outcome.status] += 1
        return PreparedInsulationImportPersistenceResult(
            success=success,
            source_path="import.hpxins.json",
            summary=summary,
            outcomes=outcomes,
            errors=errors or [],
        )

    def test_success_create_new_shows_family_specific_outcome(self) -> None:
        decisions = self._decisions([(0, "Neu A", "no_match")])
        tab = self._tab_stub(decisions=decisions)
        persistence_result = self._result(
            success=True,
            outcomes=[
                FamilyPersistenceOutcome(
                    import_index=0,
                    import_family_name="Neu A",
                    action="create_new",
                    status="created",
                    created_family_id=11,
                )
            ],
        )

        with (
            patch("app.ui_qt.global_tabs.isolierungen_db.QFileDialog.getOpenFileName", return_value=("dummy.json", "")),
            patch("app.ui_qt.global_tabs.isolierungen_db.prepare_insulation_exchange_import_from_file", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.analyze_prepared_insulation_import_matching", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.PreparedInsulationImportPersistenceService") as persistence_cls,
            patch("app.ui_qt.global_tabs.isolierungen_db.QMessageBox.information") as info_box,
        ):
            persistence_cls.return_value.persist.return_value = persistence_result
            tab.import_family_prepare()

        tab.refresh_table.assert_called_once()
        message_text = info_box.call_args[0][2]
        self.assertIn("Ergebnis pro Importfamilie", message_text)
        self.assertIn("Neu A: Neu angelegt", message_text)

    def test_success_exact_match_and_skip_are_explicit_noops(self) -> None:
        decisions = self._decisions([(0, "Exact A", "exact_match"), (1, "Skip B", "no_match")])
        tab = self._tab_stub(decisions=decisions)
        persistence_result = self._result(
            success=True,
            outcomes=[
                FamilyPersistenceOutcome(
                    import_index=0,
                    import_family_name="Exact A",
                    action="use_exact_match",
                    status="exact_match_confirmed",
                    selected_candidate_id=7,
                ),
                FamilyPersistenceOutcome(
                    import_index=1,
                    import_family_name="Skip B",
                    action="skip_import",
                    status="skipped",
                ),
            ],
        )

        with (
            patch("app.ui_qt.global_tabs.isolierungen_db.QFileDialog.getOpenFileName", return_value=("dummy.json", "")),
            patch("app.ui_qt.global_tabs.isolierungen_db.prepare_insulation_exchange_import_from_file", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.analyze_prepared_insulation_import_matching", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.PreparedInsulationImportPersistenceService") as persistence_cls,
            patch("app.ui_qt.global_tabs.isolierungen_db.QMessageBox.information") as info_box,
        ):
            persistence_cls.return_value.persist.return_value = persistence_result
            tab.import_family_prepare()

        message_text = info_box.call_args[0][2]
        self.assertIn("Exact Match bestätigt (keine Änderung)", message_text)
        self.assertIn("Skip B: Übersprungen", message_text)

    def test_cancel_in_decision_dialog_skips_persistence(self) -> None:
        tab = self._tab_stub(decisions=None)

        with (
            patch("app.ui_qt.global_tabs.isolierungen_db.QFileDialog.getOpenFileName", return_value=("dummy.json", "")),
            patch("app.ui_qt.global_tabs.isolierungen_db.prepare_insulation_exchange_import_from_file", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.analyze_prepared_insulation_import_matching", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.PreparedInsulationImportPersistenceService") as persistence_cls,
            patch("app.ui_qt.global_tabs.isolierungen_db.QMessageBox.information") as info_box,
        ):
            tab.import_family_prepare()

        persistence_cls.return_value.persist.assert_not_called()
        tab.refresh_table.assert_not_called()
        self.assertIn("Import abgebrochen", info_box.call_args[0][1])

    def test_failure_with_rollback_lists_all_affected_families(self) -> None:
        decisions = self._decisions([(0, "Neu A", "no_match"), (1, "Neu B", "no_match")])
        tab = self._tab_stub(decisions=decisions)
        persistence_result = self._result(
            success=False,
            outcomes=[
                FamilyPersistenceOutcome(
                    import_index=0,
                    import_family_name="Neu A",
                    action="create_new",
                    status="rolled_back",
                    message="Transaktion wegen Folgefehler zurückgerollt.",
                    created_family_id=99,
                )
            ],
            errors=["Import abgebrochen: create_new für 'Neu B' nicht möglich."],
        )

        with (
            patch("app.ui_qt.global_tabs.isolierungen_db.QFileDialog.getOpenFileName", return_value=("dummy.json", "")),
            patch("app.ui_qt.global_tabs.isolierungen_db.prepare_insulation_exchange_import_from_file", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.analyze_prepared_insulation_import_matching", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.PreparedInsulationImportPersistenceService") as persistence_cls,
            patch("app.ui_qt.global_tabs.isolierungen_db.QMessageBox.critical") as critical_box,
        ):
            persistence_cls.return_value.persist.return_value = persistence_result
            tab.import_family_prepare()

        message_text = critical_box.call_args[0][2]
        self.assertIn("zurückgerollt", message_text)
        self.assertIn("Neu A: Wegen Rollback nicht übernommen", message_text)
        self.assertIn("Neu B: Wegen Rollback nicht übernommen", message_text)

    def test_mixed_outcomes_are_rendered_per_family(self) -> None:
        decisions = self._decisions(
            [(0, "Create", "no_match"), (1, "Exact", "exact_match"), (2, "Skip", "no_match"), (3, "Cand", "candidate_conflict")]
        )
        tab = self._tab_stub(decisions=decisions)
        persistence_result = self._result(
            success=True,
            outcomes=[
                FamilyPersistenceOutcome(0, "Create", "create_new", "created", created_family_id=5),
                FamilyPersistenceOutcome(1, "Exact", "use_exact_match", "exact_match_confirmed", selected_candidate_id=2),
                FamilyPersistenceOutcome(2, "Skip", "skip_import", "skipped"),
                FamilyPersistenceOutcome(3, "Cand", "select_candidate", "candidate_confirmed_noop", selected_candidate_id=8),
            ],
        )

        with (
            patch("app.ui_qt.global_tabs.isolierungen_db.QFileDialog.getOpenFileName", return_value=("dummy.json", "")),
            patch("app.ui_qt.global_tabs.isolierungen_db.prepare_insulation_exchange_import_from_file", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.analyze_prepared_insulation_import_matching", return_value=Mock()),
            patch("app.ui_qt.global_tabs.isolierungen_db.PreparedInsulationImportPersistenceService") as persistence_cls,
            patch("app.ui_qt.global_tabs.isolierungen_db.QMessageBox.information") as info_box,
        ):
            persistence_cls.return_value.persist.return_value = persistence_result
            tab.import_family_prepare()

        message_text = info_box.call_args[0][2]
        self.assertIn("Create: Neu angelegt", message_text)
        self.assertIn("Exact: Exact Match bestätigt (keine Änderung)", message_text)
        self.assertIn("Skip: Übersprungen", message_text)
        self.assertIn("Cand: Kandidat bestätigt (No-Op)", message_text)


if __name__ == "__main__":
    unittest.main()
