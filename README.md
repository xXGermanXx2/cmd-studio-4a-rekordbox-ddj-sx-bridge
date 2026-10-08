# CMD Studio 4A rekordbox 7 DDJ-SX Bridge

Windows-MIDI-Bridge für den Behringer CMD Studio 4A. Die Bridge übersetzt die dokumentierten MIDI-Daten des CMD Studio 4A in DDJ-SX-kompatible Nachrichten für rekordbox 7.

## Eigenschaften

- Reines Python 3 ohne C++-Compiler
- Keine externen Python-Pakete
- Windows-`winmm.dll` über `ctypes`
- Zwei Decks
- Jogwheel mit Touch, Scratch/Search und Release-Verhalten
- Pitchfader, EQ, Gain, Kanal-Fader und Crossfader
- Play/Pause, Cue, Sync, Hot Cues und Load
- DEL-Taste als Umschalter zwischen Hot Cue und Beat Jump
- Browser, FX und AutoLoop
- Lokale LED-Steuerung ohne MIDI-OUT-Feedback-Schleife
- FX1, FX2 und FX3 mit jeweils eigenem Parameter und An/Aus-Taste
- FX4 als High-/Low-Pass-Filter mit eigenem An/Aus-Schalter

## Voraussetzungen

- Windows 10/11
- Python 3
- Behringer CMD Studio 4A per USB
- [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
- rekordbox 7

Es werden keine C++-Compiler, `pip`, `mido` oder `python-rtmidi` benötigt.

## Installation

1. CMD Studio 4A per USB anschließen.
2. loopMIDI starten.
3. Genau **einen** virtuellen MIDI-Port mit diesem Namen anlegen:

   ```text
   PIONEER DDJ-SX
   ```

   Ein zweiter LED-Port ist für die aktuelle lokale LED-Steuerung nicht erforderlich.
4. `PIONEER DDJ-SX.midi.csv` in den `MidiMappings`-Ordner der rekordbox-Installation kopieren. Den vorhandenen Ordner vorher sichern.
5. rekordbox vollständig schließen und neu starten.
6. In rekordbox unter den MIDI-Einstellungen als **MIDI Input** auswählen:

   ```text
   PIONEER DDJ-SX
   ```

   `Studio 4A` wird nicht direkt in rekordbox ausgewählt; das Gerät wird ausschließlich vom Bridge-Script geöffnet.

## Start

Die Batch-Datei starten:

```text
start_windows_pure.bat
```

Oder manuell:

```bat
py cmd4a_ddjsx_windows.py --list
py cmd4a_ddjsx_windows.py --input "Studio 4A" --output "PIONEER DDJ-SX" --monitor
```

Die erwartete Ausgabe lautet ungefähr:

```text
Eingang: Studio 4A
Ausgang: PIONEER DDJ-SX
LED-Feedback: lokale Simulation
Strg+C beendet.
```

## LED-Steuerung

Die LED-Rückmeldung wird lokal vom Script an den physischen Studio-4A-Ausgang gesendet. Die Mapping-Datei enthält absichtlich keine MIDI-OUT-Rückmeldungen, weil rekordbox in dieser Konfiguration Ein- und Ausgang über denselben LoopMIDI-Port führt. MIDI-OUT-Werte würden deshalb als neue Eingaben zurück zu rekordbox gelangen und Play/Pause doppelt auslösen.

Beim Start leuchten dauerhaft:

- Play/Pause links und rechts
- Cue links und rechts
- Sync links und rechts

Lokal umgeschaltet werden:

- Phones/PFL
- AutoLoop
- FX1, FX2 und FX3

Die offizielle CMD-Studio-4A-Definition verwendet für LED-Statuswerte:

```text
00 = aus
01 = dauerhaft an
02 = blinken
```

Die Bridge verwendet für die lokalen LEDs die dokumentierten Werte `00` und `01`.

Die lokale LED-Simulation kennt nur Eingaben vom Controller. Wenn ein Zustand ausschließlich mit der Maus in rekordbox geändert wird, kann das Script diesen Zustand nicht automatisch kennen.

## MIDI-Funktionen

Die Bridge verarbeitet dokumentierte CMD-Studio-4A-Eingangsdaten und sendet DDJ-SX-Zieldaten für:

- Jogwheel links/rechts und Jog-Touch
- Pitchfader links/rechts
- Play/Pause
- Cue
- Sync
- Hot Cue 1–8
- Loop-Größe und AutoLoop
- Load
- EQ High/Mid/Low
- Kanal-Fader
- Crossfader
- FX-Parameter links/rechts
- FX-Assign links/rechts
- Browser-Regler, Enter sowie Zurück/Weiter

Gain/Trim ist absichtlich vollständig entfernt. Die vier FX-Bedienelemente
werden so übersetzt:

| CMD-Bedienelement | Funktion |
|---|---|
| FX1-Regler und FX1-Taste | DDJ-SX FX1-Parameter 1 und An/Aus |
| FX2-Regler und FX2-Taste | DDJ-SX FX1-Parameter 2 und An/Aus |
| FX3-Regler und FX3-Taste | DDJ-SX FX1-Parameter 3 und An/Aus |
| FX4-Regler und FX4-Taste | High-/Low-Pass-Filter und Filter An/Aus |

Die DEL-Taste arbeitet deckweise: `90 2A` schaltet die linken acht Pads um,
`91 4A` die rechten acht Pads. Ein weiterer Druck stellt den jeweiligen
Hot-Cue-Modus wieder her.

Beim FX4-Filter bedeutet Aus den neutralen Mittelpunkt. Beim erneuten
Einschalten wird die zuletzt eingestellte Filterposition wiederhergestellt.

Key Lock/Master Tempo und Tempo Range sind aus dem Controller-Mapping entfernt.
Damit kann das Pult die Tonart nicht mehr umschalten. Für tonartneutrale
Tempoänderungen muss **Key Lock in rekordbox selbst aktiviert** sein.

Die DDJ-SX-Zielcodes für Jogwheel, Touch, EQ und Fader stammen aus der DDJ-SX-MIDI-Definition. Die CMD-Eingangscodes stammen aus der dokumentierten CMD-Studio-4A-Controllerdefinition.

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
| `cmd4a_ddjsx_windows.py` | Hauptprogramm für Windows ohne externe Python-Pakete |
| `start_windows_pure.bat` | Startdatei mit den Standard-Portnamen |
| `PIONEER DDJ-SX.midi.csv` | rekordbox-DDJ-SX-Mapping ohne MIDI-OUT-Loop |
| `CMD4A_to_DDJ-SX_facts.csv` | Dokumentation der Eingangs- und Zielcodes |

## Quellen

- [CMD Studio 4A MIDI-Definition](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer%20CMDStudio4a.midi.xml)
- [CMD Studio 4A Script](https://github.com/mixxxdj/mixxx/blob/main/res/controllers/Behringer-CMDStudio4a-scripts.js)
- [CMD Studio 4A MIDI Map und LED-Feedback-Referenz](https://www.djshop.gr/Attachment/DownloadFile?downloadId=2496)
- [AlphaTheta DDJ-SX MIDI-kompatible Software und MIDI-Liste](https://support.alphatheta.com/en-US/articles/23923285968537?product=4416570097177)
- [RekordJog-Projekt](https://github.com/timkondratev/RekordJog)

## Bekannte Grenzen

Die Bridge kann MIDI-Nachrichten senden, aber die Annahme der Nachrichten hängt von der verwendeten rekordbox-Version, dem aktiven `MidiMappings`-Ordner und dem virtuellen MIDI-Treiber ab. Die lokalen LEDs spiegeln Controller-Eingaben wider, nicht Änderungen, die ausschließlich mit der rekordbox-Mausoberfläche vorgenommen werden.
