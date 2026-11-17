"""Exercise installation against temporary paths; no services or printer needed."""
from pathlib import Path
import subprocess
import os
import pty
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def run_install(self, directory, *options, answer=None):
        script = '''
source "$1/install.sh"
CONFIG_PATH="$2/config"
KLIPPER_PATH="$2/klipper"
preflight_checks() { :; }
check_download() { :; }
# Keep the marker path independent of function positional arguments.
restart_marker="$2/restarted"
restart_klipper() { touch "$restart_marker"; }
shift 2
main "$@"
'''
        command = ['bash', '-c', script, 'test', str(ROOT), str(directory), *options]
        if answer is None:
            return subprocess.run(command, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(command, stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            os.write(master, answer.encode())
            stdout, stderr = process.communicate(timeout=10)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        finally:
            os.close(master)
            os.close(slave)

    def test_interactive_profile_choice(self):
        for answer, madmax, status in [('1\n', False, 0), ('2\n', True, 0), ('3\n', False, 1)]:
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as directory:
                result = self.run_install(directory, answer=answer)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual((Path(directory) / 'config/toolchanger/madmax.cfg').exists(), madmax)
                if status:
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_madmax_install_and_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config/toolchanger'
            result = self.run_install(directory, '--madmax')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / 'madmax.cfg').resolve(), ROOT / 'examples/madmax/toolchanger.cfg')
            self.assertEqual((target / 'madmax-include.cfg').resolve(), ROOT / 'examples/madmax/madmax-include.cfg')
            user = target / 'madmax-user.cfg'
            self.assertIn('params_safe_toolhead_y: None', user.read_text())
            self.assertFalse((Path(directory) / 'restarted').exists())
            self.assertTrue((Path(directory) / 'klipper/klippy/extras/toolchanger.py').is_symlink())
            user.write_text('# measured settings\n')
            result = self.run_install(directory, '--madmax')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(user.read_text(), '# measured settings\n')
            for line in (target / 'madmax-include.cfg').read_text().splitlines():
                if line.startswith('[include '):
                    self.assertTrue((target / line[9:-1]).is_file())

    def test_extensions_only_does_not_install_profile(self):
        for options in ((), ('--extensions-only',)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.run_install(directory, *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((Path(directory) / 'config').exists())
                self.assertTrue((Path(directory) / 'restarted').exists())

    def test_help_and_invalid_options_do_not_mutate(self):
        for options, status in [(('--help',), 0), (('--invalid',), 1),
                                (('--madmax', '--extensions-only'), 1)]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.run_install(directory, *options)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_streamed_help_entrypoint(self):
        # The original wget | bash mode must still enter main, even without BASH_SOURCE.
        result = subprocess.run(['bash', '-s', '--', '--help'], input=(ROOT / 'install.sh').read_text(),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Usage:', result.stdout)
