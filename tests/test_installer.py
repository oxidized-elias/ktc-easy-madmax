"""Exercise installer choices in a temporary config tree without printer services."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def run_installer(self, directory, answers):
        script = '''
source "$1/install.sh"
CONFIG_PATH="$2"
preflight_checks() { :; }
install_requirements() { :; }
link_extension() { :; }
restart_klipper() { touch "$CONFIG_PATH/restarted"; }
main
'''
        return subprocess.run(['bash', '-c', script, 'test', str(ROOT), str(directory)],
                              input=answers, text=True, capture_output=True)

    def test_madmax_and_switch_back_preserve_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'toolchanger'
            result = self.run_installer(directory, '2\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            wrapper = config / 'readonly-configs/toolchanger-include.cfg'
            self.assertEqual(wrapper.resolve(), ROOT / 'examples/madmax/toolchanger-include.cfg')
            profile = config / 'readonly-configs/madmax.cfg'
            self.assertEqual(profile.resolve(), ROOT / 'examples/madmax/toolchanger.cfg')
            user = config / 'madmax-user.cfg'
            self.assertIn('params_madmax_calibrated: False', user.read_text())
            self.assertFalse((Path(directory) / 'restarted').exists())
            user.write_text('# measured user configuration\n')
            result = self.run_installer(directory, '2\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(user.read_text(), '# measured user configuration\n')
            result = self.run_installer(directory, '1\n1\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(wrapper.resolve(), ROOT / 'examples/easy-additions/user-configs/toolchanger-include.cfg')
            self.assertEqual(user.read_text(), '# measured user configuration\n')
            self.assertTrue((Path(directory) / 'restarted').exists())

    def test_stealthchanger_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_installer(directory, '1\n2\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            config = Path(directory) / 'toolchanger'
            self.assertEqual((config / 'readonly-configs/toolchanger-include.cfg').resolve(),
                             ROOT / 'examples/easy-additions/user-configs/toolchanger-include_scanner.cfg')
            self.assertFalse((config / 'madmax-user.cfg').exists())

    def test_invalid_choice_changes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_installer(directory, '3\n')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_madmax_include_order_and_targets(self):
        lines = (ROOT / 'examples/madmax/toolchanger-include.cfg').read_text().splitlines()
        includes = [line[9:-1] for line in lines if line.startswith('[include ')]
        self.assertEqual(includes[-3:], ['../toolchanger-config.cfg', 'madmax.cfg', '../madmax-user.cfg'])
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_installer(directory, '2\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            base = Path(directory) / 'toolchanger/readonly-configs'
            for name in includes:
                if '*' not in name:
                    self.assertTrue((base / name).is_file(), name)
