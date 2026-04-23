"""
Safety Manager
Coordinates safety guardrails and logs safety events.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json

from pathlib import Path
from src.guardrails.input_guardrail import InputGuardrail
from src.guardrails.output_guardrail import OutputGuardrail


class SafetyManager:
    """
    Manages safety guardrails for the multi-agent system.

    TODO: YOUR CODE HERE
    - Integrate with Guardrails AI or NeMo Guardrails
    - Define safety policies
    - Implement logging of safety events
    - Handle different violation types with appropriate responses
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize safety manager.

        Args:
            config: Full configuration dictionary
        """
        self.full_config = config
        self.config = config.get("safety", config)
        self.enabled = self.config.get("enabled", True)
        self.log_events = self.config.get("log_events", True)
        self.logger = logging.getLogger("safety")

        # Safety event log
        self.safety_events: List[Dict[str, Any]] = []

        # Prohibited categories
        self.prohibited_categories = self.config.get("prohibited_categories", [
            "harmful_content",
            "personal_attacks",
            "misinformation",
            "off_topic_queries"
        ])

        # Violation response strategy
        self.on_violation = self.config.get("on_violation", {})

        # Initialize guardrails
        self.input_guardrail = InputGuardrail(self.full_config)
        self.output_guardrail = OutputGuardrail(self.full_config)

        # Safety log path
        self.log_file = (
            self.config.get("safety_log_file")
            or self.config.get("safety_log")
            or self.full_config.get("logging", {}).get("safety_log")
        )
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

    def check_input_safety(self, query: str) -> Dict[str, Any]:
        """
        Check if input query is safe to process.
        """
        if not self.enabled:
            return {"safe": True, "query": query, "violations": [], "action": "allow"}

        result = self.input_guardrail.validate(query)
        safe = result.get("valid", True)
        action = result.get("action", "allow")

        if (not safe or result.get("violations")) and self.log_events:
            self._log_safety_event("input", query, result.get("violations", []), safe)

        return {
            "safe": safe,
            "query": result.get("sanitized_input", query),
            "violations": result.get("violations", []),
            "action": action,
        }

    def check_output_safety(
        self,
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Check if output response is safe to return.
        """
        if not self.enabled:
            return {"safe": True, "response": response, "violations": [], "action": "allow"}

        result = self.output_guardrail.validate(response, sources or [])
        safe = result.get("valid", True)
        action = result.get("action", "allow")

        if (not safe or result.get("violations")) and self.log_events:
            self._log_safety_event("output", response, result.get("violations", []), safe)

        return {
            "safe": safe,
            "violations": result.get("violations", []),
            "response": result.get("sanitized_output", response),
            "action": action,
        }

    def _sanitize_response(self, response: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize response by removing or redacting unsafe content.
        """
        sanitized = response

        for violation in violations:
            if violation.get("validator") == "pii":
                for match in violation.get("matches", []):
                    sanitized = sanitized.replace(match, "[REDACTED]")

        if any(v.get("severity") == "high" for v in violations):
            return self.on_violation.get(
                "message",
                "I cannot provide this response due to safety policies."
            )

        return sanitized

    def _log_safety_event(
        self,
        event_type: str,
        content: str,
        violations: List[Dict[str, Any]],
        is_safe: bool
    ):
        """
        Log a safety event.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "safe": is_safe,
            "violations": violations,
            "content_preview": content[:100] + "..." if len(content) > 100 else content
        }

        self.safety_events.append(event)
        self.logger.warning(f"Safety event: {event_type} - safe={is_safe}")

        if self.log_file and self.log_events:
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                self.logger.error(f"Failed to write safety log: {e}")

    def get_safety_events(self) -> List[Dict[str, Any]]:
        """Get all logged safety events."""
        return self.safety_events

    def get_safety_stats(self) -> Dict[str, Any]:
        """
        Get statistics about safety events.

        Returns:
            Dictionary with safety statistics
        """
        total = len(self.safety_events)
        input_events = sum(1 for e in self.safety_events if e["type"] == "input")
        output_events = sum(1 for e in self.safety_events if e["type"] == "output")
        violations = sum(1 for e in self.safety_events if not e["safe"])

        return {
            "total_events": total,
            "input_checks": input_events,
            "output_checks": output_events,
            "violations": violations,
            "violation_rate": violations / total if total > 0 else 0
        }

    def clear_events(self):
        """Clear safety event log."""
        self.safety_events = []
