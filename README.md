# CMD Studio 4A → rekordbox 7 (2 Decks)

Dieses Paket ist eine **MIDI-Bridge** für den Behringer CMD Studio 4A. Sie empfängt die MIDI-Daten des Controllers und sendet sie an einen virtuellen MIDI-Ausgang, den rekordbox 7 als MIDI-Gerät verwenden kann.

## Wichtige technische Grenze

Rekordbox bietet keine öffentliche Python-API, mit der ein externes Script Play, Cue oder Jog direkt aufrufen kann. Deshalb ist der korrekte und stabile Weg:

1. CMD Studio 4A → Python-Bridge
2. Python-Bridge → virtueller MIDI-Port
3. virtueller MIDI-Port → einmaliges MIDI-Mapping in rekordbox 7

Das Script ist somit kein inoffizieller Tastatur-Hack und verändert keine rekordbox-Dateien.

## Installation

### Windows

1. [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) installieren.
2. Einen virtuellen Port mit dem Namen `CMD4A rekordbox` anlegen.
3. Python 3 installieren und im Paketordner ausführen:

```bat
py -m pip install -r requirements.txt
py cmd4a_rekordbox_bridge.py --list
```

4. Den Gerätenamen aus `--list` übernehmen. Starten:

```bat
py cmd4a_rekordbox_bridge.py --input "CMD Studio 4A" --output "CMD4A rekordbox" --monitor
```

Alternativ `start_windows.bat` anpassen und doppelklicken.

### macOS

1. In **Audio-MIDI-Setup → Fenster → MIDI-Studio** das **IAC-Treibersystem** aktivieren.
2. Einen Port `CMD4A rekordbox` anlegen.
3. Im Paketordner:

```bash
python3 -m pip install -r requirements.txt
python3 cmd4a_rekordbox_bridge.py --list
python3 cmd4a_rekordbox_bridge.py --input "CMD Studio 4A" --output "CMD4A rekordbox" --monitor
```

## rekordbox 7 einrichten

1. Bridge starten.
2. In rekordbox: **Preferences → Controller → MIDI**.
3. Als MIDI-Gerät den virtuellen Port `CMD4A rekordbox` auswählen.
4. Für jede Funktion **Learn** wählen und den jeweiligen Regler/Button am CMD Studio 4A bewegen.
5. Mapping speichern.

Rekordbox erkennt dann die weitergeleiteten Original-MIDI-Nachrichten. Bei `--monitor` sieht man die Werte vorher im Terminal.

## Empfohlenes Zwei-Deck-Mapping

| CMD Studio 4A | Rekordbox-Funktion | MIDI-Nachricht aus dem Controller |
|---|---|---|
| Play links/rechts | Play/Pause Deck 1/2 | Note On, Kanal 1/2 |
| Cue links/rechts | Cue Deck 1/2 | Note On, Kanal 1/2 |
| Jogwheel | Jog / Vinyl | Pitch Bend bzw. relative Daten, Kanal 1/2 |
| Pitchfader | Tempo | CC, Kanal 1/2 |
| Kanal-Fader | Volume Deck 1/2 | CC, Kanal 1/2 |
| Crossfader | Crossfader | CC, Kanal 1 |
| Gain | Trim/Gain Deck 1/2 | CC 16 / CC 48 |
| EQ High/Mid/Low | EQ Deck 1/2 | jeweilige CC-Werte per Learn ermitteln |
| Hot Cue 1–8 | Hot Cue 1–8 | Note On, Kanal 1/2 |
| Loop In/Out/On-Off | Loop-Steuerung | Note On, Kanal 1/2 |
| Browse/Enter | Bibliothek | CC/Note auf Kanal 1 |

Die Tabelle nennt bewusst die Learn-Funktion als letzte Instanz: Je nach Firmware-Revision und Betriebssystem können Note-Off, LED-Rückmeldung und Jogwheel-Message unterschiedlich erscheinen. Mit dem beiliegenden Monitor werden die tatsächlich gesendeten Werte des eigenen Geräts angezeigt.

## Bedienung / Diagnose

Nur Ports anzeigen:

```bash
python cmd4a_rekordbox_bridge.py --list
```

Nur MIDI sehen, ohne rekordbox-Ausgang:

```bash
python cmd4a_rekordbox_bridge.py --input "CMD Studio 4A" --no-forward --monitor
```

Standardmäßig werden nur die beiden physischen Deck-Kanäle 1 und 2 weitergeleitet. Für einen vollständigen Rohdaten-Test:

```bash
python cmd4a_rekordbox_bridge.py --input "CMD Studio 4A" --output "CMD4A rekordbox" --all-channels --monitor
```

## Quellen

