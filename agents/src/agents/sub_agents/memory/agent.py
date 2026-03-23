"""
MemGPT Memory Agent — manages persistent user memory across sessions.
"""

from google.adk.agents import Agent

from ...memory_tools import (
    memory_get_core_profile,
    memory_update_user_profile,
    memory_update_brand_voice,
    memory_update_domain_profile,
    memory_add_domain_knowledge,
    memory_update_audience_segment,
    memory_add_audience_trait,
    memory_get_audience_segments,
    memory_collect_performance,
    memory_get_performance_pending,
    memory_mark_performance_asked,
    memory_get_behavior_insights,
    memory_archive_campaign,
    memory_search_campaigns,
    memory_get_recent_campaigns,
    memory_archive_conversation,
    memory_search_conversations,
    memory_update_working_summary,
    memory_append_recall,
    memory_get_recall_log,
    memory_add_performance_notes,
    memory_record_generated_asset,
    memory_get_assets,
    memory_compress_context,
    memory_get_context_status,
)
from . import prompt

memory_agent = Agent(
    name="memory_agent",
    model="gemini-2.5-flash",
    description=prompt.MEMORY_AGENT_DESCRIPTION,
    instruction=prompt.MEMORY_AGENT_INSTRUCTIONS,
    tools=[
        # Core Memory — profile, voice, domain
        memory_get_core_profile,
        memory_update_user_profile,
        memory_update_brand_voice,
        memory_update_domain_profile,
        memory_add_domain_knowledge,
        # Audience
        memory_update_audience_segment,
        memory_add_audience_trait,
        memory_get_audience_segments,
        # Performance & Behavior
        memory_collect_performance,
        memory_get_performance_pending,
        memory_mark_performance_asked,
        memory_get_behavior_insights,
        # Archival — campaigns & conversations
        memory_archive_campaign,
        memory_search_campaigns,
        memory_get_recent_campaigns,
        memory_archive_conversation,
        memory_search_conversations,
        # Recall & Working Memory
        memory_update_working_summary,
        memory_append_recall,
        memory_get_recall_log,
        memory_add_performance_notes,
        # Assets
        memory_record_generated_asset,
        memory_get_assets,
        # Context Management
        memory_compress_context,
        memory_get_context_status,
    ],
    output_key="memory_agent_output",
)
