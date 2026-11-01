# Sensoto Environment Sensors for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Eine Home Assistant Custom Integration zur Anbindung öffentlicher Umwelt- und Wettersensoren über die [SENSOTO](https://sensoto.io/) Plattform (ehemals *OpenSensorWeb* – u. a. Daten von **DWD**, **Bundesamt für Strahlenschutz (BfS)**, **Sensor.Community / Luftdaten**, **Pegelonline**, **NOAA**).

---

## Features

- **Flexible Standort-Suche im Config Flow:**
  - **Umkreissuche:** Nutzt automatisch die Home-Koordinaten aus Home Assistant + einstellbaren Suchradius in Kilometern.
  - **Bounding Box:** Direkte Eingabe von `Top-Left` (Nord-West) und `Bottom-Right` (Süd-Ost) Koordinaten.
- **Unterstützte Umwelt-Kategorien:**
  - **Licht & Strahlung:** Globalstrahlung (kurz-/langwellig), diffuse Himmelsstrahlung, Sonnenscheindauer, Sonnenzenitwinkel, Ortsdosisleistung (Radioaktivität/ODL in `µSv/h`), radioaktive Zählrate, UV-Strahlung (UV, UV-A, UV-B), Infrarot, PAR-Strahlung.
  - **Luft & Atmosphäre:** Lufttemperatur, relative Luftfeuchtigkeit, Luftdruck, Niederschlag, Windgeschwindigkeit, Windrichtung, Bewölkungsgrad, Schneefall, Feinstaub (`PM10` & `PM2.5`).
  - **Wasser & Boden:** Wasserstand/Pegel, Wassertemperatur, Bodentemperatur (in verschiedenen Tiefen), Schneehöhe.
- **Automatische Geräte-Gruppierung:** Alle Sensoren einer Messstation (z. B. `Ahaus (DWD)` oder `TBL Ahaus Sektor 11 (BFS)`) werden übersichtlich als gemeinsames Home Assistant Gerät angelegt.
- **Messwert & Erfassungszeitpunkt:** Für jeden Sensor wird sowohl die Messwert-Entität als auch eine eigene Timestamp-Entität (`device_class: timestamp`, z. B. `Lufttemperatur Erfassungszeitpunkt`) angelegt. So ist der genaue Erfassungszeitpunkt direkt auf Dashboards und in Automationen auslesbar.
- **Umfangreiche Attribute:** Jede Entität liefert zudem detaillierte Attribute wie `last_measured_at`, `timestamp`, `erfassungszeitpunkt`, Geokoordinaten (`latitude`, `longitude`), Mess- und Abtastintervall, historische Min-/Max-Werte sowie den offiziellen Quellenhinweis (`attribution`).
- **Jederzeit anpassbar (Options Flow):** Sensoren im Suchbereich können nachträglich über *Konfigurieren* hinzugefügt oder abgewählt sowie das Abfrageintervall angepasst werden.

---

## Installation über HACS

1. Öffne **HACS** in deiner Home Assistant Instanz.
2. Klicke oben rechts auf das **Drei-Punkte-Menü (⋮)** und wähle **Benutzerdefinierte Repositories (Custom repositories)**.
3. Trage die URL dieses GitHub-Repositories ein und wähle als Typ **Integration** (bzw. *Integration*).
4. Suche in HACS nach **Sensoto Environment Sensors** und klicke auf **Herunterladen**.
5. **Starte Home Assistant neu.**

### Manuelle Installation

Kopiere den Ordner `custom_components/sensoto` in das Verzeichnis `config/custom_components/` deiner Home Assistant Installation und starte Home Assistant neu.

---

## Einrichtung (Konfiguration)

1. Gehe in Home Assistant auf **Einstellungen** → **Geräte & Dienste**.
2. Klicke unten rechts auf **+ Integration hinzufügen** und suche nach **Sensoto Environment Sensors**.
3. **Schritt 1:** Wähle den Suchmodus (*Umkreissuche* oder *Bounding Box*), die gewünschten Kategorien (*Licht & Strahlung*, *Luft & Atmosphäre*, *Wasser & Boden*) und das maximale Alter des letzten Messwerts (Standard: `7 Tage`, damit stillgelegte historische Stationen ausgeblendet werden).
4. **Schritt 2:** Bestätige oder passe den Standort/Radius bzw. die Bounding-Box-Koordinaten an.
5. **Schritt 3:** Wähle aus der nach Entfernung sortierten Liste deine gewünschten Messstationen und Sensoren aus und lege das Abfrageintervall (Standard: `15 Minuten`) fest.
