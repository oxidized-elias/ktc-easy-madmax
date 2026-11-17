# MadMax XY docking (experimental)

This profile adapts [MadMax's documented side/keyslot docking sequence](https://github.com/zruncho3d/madmax/blob/main/CONFIGURATION.md)
and [r2pdx's Micron example](https://github.com/zruncho3d/madmax/blob/main/Configs/r2pdx_config-micron-2025-12-21/klipper-toolchanger/toolchanger.cfg)
to this repository's current toolchanger API. Source inspected at MadMax commit
`277a63cbb696f937fbf9d883a8d8c46a658cd6d9`.
No new Python extension is required. This is a starting point for hardware testing,
not a claim of printer-tested support.

## Install

1. Clone this fork/branch on the printer, then run `./install.sh` **from that checkout**.
   The installer now links the checkout it was run from. Use the per-tool TAP option:
   MadMax's Maxwell coupling contacts serve as per-tool probes. A shuttle scanner
   without coupling detection is not supported by this initial profile.
2. Configure real toolboards, extruders, fans, and `[tool_probe T0]` / `[tool_probe T1]`
   sections using the Easy Install examples. Replace every sample pin and CAN UUID.
   Test contacts: attached and seated must be untriggered, detached or lifted must
   be triggered. Do not configure the same pin twice for probe and detection.
3. Copy this directory's `toolchanger.cfg` to
   `~/printer_data/config/toolchanger/madmax.cfg`. Add to `printer.cfg` in this order:

   ```ini
   [include toolchanger/readonly-configs/toolchanger-include.cfg]
   [include toolchanger/madmax.cfg]
   [include toolchanger/madmax-user.cfg]
   ```

   Create `madmax-user.cfg` using the template below. It is user-owned and is not
   overwritten by installation. The last two includes must follow Easy Install's
   overrides so the StealthChanger paths cannot replace the MadMax profile.
4. Review homing, mesh, leveling and print macros for your printer. Keep an attached
   tool for initialization. Homing must reach a safe Y before sweeping X past docks.
   The bundled homing macro assumes rear Y homing; front homing needs a custom
   sequence. Use `Z_TILT_ADJUST` on a Trident rather than copying the README's QGL.
   Remove per-tool pickup/dropoff/before-change overrides so these shared paths apply.

## Calibration

Follow [MadMax's dock calibration instructions](https://github.com/zruncho3d/madmax/blob/main/CONFIGURATION.md#calibrate-docking-positions).
Measure positions in docking coordinates (Easy Install's `ENTER_DOCKING_MODE` removes
tool offsets; `EXIT_DOCKING_MODE` restores them). Do not copy another printer's
coordinates. Keep all tools and the carriage clear of docks before homing.

```ini
# madmax-user.cfg -- replace None with measured numeric coordinates.
[toolchanger]
params_safe_toolhead_y: None
params_safe_shuttle_y: None
params_close_y: None
params_attach_y: None
params_fast_speed: 6000  # mm/min
params_path_speed: 600  # mm/min; start slowly

[tool T0]
params_park_x: None
params_detach_x: None
params_madmax_calibrated: False

[tool T1]
params_park_x: None
params_detach_x: None
params_madmax_calibrated: False
```

`park_x` aligns the docked head; `detach_x` aligns its screws with the large keyslot
openings. The two heads usually have opposite signs for `detach_x - park_x`.
`attach_y` aligns the dock entrance; `close_y` is outside magnetic capture range.
`safe_shuttle_y` permits empty-carriage X travel and `safe_toolhead_y` permits
attached-head X travel. This profile assumes front docks and increasing Y away
from them: `attach_y < close_y <= safe_shuttle_y <= safe_toolhead_y`.
Other dock orientations require different paths.

After measuring and checking each tool's full swept envelope, set its
`params_madmax_calibrated: True` and restart Klipper. The guard checks both heads
before a change and rejects unset/out-of-travel coordinates. It cannot establish
physical clearance from coordinates alone. Per-tool Y parameters can override
the shared values when the docks differ.

Docking is strictly XY; no park Z is used. Maintain print clearance before calling
tool changes (for example, a slicer Z hop). The carriage keeps its current Z until
it has left the dock and restored XY, then restores the requested Z. Frame-mounted
docks on a moving gantry require additional Z alignment and are outside this
profile's scope. Use gantry-mounted docks or a fixed gantry.

Test `UNSELECT_TOOL`, then `T0`, followed by the same for T1, slowly with the stop
button available. Test `TEST_TOOL_DOCKING RESTORE_AXIS=XYZ` and repeated T0/T1
switches only after those pass. Confirm detection rejects the wrong/missing tool
and crash detection works. The stock `TOOL_ALIGN_*` helpers are disabled because
they assume lift-out docking. Calibrate Z and inter-tool offsets using the current
Easy Install workflow; older MadMax offset macros target an older API.

## Development checks

```sh
python -m pip install jinja2
python -m unittest discover -s tests -v
bash -n install.sh
```

Tests render the actual config with Klipper's Jinja delimiters and exercise
clearance ordering, both dock sides, restoration, and calibration guards. They
do not simulate Klipper motion planning, probe hardware or physical collisions.
Use this fork's URL and branch in Moonraker's update manager; the upstream URL
in the original README would switch updates back to StealthChanger defaults.
