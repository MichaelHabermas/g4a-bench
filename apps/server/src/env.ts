import { config } from 'dotenv';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { findRepoRoot } from '@yardstick/core';

const root = findRepoRoot();
for (const f of ['.env.local', '.env']) {
  const p = join(root, f);
  if (existsSync(p)) config({ path: p });
}

export { root };
