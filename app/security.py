"""
Safety module for prompt handling and validation.
This module provides functions to validate and sanitize user prompts before they are processed by the AI model.
"""

import re
from typing import Optional
from langsmith import traceable

class PromptSenitizer:

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions\s*:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
        r"reveal\s+(your|the)\s+(system|instructions|prompt)",
        r"you\s+are\s+now\s+(DAN|jailbroken)",
    ]

    def __init__(self):
        self.compiled_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in self.INJECTION_PATTERNS
            ]

    def check(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Check if the input text contains any prompt injection patterns.
        Returns a tuple of (is_safe, matched_pattern).
        """
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return False, f"Blocked Prompt Injection: {pattern.pattern}"
        return True, None

    def clean(self, text: str) -> str:
        """
        Clean the input text by removing any prompt injection patterns.
        Returns the cleaned text.
        """
        for pattern in self.compiled_patterns:
            text = pattern.sub("", text)
        return text.strip()

