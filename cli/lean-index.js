#!/usr/bin/env node
'use strict';

// ─── Lean Index ───────────────────────────────────────────────────────────────
//
// Metadata-only view of the wiki — title, type, tags, and a one-line summary
// per article. No article bodies, no TF vectors. Designed for /prime to load
// cheaply at session start. The full TF-IDF index (cli/kb-search.js) is the
// authoritative source for semantic search; the lean index is a lightweight
// companion for quick enumeration.
//
// GOTCHA: never embed full article bodies here — the lean index is supposed
// to be tiny (<5% of the full index). A size-cap test in lean-index.test.js
// enforces this invariant.

const fs = require('fs');
const path = require('path');

// ─── Config ───────────────────────────────────────────────────────────────────

const KB_PATH = process.env.KB_PATH || '.obsidian';
const WIKI_DIR = path.join(KB_PATH, 'wiki');
const SEARCH_DIR = path.join(KB_PATH, '_search');
const LEAN_INDEX_FILE = path.join(SEARCH_DIR, 'lean-index.json');

// ─── Frontmatter parser (duplicated from kb-search.js) ────────────────────────
//
// The parser is duplicated here instead of imported because kb-search.js does
// not export it, and we want the lean-index module to stand alone (no new
// runtime deps, no cross-module coupling). Any behaviour change should be
// mirrored in both files.

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
      const inner = raw.replace(/^\[|\]$/g, '');
      meta[key] = inner ? inner.split(',').map((s) => s.trim()).filter(Boolean) : [];
      i++;
    } else if (raw === '') {
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

// ─── Summary extraction ───────────────────────────────────────────────────────
//
// Take the first sentence of the article body (up to 160 chars). Strip
// headings, wikilinks, and collapse whitespace so the summary reads like a
// short one-liner. Never include the full body.

function extractSummary(body) {
  const cleaned = body
    .replace(/^#+\s+.*/gm, '')          // strip headings
    .replace(/\[\[([^\]|]+)(\|[^\]]+)?\]\]/g, '$1')  // unwrap wikilinks
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return '';

  // First sentence: up to the first `.`, `!`, or `?` followed by space/end.
  const sentenceMatch = cleaned.match(/^(.+?[.!?])(\s|$)/);
  const firstSentence = sentenceMatch ? sentenceMatch[1] : cleaned;
  if (firstSentence.length <= 160) return firstSentence;
  return firstSentence.slice(0, 157) + '...';
}

// ─── Builder ──────────────────────────────────────────────────────────────────

function buildLeanIndex() {
  // Graceful handling — /prime may call buildLeanIndex() before the KB has
  // been initialised. Return an empty shape instead of crashing.
  if (!fs.existsSync(WIKI_DIR)) {
    const empty = { generated: new Date().toISOString(), docs: [] };
    fs.mkdirSync(SEARCH_DIR, { recursive: true });
    writeIndex(empty);
    return empty;
  }

  const files = fs.readdirSync(WIKI_DIR).filter(
    (f) => f.endsWith('.md') && !f.startsWith('_')
  );

  const docs = [];
  for (const file of files) {
    let content;
    try {
      content = fs.readFileSync(path.join(WIKI_DIR, file), 'utf-8');
    } catch (e) {
      console.warn(`Warning: could not read wiki/${file}: ${e.message}`);
      continue;
    }

    // Per-file YAML parse errors must not crash the build — skip malformed
    // articles with a warning so a single bad file doesn't break the whole
    // index. Matches the resilience pattern used by kb-search.js corrupt-index
    // recovery.
    let parsed;
    try {
      parsed = parseFrontmatter(content);
    } catch (e) {
      console.warn(`Warning: malformed frontmatter in wiki/${file}: ${e.message}`);
      continue;
    }

    const { meta, body } = parsed;
    docs.push({
      file,
      title: meta.title || file,
      type: meta.type || '',
      tags: Array.isArray(meta.tags) ? meta.tags : [],
      summary: extractSummary(body),
    });
  }

  const index = { generated: new Date().toISOString(), docs };

  fs.mkdirSync(SEARCH_DIR, { recursive: true });
  writeIndex(index);
  return index;
}

// Atomic write: write to a sibling .tmp file, then rename. rename(2) is
// atomic on POSIX (and Windows same-volume), so concurrent readers always
// see either the old or new index — never a torn write. Mirrors the pattern
// used by kb-search.js#writeIndex.
function writeIndex(index) {
  const tmp = LEAN_INDEX_FILE + '.tmp';
  try {
    fs.writeFileSync(tmp, JSON.stringify(index, null, 2), 'utf-8');
    fs.renameSync(tmp, LEAN_INDEX_FILE);
  } catch (e) {
    try { fs.unlinkSync(tmp); } catch (_) {}
    throw e;
  }
}

function loadLeanIndex() {
  if (!fs.existsSync(LEAN_INDEX_FILE)) return buildLeanIndex();
  try {
    return JSON.parse(fs.readFileSync(LEAN_INDEX_FILE, 'utf-8'));
  } catch (e) {
    // Corrupted — rebuild from scratch (mirrors kb-search.js recovery).
    try { fs.unlinkSync(LEAN_INDEX_FILE); } catch (_) {}
    return buildLeanIndex();
  }
}

// ─── CLI entry ────────────────────────────────────────────────────────────────
//
// Guard CLI execution so `require('./lean-index.js')` is side-effect-free.
// Matches kb-search.js / init.js / update.js pattern.

if (require.main === module) {
  const [, , command] = process.argv;

  switch (command) {
    case undefined:
    case 'build':
    case 'index': {
      const idx = buildLeanIndex();
      console.log(`Lean-indexed ${idx.docs.length} articles → ${LEAN_INDEX_FILE}`);
      break;
    }
    case 'print':
    case 'show': {
      const idx = loadLeanIndex();
      console.log(JSON.stringify(idx, null, 2));
      break;
    }
    case '--help':
    case '-h': {
      console.log([
        'Usage: lean-index <command>',
        '',
        'Commands:',
        '  build    Build (or rebuild) the lean index (default)',
        '  print    Print the lean index as JSON',
        '',
        'Environment:',
        '  KB_PATH  Path to the KB root (default: .obsidian)',
      ].join('\n'));
      break;
    }
    default: {
      console.error('Unknown command: ' + command);
      process.exit(1);
    }
  }
}

module.exports = {
  buildLeanIndex,
  loadLeanIndex,
  extractSummary,
  parseFrontmatter,
};
