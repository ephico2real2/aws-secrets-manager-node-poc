#!/usr/bin/env node
// CloudFormation can only take inline Lambda code inside the template (ZipFile,
// at most 4096 characters). The source of truth is
// infra/rotation/elasticache-user-rotation.js, which the unit tests run; this
// copies it into infra/cloudformation.yaml.
//
//   node scripts/sync-rotation-lambda.js           update the template
//   node scripts/sync-rotation-lambda.js --check   fail if the template is out of date (CI)
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const srcPath = `${root}infra/rotation/elasticache-user-rotation.js`;
const tplPath = `${root}infra/cloudformation.yaml`;
const MARKER = 'ZipFile: | # synced from infra/rotation/elasticache-user-rotation.js';

const code = readFileSync(srcPath, 'utf8').trimEnd();
if (code.length > 4096) throw new Error(`rotation code is ${code.length} characters; inline ZipFile allows 4096`);

const lines = readFileSync(tplPath, 'utf8').split('\n');
const at = lines.findIndex((l) => l.trim() === MARKER);
if (at < 0) throw new Error(`marker not found in ${tplPath}: ${MARKER}`);
const indent = ' '.repeat(lines[at].indexOf('ZipFile') + 2);
let end = at + 1;
while (end < lines.length && (lines[end] === '' || lines[end].startsWith(indent))) end++;
while (end > at + 1 && lines[end - 1] === '') end--; // keep the blank line after the block

const block = code.split('\n').map((l) => (l ? indent + l : ''));
const next = [...lines.slice(0, at + 1), ...block, ...lines.slice(end)].join('\n');
const current = lines.join('\n');

if (process.argv.includes('--check')) {
  if (next !== current) {
    console.error('infra/cloudformation.yaml is out of date: run node scripts/sync-rotation-lambda.js');
    process.exit(1);
  }
  console.log(`rotation code in the template matches its source (${code.length}/4096 characters)`);
} else {
  writeFileSync(tplPath, next);
  console.log(`synced ${code.length} characters into infra/cloudformation.yaml`);
}
