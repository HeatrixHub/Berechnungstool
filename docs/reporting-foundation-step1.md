# Reporting Foundation – Ausbauschritt 1

## Neu eingeführte Dateien

- `app/core/reporting/model.py`
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
2. Der neue Builder `build_isolierung_report_document(...)` liest ausschließlich diesen
   exportierten State (ohne UI- oder Rendering-Abhängigkeiten).
3. Der Builder normalisiert und extrahiert Daten defensiv (fehlende Felder werden als
   leere Tabellen, optionale Textblöcke oder Fallback-Kennzahlen dargestellt).
4. Ergebnis ist ein vollständiges `ReportDocument` mit vier fachlichen Abschnitten:
   Projektübersicht, Isolierungsberechnung, Schichtaufbau und Zuschnittsplan.

Damit ist die fachliche Datenbasis für spätere PDF-/HTML-Renderer vorbereitet, ohne
bereits Renderinglogik einzuführen.
