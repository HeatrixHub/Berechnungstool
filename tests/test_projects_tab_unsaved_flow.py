import sys
import types
import unittest


def _install_qt_stubs() -> None:
    if "PySide6" in sys.modules:
        return

    class _Dummy:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _DummyMessageBox:
        class StandardButton:
            NoButton = 0
            Save = 1
            Discard = 2
            Cancel = 3
            Yes = 4
            No = 5

        @staticmethod
        def question(*_args, **_kwargs):
            return _DummyMessageBox.StandardButton.Cancel

        information = warning = critical = staticmethod(lambda *_a, **_k: None)

    class _DummyQt:
        AlignRight = 0x0002
        AlignLeft = 0x0001
        AlignHCenter = 0x0004
        AlignVCenter = 0x0080
        Alignment = int

        class ItemDataRole:
            UserRole = 0

    class _QtWidgetsModule(types.ModuleType):
        def __getattr__(self, _name: str):
            return _Dummy

    class _QtCoreModule(types.ModuleType):
        def __getattr__(self, name: str):
            if name == "Qt":
                return _DummyQt
            return _Dummy

    class _QtGenericModule(types.ModuleType):
        def __getattr__(self, _name: str):
            return _Dummy

    qtwidgets = _QtWidgetsModule("PySide6.QtWidgets")
    qtwidgets.QMessageBox = _DummyMessageBox
    qtwidgets.QInputDialog = _Dummy
    qtcore = _QtCoreModule("PySide6.QtCore")
    qtgui = _QtGenericModule("PySide6.QtGui")
    qtsvg = _QtGenericModule("PySide6.QtSvg")
    qtsvgwidgets = _QtGenericModule("PySide6.QtSvgWidgets")
    pyside6 = types.ModuleType("PySide6")
    pyside6.__path__ = []  # mark as package
    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets
    pyside6.QtGui = qtgui
    pyside6.QtSvg = qtsvg
    pyside6.QtSvgWidgets = qtsvgwidgets
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtSvg"] = qtsvg
    sys.modules["PySide6.QtSvgWidgets"] = qtsvgwidgets


_install_qt_stubs()

from app.ui_qt.projects.tab import ProjectsTab


class ProjectsTabUnsavedFlowTests(unittest.TestCase):
    def _build_tab_stub(self) -> ProjectsTab:
        tab = ProjectsTab.__new__(ProjectsTab)
        tab._dirty = True
        tab._active_project_id = None
        tab._preview_mode = True
        tab._active_form_snapshot = {"name": "", "author": "Tester", "description": "Desc"}
        tab._set_status = lambda _message: None
        tab._set_dirty = lambda dirty: setattr(tab, "_dirty", dirty)
        tab._capture_active_form_snapshot = lambda: None
        return tab

    def test_unnamed_draft_save_prompts_for_name_and_then_saves(self) -> None:
        tab = self._build_tab_stub()
        tab._prompt_unsaved_changes = lambda _label: "save"
        tab._prompt_project_name_for_new_save = lambda: "Neues Projekt"

        save_calls: list[str] = []

        def _save_snapshot() -> bool:
            save_calls.append(tab._active_form_snapshot["name"])
            return True

        tab._save_project_from_form_snapshot = _save_snapshot
        tab.save_project = lambda: False

        result = tab.confirm_unsaved_changes("Projekt laden")

        self.assertTrue(result)
        self.assertEqual(save_calls, ["Neues Projekt"])

    def test_unnamed_draft_discard_continues_without_save(self) -> None:
        tab = self._build_tab_stub()
        tab._prompt_unsaved_changes = lambda _label: "discard"
        tab._save_project_from_form_snapshot = lambda: self.fail("save should not be called")
        tab.save_project = lambda: self.fail("save_project should not be called")

        result = tab.confirm_unsaved_changes("Neues Projekt")

        self.assertTrue(result)
        self.assertFalse(tab._dirty)

    def test_unnamed_draft_cancel_keeps_state(self) -> None:
        tab = self._build_tab_stub()
        tab._prompt_unsaved_changes = lambda _label: "cancel"
        tab._save_project_from_form_snapshot = lambda: self.fail("save should not be called")
        tab.save_project = lambda: self.fail("save_project should not be called")

        result = tab.confirm_unsaved_changes("Projekt laden")

        self.assertFalse(result)
        self.assertTrue(tab._dirty)

    def test_existing_project_save_uses_normal_save_path(self) -> None:
        tab = self._build_tab_stub()
        tab._active_project_id = "existing-id"
        tab._preview_mode = False
        tab._prompt_unsaved_changes = lambda _label: "save"
        tab._prompt_project_name_for_new_save = (
            lambda: self.fail("name prompt should not be used for existing project")
        )
        tab._save_project_from_form_snapshot = lambda: self.fail(
            "snapshot save path should not be used here"
        )
        tab.save_project = lambda: True

        result = tab.confirm_unsaved_changes("Projekt laden")

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
