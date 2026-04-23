"""
Input Guardrail
Checks user inputs for safety violations.
"""

from typing import Dict, Any, List
import re


class InputGuardrail:
    """
    Guardrail for checking input safety.

    TODO: YOUR CODE HERE
    - Integrate with Guardrails AI or NeMo Guardrails
    - Define validation rules
    - Implement custom validators
    - Handle different types of violations
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize input guardrail.
        """
        self.config = config
        safety_cfg = config.get("safety", {})
        self.system_topic = config.get("system", {}).get("topic", "HCI Research").lower()
        self.min_query_length = safety_cfg.get("min_query_length", 5)
        self.max_query_length = safety_cfg.get("max_query_length", 2000)

        self.allowed_topic_keywords = [
            "hci", "ux", "ui", "user interface", "accessibility", "ar", "vr",
            "xai", "explainable ai", "education", "design", "interaction",
            "human computer interaction", "usability", "trust", "privacy"
        ]

    def validate(self, query: str) -> Dict[str, Any]:
        """
        Validate input query.
        """
        violations = []
        normalized = (query or "").strip()
        lowered = normalized.lower()

        if len(normalized) < self.min_query_length:
            violations.append({
                "validator": "length",
                "category": "off_topic_queries",
                "reason": "Query too short",
                "severity": "low"
            })

        if len(normalized) > self.max_query_length:
            violations.append({
                "validator": "length",
                "category": "off_topic_queries",
                "reason": "Query too long",
                "severity": "medium"
            })

        violations.extend(self._check_toxic_language(lowered))
        violations.extend(self._check_prompt_injection(lowered))
        violations.extend(self._check_relevance(lowered))

        action = "allow"
        if any(v.get("severity") == "high" for v in violations):
            action = "refuse"
        elif violations:
            action = "warn"

        return {
            "valid": not any(v.get("severity") == "high" for v in violations),
            "violations": violations,
            "sanitized_input": normalized,
            "action": action,
        }

    def _check_toxic_language(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for toxic/harmful language.
        """
        violations = []
        harmful_patterns = [
            r"\b(hack|exploit|bypass|weapon|malware|phish|ddos)\b",
            r"\b(make a bomb|poison|kill|harm someone)\b",
        ]

        for pattern in harmful_patterns:
            if re.search(pattern, text):
                violations.append({
                    "validator": "harmful_request",
                    "category": "harmful_content",
                    "reason": "Input appears to request harmful or dangerous assistance.",
                    "severity": "high"
                })

        return violations

    def _check_prompt_injection(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for prompt injection attempts.
        """
        violations = []

        injection_patterns = [
            "ignore previous instructions",
            "disregard previous instructions",
            "forget everything",
            "reveal the system prompt",
            "show hidden instructions",
            "developer:",
            "system:",
            "sudo",
        ]

        for pattern in injection_patterns:
            if pattern in text:
                violations.append({
                    "validator": "prompt_injection",
                    "category": "prompt_injection",
                    "reason": f"Potential prompt injection attempt detected: '{pattern}'",
                    "severity": "high"
                })

        return violations

    def _check_relevance(self, query: str) -> List[Dict[str, Any]]:
        """
        Check if query is relevant to the system's purpose.
        """
        violations = []

        if not query:
            return violations

        if any(keyword in query for keyword in self.allowed_topic_keywords):
            return violations

        research_words = ["research", "literature", "paper", "study", "design", "interface", "user"]
        if not any(word in query for word in research_words):
            violations.append({
                "validator": "topic_relevance",
                "category": "off_topic_queries",
                "reason": f"Query does not appear relevant to the configured system topic ({self.system_topic}).",
                "severity": "medium"
            })

        return violations
