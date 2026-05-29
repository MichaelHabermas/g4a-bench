#!/usr/bin/env node
/**
 * Clone all team repos for a benchmark run.
 * Usage: node scripts/yardstick-clone.mjs --cohort g4a-c5-2 --week 4 --run 20260527T182321Z-static-prototype [--install]
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  findRepoRoot,
  runDir,
  cloneAllForRun,
  buildClonePlan,
  syncAndIndexRun,
} from '@yardstick/core';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = findRepoRoot(join(__dirname, '..'));
for (const f of ['.env.local', '.env']) {
  const p = join(root, f);
  if (!existsSync(p)) continue;
  for (const line of readFileSync(p, 'utf8').split('\n')) {
    const m = /^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/.exec(line.trim());
    if (m && process.env[m[1]] === undefined) {
      process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  }
}

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

const cohort = arg('--cohort');
const week = Number(arg('--week'));
const runId = arg('--run');
const install = process.argv.includes('--install');

if (!cohort || !week || !runId) {
  console.error('Usage: node scripts/yardstick-clone.mjs --cohort COHORT --week N --run RUN_ID [--install]');
  process.exit(1);
}

const rd = runDir(cohort, week, runId, root);
const plan = buildClonePlan(rd, cohort, week, runId, root);
if (plan.warnings.length) {
  for (const w of plan.warnings) console.warn('warn:', w);
}

const manifest = cloneAllForRun(rd, cohort, week, runId, { install }, root);
console.log(JSON.stringify(manifest, null, 2));

const sync = syncAndIndexRun({ runDir: rd, cohort, week });
console.error(
  `sync: verify=${sync.typesafety_verify} judgment=${sync.typesafety_judgment} measurements=${sync.measurementCount}`,
);
