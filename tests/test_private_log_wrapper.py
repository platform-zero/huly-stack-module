#!/usr/bin/env python3
"""Synthetic native-process checks, not authenticated Huly acceptance."""
import os
import json
from pathlib import Path
import signal
import subprocess
import unittest

WRAPPER = Path(__file__).resolve().parents[1] / 'stack.config/huly/private-log-wrapper.cjs'

class Privacy(unittest.TestCase):
    def test_wrapper_is_declared_materialized_overlay(self):
        module=json.loads((WRAPPER.parents[2]/'stack.module.json').read_text())
        self.assertIn('stack.config/huly/private-log-wrapper.cjs',module['overlays'])
        runtime=(WRAPPER.parents[2]/'stack.runtime.yaml').read_text()
        self.assertIn('command: ["node", "/private-log-wrapper.cjs", "node", "bundle.js"]',runtime)
        self.assertIn('./configs/huly/private-log-wrapper.cjs:/private-log-wrapper.cjs:ro',runtime)

    def test_split_json_escaped_stdout_stderr_and_exit_code(self):
        secret = 'public-fixture-only-quote"slash\\unicode-π-12345678'
        code = '''const v=process.env.SECRET;
process.stdout.write('config.Secret='+v.slice(0,12));
setTimeout(()=>{process.stdout.write(v.slice(12)+'\\nretained ordinary record\\n');
process.stderr.write(JSON.stringify({Secret:v})+'\\n');process.exitCode=17;},20);'''
        r = subprocess.run(['node', str(WRAPPER), 'node', '-e', code],
                           env=dict(os.environ, SECRET=secret), capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 17)
        self.assertNotIn(secret, r.stdout+r.stderr)
        self.assertNotIn('public-fixture-only', r.stdout+r.stderr)
        self.assertIn('[REDACTED-CREDENTIAL]', r.stdout)
        self.assertIn('[REDACTED-CREDENTIAL]', r.stderr)
        self.assertIn('retained ordinary record', r.stdout)

    def test_oversized_unterminated_record_is_suppressed(self):
        code = "process.stdout.write('x'.repeat(1024*1024+65536)+process.env.SECRET+'\\nordinary\\n')"
        r = subprocess.run(['node', str(WRAPPER), 'node', '-e', code],
                           env=dict(os.environ, SECRET='public-fixture-only-secret-123'),
                           capture_output=True, text=True, timeout=5)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('public-fixture-only', r.stdout)
        self.assertIn('OVERSIZED-LOG-RECORD-SUPPRESSED', r.stdout)
        self.assertIn('ordinary', r.stdout)

    def test_shutdown_forwards_to_native_process_group(self):
        p = subprocess.Popen(['node', str(WRAPPER), 'node', '-e',
                              "console.log('ready');setInterval(()=>{},1000)"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(), 'ready')
            p.send_signal(signal.SIGTERM)
            p.communicate(timeout=4)
            self.assertEqual(p.returncode, 143)
        finally:
            if p.poll() is None: p.kill(); p.communicate()

if __name__ == '__main__': unittest.main()
