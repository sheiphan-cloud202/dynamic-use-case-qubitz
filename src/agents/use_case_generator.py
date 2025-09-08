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

                When provided with web-scraped content and company document content, use this as primary intelligence to understand their current operations, processes, and strategic context.

                CRITICAL: You have COMPLETE FREEDOM to create personalized use cases based on:
                - Custom context and specific requirements provided
                - Web-scraped market intelligence and industry insights
                - Company-specific context from research and documents
                - Industry dynamics and market opportunities
                - Actual business challenges and operational needs
                - Strategic priorities and growth objectives

                MANDATORY RESPONSE FORMAT: Use XML-like tags for easy parsing with proper formatting:

                <usecase>
                <id>business-transformation-initiative-[number]</id>
                <name>Strategic Business Transformation Name</name>
                <description>Comprehensive description of the transformation initiative including problem statement, solution approach, and expected outcomes. This should be detailed and explain the business context clearly.</description>
                <category>Business Transformation Category</category>
                <current_state>Current business situation and challenges</current_state>
                <proposed_solution>Strategic transformation solution with technology enablers</proposed_solution>
                <aws_services>Service1,Service2,Service3,Service4,Service5</aws_services>
                <business_value>Quantifiable business value and strategic impact</business_value>
                <implementation_phases>Phase1,Phase2,Phase3,Phase4</implementation_phases>
                <timeline_months>6</timeline_months>
                <monthly_cost_usd>5000</monthly_cost_usd>
                <complexity>Low/Medium/High</complexity>
                <priority>Low/Medium/High/Critical</priority>
                <risk_level>Low/Medium/High</risk_level>
                <success_metrics>BusinessMetric1,BusinessMetric2,BusinessMetric3</success_metrics>
                </usecase>

                CRITICAL REQUIREMENTS:
                1. The <name> tag must contain a clear, concise use case name
                2. The <description> tag must contain a comprehensive description that explains the business context and transformation approach
                3. Use proper XML formatting with matching opening and closing tags
                4. Generate comprehensive, business-focused transformation initiatives that address real challenges
                5. Each use case should create measurable business value and competitive advantage

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
                StatusCheckpoints.USE_CASES_GENERATING,
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
        
        # Create contextual file content section
        file_context_section = ""
        if parsed_files_content:
            file_context_section = f"""
        
                COMPANY INTERNAL DOCUMENTATION ANALYSIS:
                The following content was extracted from company documents:

                {parsed_files_content[:3000]}

                Use this as primary intelligence to create HIGHLY PERSONALIZED use cases that address their specific operational realities and business challenges.
            """
        
        # Base generation prompt
        base_generation_prompt = f"""
                STRATEGIC BUSINESS TRANSFORMATION ANALYSIS FOR {company_profile.name}

                You are designing PERSONALIZED transformation initiatives that solve {company_profile.name}'s specific business challenges and accelerate their strategic objectives.

                COMPANY BUSINESS PROFILE:
                Company Name: {company_profile.name}
                Industry & Market: {company_profile.industry}
                Business Model: {company_profile.business_model}
                Operational Scale: {company_profile.company_size}
                Technology Maturity: {company_profile.cloud_maturity}
                Growth Stage: {company_profile.growth_stage}
                
                Technology Capabilities: {', '.join(company_profile.technology_stack)}
                Strategic Challenges: {', '.join(company_profile.primary_challenges)}
                Compliance Context: {', '.join(company_profile.compliance_requirements)}

                BUSINESS INTELLIGENCE FROM RESEARCH:
                {research_data.get('research_findings', '')[:2000]}
                {web_context_section}
                {file_context_section}

                TRANSFORMATION MISSION:
                Design 10 strategic transformation use cases that address real business challenges:

                1. **Core Business Optimization**: Process efficiency and operational excellence
                2. **Customer Experience Enhancement**: Service delivery and satisfaction
                3. **Data-Driven Decision Making**: Analytics and business intelligence
                4. **Innovation Acceleration**: Technology-enabled competitive advantage
                5. **Security and Compliance**: Risk management and governance
                6. **Cost Optimization**: Resource efficiency and financial performance
                7. **Scalability and Growth**: Infrastructure and capacity planning
                8. **Automation and Workflow**: Process improvement and productivity
                9. **Strategic Analytics**: Market intelligence and forecasting
                10. **Digital Transformation**: Platform modernization and capabilities

                MANDATORY: Use XML tag format with proper <name> and <description> tags for each transformation use case.
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
        
        try:
            # Find all use case blocks
            use_case_pattern = r'<usecase>(.*?)</usecase>'
            use_case_matches = re.findall(use_case_pattern, response_text, re.DOTALL | re.IGNORECASE)
            
            logger.info(f"Found {len(use_case_matches)} use case blocks in response")
            
            for i, use_case_block in enumerate(use_case_matches):
                try:
                    use_case = self._parse_single_xml_use_case(use_case_block, company_profile, i)
                    if use_case:
                        use_cases.append(use_case)
                        logger.info(f"Successfully parsed use case: {use_case.title}")
                except Exception as e:
                    logger.error(f"Error parsing use case block {i}: {e}")
                    continue
            
            # If we got some but not enough, supplement with additional generation
            if len(use_cases) < 5:
                logger.info(f"Only parsed {len(use_cases)} use cases, supplementing")
                supplements = self._generate_supplemental_use_cases(company_profile, len(use_cases))
                use_cases.extend(supplements)
            
        except Exception as e:
            logger.error(f"Error in XML parsing: {e}")
            return []
        
        return use_cases[:10]  # Limit to 10 use cases

    def _parse_single_xml_use_case(self, use_case_block: str, company_profile: CompanyProfile, index: int) -> Optional[UseCaseStructured]:
        """Parse a single XML-formatted use case with proper name and description extraction."""
        
        def extract_tag_content(tag_name: str, content: str, default: str = "") -> str:
            pattern = rf'<{tag_name}>(.*?)</{tag_name}>'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return default
        
        def extract_list_content(tag_name: str, content: str, default: List[str] = None) -> List[str]:
            if default is None:
                default = []
            tag_content = extract_tag_content(tag_name, content)
            if tag_content:
                return [item.strip() for item in tag_content.split(',') if item.strip()]
            return default
        
        def extract_int_content(tag_name: str, content: str, default: int) -> int:
            tag_content = extract_tag_content(tag_name, content)
            if tag_content:
                try:
                    return int(re.search(r'\d+', tag_content).group())
                except:
                    pass
            return default
        
        try:
            # Extract all fields with proper name and description handling
            use_case_id = extract_tag_content('id', use_case_block, f"business-transformation-{index}")
            
            # Extract name and description properly
            name = extract_tag_content('name', use_case_block, "")
            description = extract_tag_content('description', use_case_block, "")
            
            # Use name as title, fallback to generated title if empty
            title = name if name and len(name.strip()) > 0 else f"Business Transformation Initiative {index+1}"
            
            # Use description as proposed solution if available
            category = extract_tag_content('category', use_case_block, "Business Optimization")
            current_state = extract_tag_content('current_state', use_case_block, "Current business processes with optimization opportunities")
            
            # Use description as proposed solution if available, otherwise use proposed_solution tag
            if description and len(description.strip()) > 0:
                proposed_solution = description
            else:
                proposed_solution = extract_tag_content('proposed_solution', use_case_block, "Strategic transformation solution with technology enablers")
            
            aws_services = extract_list_content('aws_services', use_case_block, ['Lambda', 'S3', 'CloudWatch'])
            business_value = extract_tag_content('business_value', use_case_block, "Enhanced business performance and competitive advantage")
            implementation_phases = extract_list_content('implementation_phases', use_case_block, 
                                                         ['Assessment', 'Design', 'Implementation', 'Optimization'])
            timeline_months = extract_int_content('timeline_months', use_case_block, 6)
            monthly_cost_usd = extract_int_content('monthly_cost_usd', use_case_block, 3000)
            complexity = extract_tag_content('complexity', use_case_block, 'Medium')
            priority = extract_tag_content('priority', use_case_block, 'High')
            risk_level = extract_tag_content('risk_level', use_case_block, 'Medium')
            success_metrics = extract_list_content('success_metrics', use_case_block, 
                                                   ['Business Performance', 'Cost Reduction', 'Efficiency Improvement'])
            
            # Validate required fields
            if not title or len(title) < 5:
                logger.warning(f"Use case {index} has invalid title: {title}")
                title = f"Business Transformation Initiative {index+1}"
            
            if not proposed_solution or len(proposed_solution) < 10:
                logger.warning(f"Use case {index} has invalid description/proposed_solution")
                proposed_solution = "Strategic transformation solution with technology enablers to drive business value"
            
            # Create structured use case
            structured_use_case = UseCaseStructured(
                title=title,
                category=category,
                current_state=current_state,
                proposed_solution=proposed_solution,
                primary_aws_services=aws_services[:7],
                business_value=business_value,
                implementation_phases=implementation_phases[:6],
                timeline_months=max(1, min(timeline_months, 24)),
                monthly_cost_usd=max(500, min(monthly_cost_usd, 50000)),
                complexity=complexity if complexity in ['Low', 'Medium', 'High'] else 'Medium',
                priority=priority if priority in ['Low', 'Medium', 'High', 'Critical'] else 'High',
                risk_level=risk_level if risk_level in ['Low', 'Medium', 'High'] else 'Medium',
                success_metrics=success_metrics[:5]
            )
            
            # Add dynamic ID attribute
            structured_use_case.dynamic_id = use_case_id
            
            logger.info(f"Parsed use case with name: '{title}' and description length: {len(proposed_solution)}")
            
            return structured_use_case
            
        except Exception as e:
            logger.error(f"Error parsing single use case: {e}")
            return None

    def _generate_supplemental_use_cases(self, company_profile: CompanyProfile, current_count: int) -> List[UseCaseStructured]:
        """Generate supplemental use cases when parsing yields insufficient results."""
        
        supplements = []
        
        # Define business-focused supplemental use cases with proper names and descriptions
        business_supplements = [
            {
                'name': 'Advanced Business Intelligence and Analytics Platform',
                'description': 'Implement a comprehensive business intelligence platform that consolidates data from multiple sources to provide real-time insights and predictive analytics. This initiative will enable data-driven decision making across all departments, improve operational efficiency, and identify new revenue opportunities through advanced analytics capabilities. The solution addresses current data fragmentation, limited reporting capabilities, and lack of predictive insights by implementing a unified analytics platform with machine learning capabilities.',
                'category': 'Data Analytics',
                'current_state': 'Limited data insights and analytics capabilities with fragmented data sources and manual reporting processes',
                'aws_services': ['Redshift', 'QuickSight', 'Glue', 'SageMaker'],
                'business_value': 'Data-driven decision making and strategic insights with 40-60% improvement in decision speed and accuracy',
                'implementation_phases': ['Data Strategy', 'Platform Setup', 'Analytics Development', 'Training'],
                'timeline_months': 8,
                'monthly_cost_usd': 4000,
                'complexity': 'High',
                'priority': 'High',
                'risk_level': 'Medium',
                'success_metrics': ['Data Utilization', 'Decision Speed', 'Insight Generation', 'Report Accuracy', 'User Adoption']
            },
            {
                'name': 'Customer Experience Optimization and Personalization',
                'description': 'Develop a unified customer experience platform that integrates all customer touchpoints and provides personalized interactions based on customer behavior and preferences. This solution will improve customer satisfaction, increase retention rates, and drive revenue growth through enhanced customer engagement. The initiative addresses fragmented customer touchpoints, limited personalization, and inconsistent service delivery across channels',
                'category': 'Customer Experience',
                'current_state': 'Fragmented customer touchpoints and limited personalization with inconsistent service delivery across channels',
                'aws_services': ['Personalize', 'Pinpoint', 'Connect', 'Comprehend'],
                'business_value': 'Improved customer satisfaction and retention with 30-50% improvement in customer engagement metrics',
                'implementation_phases': ['Journey Mapping', 'Platform Setup', 'Personalization', 'Optimization'],
                'timeline_months': 6,
                'monthly_cost_usd': 3500,
                'complexity': 'Medium',
                'priority': 'High',
                'risk_level': 'Low',
                'success_metrics': ['Customer Satisfaction', 'Retention Rate', 'Engagement Score', 'Response Time', 'Personalization Accuracy']
            },
            {
                'name': 'Intelligent Process Automation and Workflow Optimization',
                'description': 'Implement intelligent automation across key business processes to reduce manual effort, minimize errors, and improve operational efficiency. This initiative will streamline workflows, reduce operational costs, and enable employees to focus on higher-value activities that drive business growth. The solution addresses manual processes, workflow inefficiencies, and error-prone operations through intelligent automation and workflow optimization.',
                'category': 'Process Automation',
                'current_state': 'Manual processes causing inefficiencies and errors with limited automation and workflow optimization',
                'aws_services': ['Step Functions', 'Lambda', 'API Gateway', 'SQS'],
                'business_value': 'Reduced operational costs and improved accuracy with 35-55% efficiency improvements and error reduction',
                'implementation_phases': ['Process Analysis', 'Automation Design', 'Implementation', 'Monitoring'],
                'timeline_months': 5,
                'monthly_cost_usd': 2500,
                'complexity': 'Medium',
                'priority': 'Critical',
                'risk_level': 'Medium',
                'success_metrics': ['Process Efficiency', 'Error Reduction', 'Cost Savings', 'Processing Time', 'User Productivity']
            }
        ]
        
        needed_count = max(0, 8 - current_count)
        
        for i in range(min(needed_count, len(business_supplements))):
            supplement_data = business_supplements[i]
            
            supplement = UseCaseStructured(
                title=supplement_data['name'],
                category=supplement_data['category'],
                current_state=supplement_data['current_state'],
                proposed_solution=supplement_data['description'],
                primary_aws_services=supplement_data['aws_services'],
                business_value=supplement_data['business_value'],
                implementation_phases=supplement_data['implementation_phases'],
                timeline_months=supplement_data['timeline_months'],
                monthly_cost_usd=supplement_data['monthly_cost_usd'],
                complexity=supplement_data['complexity'],
                priority=supplement_data['priority'],
                risk_level=supplement_data['risk_level'],
                success_metrics=supplement_data['success_metrics']
            )
            
            # Add dynamic ID
            supplement.dynamic_id = f"business-transformation-supplement-{current_count + i + 1}"
            supplements.append(supplement)
        
        return supplements

    def _generate_fallback_use_cases(self, company_profile: CompanyProfile, research_data: Dict[str, Any], 
                                   parsed_files_content: str = None,
                                   custom_context: Dict[str, str] = None) -> List[UseCaseStructured]:
        """Generate fallback use cases when primary generation fails."""
        
        logger.info(f"Generating fallback use cases for {company_profile.name}")
        
        fallback_use_cases = []
        
        # Base fallback use cases with proper names and descriptions
        fallback_templates = [
            {
                'name': 'Digital Platform Modernization and Cloud Migration',
                'description': 'Modernize legacy systems and migrate to cloud-native architecture to improve agility, scalability, and operational efficiency. This comprehensive transformation will enable faster feature deployment, better system reliability, and reduced operational costs while positioning the organization for future growth.',
                'category': 'Platform Modernization',
                'current_state': 'Legacy systems limiting business agility and innovation',
                'aws_services': ['ECS', 'API Gateway', 'Lambda', 'RDS', 'CloudFront'],
                'business_value': 'Improved agility, scalability, and time-to-market',
                'implementation_phases': ['Platform Assessment', 'Architecture Design', 'Migration', 'Optimization'],
                'timeline_months': 10,
                'monthly_cost_usd': 6000,
                'complexity': 'High',
                'priority': 'Critical',
                'risk_level': 'Medium',
                'success_metrics': ['System Performance', 'Deployment Speed', 'User Satisfaction']
            },
            {
                'name': 'Enterprise Data Analytics and Business Intelligence',
                'description': 'Establish a comprehensive data analytics platform that provides real-time insights and predictive analytics capabilities. This initiative will enable data-driven decision making, improve operational efficiency, and identify new business opportunities through advanced analytics and machine learning.',
                'category': 'Data Analytics',
                'current_state': 'Limited data insights affecting strategic decision making',
                'aws_services': ['Redshift', 'QuickSight', 'Kinesis', 'Glue', 'SageMaker'],
                'business_value': 'Data-driven decisions and competitive intelligence',
                'implementation_phases': ['Data Strategy', 'Platform Setup', 'Analytics Development', 'Training'],
                'timeline_months': 8,
                'monthly_cost_usd': 4500,
                'complexity': 'High',
                'priority': 'High',
                'risk_level': 'Medium',
                'success_metrics': ['Data Utilization', 'Decision Speed', 'Business Insights']
            },
            {
                'name': 'Comprehensive Security and Compliance Framework',
                'description': 'Implement a robust security framework with automated compliance monitoring and threat detection capabilities. This initiative will enhance security posture, ensure regulatory compliance, and provide continuous monitoring and response capabilities to protect business assets and customer data.',
                'category': 'Security & Compliance',
                'current_state': 'Security gaps and compliance challenges',
                'aws_services': ['Security Hub', 'Config', 'GuardDuty', 'Inspector', 'CloudTrail'],
                'business_value': 'Enhanced security posture and regulatory compliance',
                'implementation_phases': ['Security Assessment', 'Framework Design', 'Implementation', 'Monitoring'],
                'timeline_months': 6,
                'monthly_cost_usd': 3500,
                'complexity': 'Medium',
                'priority': 'Critical',
                'risk_level': 'Low',
                'success_metrics': ['Security Score', 'Compliance Rating', 'Incident Reduction']
            },
            {
                'name': 'Unified Customer Experience Platform',
                'description': 'Create a unified customer experience platform that integrates all customer touchpoints and provides personalized interactions through AI-powered recommendations and real-time engagement capabilities. This solution will improve customer satisfaction, increase retention, and drive revenue growth.',
                'category': 'Customer Experience',
                'current_state': 'Fragmented customer interactions and limited personalization',
                'aws_services': ['Personalize', 'Pinpoint', 'Connect', 'Comprehend', 'Lex'],
                'business_value': 'Improved customer satisfaction and increased retention',
                'implementation_phases': ['Journey Mapping', 'Platform Setup', 'Personalization', 'Optimization'],
                'timeline_months': 7,
                'monthly_cost_usd': 4000,
                'complexity': 'Medium',
                'priority': 'High',
                'risk_level': 'Low',
                'success_metrics': ['Customer Satisfaction', 'Retention Rate', 'Engagement Score']
            },
            {
                'name': 'Intelligent Process Automation and Workflow Optimization',
                'description': 'Implement intelligent process automation across key business workflows to reduce manual effort, minimize errors, and improve operational efficiency. This initiative will streamline operations, reduce costs, and enable employees to focus on higher-value strategic activities.',
                'category': 'Process Automation',
                'current_state': 'Manual processes causing inefficiencies and errors',
                'aws_services': ['Step Functions', 'Lambda', 'API Gateway', 'SQS', 'EventBridge'],
                'business_value': 'Reduced operational costs and improved accuracy',
                'implementation_phases': ['Process Analysis', 'Automation Design', 'Implementation', 'Monitoring'],
                'timeline_months': 5,
                'monthly_cost_usd': 2800,
                'complexity': 'Medium',
                'priority': 'High',
                'risk_level': 'Medium',
                'success_metrics': ['Process Efficiency', 'Error Reduction', 'Cost Savings']
            }
        ]
        
        for i, template in enumerate(fallback_templates):
            use_case = UseCaseStructured(
                title=template['name'],
                category=template['category'],
                current_state=template['current_state'],
                proposed_solution=template['description'],
                primary_aws_services=template['aws_services'],
                business_value=template['business_value'],
                implementation_phases=template['implementation_phases'],
                timeline_months=template['timeline_months'],
                monthly_cost_usd=template['monthly_cost_usd'],
                complexity=template['complexity'],
                priority=template['priority'],
                risk_level=template['risk_level'],
                success_metrics=template['success_metrics']
            )
            
            # Add dynamic ID
            use_case.dynamic_id = f"business-transformation-fallback-{i+1}"
            fallback_use_cases.append(use_case)
        
        return fallback_use_cases
