from google.adk.agents import Agent
from typing import List, Optional, Dict

from ...twitter_tools import advanced_search, get_trends

from . import prompt

idea_generation_agent = Agent(
    name="idea_generation_agent",
    model="gemini-2.5-flash",
    description=prompt.DESCRIPTION,
    instruction=prompt.INSTRUCTIONS,
    output_key="idea_generation_output",
    tools=[advanced_search, get_trends],
)
