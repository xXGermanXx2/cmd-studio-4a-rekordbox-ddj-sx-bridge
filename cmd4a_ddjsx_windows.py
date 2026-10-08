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
    matches = [(i, n) for i, n in items if hint.lower() in n.lower()]
    if len(matches) != 1:
        raise RuntimeError(f"Eindeutiger {label}-Port nicht gefunden für '{hint}': {matches}")
    return matches[0][0]


def pack(status, d1=0, d2=0):
    return (status & 0xFF) | ((d1 & 0x7F) << 8) | ((d2 & 0x7F) << 16)


def translate(status, d1, d2):
    typ, ch = status & 0xF0, status & 0x0F
    # Hard priority: the documented CMD jog messages are handled before any
    # button map. They must never be interpreted as Cue or another button.
    if typ == 0xB0 and ch in (0, 1) and d1 in (0x1A, 0x3A):
        return pack(0xB0 | ch, 0x22, max(34, min(89, d2)))
    if typ in (0x80, 0x90) and ch in (0, 1) and d1 in (0x1A, 0x3A):
        return pack(typ | ch, 0x36, d2)
    # CMD 7-bit mixer controls -> official DDJ-SX 14-bit CC pairs.
    analog = {
        (0, 0x10):(0,0x04,0x24), (1,0x30):(1,0x04,0x24),
        (0, 0x60):(0,0x07,0x27), (1,0x63):(1,0x07,0x27),
        (0, 0x61):(0,0x0B,0x2B), (1,0x64):(1,0x0B,0x2B),
        (0, 0x62):(0,0x0F,0x2F), (1,0x65):(1,0x0F,0x2F),
        (0, 0x70):(0,0x13,0x00), (1, 0x71):(1,0x13,0x00),
        (0, 0x72):(6,0x1F,0x3F),
    }
    if typ == 0xB0 and (ch, d1) in analog:
        target_ch, msb, lsb = analog[(ch, d1)]
        return pack(0xB0 | target_ch, msb, d2)
    # CMD FX knobs 2/3 -> official DDJ-SX FX1/FX2 parameter MSB+LSB pairs.
    fx_knobs = {
        (0, 0x11):(4, 0x02, 0x22), (0, 0x12):(4, 0x04, 0x24),
        (1, 0x31):(5, 0x02, 0x22), (1, 0x32):(5, 0x04, 0x24),
    }
    if typ == 0xB0 and (ch, d1) in fx_knobs:
        target_ch, msb, lsb = fx_knobs[(ch, d1)]
        return pack(0xB0 | target_ch, msb, d2)
    # Official DDJ-SX list: platter jog is CC 0x22; limit to its documented
    # relative range (34..63 CCW, 65..89 CW).
    # Pitch bend: CMD 14-bit pitch -> DDJ-SX 14-bit CC 0x00 + 0x20.
    if typ == 0xE0 and ch in (0, 1):
        value = d1 | (d2 << 7)
        msb, lsb = value >> 7, value & 0x7F
        return (pack(0xB0 | ch, 0x00, msb), pack(0xB0 | ch, 0x20, lsb))
    # Equal-function buttons: CMD note -> DDJ-SX note on channel 16.
    button = {
        (0,0x2C):0x0B, (1,0x4C):0x0B,  # Play/Pause
        (0,0x2B):0x0C, (1,0x4B):0x0C,  # Cue
        (0,0x2D):0x58, (1,0x4D):0x58,  # Sync
        (0,0x17):0x10, (1,0x38):0x10,  # Loop In
        (0,0x18):0x11, (1,0x37):0x11,  # Loop Out
    }
    hotcue = {}
    for i, note in enumerate(range(0x22, 0x2A)):
        hotcue[(0, note)] = (7, i)
    for i, note in enumerate(range(0x42, 0x4A)):
        hotcue[(1, note)] = (8, i)
    if typ in (0x80, 0x90) and (ch, d1) in hotcue:
        target_ch, note = hotcue[(ch, d1)]
        return pack(0x90 | target_ch, note, d2)
    # FX assign 1/2: official DDJ-SX FX1/FX2 ON messages.
    fx_buttons = {(0,0x52):(4,0x47), (0,0x53):(4,0x48),
                  (1,0x54):(5,0x47), (1,0x55):(5,0x48)}
    if typ in (0x80, 0x90) and (ch, d1) in fx_buttons:
        target_ch, note = fx_buttons[(ch, d1)]
        return pack(0x90 | target_ch, note, d2)
    if typ in (0x80, 0x90) and ch in (0, 1) and (ch, d1) in button:
        if (ch, d1) == (0, 0x50):
            return pack(0x96, 0x46, d2)
        if (ch, d1) == (1, 0x51):
            return pack(0x96, 0x47, d2)
        return pack(0x90 | ch, button[(ch, d1)], d2)
    return None


def main():
    ap = argparse.ArgumentParser(description="CMD Studio 4A DDJ-SX-Bridge ohne C++/pip")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--input", default="CMD Studio 4A")
    ap.add_argument("--output", default="PIONEER DDJ-SX")
    ap.add_argument("--monitor", action="store_true")
    args = ap.parse_args()
    ins, outs = in_ports(), out_ports()
    if args.list:
        print("MIDI-Eingänge:"); print("\n".join(f"{i}: {n}" for i,n in ins))
        print("MIDI-Ausgänge:"); print("\n".join(f"{i}: {n}" for i,n in outs)); return 0
    try:
        in_id, out_id = select(ins, args.input, "Eingangs"), select(outs, args.output, "Ausgangs")
        events = queue.Queue()
        @MIDI_CALLBACK
        def callback(handle, message, instance, param1, param2):
            if message == MIM_DATA:
                events.put(param1 & 0xFFFFFF)
        in_handle = wintypes.HANDLE(); out_handle = wintypes.HANDLE()
        r = winmm.midiOutOpen(ctypes.byref(out_handle), out_id, 0, 0, 0)
        if r != MMSYSERR_NOERROR: raise RuntimeError(f"midiOutOpen Fehler {r}")
        r = winmm.midiInOpen(ctypes.byref(in_handle), in_id, ctypes.cast(callback, ctypes.c_void_p), 0, CALLBACK_FUNCTION)
        if r != MMSYSERR_NOERROR: raise RuntimeError(f"midiInOpen Fehler {r}")
        winmm.midiInStart(in_handle)
        print(f"Eingang: {ins[in_id][1]}\nAusgang: {outs[out_id][1]}\nStrg+C beendet.")
        try:
            while True:
                try:
                    raw = events.get(timeout=0.1)
                except queue.Empty:
                    # Normalzustand: Der Controller sendet nicht permanent.
                    continue
                status, d1, d2 = raw & 255, (raw >> 8) & 127, (raw >> 16) & 127
                if args.monitor:
                    print(f"IN  {status:02X} {d1:02X} {d2:02X}", flush=True)
                result = translate(status, d1, d2)
                if result is None: continue
                packets = result if isinstance(result, tuple) else (result,)
                for packet in packets: winmm.midiOutShortMsg(out_handle, packet)
                if args.monitor: print(f"OUT {packets}", flush=True)
        except KeyboardInterrupt:
            pass
        finally:
            winmm.midiInStop(in_handle); winmm.midiInClose(in_handle); winmm.midiOutClose(out_handle)
    except Exception as exc:
        print(f"Fehler: {exc}", file=sys.stderr); return 2
    return 0

if __name__ == "__main__": sys.exit(main())
