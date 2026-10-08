# CMD Studio 4A → rekordbox 7 / DDJ-SX

Windows-MIDI-Bridge für den Behringer CMD Studio 4A. Die Bridge übersetzt die MIDI-Daten des CMD Studio 4A in DDJ-SX-kompatible Nachrichten für rekordbox 7.

## Windows-Version ohne C++

Verwendete Datei:

```text
cmd4a_ddjsx_windows.py
```

Die Datei verwendet ausschließlich:

- Python-Standardbibliothek
- Windows `winmm.dll`
- keinen C++-Compiler
- kein `pip`
- kein `mido`
- kein `python-rtmidi`

Zusätzlich wird ein virtueller MIDI-Treiber wie [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) benötigt.

## Einrichtung

1. CMD Studio 4A per USB anschließen.
2. loopMIDI starten.
3. Einen virtuellen Port exakt mit diesem Namen anlegen:

```text
PIONEER DDJ-SX
```

4. Die Datei `PIONEER DDJ-SX.midi.csv` in den `MidiMappings`-Ordner der verwendeten rekordbox-Installation kopieren. Den Originalordner vorher sichern.
5. rekordbox vollständig schließen und neu starten.
6. Bridge starten:

```bat
py cmd4a_ddjsx_windows.py --list
py cmd4a_ddjsx_windows.py --input "Studio 4A" --output "PIONEER DDJ-SX" --monitor
```

Alternativ:

```text
start_windows_pure.bat
```

## MIDI-Funktionen

Die Bridge verarbeitet die dokumentierten Eingangsdaten des CMD Studio 4A und sendet DDJ-SX-Zieldaten für:

- Jogwheel links/rechts und Jog-Touch
- Pitchfader links/rechts
- Play/Pause
- Cue
- Sync
- Hot Cue 1–8
- Loop In / Loop Out
- Load
- Gain/Trim
- EQ High/Mid/Low
- Kanal-Fader
- Crossfader

Die offiziellen DDJ-SX-Zielcodes für Jogwheel, Touch, EQ und Fader stammen aus der AlphaTheta/Pioneer-MIDI-Liste. Die CMD-Eingangscodes stammen aus der dokumentierten CMD-Studio-4A-Controllerdefinition.

## Diagnose

Mit `--monitor` werden Eingang und Ausgang angezeigt:

```text
IN  B0 1A 41
OUT (4268720,)
```

Die Dezimalzahl bei `OUT` ist ein gepackter Windows-MIDI-Wert. Die Eingangsbytes sind die wichtigen Diagnosewerte.

Beispiele der CMD-Eingänge:

```text
Jog links:       B0 1A xx
Jog rechts:      B1 3A xx
EQ High links:   B0 60 xx
EQ Mid links:    B0 61 xx
EQ Low links:    B0 62 xx
EQ High rechts:  B1 63 xx
EQ Mid rechts:   B1 64 xx
EQ Low rechts:   B1 65 xx
Fader links:     B0 70 xx
Fader rechts:    B1 71 xx
```

## Dateien

| Datei | Zweck |
|---|---|
| `cmd4a_ddjsx_windows.py` | Hauptprogramm für Windows ohne C++/pip |
| `start_windows_pure.bat` | Startdatei mit dem Gerätenamen `Studio 4A` |
| `PIONEER DDJ-SX.midi.csv` | rekordbox-DDJ-SX-Mapping |
| `CMD4A_to_DDJ-SX_facts.csv` | Dokumentation der Eingangs- und Zielcodes |

## Quellen

- [CMD Studio 4A MIDI-Definition](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer%20CMDStudio4a.midi.xml)
- [CMD Studio 4A Script](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer-CMDStudio4a-scripts.js)
- [AlphaTheta DDJ-SX MIDI-kompatible Software und MIDI-Liste](https://support.alphatheta.com/en-US/articles/23923285968537?product=4416570097177)
- [RekordJog-Projekt](https://github.com/timkondratev/RekordJog)

## Bekannte Grenze

Die Bridge kann MIDI-Nachrichten senden, aber die Annahme der Nachrichten hängt von der verwendeten rekordbox-Version, dem aktiven `MidiMappings`-Ordner und dem virtuellen MIDI-Treiber ab. FX-Assign und FX-Regler sind nicht künstlich einer nicht dokumentierten DDJ-SX-Funktion zugeordnet.
