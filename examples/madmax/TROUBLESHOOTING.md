# MadMax troubleshooting and maintenance

Use this with [the commissioning guide](COMMISSIONING.md) and
[MadMax's mechanical troubleshooting](https://github.com/zruncho3d/madmax/blob/main/TROUBLESHOOTING.md).
The profile is experimental. The repository's tests check macro behavior and
installer output; they do not validate wiring, contact reliability or collisions.

## Installation and include problems

**The installer never asks about MadMax.** Confirm you are executing this fork's
`install.sh`, not the original upstream checkout. Run `git remote -v` and
`git log -1 --oneline` inside the directory you are installing from. Update the
fork's `main` branch, then rerun the installer and select option 2.

**Klipper does not see the tool configs.** The wildcard is `tools/T*.cfg`. The
installer supplies `example_T0.cfg` and `example_T1.cfg` as examples, which are not
automatically loaded. Configure the hardware and rename the files when ready.
Keep each tool, extruder, probe and MCU section defined in one place.

**Duplicate sections or unexpected StealthChanger motion.** Keep one include for
`toolchanger/readonly-configs/toolchanger-include.cfg` in `printer.cfg`. When
migrating from the earlier manual MadMax instructions, remove the separate
MadMax profile and calibration includes. Check that the selected wrapper points
to `examples/madmax/toolchanger-include.cfg`. Its final includes must be the
MadMax profile and then the editable calibration file. Look for per-tool motion
macro overrides, which take precedence over shared toolchanger defaults.

**My measurements disappeared after selecting MadMax.** The installer does not
overwrite an existing `toolchanger/madmax-user.cfg`. Confirm the config directory
and file you edited. Older manual setups may have measurements in a different
file; merge them into the installed editable file. Coordinates stored in a
separate file have no effect unless that file is included in the active config.

**The installer did not restart Klipper.** That is intentional for MadMax. Review
the generated config, tool hardware and homing before a manual Klipper restart.
The calibration guard does not block ordinary homing or unrelated macros.

## Calibration guard messages

| Message | What to check |
| --- | --- |
| `calibrate all dock coordinates` | The named tool still has `params_madmax_calibrated: False`; measure and review its coordinates before changing it |
| `missing or out-of-range params_...` | Replace `None`, check absolute docking coordinates and axis limits; do not extend axis limits solely to silence the guard |
| `expected attach_y < close_y ...` | Check the front-dock geometry and the ordering of all Y positions, including per-tool overrides |
| `park_x and detach_x must differ ...` | Confirm both X measurements and positive path/travel speeds |
| `requires per-tool coupling probes` | Use the per-tool probe setup selected by the MadMax installer, including `tool_probe_endstop` |
| An error directing you to manual XY calibration | `TOOL_ALIGN_START`, `TOOL_ALIGN_TEST` and `TOOL_ALIGN_DONE` intentionally reject lift-out alignment commands |

An incoming tool's incomplete calibration blocks the entire normal change before
the current head is released. `UNSELECT_TOOL` validates the head being released.
After editing config values, restart Klipper so the configured tool parameters
are reloaded.

## Detection and initialization

**Failed to detect active tool at startup or homing.** Keep one configured head
seated on the carriage. Check that its contact is untriggered and every detached
head's contact is triggered. Inspect tool numbers, input inversion, pull-ups,
connectors, and the physical coupling contact surfaces. Do not change the motion
path until detection is reliable while stationary.

**The wrong head is detected after pickup.** Stop testing motion. Check the
`tool:` number in each probe section against `tool_number:` in its tool section.
Check the input associated with each head individually. A parked head that reads
untriggered can make detection ambiguous. The explicit
`START_TOOL_PROBE_CRASH_DETECTION T=...` call checks that the expected tool was
actually detected before the attached head leaves the dock.

**Probe triggers while the head appears seated.** Inspect screw/pin contact,
magnet seating, debris, cable load and coupling alignment. For repeatable probing,
the head must return to the same mechanically seated position. Raising crash
filter time can hide a bad connection rather than fix it.

**A crash response disabled motors and heaters.** Treat the attached-tool state
as unknown. Support any loose head, establish a mechanically safe position, and
inspect the cause before reinitializing or homing. Avoid immediately repeating
the failed toolchange. The bundled crash macro is a shutdown response, not an
automatic docking recovery procedure.

## Motion and docking problems

**The screws hit the edge of the slots.** Recheck dock height, head angle,
`attach_y` and `detach_x`. Confirm measurements were taken in docking coordinates
rather than with a print tool offset applied. Mechanical alignment is separate
from probe or inter-tool offset calibration.

**The empty carriage drags on a parked head while crossing X.** Increase the
measured empty-carriage clearance where appropriate and check magnets, tool plate
protrusions and umbilicals. The empty-carriage clearance is
`params_safe_shuttle_y`; the larger attached-head clearance is
`params_safe_toolhead_y`. Inspect both heads' envelopes before changing either.

**The attached head clips the other docked head.** Recheck
`params_safe_toolhead_y` and the complete swept envelope. The profile moves to
that Y before crossing X on dropoff. It cannot account for an unrelated homing,
purge, print-end or manual move that ignores dock clearance.

**Docking only works at one Z.** Check the mechanical arrangement. This profile
has no dock-Z alignment move. If docks are fixed to a frame while the gantry moves
in Z, XY-only motion cannot keep their entrance aligned at every height. Use an
appropriate dock mounting arrangement or design a separate supported motion
sequence; adding a guessed `park_z` does not change this profile's behavior.

**The head crosses the print too closely.** The profile does not automatically
hop Z. Arrange adequate clearance before toolchange travel and check restored
positions after applying inter-tool offsets. Review the slicer's toolchange
sequence and any custom macros that request a change.

**A toolchange pauses before picking up a head.** Pickup waits at `close_y` for
the target tool's existing heater target using M109. Check the target, heater
readings, heater configuration and Easy Install's temperature deadband. Set the
intended targets before requesting the change. Removing the wait can move thermal
stabilization pauses into the print and should be a deliberate custom behavior.

**The nozzle lands correctly but the colors are misaligned.** Revisit inter-tool
XYZ offsets. Dock coordinates determine retention and release; they do not align
printed features. Also check that the head seats repeatably after each pickup.

## Updating, switching and migrating

Before an update or configuration migration, back up `printer.cfg`,
`toolchanger-config.cfg`, the tool files and `madmax-user.cfg`. Record the working
commit with `git rev-parse HEAD`. Keep the clone's remote and Moonraker origin
pointing to this fork if you want MadMax updates.

Rerun `./install.sh` after updates that add Python extensions or change installed
symlinks. Select MadMax again to retain the MadMax include wrapper. The installer
preserves editable files, so new template options may need to be merged manually
into an existing calibration file.

To switch to StealthChanger, rerun the installer, select option 1 and choose its
probe arrangement. This changes the active include wrapper, while leaving
`madmax-user.cfg` available for a future switch back. It does not physically
convert the mechanism or validate your StealthChanger coordinates. Remove old
manual MadMax includes from `printer.cfg` before using the StealthChanger wrapper.

When importing an older MadMax configuration, carry across measured geometry,
hardware pins and calibration values deliberately. Do not copy its complete
`toolchanger.cfg`, homing override or offset-saving macros over the current files.
The current Easy Install uses a dedicated tool offset transform and newer APIs.
See [the upgrade notes](../../upgrade.md) when migrating an older Easy Install.

## Useful information when reporting results

Include the fork commit, Klipper version, printer/gantry arrangement, dock design,
toolhead design, and whether docks move with the gantry. Describe which stage
failed: initialization, approach, sideways engagement, magnetic separation,
verification, departure or position restoration.

Provide relevant console output and sanitized tool/profile settings, including
park/detach X, the four Y positions, speeds and probe polarity. Describe physical
contact states and whether the issue changes with temperature or cable position.
Record whether the failure happens in both directions or only for one head.

Do not include credentials, complete private printer backups or unrelated network
configuration. A passing dry macro test is useful evidence about software, but
physical docking reliability needs repeated observation on the actual machine.
