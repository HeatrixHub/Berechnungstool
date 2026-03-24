# Reporting-Tab Rückbau (Zwischenstand)

Datum: 2026-03-24

Der bisherige Berichte-Tab wurde bewusst auf einen stabilen Minimalzustand reduziert,
um einen modularen Neuaufbau vorzubereiten.

## Entfernt / entkoppelt

- Jinja2-Template-Rendering aus dem Berichte-Tab entfernt.
- Plugin-spezifische Isolierungs-Datenaufbereitung im Berichte-Tab entfernt.
- Textbasierte Vorschau (`QTextBrowser` + Plain-Text-Ausgabe) entfernt.
- PDF-Erzeugung über die bisherige integrierte ReportLab-Logik entfernt.
- Diagrammerzeugung im Berichte-Tab entfernt.
- Altes Berichtstemplate `Isolierung/reports/berechnung.j2` entfernt.
- Nicht mehr benötigte direkte Abhängigkeiten für den alten Berichte-Tab aus
  `requirements.txt` entfernt (`reportlab`, `Jinja2`).

## Bewusst verbleibend

- Der Berichte-Tab bleibt in der Anwendung vorhanden und startbar.
- Der Tab zeigt eine einfache Platzhalter-UI mit Hinweis auf den Neuaufbau.
- Minimale, deaktivierte Bedienelemente bleiben als UX-Platzhalter erhalten.

## Technischer Schnitt

Die UI-Schicht des Berichte-Tabs enthält keine Berichtslogik mehr.
Es bestehen dort keine Pfade mehr für Template-Rendering, PDF-Erzeugung,
plugin-spezifische Datenaufbereitung oder Diagrammerzeugung.
