#!/usr/bin/env python3
"""Behringer CMD Studio 4A -> rekordbox 7 MIDI bridge (2 decks).

The bridge reads MIDI from the CMD Studio 4A and forwards the messages to a
virtual MIDI output port. rekordbox 7 is then mapped to that virtual port.
It deliberately does not pretend to control rekordbox through an undocumented
API: rekordbox must learn the forwarded MIDI messages once.

Tested design: mido + python-rtmidi, MIDI channels 1/2 for Deck A/B.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

try:
    import mido
except ImportError:
    print("Fehlt: mido. Installiere mit: python -m pip install -r requirements.txt", file=sys.stderr)
    raise

DEFAULT_INPUT_HINT = "CMD"
DEFAULT_OUTPUT_HINT = "rekordbox"


def choose_port(ports: list[str], hint: Optional[str], label: str) -> str:
    if not ports:
        raise RuntimeError(f"Kein MIDI-{label}-Port gefunden.")
    if hint:
        matches = [p for p in ports if hint.lower() in p.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(f"Mehrere {label}-Ports passen zu '{hint}':", file=sys.stderr)
            for i, p in enumerate(matches, 1):
                print(f"  {i}: {p}", file=sys.stderr)
            raise RuntimeError("Bitte --input/--output mit einem eindeutigen Namen angeben.")
    if len(ports) == 1:
        return ports[0]
    raise RuntimeError(
        f"Mehrere MIDI-{label}-Ports gefunden. Bitte explizit auswählen:\n"
        + "\n".join(f"  {i}: {p}" for i, p in enumerate(ports, 1))
    )


def format_message(msg: mido.Message) -> str:
    attrs = []
    for name in ("channel", "note", "control", "value", "velocity", "pitch"):
        if hasattr(msg, name):
            attrs.append(f"{name}={getattr(msg, name)}")
    return f"{msg.type} " + " ".join(attrs)


def allowed_two_decks(msg: mido.Message, include_global: bool) -> bool:
    """Keep channels 1 and 2 (zero-based 0/1), plus non-channel messages.

    The controller's left/right physical decks are channels 1/2. Global mixer
    and browser messages commonly use channel 1, so they are retained.
    """
    if not hasattr(msg, "channel"):
        return True
    return msg.channel in (0, 1) or include_global


def main() -> int:
    parser = argparse.ArgumentParser(description="CMD Studio 4A MIDI-Bridge für rekordbox 7 (2 Decks)")
    parser.add_argument("--list", action="store_true", help="MIDI-Ports anzeigen und beenden")
    parser.add_argument("--input", help="Exakter Name oder eindeutiger Teil des CMD-Eingangs")
    parser.add_argument("--output", help="Exakter Name des virtuellen MIDI-Ausgangs")
    parser.add_argument("--monitor", action="store_true", help="MIDI-Nachrichten zusätzlich im Terminal anzeigen")
    parser.add_argument("--all-channels", action="store_true", help="Alle MIDI-Kanäle weiterleiten (nicht nur Deck A/B)")
    parser.add_argument("--no-forward", action="store_true", help="Nur überwachen, nichts weiterleiten")
    args = parser.parse_args()

    inputs = mido.get_input_names()
    outputs = mido.get_output_names()
    if args.list:
        print("MIDI-Eingänge:")
        for p in inputs:
            print(f"  {p}")
        print("MIDI-Ausgänge:")
        for p in outputs:
            print(f"  {p}")
        return 0

    input_name = choose_port(inputs, args.input or DEFAULT_INPUT_HINT, "Eingangs")
    output_name = None
    if not args.no_forward:
        output_name = choose_port(outputs, args.output or DEFAULT_OUTPUT_HINT, "Ausgangs")

    print(f"Eingang : {input_name}")
    print(f"Ausgang : {output_name or '(kein Forwarding)'}")
    print("Aktiv. Strg+C beendet.")
    try:
        with mido.open_input(input_name) as midi_in:
            if output_name:
                with mido.open_output(output_name) as midi_out:
                    run(midi_in, midi_out, args)
            else:
                run(midi_in, None, args)
    except KeyboardInterrupt:
        print("\nBeendet.")
    except (OSError, RuntimeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    return 0


def run(midi_in, midi_out, args) -> None:
    while True:
        for msg in midi_in.iter_pending():
            if not allowed_two_decks(msg, args.all_channels):
                continue
            if args.monitor:
                print(f"  {format_message(msg)}", flush=True)
            if midi_out is not None:
                # copy() avoids backends retaining a mutable object reference.
                midi_out.send(msg.copy())
        time.sleep(0.001)


if __name__ == "__main__":
    raise SystemExit(main())
