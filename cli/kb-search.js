#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

// ─── Config ───────────────────────────────────────────────────────────────────

const KB_PATH = process.env.KB_PATH || '.obsidian';
const WIKI_DIR = path.join(KB_PATH, 'wiki');
const SEARCH_DIR = path.join(KB_PATH, '_search');
const INDEX_FILE = path.join(SEARCH_DIR, 'index.json');

// ─── Frontmatter parser ───────────────────────────────────────────────────────

function parseFrontmatter(content) {
  const meta = {};
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return { meta, body: content };

  const body = content.slice(match[0].length).trim();
  const lines = match[1].split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].replace(/\r$/, '');
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (!kv) { i++; continue; }

    const key = kv[1];
    const raw = kv[2].trim();

    if (raw.startsWith('[')) {
      // Inline array: [a, b, c]
      const inner = raw.replace(/^\[|\]$/g, '');
      meta[key] = inner ? inner.split(',').map((s) => s.trim()).filter(Boolean) : [];
      i++;
    } else if (raw === '') {
      // Multi-line list
      const items = [];
      i++;
      while (i < lines.length && lines[i].match(/^\s+-\s+/)) {
        items.push(lines[i].replace(/^\s+-\s+/, '').trim());
        i++;
      }
      meta[key] = items;
    } else {
      meta[key] = raw;
      i++;
    }
  }

  return { meta, body };
}

// ─── Tokenizer ────────────────────────────────────────────────────────────────

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 1 || /^\d$/.test(t));
}

// ─── TF-IDF builder ───────────────────────────────────────────────────────────

function buildDoc(file, content) {
  const { meta, body } = parseFrontmatter(content);

  const titleTokens = tokenize(meta.title || '');
  const tagTokens = (meta.tags || []).flatMap(tokenize);
  const bodyTokens = tokenize(body);

  // Weighted token frequency: title x3, tags x2, body x1
  const tf = {};
  for (const t of titleTokens) tf[t] = (tf[t] || 0) + 3;
  for (const t of tagTokens)   tf[t] = (tf[t] || 0) + 2;
  for (const t of bodyTokens)  tf[t] = (tf[t] || 0) + 1;

  const excerpt = body
    .replace(/^#+\s+.*/gm, '')   // strip headings
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 200);

  return {
    file,
    title: meta.title || file,
    type: meta.type || '',
    tags: meta.tags || [],
    status: meta.status || '',
    related: meta.related || [],
    excerpt,
    tf,
  };
}

// ─── Index operations ─────────────────────────────────────────────────────────

function buildIndex() {
  if (!fs.existsSync(WIKI_DIR)) {
    console.error(`Wiki directory not found: ${WIKI_DIR}`);
    process.exit(1);
  }

  const files = fs.readdirSync(WIKI_DIR).filter(
    (f) => f.endsWith('.md') && !f.startsWith('_')
  );

  const docs = files.map((file) => {
    const content = fs.readFileSync(path.join(WIKI_DIR, file), 'utf-8');
    return buildDoc(file, content);
  });

  // Compute IDF: log(N / df) for each term
  const N = docs.length;
  const df = {};
  for (const doc of docs) {
    for (const term of Object.keys(doc.tf)) {
      df[term] = (df[term] || 0) + 1;
    }
  }
  const idf = {};
  for (const [term, count] of Object.entries(df)) {
    idf[term] = Math.log((N + 1) / (count + 1)) + 1;
  }

  const index = { built: new Date().toISOString(), docs, idf };

  fs.mkdirSync(SEARCH_DIR, { recursive: true });
  writeIndex(index);

  // Keep the lean index in lockstep with the full index. A missing or stale
  // lean index would force /prime to fall back to the heavy wiki scan, which
  // defeats the whole point of shipping the lean companion. Failures here
  // shouldn't break the main index build — warn and continue.
  try {
    const { buildLeanIndex } = require('./lean-index.js');
    buildLeanIndex();
  } catch (e) {
    console.warn(`Warning: lean-index build failed: ${e.message}`);
  }

  return index;
}

