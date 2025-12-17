# Feature: Phase 1 - Project Scaffolding & Configuration

## Feature Description

Establish the foundational project structure with UV package management, MongoDB-specific configuration, and validation tooling. This phase creates the bare minimum infrastructure needed to run code and validate the environment before implementing database connections, search tools, or the agent.

This is a greenfield MongoDB implementation in a new `src/` directory while preserving the existing `examples/` folder as reference material from a PostgreSQL-based RAG system.

## User Story

As a **developer setting up the MongoDB RAG Agent**
I want to **initialize the project with proper dependency management and configuration**
So that **I can validate the environment and begin implementing MongoDB-specific features**

## Problem Statement

The project currently has:
- No package management configuration (missing pyproject.toml)
- No source directory for MongoDB implementation (examples/ is PostgreSQL reference only)
- PostgreSQL-specific settings that need MongoDB equivalents
- No validation script to verify environment setup
- No .gitignore to protect sensitive credentials

We need project scaffolding that allows developers to:
1. Install dependencies reliably with UV
2. Configure MongoDB connection parameters via .env
3. Validate configuration before attempting connections
4. Maintain clear separation between PostgreSQL reference (examples/) and MongoDB implementation (src/)

## Solution Statement

Create a complete project foundation with:
- `pyproject.toml` configured for UV with all required dependencies
- `src/` directory structure for MongoDB implementation
- `src/settings.py` adapted from examples/ with MongoDB-specific fields
- `src/providers.py` copied from examples/ (no changes needed)
- `src/test_config.py` validation script to verify environment setup
- `.gitignore` to protect credentials and virtual environments
- `.env.example` template showing required configuration
- Updated `README.md` with MongoDB setup instructions

## Feature Metadata

**Feature Type**: New Capability (Project Foundation)
**Estimated Complexity**: Low
**Primary Systems Affected**: Project Structure, Configuration, Environment Setup
**Dependencies**:
- UV package manager (0.5.0+)
- PyMongo 4.10+ (with async API, replaces Motor)
- Pydantic 2.10+
- Pydantic AI 0.1.0+
- Docling 2.14+
- OpenAI 1.58+
- Rich 13.9+

---

## CONTEXT REFERENCES

### Relevant Codebase Files IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `examples/settings.py` (lines 1-98) - Why: PostgreSQL settings structure to adapt for MongoDB
- `examples/providers.py` (lines 1-81) - Why: LLM provider setup that works as-is, copy directly
- `.claude/PRD.md` (lines 262-297) - Why: Required MongoDB environment variables specification
- `.claude/PRD.md` (lines 744-795) - Why: Target project structure showing src/ directory layout
- `CLAUDE.md` (lines 1-80) - Why: Project development principles (TYPE SAFETY, KISS, YAGNI, ASYNC)
- `.env` (lines 1-18) - Why: Current environment variables (contains credentials - DO NOT COMMIT)

### New Files to Create

- `pyproject.toml` - UV package management configuration with all dependencies
- `.gitignore` - Standard Python gitignore with .env, .venv, __pycache__
- `.env.example` - Template showing required MongoDB environment variables (NO ACTUAL CREDENTIALS)
- `README.md` - MongoDB-focused setup instructions
- `src/__init__.py` - Empty module initialization
- `src/settings.py` - MongoDB-specific settings (adapted from examples/settings.py)
- `src/providers.py` - LLM provider setup (copied from examples/providers.py)
- `src/test_config.py` - Configuration validation script

### Relevant Documentation YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [UV Project Configuration](https://docs.astral.sh/uv/concepts/projects/config/)
  - Specific section: pyproject.toml structure and [tool.uv] configuration
  - Why: Required for setting up UV package management correctly

