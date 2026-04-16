# Review der Python-Testbasis

## Kriterien
- **Behalten**: Tests, die stabiles fachliches Verhalten der Core-Services absichern.
- **Überarbeiten**: Tests mit sinnvollem Ziel, aber unnötig fragiler Technik (z. B. Import-/Pfadannahmen).
- **Entfernen**: Tests mit aggressiven globalen GUI-/Backend-Stubs oder Fokus auf interne Wiring-Details statt Produktverhalten.

## Entscheidungen

### Überarbeitet
- **`tests/conftest.py` ergänzt**: Der Repository-Root wird explizit in `sys.path` eingetragen, damit Test-Imports reproduzierbar funktionieren und nicht von lokalen Startpfaden abhängen.

### Entfernt
- **`tests/test_isolierungen_import_ui_flow.py`** entfernt.
- **`tests/test_projects_tab_unsaved_flow.py`** entfernt.

Begründung: Beide Testmodule setzten auf globale PySide6-/matplotlib-Stub-Injektion über `sys.modules`. Diese Technik verursachte testübergreifende Seiteneffekte (u. a. im Reporting-PDF-Test) und prüfte primär künstlich nachgestellte UI-Wiring-Pfade statt robuste Fachlogik.

## Ergebnis
- Kleinere, dafür robustere Suite mit Fokus auf Core-Import-/Matching-/Persistence-/Reporting-Verhalten.
- Voller Lauf erfolgreich mit `pytest -q`.
