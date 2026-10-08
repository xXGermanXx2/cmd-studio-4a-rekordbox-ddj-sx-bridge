#!/usr/bin/env python3
"""CMD Studio 4A -> DDJ-SX translator, Windows-only, pure Python.

No C++ compiler, no pip packages and no mido/rtmidi are required. MIDI is
accessed through the Windows winmm.dll API via ctypes. A virtual MIDI port
(e.g. loopMIDI named 'PIONEER DDJ-SX') is still required for rekordbox.
"""
import argparse
import ctypes
from ctypes import wintypes
import queue
import sys
import time

RELEASE = "2026.10.08-factual-no-jog-cue"

winmm = ctypes.WinDLL("winmm.dll")
MIDI_CALLBACK = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
CALLBACK_FUNCTION = 0x30000
MIM_DATA = 0x3C3
MMSYSERR_NOERROR = 0

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD),
                ("vDriverVersion", wintypes.UINT), ("szPname", wintypes.WCHAR * 32),
                ("dwSupport", wintypes.DWORD)]

class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD),
                ("vDriverVersion", wintypes.UINT), ("szPname", wintypes.WCHAR * 32),
                ("wTechnology", wintypes.WORD), ("wVoices", wintypes.WORD),
                ("wNotes", wintypes.WORD), ("wChannelMask", wintypes.WORD),
                ("dwSupport", wintypes.DWORD)]

winmm.midiInGetNumDevs.restype = wintypes.UINT
winmm.midiOutGetNumDevs.restype = wintypes.UINT


def in_ports():
    result = []
    for i in range(winmm.midiInGetNumDevs()):
        c = MIDIINCAPSW(); winmm.midiInGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
        result.append((i, c.szPname))
    return result


def out_ports():
    result = []
    for i in range(winmm.midiOutGetNumDevs()):
        c = MIDIOUTCAPSW(); winmm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
        result.append((i, c.szPname))
    return result