// Atomic index write: write to a sibling .tmp file, then rename. rename(2)
// is atomic on POSIX and on Windows (when target is on the same volume), so
// concurrent readers always see either the old or new index — never a
// partially-written file. Prevents JSON parse failures when two CLI runs
// race to rebuild the index.
function writeIndex(index) {
  const tmp = INDEX_FILE + '.tmp';
  try {
    fs.writeFileSync(tmp, JSON.stringify(index, null, 2), 'utf-8');
    fs.renameSync(tmp, INDEX_FILE);
  } catch (e) {
    // On failure, clean up the tmp file so it doesn't linger and confuse
    // future runs or our own hardening tests.
    try { fs.unlinkSync(tmp); } catch (_) {}
    throw e;
  }
}

function loadIndex() {
  // Auto-rebuild if index is missing or stale
  if (fs.existsSync(INDEX_FILE) && fs.existsSync(WIKI_DIR)) {
    const indexMtime = fs.statSync(INDEX_FILE).mtimeMs;
    const wikiFiles = fs.readdirSync(WIKI_DIR).filter(
      (f) => f.endsWith('.md') && !f.startsWith('_')
    );
    const anyNewer = wikiFiles.some(
      (f) => fs.statSync(path.join(WIKI_DIR, f)).mtimeMs > indexMtime
    );
    let index;
    try {
      index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf-8'));
    } catch (e) {
      // Corrupted index (truncated JSON from a crashed write, manual edit,
      // disk full, etc). Delete it before rebuilding — previously a corrupt
      // file would silently loop through buildIndex() which overwrites it,
      // but only if SEARCH_DIR existed and writes succeeded. Explicit delete
      // makes the recovery behavior obvious and guards against repeat corruption.
      try { fs.unlinkSync(INDEX_FILE); } catch (_) {}
      return buildIndex();
    }
    if (anyNewer || wikiFiles.length !== index.docs.length) return buildIndex();
    return index;
  }
  return buildIndex();
}

// ─── Search ───────────────────────────────────────────────────────────────────

function search(query, opts = {}) {
  const index = loadIndex();
  const queryTerms = tokenize(query);

  if (queryTerms.length === 0) {
    return { query, results: [], total: 0 };
  }

  const scored = index.docs
    .filter((doc) => {
      if (opts.type && doc.type !== opts.type) return false;
      if (opts.tag && !doc.tags.includes(opts.tag)) return false;
      return true;
    })
    .map((doc) => {
      let score = 0;
      for (const term of queryTerms) {
        const tf = doc.tf[term] || 0;
        const idf = index.idf[term] || 0;
        score += tf * idf;
      }
      return { ...doc, file: 'wiki/' + doc.file, score };
    })
    .filter((doc) => doc.score > 0)
    .sort((a, b) => b.score - a.score);

  // Strip internal tf field from output
  const results = scored.map(({ tf: _tf, ...rest }) => rest);

  return { query, results, total: results.length };
}

// ─── Stats ────────────────────────────────────────────────────────────────────

function stats() {
  const index = loadIndex();
  const docs = index.docs;

  const byType = {};
  const byStatus = {};
  const tagCount = {};

  for (const doc of docs) {
    byType[doc.type || 'unknown'] = (byType[doc.type || 'unknown'] || 0) + 1;
    byStatus[doc.status || 'unknown'] = (byStatus[doc.status || 'unknown'] || 0) + 1;
    for (const tag of doc.tags) {
      tagCount[tag] = (tagCount[tag] || 0) + 1;
    }
  }

  const topTags = Object.entries(tagCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20);

  const lines = [
    `Total articles: ${docs.length}`,
    '',
    'By type:',
    ...Object.entries(byType)
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => `  ${t}: ${n}`),
    '',
    'By status:',
    ...Object.entries(byStatus)
      .sort((a, b) => b[1] - a[1])
      .map(([s, n]) => `  ${s}: ${n}`),
    '',
    'Top tags:',
    ...topTags.map(([tag, n]) => `  ${tag}: ${n}`),
  ];

  console.log(lines.join('\n'));
}

// ─── Help text ────────────────────────────────────────────────────────────────

