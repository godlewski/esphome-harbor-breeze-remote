# Harbor Breeze ceiling fan remote (A25-TX012) → Home Assistant

> [!CAUTION]
> **Use at your own risk.** This is a hobby project shared as-is, with no warranty of any kind. I am
> not responsible for any damage, voided warranty or other loss that results from using this code,
> these instructions or the hardware described here. You alone are responsible for how you build
> and use it, including following the radio rules where you live. See the [license](LICENSE).

**Control Harbor Breeze DC ceiling fans from Home Assistant**, with an ESP32 and a cheap CC1101
radio that sends exactly what the fan's 315 MHz remote sends. No wiring into the fan, no cloud, and
the original remotes keep working.

- **Fan:** on/off, all 6 speeds, direction, and the remote's breeze ("wave") mode.
- **Timers:** 2 h / 4 h / 8 h, and Home Assistant shows the fan off when the timer ends.
- **Light:** the remote's Light, Home and Clock buttons.
- **Two-way:** it also listens for the real remotes, so Home Assistant follows them.
- **Several fans** from one ESP32, each paired to its own remote ID.

> [!NOTE]
> **Built with AI.** I worked this out and wrote the config and these docs together with an AI
> coding agent (Claude Code), and tested each step on my own fans. The [build log](docs/LOG.md)
> shows how, including the mistakes that cost the most time. Review it before you trust it, like
> any code you find online.

Unofficial; not affiliated with or endorsed by Harbor Breeze, Lowe's or the remote's maker.

---

## Does it work with my fan?

**Tested with:** two Harbor Breeze **DC-motor** ceiling fans whose remote has **FCC ID A25-TX012**
(printed on the back or in the battery compartment), from about 2013. It has a 0/1 switch and a
learn button under the battery cover, and these buttons:

fan power · speeds 1–6 · wave · home · light · clock · 2h · 4h · 8h · sun/snowflake slide switch

