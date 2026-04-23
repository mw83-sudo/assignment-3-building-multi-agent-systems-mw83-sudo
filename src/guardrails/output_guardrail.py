"""
Output Guardrail
Checks system outputs for safety violations.
"""

from typing import Dict, Any, List
import re


class OutputGuardrail:
    """
    Guardrail for checking output safety.

    TODO: YOUR CODE HERE
    - Integrate with Guardrails AI or NeMo Guardrails
    - Check for harmful content in responses
    - Verify factual consistency
    - Detect potential misinformation
    - Remove PII (personal identifiable information)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output guardrail.
        """
        self.config = config
        self.harmful_keywords = [
            "build a bomb",
            "malware",
            "phishing kit",
            "steal credentials",
            "violent attack"
        ]

    def validate(self, response: str, sources: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate output response.
        """
        sources = sources or []
        violations = []

        pii_violations = self._check_pii(response)
        violations.extend(pii_violations)

        harmful_violations = self._check_harmful_content(response)
        violations.extend(harmful_violations)

        bias_violations = self._check_bias(response)
        violations.extend(bias_violations)

        consistency_violations = self._check_factual_consistency(response, sources)
        violations.extend(consistency_violations)

        action = "allow"
        sanitized_output = response

        if any(v.get("severity") == "high" for v in violations):
            action = "refuse"
            sanitized_output = self.config.get("safety", {}).get("on_violation", {}).get(
                "message",
                "I cannot provide this response due to safety policies."
            )
        elif violations:
            action = "sanitize"
            sanitized_output = self._sanitize(response, violations)

        return {
            "valid": action == "allow",
            "violations": violations,
            "sanitized_output": sanitized_output,
            "action": action,
        }

    def _check_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for personally identifiable information.

        TODO: YOUR CODE HERE
        Suggested implementation:
        - Expand regex checks for emails, phone numbers, SSNs, addresses, etc.
        - Use a stronger PII detection library if desired
        - Return violation metadata needed for redaction
        """
        violations = []

        # Simple regex patterns for common PII
        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        }

        for pii_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                violations.append({
                    "validator": "pii",
                    "pii_type": pii_type,
                    "reason": f"Contains {pii_type}",
                    "severity": "high",
                    "matches": matches
                })

        return violations

    def _check_harmful_content(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for harmful or inappropriate content.
        """
        violations = []
        lowered = text.lower()

        for keyword in self.harmful_keywords:
            if keyword in lowered:
                violations.append({
                    "validator": "harmful_content",
                    "category": "harmful_content",
                    "reason": f"Potentially unsafe instruction detected: {keyword}",
                    "severity": "high"
                })

        return violations

    def _check_factual_consistency(
        self,
        response: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check if response is consistent with sources.
        """
        violations = []

        has_reference_section = "references" in response.lower() or "[source:" in response.lower()
        if has_reference_section and not sources:
            violations.append({
                "validator": "citation_grounding",
                "category": "misinformation",
                "reason": "Response contains citations or a references section, but no source metadata was captured.",
                "severity": "medium"
            })

        placeholder_patterns = [
            r"\bSmith, J\.",
            r"\bJenkins, A\.",
            r"\bCase Studies on Accessibility\b",
        ]
        if any(re.search(pattern, response) for pattern in placeholder_patterns) and not sources:
            violations.append({
                "validator": "fabricated_reference",
                "category": "misinformation",
                "reason": "Response appears to contain unsupported placeholder references.",
                "severity": "medium"
            })

        return violations

    def _check_bias(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for biased language.
        """
        violations = []
        lowered = text.lower()

        stereotype_patterns = [
            "all elderly users",
            "all disabled users",
            "obviously women",
            "obviously men",
        ]

        for phrase in stereotype_patterns:
            if phrase in lowered:
                violations.append({
                    "validator": "bias",
                    "category": "bias",
                    "reason": f"Potential stereotype or blanket generalization detected: {phrase}",
                    "severity": "medium"
                })

        return violations

    def _sanitize(self, text: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize text by removing/redacting violations.
        """
        sanitized = text

        for violation in violations:
            if violation.get("validator") == "pii":
                for match in violation.get("matches", []):
                    sanitized = sanitized.replace(match, "[REDACTED]")

        if any(v.get("validator") == "fabricated_reference" for v in violations):
            sanitized += "\n\n[Safety note: some references could not be verified from retrieved sources.]"

        return sanitized
