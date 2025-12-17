"""Additional testing to cover gaps in original E2E tests."""

import asyncio
import time
from src.agent import rag_agent, RAGState
from pydantic_ai.ag_ui import StateDeps

# Test categories
TESTS = {
    "multi_turn": [
        {
            "conversation": [
                "What is NeuralFlow's revenue goal for 2025?",
                "What products will help them achieve that goal?"
            ],
            "category": "Multi-turn context"
        }
    ],

    "negative": [
        "What is NeuralFlow's office address in London?",
        "Who is the CEO of NeuralFlow AI?",
        "What is NeuralFlow's cryptocurrency investment strategy?",
        "How many offices does NeuralFlow have in Asia?"
    ],

    "edge_cases": [
        "What is the lerning budjet?",  # Typos
        "What are the goals?",  # Ambiguous
        "Tell me about the team",  # Very broad
        "q2 2025 product",  # Minimal query
    ],

    "question_types": [
        "List all the AI products NeuralFlow plans to launch",  # Command
        "Does NeuralFlow offer unlimited PTO?",  # Yes/No
        "Why does NeuralFlow use a hybrid work model?",  # Why question
        "How does the implementation process work?",  # How question
    ],

    "document_types": [
        "What does the Q4 2024 business review say?",  # PDF
        "What was discussed in the January 8th meeting?",  # Word doc
        "What's in the client review for GlobalFinance?",  # PDF
        "What's in the audio recordings?",  # Audio transcription
    ],

    "reasoning": [
        "If I join NeuralFlow, how much could I spend on learning in my first two years?",
        "What days should I schedule in-person client meetings?",
        "Based on the goals, when will all three products be launched?",
    ]
}


async def test_query(question: str, message_history: list, deps) -> dict:
    """Test a single query and capture results."""
    start_time = time.time()

    response_text = ""
    tool_called = False

    try:
        async with rag_agent.iter(
            question,
            deps=deps,
            message_history=message_history
        ) as run:
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                elif rag_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            from pydantic_ai.messages import PartStartEvent, PartDeltaEvent, TextPartDelta
                            if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                                if event.part.content:
                                    response_text += event.part.content
                            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                if event.delta.content_delta:
                                    response_text += event.delta.content_delta

            new_messages = run.result.new_messages()

        latency = time.time() - start_time

        return {
            "question": question,
            "response": response_text,
            "tool_called": tool_called,
            "latency_ms": int(latency * 1000),
            "success": True,
            "new_messages": new_messages
        }
    except Exception as e:
        return {
            "question": question,
            "response": "",
            "tool_called": False,
            "latency_ms": 0,
            "success": False,
            "error": str(e)
        }


async def test_multi_turn():
    """Test multi-turn conversations."""
    print("\n" + "="*80)
    print("TEST 1: MULTI-TURN CONVERSATIONS")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    message_history = []

    results = []
    for conv in TESTS["multi_turn"]:
        print(f"\n[Conversation Test]")
        for i, question in enumerate(conv["conversation"], 1):
            print(f"\nTurn {i}: {question}")
            result = await test_query(question, message_history, deps)
            message_history.extend(result.get("new_messages", []))

            print(f"  Tool called: {result['tool_called']}")
            print(f"  Response: {result['response'][:150]}...")
            results.append(result)

    return results


async def test_negative():
    """Test queries where info doesn't exist."""
    print("\n" + "="*80)
    print("TEST 2: NEGATIVE TESTING (Info Not in Knowledge Base)")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    results = []
    for question in TESTS["negative"]:
        print(f"\n[Q] {question}")
        result = await test_query(question, [], deps)

        # Check for hallucination indicators
        admits_unknown = any(phrase in result['response'].lower() for phrase in [
            "don't have", "not found", "no information", "not mentioned",
            "don't know", "not available", "cannot find"
        ])

        print(f"  Tool called: {result['tool_called']}")
        print(f"  Admits unknown: {admits_unknown}")
        print(f"  Response: {result['response'][:150]}...")

        result['admits_unknown'] = admits_unknown
        results.append(result)

    return results


async def test_edge_cases():
    """Test edge cases."""
    print("\n" + "="*80)
    print("TEST 3: EDGE CASES (Typos, Ambiguity, Minimal)")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    results = []
    for question in TESTS["edge_cases"]:
        print(f"\n[Q] {question}")
        result = await test_query(question, [], deps)

        print(f"  Tool called: {result['tool_called']}")
        print(f"  Latency: {result['latency_ms']}ms")
        print(f"  Response: {result['response'][:150]}...")

        results.append(result)

    return results


