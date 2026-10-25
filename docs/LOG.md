# Build log

How the A25-TX012 remote was mapped and taught to an ESP32, in order, all on 2026-10-25. Real
output, trimmed; addresses and network details removed. Several early conclusions were wrong;
they're kept and marked **Correction**, because the mistake is the useful part. The finished
protocol is in [PROTOCOL.md](PROTOCOL.md).

## The remote: FCC ID A25-TX012

The FCC record for `A25-TX012` is a "TX012 Transmitter" from DawnSun Electronic, granted
2013-04-12, **315 MHz**, equipment class "Part 15 Security/Remote Control Transmitter". Replacement
listings describe it as the remote for Harbor Breeze DC fans: 6 speeds, dimmable light, reverse,
timer. So: a simple fixed-code remote, probably on-off keying. A CC1101 (300–348 MHz among its
bands) and ESPHome's built-in `cc1101` component should do.

## The 433 MHz board

The CC1101 module was listed as 315 MHz, but its silkscreen says **433M**. The chip tunes 315 MHz
either way; only the matching parts around it differ, which costs range. Decided to test before
returning it. (It turned out fine.)

## Wiring and first boot

8-pin CC1101 to an ESP-WROOM-32 (pinout in the README). Listen-only config: `cc1101` at 315 MHz,
ASK/OOK, `remote_receiver` on GDO2. First boot:

```
[D][cc1101]: CC1101 found! Chip ID: 0x0014
[C][cc1101]:   Frequency: 314999680 Hz
[C][cc1101]:   Modulation: ASK/OOK
[C][cc1101]:   Output Power: 9.6 dBm
```

## First capture: clean, regular frames

Pressing remote buttons a few metres away gave 6 identical bursts per press, ~44 ms apart, and no
noise in between. ESPHome's `rc_switch` decoder misread them (`protocol=3 data='00000000000000000'`),
so I logged the raw timings (µs, positive = carrier on):

```
475,-913,435,-919,434,-944,424,-940,435,-941,411,-949,429,-944,414,-948,435,-917,436,-940,
435,-939,436,-914,434,-939,435,-941,412,-948,430,-943,414,-953,417,-491,889,-485,863,-948,
430,-491,874,-946,411,-493,898,-918,446,-8000
```

Decoded as "short pulse = 0, long pulse = 1" this is 24 bits plus a stop pulse: sixteen zeros, then
`0x35` for Light. Pressing every button gave a code each (`0x79` power, `0x39` speed 1, …), and
pressing the same button twice gave the same code: **no rolling code**.

> **Correction:** that reading threw away half the information. Look at `417,-491`: a short pulse
> followed by a *short* gap. The gaps aren't simply the complement of the pulses. See below.

## Transmit doesn't work

Added `remote_transmitter` on GDO0 and a test button per code, sending "short pulse + long gap" for 0
and "long pulse + short gap" for 1. The log showed `Sending 0x000035`, but the fan didn't react,
even with the ESP32 right under it, with every antenna to hand.

Tried, all without result:

- **13 frequencies**, 314.70–315.30 MHz in 50 kHz steps, 10 repeats each;
- **8 pulse widths**, 280–540 µs short pulse at a fixed 1360 µs bit period;
- **single-pin mode** (`gdo0_pin`, RX and TX both on GDO0), which also proved the GDO0 wire was
  fine, because the remote's frames came in on it;
- a **5-second carrier** to see whether it jams the real remote. Inconclusive: the real remote
  itself only worked about half the time near the fan.

> **Correction:** the last point was a clue I missed at the time: the ESP32 was jamming the fan.
> See below.

## An RTL-SDR settles what's on the air

With a Nooelec NESDR and `rtl_433 -f 315M -A`, standing at the same spot:

| Source | What the SDR saw |
|---|---|
| Real remote, Light | 6 frames of 25 pulses, +1 dB (full scale) |
| ESP32, Light (single-pin mode) | **nothing**, only noise |
| ESP32, 5 s carrier at 315 MHz | **nothing** |
| ESP32, 5 s carrier at 433.92 MHz | strong; the board does transmit |

