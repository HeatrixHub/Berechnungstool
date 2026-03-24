# Reporting Foundation – Ausbauschritt 1

## Neu eingeführte Dateien

- `app/core/reporting/report_document.py`
- `app/core/reporting/__init__.py`
- `app/core/reporting/builders/isolierung.py`
- `app/core/reporting/builders/__init__.py`

## Dataclasses des Berichtsdokuments

Das renderer-neutrale Berichtsdokument basiert auf folgenden Dataclasses:

- `ReportMetadata`
- `ReportDocument`
- `ReportSection`
- `TextBlock`
- `TableBlock`
- `MetricItem`
- `MetricsBlock`
- `ImageBlock`

## Datenfluss in diesem Schritt

1. Das Isolierungs-Plugin exportiert seinen Zustand über `export_state()` in die Struktur
   `inputs/results/ui`.
2. Der neue Builder `build_isolierung_report(...)` liest ausschließlich diesen
   exportierten State (ohne UI- oder Rendering-Abhängigkeiten).
3. Der Builder normalisiert und extrahiert Daten defensiv (fehlende Felder werden als
   leere Tabellen, optionale Textblöcke oder Fallback-Kennzahlen dargestellt).
4. Ergebnis ist ein vollständiges `ReportDocument` mit vier fachlichen Abschnitten:
   Projektübersicht, Isolierungsberechnung, Schichtaufbau und Zuschnittsplan.

Damit ist die fachliche Datenbasis für spätere PDF-/HTML-Renderer vorbereitet, ohne
bereits Renderinglogik einzuführen.

## Technische Notiz – HTML-Vorschau (Ausbauschritt 2)

Neu eingeführt:

- `app/core/reporting/renderers/html.py` mit `render_report_html(document)` als erstem renderer-spezifischem Baustein für die Vorschau.
- `app/core/reporting/renderers/__init__.py` als stabiler Einstiegspunkt für Renderer-Imports.

Aktueller Vorschau-Datenfluss im Qt-Berichte-Tab:

1. `QtPluginManager.export_all_states()` liefert alle Plugin-States.
2. Der Berichte-Tab liest ausschließlich den State `isolierung` aus.
3. `build_isolierung_report(...)` erzeugt daraus ein renderer-neutrales `ReportDocument`.
4. `render_report_html(...)` rendert das `ReportDocument` in strukturierte HTML-Ausgabe.
5. `QTextBrowser.setHtml(...)` zeigt die Vorschau im Tab an.

Dabei bleibt die UI-Schicht rein orchestrierend; Datenaufbereitung liegt im Builder,
HTML-Formatierung ausschließlich im Renderer.
