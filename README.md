# Berechnungstool

Übergeordnetes Programm, in dem alle Heatrix Berechnungstools untergebracht sind.

## Starten (Qt UI)

Die produktive Oberfläche basiert ausschließlich auf PySide6/PyQt6. Starte die
Anwendung über den Qt-Entry-Point:

```
python -m app.main_qt
```

Der frühere Tkinter-Client wurde als reine Referenz nach `legacy_tk/` verschoben
und wird nicht mehr geladen oder gepflegt.

## Plugin-System

Die Qt-Host-Anwendung lädt ihre Werkzeuge dynamisch auf Basis der Datei
`app/ui_qt/plugins/registry.json`. Jeder Eintrag beschreibt ein Plugin mit Name,
Python-Modul und Klassenname. Fehlende Plugins führen nicht mehr zum Absturz,
sondern werden beim Laden protokolliert.

Neue Plugins können als eigenständige Python-Pakete in die Umgebung installiert
werden; der Host benötigt lediglich den importierbaren Modulpfad und den Namen
der `Plugin`-Unterklasse.
