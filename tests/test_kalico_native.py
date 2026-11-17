"""Optional integration tests using real Kalico probe/config classes and fake motion.

Set KALICO_SOURCE to a current Kalico checkout. No MCU or printer is required.
"""
import configparser
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('KALICO_SOURCE')


@unittest.skipUnless(SOURCE, 'Set KALICO_SOURCE for native Kalico integration tests')
class KalicoNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, SOURCE)
        from klippy import configfile
        from klippy.extras import probe
        import klippy.extras
        klippy.extras.__path__.append(str(ROOT / 'klipper/extras'))
        cls.config_class = configfile.ConfigWrapper
        cls.probe = probe
        cls.tool_module = importlib.import_module('klippy.extras.tool_probe')
        cls.endstop_module = importlib.import_module('klippy.extras.tool_probe_endstop')
        cls.blind_module = importlib.import_module('klippy.extras.probe_blind_button')

    def setUp(self):
        self.build_printer()

    def build_printer(self, named=False):
        from klippy.gcode import GCodeCommand
        self.mux = {}
        self.chips = {}
        self.events = {}
        self.objects = {}
        self.position = [10., 20., 5., 0.]
        self.scrubs = []
        self.outcomes = []
        self.compensated = []
        test = self

        class Gcode:
            is_printer_ready = False
            def register_command(self, *args, **kwargs): pass
            def register_mux_command(self, name, parameter, key, handler, **kwargs):
                test.assertNotIn((name, key), test.mux)
                test.mux[name, key] = handler
            def respond_info(self, *args): pass
            def respond_raw(self, *args): pass
            def create_gcode_command(self, name, line, params):
                return GCodeCommand(self, name, line, params, None, None)

        class Template:
            def __bool__(self): return True
            def create_template_context(self): return {}
            def run_gcode(self, *args): test.scrubs.append(args)
            def run_gcode_from_command(self, *args): pass

        class Pins:
            def allow_multi_use_pin(self, pin): pass
            def register_chip(self, name, chip):
                test.assertNotIn(name, test.chips)
                test.chips[name] = chip
            def lookup_pin(self, name, **kwargs): return {'chip': mcu}

        endstop = SimpleNamespace(
            get_mcu=lambda: mcu, add_stepper=lambda stepper: None,
            get_steppers=lambda: [], home_start=lambda *args: None,
            home_wait=lambda *args: None, query_endstop=lambda time: False)
        mcu = SimpleNamespace(setup_pin=lambda *args: endstop,
                              estimated_print_time=lambda time: time)
        toolhead = SimpleNamespace(get_position=lambda: self.position[:],
            get_status=lambda time: {'homed_axes': 'xyz'}, get_last_move_time=lambda: 0.,
            manual_move=lambda coords, speed: self.position.__setitem__(slice(None),
                [old if new is None else new for old, new in zip(self.position, coords)]),
            get_kinematics=lambda: SimpleNamespace(get_steppers=lambda: []))

        class Printer:
            command_error = RuntimeError
            config_error = RuntimeError
            def lookup_object(self, name, default=None): return test.objects.get(name, default)
            def add_object(self, name, obj):
                test.assertNotIn(name, test.objects)
                test.objects[name] = obj
            def get_reactor(self): return SimpleNamespace(monotonic=lambda: 0.)
            def register_event_handler(self, name, callback):
                test.events.setdefault(name, []).append(callback)
            def load_object(self, config, name):
                if name == 'tool_probe_endstop' and name not in test.objects:
                    obj = test.endstop_module.load_config(test.config('tool_probe_endstop'))
                    test.objects[name] = obj
                return test.objects[name]

        self.printer = Printer()
        self.objects.update(gcode=Gcode(), pins=Pins(), toolhead=toolhead,
            gcode_move=SimpleNamespace(), manual_probe=SimpleNamespace(verify_no_manual_probe=lambda: None),
            buttons=SimpleNamespace(register_buttons=lambda *args: None),
            gcode_macro=SimpleNamespace(load_template=lambda *args: Template()),
            axis_twist_compensation=SimpleNamespace(get_z_compensation_value=self.compensate))
        self.raw = configparser.RawConfigParser()
        self.raw.read_string('''[printer]
minimum_z_position: -10
[tool_probe_endstop]
[tool_probe T0]
tool: 0
pin: board:PA1
z_offset: -1
samples: 1
bad_probe_strategy: retry
bad_probe_retries: 2
scrubbing_frequency: 1
[tool_probe T1]
tool: 1
pin: board2:PA1
z_offset: -2
samples: 1
''')
        if named:
            self.raw.set('tool_probe_endstop', 'register_as_probe', 'False')
            self.objects['probe'] = SimpleNamespace(probe_name='bed', multi_probe_count=0)
            registry = self.probe.ProbeList.get_list(self.printer)
            registry.default_probe = ('bed', self.objects['probe'])
        self.access = {}
        self.t0 = self.tool_module.load_config_prefix(self.config('tool_probe T0'))
        self.t1 = self.tool_module.load_config_prefix(self.config('tool_probe T1'))
        self.router = self.objects['tool_probe_endstop']
        self.router.set_active_probe(self.t0)

    def config(self, section):
        return self.config_class(self.printer, self.raw, self.access, section)

    def command(self, **params):
        return self.objects['gcode'].create_gcode_command('PROBE', 'PROBE', params)

    def compensate(self, position, selected):
        self.compensated.append(selected.probe_name)
        return .25

    def test_registry_commands_and_routing(self):
        registry = self.probe.ProbeList.get_list(self.printer)
        self.assertIs(registry.get_default_probe(), self.t0.native)
        self.assertIs(registry.get_probe('T0'), self.t0.native)
        self.assertIs(registry.get_probe('T1'), self.t1.native)
        self.assertEqual(self.router.get_offsets(), (0., 0., -1.))
        self.router.set_active_probe(self.t1)
        self.assertEqual(self.router.get_offsets(), (0., 0., -2.))
        self.assertIs(self.objects['probe'], self.router)
        self.assertIs(self.chips['probe'], self.router)
        for key in (None, 'tool_probe_endstop', 'T0', 'T1'):
            self.assertIn(('PROBE', key), self.mux)
        self.mux['QUERY_PROBE', None](self.command())
        self.assertEqual(self.router.get_status(0.)['active_tool_number'], 1)

    def test_retry_scrubbing_and_compensation_use_native_kalico(self):
        outcomes = iter([False, True])
        def probing_move(pos, speed, gcmd):
            return [10., 20., 1.], next(outcomes)
        self.t0.mcu_probe.probing_move = probing_move
        result = self.router.run_probe(self.command())
        self.assertEqual(result, [10., 20., 1.25])
        self.assertEqual(self.compensated, ['T0', 'T0'])
        # One scrub following the rejected sample, with native ATTEMPT/RETRIES context.
        self.assertEqual(len(self.scrubs), 1)
        self.assertEqual(self.scrubs[0][1]['params']['ATTEMPT'], 1)
        self.assertEqual(self.router.multi_probe_count, 0)

    def test_context_sessions_blind_native_detection(self):
        context = self.probe.ProbingContext(gcmd=self.command())
        self.router.multi_probe_begin(context)
        self.assertEqual(self.router.multi_probe_count, 1)
        blind = self.blind_module.ProbeBlindButton(self.printer, lambda old, new: None)
        blind._on_connect()
        self.assertTrue(blind._session_busy())
        self.router.multi_probe_end(context)
        self.assertFalse(blind._session_busy())

    def test_virtual_endstop_routes_homing_callbacks(self):
        context = self.probe.ProbingContext(gcmd=self.command())
        rails = [SimpleNamespace(get_endstops=lambda: [(self.router.mcu_probe, 'z')])]
        state = SimpleNamespace(gcmd=context.gcmd)
        for callback in self.events['homing:home_rails_begin']:
            callback(state, rails)
        self.assertEqual(self.router.multi_probe_count, 1)
        for callback in self.events['homing:home_rails_end']:
            callback(state, rails)
        self.assertEqual(self.router.multi_probe_count, 0)

    def test_named_router_preserves_separate_default(self):
        self.build_printer(named=True)
        registry = self.probe.ProbeList.get_list(self.printer)
        self.assertIs(registry.get_default_probe(), self.objects['probe'])
        self.assertIs(registry.get_probe('tool_probe_endstop'), self.router)
        self.assertNotIn('probe', self.chips)
        self.assertNotIn(('PROBE', None), self.mux)
        context = self.probe.ProbingContext(gcmd=self.command())
        self.t0.native.multi_probe_begin(context)
        blind = self.blind_module.ProbeBlindButton(self.printer, lambda old, new: None)
        blind._on_connect()
        self.assertTrue(blind._session_busy())
        self.t0.native.multi_probe_end(context)
        self.assertFalse(blind._session_busy())

    def test_current_mesh_compensation_matches_selected_native_identity(self):
        from klippy.extras.axis_twist_compensation import AxisTwistCompensation
        compensation = AxisTwistCompensation.__new__(AxisTwistCompensation)
        compensation.probe_list = self.probe.ProbeList.get_list(self.printer)
        compensation.maps = {
            'T0': SimpleNamespace(probe=self.t0.native, mesh=SimpleNamespace(calc_z=lambda x, y: .3)),
            'T1': SimpleNamespace(probe=self.t1.native, mesh=SimpleNamespace(calc_z=lambda x, y: .6)),
        }
        self.assertEqual(compensation.get_z_compensation_value([10., 20., 1.]), .3)
        self.router.set_active_probe(self.t1)
        self.assertEqual(compensation.get_z_compensation_value([10., 20., 1.]), .6)
        self.assertEqual(compensation.get_z_compensation_value([10., 20., 1.], self.t1.native), .6)

    def test_switching_during_session_is_rejected(self):
        context = self.probe.ProbingContext(gcmd=self.command())
        self.router.multi_probe_begin(context)
        with self.assertRaisesRegex(RuntimeError, 'during a probe session'):
            self.router.set_active_probe(self.t1)
        self.assertIs(self.router.active_probe, self.t0)
        self.router.multi_probe_end(context)
        self.router.set_active_probe(self.t1)

    def test_default_probe_command_uses_current_native_probe(self):
        self.router.set_active_probe(self.t1)
        self.t1.mcu_probe.probing_move = lambda pos, speed, gcmd: ([10., 20., 2.], True)
        self.mux['PROBE', None](self.command())
        self.assertEqual(self.t1.native.last_z_result, 2.25)
        self.assertEqual(self.compensated, ['T1'])

    def test_legacy_session_and_parameter_consumers(self):
        params = self.router.get_probe_params(self.command(PROBE_SPEED='7', SAMPLES='2'))
        self.assertEqual(params['probe_speed'], 7.)
        self.assertEqual(params['samples'], 2)
        self.t0.mcu_probe.probing_move = lambda pos, speed, gcmd: ([10., 20., 1.], True)
        session = self.router.start_probe_session(self.command())
        session.run_probe(self.command())
        self.assertEqual(session.pull_probed_results(), [[10., 20., 1.25]])
        session.end_probe_session()
        self.assertEqual(session.pull_probed_results(), [])

    def test_native_probe_errors_propagate_and_sessions_close(self):
        def broken(pos, speed, gcmd): raise RuntimeError('probe failed')
        self.t0.mcu_probe.probing_move = broken
        with self.assertRaisesRegex(RuntimeError, 'probe failed'):
            self.router.run_probe(self.command())
        self.assertEqual(self.router.multi_probe_count, 0)
