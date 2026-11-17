"""Use Kalico's named-probe/retry API without replacing its native helpers."""
from types import SimpleNamespace


def has_native_probe_api(probe):
    return (hasattr(probe, 'ProbeList') and hasattr(probe, 'ProbingContext')
            and hasattr(getattr(probe, 'PrinterProbe', None), 'run_probe'))


class NativeSession:
    """Adapt legacy extension callers to Kalico's native run_probe API."""
    def __init__(self, native, gcmd):
        self.native, self.gcmd = native, gcmd
        self.results = []

    def run_probe(self, gcmd):
        self.results.append(self.native.run_probe(gcmd))

    def pull_probed_results(self):
        results, self.results = self.results, []
        return results

    def end_probe_session(self):
        self.results = []


def build_tool_probe(config, probe):
    class NativeToolProbe:
        def __init__(self):
            self.tool = config.getint('tool')
            self.printer = config.get_printer()
            self.name = config.get_name()
            pin = config.get('pin')
            pins = self.printer.lookup_object('pins')
            pins.allow_multi_use_pin(pin.replace('^', '').replace('!', '').replace('~', ''))
            self.mcu_probe = probe.ProbeEndstopWrapper(config)
            # Named probes retain all native Kalico options, retries and scrubbing.
            self.native = probe.PrinterProbe(config, self.mcu_probe,
                                            register_as_probe=False)
            self.endstop = self.printer.load_object(config, 'tool_probe_endstop')
            self.endstop.add_probe(config, self)
            buttons = self.printer.load_object(config, 'buttons')
            buttons.register_buttons([pin], self._button_handler)

        def _button_handler(self, eventtime, triggered):
            self.endstop.note_probe_triggered(self, eventtime, triggered)

        def get_offsets(self):
            return self.native.get_offsets()

        def get_probe_params(self, gcmd=None):
            if gcmd is None:
                gcmd = self.printer.lookup_object('gcode').create_gcode_command('', '', {})
            native = self.native
            return {
                'probe_speed': gcmd.get_float('PROBE_SPEED', native.speed, above=0.),
                'lift_speed': native.get_lift_speed(gcmd),
                'samples': gcmd.get_int('SAMPLES', native.sample_count, minval=1),
                'sample_retract_dist': gcmd.get_float('SAMPLE_RETRACT_DIST', native.sample_retract_dist, above=0.),
                'samples_tolerance': gcmd.get_float('SAMPLES_TOLERANCE', native.samples_tolerance, minval=0.),
                'samples_tolerance_retries': gcmd.get_int('SAMPLES_TOLERANCE_RETRIES', native.samples_retries, minval=0),
                'samples_result': gcmd.get('SAMPLES_RESULT', native.samples_result),
            }

        def run_probe(self, gcmd, retry_session=None):
            return self.native.run_probe(gcmd, retry_session)

        def start_probe_session(self, gcmd):
            return NativeSession(self.native, gcmd)

    return NativeToolProbe()


def build_tool_endstop(config, probe, legacy_class, router_class):
    class NativeToolEndstop(legacy_class):
        def __init__(self):
            self.printer = config.get_printer()
            self.reactor = self.printer.get_reactor()
            self.name = config.get_name()
            self.probe_name = self.name
            self.is_default_probe = config.getboolean('register_as_probe', True)
            self.tool_probes = {}
            self.last_query = {}
            self.active_probe = None
            self.active_tool_number = -1
            self._active_session = None
            self.crash_detection_active = False
            self.crash_lasttime = 0.
            self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
            self.gcode = self.printer.lookup_object('gcode')
            self.mcu_probe = router_class(self.printer)
            # Legacy selection/status methods update these fields; actual probing
            # and parameter parsing stay entirely with the selected native probe.
            self.probe_offsets = SimpleNamespace(x_offset=0., y_offset=0., z_offset=0.)
            self.cmd_helper = SimpleNamespace(name=self.name, get_status=self._native_status)
            probe.ProbeList.get_list(self.printer).add_probe_object(self, config)
            pins = self.printer.lookup_object('pins')
            if self.is_default_probe:
                pins.register_chip('probe', self)
            pins.register_chip(self.probe_name, self)
            for command in ('PROBE', 'QUERY_PROBE', 'PROBE_CALIBRATE',
                            'PROBE_ACCURACY', 'Z_OFFSET_APPLY_PROBE'):
                def dispatch(gcmd, name=command):
                    self._ensure_active_probe(gcmd)
                    return getattr(self.active_probe.native, 'cmd_' + name)(gcmd)
                keys = (None, self.probe_name) if self.is_default_probe else (self.probe_name,)
                for key in keys:
                    self.gcode.register_mux_command(command, 'PROBE', key, dispatch,
                        desc=getattr(probe.PrinterProbe, 'cmd_' + command + '_help'))
            for command in ('SET_ACTIVE_TOOL_PROBE', 'DETECT_ACTIVE_TOOL_PROBE',
                            'START_TOOL_PROBE_CRASH_DETECTION', 'STOP_TOOL_PROBE_CRASH_DETECTION'):
                self.gcode.register_command(command, getattr(self, 'cmd_' + command),
                                            desc=getattr(self, 'cmd_' + command + '_help'))
            for event, method in (
                ('homing:homing_move_begin', '_handle_homing_move_begin'),
                ('homing:homing_move_end', '_handle_homing_move_end'),
                ('homing:home_rails_begin', '_handle_home_rails_begin'),
                ('homing:home_rails_end', '_handle_home_rails_end')):
                self.printer.register_event_handler(event,
                    lambda *args, method=method: getattr(probe.PrinterProbe, method)(self, *args))
            self.crash_mintime = config.getfloat('crash_mintime', .5, above=0.)
            self.crash_gcode = self.gcode_macro.load_template(config, 'crash_gcode', '')
            self.printer.register_event_handler('klippy:connect', self._handle_connect)

        def set_active_probe(self, tool_probe):
            if tool_probe is not self.active_probe and self.multi_probe_count:
                raise self.printer.command_error("Cannot switch tool probes during a probe session")
            result = super().set_active_probe(tool_probe)
            if self.is_default_probe:
                # Kalico compensation maps match both name and object identity.
                # Expose the actual selected native probe as the registry default,
                # while the virtual endstop pin and legacy 'probe' object stay routed.
                native = tool_probe.native if tool_probe else self
                probe.ProbeList.get_list(self.printer).default_probe = (native.probe_name, native)
            return result

        def setup_pin(self, pin_type, pin_params):
            return probe.PrinterProbe.setup_pin(self, pin_type, pin_params)

        @property
        def multi_probe_count(self):
            return self.active_probe.native.multi_probe_count if self.active_probe else 0

        def _native_status(self, eventtime):
            return dict(self.active_probe.native.get_status(eventtime)) if self.active_probe else {}

        def get_lift_speed(self, gcmd=None):
            self._ensure_active_probe(gcmd)
            return self.active_probe.native.get_lift_speed(gcmd)

        def run_probe(self, gcmd, retry_session=None):
            self._ensure_active_probe(gcmd)
            return self.active_probe.run_probe(gcmd, retry_session)

        def multi_probe_begin(self, context):
            self._ensure_active_probe(context.gcmd)
            return self.active_probe.native.multi_probe_begin(context)

        def multi_probe_end(self, context):
            self._ensure_active_probe(context.gcmd)
            return self.active_probe.native.multi_probe_end(context)

        def cancel_probe(self):
            if self.active_probe:
                self.active_probe.native.cancel_probe()

    return NativeToolEndstop()
