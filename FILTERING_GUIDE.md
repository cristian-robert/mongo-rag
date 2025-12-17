# Content Filtering Usage Guide

## Overview

The content filtering system allows you to selectively exclude specific sections, pages, and content patterns from textbooks during document ingestion. This is particularly useful for medical school preparation where you only want exam-relevant theory, not practice exercises or supplemental materials.

## Quick Start

### 1. Run Ingestion with Filtering

For your biology textbook with the predefined filter config:

```bash
uv run python -m examples.ingestion.ingest \
  -d ./documents \
  --filter-config .claude/filters/biology-clasa-11-corint.json
```

### 2. Run Without Filtering (Default)

```bash
uv run python -m examples.ingestion.ingest -d ./documents
```

## What Gets Filtered

Based on your biology textbook configuration (`.claude/filters/biology-clasa-11-corint.json`), the following content will be excluded:

### **Excluded Sections** (entire section removed)
- "Teme și aplicații" (Homework and Applications)
- "Lucrări practice" (Practical Work)
- "Autoevaluare" (Self-Assessment)
- "Noțiuni elementare de igienă și patologie" (Basic Hygiene and Pathology)

### **Excluded Subsections** (specific subsection removed)
- "Disfuncții endocrine" on page 61

### **Excluded Pages** (all content from these pages removed)
- Pages 109, 111, 112 (schemas not in curriculum)

### **Excluded Patterns** (content matching regex)
- Nutritional tables: "Conținutul în nutrimente (principii alimentare) și valoarea energetică la 100 g produs comestibil"

## How It Works

```
┌──────────────────┐
│  PDF Document    │
│  (biologie.pdf)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│  Docling Converter   │  ← Converts PDF to structured document
│  (with page info)    │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Content Filter      │  ← Applies exclusion rules
│  - Remove sections   │     • Section headers: "Teme și aplicații"
│  - Remove pages      │     • Pages: 109, 111, 112
│  - Remove patterns   │     • Patterns: nutritional tables
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Filtered Document   │  ← Only exam-relevant content
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  HybridChunker       │  ← Chunks filtered document
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Embedding Generator │  ← Creates vectors
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  MongoDB Storage     │  ← Stores only exam content
└──────────────────────┘
```

## Filtering Metadata

After ingestion, each document includes metadata showing what was filtered:

```json
{
  "document_id": "507f1f77bcf86cd799439011",
  "title": "Biologie - Manual pentru clasa a XI-a",
  "metadata": {
    "filter_metadata": {
      "sections_removed": [
        "Teme și aplicații",
        "Lucrări practice",
        "Autoevaluare",
        "Noțiuni elementare de igienă și patologie"
      ],
      "pages_removed": [109, 111, 112],
      "blocks_removed": 287,
      "filter_config_used": "biology:Biologie - Manual pentru clasa a XI-a"
    }
  }
}
```

This metadata allows you to:
- Verify what content was excluded
- Debug if important content is missing
- Audit compliance with curriculum requirements

## Creating Filter Configs for Other Textbooks

### Chemistry Example

Create `.claude/filters/chemistry-clasa-12-corint.json`:

```json
{
  "subject": "chemistry",
  "book": "Chimie - Manual pentru clasa a XII-a",
  "authors": ["..."],
  "exclude_sections": [
    "Exerciții",
    "Probleme rezolvate",
    "Autoevaluare"
  ],
  "exclude_pages": [],
  "exclude_patterns": [],
  "case_sensitive": false
}
```

Then run:

```bash
uv run python -m examples.ingestion.ingest \
  -d ./documents \
  --filter-config .claude/filters/chemistry-clasa-12-corint.json
```

### Physics Example

For physics textbooks excluding numerical problems:

```json
{
  "subject": "physics",
  "book": "Fizică - Manual pentru clasa a XI-a",
  "exclude_sections": [
    "Probleme rezolvate",
    "Exerciții propuse"
  ],
  "exclude_patterns": [
    "Exemplu \\d+:",
    "Problemă rezolvată \\d+:"
  ]
}
```

## Advanced Usage

### Multiple Subject Ingestion

Process all subjects with their respective filters:

```bash
# Biology
uv run python -m examples.ingestion.ingest \
  -d ./documents/biology \
  --filter-config .claude/filters/biology-clasa-11-corint.json

# Chemistry
uv run python -m examples.ingestion.ingest \
  -d ./documents/chemistry \
  --filter-config .claude/filters/chemistry-clasa-12-corint.json

# Physics
uv run python -m examples.ingestion.ingest \
  -d ./documents/physics \
  --filter-config .claude/filters/physics-clasa-11.json
```

### Custom Filtering Per Document

Create document-specific configs for different editions or publishers:

```
.claude/filters/
├── biology-clasa-11-corint.json       ← Corint publisher, 2006 edition
├── biology-clasa-11-niculescu.json    ← Niculescu publisher
├── chemistry-clasa-12-corint.json
└── physics-clasa-11.json
```

### Verify Filtering Before Full Ingestion

Test filtering on a single document first:

```bash
# Ingest just one document with filtering
uv run python -m examples.ingestion.ingest \
  -d ./documents/test-sample.pdf \
  --filter-config .claude/filters/biology-clasa-11-corint.json \
  --verbose
```

Check the logs to see what was filtered:
```
INFO - Applying content filter to Biologie - Manual pentru clasa a XI-a
INFO - Filtering complete: 287 blocks removed, 4 sections excluded
INFO - Loaded filter config for biology: Biologie - Manual pentru clasa a XI-a
INFO -   Exclude sections: 4, pages: 3, patterns: 1
```

## Troubleshooting

### Problem: Important content is being filtered out

**Solution:** Check your filter config and make section names more specific

```json
{
  "exclude_sections": [
    "Teme și aplicații"  // ❌ Too broad, might match subsections
  ]
}
```

Change to:

```json
{
  "exclude_subsections": [
    {"title": "Teme și aplicații", "page": 45}  // ✅ More specific
  ]
}
```

### Problem: Sections not being filtered

**Check:**
1. Section header text matches exactly (case-insensitive by default)
2. The PDF was successfully converted by Docling
3. Logging shows filtering was applied (`--verbose` flag)

**Debug:**
```bash
uv run python -m examples.ingestion.ingest \
  -d ./documents \
  --filter-config .claude/filters/biology-clasa-11-corint.json \
  --verbose \
  --no-clean  # Don't clean DB, just see logs
```

### Problem: Filter config not loading

**Check:**
1. JSON syntax is valid: `python -m json.tool .claude/filters/your-config.json`
2. File path is correct (relative to project root)
3. All required fields are present (`subject`, `book`)

## Best Practices

1. **Start with section-level exclusions** - Remove major sections first (e.g., "Teme și aplicații")

2. **Add page-specific exclusions** - For tables, charts, schemas not in curriculum

3. **Use patterns for repeated structures** - Tables, problem examples, etc.

4. **Test incrementally** - Filter one textbook at a time, verify results

5. **Version control your configs** - Commit filter configs to git

6. **Document your rationale** - Add comments explaining why sections are excluded (in README or separate doc)

7. **Coordinate with curriculum** - Sync exclusion rules with official medical school admission requirements

## Platform Integration

For your Romanian medical school learning platform, you can:

1. **Pre-process all textbooks** with their respective filter configs
2. **Store only exam-relevant content** in MongoDB
3. **Track filtered metadata** for transparency
4. **Allow administrators** to update filter configs as curriculum changes
5. **Generate reports** showing what content is included/excluded per subject

## Example: Complete Workflow

```bash
# 1. Prepare your documents folder
mkdir -p documents/biology documents/chemistry documents/physics

# 2. Add PDF textbooks
cp ~/Downloads/biologie-cls-11.pdf documents/biology/
cp ~/Downloads/chimie-cls-xii.pdf documents/chemistry/

# 3. Create/verify filter configs
ls .claude/filters/
# biology-clasa-11-corint.json
# chemistry-clasa-12-corint.json

# 4. Run ingestion with filtering
uv run python -m examples.ingestion.ingest \
  -d documents/biology \
  --filter-config .claude/filters/biology-clasa-11-corint.json \
  --verbose

# 5. Query your RAG agent
uv run python -m examples.cli
# User: "Explică-mi procesul de fotosinteză"
# Agent: [Returns only theory content, no practice problems]
```

## Next Steps

- Test filtering with `documents/biologie-cls-xi.pdf`
- Create filter configs for other subjects (chemistry, physics)
- Verify filtered content aligns with medical school admission requirements
- Build student-facing query interface on top of filtered corpus
