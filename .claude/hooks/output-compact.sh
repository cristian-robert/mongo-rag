#!/usr/bin/env bash
# .claude/hooks/output-compact.sh
# Stop hook — compact user-facing final message (caveman style).
#
# Contract:
#   - Reads stdin (plain text OR JSON envelope with .assistant_text/.message/.text/.content).
#   - Writes compacted text (or unmodified JSON with compacted field) to stdout.
#   - Preserves fenced code blocks, markdown tables, list items, headings, and
#     file:line paths. Strips hedging and redundant politeness from prose lines.
#
# Empty stdin / smoke-test safety:
#   - If stdin is a TTY (no data piped), exit 0 immediately.
#   - If piped input is empty, exit 0 silently.
#
# Default: OFF (opt-in). The hook only runs compaction when:
#   - CLAUDE.md has a "## Output Compaction" section with "State: on", OR
#   - Env var CLAUDE_OUTPUT_COMPACT=on is set
# In all other cases (no section, "State: off", absent state line, no env)
# the hook passes input through unchanged.
#
# Per-session opt-outs (force OFF even when default is ON):
#   - Env var: CLAUDE_OUTPUT_COMPACT=off
#   - The input contains the literal marker "<!-- no-compact -->" anywhere
#
# Why opt-in: the hedge word-list is Anglocentric and may drop tokens from
# quoted speech, numeric prose, or non-English content. Users should read
# .claude/references/output-compaction.md and verify the rules match their
# expectations before flipping State: on.
#
# Awk portability: we DO NOT use gawk-only \y word boundaries in awk. Awk
# handles per-line PRESERVATION (code fences, tables, lists, headings,
# file:line paths). Prose lines are marked with a sentinel prefix and the
# actual word-boundary-aware strip is done with sed (BSD + GNU sed both
# support the [[:<:]] / [[:>:]] word-boundary atoms). This avoids matching
# "I think" inside "Greatly", "Basicallyism", etc. macOS default awk is BSD
# awk; Linux default is gawk — both work for preservation. BSD sed and
# recent GNU sed (>=4.8) both accept [[:<:]] and [[:>:]].

set -uo pipefail

# --- Empty stdin check -------------------------------------------------------
if [ -t 0 ]; then
  exit 0
fi

input="$(cat || true)"
if [ -z "$input" ]; then
  exit 0
fi

# --- Opt-in resolution -------------------------------------------------------
# Default is OFF. Compaction only runs when an explicit opt-in is found:
#   1. Env var CLAUDE_OUTPUT_COMPACT=on, OR
#   2. CLAUDE.md "## Output Compaction" section with "State: on"
# CLAUDE_OUTPUT_COMPACT=off forces OFF regardless of section state, so a user
# can quickly disable per-session even if the project opted in.
env_state="${CLAUDE_OUTPUT_COMPACT:-}"
section_state=""
if [ -f CLAUDE.md ]; then
  section="$(awk '
    /^## Output Compaction/ { inside=1; next }
    inside && /^## / { exit }
    inside { print }
  ' CLAUDE.md 2>/dev/null || true)"
  if [ -n "$section" ]; then
    if printf '%s' "$section" | grep -Eqi '^[[:space:]]*State:[[:space:]]*on[[:space:]]*$'; then
      section_state="on"
    elif printf '%s' "$section" | grep -Eqi '^[[:space:]]*State:[[:space:]]*off[[:space:]]*$'; then
      section_state="off"
    fi
  fi
fi

# Per-session env=off forces OFF, no matter what the section says.
if [ "$env_state" = "off" ]; then
  printf '%s' "$input"
  exit 0
fi

# Otherwise, require an explicit opt-in. Anything else (no section, no
# State line, State: off, env unset) → pass-through.
if [ "$env_state" != "on" ] && [ "$section_state" != "on" ]; then
  printf '%s' "$input"
  exit 0
fi

# --- No-compact marker bypass ------------------------------------------------
if printf '%s' "$input" | grep -q '<!-- no-compact -->'; then
  printf '%s' "$input"
  exit 0