| Feature | Status |
|---|---|
| Fan on/off, speeds 1–6 | ✅ |
| Direction (sun = forward, snowflake = reverse) | ✅ |
| Breeze (the wave button) | ✅ preset in Home Assistant |
| Timer 2h / 4h / 8h | ✅ |
| Light, Home, Clock buttons | ✅ sent as-is (see [what they do](docs/PROTOCOL.md#buttons)) |
| Real remote updates Home Assistant | ✅ |
| Two fans controlled separately | ✅ one on remote switch 0, one on 1 |
| More than two fans | Untested; the remote only has two switch positions (see [PROTOCOL](docs/PROTOCOL.md#remote-ids)) |

A different remote (another FCC ID) almost certainly uses a different signal. The firmware has a
**Log raw frames** switch and [tools/decode_frames.py](tools/decode_frames.py) to capture one; see
[mapping another remote](docs/PROTOCOL.md#mapping-another-remote).

## What you need

- An **ESP32 dev board** (tested: a classic ESP-WROOM-32 board, `esp32dev`).
- A **CC1101 module with 8 pins** in a 2×4 header and an antenna. Tested: a generic green board whose
  silkscreen says **433M**. It works at 315 MHz anyway; a true 315 MHz board should do as well or
  better.
- **8 female-to-female jumper wires.**
- A USB power supply for wherever the ESP32 ends up.
- A computer with [uv](https://docs.astral.sh/uv/) (to run ESPHome as `uvx esphome …`), or the
  ESPHome add-on in Home Assistant.
- 2.4 GHz Wi-Fi.

Optional, only for mapping a different remote: an **RTL-SDR** USB receiver (tested: Nooelec NESDR
Smart) with [rtl_433](https://github.com/merbanan/rtl_433). It shows what's actually on the air,
which is how most bugs in this project were found.

## How it works

```
Remote  ~~ 315 MHz ~~>  Fan receiver
                ^
                |  315 MHz (sends and listens)
          CC1101 radio  <-- SPI -->  ESP32 (ESPHome)  <-- Wi-Fi -->  Home Assistant
```

The remote sends a fixed code per button: the remote's **ID** (set by its 0/1 switch) plus the
**button**, repeated 6 times. There's **no rolling code and no encryption**, so the ESP32 can send
the same thing. The fan's receiver learns which ID to obey when you press the learn button. Details:
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Setup

### 1. Wire the radio

**Unplug the ESP32 while wiring.** Match by the numbers printed next to the CC1101's pins. On a 2×4
header they usually run across the pairs: 1 and 2 side by side, then 3 and 4, and so on.

| CC1101 pin | Signal | ESP32 pin |
|---|---|---|
| 1 | GND | GND |
| 2 | VCC | **3V3** (never 5V or VIN) |
| 3 | GDO0 | GPIO32 (`D32`) |
| 4 | CSN | GPIO5 (`D5`) |
| 5 | SCK | GPIO18 (`D18`) |
| 6 | MOSI | GPIO23 (`D23`) |
| 7 | MISO | GPIO19 (`D19`) |
| 8 | GDO2 | GPIO33 (`D33`) |

Check pins 1 and 2 before powering on: they're the only ones that can break something. Pin 1 (GND)
connects to the metal shield and the antenna connector's outer ring (a multimeter beeps). If your
board's listing shows a different pinout, follow the listing. Attach the antenna.

### 2. Get the code and fill in your secrets

```bash
git clone https://github.com/godlewski/esphome-harbor-breeze-remote.git
cd esphome-harbor-breeze-remote/esphome
cp secrets.yaml.template secrets.yaml
openssl rand -base64 32                   # paste as fans_api_key
```

Fill in your Wi-Fi name and password, the API key, and a fallback-hotspot password.
`secrets.yaml` is gitignored; keep it that way.

On Linux, your user needs access to the serial port (group `dialout` on Debian/Ubuntu, `uucp` on
Arch; log out and back in after adding it).

### 3. Pair each fan to its own remote ID

If you have **one fan**, delete the `fan_2` entry in `fans.yaml` and skip to step 4.

If you have **two**, they must be on different IDs, or every command (from the ESP32 or either
remote) moves both fans. Out of the box both remotes are usually on **0**.

1. Leave the first fan's remote on **0**.
2. Set the second fan's remote switch to **1**.
3. Turn the second fan's power off at the wall or breaker for about 10 seconds, then back on.
4. Within about 30 seconds, press and hold **learn** on that remote until the fan's light blinks.
5. Check: the second remote (on 1) works its fan; the first remote no longer does anything there.

In `fans.yaml`, give each fan a name. `remote_id` stays as it is: on the remotes tested, switch 0
and switch 1 always sent those IDs. If yours differs, the log tells you (step 5).

### 4. Flash

```bash
uvx esphome config fans.yaml              # validate first
uvx esphome run fans.yaml                 # first time over USB; pick the serial port
```

Later updates go over Wi-Fi: `uvx esphome run fans.yaml --device <ESP32 IP>`.

### 5. Check the log

```bash
uvx esphome logs fans.yaml --device <ESP32 IP>
```

At boot you should see `CC1101 found! Chip ID: 0x0014` (anything like `FF0F`, `0000` or `FFFF`
means the SPI wiring is wrong). Then press **Light** on each remote:

```
[I][remote]: Fan 1: heard Light
[I][remote]: Fan 2: heard Light
```

`Other remote: id 0010… button 0x9666` means the ESP32 heard a remote whose ID isn't in
`fans.yaml`. Copy that ID into the right fan's `remote_id` and flash again.

### 6. Place it

**Not right next to a fan.** While listening, the CC1101 leaks enough at 315 MHz to deafen a fan
receiver a few centimetres away (the real remote starts missing). A few metres away is fine, and its
range is good: in the tested house one ESP32 reaches fans on another floor at the far end.

### 7. Add it to Home Assistant

It's usually discovered: *Settings → Devices & services → ESPHome*. Otherwise add ESPHome by IP.
Enter your `fans_api_key`. Reserve the ESP32's IP on your router so it doesn't change.

## Home Assistant

Per fan (names come from `fan_name`; Home Assistant may prefix the device's area):

| Entity | What |
|---|---|
| `fan.…_fan_1` | On/off, 6 speeds, direction (forward = sun, reverse = snowflake), preset **Breeze** |
| `button.…_fan_1_light` / `_home` / `_clock` | The remote's Light, Home and Clock buttons |
| `button.…_fan_1_timer_2h` / `_4h` / `_8h` | The fan's timer; the ESP32 counts down too and shows the fan off at the end |
| `sensor.…_fan_1_last_remote_button` | Last button pressed on that fan's real remote |

For the whole device: **Listen for remote**, **TX frequency**, **TX wake carrier**, **TX repeats**
(config) and **Log raw frames** (diagnostic).

**Dashboard card:** [homeassistant/dashboard-card.yaml](homeassistant/dashboard-card.yaml), standard
cards only: the fan tile, buttons for speeds 1–6 and Breeze, Light and the timers.

**How commands are sent:**

- **Speed and Breeze buttons turn the fan on by themselves**, so "on" and speed changes always send
  a speed. That's exact: it can't flip the wrong way.
- **Fan power is a toggle** on this remote (same code for on and off), so it's only sent to turn a
  fan **off**. If Home Assistant and the fan ever disagree, set a speed.
- **Light is a toggle too.** Home Assistant can't know whether the light is on, so it's a button,
  not a light entity. With smart bulbs in the fan, leave the fan's light power on and control the
  bulbs directly (the receiver's dimming makes smart bulbs flicker; the **Home** button gave steady
  full power on the tested fans).
- **A wall dimmer or fan control in front of the fan must stay on full.** It now only supplies
  power; off or low starves the receiver while Home Assistant still shows the fan running.
- Each command starts with a 300 ms wake-up carrier, because the fan's receiver dozes when idle and
  otherwise misses the first press (the real remote does too).

The ESP32 never transmits at boot; restarting it doesn't change any fan.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Chip ID: 0xFF0F` / `0x0000` / `0xFFFF` at boot | SPI wiring: check MISO, MOSI, SCK and CSN (pins 4–7) |
| Nothing logged when pressing the remote | Check GDO2 (pin 8 → GPIO33) and the antenna; move closer |
| Remote heard, but the fan ignores Home Assistant | Check GDO0 (pin 3 → GPIO32). Don't add `gdo0_pin:` to `cc1101:` (single-pin mode sent no data in testing) |
| Fan reacts only to every second command | Its receiver dozes: raise **TX wake carrier** (e.g. 500 ms) |
| The real remote got unreliable after installing this | The ESP32 is too close to the fan; move it a few metres away, or turn **Listen for remote** off |
| Both fans react to everything | Both are on the same remote ID; pair one to switch 1 (step 3) |
| Home Assistant shows the fan on but it's off | Someone used the wall switch, or a command was missed. Set a speed, then turn it off |
| `Other remote: id …` | A remote whose ID isn't in `fans.yaml` (or a neighbour's); see step 5 |

## Security

There's no rolling code or encryption, and on the tested remotes every remote on switch 0 sends the
same ID (likewise on 1). **Anyone within radio range with a similar setup can control your fans**,
and this repo shows how. That was already true of the original remote; this project doesn't make
it worse, but it's worth knowing. Don't use it for anything where an unexpected on/off matters.

## For AI agents

If you're an AI agent helping someone set this up, read [AGENTS.md](AGENTS.md) first.

## Repo layout

| Path | What |
|---|---|
| `esphome/fans.yaml` | The config you flash: device name and your list of fans |
| `esphome/fan.yaml` | One fan (included once per fan) |
| `esphome/harbor-fans.yaml` | The shared part: radio, transmitter, receiver |
| `esphome/secrets.yaml.template` | Copy to `secrets.yaml` and fill in |
| `homeassistant/dashboard-card.yaml` | Dashboard card |
| `docs/PROTOCOL.md` | The signal, the button codes, mapping another remote |
| `docs/LOG.md` | Build log: how it was worked out, mistakes included |
| `tools/decode_frames.py` | Decodes **Log raw frames** output into IDs and buttons |

## License

MIT. See [LICENSE](LICENSE).