- [UV Working on Projects](https://docs.astral.sh/uv/guides/projects/)
  - Specific section: Creating projects and managing dependencies
  - Why: Shows how to use `uv init`, `uv add`, and `uv run` commands

- [PyMongo Async Migration Guide](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/)
  - Specific section: Motor to PyMongo Async migration patterns
  - Why: Motor is deprecated (May 2025), use PyMongo AsyncMongoClient instead

- [PyMongo Async API Tutorial](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/get-started/quickstart/)
  - Specific section: AsyncMongoClient usage patterns
  - Why: Shows correct async MongoDB connection patterns for 2025

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
  - Specific section: Environment variable loading and ConfigDict
  - Why: Required for type-safe settings management

### Patterns to Follow

**Naming Conventions:**
```python
# From examples/settings.py - snake_case for variables and functions
database_url: str = Field(...)
def load_settings() -> Settings:
```

**Pydantic Settings Pattern:**
```python
# From examples/settings.py (lines 12-98)
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars
    )

    field_name: str = Field(
        default="default_value",
        description="Clear description of field purpose"
    )
```

**Error Handling Pattern:**
```python
# From examples/settings.py (lines 88-98)
def load_settings() -> Settings:
    """Load settings with proper error handling."""
    try:
        return Settings()
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "mongodb_uri" in str(e).lower():
            error_msg += "\nMake sure to set MONGODB_URI in your .env file"
        raise ValueError(error_msg) from e
```

**Import Organization:**
```python
# Standard library imports first
import os
import logging
from typing import Optional, List

# Third-party imports
from pydantic import Field
from pydantic_settings import BaseSettings

# Local imports last
from .providers import get_llm_model
```

**Type Hints (MANDATORY):**
```python
# From CLAUDE.md - ALL functions must have type annotations
def create_chunker(config: ChunkingConfig) -> DoclingHybridChunker:
    """Create DoclingHybridChunker for intelligent document splitting."""
    return DoclingHybridChunker(config)
```

**Google-style Docstrings (MANDATORY):**
```python
# From CLAUDE.md and examples/ingestion/embedder.py (lines 63-82)
async def generate_embedding(self, text: str) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed

    Returns:
        Embedding vector

    Raises:
        ValueError: If text is empty or too long
    """
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation Files

Create core project configuration files that enable UV dependency management and environment setup.

**Tasks:**
- Create pyproject.toml with UV configuration
- Create .gitignore for Python projects
- Create .env.example template

### Phase 2: Source Directory & Settings

Establish src/ directory and adapt settings from examples/ for MongoDB.

**Tasks:**
- Create src/ directory structure
- Adapt settings.py for MongoDB (remove PostgreSQL fields, add MongoDB fields)
- Copy providers.py directly from examples/

### Phase 3: Validation Script

Build configuration validation script to verify environment before database connections.

**Tasks:**
- Create test_config.py validation script
- Test settings loading
- Validate all required environment variables present

### Phase 4: Documentation

Update project documentation with MongoDB-specific setup instructions.

**Tasks:**
- Update README.md with MongoDB setup
- Document UV commands
- Add MongoDB Atlas setup requirements

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### CREATE pyproject.toml

- **IMPLEMENT**: UV project configuration with metadata and dependencies
- **PATTERN**: Follow [UV Project Config](https://docs.astral.sh/uv/concepts/projects/config/) - [project] and [tool.uv] sections
- **DEPENDENCIES**:
  ```toml
  [project]
  name = "mongodb-rag-agent"
  version = "0.1.0"
  description = "Agentic RAG system with MongoDB Atlas Vector Search"
  requires-python = ">=3.10"
  dependencies = [
      "pydantic>=2.10.0",
      "pydantic-settings>=2.7.0",
      "pydantic-ai>=0.1.0",
      "pymongo>=4.10.0",  # NOT motor - Motor deprecated May 2025
      "openai>=1.58.0",
      "docling>=2.14.0",
      "docling-core>=2.4.0",
      "transformers>=4.47.0",
      "rich>=13.9.0",
      "python-dotenv>=1.0.1",
      "aiofiles>=24.1.0",
  ]

  [build-system]
  requires = ["setuptools>=61.0"]
  build-backend = "setuptools.build_meta"

  [tool.uv]
  dev-dependencies = [
      "pytest>=8.3.0",
      "pytest-asyncio>=0.24.0",
      "black>=24.10.0",
      "ruff>=0.8.0",
  ]
  ```
- **GOTCHA**: Use `pymongo>=4.10.0` NOT `motor` - Motor is deprecated as of May 2025, PyMongo now has native async API
- **GOTCHA**: Specify `requires-python = ">=3.10"` for async and type hint compatibility
- **VALIDATE**: `uv lock` (generates uv.lock file without errors)

### CREATE .gitignore

- **IMPLEMENT**: Standard Python gitignore protecting credentials and build artifacts
- **PATTERN**: Mirror standard Python gitignore patterns
- **CONTENT**:
  ```gitignore
  # Environment
  .env
  .venv/
  venv/
  ENV/
  env/

  # Python
  __pycache__/
  *.py[cod]
  *$py.class
  *.so
  .Python
  build/
  develop-eggs/
  dist/
  downloads/
  eggs/
  .eggs/
  lib/
  lib64/
  parts/
  sdist/
  var/
  wheels/
  *.egg-info/
  .installed.cfg
  *.egg

  # Testing
  .pytest_cache/
  .coverage
  htmlcov/

  # IDEs
  .vscode/
  .idea/
  *.swp
  *.swo
  *~
  .DS_Store

  # UV
  uv.lock

  # Logs
  *.log
  ```
- **GOTCHA**: MUST include `.env` to prevent committing MongoDB credentials
- **VALIDATE**: `git check-ignore .env` (should output ".env" if git initialized)

### CREATE .env.example

- **IMPLEMENT**: Template showing required MongoDB environment variables WITHOUT actual credentials
- **PATTERN**: Follow PRD.md (lines 266-297) environment variable specification
- **CONTENT**:
  ```bash
  # MongoDB Atlas Configuration
  MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
  MONGODB_DATABASE=rag_db
  MONGODB_COLLECTION_DOCUMENTS=documents
  MONGODB_COLLECTION_CHUNKS=chunks

  # MongoDB Atlas Indexes (must be created in Atlas UI)
  MONGODB_VECTOR_INDEX=vector_index
  MONGODB_TEXT_INDEX=text_index

  # LLM Provider Configuration
  # Options: openai, openrouter, ollama, gemini
  LLM_PROVIDER=openrouter
  LLM_API_KEY=your-api-key-here
  LLM_MODEL=anthropic/claude-haiku-4.5
  LLM_BASE_URL=https://openrouter.ai/api/v1

  # Embedding Provider Configuration
  EMBEDDING_PROVIDER=openai
  EMBEDDING_API_KEY=your-openai-api-key-here
  EMBEDDING_MODEL=text-embedding-3-small
  EMBEDDING_BASE_URL=https://api.openai.com/v1

  # Search Configuration
  DEFAULT_MATCH_COUNT=10
  MAX_MATCH_COUNT=50
  DEFAULT_TEXT_WEIGHT=0.3

  # Application Settings
  APP_ENV=development
  LOG_LEVEL=INFO
  ```
- **GOTCHA**: Use placeholder values like "your-api-key-here", NOT real credentials
- **GOTCHA**: Document that MongoDB indexes must be created in Atlas UI (cannot be created programmatically)
- **VALIDATE**: `cat .env.example | grep -i "password\|key" | grep -v "your-"` (should return nothing - no real credentials)

### CREATE src/__init__.py

- **IMPLEMENT**: Empty Python module initialization file
- **CONTENT**: Empty file (0 bytes) or simple docstring
- **VALIDATE**: `python -c "import src"` (no errors after uv sync)

### CREATE src/settings.py

- **IMPLEMENT**: MongoDB-specific settings adapted from examples/settings.py
- **PATTERN**: Follow examples/settings.py (lines 12-98) Pydantic Settings structure
- **ADAPT**:
  - REMOVE: `database_url`, `db_pool_min_size`, `db_pool_max_size` (PostgreSQL-specific)
  - ADD: `mongodb_uri`, `mongodb_database`, `mongodb_collection_documents`, `mongodb_collection_chunks`, `mongodb_vector_index`, `mongodb_text_index`
  - KEEP: LLM settings, embedding settings, search settings
- **IMPORTS**:
  ```python
  from pydantic_settings import BaseSettings
  from pydantic import Field, ConfigDict
  from dotenv import load_dotenv
  from typing import Optional
  ```
- **CONTENT**:
  ```python
  """Settings configuration for MongoDB RAG Agent."""

  from pydantic_settings import BaseSettings
  from pydantic import Field, ConfigDict
  from dotenv import load_dotenv
  from typing import Optional

  # Load environment variables from .env file
  load_dotenv()


  class Settings(BaseSettings):
      """Application settings with environment variable support."""

      model_config = ConfigDict(
          env_file=".env",
          env_file_encoding="utf-8",
          case_sensitive=False,
          extra="ignore"
      )

      # MongoDB Configuration
      mongodb_uri: str = Field(
          ...,
          description="MongoDB Atlas connection string"
      )

      mongodb_database: str = Field(
          default="rag_db",
          description="MongoDB database name"
      )

      mongodb_collection_documents: str = Field(
          default="documents",
          description="Collection for source documents"
      )

      mongodb_collection_chunks: str = Field(
          default="chunks",
          description="Collection for document chunks with embeddings"
      )

      mongodb_vector_index: str = Field(
          default="vector_index",
          description="Vector search index name (must be created in Atlas UI)"
      )

      mongodb_text_index: str = Field(
          default="text_index",
          description="Full-text search index name (must be created in Atlas UI)"
      )

      # LLM Configuration (OpenAI-compatible)
      llm_provider: str = Field(
          default="openrouter",
          description="LLM provider (openai, anthropic, gemini, ollama, etc.)"
      )

      llm_api_key: str = Field(
          ...,
          description="API key for the LLM provider"
      )

      llm_model: str = Field(
          default="anthropic/claude-haiku-4.5",
          description="Model to use for search and summarization"
      )

      llm_base_url: Optional[str] = Field(
          default="https://openrouter.ai/api/v1",
          description="Base URL for the LLM API (for OpenAI-compatible providers)"
      )

      # Embedding Configuration
      embedding_provider: str = Field(
          default="openai",
          description="Embedding provider"
      )

      embedding_api_key: str = Field(
          ...,
          description="API key for embedding provider"
      )

      embedding_model: str = Field(
          default="text-embedding-3-small",
          description="Embedding model to use"
      )

      embedding_base_url: Optional[str] = Field(
          default="https://api.openai.com/v1",
          description="Base URL for embedding API"
      )

      embedding_dimension: int = Field(
          default=1536,
          description="Embedding vector dimension (1536 for text-embedding-3-small)"
      )

      # Search Configuration
      default_match_count: int = Field(
          default=10,
          description="Default number of search results to return"
      )

      max_match_count: int = Field(
          default=50,
          description="Maximum number of search results allowed"
      )

      default_text_weight: float = Field(
          default=0.3,
          description="Default text weight for hybrid search (0-1)"
      )


  def load_settings() -> Settings:
      """Load settings with proper error handling."""
      try:
          return Settings()
      except Exception as e:
          error_msg = f"Failed to load settings: {e}"
          if "mongodb_uri" in str(e).lower():
              error_msg += "\nMake sure to set MONGODB_URI in your .env file"
          if "llm_api_key" in str(e).lower():
              error_msg += "\nMake sure to set LLM_API_KEY in your .env file"
          if "embedding_api_key" in str(e).lower():
              error_msg += "\nMake sure to set EMBEDDING_API_KEY in your .env file"
          raise ValueError(error_msg) from e
  ```
- **GOTCHA**: MongoDB indexes CANNOT be created programmatically - must be created in Atlas UI
- **GOTCHA**: Use `...` (Ellipsis) for required fields without defaults
- **VALIDATE**: `uv run python -c "from src.settings import load_settings; print('Settings loaded')"` (requires .env file with MongoDB credentials)

### COPY examples/providers.py → src/providers.py

- **IMPLEMENT**: Copy providers.py directly from examples/ - no changes needed
- **PATTERN**: File works as-is for LLM/embedding provider setup
- **IMPORTS**: Update import to use `from src.settings import load_settings`
- **GOTCHA**: Change line 6 from `from settings import load_settings` to `from src.settings import load_settings`
- **CONTENT**: Copy entire file from examples/providers.py with only import path change
- **VALIDATE**: `uv run python -c "from src.providers import get_llm_model; print('Providers loaded')"` (requires .env with API keys)

### CREATE src/test_config.py

- **IMPLEMENT**: Configuration validation script to verify environment setup
- **PATTERN**: Simple script that loads settings and prints masked configuration
- **IMPORTS**:
  ```python
  import sys
  from src.settings import load_settings
  from src.providers import get_model_info
  ```
- **CONTENT**:
  ```python
  """Configuration validation script for MongoDB RAG Agent."""

  import sys
  from src.settings import load_settings
  from src.providers import get_model_info


  def mask_credential(value: str) -> str:
      """Mask credentials for safe display."""
      if not value or len(value) < 8:
          return "***"
      return value[:4] + "..." + value[-4:]


  def validate_config() -> bool:
      """
      Validate configuration and display settings.

      Returns:
          True if configuration is valid, False otherwise
      """
      try:
          print("=" * 60)
          print("MongoDB RAG Agent - Configuration Validation")
          print("=" * 60)
          print()

          # Load settings
          print("[1/4] Loading settings...")
          settings = load_settings()
          print("✓ Settings loaded successfully")
          print()

          # Validate MongoDB configuration
          print("[2/4] Validating MongoDB configuration...")
          print(f"  MongoDB URI: {mask_credential(settings.mongodb_uri)}")
          print(f"  Database: {settings.mongodb_database}")
          print(f"  Documents Collection: {settings.mongodb_collection_documents}")
          print(f"  Chunks Collection: {settings.mongodb_collection_chunks}")
          print(f"  Vector Index: {settings.mongodb_vector_index}")
          print(f"  Text Index: {settings.mongodb_text_index}")
          print("✓ MongoDB configuration present")
          print()

          # Validate LLM configuration
          print("[3/4] Validating LLM configuration...")
          model_info = get_model_info()
          print(f"  Provider: {model_info['llm_provider']}")
          print(f"  Model: {model_info['llm_model']}")
          print(f"  Base URL: {model_info['llm_base_url']}")
          print(f"  API Key: {mask_credential(settings.llm_api_key)}")
          print("✓ LLM configuration present")
          print()

          # Validate Embedding configuration
          print("[4/4] Validating Embedding configuration...")
          print(f"  Provider: {settings.embedding_provider}")
          print(f"  Model: {settings.embedding_model}")
          print(f"  Dimension: {settings.embedding_dimension}")
          print(f"  API Key: {mask_credential(settings.embedding_api_key)}")
          print("✓ Embedding configuration present")
          print()

          # Success summary
          print("=" * 60)
          print("✓ ALL CONFIGURATION CHECKS PASSED")
          print("=" * 60)
          print()
          print("Next steps:")
          print("1. Create MongoDB Atlas vector search index (see .claude/reference/mongodb-patterns.md)")
          print("2. Create MongoDB Atlas full-text search index")
          print("3. Run: uv run python -m src.dependencies (Phase 2 - test MongoDB connection)")
          print()

          return True

      except ValueError as e:
          print()
          print("=" * 60)
          print("✗ CONFIGURATION VALIDATION FAILED")
          print("=" * 60)
          print()
          print(f"Error: {e}")
          print()
          print("Please check your .env file and ensure all required variables are set.")
          print("See .env.example for required variables.")
          print()
          return False

      except Exception as e:
          print()
          print("=" * 60)
          print("✗ UNEXPECTED ERROR")
          print("=" * 60)
          print()
          print(f"Error: {e}")
          print()
          import traceback
          traceback.print_exc()
          return False


  if __name__ == "__main__":
      success = validate_config()
      sys.exit(0 if success else 1)
  ```
- **GOTCHA**: Use sys.exit(0) for success, sys.exit(1) for failure (standard Unix convention)
- **GOTCHA**: Mask credentials in output using mask_credential() function
- **VALIDATE**: `uv run python -m src.test_config` (requires .env file with all required vars)

### UPDATE README.md

- **IMPLEMENT**: MongoDB-focused setup instructions replacing PostgreSQL references
- **PATTERN**: Clear step-by-step setup guide with UV commands
- **CONTENT**:
  ```markdown
  # MongoDB RAG Agent - Intelligent Knowledge Base Search

  Agentic RAG system combining MongoDB Atlas Vector Search with Pydantic AI for intelligent document retrieval.

  ## Features

  - **Hybrid Search**: Combines semantic vector search with full-text keyword search using MongoDB's `$rankFusion`
  - **Multi-Format Ingestion**: PDF, Word, PowerPoint, Excel, HTML, Markdown, Audio transcription
  - **Intelligent Chunking**: Docling HybridChunker preserves document structure and semantic boundaries
  - **Conversational CLI**: Rich-based interface with real-time streaming and tool call visibility
  - **Multiple LLM Support**: OpenAI, OpenRouter, Ollama, Gemini

  ## Prerequisites

  - Python 3.10+
  - MongoDB Atlas account with cluster (M0 free tier works for development)
  - LLM provider API key (OpenAI, OpenRouter, etc.)
  - Embedding provider API key (OpenAI recommended)
  - UV package manager ([installation guide](https://docs.astral.sh/uv/))

  ## Quick Start

  ### 1. Install UV Package Manager

  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

  ### 2. Clone and Setup Project

  ```bash
  git clone <repository-url>
  cd MongoDB-RAG-Agent

  # Create virtual environment
  uv venv

  # Activate environment
  source .venv/bin/activate  # Unix
  .venv\Scripts\activate     # Windows

  # Install dependencies
  uv sync
  ```

  ### 3. Configure Environment

  ```bash
  # Copy environment template
  cp .env.example .env

  # Edit .env with your credentials
  # Required: MONGODB_URI, LLM_API_KEY, EMBEDDING_API_KEY
  ```

  ### 4. Create MongoDB Atlas Indexes

  **IMPORTANT**: Vector and full-text search indexes MUST be created in MongoDB Atlas UI before running searches.

  See `.claude/reference/mongodb-patterns.md` (lines 254-321) for detailed index creation instructions.

  **Vector Search Index** (for semantic search):
  ```json
  {
    "name": "vector_index",
    "type": "vectorSearch",
    "definition": {
      "fields": [{
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1536,
        "similarity": "cosine"
      }]
    }
  }
  ```

  **Full-Text Search Index** (for hybrid search):
  ```json
  {
    "name": "text_index",
    "type": "search",
    "definition": {
      "mappings": {
        "dynamic": false,
        "fields": {
          "content": {
            "type": "string",
            "analyzer": "lucene.standard"
          }
        }
      }
    }
  }
  ```

  ### 5. Validate Configuration

  ```bash
  uv run python -m src.test_config
  ```

  If validation passes, you'll see:
  ```
  ✓ ALL CONFIGURATION CHECKS PASSED
  ```

  ## Project Structure

  ```
  MongoDB-RAG-Agent/
  ├── src/                    # MongoDB implementation
  │   ├── settings.py        # Configuration management
  │   ├── providers.py       # LLM/embedding providers
  │   ├── test_config.py     # Configuration validation
  │   └── (Phase 2+)         # dependencies.py, tools.py, agent.py, cli.py
  ├── examples/              # PostgreSQL reference (DO NOT MODIFY)
  ├── documents/             # Document folder for ingestion
  ├── .claude/               # Project documentation
  │   ├── PRD.md            # Product requirements
  │   └── reference/        # MongoDB patterns, Docling, Agent docs
  └── pyproject.toml        # UV package configuration
  ```

  ## Development Workflow

  ### Phase 1: Configuration (Current)
  - ✅ Project scaffolding with UV
  - ✅ MongoDB-specific settings
  - ✅ Configuration validation

  ### Phase 2: MongoDB Connection
  - ⏳ MongoDB dependencies with PyMongo async
  - ⏳ Connection management and health checks

  ### Phase 3: Search Tools
  - ⏳ Semantic search with `$vectorSearch`
  - ⏳ Hybrid search with `$rankFusion`

  ### Phase 4: Ingestion Pipeline
  - ⏳ Docling multi-format conversion
  - ⏳ HybridChunker for intelligent splitting
  - ⏳ Batch embedding generation

  ### Phase 5: Agent & CLI
  - ⏳ Pydantic AI agent with search tools
  - ⏳ Rich CLI with streaming

  ## Commands

  ```bash
  # Validate configuration
  uv run python -m src.test_config

  # (Phase 2+) Test MongoDB connection
  uv run python -m src.dependencies

  # (Phase 4+) Ingest documents
  uv run python -m src.ingestion.ingest -d ./documents

  # (Phase 5+) Run CLI agent
  uv run python -m src.cli
  ```

  ## Documentation

  - `CLAUDE.md` - Development guidelines and patterns
  - `.claude/PRD.md` - Product requirements document
  - `.claude/reference/mongodb-patterns.md` - MongoDB implementation patterns
  - `.claude/reference/docling-ingestion.md` - Document processing guide
  - `.claude/reference/agent-tools.md` - Agent patterns and tools

  ## Technology Stack

  - **Database**: MongoDB Atlas 8.0+ (Vector Search + Full-Text Search)
  - **Agent Framework**: Pydantic AI 0.1.0+
  - **Document Processing**: Docling 2.14+ (PDF, Word, PowerPoint, Excel, Audio)
  - **Async Driver**: PyMongo 4.10+ with native async API (Motor deprecated)
  - **CLI**: Rich 13.9+ (terminal formatting and streaming)
  - **Package Manager**: UV 0.5.0+ (fast, reliable dependency management)

  ## License

  [Add your license here]
  ```
- **GOTCHA**: Emphasize that MongoDB indexes MUST be created in Atlas UI
- **GOTCHA**: Note that Motor is deprecated, project uses PyMongo async API
- **VALIDATE**: `cat README.md | grep -i "postgresql\|pgvector"` (should return nothing - all PostgreSQL references removed)

---

## TESTING STRATEGY

### Unit Tests

**Scope**: Configuration loading, settings validation, provider setup

**Test Files** (Phase 5 - Testing):
- `tests/test_settings.py` - Settings loading with various env configurations
- `tests/test_providers.py` - Provider initialization and model info

**Test Approach**:
- Mock environment variables using `pytest.monkeypatch`
- Test both success cases and failure cases (missing required fields)
- Verify error messages guide users to fix .env file

### Integration Tests

**Scope**: Not applicable for Phase 1 (no external connections yet)

Phase 2 will add MongoDB connection tests.

### Edge Cases

1. **Missing .env file**: Should fail with clear error about creating .env
2. **Incomplete .env file**: Should fail with specific missing field
3. **Invalid MongoDB URI format**: Should fail with connection string error
4. **Empty API keys**: Should fail with authentication error message
5. **Extra environment variables**: Should be ignored (extra="ignore" in ConfigDict)

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style

```bash
# Check Python syntax (if black/ruff installed)
uv run black --check src/
uv run ruff check src/

# Type checking (if mypy added in Phase 5)
# uv run mypy src/
```

### Level 2: Package Management

```bash
# Verify UV lock file generation
uv lock

# Verify dependency installation
uv sync

# Verify no conflicting dependencies
uv tree
```

### Level 3: Configuration Validation

```bash
# Validate settings load successfully
uv run python -m src.test_config

# Verify settings structure
uv run python -c "from src.settings import load_settings, Settings; s = load_settings(); print(f'MongoDB: {s.mongodb_database}')"

# Verify provider info
uv run python -c "from src.providers import get_model_info; print(get_model_info())"
```

### Level 4: Manual Validation

1. **Environment Template Check**:
   ```bash
   diff .env.example .env
   ```
   - Verify .env has actual credentials where .env.example has placeholders

2. **Gitignore Check**:
   ```bash
   git check-ignore .env
   ```
   - Should output ".env" (protected from commits)

3. **Documentation Review**:
   - Open README.md and verify all PostgreSQL references removed
   - Confirm MongoDB Atlas index creation instructions present
   - Verify UV commands are correct

4. **Directory Structure**:
   ```bash
   ls -la src/
   ```
   - Should show: __init__.py, settings.py, providers.py, test_config.py

---

## ACCEPTANCE CRITERIA

- [x] pyproject.toml created with UV configuration and all dependencies
- [x] Dependencies install successfully with `uv sync`
- [x] .gitignore protects .env file and virtual environments
- [x] .env.example provides complete template without credentials
- [x] src/ directory structure created
- [x] src/settings.py loads MongoDB-specific settings from .env
- [x] src/providers.py copied from examples/ with correct import paths
- [x] src/test_config.py validates configuration successfully
- [x] README.md updated with MongoDB setup instructions
- [x] All validation commands pass with zero errors
- [x] Configuration validation script provides clear feedback
- [x] Error messages guide users to fix .env file issues
- [x] No actual credentials committed to repository
- [x] Code follows type safety and documentation standards from CLAUDE.md

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] pyproject.toml validates with `uv lock`
- [ ] Dependencies install with `uv sync`
- [ ] .gitignore prevents .env commits
- [ ] .env.example has no real credentials
- [ ] src/__init__.py created (empty module)
- [ ] src/settings.py loads successfully
- [ ] src/providers.py imports work correctly
- [ ] src/test_config.py runs and validates configuration
- [ ] README.md has MongoDB setup instructions
- [ ] All validation commands executed successfully
- [ ] No syntax or import errors
- [ ] Manual testing confirms settings load from .env
- [ ] Acceptance criteria all met
- [ ] Code reviewed for quality and type safety

---

## NOTES

### Design Decisions

**PyMongo vs Motor**: Using PyMongo 4.10+ native async API instead of Motor because Motor was deprecated in May 2025. PyMongo's AsyncMongoClient provides better performance by using Python asyncio directly instead of delegating to thread pools.

**UV vs pip**: Using UV for faster dependency resolution (10-100x faster than pip), built-in virtual environment management, and lock file support for reproducible builds.

**Settings-First Approach**: Validating configuration before attempting any MongoDB connections. This "fail fast" approach catches environment issues early before investing time in code changes.

### Critical Dependencies

1. **MongoDB Atlas Indexes**: MUST be created in Atlas UI - cannot be created programmatically via PyMongo/Motor. This is a MongoDB Atlas limitation.

2. **Embedding Dimensions**: `text-embedding-3-small` uses 1536 dimensions. If changing embedding model, update `embedding_dimension` in settings AND MongoDB vector index `numDimensions`.

3. **Python Version**: Requires 3.10+ for:
   - Type hint syntax (e.g., `list[float]` instead of `List[float]`)
   - Async/await improvements
   - Pydantic 2.x compatibility

### Security Considerations

- `.env` file MUST be gitignored (contains MongoDB Atlas credentials and API keys)
- Use `.env.example` as template with placeholder values
- `mask_credential()` function in test_config.py ensures credentials not printed to console
- MongoDB Atlas connection strings include username/password - handle carefully

### Next Phase Dependencies

Phase 2 (MongoDB Connection) requires:
- Phase 1 completion (this phase)
- MongoDB Atlas cluster created
- Network access configured in Atlas (IP whitelist or 0.0.0.0/0 for dev)
- Database user created in Atlas with read/write permissions

### Performance Notes

- UV dependency installation ~10x faster than pip
- Configuration validation takes <1 second
- No network calls in Phase 1 (validation only checks .env file)

### Future Enhancements (Not in MVP)

- CI/CD pipeline with GitHub Actions
- Docker containerization
- Automated MongoDB Atlas setup via Terraform
- Configuration validation in pre-commit hooks
