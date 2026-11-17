# MadMax XY docking (experimental)

This profile adapts [MadMax's documented side/keyslot docking sequence](https://github.com/zruncho3d/madmax/blob/main/CONFIGURATION.md)
and [r2pdx's Micron example](https://github.com/zruncho3d/madmax/blob/main/Configs/r2pdx_config-micron-2025-12-21/klipper-toolchanger/toolchanger.cfg)
to this repository's current toolchanger API. Source inspected at MadMax commit
`277a63cbb696f937fbf9d883a8d8c46a658cd6d9`.
No new Python extension is required. This is a starting point for hardware testing,
not a claim of printer-tested support.

## Install

1. Clone this fork on the printer and run `./install.sh` from that checkout.
   Select **2. MadMax** at the toolchanger prompt. The installer selects per-tool
   Maxwell coupling probes, links the MadMax profile, and creates a user-owned
   `toolchanger/madmax-user.cfg` without overwriting an existing one. A shuttle
   scanner without coupling detection is not supported by this initial profile.
   Klipper is not automatically restarted for MadMax; complete configuration first.
2. Configure real toolboards, extruders, fans, and `[tool_probe T0]` / `[tool_probe T1]`
   sections using the Easy Install examples. Replace every sample pin and CAN UUID.
   Test contacts: attached and seated must be untriggered, detached or lifted must
   be triggered. Do not configure the same pin twice for probe and detection.
3. Add just this include to `printer.cfg`:

   ```ini
   [include toolchanger/readonly-configs/toolchanger-include.cfg]
   ```

   The installer-selected include loads the shared config, ordinary user overrides,
   MadMax profile, and finally `madmax-user.cfg` in that order. If migrating from
   manual setup, remove the separate `toolchanger/madmax.cfg` and
   `toolchanger/madmax-user.cfg` includes from `printer.cfg`; keep your calibration
   file. Do not edit files in `readonly-configs`. To switch back to StealthChanger,
   rerun the installer and select option 1; the MadMax calibration file is preserved
   but no longer included.
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
clearance ordering, both dock sides, restoration, and calibration guards. Installer
tests use temporary config trees to check profile selection, include order,
calibration preservation, and switching back to StealthChanger. They do not
simulate Klipper motion planning, probe hardware or physical collisions.
Use this fork's URL and branch in Moonraker's update manager to retain MadMax updates.

## Detailed guides

- [Installation, parameters, and commissioning](COMMISSIONING.md): supported hardware,
  installed files, coordinate worksheet, staged docking tests, and first prints.
- [Troubleshooting and maintenance](TROUBLESHOOTING.md): detection faults, guard
  messages, temperature waits, migration, and reporting hardware results.
- [Per-tool probing reference](../../tool_probe.md) and
  [offset calibration reference](../../tools_calibrate.md) describe the underlying
  extension APIs used by this profile.
