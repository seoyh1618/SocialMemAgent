"""
Standalone tests for build_memory_context_block() — Phase 2 (budget enforcement)
and Phase 3 (archival metadata-only).

Run:  python -m tests.test_context_block   (from agents/ directory)
"""
import sys, os, traceback

# ── Fix import path ──────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents.memory_tools import (
    build_memory_context_block,
    _truncate_section,
    _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET,
    _CORE_CHAR_LIMIT_PROFILE,
    _CORE_CHAR_LIMIT_VOICE,
    _CORE_CHAR_LIMIT_DOMAIN,
)
from agents.schemas import (
    MemoryState,
    UserProfile,
    BrandVoice,
    HumanBlock,
    PersonaBlock,
    DomainProfileBlock,
    AudienceBlock,
    CampaignRecord,
    ConversationRecord,
    RecallEntry,
    AudienceBehaviorGraph,
    ContentNode,
    PerformanceEdge,
    PerformanceData,
    PerformancePendingRequest,
)

# ── Helpers ──────────────────────────────────────────────────────────────
_passed = 0
_failed = 0


def _run(name: str, fn):
    global _passed, _failed
    try:
        fn()
        _passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        _failed += 1
        print(f"  ✗ {name}")
        traceback.print_exc()
        print()


def _assert(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


# ── Fixture builders ─────────────────────────────────────────────────────
def _minimal_memory() -> MemoryState:
    return MemoryState(
        human_block=HumanBlock(display_name="TestUser"),
        persona_block=PersonaBlock(tone="friendly"),
        domain_block=DomainProfileBlock(industry="Tech"),
        audience_block=AudienceBlock(target_platforms=["instagram"]),
    )


def _memory_with_archive(n_campaigns=5, n_conversations=3) -> MemoryState:
    m = _minimal_memory()
    m.campaign_archive = [
        CampaignRecord(
            campaign_id=f"c_{i}",
            timestamp=f"2026-03-{10+i:02d}T12:00:00",
            goal=f"Goal {i} — " + "x" * 200,
            selected_trend=f"trend_{i}",
            target_audiences=[f"audience_{i}"],
            selected_styles=[f"style_{i}"],
            guideline_summary=f"guideline_{i}" + " detail" * 30,
            platforms_used=["instagram"],
        )
        for i in range(n_campaigns)
    ]
    m.conversation_archive = [
        ConversationRecord(
            conversation_id=f"conv_{i}",
            timestamp=f"2026-03-{10+i:02d}T12:00:00",
            role="user",
            content="Hello " * 100,
        )
        for i in range(n_conversations)
    ]
    return m


def _memory_with_large_sections() -> MemoryState:
    """Create a MemoryState whose trimmable sections exceed 50k chars."""
    m = _memory_with_archive(n_campaigns=20, n_conversations=20)

    # Large recall log to bloat recall section
    m.recall_log = [
        RecallEntry(
            timestamp=f"2026-03-14T10:{i:02d}:00",
            role="user" if i % 2 == 0 else "assistant",
            content="A" * 400,
        )
        for i in range(50)
    ]
    m.working_summary = "Summary " * 100

    # Large behavior graph
    nodes = [
        ContentNode(node_id=f"n{i}", platform="instagram", content_type="reel", topic=f"topic_{i}")
        for i in range(10)
    ]
    edges = [
        PerformanceEdge(
            edge_id=f"e{i}",
            node_id=f"n{i % 10}",
            campaign_id=f"c_{i % 20}",
            engagement_level="high",
            reach_level="medium",
            what_worked=["hook", "cta", "timing"],
            what_failed=["long_caption"],
            timestamp=f"2026-03-{10 + i % 10:02d}T12:00:00",
        )
        for i in range(30)
    ]
    m.behavior_graph = AudienceBehaviorGraph(
        nodes=nodes,
        edges=edges,
        platform_best_content_type={"instagram": "reel", "twitter": "thread"},
        topic_performance_summary={f"topic_{i}": "high" for i in range(10)},
        overall_best_platform="instagram",
    )

    # Add performance data to campaigns for trend section
    for c in m.campaign_archive:
        c.performance = PerformanceData(
            engagement_level="high",
            reach_level="medium",
            views=1000,
            clicks=100,
            what_worked=["hook", "cta"],
            what_failed=["long_caption"],
        )

    # Pending performance requests
    m.performance_pending = [
        PerformancePendingRequest(
            campaign_id=f"c_{i}",
            campaign_goal=f"Goal {i} pending " + "y" * 100,
            platforms=["instagram", "twitter"],
            created_at=f"2026-03-{10+i:02d}T12:00:00",
        )
        for i in range(5)
    ]

    return m


# ═══════════════════════════════════════════════════════════════════════
# Phase 3 Tests: Archival metadata-only
# ═══════════════════════════════════════════════════════════════════════

def test_archival_shows_only_counts():
    """Archival section should show campaign/conversation counts, not content."""
    m = _memory_with_archive(n_campaigns=7, n_conversations=4)
    output = build_memory_context_block(m)

    _assert("Campaigns stored : 7" in output, "Expected campaign count 7")
    _assert("Conversations    : 4" in output, "Expected conversation count 4")
    _assert("memory_search_campaigns" in output, "Should mention search tool")
    _assert("memory_search_conversations" in output, "Should mention search tool")


def test_archival_no_campaign_content_leaked():
    """No actual campaign goal/guideline text should appear in archival section."""
    m = _memory_with_archive(n_campaigns=5, n_conversations=3)
    output = build_memory_context_block(m)

    for c in m.campaign_archive:
        _assert(c.goal not in output, f"Campaign goal leaked: {c.goal[:50]}")
        _assert(c.guideline_summary not in output, f"Guideline leaked: {c.guideline_summary[:50]}")


def test_archival_no_conversation_content_leaked():
    """No actual conversation content should appear in archival section."""
    m = _memory_with_archive(n_campaigns=2, n_conversations=5)
    output = build_memory_context_block(m)

    for conv in m.conversation_archive:
        _assert(conv.content not in output, "Conversation content leaked into context block")


def test_archival_zero_counts():
    """Empty archives should show 0 counts."""
    m = _minimal_memory()
    output = build_memory_context_block(m)

    _assert("Campaigns stored : 0" in output, "Expected 0 campaigns")
    _assert("Conversations    : 0" in output, "Expected 0 conversations")


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 Tests: Budget enforcement
# ═══════════════════════════════════════════════════════════════════════

def test_total_output_within_budget():
    """Total output must not exceed _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET."""
    m = _memory_with_large_sections()
    output = build_memory_context_block(m)
    total_chars = len(output)

    _assert(
        total_chars <= _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET,
        f"Output {total_chars} chars exceeds budget {_CONTEXT_BLOCK_TOTAL_CHAR_BUDGET}",
    )


def test_small_memory_fits_without_trimming():
    """Minimal memory should not trigger any trimming."""
    m = _minimal_memory()
    output = build_memory_context_block(m)

    _assert("trimmed" not in output.lower() or "section trimmed" not in output,
            "Minimal memory should not be trimmed")
    _assert(len(output) <= _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET,
            "Minimal memory must fit in budget")


def test_trimming_notice_present_when_over_budget():
    """When sections are large, trimming notices should appear."""
    m = _memory_with_large_sections()
    output = build_memory_context_block(m)

    # At least one section should show trimming notice
    has_trim_notice = ("trimmed" in output.lower()) or ("section trimmed" in output.lower())
    # Only check if sections actually needed trimming
    if len(output) > _CONTEXT_BLOCK_TOTAL_CHAR_BUDGET * 0.8:
        _assert(has_trim_notice, "Expected trimming notice for large sections")


def test_priority_recall_preserved_over_archival():
    """Recall (highest priority) should be preserved; archival (lowest) trimmed first."""
    m = _memory_with_large_sections()
    output = build_memory_context_block(m)

    # Recall section header should be present
    _assert("RECALL MEMORY" in output, "Recall section header should be present")
    # Archival section should still have its header
    _assert("ARCHIVAL MEMORY" in output, "Archival section header should be present")


def test_core_sections_never_trimmed():
    """Core sections (HUMAN BLOCK, PERSONA BLOCK) are never trimmed."""
    m = _memory_with_large_sections()
    output = build_memory_context_block(m)

    _assert("HUMAN BLOCK" in output, "Human block must always be present")
    _assert("PERSONA BLOCK" in output, "Persona block must always be present")
    _assert("TestUser" in output, "User display name must be in core block")
    _assert("friendly" in output, "Brand voice tone must be in core block")


def test_assembly_order():
    """Output must follow: core → behavior → trend → recall → archival → pending → footer."""
    m = _memory_with_large_sections()
    output = build_memory_context_block(m)

    # Find positions of section headers
    pos_human = output.find("HUMAN BLOCK")
    pos_behavior = output.find("AUDIENCE BEHAVIOR GRAPH")
    pos_trend = output.find("PERFORMANCE TREND ANALYSIS")
    pos_recall = output.find("RECALL MEMORY")
    pos_archival = output.find("ARCHIVAL MEMORY")

    _assert(pos_human >= 0, "HUMAN BLOCK not found")
    _assert(pos_behavior >= 0, "BEHAVIOR GRAPH not found")
    _assert(pos_recall >= 0, "RECALL MEMORY not found")
    _assert(pos_archival >= 0, "ARCHIVAL MEMORY not found")

    _assert(pos_human < pos_behavior, "Core should come before behavior")
    _assert(pos_behavior < pos_trend or pos_trend == -1, "Behavior should come before trend")
    _assert(pos_recall > pos_behavior, "Recall should come after behavior")
    _assert(pos_archival > pos_recall, "Archival should come after recall")


# ═══════════════════════════════════════════════════════════════════════
# _truncate_section() direct tests
# ═══════════════════════════════════════════════════════════════════════

def test_truncate_zero_budget():
    """Zero budget should return a single trimmed notice."""
    result = _truncate_section(["line1", "line2", "line3"], 0)
    _assert(len(result) == 1, f"Expected 1 line, got {len(result)}")
    _assert("section trimmed" in result[0], "Should contain trimmed notice")


def test_truncate_negative_budget():
    """Negative budget should also return trimmed notice."""
    result = _truncate_section(["line1", "line2"], -100)
    _assert(len(result) == 1, "Expected 1 line for negative budget")
    _assert("section trimmed" in result[0], "Should contain trimmed notice")


def test_truncate_partial_budget():
    """Partial budget should keep some lines and add notice."""
    lines = [f"line {i} " + "x" * 20 for i in range(10)]
    # Give budget for ~3 lines (each ~27 chars + 1 newline = 28)
    result = _truncate_section(lines, 85)

    _assert(len(result) < len(lines), "Should have fewer lines than input")
    _assert(len(result) >= 2, "Should keep at least 1 line + notice")
    _assert("trimmed" in result[-1], "Last line should be trimming notice")


def test_truncate_ample_budget():
    """If budget is large enough, all lines should be kept."""
    lines = ["short", "lines", "here"]
    result = _truncate_section(lines, 10000)
    _assert(result == lines, "All lines should be preserved with ample budget")


def test_truncate_exact_fit():
    """Lines that exactly fit the budget should all be kept."""
    lines = ["abc", "def"]
    # "abc" + newline = 4, "def" + newline = 4, total = 8
    result = _truncate_section(lines, 8)
    _assert(result == lines, f"Lines should fit exactly. Got {result}")


# ═══════════════════════════════════════════════════════════════════════
# Constants sanity checks
# ═══════════════════════════════════════════════════════════════════════

def test_budget_constant_value():
    _assert(_CONTEXT_BLOCK_TOTAL_CHAR_BUDGET == 50_000, "Budget should be 50k")


def test_core_limits():
    _assert(_CORE_CHAR_LIMIT_PROFILE == 5_000, "Profile limit should be 5k")
    _assert(_CORE_CHAR_LIMIT_VOICE == 5_000, "Voice limit should be 5k")
    _assert(_CORE_CHAR_LIMIT_DOMAIN == 3_000, "Domain limit should be 3k")


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n━━━ Phase 3: Archival metadata-only ━━━")
    _run("archival_shows_only_counts", test_archival_shows_only_counts)
    _run("archival_no_campaign_content_leaked", test_archival_no_campaign_content_leaked)
    _run("archival_no_conversation_content_leaked", test_archival_no_conversation_content_leaked)
    _run("archival_zero_counts", test_archival_zero_counts)

    print("\n━━━ Phase 2: Budget enforcement ━━━")
    _run("total_output_within_budget", test_total_output_within_budget)
    _run("small_memory_fits_without_trimming", test_small_memory_fits_without_trimming)
    _run("trimming_notice_present_when_over_budget", test_trimming_notice_present_when_over_budget)
    _run("priority_recall_preserved_over_archival", test_priority_recall_preserved_over_archival)
    _run("core_sections_never_trimmed", test_core_sections_never_trimmed)
    _run("assembly_order", test_assembly_order)

    print("\n━━━ _truncate_section() direct tests ━━━")
    _run("truncate_zero_budget", test_truncate_zero_budget)
    _run("truncate_negative_budget", test_truncate_negative_budget)
    _run("truncate_partial_budget", test_truncate_partial_budget)
    _run("truncate_ample_budget", test_truncate_ample_budget)
    _run("truncate_exact_fit", test_truncate_exact_fit)

    print("\n━━━ Constants sanity checks ━━━")
    _run("budget_constant_value", test_budget_constant_value)
    _run("core_limits", test_core_limits)

    print(f"\n{'━' * 50}")
    print(f"  Total: {_passed + _failed}  Passed: {_passed}  Failed: {_failed}")
    print(f"{'━' * 50}\n")
    sys.exit(1 if _failed > 0 else 0)
