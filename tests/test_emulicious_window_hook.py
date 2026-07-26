"""Tests for tools/emulicious_window_hook.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from tools.emulicious_window_hook import WINDOW_SETTINGS, is_launch, rewrite

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools',
                      'emulicious_window_hook.py')

INI = """SomeOtherKey=keepme
WindowEmuliciousX=1234
WindowEmuliciousY=999
WindowDebuggerX=4000
WindowDebuggerY=3000
WindowDebuggerOpen=true
TrailingKey=alsokeep
"""


class LaunchDetectionTests(unittest.TestCase):
    def test_detects_bash_java_jar(self):
        self.assertTrue(is_launch(
            r'java -jar C:\Tools\Emulicious\Emulicious.jar build/nuke-raider.gb'))

    def test_detects_powershell_start_process(self):
        self.assertTrue(is_launch(
            'Start-Process -FilePath "java" -ArgumentList "-jar",'
            ' "C:\\Tools\\Emulicious\\Emulicious.jar"'))

    def test_ignores_unrelated_command(self):
        self.assertFalse(is_launch('make clean'))

    def test_is_case_insensitive(self):
        self.assertTrue(is_launch('java -jar emulicious.JAR rom.gb'))


class RewriteTests(unittest.TestCase):
    def test_resets_all_window_keys(self):
        out = rewrite(INI)
        for key, value in WINDOW_SETTINGS.items():
            self.assertIn('%s=%s' % (key, value), out)

    def test_preserves_unrelated_keys(self):
        out = rewrite(INI)
        self.assertIn('SomeOtherKey=keepme', out)
        self.assertIn('TrailingKey=alsokeep', out)

    def test_does_not_add_missing_keys(self):
        out = rewrite('OnlyKey=1\n')
        self.assertEqual(out, 'OnlyKey=1\n')

    def test_is_idempotent(self):
        self.assertEqual(rewrite(rewrite(INI)), rewrite(INI))


class ScriptTests(unittest.TestCase):
    def _run(self, command, ini_path=None):
        env = dict(os.environ)
        env.pop('EMULICIOUS_INI', None)
        if ini_path:
            env['EMULICIOUS_INI'] = ini_path
        payload = json.dumps({'cwd': os.getcwd(), 'tool_name': 'Bash',
                              'tool_input': {'command': command}})
        return subprocess.run([sys.executable, SCRIPT], input=payload,
                              capture_output=True, text=True, env=env)

    def test_exits_zero_when_env_unset(self):
        self.assertEqual(self._run('java -jar Emulicious.jar rom.gb').returncode, 0)

    def test_exits_zero_when_ini_missing(self):
        self.assertEqual(
            self._run('java -jar Emulicious.jar rom.gb',
                      os.path.join(tempfile.mkdtemp(), 'nope.ini')).returncode, 0)

    def test_rewrites_the_ini_on_launch(self):
        path = os.path.join(tempfile.mkdtemp(), 'Emulicious.ini')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(INI)
        self.assertEqual(
            self._run('java -jar Emulicious.jar rom.gb', path).returncode, 0)
        with open(path, encoding='utf-8') as fh:
            self.assertIn('WindowEmuliciousX=100', fh.read())

    def test_leaves_ini_untouched_for_other_commands(self):
        path = os.path.join(tempfile.mkdtemp(), 'Emulicious.ini')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(INI)
        self._run('make clean', path)
        with open(path, encoding='utf-8') as fh:
            self.assertIn('WindowEmuliciousX=1234', fh.read())


if __name__ == '__main__':
    unittest.main()
