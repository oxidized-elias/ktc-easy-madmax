# MadMax installation and commissioning

This guide covers the experimental profile in this repository. Mechanical assembly,
magnet selection, coupling wiring, and dock geometry remain defined by
[the MadMax project](https://github.com/zruncho3d/madmax). Start with its
[configuration guide](https://github.com/zruncho3d/madmax/blob/main/CONFIGURATION.md)
for the physical alignment procedure. This guide explains how those measurements
are used by Easy Install.

## Supported arrangement

The initial profile targets front-facing side/keyslot docks. The attached head
moves into the entrance in Y, slides sideways in X into the narrow keyslots, and
stays in the dock as the carriage retreats in Y. Pickup reverses that sequence.
There is no Z motion to lift a head out of its dock.

The profile assumes:

- Increasing Y moves away from the front docks.
- The dock and carriage remain vertically aligned at every Z where docking occurs.
  A fixed gantry or gantry-mounted docks can provide that alignment. Frame-mounted
  docks on a moving gantry need a separate Z-alignment solution.
- Each tool has working Maxwell coupling contacts configured as a `tool_probe`.
  A detached head reads triggered; exactly one attached, seated head reads
  untriggered. This is how the software identifies the active head.
- The existing printer homes and probes correctly, and runs a Klipper version
  compatible with this repository. The root README lists the version requirement.

MadMax has multiple dock and toolhead variants. This profile does not establish
compatibility with every variant, rear docks, or rotated docks. It does not use
motorized latches or liftbar control.

## Install the fork

From the printer's SSH terminal:

```sh
cd ~
git clone https://github.com/oxidized-elias/ktc-easy-madmax.git
cd ktc-easy-madmax
./install.sh
```

Select **2. MadMax**. This choice also selects per-tool probing; there is no
scanner-only option for this profile. The script still checks for Klipper and
installs Python requirements using Klipper's environment. Do not run it as root.

The installer creates or updates these files under `~/printer_data/config`:

| Path under `toolchanger/` | Ownership and purpose |
| --- | --- |
| `readonly-configs/toolchanger-include.cfg` | Symlink to the MadMax include wrapper selected by the installer |
| `readonly-configs/madmax.cfg` | Symlink to the repository's shared MadMax motion profile |
| Other files in `readonly-configs/` | Shared Easy Install homing, macros, detection and calibration configuration |
| `madmax-user.cfg` | Copied once; editable dock coordinates, speeds and calibration flags |
| `toolchanger-config.cfg` | Existing Easy Install editable overrides, preserved on reruns |
| `tools/example_T0.cfg`, `tools/example_T1.cfg` | Per-tool probe examples; existing files are preserved |

The script also symlinks Python extensions into Klipper's extras directory. It
uses the directory containing `install.sh`, so clone directory names can differ.
MadMax installation deliberately leaves Klipper running its current configuration
until you review the files and restart it manually. It does not edit `printer.cfg`.

Rename and adapt the tool examples to `T0.cfg` and `T1.cfg` when they are ready.
The include wildcard loads `T*.cfg`, not `example_T*.cfg`. If you already have tool
sections, merge the required fields into those sections instead of defining the
same tool, extruder or MCU twice. The example UUIDs, pins, heater settings and
motor parameters describe example hardware, not your printer.

Add one include to `printer.cfg`:

```ini
[include toolchanger/readonly-configs/toolchanger-include.cfg]
```

The wrapper loads shared configuration, tool files, `toolchanger-config.cfg`, the
MadMax motion profile, then `madmax-user.cfg`. The last file has the final values.
Do not add a second include for the MadMax profile or calibration file.

To track this fork in Moonraker, use the actual clone path:

```ini
[update_manager ktc-easy-madmax]
type: git_repo
channel: dev
path: ~/ktc-easy-madmax
origin: https://github.com/oxidized-elias/ktc-easy-madmax.git
managed_services: klipper
primary_branch: main
```

If you use another clone directory, change `path`. Replace an existing update
manager entry for the same checkout rather than managing it twice. Python files
newly added by an update need another installer run to create their symlinks.

## Configure detection before motion

For each head, keep a `[tool Tx]` section and matching `[tool_probe Tx]`. Tool
numbers must agree; T0 normally uses `extruder`, T1 uses `extruder1`. The part
cooling fan is also selected through the tool section.

Use your measured probe pin and required pull-up/inversion. Do not copy a `!` or
`^` prefix without checking what it means for your wiring. Configure the contact
pin through `tool_probe`; adding a second consumer for the same input can produce
pin conflicts.

With motion and heaters idle, verify the electrical states using the probe query
commands and `DETECT_ACTIVE_TOOL_PROBE`. Lift or remove a head only when it is
physically supported and the printer cannot move it. This test is about contacts,
not forcing a magnetic separation during motion.

| Physical state | Expected detection behavior |
| --- | --- |
| T0 seated, T1 docked | T0 is detected |
| T1 seated, T0 docked | T1 is detected |
| No head seated on carriage | No active tool is detected |
| Head lifted from the coupling | Its contact transitions to triggered |

Fix reversed polarity, intermittent wiring or ambiguous detection before homing.
Do not use `SET_ACTIVE_TOOL_PROBE` to conceal an electrical detection fault.
The profile requires the `tool_probe_endstop` object and uses its crash detector.
The bundled crash response disables motors and heaters; review that response
against your machine's mechanics before testing it.

## Review homing and the usable bed

The installer does not infer printer dimensions or dock clearances. The shared
homing override assumes rear Y homing and needs explicit sensorless/endstop
settings in `toolchanger-config.cfg`. A front-homing machine needs a sequence
that avoids sweeping an attached head across the parked heads.

Keep one configured tool attached for startup and initialization. For first
commissioning, use T0 consistently for Z homing, leveling and mesh generation.
If the coupling is the Z probe, the Z virtual endstop is `probe:z_virtual_endstop`.
A nozzle probe has zero nominal XY probe offset; set the actual Z offset by
calibration, not by copying a sample value.

Review mesh bounds, leveling probe points, homing positions, purge lines, brush
positions, parking moves, pause and print-end moves. All must avoid both docked
heads and the carriage's larger swept envelope. Use `Z_TILT_ADJUST` for an
appropriate Trident setup or `QUAD_GANTRY_LEVEL` for an appropriate four-motor
moving gantry. They are not interchangeable.

## Coordinate worksheet

Record measurements separately for each head before enabling its calibration flag.
All coordinates below are absolute docking coordinates in millimeters. Speeds are
millimeters per minute, so `600` means 10 mm/s, not 600 mm/s.

| Setting | Meaning | Where to set it |
| --- | --- | --- |
| `params_park_x` | X with the head fully retained by its dock | Each `[tool Tx]` |
| `params_detach_x` | X with screws aligned to the large keyslot openings | Each `[tool Tx]` |
| `params_attach_y` | Y at the dock entrance, where sideways engagement is possible | Shared or per tool |
| `params_close_y` | Y outside magnetic capture before careful approach | Shared or per tool |
| `params_safe_shuttle_y` | Y where the empty carriage can safely cross X | Shared or per tool |
| `params_safe_toolhead_y` | Y where an attached head can safely cross X | Shared or per tool |
| `params_path_speed` | Slow speed for engagement, release and magnetic separation | Shared or per tool |
| `params_fast_speed` | Travel speed outside the careful docking path | Shared or per tool |
| `params_madmax_calibrated` | Explicitly enables docking after measurements are reviewed | Each `[tool Tx]` |

Use `madmax-user.cfg` for these settings. Its initial coordinates are `None`, and
its calibration flags are `False`. This prevents sample measurements from becoming
unintended motion commands. Add matching sections for additional tools if used;
the installed editable template initially lists T0 and T1 only.

For a conventional left dock, `detach_x` is commonly greater than `park_x`; for a
right dock it is commonly smaller. The software accepts either direction. Measure
the keyslot opening and required clearance instead of assuming a fixed X distance.

Measure in docking mode with the correct tool already initialized:

```gcode
ENTER_DOCKING_MODE
; Perform deliberate, small manual positioning moves using your measured limits.
; Record the dock coordinates.
EXIT_DOCKING_MODE
```

Docking mode removes the tool offset transform. Normal print coordinates can differ
once inter-tool offsets are configured. These commands do not establish homing,
clearance or correct contact polarity. Do not perform unrelated print moves while
in docking mode.

The required Y ordering is:

```text
front / dock entrance                         back / print area
attach_y < close_y <= safe_shuttle_y <= safe_toolhead_y
```

This is a geometric assumption of the front-dock profile. Increasing a clearance
coordinate can still make it unsafe on a particular printer; test the entire
carriage, toolhead, umbilical and parked-head envelope.

The guard rejects unset or out-of-axis-range coordinates, equal park/detach X,
non-positive speeds, and the wrong Y ordering. It checks both tools before a
normal toolchange releases the currently attached one. The limits come from
`stepper_x` and `stepper_y`, with a default minimum of zero when no minimum is
configured. These checks cannot infer physical clearance, magnet force, dock
engagement or bed travel restrictions.

Remove per-tool `before_change_gcode`, `pickup_gcode` and `dropoff_gcode` overrides
unless you deliberately maintain a custom sequence; a per-tool override can bypass
the shared MadMax behavior.

## What a toolchange does

Dropoff first stops coupling crash detection, then moves the attached head to
`safe_toolhead_y`. Only after that clearance move does it cross X to `detach_x`.
It approaches `attach_y`, slides to `park_x` at path speed, separates the carriage
to `close_y` at path speed, and retreats to `safe_shuttle_y`.

Pickup moves the empty carriage to `safe_shuttle_y`, crosses X to `park_x`, and
approaches `close_y`. If the tool has an extruder, it waits for its current heater
target using Easy Install's M109 behavior. It then approaches `attach_y`, slides
to `detach_x`, checks the detected tool, and enables crash detection for that tool.
The attached head exits to `safe_toolhead_y`, then restores requested X, Y and Z
positions in that order.

No Z motion occurs during dock engagement or disengagement. Provide print
clearance before toolchange travel, for example with your slicer's Z hop. The
profile does not add a Z hop automatically. Inter-tool offsets can also affect
the requested restored Z, so validate print clearance after calibrating them.

## Staged commissioning

1. **Electrical checks:** verify each tool's detection states before moving near
   docks. Review the crash response and have a way to stop the printer.
2. **Homing:** with T0 seated and all heads clear, verify the reviewed homing
   sequence. Check probe accuracy and usable leveling/mesh points.
3. **Mechanical alignment:** follow MadMax's procedure to align dock height and
   the head's screws with the openings. Measure all coordinates at low speed.
4. **Enable one tool:** enter its measured values and set its calibration flag to
   `True`. Restart Klipper, initialize normally, then test `UNSELECT_TOOL` and
   pickup with `T0`. Keep the other tool's flag false until it is measured.
5. **Enable the second tool:** repeat its individual release and pickup tests.
   Then test T0-to-T1 and T1-to-T0 changes from a clear position.
6. **Repeated docking:** after individual tests succeed, use
   `TEST_TOOL_DOCKING RESTORE_AXIS=XYZ` for controlled docking tests. Watch for
   inconsistent seating, screw contact, magnetic drag and umbilical interference.
7. **Offsets:** calibrate nozzle Z and inter-tool XYZ offsets. Recheck motion
   clearance, then run a single-tool print before a two-tool calibration print.
8. **Operating conditions:** repeat checks at realistic chamber temperatures and
   with actual heater targets before relying on long multicolor prints.

Do not increase path speed to compensate for mechanical misalignment. Verify
reliability at low speed first, then increase travel and path speeds separately.
A passing software test does not qualify a dock mechanically.

## Probe and inter-tool offsets

Three kinds of calibration solve different problems:

| Calibration | Purpose |
| --- | --- |
| MadMax docking coordinates | Places screws, keyslots and magnets correctly |
| Tool probe Z offset | Places the nozzle correctly relative to probe triggering and the bed |
| Tool `gcode_x_offset`, `gcode_y_offset`, `gcode_z_offset` | Aligns printed features between tools |

Changing a nozzle may require probe and inter-tool calibration while leaving dock
coordinates unchanged. Moving a dock requires checking dock coordinates even if
printed features were previously aligned.

See [the current calibration reference](../../tools_calibrate.md) before using
`TOOL_LOCATE_SENSOR`, `TOOL_CALIBRATE_TOOL_OFFSET` or the bundled
`CALIBRATE_ALL_OFFSETS` macro. Those commands require a configured, reachable
calibration sensor. Configure its pin and the `_CALIBRATION_SWITCH` position before
calling them. A Nudge-style sensor can supply the hardware, but this installer
does not automatically configure that sensor or install third-party calibration
macros. Older MadMax configurations use APIs from older toolchanger versions;
merge the settings you need rather than replacing this fork's current macros.
