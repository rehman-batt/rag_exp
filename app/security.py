"""
Safety module for prompt handling and validation.
This module provides functions to validate and sanitize user prompts before they are processed by the AI model.
"""

import re
from typing import Optional
from langsmith import traceable

## To DO
 # Add Smarter JEV Based Prompt and Output Classifier
 

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

class PIIDetector:
    """
    Class to detect Personally Identifiable Information (PII) in text.
    """

    PATTERNS = {
        "email": re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),

        "phone": re.compile(
            r"\+?\d[\d\s-]{8,12}\d"
        ),

        "ssn": re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        ),

        "credit_card": re.compile(
            r"\b(?:\d[ -]?){12,15}\d\b"
        ),

        "ip_address": re.compile(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        ),
    }

    MASK_PATTERNS = {
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "ssn": "[SSN]",
        "credit_card": "[CREDIT_CARD]",
        "ip_address": "[IP_ADDRESS]",
    }

    def __init__(self):
        pass

    def detect(self, text: str) -> bool:
        """
        Detect if the input text contains any PII.
        Returns True if PII is detected, False otherwise.
        """
        patterns_found = {}

        for key, pattern in self.PATTERNS.items():
            if pattern.search(text):
                patterns_found[key] = True
            
        return len(patterns_found) > 0, patterns_found

    def mask(self, text: str) -> str:
        """
        Mask any detected PII in the input text.
        Returns the text with PII masked.
        """
        for key in ("credit_card", "ssn", "email", "ip_address", "phone"):
            pattern = self.PATTERNS[key]
            text = pattern.sub(self.MASK_PATTERNS[key], text)
        return text

class OutputSenitization:
    """
    Class to sanitize the output text from the AI model.
    This is a placeholder for future implementation of output sanitization logic.
    """

    def __init__(self):
        pass

    def sanitize(self, text: str) -> str:
        """
        Sanitize the output text.
        Returns the sanitized text.
        """
        # Placeholder for actual sanitization logic
        return text



class SecurityManager:
    """
    Security Manager to handle prompt sanitization and PII detection.
    """

    def __init__(self):
        self.prompt_sanitizer = PromptSenitizer()
        self.pii_detector = PIIDetector()
        # self.output_sanitizer = OutputSenitization()

    def process_input(self, prompt: str) -> tuple[bool, str, Optional[str]]:
        """
        Returns: is_safe, sanitized_prompt, warning_message
        """

        is_safe, matched_pattern = self.prompt_sanitizer.check(prompt)

        if not is_safe:
            return (False, "", f"Prompt Injection Detected: {matched_pattern}")

        # Clean prompt injection-like content if needed
        sanitized_prompt = self.prompt_sanitizer.clean(prompt)

        # Detect and mask PII
        contains_pii, pii_patterns = self.pii_detector.detect(sanitized_prompt)

        if contains_pii:
            sanitized_prompt = self.pii_detector.mask(sanitized_prompt)

            return (
                True, sanitized_prompt, f"PII detected and masked: {pii_patterns}"
            )

        return True, sanitized_prompt, None
        

    # def process_output(self, output: str) -> str:
    #     """
    #     Sanitize the output text from the AI model.
    #     Returns the sanitized output.
    #     """
    #     return self.output_sanitizer.sanitize(output)

