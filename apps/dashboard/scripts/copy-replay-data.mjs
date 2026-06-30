import { copyFileSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const replaySource = resolve(here, '../../../data/replay');
const replayTarget = resolve(here, '../public/data/replay');
const catalogSource = resolve(here, '../../../data/scenarios/catalog.json');
const catalogTarget = resolve(here, '../public/data/scenarios/catalog.json');

mkdirSync(replayTarget, { recursive: true });
mkdirSync(dirname(catalogTarget), { recursive: true });

for (const file of readdirSync(replaySource)) {
  if (file.endsWith('.jsonl')) {
    copyFileSync(resolve(replaySource, file), resolve(replayTarget, file));
  }
}

copyFileSync(catalogSource, catalogTarget);
