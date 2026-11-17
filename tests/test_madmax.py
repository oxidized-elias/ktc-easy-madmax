"""Render the shipped profile using Klipper's Jinja syntax, without hardware."""
import ast
import configparser
from pathlib import Path
import unittest

import jinja2


PROFILE = Path(__file__).resolve().parents[1] / 'examples/madmax/toolchanger.cfg'
CONFIG = configparser.RawConfigParser()
CONFIG.read(PROFILE)
ENV = jinja2.Environment(block_start_string='{%', block_end_string='%}',
                         variable_start_string='{', variable_end_string='}')


def fail(message):
    raise ValueError(message)


def make_tool(right=False):
    return dict(name='tool T1' if right else 'tool T0',
                tool_number=1 if right else 0, extruder='extruder1' if right else 'extruder',
                params_madmax_calibrated=True,
                params_park_x=170 if right else 3,
                params_detach_x=165 if right else 8,
                params_safe_toolhead_y=110, params_safe_shuttle_y=20,
                params_close_y=16, params_attach_y=2,
                params_fast_speed=6000, params_path_speed=600)


class MadMaxTests(unittest.TestCase):
    def setUp(self):
        self.tool = make_tool()
        self.printer = {
            'tool T0': self.tool, 'tool T1': make_tool(True),
            'tool_probe_endstop': {}, 'extruder': {'target': 210},
            'extruder1': {'target': 0},
            'configfile': {'config': {'stepper_x': {'position_max': '180'},
                                      'stepper_y': {'position_min': '-5', 'position_max': '180'}}},
        }

    def render(self, section, option='gcode', **context):
        return ENV.from_string(CONFIG[section][option]).render(
            printer=self.printer, action_raise_error=fail, **context)

    def check(self):
        return self.render('gcode_macro _MADMAX_CHECK', params={'TOOL': self.tool['name']})

    def moves(self, option, **context):
        output = self.render('toolchanger', option, tool=self.tool,
                             restore_position=context.get('restore_position', {}))
        return [line.strip() for line in output.splitlines()
                if line.strip().startswith('G0 ')]

    def test_all_templates_compile(self):
        for section in CONFIG.sections():
            for name, value in CONFIG[section].items():
                if name.endswith('gcode'):
                    ENV.from_string(value)

    def test_safe_defaults_block_changes(self):
        for name, value in CONFIG['toolchanger'].items():
            if name.startswith('params_'):
                self.tool[name] = ast.literal_eval(value)
        with self.assertRaisesRegex(ValueError, 'calibrate'):
            self.check()

    def test_both_sides_and_clearance_before_crossing(self):
        for right in (False, True):
            self.tool = make_tool(right)
            self.printer[self.tool['name']] = self.tool
            self.check()
            drop = self.moves('dropoff_gcode')
            self.assertEqual(drop[:2], ['G0 Y110 F6000',
                                       f'G0 X{self.tool["params_detach_x"]} F6000'])
            self.assertEqual(drop[-1], 'G0 Y20 F6000')
            pickup = self.moves('pickup_gcode')
            self.assertEqual(pickup[:2], ['G0 Y20 F6000',
                                          f'G0 X{self.tool["params_park_x"]} F6000'])
            self.assertEqual(pickup[-1], 'G0 Y110 F6000')
            self.assertFalse(any('Z' in move for move in drop + pickup))

    def test_restore_after_clearance(self):
        moves = self.moves('pickup_gcode', restore_position={'X': 80, 'Y': 90, 'Z': 15})
        self.assertEqual(moves[-4:], ['G0 Y110 F6000', 'G0 X80 F6000',
                                     'G0 Y90 F6000', 'G0 Z15 F6000'])

    def test_invalid_coordinates(self):
        for field, value in [('park_x', None), ('detach_x', 181),
                             ('attach_y', -6), ('close_y', 1),
                             ('safe_shuttle_y', 111), ('path_speed', 0),
                             ('detach_x', 3)]:
            with self.subTest(field=field, value=value):
                self.tool = make_tool()
                self.printer['tool T0'] = self.tool
                self.tool['params_' + field] = value
                with self.assertRaises(ValueError):
                    self.check()

    def test_requires_coupling_detection(self):
        del self.printer['tool_probe_endstop']
        with self.assertRaisesRegex(ValueError, 'per-tool coupling probes'):
            self.check()

    def test_both_tools_checked_before_motion(self):
        output = self.render('toolchanger', 'before_change_gcode', tool=self.tool,
                             dropoff_tool='tool T0', pickup_tool='tool T1')
        self.assertIn('_MADMAX_CHECK TOOL="tool T0"', output)
        self.assertIn('_MADMAX_CHECK TOOL="tool T1"', output)
        self.assertNotIn('G0 ', output)
        self.printer['tool T1']['params_madmax_calibrated'] = False
        with self.assertRaisesRegex(ValueError, 'calibrate'):
            self.render('gcode_macro _MADMAX_CHECK', params={'TOOL': 'tool T1'})
        self.render('toolchanger', 'before_change_gcode', tool={},
                    dropoff_tool=None, pickup_tool='tool T1')

    def test_detection_before_departure(self):
        output = self.render('toolchanger', 'pickup_gcode', tool=self.tool, restore_position={})
        self.assertLess(output.index('VERIFY_TOOL_DETECTED T=0'),
                        output.index('START_TOOL_PROBE_CRASH_DETECTION T=0'))
        self.assertLess(output.index('START_TOOL_PROBE_CRASH_DETECTION T=0'),
                        output.index('G0 Y110'))

    def test_alignment_helpers_disabled(self):
        for name in ('START', 'TEST', 'DONE'):
            with self.assertRaises(ValueError):
                self.render('gcode_macro TOOL_ALIGN_' + name)


if __name__ == '__main__':
    unittest.main()
