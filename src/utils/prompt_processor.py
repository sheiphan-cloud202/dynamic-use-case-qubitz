"""
Custom prompt processing utility for the Business Transformation Agent.
"""

import re
from typing import Dict


class CustomPromptProcessor:
    """Utility class for processing custom prompts and integrating them into the system."""

    @staticmethod
    def process_custom_prompt(
        prompt: str, company_name: str, company_context: str = ""
    ) -> Dict[str, str]:
        """Process custom prompt and extract contextual information."""
        if not prompt or not prompt.strip():
            return {
                "processed_prompt": "",
                "context_type": "none",
                "focus_areas": [],
                "specific_requirements": "",
                "integration_notes": "No custom prompt provided",
            }

        prompt = prompt.strip()

        # Analyze prompt for context clues
        focus_areas = []
        context_type = "general"
        specific_requirements = ""

        # Check for specific focus areas
        if any(
            keyword in prompt.lower()
            for keyword in ["security", "compliance", "governance", "risk"]
        ):
            focus_areas.append("security_governance")
            context_type = "security_focused"

        if any(
            keyword in prompt.lower()
            for keyword in ["cost", "budget", "optimization", "efficiency"]
        ):
            focus_areas.append("cost_optimization")
            context_type = "cost_focused"

        if any(
            keyword in prompt.lower()
            for keyword in ["customer", "experience", "user", "satisfaction"]
        ):
            focus_areas.append("customer_experience")
            context_type = "customer_focused"

        if any(
            keyword in prompt.lower()
            for keyword in ["data", "analytics", "intelligence", "insights"]
        ):
            focus_areas.append("data_analytics")
            context_type = "data_focused"

        if any(
            keyword in prompt.lower()
            for keyword in ["automation", "workflow", "process", "efficiency"]
        ):
            focus_areas.append("process_automation")
            context_type = "automation_focused"

        if any(
            keyword in prompt.lower()
            for keyword in ["scale", "performance", "reliability", "availability"]
        ):
            focus_areas.append("scalability_performance")
            context_type = "performance_focused"

        # Extract specific requirements
        if "must" in prompt.lower() or "requirement" in prompt.lower():
            specific_requirements = prompt

        # Create processed prompt with company context
        processed_prompt = f"""
CUSTOM CONTEXT FOR {company_name}:
{prompt}

INTEGRATION NOTES:
- Focus Areas Identified: {", ".join(focus_areas) if focus_areas else "General transformation"}
- Context Type: {context_type}
- Specific Requirements: {specific_requirements if specific_requirements else "None specified"}
- Company Context: {company_context if company_context else "Standard business analysis"}

This custom context should be integrated into all analysis, research, and use case generation to ensure personalized recommendations that align with the specified requirements and focus areas.
"""

        return {
            "processed_prompt": processed_prompt,
            "context_type": context_type,
            "focus_areas": focus_areas,
            "specific_requirements": specific_requirements,
            "integration_notes": f"Custom prompt processed with {len(focus_areas)} focus areas identified",
        }

    @staticmethod
    def integrate_prompt_into_research(
        base_prompt: str, custom_context: Dict[str, str]
    ) -> str:
        """Integrate custom prompt context into research prompts."""
        if not custom_context.get("processed_prompt"):
            return base_prompt

        integration = f"""
        
CUSTOM CONTEXT INTEGRATION:
{custom_context["processed_prompt"]}

FOCUS AREAS TO EMPHASIZE:
{", ".join(custom_context.get("focus_areas", ["General business transformation"]))}

SPECIFIC REQUIREMENTS TO ADDRESS:
{custom_context.get("specific_requirements", "None specified")}

Please ensure all research, analysis, and recommendations align with this custom context and address the specified focus areas and requirements.
        """

        return base_prompt + integration

    @staticmethod
    def integrate_prompt_into_use_case_generation(
        base_prompt: str, custom_context: Dict[str, str]
    ) -> str:
        """Integrate custom prompt context into use case generation prompts."""
        if not custom_context.get("processed_prompt"):
            return base_prompt

        integration = f"""
        
CUSTOM CONTEXT FOR USE CASE GENERATION:
{custom_context["processed_prompt"]}

PRIORITIZATION GUIDELINES:
- Context Type: {custom_context.get("context_type", "general")}
- Focus Areas: {", ".join(custom_context.get("focus_areas", ["General"]))}
- Specific Requirements: {custom_context.get("specific_requirements", "None")}

MANDATORY ALIGNMENT:
Every use case generated must align with the custom context provided. Prioritize use cases that directly address the specified focus areas and requirements. Ensure recommendations are tailored to the custom context rather than generic transformation initiatives.
        """

        return base_prompt + integration
