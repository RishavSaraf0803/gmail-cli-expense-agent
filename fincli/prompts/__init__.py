"""
Prompt management module for versioned, testable prompts.
"""
from fincli.prompts.prompt_manager import (
    PromptManager,
    get_prompt_manager,
    PromptTemplate
)

__all__ = [
    "PromptManager",
    "get_prompt_manager",
    "PromptTemplate"
]
