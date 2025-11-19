# Berechnungstool

Übergeordnetes Programm indem alle Heatrix Berechnungstools untergebracht sind.

## Plugin-System

Die Host-Anwendung lädt ihre Werkzeuge jetzt dynamisch auf Basis der Datei
`app/plugins/plugins.json`. Jeder Eintrag beschreibt ein Plugin mit Name,
Python-Modul und Klassenname. Plugins können über die Oberfläche aktiviert bzw.
deaktiviert werden; fehlende Plugins führen nicht mehr zum Absturz, sondern
werden im Header als Warnung angezeigt.

### Plugins verwalten

* Über den Button **"Plugins verwalten"** in der Kopfzeile lässt sich ein
  Dialog öffnen, in dem alle bekannten Plugins aufgeführt werden.
* Mit den Kontrollkästchen können Plugins aktiviert/deaktiviert werden.
* Über **"Plugin hinzufügen"** lassen sich zusätzliche Module registrieren,
  indem Name, Modulpfad (z. B. `meinplugin.plugin`) und Klassenname angegeben
  werden.
* Änderungen werden in `app/plugins/plugins.json` gespeichert. Nach dem
  Speichern muss die Anwendung neu gestartet werden, damit die neue Auswahl
  wirksam wird.

Neue Plugins können als eigenständige Python-Pakete in die Umgebung installiert
werden; der Host benötigt lediglich den importierbaren Modulpfad und den Namen
der `Plugin`-Unterklasse.

## Globale Architektur

Die Anwendung stellt eine gemeinsame Oberfläche für alle Module bereit. Vor den
Plugin-Tabs befinden sich drei feste Bereiche, die den gemeinsamen
Datenhaushalt bilden:

1. **Projekte** – Der `ProjectManager` hält den vollständigen Arbeitsstand aller
   Plugins fest. Ein Projekt enthält sämtliche Plugin-Daten und lässt sich über
   die GUI anlegen, auswählen und aktualisieren.
2. **Isolierungen** – Die `IsolationLibrary` fungiert als zentrale Datenbank für
   Materialien, Dicken und Metadaten. Plugins können Einträge schreiben oder
   wiederverwenden, ohne eigene Kopien zu pflegen.
3. **Bericht** – Der `ReportManager` sammelt optionale Beiträge aller Plugins.
   Der Benutzer entscheidet über die Aufnahme einzelner Abschnitte und kann die
   finale Vorschau direkt im Tab generieren.

Jedes Plugin erhält über den `AppContext` Zugriff auf diese Manager und kann so
zustandslos und lose gekoppelt bleiben. Neue Plugins müssen lediglich die
`Plugin`-Schnittstelle implementieren und nutzen automatisch Projektverwaltung,
gemeinsame Datenbasis und Berichtssystem.
