# Reporting-Zielbild – Standardbericht 01 (Isolierung)

## Fachliche Zieldefinition

Der erste Standardbericht für das Isolierungs-Berechnungstool heißt:

**„Stationäre Wärmedurchgangsrechnung durch Isolierung“**

Die Reihenfolge der Berichtsinhalte ist bewusst festgelegt und orientiert sich am bereitgestellten Beispiel-PDF (ohne starre Layout-Kopie):

1. Titel
2. Projektdaten (Projektname, Autor, Datum mit Fallbacks)
3. Allgemeine Daten
4. Schichttabelle
5. Temperaturverlauf

## Abbildung in der aktuellen Reporting-Struktur

### Metadatenblock unter dem Titel

- Quelle: `ReportMetadata`.
- Pflichtfelder: `title`, `project_name`, `author`, `created_at`.
- Fallbacks:
  - Titel: „Stationäre Wärmedurchgangsrechnung durch Isolierung“
  - Projektname: „Unbenanntes Projekt“
  - Autor: „Unbekannt“
  - Datum: Laufzeitstempel via `datetime.now(timezone.utc)`

### Abschnitt „Allgemeine Daten"

Als `MetricsBlock` mit folgenden Kennwerten:

- Temperatur innen (`inputs.berechnung.T_left`)
- Umgebungstemperatur (`inputs.berechnung.T_inf`)
- Gesamtwärmestromdichte (`results.berechnung.data.q`)
- Gesamtwärmewiderstand (`results.berechnung.data.R_total`)

Hinweis: technische Feldnamen (`T_left`, `T_inf`) werden im Bericht fachlich verständlich benannt.

### Abschnitt „Schichtübersicht Isolierungen"

Als `TableBlock` mit stabilen Spalten-Keys:

- `layer_name` – Name der Isolierung
- `thickness_mm` – Dicke
- `classification_temperature_c` – Klassifizierungstemperatur
- `interface_temperature_c` – Grenzflächentemperatur der Schicht
- `mean_temperature_c` – mittlere Temperatur der Schicht
- `thermal_conductivity` – Wärmeleitfähigkeit der Schicht

Datenquellen:

- Eingabeschichten aus `inputs.berechnung.layers`
- Ergebnisreihen aus `results.berechnung.data` (`interface_temperatures`, `T_avg`, `k_final`)

### Abschnitt „Temperaturverlauf durch die Isolierung"

Als `ImageBlock`-Slot mit `image_role="chart"`.

- Fachliche Referenz auf den vorhandenen Plot im Isolierung-Plugin (Berechnungs-Tab).
- Für spätere Diagramm-Erzeugung werden Referenzdaten in `ImageBlock.metadata` abgelegt:
  - `thickness_profile_mm`
  - `interface_temperatures_c`
  - `preferred_asset_key`
  - Quellhinweise (`source_plugin`, `source_tab`, `source_plot`)

Damit ist die Reporting-Basis inhaltlich auf den ersten Standardbericht ausgerichtet, ohne PDF-Renderer oder PDF-Export bereits umzusetzen.
