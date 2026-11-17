# Kalico compatibility

## Current API support

The native tool-probe path was checked against Kalico `main` commit
`991e1823e983a31d26b9264d2b6305fd64e3a09a` (2026-11-08), including its
mesh-based axis-twist compensation update. API detection selects this path when
Kalico provides `ProbeList`, `ProbingContext` and `PrinterProbe.run_probe`.
Current Klipper and older Kalico continue using the existing helper/session path.
This uses capabilities rather than a version string.

| Area | Implementation and checks |
| --- | --- |
| Named probes | Each `[tool_probe T0]` registers a native named probe `T0`; named probe commands and `LIST_PROBES` use Kalico's registry |
| Default probe | `tool_probe_endstop` routes the virtual endstop; the registry's default follows the selected native tool probe |
| Probing sessions | Native `ProbingContext` is forwarded through multi-probe and routed homing callbacks |
| Retry policies and nozzle scrubbing | Native `PrinterProbe` parses and executes the configured strategy, retries and scrubbing; no copied sampling loop replaces it |
| Axis-twist compensation | Native probing retains the current compensation implementation; the registry default has the selected probe's real name and identity |
| Detection during probing | The detector checks native multi-probe counts, including named probes other than the default |
| Probe switching | Switching away from a tool during its native probe session is rejected |
| Calibration consumers | The legacy session/parameter interface remains available for extras that still consume it |

## Configuration

Keep probing options on the actual per-tool probe sections:

```ini
[tool_probe T0]
pin: YOUR_VERIFIED_PROBE_PIN
tool: 0
z_offset: YOUR_CALIBRATED_OFFSET
samples: 3
samples_result: median
samples_tolerance: 0.02
samples_tolerance_retries: 3
# Current Kalico options, if your hardware needs them:
#retry_speed: 5
#bad_probe_strategy: retry
#bad_probe_retries: 6
#scrubbing_frequency: 0
#nozzle_scrubber_gcode:
#    YOUR_REVIEWED_SCRUB_SEQUENCE
```

The placeholders above require real values. Configure a native tool `detection_pin`
separately when using tool detection. Its logical polarity can differ from the
probe interpretation of the same physical contact.

The tool-probe router is the default probe unless explicitly configured otherwise.
For a separate default bed probe with additional named coupling probes, current
Kalico supports:

```ini
[tool_probe_endstop]
register_as_probe: False
```

In that mode the router remains named `tool_probe_endstop`; it does not replace
the separate default probe, its commands or its virtual endstop pin. Select the
intended device with native `PROBE=T0`, `PROBE=T1` or
`PROBE=tool_probe_endstop` arguments where the command supports them. The selected
head must physically match the named tool probe. Explicitly naming a probe does
not pick up its toolhead.

Use per-tool names when configuring or calibrating native compensation maps, for
example `T0` and `T1`, so that their saved maps match the actual devices. Selecting
a tool updates the registry default, while `probe:z_virtual_endstop` continues to
route through the tool-probe endstop when that router is the default. A consumer
that caches a named probe object deliberately keeps that named device; select the
right probe at the start of each operation and do not change tools while probing.

Avoid enabling a second legacy crash detector over native missing-tool monitoring
without reviewing its docking and probing behavior. The MadMax profile uses native
monitoring and disables automatic core restore moves because it restores axes in
its own clearance-aware order.

## Reproducing the checks

Install development dependencies in a suitable environment and point to a checkout
of the Kalico version being tested:

```sh
python -m pip install jinja2 pyserial cffi greenlet PyYAML
KALICO_SOURCE=/path/to/kalico KLIPPER_SOURCE=/path/to/klipper \
    python -m unittest discover -s tests -v
bash -n install.sh
```

The Kalico integration tests import the actual upstream probe, configuration,
G-code and compensation classes, with fake printer services and motion. They cover
registry/default routing, context-aware homing, native retry/scrubbing, compensation
identity, busy detection, errors, switching and legacy session consumers.
Without `KALICO_SOURCE`, these integration tests are explicitly skipped; macro and
installer tests still run.

The optional `KLIPPER_SOURCE` test checks imports, legacy API selection and probe
result conversion in an isolated interpreter. It was run against current Klipper
`29d4ec2d6d840ee839333306003a400da186d41d`. This does not establish full hardware
compatibility with every Klipper or Kalico release.

## Limits

These checks do not certify physical probing accuracy, live MCU communication,
endstop timing, heater behavior, emergency response, or every optional extension.
Manual rail and hardware-specific extras need separate validation. The work here
addresses the concrete current probing API changes used by MadMax and tool
selection; it does not claim that every Kalico feature or third-party probe backend
has been validated. Test the exact printer configuration before production use.