- [Mixxx CMD Studio 4A Controller-Definition](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer%20CMDStudio4a.midi.xml)
- [Mixxx CMD Studio 4A Script](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer-CMDStudio4a-scripts.js)
- [Mixxx-Dokumentation zum CMD Studio 4A](https://manual.mixxx.org/2.5/fi/hardware/controllers/behringer_cmd_studio_4a)

## DDJ-SX-Emulation ohne Jogwheel-MIDI-Learn

Die Datei `rekordjog_cmd4a_ddjsx.py` sendet den CMD Studio 4A als DDJ-SX-kompatible Signale:

```bash
python rekordjog_cmd4a_ddjsx.py --input "CMD Studio 4A" --output "PIONEER DDJ-SX" --monitor
```

Der virtuelle Port muss exakt `PIONEER DDJ-SX` heißen. Zusätzlich liegt `PIONEER DDJ-SX.midi.csv` bei. Diese Datei ist die DDJ-SX-MIDI-Map aus dem RekordJog-Projekt und muss nach dessen Anleitung in den rekordbox-Ordner `MidiMappings` übernommen werden. Vorher den Originalordner sichern.

### Fakt umgesetzt

| Bereich | Umsetzung |
|---|---|
| Jog A/B | CMD CC 0x1A/0x3A → DDJ-SX CC 0x0A |
| Jog-Touch A/B | CMD Note 0x1A/0x3A → DDJ-SX Note 0x08 |
| Pitchfader A/B | CMD Pitch-Bend → DDJ-SX 14-bit CC 0x00 + 0x20 |

Die Eingangs-Codes stammen aus der offiziellen Mixxx-CMD-Definition; die Ausgangs-Codes aus der DDJ-SX-rekordbox-MIDI-Map. Siehe `CMD4A_to_DDJ-SX_facts.csv`.

### Bewusst nicht behauptet

Für Play, Cue, Hot-Cue, Loop, FX und LEDs gibt es in den beiden Quellen keine eindeutige 1:1-Beziehung zwischen CMD-Bedienelement und DDJ-SX-Bedienelement. Diese werden in dieser Emulationsdatei nicht erfunden. Mit `--passthrough` können sie zusätzlich roh weitergeleitet werden, sind dadurch aber nicht automatisch in rekordbox belegt.

## Vollständige gleichnamige Tastenübersetzung

Die DDJ-SX-Bridge übersetzt jetzt zusätzlich faktisch abgeleitet:

- Play/Pause Deck A/B
- Cue Deck A/B
- Sync Deck A/B
- Hot Cue 1–8 Deck A/B
- Loop In Deck A/B
- Loop Out Deck A/B

Diese Zuordnungen verbinden nur gleichnamige Funktionen aus der CMD-Definition und der DDJ-SX-Controller-Map. Die einzelnen Eingangs- und Ausgangsbytes stehen in `CMD4A_to_DDJ-SX_facts.csv`.

FX-Assign-Tasten und FX-Regler bleiben absichtlich unübersetzt: Die DDJ-SX-Map enthält dort keine eindeutige gleichnamige rekordbox-Funktion, die eine belastbare 1:1-Zuordnung erlauben würde. Eine FX-Zuordnung wäre daher eine kreative Belegung und keine Fakt-Daten-Übersetzung.

## Windows-Version ohne C++ und ohne pip-Pakete

Wenn keine C++-Build-Tools installiert werden sollen, benutze `cmd4a_ddjsx_windows.py`. Diese Version verwendet ausschließlich Python-Standardbibliothek und die bereits in Windows enthaltene `winmm.dll`.

Es ist **kein** `pip install`, kein `mido`, kein `python-rtmidi` und kein C++-Compiler erforderlich. Voraussetzung bleibt nur Python 3 und ein virtueller MIDI-Treiber wie loopMIDI.

```bat
py cmd4a_ddjsx_windows.py --list
py cmd4a_ddjsx_windows.py --input "CMD Studio 4A" --output "PIONEER DDJ-SX" --monitor
```

Oder `start_windows_pure.bat` starten. Die bisherige `rekordjog_cmd4a_ddjsx.py` bleibt als plattformübergreifende Variante mit `mido` erhalten; für Windows ohne native Python-Pakete ist die neue `cmd4a_ddjsx_windows.py` die richtige Datei.

## Aktualisierte Mapping-Datei

`PIONEER DDJ-SX.midi.csv` enthält jetzt zusätzlich die dokumentierten DDJ-SX-Funktionen für Play/Pause, Cue, Sync, Hot Cue 1–8, Loop In, Loop Out und Load. Die Python-Übersetzer geben dieselben DDJ-SX-Status-/Notenwerte aus.

Die CSV-Zeilen sind die DDJ-SX-Zieldefinitionen. Die CMD-Eingangsbytes und die abgeleitete Verbindung stehen vollständig in `CMD4A_to_DDJ-SX_facts.csv`.

## Mixer- und EQ-Regler

Die Übersetzer enthalten jetzt auch die dokumentierten CMD-CCs für:

- Gain/Trim Deck A/B
- EQ High Deck A/B
- EQ Mid Deck A/B
- EQ Low Deck A/B
- Kanal-Fader Deck A/B
- Crossfader

Die DDJ-SX-Ziele sind die offiziellen 14-Bit-CC-Paare aus der AlphaTheta/Pioneer-MIDI-Liste. Der CMD Studio 4A liefert diese Regler als 7-Bit-CC; der Übersetzer sendet deshalb den CMD-Wert als MSB und `0` als LSB. Diese konkrete 7→14-Bit-Konvertierung ist technisch erforderlich und als `fact-derived` dokumentiert; sie ist keine direkte 14-Bit-Ausgabe des CMD.