fi

# --- JSON envelope detection -------------------------------------------------
# Weak heuristic: leading '{' and a known text field. If node is available,
# try to extract the field; on any failure, fall back to treating the input
# as plain text. Passing through valid JSON untouched is safer than mangling.
text="$input"
is_json=0
json_field=""

first_char="$(printf '%s' "$input" | head -c1)"
if [ "$first_char" = "{" ] && command -v node >/dev/null 2>&1; then
  for field in assistant_text message text content; do
    extracted="$(node -e '
      let d="";
      process.stdin.on("data",c=>d+=c);
      process.stdin.on("end",()=>{
        try {
          const j = JSON.parse(d);
          const f = process.argv[1];
          if (j && typeof j[f] === "string") process.stdout.write(j[f]);
          else process.exit(1);
        } catch (e) { process.exit(1); }
      });
    ' "$field" <<<"$input" 2>/dev/null)" || extracted=""
    if [ -n "$extracted" ]; then
      text="$extracted"
      is_json=1
      json_field="$field"
      break
    fi
  done
fi

# --- Compaction filter -------------------------------------------------------
# Stage 1 (awk): PRESERVE lines pass through untouched; prose lines get a
# sentinel prefix (\x01PROSE\x01) so stage 2 can tell them apart.
#   * fenced code blocks (toggle on lines beginning with ```),
#   * markdown tables (leading |),
#   * list items (leading -, *, or N.),
#   * headings (leading #),
#   * blockquotes (leading >),
#   * any line containing a file:line pattern (e.g. foo.ts:42),
#   * any line containing a dispatch marker "[dispatch] role=" — these are
#     structural coupling tokens consumed by spec-reviewer-enforce.sh and
#     MUST NOT be rewritten,
#   * any line containing the literal "[no-compact]" — explicit per-line
#     bypass marker.
# Stage 2a (awk): on prose-marked lines, replace inline `...` spans with a
#   placeholder sentinel (\x02NUM\x02) and append a trailer after \x03 holding
#   the originals, so stage 2b's word-boundary strip cannot touch backtick
#   contents. `I think` inside an inline literal becomes a placeholder that
#   sed won't see as the hedging phrase.
# Stage 2b (sed): on prose-marked lines only,
#   * drop hedging phrases (word-boundary-anchored, case-insensitive),
#   * drop redundant politeness ("Great!", etc.) with optional bang,
#   * collapse runs of spaces, trim leading whitespace,
#   * remove the sentinel prefix (but NOT the trailer — stage 2c needs it).
# Stage 2c (awk): restore placeholders from the trailer, strip the trailer.
compacted="$(printf '%s' "$text" | awk '
  BEGIN { in_fence = 0 }
  /^```/               { in_fence = !in_fence; print; next }
  in_fence              { print; next }
  /^\|/                 { print; next }
  /^[ \t]*([-*]|[0-9]+\.)[ \t]/ { print; next }
  /^#/                  { print; next }
  /^[ \t]*>/            { print; next }
  /\[dispatch\] role=/  { print; next }
  /\[no-compact\]/      { print; next }
  /[A-Za-z_.\/-]+\.[A-Za-z0-9]+:[0-9]+/ { print; next }
  { print "\001PROSE\001" $0 }
' | awk '
  # Extract inline `...` spans on prose lines only. Placeholder sentinel is
  # \x02NUM\x02 embedded in the PROSE body line; originals are emitted on a
  # SEPARATE following line prefixed with \x05TRAIL\x05, packed as
  # NUM\x04ORIGINAL (repeated, one \x03 separating records). We use a
  # separate line so sed''s /^\x01PROSE\x01/ address does NOT fire on the
  # trailer — otherwise sed would strip "I think" out of the stored original.
  # Double-backtick / triple-backtick spans are already handled by the
  # fenced-block guard — we only match single-backtick spans with no
  # backticks inside. Non-greedy via char class [^`].
  BEGIN { SEP1 = "\002"; SEP2 = "\003"; SEP3 = "\004" }
  /^\001PROSE\001/ {
    line = $0
    out = ""
    trailer = ""
    n = 0
    while (match(line, /`[^`]+`/)) {
      out = out substr(line, 1, RSTART - 1) SEP1 n SEP1
      orig = substr(line, RSTART, RLENGTH)
      if (n > 0) trailer = trailer SEP2
      trailer = trailer n SEP3 orig
      line = substr(line, RSTART + RLENGTH)
      n++
    }
    out = out line
    print out
    if (n > 0) {
      print "\005TRAIL\005" trailer
    }
    next
  }
  { print }
' | sed -E '
  /^\x01PROSE\x01/ {
    s/[[:<:]](It seems|I think|I believe|Essentially|Basically|As you can see)[[:>:]][,]?[ ]*//g
    s/[[:<:]](it seems|i think|i believe|essentially|basically|as you can see)[[:>:]][,]?[ ]*//g
    s/[[:<:]](Great|Absolutely|Of course|Certainly)[[:>:]]!?[ ]*//g
    s/  +/ /g
    s/^\x01PROSE\x01[[:space:]]*/\x01PROSE\x01/
    s/^\x01PROSE\x01//
  }
' | awk '
  # Restore inline-backtick placeholders from the trailer line (if any).
  # The extractor emitted the body first, then (optionally) a TRAIL line with
  # records separated by \x03, each record being NUM\x04ORIGINAL. We buffer
  # the body line and, when the next line is a TRAIL, substitute placeholders
  # back in; otherwise the buffered body is emitted as-is.
  BEGIN { SEP1 = "\002"; RECSEP = "\003"; FIELDSEP = "\004"; pending = ""; have_pending = 0 }
  /^\005TRAIL\005/ {
    trailer = substr($0, 8)  # strip \x05TRAIL\x05 (7 chars: 1+5+1)
    body = have_pending ? pending : ""
    n_rec = split(trailer, recs, RECSEP)
    for (i = 1; i <= n_rec; i++) {
      sep = index(recs[i], FIELDSEP)
      if (sep == 0) continue
      num = substr(recs[i], 1, sep - 1)
      orig = substr(recs[i], sep + 1)
      placeholder = SEP1 num SEP1
      p = index(body, placeholder)
      if (p > 0) {
        body = substr(body, 1, p - 1) orig substr(body, p + length(placeholder))
      }
    }
    print body
    pending = ""; have_pending = 0
    next
  }
  {
    if (have_pending) print pending
    pending = $0
    have_pending = 1
  }
  END {
    if (have_pending) print pending
  }
')"

# --- Emit --------------------------------------------------------------------
if [ "$is_json" = 1 ] && command -v node >/dev/null 2>&1; then
  # Re-serialize the envelope with the compacted field value. Both the raw
  # JSON input and the compacted text are passed via stdin (separated by NUL)
  # so large messages can't hit ARG_MAX and odd characters can't be mangled
  # by shell quoting. On any failure fall back to raw compacted text —
  # never emit malformed JSON.
  rewrapped="$(printf '%s\0%s' "$input" "$compacted" | node -e '
    const chunks = [];
    process.stdin.on("data", c => chunks.push(c));
    process.stdin.on("end", () => {
      try {
        const d = Buffer.concat(chunks).toString("utf8");
        const sep = d.indexOf("\0");
        if (sep === -1) process.exit(1);
        const raw = d.slice(0, sep);
        const v = d.slice(sep + 1);
        const j = JSON.parse(raw);
        const f = process.argv[1];
        j[f] = v;
        process.stdout.write(JSON.stringify(j));
      } catch (e) { process.exit(1); }
    });
  ' "$json_field" 2>/dev/null)" || rewrapped=""
  if [ -n "$rewrapped" ]; then
    printf '%s' "$rewrapped"
  else
    printf '%s' "$compacted"
  fi
else
  printf '%s' "$compacted"
fi
