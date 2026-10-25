#!/usr/bin/env python3
"""Decode remote frames from an ESPHome log into short/long elements, an ID and a button.

Turn on the "Log raw frames" switch, press buttons on the remote, and save the log:

    uvx esphome logs fans.yaml --device <ESP32 IP> | tee presses.log
    python3 tools/decode_frames.py presses.log

Each `[raw]` line is one frame: microseconds, positive = carrier on, negative = off, ending with
the idle gap. Pulses and gaps are each sorted into short/long around the midpoint of what was
heard, so it also works for remotes with other timings. Consecutive identical frames (one press)
are printed once with a count.

For the A25-TX012 the first 33 elements are the remote's ID and the last 16 the button
(docs/PROTOCOL.md). Other remotes may split differently: compare several buttons and see which
elements never change.
"""
import re
import sys

LINE = re.compile(r"\[(\d\d:\d\d:\d\d(?:\.\d+)?)\].*\[raw[^\]]*\]: (\d+): ([-0-9,]+)")
ID_LEN = 33


def frames(path):
    for line in open(path, errors="replace"):
        m = LINE.search(line)
        if m:
            values = [int(v) for v in m.group(3).strip(",").split(",") if v]
            yield m.group(1), values[:-1]  # drop the closing idle gap


def midpoint(values):
    """A threshold between the short and long cluster of these durations."""
    if not values:
        return 0
    lo, hi = min(values), max(values)
    for _ in range(20):
        mid = (lo + hi) / 2
        short = [v for v in values if v < mid] or [lo]
        long_ = [v for v in values if v >= mid] or [hi]
        lo, hi = sum(short) / len(short), sum(long_) / len(long_)
    return (lo + hi) / 2


def main(path):
    found = list(frames(path))
    if not found:
        sys.exit("No [raw] lines found. Turn on 'Log raw frames' and press some buttons.")
    pulses = [v for _, f in found for v in f if v > 0]
    gaps = [-v for _, f in found for v in f if v < 0]
    p_mid, g_mid = midpoint(pulses), midpoint(gaps)
    print(f"pulses: short/long split at {p_mid:.0f} us; gaps: at {g_mid:.0f} us")

    presses = []
    for t, f in found:
        bits = "".join("1" if (v > p_mid if v > 0 else -v > g_mid) else "0" for v in f)
        if presses and presses[-1][1] == bits:
            presses[-1][2] += 1
        else:
            presses.append([t, bits, 1])

    for t, bits, n in presses:
        if len(bits) == 49:
            print(f"{t}  x{n}  id {bits[:ID_LEN]}  button 0x{int(bits[ID_LEN:], 2):04X}")
        else:
            print(f"{t}  x{n}  {len(bits)} elements: {bits}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
