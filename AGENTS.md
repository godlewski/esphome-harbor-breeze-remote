# Instructions for AI agents

You're helping someone set up this bridge. The human-facing guide is [README.md](README.md); this
file tells you how to run it safely. The signal is described in [docs/PROTOCOL.md](docs/PROTOCOL.md),
and [docs/LOG.md](docs/LOG.md) shows the dead ends, so you don't repeat them.

## Ground rules

- **The person must physically do these themselves:** wire the radio, place the ESP32, press remote
  buttons, flip the remote's 0/1 switch, power-cycle a fan and press learn, and say what the fan
  actually did. Ask them, and wait for their answer. You can't see or hear the fan.
- **Never invent values.** Wi-Fi name and password come from the person. Generate `fans_api_key`
  (`openssl rand -base64 32`) and `fans_ap_password` (`openssl rand -hex 16`) yourself. A
  `remote_id` comes from the table in PROTOCOL.md or from an `Other remote: id …` log line, nothing else.
- **Never commit or print** `esphome/secrets.yaml`. It's gitignored. Don't paste the Wi-Fi password
  or the API key into chat output, issues or PRs. If the person wants the key for Home Assistant,
  put it on their clipboard or tell them where it is.
- **Ask before sending anything that changes a fan** (a speed, off, direction, Light). Tell them
  what's about to happen. Light and fan power are toggles, so a "test" flips the real state.
- **Check pins 1 and 2 (GND, VCC → 3V3) with them before first power-on.** 5 V on VCC kills the radio.
- **Don't add `gdo0_pin:` to the `cc1101:` block.** ESPHome's single-pin mode sent no data in testing.
- **Don't trust "it should work" for transmit.** If the fan ignores the ESP32, ask whether they have
  an RTL-SDR and compare on the air (PROTOCOL.md) before changing timings at random.

## Steps

1. **Check the remote.** Ask for the FCC ID on the remote. Proceed if it's `A25-TX012`. Otherwise
   explain that it's untested, and go to [mapping another remote](docs/PROTOCOL.md#mapping-another-remote)
   after step 7.
2. **Tools.** Make sure `uv` is installed (`uvx esphome version` works). On Linux, make sure the
   user is in the serial group (`uucp` on Arch, `dialout` on Debian/Ubuntu); adding them needs sudo
   and a re-login, so tell them.
3. **Wiring.** Walk them through README step 1, by the pin **numbers** printed on their CC1101.
   Have them check pins 1/2 (multimeter, or the listing's pinout) before power-on.
4. **Secrets.** In `esphome/`: `cp secrets.yaml.template secrets.yaml` and fill it in. Wi-Fi must be
   2.4 GHz.
5. **Fans.** Ask how many fans and what to call them. Edit `esphome/fans.yaml`: one `packages:` entry
   per fan, unique `fan_id` (letters, digits, `_`). With two fans, they must be paired to different
   switch positions (README step 3); ask whether that's done.
6. **Validate, then flash:** `uvx esphome config fans.yaml`, then `uvx esphome run fans.yaml
   --device <port> --no-logs` over USB the first time and `--device <ESP32 IP>` after that.
7. **Verify receive.** Run `uvx esphome logs fans.yaml --device <ESP32 IP>`. Expect
   `CC1101 found! Chip ID: 0x0014` at boot. Ask them to press Light on each remote and wait for
   `<fan name>: heard Light`. An `Other remote: id …` line means a `remote_id` needs that value.
8. **Verify send (ask first).** Tell them a speed command is coming, have them watch the fan, and
   send it from Home Assistant or the API. If it misses only the first time, raise **TX wake
   carrier**. If it never responds, see the README troubleshooting table.
9. **Place it** a few metres from any fan (not right next to one), then add it to Home Assistant
   (README step 7) and suggest a DHCP reservation. Offer the dashboard card.

## Reading the log

| Line | Meaning |
|---|---|
| `CC1101 found! Chip ID: 0x0014` | The ESP32 talks to the radio. `FF0F`/`0000`/`FFFF` = SPI wiring |
| `<fan>: heard <button>` | The real remote of that fan was heard; the entity follows it |
| `Other remote: id … button 0x…` | A valid frame with an ID not in `fans.yaml` |
| `<fan>: unknown button 0x…` | The ID matched but the button isn't in the table |
| `Sending <id> 0x…` | The ESP32 is transmitting a command |
| `[raw]: N: …` | **Log raw frames** is on: one frame's timings (µs, + = carrier on) |
| `Failed to enter TX state!` / `PLL lock failed` | The radio didn't switch to transmit; reset or check power |
