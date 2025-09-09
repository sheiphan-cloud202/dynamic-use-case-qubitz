"""
Dataclasses for the Business Transformation Agent.
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class CompanyProfile:
    """Company profile data structure."""
    name: str
    industry: str
    business_model: str
    company_size: str
    technology_stack: List[str]
    cloud_maturity: str
    primary_challenges: List[str]
    growth_stage: str
    compliance_requirements: List[str]

@dataclass
class UseCaseStructured:
    """Structured business transformation use case data."""
    title: str
    category: str
    current_state: str
    proposed_solution: str
    primary_aws_services: List[str]
    business_value: str
    implementation_phases: List[str]
    timeline_months: int
    monthly_cost_usd: int
    complexity: str
    priority: str
    risk_level: str
    success_metrics: List[str]
    dynamic_id: str = ""

@dataclass
class UseCase:
    """Legacy use case format for compatibility."""
    id: str
    title: str
    description: str
    business_value: str
    technical_requirements: List[str]
    priority: str
    complexity: str
    citations: List[str] = field(default_factory=list)
    aws_services: List[str] = field(default_factory=list)
    implementation_approach: str = ""
    estimated_timeline: str = ""
    cost_estimate: str = ""
    current_implementation: str = ""
    proposed_solution: str = ""
    url: str = ""

@dataclass
class CompanyInfo:
    """Legacy company info format."""
    name: str
    url: str
    industry: str
    description: str
    size: str
    technologies: List[str]
    business_model: str
    additional_context: str = ""
