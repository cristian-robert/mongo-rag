"""Check MongoDB Atlas indexes configuration."""

import asyncio
from src.dependencies import AgentDependencies

async def main():
    deps = AgentDependencies()
    await deps.initialize()

    print("="*80)
    print("MongoDB Atlas Index Configuration")
    print("="*80)

    collection = deps.db[deps.settings.mongodb_collection_chunks]

    # List all indexes
    print("\n[Standard Indexes]")
    cursor = await collection.list_indexes()
    indexes = [idx async for idx in cursor]
    for idx in indexes:
        print(f"  - {idx.get('name')}: {idx.get('key')}")

    # Try to list search indexes (Atlas Search indexes are different)
    print("\n[Atlas Search Indexes]")
    print("(Note: Search indexes must be viewed in Atlas UI - they're not visible via standard listIndexes)")
    print(f"Expected vector index: {deps.settings.mongodb_vector_index}")
    print(f"Expected text index: {deps.settings.mongodb_text_index}")

    print("\n[IMPORTANT]")
    print("For $rankFusion to work, you MUST have:")
    print("  1. A Vector Search index (for $vectorSearch)")
    print("  2. An Atlas Search index (for $search with text)")
    print("\nBoth must be created in the Atlas UI:")
    print("  Atlas UI > Database > Search > Create Search Index")
    print("\nThe text_index should be configured with:")
    print("  - Index Type: Atlas Search (NOT Vector Search)")
    print("  - Field: content")
    print("  - Analyzer: lucene.standard")

    await deps.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
