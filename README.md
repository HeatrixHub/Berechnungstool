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
