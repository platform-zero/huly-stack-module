'use strict';
// Preserve the native service command/image while suppressing credential values
// from stdout/stderr. Huly collaborator v0.7.423 logs config.Secret at startup.
const { spawn } = require('node:child_process');
const { StringDecoder } = require('node:string_decoder');
const secrets = new Set();
function protect(value) {
  if (typeof value !== 'string' || value.length < 8) return;
  secrets.add(value);
  secrets.add(JSON.stringify(value).slice(1, -1));
}
for (const [name, value] of Object.entries(process.env)) {
  if (/SECRET|PASSWORD|TOKEN|API_KEY/.test(name)) protect(value);
}
for (const match of (process.env.STORAGE_CONFIG || '').matchAll(/(?:accessKey|secretKey)=([^&;\s]+)/g)) {
  protect(match[1]);
  try { protect(decodeURIComponent(match[1])); } catch { /* Keep raw value protected. */ }
}
const needles = [...secrets].sort((a, b) => b.length - a.length);
function redact(text) {
  for (const value of needles) text = text.split(value).join('[REDACTED-CREDENTIAL]');
  return text;
}
function forward(input, output) {
  const decoder = new StringDecoder('utf8');
  let pending = '', suppress = false, waiting = false;
  function emit(text) {
    if (!output.write(text) && !waiting) {
      waiting = true; input.pause();
      output.once('drain', () => { waiting = false; input.resume(); });
    }
  }
  function consume(text, final = false) {
    pending += text;
    let end;
    while ((end = pending.indexOf('\n')) >= 0) {
      const line = pending.slice(0, end + 1); pending = pending.slice(end + 1);
      emit(suppress ? '[OVERSIZED-LOG-RECORD-SUPPRESSED]\n' : redact(line)); suppress = false;
    }
    // Never flush a partial credential or grow memory without bound.
    if (pending.length > 1024 * 1024) { pending = ''; suppress = true; }
    if (final && (pending || suppress)) {
      emit(suppress ? '[OVERSIZED-LOG-RECORD-SUPPRESSED]\n' : redact(pending)); pending = '';
    }
  }
  input.on('data', data => consume(decoder.write(data)));
  input.on('end', () => consume(decoder.end(), true));
}
const [command, ...args] = process.argv.slice(2);
if (!command) { console.error('Native service command required'); process.exit(2); }
const child = spawn(command, args, { stdio: ['inherit', 'pipe', 'pipe'], detached: true });
forward(child.stdout, process.stdout); forward(child.stderr, process.stderr);
for (const signal of ['SIGTERM', 'SIGINT', 'SIGHUP']) {
  process.on(signal, () => { try { process.kill(-child.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; } });
}
child.on('error', () => { console.error('Native service launch failed'); process.exitCode = 1; });
child.on('close', (code, signal) => { process.exitCode = code === null ? (signal === 'SIGTERM' ? 143 : 1) : code; });
