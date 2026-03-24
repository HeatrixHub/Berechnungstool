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

## Technische Notiz – HTML-Vorschau (Stand nach 2B)

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

### Einordnung des aktuellen Zwischenstands

- Der HTML-Vorschaufluss ist funktionsfähig und durchgängig:
  `plugin_manager` → `build_isolierung_report(...)` → `ReportDocument` → `render_report_html(...)`.
- Der Berichte-Tab enthält weiterhin nur UI/Orchestrierung; Metadaten-Auflösung für den
  Isolierungsbericht liegt in der Reporting-Builder-Schicht.
- Für Kennzahlen (`MetricItem.format_hint`) gelten nun einheitliche Konventionen in
  Datenmodell, Builder und HTML-Renderer (`plain`, `number`, `integer`, `percentage`,
  `status`, `list`).
- **Nicht** Bestandteil dieses Stands: PDF-Renderer, PDF-Export und zusätzliche
  PDF-Abhängigkeiten.

## Weiterer Ausbau – Standardbericht 01

Die fachliche Zielstruktur für den ersten Standardbericht ist in `docs/reporting-standardbericht-01.md` dokumentiert. Der Isolierung-Builder ist entsprechend auf die Reihenfolge Titel → Projektdaten → Allgemeine Daten → Schichttabelle → Temperaturverlauf ausgerichtet.
