"""Optional current Klipper smoke/regression check in an isolated interpreter."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('KLIPPER_SOURCE')


class KlipperCompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(SOURCE, 'Set KLIPPER_SOURCE for current Klipper smoke check')
    def test_legacy_api_selection_and_probe_result(self):
        script = '''
import sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1] + '/klippy')
import extras
extras.__path__.insert(0, sys.argv[2] + '/klipper/extras')
from extras import probe, tool_probe, tool_probe_endstop
from extras.kalico_compat.native_probe import has_native_probe_api
assert not has_native_probe_api(probe)
router = tool_probe_endstop.ToolProbeEndstop.__new__(tool_probe_endstop.ToolProbeEndstop)
router.active_probe = SimpleNamespace(get_offsets=lambda: (1., 2., 4.))
result = router.create_probe_result([10., 20., 3.])
assert tuple(result) == (11., 22., -1., 10., 20., 3.), result
'''
        result = subprocess.run([sys.executable, '-c', script, SOURCE, str(ROOT)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