So in **single-pin mode no data reached the radio**. Back to two pins (TX on GDO0, RX on GDO2), the
ESP32's frames showed up just like the remote's:

```
remote: pulses 478 / 925 us, gaps 888 / 441 us, frame 33.26 ms, -40 kHz, +1.1 dB
ESP32:  pulses 445 / 924 us, gaps 915 / 433 us, frame 33.11 ms, -17 kHz, +1.3 dB
```

Set the remote's exact timings and moved the carrier to 314.98 MHz, which put the two within ~10 kHz.
The fan still ignored it.

## The ESP32 was deafening the fan

Unplugging the ESP32 made the real remote work every time again. While listening, the CC1101 leaks
enough at 315 MHz to deafen a receiver a few centimetres away. Moved it a few metres away: the
remote was reliable again, with the ESP32 still listening. Added a **Listen for remote** switch
that idles the radio between sends, in case it ever has to sit close.

The fan still ignored the ESP32, though, even with listening off.

## 2026-10-25: The gaps carry data too

Comparing the `triq.org/pdv` strings that `rtl_433 -A` prints (one byte per pulse + gap, `8` + pulse
bin + gap bin) showed it at once:

```
remote: …8181 8181 80 90 91 80 91 80 91 82 55
ESP32:  …8181 8181 81 90 90 81 90 81 90 82 55
```

The pulses matched, the gaps didn't: the remote sends `80` (short pulse, short gap) and `91` (long
pulse, long gap), which "complementary" encoding can't produce. Re-decoded every button as 49
elements, pulses and gaps each short or long. All 6 copies of every press agreed:

```
0101010101010101010101010101010101001011001100110   Light
0101010101010101010101010101010100101010110100110   Fan power
0101010101010101010101010101010101001010110100110   Speed 1
```

Rewrote the encoder to send all 49 elements, checked on the SDR that the strings were identical,
and sent Light: **the fan responded on the first try.**

## The fan dozes

The fan sometimes ignored the first command and obeyed the next one right after it. The real remote
did the same (the first Light press during the SDR test did nothing). Sending everything twice
isn't an option, because power and Light are toggles. Instead each send now starts with a
**300 ms unmodulated carrier**, which wakes the receiver without counting as a press. Checked on
the SDR (one 561 ms burst: carrier, then 6 frames) and on the fan: first press, every time.

## Home Assistant entities

Behaviour tested with the remote's buttons:

- Speed buttons turn the fan on from off; power off then on comes back at the last speed.
- Wave = breeze (speed rises and falls) and switches to snowflake.
- Home: steady full light; pressed again it blinked the light and turned the fan off.
- Light flickers smart bulbs (the receiver dims), Clock blinks the light.

So the fan entity sends a **speed** to turn on or change speed (exact, never a toggle) and **power**
only to turn off. Light, Home and Clock stay plain buttons. Timer buttons start a countdown on the
ESP32 so the entity shows off when the fan's timer ends. Fan state restores at boot **without**
transmitting.

## Two fans: the 0/1 switch is the ID

Both remotes were on switch 0, and either one worked both fans. With the ESP32 logging every valid
frame's ID:

```
[I][remote]: Heard Light                                   <- remote 1, switch 0
[I][remote]: Heard Light                                   <- remote 2, switch 0 (same ID)
[I][remote]: Other remote: id 00101100110101001100110100110100 button 0x19666   <- remote 2, switch 1
```

All 16 buttons on switch 1 differed from switch 0 only in the first 33 elements. So the ID is 33
elements (not 32), and the 16 button elements are the same on every remote. Paired the second fan
to switch 1 (power-cycle, hold learn): each remote now works only its own fan, and the firmware got
one `packages:` entry per fan.

## Range

From a spot a few metres from the first fan, one ESP32 reaches a fan on another floor at the other
end of the house, both sending and hearing that fan's remote.
