// A tool the verification system MAY choose for TS type-safety metrics.
// It is not a codified verdict — the runner decides per metric whether this is
// the right instrument and records why. Pure AST parse: reads, never executes,
// so it is safe to point at an untrusted clone.
//
// Counts, over a given scope, using the TypeScript compiler's own parser:
//   any      : `any` keyword type nodes (AnyKeyword)
//   as       : real cast nodes (AsExpression), excluding `as const`; import
//              aliases are NOT AsExpression, so they are correctly ignored
//   nonnull  : non-null assertion nodes (NonNullExpression)  e.g. foo!.bar
//   tsignore : @ts-ignore / @ts-expect-error directive comments
//
// Resolution of the `typescript` lib (first that works):
//   repo/node_modules/typescript  ->  $TS_LIB  ->  /tmp/tsverify/...  ->  'typescript'
const path = require('path'), fs = require('fs');
const repo = process.argv[2];
const scope = (process.argv[3] || 'api/src,web/src,shared/src').split(',');
const includeTests = process.argv.includes('--include-tests');

function loadTs() {
  const tries = [
    path.join(repo, 'node_modules', 'typescript'),
    process.env.TS_LIB,
    '/tmp/tsverify/node_modules/typescript',
    'typescript',
  ].filter(Boolean);
  for (const t of tries) { try { return require(t); } catch (e) {} }
  throw new Error('typescript not found; set TS_LIB');
}
const ts = loadTs();

const isTest = (f) => /(__tests__|__mocks__|\.test\.|\.spec\.|[\\/]tests[\\/]|[\\/]e2e[\\/])/.test(f);
const files = [];
for (const s of scope) {
  const root = path.join(repo, s);
  if (!fs.existsSync(root)) continue;
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) { if (e.name === 'node_modules' || e.name === 'dist') continue; walk(p); }
      else if (/\.tsx?$/.test(e.name) && (includeTests || !isTest(p))) files.push(p);
    }
  })(root);
}

const c = { any: 0, as: 0, nonnull: 0, tsignore: 0 };
for (const f of files) {
  const code = fs.readFileSync(f, 'utf8');
  const src = ts.createSourceFile(f, code, ts.ScriptTarget.Latest, true,
    f.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  c.tsignore += (code.match(/@ts-(ignore|expect-error)/g) || []).length;
  (function visit(n) {
    if (n.kind === ts.SyntaxKind.AnyKeyword) c.any++;
    else if (ts.isAsExpression(n)) {
      const t = n.type;
      const isConst = t && ts.isTypeReferenceNode(t) && t.typeName && t.typeName.escapedText === 'const';
      if (!isConst) c.as++;
    } else if (ts.isNonNullExpression(n)) c.nonnull++;
    ts.forEachChild(n, visit);
  })(src);
}

console.log(JSON.stringify({
  tool: 'typescript-ast',
  ts_version: ts.version,
  scope, include_tests: includeTests,
  files: files.length,
  counts: c,
  total: c.any + c.as + c.nonnull,
}));
