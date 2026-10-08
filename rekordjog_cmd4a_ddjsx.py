#!/usr/bin/env python3
"""CMD Studio 4A -> Pioneer DDJ-SX translator for rekordbox 7.

The input codes are taken from the Mixxx CMD Studio 4A controller definition.
The output codes are taken from the RekordJog DDJ-SX controller mapping.
Only equal-name/function mappings are included; no FX assignment is guessed.
"""
from __future__ import annotations
import argparse
import sys
import time
import mido

# CMD input: (MIDI channel zero-based, note/CC) -> DDJ-SX output note.
# DDJ-SX button messages in the supplied controller map use status 0x9F
# (channel 16) for deck 1/2: notes 0x22/0x42 etc.
BUTTON_MAP = {
    # Play / Cue / Sync
    (0, 0x2C): 0x22, (1, 0x4C): 0x42,  # PlayPause
    (0, 0x2B): 0x14, (1, 0x4B): 0x34,  # Cue
    (0, 0x2D): 0x25, (1, 0x4D): 0x45,  # Sync
    # Hot Cue 1-8
    (0, 0x22): 0x1D, (1, 0x42): 0x3D,
    (0, 0x23): 0x0F, (1, 0x43): 0x2F,
    (0, 0x24): 0x11, (1, 0x44): 0x31,
    (0, 0x25): 0x1B, (1, 0x45): 0x3B,
    (0, 0x26): 0x24, (1, 0x46): 0x44,
    (0, 0x27): 0x15, (1, 0x47): 0x35,
    (0, 0x28): 0x12, (1, 0x48): 0x32,
    (0, 0x29): 0x20, (1, 0x49): 0x40,
    # Loop In / Out. CMD B has reversed physical order in its documented layout.
    (0, 0x17): 0x0E, (1, 0x38): 0x2E,
    (0, 0x18): 0x10, (1, 0x37): 0x30,
}

JOG_INPUT = {(0, 0x1A): 0, (1, 0x3A): 1}
TOUCH_INPUT = {(0, 0x1A): 0, (1, 0x3A): 1}
PITCH_CHANNELS = {0, 1}


def select_port(ports, hint, kind):
    matches = [p for p in ports if hint.lower() in p.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"Kein eindeutiger {kind}-Port für '{hint}'.\n" + "\n".join(ports))
    raise RuntimeError(f"Mehrere {kind}-Ports passen zu '{hint}':\n" + "\n".join(matches))


def send_jog(out, deck, raw):
    # CMD definition uses wheel delta raw-64; DDJ-SX uses 64 as neutral.
    value = max(1, min(127, 64 + (raw - 64)))
    out.send(mido.Message('control_change', channel=deck, control=0x0A, value=value))


def send_pitch(out, msg):
    unsigned = max(0, min(16383, msg.pitch + 8192))
    msb, lsb = unsigned >> 7, unsigned & 0x7F
    out.send(mido.Message('control_change', channel=msg.channel, control=0x00, value=msb))
    out.send(mido.Message('control_change', channel=msg.channel, control=0x20, value=lsb))


def translate(msg, out, passthrough=False, monitor=False):
    key = (getattr(msg, 'channel', -1), getattr(msg, 'note', -1))
    if msg.type == 'control_change' and (msg.channel, msg.control) in JOG_INPUT:
        deck = JOG_INPUT[(msg.channel, msg.control)]
        send_jog(out, deck, msg.value)
        result = f"JOG Deck {deck+1}: CC {msg.control:#04x} -> DDJ-SX CC 0x0A"
    elif msg.type in ('note_on', 'note_off') and key in TOUCH_INPUT:
        deck = TOUCH_INPUT[key]
        out.send(mido.Message(msg.type, channel=deck, note=0x08, velocity=msg.velocity))
        result = f"TOUCH Deck {deck+1}: Note {msg.note:#04x} -> DDJ-SX Note 0x08"
    elif msg.type == 'pitchwheel' and msg.channel in PITCH_CHANNELS:
        send_pitch(out, msg)
        result = f"PITCH Deck {msg.channel+1}: -> DDJ-SX CC 0x00/0x20"
    elif msg.type in ('note_on', 'note_off') and key in BUTTON_MAP:
        out.send(mido.Message(msg.type, channel=15, note=BUTTON_MAP[key], velocity=msg.velocity))
        result = f"BUTTON {msg.type}: CMD ch{msg.channel+1} note {msg.note:#04x} -> DDJ-SX ch16 note {BUTTON_MAP[key]:#04x}"
    elif passthrough:
        out.send(msg.copy())
        result = f"PASS: {msg}"
    else:
        result = f"IGNORED (not mapped): {msg}"
    if monitor:
        print(result, flush=True)


def main():
    ap = argparse.ArgumentParser(description='CMD Studio 4A als DDJ-SX für rekordbox 7')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--input', default='CMD Studio 4A')
    ap.add_argument('--output', default='PIONEER DDJ-SX')
    ap.add_argument('--passthrough', action='store_true', help='Nicht gemappte Nachrichten zusätzlich roh weiterleiten')
    ap.add_argument('--monitor', action='store_true')
    args = ap.parse_args()
    ins, outs = mido.get_input_names(), mido.get_output_names()
    if args.list:
        print('Eingänge:'); print('\n'.join(ins)); print('Ausgänge:'); print('\n'.join(outs)); return 0
    try:
        inp = select_port(ins, args.input, 'Eingangs')
        outp = select_port(outs, args.output, 'Ausgangs')
        print(f'CMD-Eingang: {inp}\nDDJ-SX-Ausgang: {outp}\nStrg+C zum Beenden.')
        with mido.open_input(inp) as midi_in, mido.open_output(outp) as midi_out:
            while True:
                for msg in midi_in.iter_pending():
                    translate(msg, midi_out, args.passthrough, args.monitor)
                time.sleep(0.001)
    except KeyboardInterrupt:
        print('\nBeendet.')
    except (OSError, RuntimeError) as exc:
        print(f'Fehler: {exc}', file=sys.stderr); return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