const HELP_TEXT = [
  'Usage: kb-search <command> [args] [flags]',
  '',
  'Commands:',
  '  index                 Build (or rebuild) the search index (and lean index)',
  '  search <query>        Search the wiki; prints JSON results',
  '  stats                 Print KB statistics (article counts, tags)',
  '  lean                  Print the lean (metadata-only) index as JSON',
  '',
  'Flags (for `search`):',
  '  --type=<T>            Restrict to articles with frontmatter type=T',
  '  --tag=<T>             Restrict to articles tagged with T',
  '  --limit=<N>           Return at most N results (positive integer)',
  '',
  'Global flags:',
  '  --help, -h            Show this help message',
  '',
  'Environment:',
  '  KB_PATH               Path to the KB root (default: .obsidian)',
].join('\n');

// ─── CLI entry ────────────────────────────────────────────────────────────────

// Only run the CLI block when invoked directly as a script. This keeps
// `require('./kb-search.js')` side-effect-free so other CLI entry points
// (e.g. cli/index.js) can import HELP_TEXT without triggering the switch
// below. Matches the pattern used by init.js and update.js.
if (require.main === module) {
  const [, , command, ...rest] = process.argv;

  // Top-level --help / -h handler. Handled before the command switch so
  // `kb-search --help` works without needing a subcommand.
  if (command === '--help' || command === '-h' || command === undefined) {
    console.log(HELP_TEXT);
    process.exit(command === undefined ? 1 : 0);
  }

  switch (command) {
    case 'index': {
      const idx = buildIndex();
      console.log(`Indexed ${idx.docs.length} articles → ${INDEX_FILE}`);
      break;
    }

    case 'search': {
      // Help requested within `search` subcommand
      if (rest.includes('--help') || rest.includes('-h')) {
        console.log(HELP_TEXT);
        process.exit(0);
      }

      const query = rest.find((a) => !a.startsWith('--')) || '';
      const typeArg = rest.find((a) => a.startsWith('--type'));
      const tagArg  = rest.find((a) => a.startsWith('--tag'));
      const limitArg = rest.find((a) => a.startsWith('--limit'));
      const opts = {};

      // Validate --type: must be in --type=VALUE form with a non-empty VALUE
      if (typeArg) {
        const value = typeArg.includes('=') ? typeArg.split('=').slice(1).join('=') : '';
        if (!value) {
          console.error('--type requires a value (e.g. --type=feature)');
          process.exit(2);
        }
        opts.type = value;
      }

      // Validate --tag: same contract as --type
      if (tagArg) {
        const value = tagArg.includes('=') ? tagArg.split('=').slice(1).join('=') : '';
        if (!value) {
          console.error('--tag requires a value (e.g. --tag=auth)');
          process.exit(2);
        }
        opts.tag = value;
      }

      // Validate --limit: positive integer
      let limit = null;
      if (limitArg) {
        const raw = limitArg.includes('=') ? limitArg.split('=').slice(1).join('=') : '';
        limit = Number(raw);
        if (!Number.isInteger(limit) || limit <= 0) {
          console.error('--limit requires a positive integer (e.g. --limit=10)');
          process.exit(2);
        }
      }

      // Reject empty queries: previously returned `{results:[],total:0}` silently,
      // which masked shell-quoting bugs in callers (e.g. `kb-search search ""`).
      // Exit 2 with a stderr message so scripts can detect the misuse.
      const queryTerms = tokenize(query);
      if (!queryTerms.length) {
        console.error('Empty query: provide one or more search terms');
        process.exit(2);
      }

      const result = search(query, opts);
      if (limit !== null) {
        result.results = result.results.slice(0, limit);
        // Keep `total` as the full match count so callers know how many were trimmed.
      }
      console.log(JSON.stringify(result, null, 2));
      break;
    }

    case 'stats': {
      stats();
      break;
    }

    case 'lean': {
      // Print the lean index. Building via the lean-index module keeps the
      // write path in a single place (atomic .tmp + rename) and guarantees
      // the file on disk matches what we just printed.
      const { buildLeanIndex } = require('./lean-index.js');
      const idx = buildLeanIndex();
      console.log(JSON.stringify(idx, null, 2));
      break;
    }

    default: {
      console.error('Unknown command: ' + command);
      console.error(HELP_TEXT);
      process.exit(1);
    }
  }
}

// Export HELP_TEXT (and useful internals) so other CLI entry points can
// reuse them without duplicating strings. Keeping this at the bottom lets
// the `if (require.main === module)` block stay close to the CLI logic.
module.exports = {
  HELP_TEXT,
  buildIndex,
  search,
  stats,
};
