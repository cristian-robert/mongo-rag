"""Test RAG pipeline components without requiring LLM API."""

import asyncio
from src.dependencies import AgentDependencies
from src.tools import semantic_search, hybrid_search


class MockContext:
    """Mock context for search functions."""
    def __init__(self, deps):
        self.deps = deps


async def test_rag_pipeline():
    """Test the complete RAG pipeline: embedding + search + retrieval."""
    print("="*80)
    print("Testing RAG Pipeline Components")
    print("="*80)

    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)

    # Test queries that should find relevant content
    test_cases = [
        {
            "query": "MongoDB vector search",
            "min_results": 1,
            "description": "Technical query about MongoDB"
        },
        {
            "query": "company goals and mission",
            "min_results": 1,
            "description": "Company information query"
        },
        {
            "query": "technical architecture",
            "min_results": 1,
            "description": "Architecture documentation query"
        },
        {
            "query": "meeting notes",
            "min_results": 1,
            "description": "Meeting notes query"
        }
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test_case['description']}")
        print(f"Query: '{test_case['query']}'")

        try:
            # Test semantic search
            print("\n  Testing semantic search...")
            semantic_results = await semantic_search(ctx, test_case['query'], match_count=5)
            print(f"  Results: {len(semantic_results)}")

            if semantic_results:
                top_result = semantic_results[0]
                print(f"  Top result: {top_result.document_title}")
                print(f"  Similarity: {top_result.similarity:.3f}")
                print(f"  Content preview: {top_result.content[:100]}...")

            # Test hybrid search
            print("\n  Testing hybrid search...")
            hybrid_results = await hybrid_search(ctx, test_case['query'], match_count=5)
            print(f"  Results: {len(hybrid_results)}")

            if hybrid_results:
                top_result = hybrid_results[0]
                print(f"  Top result: {top_result.document_title}")
                print(f"  Similarity: {top_result.similarity:.3f}")

            # Validate
            if len(semantic_results) >= test_case['min_results']:
                print(f"\n  [PASS] Semantic search returned sufficient results")
            else:
                print(f"\n  [FAIL] Semantic search returned {len(semantic_results)} results, expected >= {test_case['min_results']}")
                all_passed = False

            if len(hybrid_results) >= test_case['min_results']:
                print(f"  [PASS] Hybrid search returned sufficient results")
            else:
                print(f"  [FAIL] Hybrid search returned {len(hybrid_results)} results, expected >= {test_case['min_results']}")
                all_passed = False

        except Exception as e:
            print(f"\n  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    await deps.cleanup()

    print("\n" + "="*80)
    if all_passed:
        print("SUCCESS: All RAG pipeline tests passed!")
        print("\nThe search and retrieval system is working correctly.")
        print("You can now test the full agent by:")
        print("  1. Verifying your LLM API key in .env is valid")
        print("  2. Running: uv run python -m src.cli")
    else:
        print("FAILURE: Some tests failed. Check errors above.")

    print("="*80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_rag_pipeline())
    exit(exit_code)
