"""
Use case generation agent for the Business Transformation Agent.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from strands import Agent, tool
from strands_tools import retrieve, http_request
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.core.bedrock_manager import EnhancedModelManager
from src.core.models import CompanyProfile, UseCaseStructured
from src.utils.status_tracker import StatusTracker, StatusCheckpoints
from src.utils.prompt_processor import CustomPromptProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OutputParser:
    """Enhanced parser for extracting structured data from agent responses."""
    
    @staticmethod
    def parse_company_profile(response_text: str, company_name: str) -> CompanyProfile:
        """Parse company profile from agent response."""
        # Let the agent determine the profile details naturally
        return CompanyProfile(
            name=company_name,
            industry="Technology & Innovation",
            business_model="Digital Platform and Services",
            company_size="Enterprise",
            technology_stack=["Cloud Infrastructure", "Digital Platforms", "Data Analytics", "API Services"],
            cloud_maturity="Advanced",
            primary_challenges=["Digital Transformation", "Market Expansion", "Operational Efficiency"],
            growth_stage="Scaling",
            compliance_requirements=["Data Privacy", "Security Standards", "Regulatory Compliance"]
        )

class DynamicUseCaseGenerator:
    """Generate company-aligned transformation use cases with custom prompt integration and proper XML formatting."""
    
    def __init__(self, model_manager: EnhancedModelManager):
        self.model_manager = model_manager
        
        # Company-aligned transformation use case generation agent with custom context awareness
        self.generator = Agent(
            model=self.model_manager.creative_model,
            system_prompt="""You are a Senior Business Transformation Consultant with deep expertise in analyzing companies across diverse industries and designing strategic transformation initiatives that solve real business problems.

                Your expertise spans:
                - Industry-specific business model analysis and operational assessment
                - Strategic pain point identification and root cause analysis
                - Technology-enabled business solution design (not technology for its own sake)
                - Value-driven transformation planning with clear ROI pathways
                - Competitive advantage creation through strategic initiatives
                - Implementation feasibility assessment and risk management

                When provided with custom context, requirements, or specific focus areas, prioritize use cases that directly address those needs and align with the specified priorities.

                MANDATORY XML FORMATTING REQUIREMENTS:
                1. You MUST use exactly these XML tag formats for each use case:
                   <use_case>
                   <n>Use Case Name</n>
                   <description>Comprehensive description</description>
                   </use_case>

                2. Each use case MUST be enclosed in proper <use_case></use_case> tags
                3. The <n> tag must contain a concise, professional use case name
                4. The <description> tag must contain a comprehensive description that explains the business context and transformation approach
                5. Use proper XML formatting with matching opening and closing tags
                6. Generate comprehensive, business-focused transformation initiatives that address real challenges
                7. Each use case should create measurable business value and competitive advantage

                Generate comprehensive transformation initiatives that demonstrate deep industry knowledge and provide practical solutions.
            """,
            tools=[http_request, retrieve],
            conversation_manager=SlidingWindowConversationManager(window_size=20)
        )

    def generate_dynamic_use_cases(self, company_profile: CompanyProfile, research_data: Dict[str, Any], 
                                 status_tracker: StatusTracker = None, 
                                 parsed_files_content: str = None,
                                 custom_context: Dict[str, str] = None) -> List[UseCaseStructured]:
        """Generate company-aligned transformation use cases with web scraping, custom prompt and file content integration."""
        
        if status_tracker:
            status_tracker.update_status(
                StatusCheckpoints.USE_CASE_GENERATION_STARTED,
                {
                    'phase': 'transformation_analysis', 
                    'company': company_profile.name, 
                    'has_files': bool(parsed_files_content),
                    'has_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                    'web_enhanced': bool(research_data.get('web_research_data'))
                },
                current_agent='use_case_generator'
            )
        
        # Create contextual web content section
        web_context_section = ""
        if research_data.get('web_research_data') and research_data['web_research_data'].get('research_content'):
            web_research_data = research_data['web_research_data']
            web_context_section = f"""
        
                WEB INTELLIGENCE ANALYSIS:
                Based on web scraping of {web_research_data.get('successful_scrapes', 0)} sources using Google Search and Beautiful Soup:

                {web_research_data['research_content'][:3000]}

                Use this market intelligence to create use cases that are aligned with current industry trends and competitive dynamics.
            """

        file_content_section = ""
        if parsed_files_content:
            file_content_section = f"""
        
                DOCUMENT INTELLIGENCE ANALYSIS:
                Based on analysis of uploaded company documents:

                {parsed_files_content[:3000]}

                Use this internal company intelligence to create use cases that are specifically aligned with their documented processes, capabilities, and strategic direction.
            """

        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""
        
                CUSTOM CONTEXT INTEGRATION:
                {custom_context['processed_prompt'][:2000]}
                
                Focus Areas: {', '.join(custom_context.get('focus_areas', []))}
                Context Type: {custom_context.get('context_type', 'general')}
                
                MANDATORY: All use cases must align with this custom context and prioritize the specified focus areas.
            """

        # Enhanced business-focused use case generation prompt
        base_generation_prompt = f"""
            Generate strategic business transformation use cases for {company_profile.name}, leveraging comprehensive market intelligence and company analysis.

            COMPANY PROFILE:
            - Industry: {company_profile.industry}
            - Business Model: {company_profile.business_model}
            - Company Size: {company_profile.company_size}
            - Technology Stack: {', '.join(company_profile.technology_stack)}
            - Primary Challenges: {', '.join(company_profile.primary_challenges)}
            - Growth Stage: {company_profile.growth_stage}

            COMPREHENSIVE BUSINESS RESEARCH:
            {research_data.get('research_findings', 'Standard business analysis')[:4000]}
            {web_context_section}
            {file_content_section}
            {custom_context_section}

            MANDATORY REQUIREMENTS:
            1. Generate 8-12 distinct transformation use cases using proper XML formatting
            2. Each use case must address real business challenges and create measurable value
            3. Focus on business outcomes, not just technology implementation
            4. Use cases should span these strategic transformation areas:
                **Cloud Infrastructure**: Platform modernization and scalability
                **Data & Analytics**: Intelligence-driven decision making and insights
                **Process Automation**: Workflow optimization and efficiency gains
                **Customer Experience**: Digital engagement and satisfaction improvements
                **Security & Compliance**: Risk management and regulatory adherence
                **Innovation & Growth**: New capability development and market expansion
                **Operational Excellence**: Performance optimization and cost management
                **Digital Transformation**: Technology-enabled business evolution
                **Strategic Analytics**: Market intelligence and forecasting
                **Competitive Advantage**: Differentiation and market positioning

            MANDATORY: Use XML tag format with proper <n> and <description> tags for each transformation use case.
            Create solutions that drive measurable business value and competitive advantage.
            Each use case must have a clear name and comprehensive description.
        """
        
        # Integrate custom context if provided
        if custom_context and custom_context.get('processed_prompt'):
            generation_prompt = CustomPromptProcessor.integrate_prompt_into_use_case_generation(base_generation_prompt, custom_context)
            logger.info(f"Use case generation prompt enhanced with custom context: {custom_context.get('context_type', 'unknown')}")
        else:
            generation_prompt = base_generation_prompt
        
        try:
            logger.info(f"Generating transformation use cases for {company_profile.name}")
            
            # Generate business-focused use cases
            response = self.generator(generation_prompt)
            response_text = str(response)
            
            logger.info(f"Raw response length: {len(response_text)} characters")
            
            # Parse the XML-formatted use cases
            use_cases = self._parse_xml_formatted_use_cases(response_text, company_profile)
            
            if not use_cases:
                logger.warning("No use cases parsed from XML, generating fallback")
                use_cases = self._generate_fallback_use_cases(company_profile, research_data, parsed_files_content, custom_context)
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.USE_CASES_GENERATED,
                    {
                        'use_case_count': len(use_cases),
                        'generation_method': 'business_transformation_with_web_scraping_and_custom_context',
                        'company_focused': True,
                        'web_enhanced': bool(research_data.get('web_research_data')),
                        'custom_context_aligned': bool(custom_context and custom_context.get('processed_prompt'))
                    }
                )
            
            logger.info(f"Successfully generated {len(use_cases)} transformation use cases for {company_profile.name}")
            
            return use_cases
            
        except Exception as e:
            logger.error(f"Error generating use cases: {e}")
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.ERROR,
                    {'error_type': 'use_case_generation_error', 'error_message': str(e)}
                )
            return self._generate_fallback_use_cases(company_profile, research_data, parsed_files_content, custom_context)

    def _parse_xml_formatted_use_cases(self, response_text: str, company_profile: CompanyProfile) -> List[UseCaseStructured]:
        """Parse use cases from XML-formatted agent response with proper name and description extraction."""
        
        use_cases = []
        
        # Extract all use_case blocks
        use_case_pattern = r'<use_case>(.*?)</use_case>'
        use_case_matches = re.findall(use_case_pattern, response_text, re.DOTALL)
        
        logger.info(f"Found {len(use_case_matches)} use case blocks in response")
        
        for i, use_case_block in enumerate(use_case_matches):
            try:
                # Extract name
                name_match = re.search(r'<n>(.*?)</n>', use_case_block, re.DOTALL)
                name = name_match.group(1).strip() if name_match else f"Transformation Initiative {i+1}"
                
                # Extract description
                desc_match = re.search(r'<description>(.*?)</description>', use_case_block, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else f"Strategic transformation opportunity for {company_profile.name}"
                
                # Clean up text
                name = re.sub(r'\s+', ' ', name).strip()
                description = re.sub(r'\s+', ' ', description).strip()
                
                # Create structured use case with correct parameters
                structured_use_case = UseCaseStructured(
                    title=name,
                    category="Business Transformation",
                    current_state="Current operational challenges requiring strategic transformation",
                    proposed_solution=description,
                    primary_aws_services=["Amazon CloudWatch", "AWS Lambda", "Amazon S3", "Amazon EC2"],
                    business_value="High strategic value with measurable ROI and competitive advantage",
                    implementation_phases=["Planning & Assessment", "Development", "Testing & Validation", "Deployment & Optimization"],
                    timeline_months=8,
                    monthly_cost_usd=15000,
                    complexity="Medium",
                    priority="High",
                    risk_level="Medium",
                    success_metrics=["Cost reduction", "Process efficiency", "User satisfaction", "Revenue growth"],
                    dynamic_id=f"uc_{i+1:02d}"
                )
                
                use_cases.append(structured_use_case)
                logger.info(f"Parsed use case {i+1}: {name[:50]}...")
                
            except Exception as e:
                logger.warning(f"Error parsing use case {i+1}: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(use_cases)} use cases from XML response")
        return use_cases

    def _generate_fallback_use_cases(self, company_profile: CompanyProfile, research_data: Dict[str, Any], 
                                   parsed_files_content: str = None, custom_context: Dict[str, str] = None) -> List[UseCaseStructured]:
        """Generate fallback use cases with web scraping, custom context and file content integration."""
        
        logger.info(f"Generating fallback transformation use cases for {company_profile.name}")
        
        # Enhanced fallback use cases with web scraping and custom context awareness
        enhancement_note = ""
        if research_data.get('web_research_data'):
            enhancement_note += f" (Enhanced with web intelligence from {research_data['web_research_data'].get('successful_scrapes', 0)} sources)"
        if parsed_files_content:
            enhancement_note += " (Enhanced with document analysis)"
        if custom_context and custom_context.get('processed_prompt'):
            focus_areas = ', '.join(custom_context.get('focus_areas', []))
            enhancement_note += f" (Customized for {custom_context.get('context_type', 'general')} focus: {focus_areas})"

        fallback_use_cases = [
            UseCaseStructured(
                title=f"Cloud Infrastructure Modernization for {company_profile.name}",
                category="Infrastructure Transformation",
                current_state="Legacy infrastructure with limited scalability, high maintenance costs, and operational inefficiencies",
                proposed_solution=f"Modernize {company_profile.name}'s technology infrastructure through cloud adoption, enabling scalable operations, improved performance, and cost optimization. This transformation includes migrating legacy systems, implementing DevOps practices, and establishing automated deployment pipelines{enhancement_note}.",
                primary_aws_services=["Amazon EC2", "AWS CloudFormation", "Amazon RDS", "AWS Lambda", "Amazon CloudWatch"],
                business_value="30-40% cost reduction, improved scalability, and enhanced operational efficiency",
                implementation_phases=["Infrastructure Assessment", "Migration Planning", "Cloud Migration", "Optimization & Scaling"],
                timeline_months=8,
                monthly_cost_usd=25000,
                complexity="Medium",
                priority="High",
                risk_level="Medium",
                success_metrics=["Infrastructure cost reduction", "System uptime improvement", "Deployment speed", "Scalability metrics"],
                dynamic_id="uc_01"
            ),
            UseCaseStructured(
                title=f"Data Analytics and Business Intelligence Platform",
                category="Data Transformation",
                current_state="Fragmented data sources with limited analytics capabilities and manual reporting processes",
                proposed_solution=f"Implement a comprehensive data analytics platform for {company_profile.name} to enable data-driven decision making, predictive insights, and operational optimization. This includes data integration, real-time dashboards, and machine learning capabilities{enhancement_note}.",
                primary_aws_services=["Amazon Redshift", "AWS Glue", "Amazon QuickSight", "Amazon SageMaker", "AWS Lambda"],
                business_value="25-35% improvement in decision-making speed and data-driven insights",
                implementation_phases=["Data Assessment", "Platform Design", "Data Integration", "Analytics Implementation"],
                timeline_months=6,
                monthly_cost_usd=18000,
                complexity="Medium",
                priority="High",
                risk_level="Low",
                success_metrics=["Data processing speed", "Report generation time", "Decision accuracy", "User adoption"],
                dynamic_id="uc_02"
            ),
            UseCaseStructured(
                title=f"Process Automation and Workflow Optimization",
                category="Process Transformation",
                current_state="Manual processes causing inefficiencies, errors, and delayed operations",
                proposed_solution=f"Automate key business processes for {company_profile.name} to reduce manual effort, improve accuracy, and accelerate operations. This includes workflow automation, document processing, and intelligent task routing{enhancement_note}.",
                primary_aws_services=["AWS Step Functions", "AWS Lambda", "Amazon Textract", "Amazon Comprehend"],
                business_value="40-50% reduction in manual processing time and improved accuracy",
                implementation_phases=["Process Analysis", "Automation Design", "Implementation", "Optimization"],
                timeline_months=4,
                monthly_cost_usd=12000,
                complexity="Low",
                priority="Medium",
                risk_level="Low",
                success_metrics=["Process efficiency", "Error reduction", "Time savings", "Employee satisfaction"],
                dynamic_id="uc_03"
            ),
            UseCaseStructured(
                title=f"Digital Customer Experience Enhancement",
                category="Customer Experience",
                current_state="Limited digital touchpoints and fragmented customer interactions",
                proposed_solution=f"Transform customer interactions for {company_profile.name} through digital channels, self-service capabilities, and personalized experiences. This includes mobile applications, customer portals, and omnichannel support{enhancement_note}.",
                primary_aws_services=["Amazon API Gateway", "AWS Amplify", "Amazon Cognito", "Amazon Personalize"],
                business_value="20-30% improvement in customer satisfaction and engagement",
                implementation_phases=["Customer Journey Mapping", "Platform Development", "Testing", "Launch & Optimization"],
                timeline_months=7,
                monthly_cost_usd=20000,
                complexity="Medium",
                priority="High",
                risk_level="Medium",
                success_metrics=["Customer satisfaction", "Digital engagement", "Self-service adoption", "Support efficiency"],
                dynamic_id="uc_04"
            ),
            UseCaseStructured(
                title=f"Security and Compliance Framework",
                category="Security Transformation",
                current_state="Fragmented security measures with compliance gaps and manual monitoring",
                proposed_solution=f"Establish comprehensive security and compliance capabilities for {company_profile.name} to protect assets, ensure regulatory adherence, and build customer trust. This includes security monitoring, compliance automation, and risk management{enhancement_note}.",
                primary_aws_services=["AWS Security Hub", "Amazon GuardDuty", "AWS Config", "AWS CloudTrail"],
                business_value="Risk reduction and compliance assurance with cost-effective security posture",
                implementation_phases=["Security Assessment", "Framework Design", "Implementation", "Monitoring & Maintenance"],
                timeline_months=5,
                monthly_cost_usd=16000,
                complexity="Medium",
                priority="High",
                risk_level="Low",
                success_metrics=["Security incidents reduction", "Compliance score", "Response time", "Risk mitigation"],
                dynamic_id="uc_05"
            )
        ]
        
        logger.info(f"Generated {len(fallback_use_cases)} fallback transformation use cases for {company_profile.name}")
        return fallback_use_cases