def select(items, hint, label):
    # Prefer an exact port name. This is required when the safe LED port is
    # named "PIONEER DDJ-SX LED", which also contains the control-port name.
    exact = [(i, n) for i, n in items if n.casefold() == hint.casefold()]
    if len(exact) == 1:
        return exact[0][0]
    matches = [(i, n) for i, n in items if hint.casefold() in n.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Eindeutiger {label}-Port nicht gefunden für '{hint}': {matches}")
    return matches[0][0]


def pack(status, d1=0, d2=0):
    return (status & 0xFF) | ((d1 & 0x7F) << 8) | ((d2 & 0x7F) << 16)


def translate(status, d1, d2, filter_state=None, pad_mode=None):
    typ, ch = status & 0xF0, status & 0x0F
    if filter_state is None:
        filter_state = {"value": {0: 0x40, 1: 0x40},
                        "active": {0: True, 1: True}}
    if pad_mode is None:
        pad_mode = {0: "hotcue", 1: "hotcue"}
    # Hard priority: the documented CMD jog messages are handled before any
    # button map. They must never be interpreted as Cue or another button.
    if (status, d1) in ((0xB0, 0x1A), (0xB1, 0x3A)):
        return pack(status, 0x22, d2)
    if (status, d1) in ((0x90, 0x1A), (0x91, 0x3A)):
        return pack(status, 0x36, d2)
    # Official DDJ-SX JogTouch uses 9n 36 with value 00 for release;
    # do not send 8n 36, which can leave rekordbox in scratch mode.
    if (status, d1) in ((0x80, 0x1A), (0x81, 0x3A)):
        return pack(0x90 | ch, 0x36, 0x00)
    # CMD 7-bit mixer controls -> official DDJ-SX 14-bit CC pairs.
    analog = {
        (0, 0x60):(0,0x07,0x27), (1,0x63):(1,0x07,0x27),
        (0, 0x61):(0,0x0B,0x2B), (1,0x64):(1,0x0B,0x2B),
        (0, 0x62):(0,0x0F,0x2F), (1,0x65):(1,0x0F,0x2F),
        (0, 0x70):(0,0x13,0x33), (1, 0x71):(1,0x13,0x33),
        (0, 0x72):(6,0x1F,0x3F),
    }
    if typ == 0xB0 and (ch, d1) in analog:
        target_ch, msb, lsb = analog[(ch, d1)]
        return (pack(0xB0 | target_ch, msb, d2),
                pack(0xB0 | target_ch, lsb, 0))
    # CMD FX1/FX2/FX3 knobs -> DDJ-SX FX1 parameter 1/2/3.
    # Gain is deliberately not translated; B0 10/B1 30 are FX1 knobs here.
    fx_knobs = {
        (0, 0x10):(4, 0x02, 0x22), (0, 0x11):(4, 0x04, 0x24),
        (0, 0x12):(4, 0x06, 0x26),
        (1, 0x30):(5, 0x02, 0x22), (1, 0x31):(5, 0x04, 0x24),
        (1, 0x32):(5, 0x06, 0x26),
        # FX4 -> DDJ-SX Color FX/filter parameter, left/right channel.
        (0, 0x13):(6, 0x17, 0x37), (1, 0x33):(6, 0x18, 0x38),
    }
    if typ == 0xB0 and (ch, d1) in fx_knobs:
        target_ch, msb, lsb = fx_knobs[(ch, d1)]
        if (ch, d1) in ((0, 0x13), (1, 0x33)):
            filter_state["value"][ch] = d2
            if not filter_state["active"][ch]:
                d2 = 0x40
        return (pack(0xB0 | target_ch, msb, d2),
                pack(0xB0 | target_ch, lsb, 0))
    # CMD browser controls -> official DDJ-SX browser messages.
    if status == 0xB0 and ch == 0 and d1 == 0x01:
        return pack(0xB6, 0x40, d2)       # Browse rotary
    if typ in (0x80, 0x90) and ch == 0 and d1 in (0x01, 0x02, 0x03):
        browser_notes = {0x01: 0x41, 0x02: 0x65, 0x03: 0x41}
        return pack(0x96, browser_notes[d1], 0x7F if typ == 0x90 else 0x00)
    # Official DDJ-SX list: platter jog is CC 0x22; limit to its documented
    # relative range (34..63 CCW, 65..89 CW).
    # Pitch bend: CMD 14-bit pitch -> DDJ-SX 14-bit CC 0x00 + 0x20.
    if typ == 0xE0 and ch in (0, 1):
        value = d1 | (d2 << 7)
        msb, lsb = value >> 7, value & 0x7F
        return (pack(0xB0 | ch, 0x00, msb),
                pack(0xB0 | ch, 0x20, lsb))
    # CMD DEL changes the deck's pad mode. Send exactly one mode command per
    # press; sending both modes in one event makes rekordbox's display flicker.
    if typ in (0x80, 0x90) and d2 and (ch, d1) in ((0, 0x2A), (1, 0x4A)):
        pad_mode[ch] = "beatjump" if pad_mode[ch] == "hotcue" else "hotcue"
        mode_note = 0x69 if pad_mode[ch] == "beatjump" else 0x1B
        return pack(0x90 | ch, mode_note, d2)
    # Equal-function buttons: CMD note -> DDJ-SX note on channel 16.
    button = {
        (0,0x2C):0x0B, (1,0x4C):0x0B,  # Play/Pause
        (0,0x2B):0x0C, (1,0x4B):0x0C,  # Cue
        (0,0x2D):0x58, (1,0x4D):0x58,  # Sync
        (0,0x17):0x12, (1,0x38):0x12,  # Loop size smaller
        (0,0x18):0x13, (1,0x37):0x13,  # Loop size larger
        (0,0x19):0x14, (1,0x39):0x14,  # AutoLoop On/Off
        (0,0x6A):0x54, (1,0x6B):0x54,  # Phones/PFL channel cue
        (0,0x50):0x46, (1,0x51):0x47,  # Load Deck 1/2
    }
    hotcue = {}
    for i, note in enumerate(range(0x22, 0x2A)):
        hotcue[(0, note)] = (7, i)
    for i, note in enumerate(range(0x42, 0x4A)):
        hotcue[(1, note)] = (8, i)
    if typ in (0x80, 0x90) and (ch, d1) in hotcue:
        target_ch, note = hotcue[(ch, d1)]
        if pad_mode[ch] == "beatjump":
            note = 0x40 + (note % 8)
        return pack(0x90 | target_ch, note, d2)
    # FX1/FX2/FX3 buttons -> their matching DDJ-SX FX parameter ON messages.
    fx_buttons = {(0,0x10):(4,0x47), (0,0x11):(4,0x48),
                  (0,0x12):(4,0x49), (1,0x30):(5,0x47),
                  (1,0x31):(5,0x48), (1,0x32):(5,0x49),
                  (0,0x52):(4,0x47), (0,0x53):(4,0x48),
                  (1,0x54):(5,0x47), (1,0x55):(5,0x48)}
    if typ in (0x80, 0x90) and (ch, d1) in fx_buttons:
        target_ch, note = fx_buttons[(ch, d1)]
        return pack(0x90 | target_ch, note, d2)
    # FX4 button toggles the CFX filter. The DDJ-SX has no separate factual
    # CFX on/off message: neutral center is the documented filter-off state.
    if typ in (0x80, 0x90) and (ch, d1) in ((0, 0x13), (1, 0x33)):
        if d2 == 0:
            return None
        filter_state["active"][ch] = not filter_state["active"][ch]
        value = filter_state["value"][ch] if filter_state["active"][ch] else 0x40
        msb, lsb = (0x17, 0x37) if ch == 0 else (0x18, 0x38)
        return (pack(0xB6, msb, value), pack(0xB6, lsb, 0))
    if typ in (0x80, 0x90) and ch in (0, 1) and (ch, d1) in button:
        if (ch, d1) == (0, 0x50):
            return pack(0x96, 0x46, d2)
        if (ch, d1) == (1, 0x51):
            return pack(0x96, 0x47, d2)
        return pack(0x90 | ch, button[(ch, d1)], d2)
    return None


def translate_led(status, d1, d2):
    """Translate DDJ-SX feedback from rekordbox to CMD Studio 4A LEDs."""
    typ, ch = status & 0xF0, status & 0x0F
    notes = {
        # Play, Cue, Sync, AutoLoop, Phones/PFL, and loop-size buttons.
        (0, 0x0B): (0, 0x2C), (1, 0x0B): (1, 0x4C),
        (0, 0x0C): (0, 0x2B), (1, 0x0C): (1, 0x4B),
        (0, 0x58): (0, 0x2D), (1, 0x58): (1, 0x4D),
        (0, 0x14): (0, 0x19), (1, 0x14): (1, 0x39),
        (0, 0x54): (0, 0x6A), (1, 0x54): (1, 0x6B),
        (0, 0x12): (0, 0x17), (1, 0x12): (1, 0x38),
        (0, 0x13): (0, 0x18), (1, 0x13): (1, 0x37),
        # FX unit buttons.
        (4, 0x47): (0, 0x10), (4, 0x48): (0, 0x11),
        (4, 0x49): (0, 0x12), (5, 0x47): (1, 0x30),
        (5, 0x48): (1, 0x31), (5, 0x49): (1, 0x32),
    }
    if typ in (0x80, 0x90) and (ch, d1) in notes:
        target_ch, note = notes[(ch, d1)]
        # CMD Studio 4A LED feedback uses 00=off, 01=solid, 02=blinking.
        return pack(0x90 | target_ch, note, 0x01 if d2 else 0x00)
    # DDJ-SX load/FX-assign feedback is on channel 7 (0x96).
    special = {
        (6, 0x46): (0, 0x50), (6, 0x47): (1, 0x51),
        (6, 0x4C): (0, 0x52), (6, 0x4D): (0, 0x53),
        (6, 0x50): (1, 0x54), (6, 0x51): (1, 0x55),
    }
    if typ in (0x80, 0x90) and (ch, d1) in special:
        target_ch, note = special[(ch, d1)]
        return pack(0x90 | target_ch, note, 0x01 if d2 else 0x00)
    return None


def local_led_feedback(status, d1, d2, led_state):
    """Create a direct Studio 4A LED message without using rekordbox MIDI-OUT."""
    typ, ch = status & 0xF0, status & 0x0F
    if typ not in (0x80, 0x90) or d2 == 0:
        return None
    key = (ch, d1)
    # Play/Pause, Cue and Sync are requested as permanently illuminated indicators.
    permanent = {
        (0, 0x2C): 0x2C, (1, 0x4C): 0x4C,
        (0, 0x2B): 0x2B, (1, 0x4B): 0x4B,
        (0, 0x2D): 0x2D, (1, 0x4D): 0x4D,
    }
    if key in permanent:
        return pack(0x90 | ch, permanent[key], 0x01)
    # These controls are locally toggled because rekordbox MIDI-OUT is
    # intentionally disabled to prevent a LoopMIDI feedback loop.
    toggles = {
        (0, 0x19): 0x19, (1, 0x39): 0x39,  # AutoLoop
        (0, 0x6A): 0x6A, (1, 0x6B): 0x6B,  # Phones/PFL
        (0, 0x10): 0x10, (0, 0x11): 0x11, (0, 0x12): 0x12,
        (0, 0x13): 0x13,
        (1, 0x30): 0x30, (1, 0x31): 0x31, (1, 0x32): 0x32,
        (1, 0x33): 0x33,
    }
    if key in toggles:
        led_state[key] = not led_state.get(key, False)
        return pack(0x90 | ch, toggles[key], 0x01 if led_state[key] else 0x00)
    return None


def main():
    ap = argparse.ArgumentParser(description="CMD Studio 4A DDJ-SX-Bridge ohne C++/pip")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--input", default="CMD Studio 4A")
    ap.add_argument("--output", default="PIONEER DDJ-SX")
    ap.add_argument("--feedback-input", default="",
                    help="Separater MIDI-Eingang für rekordbox-MIDI-OUT/LED-Feedback")
    ap.add_argument("--monitor", action="store_true")
    args = ap.parse_args()
    ins, outs = in_ports(), out_ports()
    if args.list:
        print("MIDI-Eingänge:"); print("\n".join(f"{i}: {n}" for i,n in ins))
        print("MIDI-Ausgänge:"); print("\n".join(f"{i}: {n}" for i,n in outs)); return 0
    try:
        in_id = select(ins, args.input, "Eingangs")
        out_id = select(outs, args.output, "Ausgangs")
        feedback_in_id = (select(ins, args.feedback_input, "LED-Feedback-Eingangs")
                          if args.feedback_input else None)
        led_out_id = select(outs, args.input, "LED-Ausgangs")
        events = queue.Queue()
        def make_callback(source):
            @MIDI_CALLBACK
            def callback(handle, message, instance, param1, param2):
                if message == MIM_DATA:
                    events.put((source, param1 & 0xFFFFFF))
            return callback
        control_callback = make_callback("control")
        feedback_callback = make_callback("feedback")
        in_handle = wintypes.HANDLE(); out_handle = wintypes.HANDLE()
        feedback_handle = wintypes.HANDLE(); led_handle = wintypes.HANDLE()
        r = winmm.midiOutOpen(ctypes.byref(out_handle), out_id, 0, 0, 0)
        if r != MMSYSERR_NOERROR: raise RuntimeError(f"midiOutOpen Fehler {r}")
        r = winmm.midiOutOpen(ctypes.byref(led_handle), led_out_id, 0, 0, 0)
        if r != MMSYSERR_NOERROR: raise RuntimeError(f"LED-Ausgang öffnen Fehler {r}")
        r = winmm.midiInOpen(ctypes.byref(in_handle), in_id, ctypes.cast(control_callback, ctypes.c_void_p), 0, CALLBACK_FUNCTION)
        if r != MMSYSERR_NOERROR: raise RuntimeError(f"midiInOpen Fehler {r}")
        if feedback_in_id is not None:
            r = winmm.midiInOpen(ctypes.byref(feedback_handle), feedback_in_id, ctypes.cast(feedback_callback, ctypes.c_void_p), 0, CALLBACK_FUNCTION)
            if r != MMSYSERR_NOERROR: raise RuntimeError(f"LED-Feedback öffnen Fehler {r}")
        winmm.midiInStart(in_handle)
        if feedback_in_id is not None:
            winmm.midiInStart(feedback_handle)
        # Play/Pause, Cue and Sync are intentionally always illuminated.
        # CMD Studio 4A: 00=off, 01=solid, 02=blinking.
        for packet in (pack(0x90, 0x2C, 0x01), pack(0x91, 0x4C, 0x01),
                       pack(0x90, 0x2B, 0x01), pack(0x91, 0x4B, 0x01),
                       pack(0x90, 0x2D, 0x01), pack(0x91, 0x4D, 0x01)):
            winmm.midiOutShortMsg(led_handle, packet)
        led_state = {}
        filter_state = {"value": {0: 0x40, 1: 0x40},
                        "active": {0: True, 1: True}}
        pad_mode = {0: "hotcue", 1: "hotcue"}
        feedback_line = (f"LED-Feedback: {ins[feedback_in_id][1]} -> {outs[led_out_id][1]}"
                         if feedback_in_id is not None else
                         "LED-Feedback: lokale Simulation")
        print(f"Eingang: {ins[in_id][1]}\nAusgang: {outs[out_id][1]}\n"
              f"{feedback_line}\nStrg+C beendet.")
        try:
            while True:
                try:
                    source, raw = events.get(timeout=0.1)
                except queue.Empty:
                    # Normalzustand: Der Controller sendet nicht permanent.
                    continue
                status, d1, d2 = raw & 255, (raw >> 8) & 127, (raw >> 16) & 127
                if args.monitor:
                    print(f"IN  {status:02X} {d1:02X} {d2:02X}", flush=True)
                if source == "feedback":
                    result = translate_led(status, d1, d2)
                    destination = led_handle
                else:
                    local_led = local_led_feedback(status, d1, d2, led_state)
                    if local_led is not None:
                        winmm.midiOutShortMsg(led_handle, local_led)
                    result = translate(status, d1, d2, filter_state, pad_mode)
                    destination = out_handle
                if result is None: continue
                packets = result if isinstance(result, tuple) else (result,)
                for packet in packets: winmm.midiOutShortMsg(destination, packet)
                if args.monitor: print(f"OUT {packets}", flush=True)
        except KeyboardInterrupt:
            pass
        finally:
            winmm.midiInStop(in_handle); winmm.midiInClose(in_handle)
            if feedback_in_id is not None:
                winmm.midiInStop(feedback_handle); winmm.midiInClose(feedback_handle)
            winmm.midiOutClose(out_handle); winmm.midiOutClose(led_handle)
    except Exception as exc:
        print(f"Fehler: {exc}", file=sys.stderr); return 2
    return 0

if __name__ == "__main__": sys.exit(main())
