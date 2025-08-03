"""Conflict resolution for multi-agent workflow disagreements."""

import logging
from typing import Any, cast

from coding_personas import CodingPersonas

logger = logging.getLogger(__name__)


class ConflictResolver:
    """Handles disagreements between agents and facilitates resolution."""

    def __init__(self, architect_persona=None):
        """Initialize conflict resolver with personas.

        Args:
            architect_persona: Architect persona for AI analysis tasks
        """
        self.architect_persona = architect_persona or CodingPersonas.architect()
        self.resolution_strategies = {
            "consensus": self._consensus_resolution,
            "expert_priority": self._expert_priority_resolution,
            "human_escalation": self._human_escalation,
        }

    def identify_conflicts(self, peer_reviews: dict[str, dict]) -> list[dict[str, Any]]:
        """Identify conflicts between agent reviews using AI analysis.

        Args:
            peer_reviews: Reviews from each agent

        Returns:
            List of identified conflicts
        """
        logger.info("Analyzing peer reviews for technical conflicts...")

        try:
            # Build conflict analysis prompt
            conflict_prompt = self._build_conflict_analysis_prompt(peer_reviews)

            # Get AI analysis of conflicts using injected persona
            conflict_analysis = self.architect_persona.ask(conflict_prompt)

            # Parse the response to extract structured conflicts
            conflicts = self._parse_conflict_analysis(conflict_analysis)

            logger.info(f"Identified {len(conflicts)} technical conflicts")
            return conflicts

        except Exception as e:
            logger.error(
                f"AI conflict analysis failed, falling back to keyword detection: {e}"
            )
            return self._fallback_conflict_detection(peer_reviews)

    def _build_conflict_analysis_prompt(self, peer_reviews: dict) -> str:
        """Build prompt for AI-powered conflict analysis."""

        prompt = """You are analyzing peer reviews from multiple software engineering agents to identify SPECIFIC TECHNICAL CONFLICTS.

TASK: Identify SPECIFIC technical disagreements between the agent reviews. Look for concrete contradictions, not just different emphasis.

FOCUS ON SPECIFIC DISAGREEMENTS:
1. **Architectural Conflicts**:
   - Agent A says "use Repository pattern" vs Agent B says "single class is enough"
   - Different class structures or inheritance hierarchies proposed

2. **Implementation Conflicts**:
   - Agent A: "start with SQLite" vs Agent B: "use JSON files first"
   - Different technology choices or implementation sequences

3. **Priority Conflicts**:
   - Agent A: "build tests first (TDD)" vs Agent B: "implement MVP then test"
   - Different development methodologies or ordering

4. **Technical Trade-offs**:
   - Agent A: "abstract base classes" vs Agent B: "concrete implementation only"
   - Complexity vs simplicity decisions

5. **Testing Conflicts**:
   - Agent A: "mock all GitHub API calls" vs Agent B: "use real API for tests"
   - Different testing strategies or coverage requirements

OUTPUT FORMAT for each REAL conflict found:
- **Conflict Type**: (architectural|implementation|priority|tradeoff|testing)
- **Description**: Specific technical disagreement (e.g., "Developer wants JSON files, Architect wants SQLite")
- **Agent A Position**: Exact recommendation with technical details
- **Agent B Position**: Contradicting recommendation with details
- **Technical Impact**: Specific implementation consequences
- **Severity**: (high|medium|low) based on implementation impact

PEER REVIEWS TO ANALYZE:

"""

        # Add peer reviews
        for agent_type, review in peer_reviews.items():
            review_content = review.get("peer_review", "")
            if review_content and review_content.strip():
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Review ---\n{review_content}\n"

        prompt += """

IMPORTANT: Only identify REAL conflicts where agents explicitly disagree or recommend contradictory approaches. Do not invent conflicts that don't exist.

If no significant conflicts exist, respond with: "NO_CONFLICTS_IDENTIFIED"

Otherwise, list each conflict clearly with the format above."""

        return prompt

    def _parse_conflict_analysis(self, analysis: str) -> list[dict]:
        """Parse AI conflict analysis into structured conflicts."""
        if "NO_CONFLICTS_IDENTIFIED" in analysis:
            return []

        conflicts = []

        # More robust parsing - handle various formats
        lines = analysis.split("\n")
        current_conflict: dict[str, Any] = {}

        for line in lines:
            line = line.strip()

            # Check for various separators that might indicate a new conflict
            if (
                not line
                or line.startswith("---")
                or line.startswith("###")
                or (
                    line.startswith("Conflict") and any(char.isdigit() for char in line)
                )
            ):
                # Save current conflict if it has required fields
                if current_conflict and self._is_valid_conflict(current_conflict):
                    conflicts.append(current_conflict)
                    current_conflict = {}
                continue

            # More flexible parsing for different formats
            if ":" in line:
                # Handle various formats with colons
                key_part = line.split(":", 1)[0].strip().lower()
                value_part = line.split(":", 1)[1].strip()

                if "type" in key_part and "conflict" in key_part:
                    current_conflict["type"] = value_part.strip("()[]").lower()
                elif "type" in key_part:
                    current_conflict["type"] = value_part.strip("()[]").lower()
                elif "description" in key_part:
                    current_conflict["description"] = value_part
                elif "agent a" in key_part or "position a" in key_part:
                    current_conflict["position_a"] = value_part
                elif "agent b" in key_part or "position b" in key_part:
                    current_conflict["position_b"] = value_part
                elif "impact" in key_part:
                    current_conflict["impact"] = value_part
                elif "severity" in key_part:
                    current_conflict["severity"] = value_part.strip("()[]").lower()

            # Also handle bullet points
            elif line.startswith("-") or line.startswith("*"):
                # Extract info from bullet points
                content = line.lstrip("- *").strip()
                if "vs" in content.lower() or "versus" in content.lower():
                    # This might be a position comparison
                    if "position_a" not in current_conflict:
                        current_conflict["description"] = content

        # Add final conflict if valid
        if current_conflict and self._is_valid_conflict(current_conflict):
            conflicts.append(current_conflict)

        # Ensure all conflicts have required fields with defaults
        for conflict in conflicts:
            conflict.setdefault("type", "general")
            conflict.setdefault("severity", "medium")
            conflict.setdefault("description", "Unspecified conflict")

        return conflicts

    def _is_valid_conflict(self, conflict: dict) -> bool:
        """Check if a conflict dict has minimum required fields."""
        return (
            "description" in conflict
            or "position_a" in conflict
            or "impact" in conflict
        )

    def _fallback_conflict_detection(self, peer_reviews: dict) -> list[dict]:
        """Fallback keyword-based conflict detection."""
        conflicts = []

        # Simple conflict detection based on keywords
        conflict_keywords = {
            "disagree",
            "incorrect",
            "wrong",
            "concern",
            "issue",
            "problem",
            "conflict",
            "contradict",
            "oppose",
            "reject",
            "alternative",
        }

        # Check for explicit disagreements
        for agent_type, review in peer_reviews.items():
            if review.get("status") != "success":
                continue

            review_content = review.get("peer_review", "").lower()

            # Look for conflict indicators
            for keyword in conflict_keywords:
                if keyword in review_content:
                    conflicts.append(
                        {
                            "type": "disagreement",
                            "source_agent": agent_type,
                            "description": f"{agent_type} expressed concerns or disagreement",
                            "content": review_content,
                            "severity": "medium",
                        }
                    )
                    break

        return conflicts

    def resolve_conflicts(
        self, conflicts: list[dict], peer_reviews: dict, strategy: str = "consensus"
    ) -> dict[str, Any]:
        """Resolve identified conflicts using specified strategy.

        Args:
            conflicts: List of conflicts to resolve
            peer_reviews: Original peer reviews
            strategy: Resolution strategy to use

        Returns:
            Resolution results
        """
        if not conflicts:
            return {
                "status": "no_conflicts",
                "resolution": "No conflicts detected",
                "recommendations": [],
            }

        if strategy not in self.resolution_strategies:
            strategy = "consensus"

        logger.info(f"Resolving {len(conflicts)} conflicts using {strategy} strategy")

        return cast(
            dict[str, Any],
            self.resolution_strategies[strategy](conflicts, peer_reviews),
        )

    def _consensus_resolution(
        self, conflicts: list[dict], peer_reviews: dict
    ) -> dict[str, Any]:
        """Resolve conflicts by finding consensus points."""
        recommendations = []

        for conflict in conflicts:
            conflict_type = conflict.get("type", "general")

            # Handle different conflict types with more flexibility
            if conflict_type in ["architectural", "architecture"]:
                resolution = self._resolve_architectural_conflict(conflict)
                recommendations.append(
                    {
                        "conflict": conflict.get(
                            "description", "Architectural disagreement"
                        ),
                        "resolution": resolution,
                        "action": "adopt_architecture",
                    }
                )

            elif conflict_type in ["implementation", "approach"]:
                resolution = self._resolve_implementation_conflict(conflict)
                recommendations.append(
                    {
                        "conflict": conflict.get(
                            "description", "Implementation approach disagreement"
                        ),
                        "resolution": resolution,
                        "action": "implementation_decision",
                    }
                )

            elif conflict_type in ["priority", "ordering"]:
                resolution = self._resolve_priority_conflict(conflict)
                recommendations.append(
                    {
                        "conflict": conflict.get(
                            "description", "Priority disagreement"
                        ),
                        "resolution": resolution,
                        "action": "prioritize_approach",
                    }
                )

            elif conflict_type in ["tradeoff", "complexity"]:
                resolution = self._resolve_tradeoff_conflict(conflict)
                recommendations.append(
                    {
                        "conflict": conflict.get("description", "Technical trade-off"),
                        "resolution": resolution,
                        "action": "balance_decision",
                    }
                )

            elif conflict_type == "testing":
                resolution = self._resolve_testing_conflict(conflict)
                recommendations.append(
                    {
                        "conflict": conflict.get(
                            "description", "Testing strategy disagreement"
                        ),
                        "resolution": resolution,
                        "action": "testing_approach",
                    }
                )

            else:
                # Generic resolution for unspecified types
                recommendations.append(
                    {
                        "conflict": conflict.get("description", "Unspecified conflict"),
                        "resolution": f"Review and address concerns: {conflict.get('impact', 'Consider all positions')}",
                        "action": "investigate_concern",
                    }
                )

        return {
            "status": "resolved",
            "strategy": "consensus",
            "resolution": "Conflicts resolved through consensus building",
            "recommendations": recommendations,
        }

    def _resolve_architectural_conflict(self, conflict: dict) -> str:
        """Resolve architectural conflicts with specific decisions."""
        desc = conflict.get("description", "").lower()

        if "abstract" in desc and "single" in desc:
            return "Use single CommentTracker class with CommentStorage interface for persistence abstraction (Architect's simplified design)"
        elif "repository" in desc:
            return "Implement Repository pattern with CommentInteractionRepository base class and SQLiteCommentRepository implementation"
        elif "restart" in desc or "insufficient" in desc:
            return "Proceed with current design but add explicit error handling and boundary definitions per Senior Engineer concerns"

        # Extract specific positions if available
        if "position_a" in conflict and "position_b" in conflict:
            return f"Combine approaches: {conflict['position_a']} for simplicity with {conflict['position_b']} for extensibility"

        return (
            "Adopt Architect's simplified single-class design with storage abstraction"
        )

    def _resolve_implementation_conflict(self, conflict: dict) -> str:
        """Resolve implementation approach conflicts with specific choices."""
        desc = conflict.get("description", "").lower()

        if "json" in desc and "sqlite" in desc:
            return "Start with FileCommentTracker using JSON (Week 1), migrate to SQLiteCommentTracker in Week 3 if needed"
        elif "base class" in desc:
            return "Use abstract base class CommentTracker with two implementations: FileCommentTracker and SQLiteCommentTracker"
        elif "storage" in desc:
            return "Implement FileCommentTracker first for MVP (1-2 days), add SQLite only when concurrent access issues arise"

        return "Follow Developer's iterative approach: JSON file storage first, database later based on actual requirements"

    def _resolve_priority_conflict(self, conflict: dict) -> str:
        """Resolve priority conflicts with specific development order."""
        desc = conflict.get("description", "").lower()

        if "tdd" in desc and "iterative" in desc:
            return "Hybrid approach: Write failing test for core tracking functionality first, then iterate on implementation (satisfies both Tester and Developer)"
        elif "methodology" in desc:
            return "Day 1: Core tracking with basic test, Day 2: Integration, Day 3: Comprehensive test suite"

        return "1. Implement mark_replied() and is_replied() methods\n2. Add GitHub integration\n3. Add persistence layer\n4. Comprehensive testing"

    def _resolve_tradeoff_conflict(self, conflict: dict) -> str:
        """Resolve technical trade-offs with specific decisions."""
        desc = conflict.get("description", "").lower()

        if "complexity" in desc:
            position_a = conflict.get("position_a", "")
            position_b = conflict.get("position_b", "")

            if position_a and position_b:
                return f"Start with {position_a} for MVP, evolve to {position_b} only if performance metrics justify it"

        return "JSON file for <1000 comments, SQLite for production scale, decision point at 2-week mark based on metrics"

    def _resolve_testing_conflict(self, conflict: dict) -> str:
        """Resolve testing strategy conflicts with specific test plan."""
        desc = conflict.get("description", "").lower()

        if "mock" in desc and "real" in desc:
            return "Use MockCommentTracker for unit tests, real GitHub API with test repository for integration tests (combines both approaches)"
        elif "coverage" in desc:
            return "Minimum 80% coverage for MVP, 90% before production deployment, focus on fallback scenario testing"

        return "Priority tests: 1) test_mark_replied_persists() 2) test_fallback_comment_tracked() 3) test_filter_excludes_replied()"

    def _expert_priority_resolution(
        self, conflicts: list[dict], peer_reviews: dict
    ) -> dict[str, Any]:
        """Resolve conflicts by giving priority to domain experts."""
        # Priority order: Architect > Senior Engineer > Developer > Tester
        priority_order = ["architect", "senior_engineer", "developer", "tester"]

        recommendations = []

        for conflict in conflicts:
            if conflict["type"] == "approach_contradiction":
                approaches = conflict["approaches"]

                # Find highest priority agent for each approach
                approach_priorities = {}
                for approach, agents in approaches.items():
                    min_priority = min(
                        [
                            priority_order.index(agent)
                            if agent in priority_order
                            else 99
                            for agent in agents
                        ]
                    )
                    approach_priorities[approach] = min_priority

                best_approach = min(approach_priorities.items(), key=lambda x: x[1])

                recommendations.append(
                    {
                        "conflict": conflict["description"],
                        "resolution": f"Adopt {best_approach[0]} approach (highest domain expertise)",
                        "action": "expert_decision",
                        "priority_agent": priority_order[best_approach[1]],
                    }
                )

        return {
            "status": "resolved",
            "strategy": "expert_priority",
            "resolution": "Conflicts resolved using domain expertise priority",
            "recommendations": recommendations,
        }

    def _human_escalation(
        self, conflicts: list[dict], peer_reviews: dict
    ) -> dict[str, Any]:
        """Escalate conflicts to human for resolution."""
        return {
            "status": "escalated",
            "strategy": "human_escalation",
            "resolution": "Conflicts require human decision",
            "conflicts": conflicts,
            "action": "human_review_required",
        }
