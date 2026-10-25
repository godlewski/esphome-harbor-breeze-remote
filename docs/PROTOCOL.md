# The A25-TX012 remote's signal

Everything here was measured on two A25-TX012 remotes and their two fans, first with the CC1101
itself and then checked against an RTL-SDR running `rtl_433 -A`.

## Radio

| | |
|---|---|
| FCC ID | A25-TX012 (grantee DawnSun Electronic, granted 2013-04-12), "TX012 Transmitter", 315 MHz |
| Measured carrier | about **314.96 MHz** (the config uses 314.98; the fan's receiver accepts both) |
| Modulation | On-off keying (carrier on / off) |
| Per press | The same frame **6 times**, one every ~44 ms |
| Rolling code | **None.** Pressing a button twice sends exactly the same frames |

## Frame

A frame is **49 elements** that alternate carrier **on**, **off**, **on**, … and start and end with
**on**. Each element is either short or long, and **the pulses and the gaps vary independently**:

| | Short | Long |
|---|---|---|
| Carrier on (pulse) | 478 µs | 925 µs |
| Carrier off (gap) | 441 µs | 888 µs |

A frame lasts ~33.3 ms, followed by a ~10 ms gap before the next copy.

Write a frame as 49 characters, `1` = long, `0` = short, first element first:

```
010101010101010101010101010101010 1001011001100110
└──────────── 33: remote ID ────┘ └─ 16: button ─┘
```

That's **Light** from a remote on switch 0.

> Don't decode only the pulses. Read as "short pulse = 0, long pulse = 1" the frame looks like a
> clean 24-bit code, and replaying it with complementary gaps produces something the fan ignores.
> The gaps carry information too. See the [build log](LOG.md#2026-10-25-the-gaps-carry-data-too).

## Remote IDs

The **0/1 switch** in the battery compartment picks the ID:

| Switch | ID (33 elements) |
|---|---|
| 0 | `010101010101010101010101010101010` |
| 1 | `001011001101010011001101001101001` |

Both tested remotes sent identical IDs at the same switch position, so these look like fixed codes
for the model rather than per-remote serials. The fan's receiver obeys the ID it learned when its
**learn** button was pressed (power-cycle the fan, then hold learn within ~30 s). That makes two fans
separately controllable; more than two would need IDs nobody has tested (the firmware accepts any
33-element `remote_id`, so you could try teaching a third fan an ID only the ESP32 sends).

## Buttons

The last 16 elements, written as hex with the first element in the top bit. They're the same on
every remote and switch position.

| Button | Code | What it does (tested fans) |
|---|---|---|
| Fan power | `0x55A6` | **Toggle**: on (at the last speed) or off |
| Speed 1 | `0x95A6` | Speed 1; turns the fan on if it's off |
| Speed 2 | `0x65A6` | " |
| Speed 3 | `0xA5A6` | " |
| Speed 4 | `0x59A6` | " |
| Speed 5 | `0x99A6` | " |
| Speed 6 | `0x69A6` | " |
| Wave | `0xA9A6` | Breeze mode: the speed rises and falls. Also switches to reverse (snowflake) |
| Home | `0xAA56` | Light on at steady full power; pressed again it blinked the light and turned the fan off |
| Light | `0x9666` | **Toggle** for the light (the receiver dims it, which makes smart bulbs flicker) |
| Clock | `0xA6A6` | Blinks the light; exact function unknown (maybe a sleep timer) |
| 2h | `0x9656` | Turn off after 2 hours |
| 4h | `0x6656` | Turn off after 4 hours |
| 8h | `0xA656` | Turn off after 8 hours |
| Sun | `0x5666` | Forward |
| Snowflake | `0x56A6` | Reverse |

The sun/snowflake switch sends on each change, so the direction is always known.

## Fan receiver behaviour

- **It dozes when idle** and misses the first frame burst after a while; a second press works. The
  real remote has the same habit. The firmware sends a 300 ms unmodulated carrier first, which
  wakes it without counting as a press.
- **A CC1101 that's receiving right next to it deafens it.** A few metres away, no problem.

## Mapping another remote

1. Turn on **Log raw frames** (Home Assistant, device page, diagnostic), press each button once a
   couple of seconds apart, and save the log (`uvx esphome logs fans.yaml --device <ip> | tee presses.log`).
2. `python3 tools/decode_frames.py presses.log` prints one line per press: the elements split into
   ID and button if there are 49, otherwise all of them.
3. Compare buttons: the elements that never change are the remote's ID.
4. If yours isn't 49 elements, or its timings differ a lot, the encoder and decoder in
   `esphome/harbor-fans.yaml` (the `send_code` script and `remote_receiver`'s `on_raw`) need
   adjusting. Check the result on the air before blaming the fan.

Checking on the air with an RTL-SDR:

```bash
rtl_433 -f 314.98M -s 1024k -A          # then press a button
```

For each burst `rtl_433 -A` prints a `https://triq.org/pdv/#…` link. After the header, each byte is
one pulse and the gap after it (`8` + pulse bin + gap bin), so two signals are identical when their
strings match. This is how the gap encoding showed up:

```
remote: …8181 80 90 91 80 91 80 91 82 55
ESP32:  …8181 81 90 90 81 90 81 90 82 55     (pulses right, gaps wrong)
```
