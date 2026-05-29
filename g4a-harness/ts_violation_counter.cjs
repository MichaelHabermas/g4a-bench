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
//   untyped_params : implicit-any diagnostics (TS7006, TS7010) when program
//              creation succeeds; else syntactic count of parameters missing
//              explicit type annotations (status: syntactic_fallback)
//
// Resolution of the `typescript` lib (first that works):
//   repo/node_modules/typescript  ->  $TS_LIB  ->  /tmp/tsverify/...  ->  'typescript'
const path = require('path'), fs = require('fs');
const repo = process.argv[2];
const scope = (process.argv[3] || 'api/src,web/src,shared/src').split(',');
const includeTests = process.argv.includes('--include-tests');

const UNTYPED_DIAG_CODES = new Set([7006, 7010, 7031, 7034]);

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

const c = { any: 0, as: 0, nonnull: 0, tsignore: 0, untyped_params: 0 };
let untypedMethod = 'syntactic_fallback';
let diagnosticCodes = [];

function countSyntacticUntyped() {
  let n = 0;
  for (const f of files) {
    const code = fs.readFileSync(f, 'utf8');
    const src = ts.createSourceFile(f, code, ts.ScriptTarget.Latest, true,
      f.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    (function visit(node) {
      if (ts.isParameter(node) && !node.type && !node.dotDotDotToken) {
        n++;
      }
      ts.forEachChild(node, visit);
    })(src);
  }
  return n;
}

function readJsonSafe(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

function mergeCompilerOptions(repoPath) {
  const base = {
    noImplicitAny: true,
    strict: true,
    skipLibCheck: true,
    noEmit: true,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  };
  const candidates = ['tsconfig.json', 'api/tsconfig.json', 'web/tsconfig.json', 'shared/tsconfig.json'];
  for (const rel of candidates) {
    const cfg = readJsonSafe(path.join(repoPath, rel));
    if (!cfg?.compilerOptions) continue;
    return { ...base, ...cfg.compilerOptions, noImplicitAny: true, noEmit: true };
  }
  return base;
}

function countDiagnosticUntyped() {
  const options = mergeCompilerOptions(repo);
  const host = {
    getCurrentDirectory: () => repo,
    getCanonicalFileName: (f) => f,
    useCaseSensitiveFileNames: () => true,
    getNewLine: () => '\n',
    fileExists: (f) => fs.existsSync(f),
    readFile: (f) => { try { return fs.readFileSync(f, 'utf8'); } catch { return undefined; } },
    directoryExists: (d) => { try { return fs.statSync(d).isDirectory(); } catch { return false; } },
    getDirectories: (d) => {
      try {
        return fs.readdirSync(d, { withFileTypes: true })
          .filter((e) => e.isDirectory() && e.name !== 'node_modules')
          .map((e) => e.name);
      } catch { return []; }
    },
  };
  const relFiles = files.map((f) => path.relative(repo, f).replace(/\\/g, '/'));
  const program = ts.createProgram(relFiles, options, ts.createCompilerHost(options, true));
  const diags = ts.getPreEmitDiagnostics(program);
  const codeCounts = {};
  let n = 0;
  for (const d of diags) {
    const code = d.code;
    if (!UNTYPED_DIAG_CODES.has(code)) continue;
    const file = d.file && path.resolve(repo, d.file.fileName);
    if (file && !files.some((f) => path.resolve(f) === file)) continue;
    codeCounts[code] = (codeCounts[code] || 0) + 1;
    n++;
  }
  diagnosticCodes = Object.entries(codeCounts).map(([code, count]) => ({ code: Number(code), count }));
  return n;
}

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

try {
  const diagCount = countDiagnosticUntyped();
  if (diagCount >= 0) {
    c.untyped_params = diagCount;
    untypedMethod = 'typescript-diagnostics';
  }
} catch {
  /* fall through to syntactic */
}

if (untypedMethod === 'syntactic_fallback') {
  c.untyped_params = countSyntacticUntyped();
}

console.log(JSON.stringify({
  tool: 'typescript-ast',
  ts_version: ts.version,
  scope, include_tests: includeTests,
  files: files.length,
  counts: c,
  total: c.any + c.as + c.nonnull,
  untyped_method: untypedMethod,
  diagnostic_codes: diagnosticCodes,
  untyped_status: untypedMethod === 'syntactic_fallback' ? 'syntactic_fallback' : 'diagnostics',
}));