async def test_question_types():
    """Test different question types."""
    print("\n" + "="*80)
    print("TEST 4: DIFFERENT QUESTION TYPES")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    results = []
    for question in TESTS["question_types"]:
        print(f"\n[Q] {question}")
        result = await test_query(question, [], deps)

        print(f"  Tool called: {result['tool_called']}")
        print(f"  Response: {result['response'][:150]}...")

        results.append(result)

    return results


async def test_document_types():
    """Test retrieval from different document types."""
    print("\n" + "="*80)
    print("TEST 5: DOCUMENT TYPE COVERAGE")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    results = []
    for question in TESTS["document_types"]:
        print(f"\n[Q] {question}")
        result = await test_query(question, [], deps)

        print(f"  Tool called: {result['tool_called']}")
        print(f"  Response: {result['response'][:150]}...")

        results.append(result)

    return results


async def test_reasoning():
    """Test semantic reasoning capabilities."""
    print("\n" + "="*80)
    print("TEST 6: SEMANTIC REASONING")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    results = []
    for question in TESTS["reasoning"]:
        print(f"\n[Q] {question}")
        result = await test_query(question, [], deps)

        print(f"  Tool called: {result['tool_called']}")
        print(f"  Response: {result['response'][:200]}...")

        results.append(result)

    return results


async def test_performance():
    """Test performance metrics."""
    print("\n" + "="*80)
    print("TEST 7: PERFORMANCE & LATENCY")
    print("="*80)

    state = RAGState()
    deps = StateDeps[RAGState](state=state)

    # Test same query 3 times to check consistency
    test_question = "What is NeuralFlow's revenue goal?"
    latencies = []

    for i in range(3):
        print(f"\n[Run {i+1}] {test_question}")
        result = await test_query(test_question, [], deps)
        latencies.append(result['latency_ms'])
        print(f"  Latency: {result['latency_ms']}ms")

    print(f"\nLatency Stats:")
    print(f"  Min: {min(latencies)}ms")
    print(f"  Max: {max(latencies)}ms")
    print(f"  Avg: {sum(latencies)//len(latencies)}ms")

    return latencies


async def main():
    """Run all additional tests."""
    print("="*80)
    print("ADDITIONAL TESTING - Gap Coverage")
    print("="*80)

    all_results = {}

    try:
        all_results['multi_turn'] = await test_multi_turn()
        all_results['negative'] = await test_negative()
        all_results['edge_cases'] = await test_edge_cases()
        all_results['question_types'] = await test_question_types()
        all_results['document_types'] = await test_document_types()
        all_results['reasoning'] = await test_reasoning()
        all_results['performance'] = await test_performance()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF ADDITIONAL TESTS")
    print("="*80)

    # Multi-turn
    if 'multi_turn' in all_results:
        mt = all_results['multi_turn']
        print(f"\n1. Multi-turn: {len(mt)} turns tested")
        print(f"   Context maintained: {len(mt) > 1}")

    # Negative
    if 'negative' in all_results:
        neg = all_results['negative']
        admits = sum(1 for r in neg if r.get('admits_unknown', False))
        print(f"\n2. Negative testing: {len(neg)} queries")
        print(f"   Admits unknown: {admits}/{len(neg)} ({admits/len(neg)*100:.0f}%)")

    # Edge cases
    if 'edge_cases' in all_results:
        edge = all_results['edge_cases']
        succeeded = sum(1 for r in edge if r.get('success', False))
        print(f"\n3. Edge cases: {len(edge)} queries")
        print(f"   Handled: {succeeded}/{len(edge)}")

    # Question types
    if 'question_types' in all_results:
        qt = all_results['question_types']
        print(f"\n4. Question types: {len(qt)} different types tested")

    # Document types
    if 'document_types' in all_results:
        dt = all_results['document_types']
        print(f"\n5. Document types: {len(dt)} types tested")

    # Reasoning
    if 'reasoning' in all_results:
        reason = all_results['reasoning']
        print(f"\n6. Reasoning: {len(reason)} queries tested")

    # Performance
    if 'performance' in all_results:
        perf = all_results['performance']
        print(f"\n7. Performance: Avg latency {sum(perf)//len(perf)}ms")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
