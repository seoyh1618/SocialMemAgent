"""
MemGPT Memory Agent — manages persistent user memory across sessions.
"""

from google.adk.agents import Agent

from ...memory_tools import (
    memory_get_core_profile,
    memory_update_user_profile,
    memory_update_brand_voice,
    memory_archive_campaign,
    memory_search_campaigns,
    memory_get_recent_campaigns,
    memory_update_working_summary,
    memory_add_performance_notes,
)
from . import prompt

memory_agent = Agent(
    name="memory_agent",
    model="gemini-2.5-flash",
    description=prompt.MEMORY_AGENT_DESCRIPTION,
    instruction=prompt.MEMORY_AGENT_INSTRUCTIONS,
    tools=[
        memory_get_core_profile,
        memory_update_user_profile,
        memory_update_brand_voice,
        memory_archive_campaign,
        memory_search_campaigns,
        memory_get_recent_campaigns,
        memory_update_working_summary,
        memory_add_performance_notes,
    ],
    output_key="memory_agent_output",
)
