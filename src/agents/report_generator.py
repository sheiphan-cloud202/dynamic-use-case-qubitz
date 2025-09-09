"""
Report generation agent for the Business Transformation Agent.
"""
import logging
import os
import re
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from strands import Agent, tool
from strands_tools import retrieve, http_request
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.core.bedrock_manager import EnhancedModelManager
from src.core.models import CompanyProfile, UseCaseStructured
from src.services.web_scraper import WebScraper
from src.services.aws_clients import s3_client, S3_BUCKET, LAMBDA_TMP_DIR
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import PDF generation libraries
try:
    import weasyprint
    PDF_GENERATION_AVAILABLE = True
    logger.info("✅ WeasyPrint PDF generation available")
except (ImportError, OSError) as e:
    logger.warning(f"⚠️ WeasyPrint not available: {e}")
    logger.info("🔄 Falling back to ReportLab for PDF generation")
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import black, blue, HexColor
        from reportlab.platypus.flowables import HRFlowable
        REPORTLAB_AVAILABLE = True
        PDF_GENERATION_AVAILABLE = True
        logger.info("✅ ReportLab available for PDF generation")
    except ImportError:
        REPORTLAB_AVAILABLE = False
        PDF_GENERATION_AVAILABLE = False
        logger.warning("⚠️ No PDF generation libraries available")

class ReportXMLParser:
    """Enhanced parser for converting XML tags to formatted PDF content with support for multiple formatting tags."""
    
    @staticmethod
    def parse_xml_tags(xml_content: str) -> Dict[str, Any]:
        """Parse XML-like tags from report content with comprehensive formatting support."""
        
        parsed_content = {
            'title': '',
            'sections': [],
            'citations': {},
            'inline_citations': []
        }
        
        # Clean up XML content - remove any text before the first XML tag
        xml_content = xml_content.strip()
        first_tag_match = re.search(r'<[^>]+>', xml_content)
        if first_tag_match:
            xml_content = xml_content[first_tag_match.start():]
        else:
            # If no XML tags found, return empty structure
            logger.warning("No XML tags found in content, returning empty structure")
            return parsed_content
        
        # Extract title
        title_match = re.search(r'<heading_bold>(.*?)</heading_bold>', xml_content, re.DOTALL)
        if title_match:
            parsed_content['title'] = title_match.group(1).strip()
            logger.info(f"✅ Extracted title: {parsed_content['title']}")
        else:
            logger.warning("⚠️ No title found in XML content")
        
        # Extract all content sections - now includes various types
        section_patterns = [
            r'<content>(.*?)</content>',
            r'<sub-heading-bold>(.*?)</sub-heading-bold>',
            r'<sub-heading>(.*?)</sub-heading>',
            r'<section>(.*?)</section>',
            r'<paragraph>(.*?)</paragraph>',
            r'<list>(.*?)</list>',
            r'<table>(.*?)</table>'
        ]
        
        # Find all sections in order
        all_sections = []
        for pattern in section_patterns:
            matches = re.finditer(pattern, xml_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                section_type = pattern.split('(')[0].replace('<', '').replace('>', '').replace('\\', '')
                all_sections.append({
                    'type': section_type,
                    'content': match.group(1),
                    'start_pos': match.start()
                })
        
        # Sort sections by position in document
        all_sections.sort(key=lambda x: x['start_pos'])
        
        logger.info(f"✅ Found {len(all_sections)} sections in XML content")
        
        citation_counter = 1
        for section in all_sections:
            # Process citations within content
            processed_content, citation_counter = ReportXMLParser._process_inline_citations(
                section['content'], parsed_content['citations'], 
                parsed_content['inline_citations'], citation_counter
            )
            
            # Process additional formatting tags
            processed_content = ReportXMLParser._process_formatting_tags(processed_content)
            
            parsed_content['sections'].append({
                'type': section['type'],
                'content': processed_content
            })
        
        return parsed_content
    
    @staticmethod
    def _process_inline_citations(content: str, citations_dict: Dict[str, str], 
                                inline_citations: List[Dict], citation_counter: int) -> tuple:
        """Process citation tags to create inline clickable citations with enhanced distribution."""
        
        # Find citation patterns
        citation_pattern = r'<citation_name>(.*?)</citation_name><citation_url>(.*?)</citation_url>'
        matches = re.finditer(citation_pattern, content, re.DOTALL)
        
        processed_content = content
        
        for match in matches:
            citation_name = match.group(1).strip()
            citation_url = match.group(2).strip()
            
            # Skip if citation is empty or invalid
            if not citation_name or not citation_url:
                continue
            
            # Create a clean title from citation name (limit length)
            clean_title = citation_name[:50] + "..." if len(citation_name) > 50 else citation_name
            
            # Store citation for inline use
            citation_info = {
                'number': citation_counter,
                'name': clean_title,
                'url': citation_url,
                'full_name': citation_name
            }
            
            citations_dict[str(citation_counter)] = citation_info
            inline_citations.append(citation_info)
            
            # Replace with inline clickable citation with enhanced formatting
            citation_tag = f'<citation_name>{citation_name}</citation_name><citation_url>{citation_url}</citation_url>'
            inline_citation = f'<link href="{citation_url}"><u>[{citation_counter}]</u></link>'
            processed_content = processed_content.replace(citation_tag, inline_citation)
            
            citation_counter += 1
        
        return processed_content, citation_counter

    @staticmethod
    def _process_formatting_tags(content: str) -> str:
        """Process additional formatting tags like bold, italic, underline with enhanced support."""
        
        # Process bold tags
        content = re.sub(r'<bold>(.*?)</bold>', r'<b>\1</b>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process italic tags
        content = re.sub(r'<italic>(.*?)</italic>', r'<i>\1</i>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process underline tags
        content = re.sub(r'<underline>(.*?)</underline>', r'<u>\1</u>', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process bullet points
        content = re.sub(r'<bullet>(.*?)</bullet>', r'• \1', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process numbered lists with sequential numbering
        number_counter = 1
        def replace_number(match):
            nonlocal number_counter
            result = f"{number_counter}. {match.group(1)}"
            number_counter += 1
            return result
        
        content = re.sub(r'<number>(.*?)</number>', replace_number, content, flags=re.DOTALL | re.IGNORECASE)
        
        # Process list containers
        content = re.sub(r'<list>(.*?)</list>', r'\1', content, flags=re.DOTALL | re.IGNORECASE)
        
        return content

class ConsolidatedReportGenerator:
    """Generate consolidated comprehensive reports with enhanced XML formatting support."""
    
    def __init__(self, model_manager: EnhancedModelManager):
        self.model_manager = model_manager
        self.web_scraper = WebScraper()
        
        self.report_agent = Agent(
            model=model_manager.research_model,

            system_prompt="""You are a professional technical writer and business strategist. Your task is to generate comprehensive business reports for transformation use cases using XML-like tags for structured formatting.

                Generate reports that are:
                - Professional and executive-ready
                - Data-driven with concrete business insights
                - Comprehensive yet focused on actionable recommendations
                - Formatted using XML tags for parsing
                - Include inline citations using <citation_name> and <citation_url> tags WITHIN content paragraphs
                - When custom context is provided, ensure all recommendations align with the specified focus areas and requirements

                MANDATORY: Talk comprehensively about ALL generated use cases, providing detailed analysis and strategic recommendations for each one.
                QUALITY & COMPLETENESS GUARDRAILS:
                - DO NOT repeat content or restate the same paragraph in multiple sections.
                - DO NOT cut off mid-sentence; complete every paragraph.
                - Each section MUST be unique, non-overlapping, and provide incremental insights.
                - Keep language concise; no filler phrases; avoid repeating “Immediate Next Steps” blocks.
                - If you need to reference similar ideas, summarize once and cross-reference instead of duplicating.
                MANDATORY XML TAG FORMAT - Use ALL of these tags appropriately:
                
                STRUCTURAL TAGS:
                - <heading_bold>Main Report Title</heading_bold> - For the main report title
                - <sub-heading-bold>Major Section Title</sub-heading-bold> - For major section headings with bold formatting
                - <sub-heading>Section Title</sub-heading> - For section headings without bold
                - <content>Paragraph content with inline citations</content> - For main content paragraphs
                - <section>Content blocks</section> - For organizing content sections
                - <paragraph>Individual paragraph</paragraph> - For standalone paragraphs
                
                FORMATTING TAGS:
                - <bold>Bold text</bold> - For emphasizing important text
                - <italic>Italic text</italic> - For emphasis or technical terms
                - <underline>Underlined text</underline> - For highlights
                
                FINANCIAL EXPRESSION POLICY (MANDATORY):
               - Do NOT include any absolute currency figures (no $, USD, INR, EUR, etc.).
               - Express Total Cost of Ownership (TCO), ROI, and investment in qualitative terms or percentages only.
               - Use ranges and relative values (e.g., “15–20% efficiency improvement”, “payback in 6–12 months”) instead of dollar amounts.
               - Avoid making any commercial commitment or guarantee of savings/investment.


                LIST TAGS:
                - <list>List content</list> - For organizing lists
                - <bullet>Bullet point item</bullet> - For bullet points
                - <number>Numbered item</number> - For numbered lists
                
                CITATION TAGS:
                - <citation_name>Source Name</citation_name><citation_url>https://source-url.com</citation_url> - INLINE within content
                
                EXAMPLE BETTER FORMAT FOR USE CASE OVERVIEW:
                
                <sub-heading>2.1: Identified Use Cases Overview</sub-heading>
                
                <content>Our comprehensive analysis has identified the following strategic transformation opportunities:</content>
                
                <list>
                <bullet><bold>AI-Powered Drop Prediction and Demand Forecasting</bold> - Strategic analytics for optimal inventory management</bullet>
                <bullet><bold>Hyper-Personalized Collector Experience Platform</bold> - Customer experience enhancement through personalization</bullet>
                <bullet><bold>Automated Social Media Content Generation</bold> - Automation and workflow optimization for community management</bullet>
                <bullet><bold>Intelligent Inventory Optimization</bold> - Core business optimization through supply chain automation</bullet>
                <bullet><bold>Real-Time Fan Sentiment Analysis</bold> - Data-driven decision making with market intelligence</bullet>
                <bullet><bold>Immersive AR/VR Collector Experience</bold> - Innovation acceleration through immersive technologies</bullet>
                <bullet><bold>Dynamic Pricing and Revenue Optimization</bold> - Cost optimization through intelligent pricing strategies</bullet>
                <bullet><bold>Predictive Analytics for Global Expansion</bold> - Scalability and growth enablement</bullet>
                </list>
                
                Use citations strategically throughout the document to support key claims, industry insights, and recommendations. Make citations flow naturally within the narrative.

                MANDATORY: Write detailed comprehensive analysis for EVERY use case provided. Each use case should have its own section with strategic analysis, implementation considerations, and business impact assessment using the XML formatting tags.""",
            tools=[http_request, retrieve],
            conversation_manager=SlidingWindowConversationManager(window_size=20)
        )

    def generate_consolidated_report(self, company_profile: CompanyProfile, use_cases: List[UseCaseStructured], 
                                   research_data: Dict[str, Any], session_id: str, status_tracker: StatusTracker = None,
                                   parsed_files_content: str = None, custom_context: Dict[str, str] = None) -> Optional[str]:
        """Generate consolidated PDF report with enhanced XML formatting and web scraping citations."""
        
        if status_tracker:
            status_tracker.update_status(
                StatusCheckpoints.REPORT_GENERATION_STARTED,
                {
                    'report_type': 'consolidated_comprehensive_analysis', 
                    'use_case_count': len(use_cases), 
                    'has_files': bool(parsed_files_content),
                    'has_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                    'web_citations_enabled': bool(research_data.get('web_research_data'))
                },
                current_agent='report_generator'
            )
        
        try:
            # Generate comprehensive report content with enhanced XML tags
            xml_report = self._generate_xml_report_with_enhanced_formatting(
                company_profile, use_cases, research_data, parsed_files_content, custom_context
            )
            
            # Generate and upload PDF
            pdf_url = self._generate_and_upload_pdf_from_xml(xml_report, company_profile.name, session_id)
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.REPORT_GENERATION_COMPLETED,
                    {
                        's3_url': pdf_url, 
                        'report_generated': bool(pdf_url), 
                        'content_enhanced_with_files': bool(parsed_files_content),
                        'content_aligned_with_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                        'web_citations_included': bool(research_data.get('web_research_data'))
                    }
                )
            
            return pdf_url
            
        except Exception as e:
            logger.error(f"Error generating consolidated report: {e}")
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.ERROR,
                    {'error_type': 'report_generation_error', 'error_message': str(e)}
                )
            return None

    def _generate_xml_report_with_enhanced_formatting(self, company_profile: CompanyProfile, use_cases: List[UseCaseStructured], 
                                                    research_data: Dict[str, Any], parsed_files_content: str = None,
                                                    custom_context: Dict[str, str] = None) -> str:
        """Generate XML-tagged report with enhanced formatting and comprehensive use case analysis."""
        
        # Get web research data for citations
        web_research_data = research_data.get('web_research_data', {})
        scraped_results = web_research_data.get('scraped_results', [])
        
        # Process and prepare real citations from web scraping
        real_citations = self._prepare_real_citations_from_web_scraping(scraped_results)
        
        # Web enhancement context
        web_context = ""
        if web_research_data.get('successful_scrapes', 0) > 0:
            web_context = f"""

                **Web Intelligence Integration**: This report incorporates insights from {web_research_data['successful_scrapes']} web sources discovered through Google Search and scraped using Beautiful Soup, providing current market intelligence and industry trends."""
        
        # File enhancement context
        file_context = ""
        if parsed_files_content:
            file_context = """

                **Document Analysis Integration**: This report incorporates insights from uploaded company documents, providing detailed context about current operations, processes, and strategic priorities."""
        
        # Custom context enhancement
        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""

                **Custom Context Alignment**: This analysis addresses the specified focus areas: {', '.join(custom_context.get('focus_areas', []))}. All recommendations align with the custom requirements and strategic priorities."""
        
        # Generate comprehensive XML report with enhanced formatting and real citations 
        xml_prompt = f""" 
Generate a comprehensive business transformation report for **{company_profile.name}** using XML-like tags for structured formatting. 

MANDATORY XML TAG STRUCTURE - Use ALL these tags appropriately:
- <heading_bold>Main Title</heading_bold>
- <sub-heading-bold>Major Section</sub-heading-bold>
- <sub-heading>Section Title</sub-heading>
- <content>Main content paragraphs with citations</content>
- <section>Content blocks</section>
- <paragraph>Individual paragraphs</paragraph>
- <bold>Bold text</bold>
- <italic>Italic text</italic>
- <underline>Underlined text</underline>

LIST TAGS:
- <list>List container</list>
- <bullet>Bullet point</bullet>
- <number>Numbered item</number>

CITATION TAGS:
- <citation_name>Source Name</citation_name><citation_url>URL</citation_url>

### Company Context:
- Industry: {company_profile.industry}
- Business Model: {company_profile.business_model}
- Company Size: {company_profile.company_size}
- Technology Maturity: {company_profile.cloud_maturity}
- Growth Stage: {company_profile.growth_stage}

### Research Intelligence:
{research_data.get('research_findings', '')[:800]}
{web_context}
{file_context}
{custom_context_section}

### REAL WEB CITATIONS AVAILABLE (USE THESE THROUGHOUT THE REPORT):
{self._format_real_citations_for_prompt(real_citations)}

### MANDATORY: Comprehensive Analysis of ALL {len(use_cases)} Transformation Use Cases:
{self._format_all_use_cases_for_comprehensive_analysis(use_cases)}

### MANDATORY XML REPORT STRUCTURE WITH ENHANCED FORMATTING AND REAL CITATIONS:

<heading_bold> GenAI Transformation Strategy for {company_profile.name}</heading_bold>

<content>The convergence of <bold>{company_profile.name}'s</bold> business operations and GenAI technologies presents transformational opportunities. Organizations in <italic>{company_profile.industry}</italic> achieve <bold>15-65% improvements</bold> through AI implementations {self._get_citation_tag(real_citations, 0)}. This comprehensive strategy provides detailed roadmaps, financial projections, and risk assessments for sustainable transformation.</content>

<sub-heading-bold>Section 1: Executive Summary and Strategic Overview</sub-heading-bold>

<content><bold>Executive Summary</bold>: This transformation strategy positions {company_profile.name} for <italic>{company_profile.industry}</italic> innovation through strategic GenAI adoption. Our analysis identifies <bold>{len(use_cases)} high-impact initiatives</bold> delivering measurable business value within 6-18 months. The total investment requirement is estimated at <underline>a moderate level</underline> with projected annual returns of <underline>high returns (300-500% ROI)</underline> within 24 months.</content>

<paragraph><bold>Key Strategic Insights</bold>: Focus on <italic>Operational Excellence</italic>, <italic>Customer Experience Innovation</italic>, and <italic>Data-Driven Decision Making</italic>. Industry analysis reveals that companies implementing comprehensive AI strategies see 3-5x higher returns than those pursuing isolated initiatives {self._get_citation_tag(real_citations, 0)}.</paragraph>

<paragraph><bold>Expected Business Impact</bold>: 25-45% operational efficiency improvements, 30-60% cost reductions, and 20-40% revenue growth {self._get_citation_tag(real_citations, 1)}. These projections are based on industry benchmarks and peer company analysis in the {company_profile.industry} sector.</paragraph>

<paragraph><bold>Critical Success Factors</bold>: Executive sponsorship, comprehensive change management, phased implementation approach, robust governance framework, and continuous performance monitoring. Organizations with strong governance achieve 40% higher AI ROI than those without structured oversight {self._get_citation_tag(real_citations, 2)}.</paragraph>

<sub-heading-bold>Section 2: Strategic Context and Business Position</sub-heading-bold>

<content><bold>{company_profile.name}</bold> operates in the <italic>{company_profile.industry}</italic> sector with significant transformation opportunities driven by market dynamics, competitive pressures, and technological advancement {self._get_citation_tag(real_citations, 2)}.</content>

<sub-heading>2.1: Market Dynamics and Transformation Imperative</sub-heading>

<content>The <italic>{company_profile.industry}</italic> sector faces digital pressure that GenAI can address. Market volatility creates operational challenges {self._get_citation_tag(real_citations, 3)}, while early AI adopters gain competitive advantages equivalent to <underline>15-25% market share growth</underline> {self._get_citation_tag(real_citations, 4)}.</content>

<paragraph><bold>Industry Transformation Drivers</bold>: Customer expectations for faster service delivery, regulatory compliance complexity, operational cost pressures, and talent shortage challenges. Companies leveraging AI for process automation report <underline>20-40% annual savings</underline> in operational costs {self._get_citation_tag(real_citations, 5)}.</paragraph>

<paragraph><bold>Technology Maturity Assessment</bold>: {company_profile.name}'s <italic>{company_profile.cloud_maturity}</italic> maturity provides foundation for GenAI transformation using {', '.join(company_profile.technology_stack)}. Current infrastructure readiness enables rapid deployment with minimal additional investment in core technology stack.</paragraph>

<paragraph><bold>Competitive Landscape Analysis</bold>: Market leaders are investing <underline>significantly</underline> in AI capabilities, creating competitive pressure for {company_profile.industry} organizations to accelerate digital transformation or risk market share erosion {self._get_citation_tag(real_citations, 6)}.</paragraph>

<sub-heading>2.2: Digital Maturity and Readiness Assessment</sub-heading>

<paragraph><bold>Current State Evaluation</bold>: Assessment of existing digital capabilities, data infrastructure quality, process automation maturity, and organizational change readiness. Key metrics include system integration complexity, data quality scores, and employee digital literacy levels.</paragraph>

<paragraph><bold>Gap Analysis</bold>: Identification of capability gaps in data management, process automation, analytics infrastructure, and talent requirements. Estimated gap closure investment: <underline>low to moderate level</underline> over 12-18 months for full transformation readiness.</paragraph>

<sub-heading-bold>Section 3: Comprehensive Use Case Portfolio Analysis</sub-heading-bold>

<content>Our analysis identifies <bold>{len(use_cases)} strategic transformation initiatives</bold> designed for {company_profile.name}'s context, each with detailed financial projections, risk assessments, and implementation roadmaps {self._get_citation_tag(real_citations, 5)}.</content>

<sub-heading>3.1: Use Case Portfolio Overview</sub-heading>

<paragraph><bold>Strategic Portfolio Design</bold>: The use case portfolio balances quick wins, foundational capabilities, and advanced innovations. Total portfolio investment: <underline>moderate level</underline> with staggered deployment to minimize risk and maximize learning.</paragraph>

<list>
 {self._format_use_cases_as_bullet_list(use_cases)}
</list>

<paragraph><bold>Portfolio Synergies</bold>: Use cases are designed with interconnected benefits where success in one area amplifies returns in others. Cross-case synergies are projected to deliver additional <underline>20-30% value</underline> through shared infrastructure, data assets, and operational efficiencies.</paragraph>

<sub-heading>3.2: Risk-Adjusted Value Proposition</sub-heading>

<paragraph><bold>Portfolio Risk Analysis</bold>: Comprehensive assessment of technical, operational, market, and regulatory risks with corresponding mitigation strategies. Risk-adjusted NPV calculation shows positive returns under conservative, base, and optimistic scenarios.</paragraph>

<paragraph><bold>Value Creation Timeline</bold>: Immediate wins (0-6 months): <underline>modest gains</underline>, Medium-term gains (6-18 months): <underline>significant gains</underline>, Long-term value (18+ months): <underline>substantial gains annually</underline>.</paragraph>

<sub-heading-bold>Section 4: Detailed Use Case Analysis</sub-heading-bold>

<content>Each use case undergoes rigorous analysis encompassing strategic rationale, technical architecture, financial modeling, risk assessment, and implementation planning. This section provides comprehensive detail for informed decision-making and successful execution.</content>

[MANDATORY: Generate comprehensive analysis for EACH use case with enhanced formatting and real citations:]

[FOR EACH USE CASE, CREATE THIS ENHANCED STRUCTURE:]

<sub-heading>4.X: Use Case - [USE CASE TITLE]</sub-heading>

<content><bold>Strategic Overview</bold>: [Detailed 3-4 sentence analysis with strategic importance, market context, and competitive implications] {self._get_citation_tag(real_citations, 6)}. This use case addresses critical business challenges while building foundational capabilities for future innovation.</content>

<paragraph><bold>Business Case and Value Proposition</bold>: [Detailed business rationale with quantified benefits] Industry research shows similar challenges affect {company_profile.industry} organizations, with leading companies achieving <underline>significant annual savings</underline> through comparable initiatives {self._get_citation_tag(real_citations, 7)}.</paragraph>

<paragraph><bold>Current State Assessment</bold>: [Comprehensive current situation analysis including process inefficiencies, cost implications, customer impact, and competitive disadvantages]. Current manual processes cost approximately <underline>high per transaction/process</underline> with significant opportunity for optimization.</paragraph>

<paragraph><bold>Proposed Solution Architecture</bold>: [Detailed technical solution with specific components and integration points] This approach leverages proven methodologies and industry best practices {self._get_citation_tag(real_citations, 8)}.</paragraph>

<list>
<bullet><bold>Technology Architecture</bold>: Comprehensive technical architecture including AI/ML models, data pipelines, integration APIs, security frameworks, and scalability considerations. Infrastructure requirements: cloud compute resources, storage capacity, network bandwidth, and disaster recovery capabilities.</bullet>
<bullet><bold>Data Strategy</bold>: Data sourcing, quality requirements, governance frameworks, privacy controls, and analytics capabilities. Estimated data infrastructure investment: <underline>low to moderate level</underline>.</bullet>
<bullet><bold>Integration Framework</bold>: Detailed integration with existing systems including CRM, ERP, project management platforms, and third-party services. API development and maintenance costs: <underline>moderate annually</underline>.</bullet>
<bullet><bold>Security and Compliance</bold>: Comprehensive security architecture, compliance frameworks, audit trails, and risk management protocols meeting industry standards and regulatory requirements.</bullet>
</list>

<paragraph><bold>Quantified Business Value</bold>: [Detailed financial analysis with specific percentage improvements]</paragraph>

<list>
<bullet><bold>Direct Cost Savings</bold>: Labor cost reduction of <underline>20-40% annually</underline> through process automation and efficiency gains.</bullet>
<bullet><bold>Revenue Enhancement</bold>: Additional revenue of <underline>15-30% annually</underline> through improved customer experience, faster delivery, and new service capabilities.</bullet>
<bullet><bold>Risk Mitigation Value</bold>: Avoided costs of <underline>10-20%</underline> through improved compliance, reduced errors, and enhanced quality assurance.</bullet>
<bullet><bold>Operational Efficiency</bold>: Process improvements delivering <underline>25-35% monthly savings</underline> through cycle time reduction, resource optimization, and waste elimination.</bullet>
</list>

<paragraph><bold>Implementation Strategy and Timeline</bold>: [Detailed phased approach with specific milestones, deliverables, and success criteria]</paragraph>

<list>
<bullet><bold>Phase 1 - Foundation (Months 1-3)</bold>: Infrastructure setup, team training, pilot deployment. Investment: <underline>low level</underline>. Success criteria: system deployment, user adoption >80%, basic functionality validation.</bullet>
<bullet><bold>Phase 2 - Scale (Months 4-9)</bold>: Production deployment, process integration, user scaling. Investment: <underline>moderate level</underline>. Success criteria: full operational deployment, efficiency targets achieved, stakeholder satisfaction >85%.</bullet>
<bullet><bold>Phase 3 - Optimize (Months 10-18)</bold>: Advanced features, analytics, continuous improvement. Investment: <underline>moderate level</underline>. Success criteria: advanced capabilities operational, ROI targets exceeded, expansion roadmap validated.</bullet>
</list>

<paragraph><bold>Success Metrics and KPIs</bold>: [Comprehensive measurement framework]</paragraph>

<list>
<bullet><bold>Financial KPIs</bold>: ROI percentage, cost savings achieved (%), revenue impact (%), payback period (months). Target: >300% ROI within 24 months, <underline>significant net benefit</underline>.</bullet>
<bullet><bold>Operational KPIs</bold>: Process efficiency improvement (%), cycle time reduction (%), error rate reduction (%), user adoption rates (%). Industry benchmarks suggest 40-70% improvement potential.</bullet>
<bullet><bold>Strategic KPIs</bold>: Customer satisfaction scores, competitive positioning metrics, innovation pipeline value, market share growth (%). Target improvements: NPS +20 points, market share +5-10%.</bullet>
<bullet><bold>Technical KPIs</bold>: System uptime (%), response time (ms), scalability metrics, security incident rates. Target: >99.9% uptime, <2 second response times.</bullet>
</list>

<paragraph><bold>Risk Assessment and Mitigation</bold>: [Comprehensive risk analysis with quantified impact and mitigation strategies]</paragraph>

<list>
<bullet><bold>Technical Risks</bold>: System integration complexity, performance issues, scalability challenges. Mitigation cost: <underline>low level</underline> for redundancy and testing.</bullet>
<bullet><bold>Adoption Risks</bold>: User resistance, training inadequacy, process disruption. Change management investment: <underline>moderate level</underline> for comprehensive training and support.</bullet>
<bullet><bold>Financial Risks</bold>: Cost overruns, delayed benefits realization, market changes. Contingency budget: <underline>15-20% of total investment</underline>.</bullet>
<bullet><bold>Compliance Risks</bold>: Regulatory changes, data privacy issues, audit failures. Compliance infrastructure cost: <underline>moderate annually</underline>.</bullet>
</list>

<paragraph><bold>Governance and Change Management</bold>: [Detailed governance structure and change management approach]</paragraph>

<list>
<bullet><bold>Governance Structure</bold>: Executive steering committee, technical oversight board, user advisory groups. Governance operating cost: <underline>low annually</underline>.</bullet>
<bullet><bold>Change Management Strategy</bold>: Communication plans, training programs, support systems, feedback mechanisms. Total change management investment: <underline>moderate level</underline>.</bullet>
<bullet><bold>Quality Assurance</bold>: Testing protocols, performance monitoring, continuous improvement processes. QA infrastructure cost: <underline>low level</underline> for tools and resources.</bullet>
<bullet><bold>Stakeholder Engagement</bold>: User engagement strategy, feedback collection, adaptation mechanisms. Stakeholder management cost: <underline>low level</underline> for dedicated resources.</bullet>
</list>

<paragraph><bold>Industry-Specific Considerations</bold>: [Tailored analysis based on {company_profile.industry} requirements including regulatory compliance, operational standards, technology constraints, and market dynamics specific to the industry sector.]</paragraph>

<paragraph><bold>Competitive Differentiation</bold>: [Analysis of how this use case creates sustainable competitive advantage, market positioning benefits, and barriers to competitor replication. Estimated competitive advantage value: <underline>significant over 3 years</underline>.]</paragraph>

<paragraph><bold>Scalability and Future Evolution</bold>: [Long-term vision for use case evolution, scalability considerations, and future enhancement opportunities. Projected scaling benefits: additional <underline>20-30% annually</underline> for each 25% capacity increase.]</paragraph>

[Continue this enhanced pattern for ALL {len(use_cases)} use cases - DO NOT SKIP ANY - USE REAL CITATIONS THROUGHOUT - INCLUDE DETAILED FINANCIAL PROJECTIONS FOR EACH]

<sub-heading-bold>Section 5: Implementation Roadmap and Strategic Recommendations</sub-heading-bold>

<content><bold>Success requires disciplined execution</bold> focusing on quick wins while building long-term capabilities. The phased approach minimizes disruption while maximizing value creation, with total program investment of <underline>moderate level</underline> and projected returns of <underline>high returns (400-600% ROI over 3 years)</underline> {self._get_citation_tag(real_citations, 10)}.</content>

<sub-heading>5.1: Priority Implementation Sequence and Financial Projections</sub-heading>

<list>
<bullet><bold>Phase 1: Foundation and Quick Wins (Months 1-3)</bold> — Investment: <underline>low level</underline>. Establish baseline capabilities, run initial pilots, create governance body, and validate KPIs. Expected early wins: <underline>modest cost savings</underline> and 15-25% process improvements.</bullet>
<bullet><bold>Phase 2: Core Transformation Initiatives (Months 4-9)</bold> — Investment: <underline>moderate level</underline>. Scale pilots into production, integrate with enterprise systems, expand training and adoption programs. Projected savings: <underline>significant annually</underline>.</bullet>
<bullet><bold>Phase 3: Advanced Capabilities (Months 10-15)</bold> — Investment: <underline>moderate level</underline>. Build predictive capabilities, automation at scale, and strengthen resilience and security controls. Additional value creation: <underline>substantial annually</underline>.</bullet>
<bullet><bold>Phase 4: Innovation and Optimization (Months 16-18)</bold> — Investment: <underline>low level</underline>. Optimize with feedback loops, embed continuous improvement, explore adjacent innovations. Optimization benefits: <underline>significant in efficiency gains</underline>.</bullet>
</list>

<sub-heading>5.2: Resource Requirements and Investment Analysis</sub-heading>

<paragraph><bold>Human Capital Investment</bold>: Total talent investment of <underline>moderate level</underline> over 18 months including hiring, training, and retention programs.</paragraph>

<list>
<bullet><bold>Project Leadership</bold>: Experienced transformation leaders with accountability for delivery. Cost: <underline>moderate annually</underline> for senior program management.</bullet>
<bullet><bold>Technical Expertise</bold>: Data engineers, automation specialists, cloud architects, and model operations experts. Team cost: <underline>significant annually</underline> for 8-12 FTE technical resources.</bullet>
<bullet><bold>Business Analysts</bold>: Domain experts who translate business pain points into solution requirements. Investment: <underline>moderate annually</underline> for 4-6 FTE business analysis resources.</bullet>
<bullet><bold>Change Management</bold>: Adoption specialists with communication and stakeholder engagement plans. Budget: <underline>low level</underline> for comprehensive change management program.</bullet>
<bullet><bold>Governance & Compliance</bold>: Risk officers and audit experts to oversee controls and adherence. Annual cost: <underline>low level</underline> for governance infrastructure.</bullet>
</list>

<sub-heading>5.3: Technology and Infrastructure Investment</sub-heading>

<paragraph><bold>Technology Platform Costs</bold>: Cloud infrastructure, AI/ML platforms, integration tools, and security solutions. Total technology investment: <underline>moderate level over 3 years</underline>.</paragraph>

<list>
<bullet><bold>Training & Upskilling</bold>: Role-based training for executives, analysts, and operations staff. Training budget: <underline>low level</underline> for comprehensive capability development.</bullet>
<bullet><bold>Data Foundations</bold>: Catalog, lineage, and quality assurance pipelines for trustworthy inputs. Data infrastructure cost: <underline>low to moderate level</underline>.</bullet>
<bullet><bold>Security Infrastructure</bold>: Identity management, encryption policies, and data access controls. Security investment: <underline>moderate annually</underline>.</bullet>
<bullet><bold>Change Governance</bold>: Steering committee with regular cadence to monitor risks and progress. Governance operating cost: <underline>low annually</underline>.</bullet>
</list>

<sub-heading-bold>Section 6: Financial Analysis and ROI Projections</sub-heading-bold>

<content>Comprehensive financial analysis demonstrates strong ROI potential with detailed cash flow projections, sensitivity analysis, and risk-adjusted returns. Based on industry benchmarks and peer analysis, the initiatives are projected to deliver <underline>high net benefit (400-600% ROI over 3 years)</underline> with payback within 18-24 months.</content>

<sub-heading>6.1: Investment Requirements and Funding Strategy</sub-heading>

<paragraph><bold>Total Investment Breakdown</bold>: Comprehensive financial requirements totaling <underline>moderate level</underline> over the implementation period.</paragraph>

<list>
<bullet><bold>Technology and Platforms</bold>: <underline>significant portion</underline> for AI/ML platforms, cloud infrastructure, integration tools, and security solutions.</bullet>
<bullet><bold>Human Resources</bold>: <underline>significant portion</underline> for project teams, training, change management, and ongoing support.</bullet>
<bullet><bold>Process Transformation</bold>: <underline>modest portion</underline> for business process redesign, workflow optimization, and operational changes.</bullet>
<bullet><bold>Risk Mitigation and Contingency</bold>: <underline>15% of total investment</underline> for unexpected challenges and market changes.</bullet>
</list>

<paragraph><bold>Funding Strategy Options</bold>: Capital allocation approaches including phased investment, ROI reinvestment, external funding considerations, and cash flow optimization to minimize financial impact while maximizing returns.</paragraph>

<sub-heading>6.2: Expected Returns and Value Creation</sub-heading>

<paragraph><bold>Revenue Impact Analysis</bold>: Detailed revenue projections with conservative, base, and optimistic scenarios.</paragraph>

<list>
<bullet><bold>Direct Revenue Growth</bold>: <underline>20-40% annually</underline> from new capabilities, faster delivery, and expanded market reach.</bullet>
<bullet><bold>Operational Cost Savings</bold>: <underline>30-50% annually</underline> from reduced manual processing, improved efficiency, and waste elimination.</bullet>
<bullet><bold>Quality and Risk Benefits</bold>: <underline>10-25% annually</underline> in avoided costs through reduced errors, compliance improvements, and risk mitigation.</bullet>
<bullet><bold>Strategic Value Creation</bold>: <underline>15-30% annually</underline> from competitive advantages, market positioning, and innovation capabilities.</bullet>
</list>

<paragraph><bold>Cash Flow Projections</bold>: Monthly cash flow analysis showing investment timeline, benefit realization curve, and net present value calculations. Positive cash flow projected by month 12-15 with full payback within 24-30 months.</paragraph>

<sub-heading>6.3: Sensitivity Analysis and Risk Scenarios</sub-heading>

<paragraph><bold>Scenario Modeling</bold>: Financial returns under various adoption and market scenarios:</paragraph>

<list>
<bullet><bold>Conservative Scenario (70% adoption)</bold>: <underline>modest net benefit</underline>, 18-month payback, 250% ROI over 3 years.</bullet>
<bullet><bold>Base Scenario (85% adoption)</bold>: <underline>significant net benefit</underline>, 15-month payback, 400% ROI over 3 years.</bullet>
<bullet><bold>Optimistic Scenario (95% adoption)</bold>: <underline>substantial net benefit</underline>, 12-month payback, 600% ROI over 3 years.</bullet>
</list>

<paragraph><bold>Break-Even Analysis</bold>: Detailed break-even calculations showing minimum performance thresholds, critical success factors, and early warning indicators for course correction.</paragraph>

<sub-heading-bold>Section 7: Success Metrics and Performance Monitoring</sub-heading-bold>

<content>Comprehensive success metrics ensure accountability and continuous improvement throughout the transformation journey. The measurement framework includes leading indicators, lagging metrics, and predictive analytics for proactive management.</content>

<sub-heading>7.1: Key Performance Indicators</sub-heading>

<list>
<bullet><bold>Financial Performance Metrics</bold>: ROI achievement (target >300%), cost savings realization (<underline>monthly targets</underline>), revenue impact tracking (<underline>quarterly goals</underline>), and budget adherence (±5% variance tolerance).</bullet>
<bullet><bold>Operational Excellence Metrics</bold>: Process cycle-time reductions (target 40-60%), throughput improvements (target 25-45% increase), quality score improvements (target >95%), and automation rates (target >80%).</bullet>
<bullet><bold>Customer Experience Metrics</bold>: Net Promoter Score improvements (target +15 points), issue resolution time reduction (target 50% faster), client retention improvements (target >95%), and service quality scores (target >90%).</bullet>
<bullet><bold>Technology Performance Metrics</bold>: Platform uptime (target >99.9%), response times (<2 seconds), user adoption rates (target >90%), and system reliability scores (target >95%).</bullet>
<bullet><bold>Governance and Risk Metrics</bold>: Compliance scores (target 100%), audit readiness (target 90+ compliance score), security incident rates (target <1 monthly), and risk exposure reduction (target 50% decrease).</bullet>
</list>

<sub-heading>7.2: Advanced Analytics and Monitoring Framework</sub-heading>

<paragraph><bold>Real-Time Dashboard Implementation</bold>: Executive dashboards providing real-time visibility into transformation progress, financial performance, and risk indicators. Dashboard development cost: <underline>low level</underline> with <underline>modest monthly</underline> maintenance.</paragraph>

<paragraph><bold>Predictive Analytics</bold>: Advanced analytics to predict performance trends, identify optimization opportunities, and prevent issues before they impact operations. Analytics platform cost: <underline>moderate annually</underline>.</paragraph>

<sub-heading>7.3: Continuous Improvement and Optimization</sub-heading>

<paragraph><bold>Feedback Integration Systems</bold>: Automated feedback collection from users, customers, and stakeholders with AI-powered sentiment analysis and trend identification. Feedback system cost: <underline>low monthly</underline>.</paragraph>

<paragraph><bold>Performance Optimization Cycles</bold>: Quarterly optimization reviews with data-driven improvements, A/B testing frameworks, and performance tuning. Optimization budget: <underline>modest quarterly</underline> for continuous enhancement.</paragraph>

<sub-heading-bold>Section 8: Risk Management and Mitigation Strategies</sub-heading-bold>

<content><bold>Comprehensive Risk Framework</bold>: Detailed analysis of potential risks across technical, operational, financial, and strategic dimensions with quantified mitigation strategies and contingency planning.</content>

<sub-heading>8.1: Technical Risk Management</sub-heading>

<list>
<bullet><bold>Integration Complexity Risks</bold>: Mitigation through phased integration, extensive testing, and fallback procedures. Risk mitigation cost: <underline>low level</underline>.</bullet>
<bullet><bold>Performance and Scalability Risks</bold>: Load testing, capacity planning, and infrastructure redundancy. Investment in resilience: <underline>moderate level</underline>.</bullet>
<bullet><bold>Data Quality and Security Risks</bold>: Comprehensive data governance, encryption, and access controls. Security investment: <underline>moderate annually</underline>.</bullet>
</list>

<sub-heading>8.2: Business and Market Risk Management</sub-heading>

<list>
<bullet><bold>Market Change Risks</bold>: Scenario planning, flexible architecture, and rapid adaptation capabilities. Adaptation budget: <underline>modest level</underline> for market response.</bullet>
<bullet><bold>Competitive Response Risks</bold>: Continuous monitoring, innovation pipeline, and strategic positioning. Competitive analysis cost: <underline>low monthly</underline>.</bullet>
<bullet><bold>Regulatory and Compliance Risks</bold>: Legal review, compliance monitoring, and regulatory engagement. Compliance cost: <underline>moderate annually</underline>.</bullet>
</list>

<sub-heading-bold>Section 9: Organizational Readiness and Change Management</sub-heading-bold>

<content><bold>Organizational transformation</bold> requires comprehensive change management addressing culture, skills, processes, and technology adoption. Investment in organizational readiness: <underline>moderate level</underline> over 18 months for sustainable transformation.</content>

<sub-heading>9.1: Culture and Leadership Transformation</sub-heading>

<paragraph><bold>Leadership Development</bold>: Executive education, digital literacy programs, and transformation leadership skills. Leadership development cost: <underline>low level</underline>.</paragraph>

<paragraph><bold>Cultural Change Strategy</bold>: Innovation mindset development, collaboration enhancement, and digital-first thinking. Culture transformation investment: <underline>moderate level</underline>.</paragraph>

<sub-heading>9.2: Skills and Capability Development</sub-heading>

<list>
<bullet><bold>Technical Skills Development</bold>: AI/ML literacy, data analysis capabilities, and automation skills. Training cost: <underline>moderate level</underline> for comprehensive upskilling.</bullet>
<bullet><bold>Business Skills Enhancement</bold>: Process optimization, digital collaboration, and customer experience design. Business training budget: <underline>low level</underline>.</bullet>
<bullet><bold>Change Leadership Skills</bold>: Change agent development, communication skills, and stakeholder management. Change leadership cost: <underline>low level</underline>.</bullet>
</list>

<sub-heading-bold>Section 10: Conclusion and Strategic Imperatives</sub-heading-bold>

<content><bold>{company_profile.name}'s readiness</bold>, market opportunity, and technology maturity create optimal conditions for GenAI transformation with projected net benefits of <underline>high returns (400-600% ROI over 3 years)</underline> against total investment of <underline>moderate level</underline> {self._get_citation_tag(real_citations, 11)}.</content>

<paragraph><bold>Strategic Imperatives for Success</bold>: The <bold>{len(use_cases)} strategic initiatives</bold> provide a comprehensive roadmap for transformation success with clear financial returns and competitive advantages.</paragraph>

<list>
<bullet><bold>Leadership Commitment and Investment</bold>: Visible sponsorship, decision-making speed, and committed budget of <underline>moderate level</underline> for full transformation success.</bullet>
<bullet><bold>Change Adoption Excellence</bold>: Strong communication strategy, comprehensive training programs, and user support systems. Change management investment: <underline>low level</underline> for sustainable adoption.</bullet>
<bullet><bold>Governance Discipline and Accountability</bold>: Transparent metrics, risk oversight, clear accountability frameworks, and regular performance reviews. Governance cost: <underline>low annually</underline>.</bullet>
<bullet><bold>Scalability and Flexibility Architecture</bold>: Build for multi-project expansion, cross-department integration, and future innovation. Scalability investment: <underline>moderate level</underline> for flexible infrastructure.</bullet>
<bullet><bold>Continuous Improvement and Innovation</bold>: Regular refinement cycles, feedback integration, and innovation pipeline development. Continuous improvement budget: <underline>low annually</underline>.</bullet>
</list>

<paragraph><bold>Financial Summary and Investment Justification</bold>: Total program investment of <underline>moderate level</underline> delivers projected returns of <underline>high returns (400-600% ROI over 3 years)</underline>, representing 400-600% ROI with 15-20 month payback period. This investment positions {company_profile.name} as a market leader in {company_profile.industry} digital transformation.</paragraph>

<paragraph><bold>Next Steps and Immediate Actions</bold>: Begin Phase 1 activities including stakeholder engagement, detailed planning, environment setup, governance structures, and infrastructure preparation. Immediate investment requirement: <underline>low level</underline> for program initiation.</paragraph>

<list>
<bullet><bold>30-60 Day Horizon</bold>: Establish program charter, finalize KPIs, identify first pilot candidate, launch change communication wave, and secure initial funding of <underline>low level</underline> for foundation activities.</bullet>
<bullet><bold>60-90 Day Horizon</bold>: Complete detailed design, begin infrastructure deployment, start pilot implementation, and establish governance framework. Phase 1 investment: <underline>moderate level</underline>.</bullet>
<bullet><bold>6-12 Month Horizon</bold>: Deliver scaled deployments, refine governance processes, validate ROI projections, and expand roadmap based on success metrics. Scale-up investment: <underline>significant level</underline>.</bullet>
</list>

<paragraph><bold>Critical Decision Points</bold>: Key decision milestones for continued investment, scope adjustments, and strategic pivots based on performance metrics and market conditions. Decision gate criteria include minimum ROI thresholds, adoption rate targets, and technical performance standards.</paragraph>

<paragraph><bold>Long-Term Vision and Sustainability</bold>: Beyond initial transformation, establish {company_profile.name} as a digitally-native organization with continuous innovation capabilities, market leadership position, and sustainable competitive advantages worth <underline>significant long-term value creation</underline>.</paragraph>

CRITICAL REQUIREMENTS FOR ENHANCED DETAIL:

0. DO NOT repeat content or cut off mid-sentence. Each section MUST be unique and non-duplicative with substantial detail
1. Use ALL XML formatting tags consistently throughout the report with enhanced visual hierarchy
2. Embed REAL citations naturally within content using citation name/URL tag pairs
3. Use the provided real web citations throughout the document with proper distribution
4. Create professional, consulting-grade document with rich formatting and detailed analysis
5. Include specific quantified metrics and strategic recommendations with percentage-based improvements
6. Focus on business value and transformation impact with financial projections
7. MANDATORY: Write comprehensive analysis for EVERY single use case with enhanced formatting and detailed financial analysis
8. Use section numbering and logical organization with proper hierarchy
9. Apply formatting tags to emphasize key points effectively throughout
10. Each use case should have its own detailed section with strategic analysis, financial projections, and risk assessment
11. Format the use cases overview as a properly formatted bullet list with bold titles and comprehensive descriptions
12. DISTRIBUTE REAL CITATIONS THROUGHOUT THE ENTIRE DOCUMENT with natural flow
13. Make citations flow naturally within the narrative without forced placement
14. Explicitly address <bold>challenge → solution → impact → financial value</bold> for each use case
15. Include <bold>governance, change management, risk controls, and financial management</bold> in each analysis
16. Provide <bold>phased roadmaps with milestones, timelines, and budget allocations</bold> for each use case
17. Use <bold>leading and lagging KPIs with specific targets and percentage values</bold> for success measurement
18. Ensure <bold>financial linkage with specific percentage amounts</bold> from use case benefits to overall ROI
19. Include <bold>next-step actions with budget requirements</bold> that are tactical and immediate
20. CRITICAL: DO NOT repeat content or cut off mid-sentence - ensure complete, non-repetitive, detailed report
21. CRITICAL: Each section must be unique and provide valuable insights without duplication, with substantial detail and analysis
22. MANDATORY: Express Total Cost of Ownership (TCO), ROI, and investment in qualitative terms or percentages only.
23. MANDATORY: Provide industry-specific insights and benchmarks with financial context
24. MANDATORY: Include detailed risk quantification with financial impact and mitigation costs
25. MANDATORY: Add comprehensive change management sections with detailed budgets and timelines
26. MANDATORY: Include scalability analysis with future financial projections and growth scenarios
27. FORMATTING STRICTNESS: Tags must be well-formed and balanced. Do not produce mismatched tags (❌ <bold>…</b>).
28. Only use these formatting tags: <bold>…</bold>, <italic>…</italic>, <underline>…</underline>.
29. Never use raw HTML tags (<b>, <i>, <u>).
30. Every <paragraph>, <content>, and <list> block must end with its correct closing tag.
31. Tags must be balanced and properly nested (no <bold>…</b> or mixed opens/closes).
32. Run a consistency check: ensure no open tags are left unclosed at the end of each section.



Generate a comprehensive, detailed report that demonstrates deep industry knowledge and provides extensive strategic analysis for ALL {len(use_cases)} transformation use cases using the complete XML formatting structure, REAL web citations throughout, and detailed financial analysis with specific percentage amounts for all improvements, returns, and projections.
            """

        try:
            response = self.report_agent(xml_prompt)
            xml_content = str(response).strip()
            
            logger.info(f"Generated enhanced XML report with real citations: {len(xml_content)} characters")
            return xml_content
            
        except Exception as e:
            logger.error(f"Error generating XML report: {e}")
            return self._create_fallback_xml_report_with_enhanced_formatting(
                company_profile, use_cases, research_data, parsed_files_content, custom_context, scraped_results
            )

    def _is_report_incomplete_or_repetitive(self, xml_content: str) -> bool:
        """Check if the report appears incomplete or contains repetitive content."""
        # Check for common signs of incomplete reports
        if not xml_content or len(xml_content) < 1000:
            return True
        
        # Check for repetition patterns
        lines = xml_content.split('\n')
        unique_lines = set(lines)
        if len(lines) > 0 and len(unique_lines) / len(lines) < 0.7:  # More than 30% repetition
            return True
        
        # Check for incomplete sections
        if not xml_content.endswith('</paragraph>') and not xml_content.endswith('</content>'):
            return True
        
        # Check for truncated content
        if '...' in xml_content[-500:] or '...' in xml_content[-1000:]:
            return True
        
        return False

    def _create_simplified_xml_prompt(self, company_profile: CompanyProfile, use_cases: List[UseCaseStructured], 
                                    research_data: Dict[str, Any], parsed_files_content: str = None,
                                    custom_context: Dict[str, str] = None, real_citations: List[Dict] = None) -> str:
        """Create a simplified XML prompt to prevent token limit issues."""
        
        return f"""
                Generate a concise but comprehensive business transformation report for **{company_profile.name}** using XML-like tags.

                MANDATORY XML TAGS:
                - <heading_bold>Title</heading_bold>
                - <sub-heading-bold>Section Title</sub-heading-bold>
                - <sub-heading>Subsection</sub-heading>
                - <content>Content</content>
                - <paragraph>Paragraph</paragraph>
                - <list>List</list>
                - <bullet>Bullet point</bullet>
                - <bold>Bold text</bold>
                - <italic>Italic text</italic>

                Company: {company_profile.name} ({company_profile.industry})
                Use Cases: {len(use_cases)} transformation initiatives

                Generate a structured report with these sections:
                1. Executive Summary
                2. Strategic Context
                3. Use Case Portfolio
                4. Detailed Use Case Analysis (one paragraph per use case)
                5. Implementation Roadmap
                6. Financial Analysis
                7. Success Metrics
                8. Conclusion

                CRITICAL: Keep each section concise but informative. Avoid repetition. Ensure the report is complete.
                Use citations: {self._format_real_citations_for_prompt(real_citations or [])}
            """

    def _prepare_real_citations_from_web_scraping(self, scraped_results: List[Dict]) -> List[Dict]:
        """Prepare real citations from web scraping results."""
        real_citations = []
        
        if not scraped_results:
            # Fallback citations if no web scraping results
            fallback_citations = [
                {'name': 'McKinsey Digital Transformation Research', 'url': 'https://www.mckinsey.com/capabilities/mckinsey-digital'},
                {'name': 'Deloitte Technology Transformation', 'url': 'https://www.deloitte.com/global/en/services/consulting/services/technology-transformation.html'},
                {'name': 'AWS Digital Transformation Guide', 'url': 'https://aws.amazon.com/digital-transformation/'},
                {'name': 'PwC Digital Strategy Framework', 'url': 'https://www.pwc.com/us/en/services/consulting/digital-strategy.html'},
                {'name': 'BCG Digital Transformation', 'url': 'https://www.bcg.com/capabilities/digital-technology-data/digital-transformation'},
                {'name': 'Gartner Technology Trends', 'url': 'https://www.gartner.com/en/topics/technology-trends'},
                {'name': 'Forrester Digital Transformation', 'url': 'https://www.forrester.com/report-category/digital-transformation/'},
                {'name': 'IDC Technology Research', 'url': 'https://www.idc.com/getdoc.jsp?containerId=prUS48907623'},
                {'name': 'Accenture Technology Vision', 'url': 'https://www.accenture.com/us-en/insights/technology/technology-trends-2024'},
                {'name': 'KPMG Digital Transformation', 'url': 'https://home.kpmg/xx/en/home/insights/2020/04/digital-transformation.html'},
                {'name': 'EY Technology Consulting', 'url': 'https://www.ey.com/en_us/technology-consulting'},
                {'name': 'Bain Digital Transformation', 'url': 'https://www.bain.com/insights/topics/digital-transformation/'},
                {'name': 'Strategy& Digital Strategy', 'url': 'https://www.strategyand.pwc.com/gx/en/unique-solutions/digital-transformation.html'},
                {'name': 'Capgemini Digital Innovation', 'url': 'https://www.capgemini.com/services/digital-innovation/'}
            ]
            return fallback_citations
        
        # Process real scraped results
        for result in scraped_results:
            if result.get('success') and result.get('url') and result.get('title'):
                # Clean and validate the citation
                title = result.get('title', '').strip()
                url = result.get('url', '').strip()
                
                # Skip if title is too short or URL is invalid
                if len(title) < 10 or not url.startswith('http'):
                    continue
                
                # Clean title (remove common prefixes)
                title = re.sub(r'^(Home|About|Contact|Services|Products)\s*[-|]?\s*', '', title)
                
                # Limit title length
                if len(title) > 80:
                    title = title[:77] + "..."
                
                real_citations.append({
                    'name': title,
                    'url': url,
                    'full_name': result.get('title', title)
                })
        
        # If we don't have enough real citations, add some fallbacks
        if len(real_citations) < 5:
            fallback_citations = [
                {'name': 'McKinsey Digital Transformation Research', 'url': 'https://www.mckinsey.com/capabilities/mckinsey-digital'},
                {'name': 'Deloitte Technology Transformation', 'url': 'https://www.deloitte.com/global/en/services/consulting/services/technology-transformation.html'},
                {'name': 'AWS Digital Transformation Guide', 'url': 'https://aws.amazon.com/digital-transformation/'}
            ]
            real_citations.extend(fallback_citations)
        
        return real_citations

    def _format_real_citations_for_prompt(self, real_citations: List[Dict]) -> str:
        """Format real citations for the prompt."""
        if not real_citations:
            return "No real citations available - using fallback citations"
        
        citations_text = "REAL WEB CITATIONS TO USE THROUGHOUT THE REPORT:\n"
        for i, citation in enumerate(real_citations[:15], 1):  # Limit to first 15
            citations_text += f"{i}. {citation['name']} - {citation['url']}\n"
        
        return citations_text

    def _get_citation_tag(self, real_citations: List[Dict], index: int) -> str:
        """Get a citation tag for use in the XML content."""
        if not real_citations or index >= len(real_citations):
            # Return empty string if no citations available
            return ""
        
        citation = real_citations[index % len(real_citations)]
        return f'<citation_name>{citation["name"]}</citation_name><citation_url>{citation["url"]}</citation_url>'

    def _format_use_cases_as_bullet_list(self, use_cases: List[UseCaseStructured]) -> str:
        """Format use cases as a properly formatted bullet list with bold titles and descriptions."""
        bullet_list = []
        
        for uc in use_cases:
            # Create a clean bullet point with bold title and description
            bullet_point = f'<bullet><bold>{uc.title}</bold> - {uc.category}: {uc.business_value}</bullet>'
            bullet_list.append(bullet_point)
        
        return '\n'.join(bullet_list)

    def _format_available_citations(self, scraped_results: List[Dict]) -> str:
        """Format available citations for the prompt."""
        if not scraped_results:
            return "No web citations available"
        
        citations = []
        for i, result in enumerate(scraped_results[:10], 1):  # Limit to first 10
            if result.get('success') and result.get('url'):
                title = result.get('title', 'Web Source')[:60]
                url = result.get('url')
                citations.append(f"{i}. {title} - {url}")
        
        return "Available web citations:\n" + "\n".join(citations) if citations else "No valid citations available"

    def _format_all_use_cases_for_comprehensive_analysis(self, use_cases: List[UseCaseStructured]) -> str:
        """Format ALL use cases for comprehensive analysis in the XML report prompt."""
        formatted_cases = []
        
        for i, uc in enumerate(use_cases, 1):
            formatted_cases.append(f"""
            {i}. **{uc.title}**
               - Category: {uc.category}
               - Current State: {uc.current_state}
               - Proposed Solution: {uc.proposed_solution}
               - Business Value: {uc.business_value}
               - AWS Services: {', '.join(uc.primary_aws_services)}
               - Implementation Phases: {', '.join(uc.implementation_phases)}
               - Timeline: {uc.timeline_months} months
               - Monthly Cost: ${uc.monthly_cost_usd:,}
               - Priority: {uc.priority}
               - Complexity: {uc.complexity}
               - Risk Level: {uc.risk_level}
               - Success Metrics: {', '.join(uc.success_metrics)}
            """)
        
        return f"""
        COMPREHENSIVE USE CASE ANALYSIS REQUIRED FOR ALL {len(use_cases)} INITIATIVES:
        
        {chr(10).join(formatted_cases)}
        
        MANDATORY: Each use case listed above MUST have its own detailed section in the report with comprehensive strategic analysis, technical considerations, business impact assessment, and implementation recommendations using enhanced XML formatting.
        """

    def _create_fallback_xml_report_with_enhanced_formatting(self, company_profile: CompanyProfile, 
                                                           use_cases: List[UseCaseStructured],
                                                           research_data: Dict[str, Any], 
                                                           parsed_files_content: str = None,
                                                           custom_context: Dict[str, str] = None, 
                                                           scraped_results: List[Dict] = None) -> str:
        """Create fallback XML report with enhanced formatting and comprehensive use case analysis."""
        
        enhancement_notes = []
        if research_data.get('web_research_data', {}).get('successful_scrapes', 0) > 0:
            enhancement_notes.append(f"Enhanced with Web Intelligence from {research_data['web_research_data']['successful_scrapes']} sources")
        if parsed_files_content:
            enhancement_notes.append("Enhanced with Document Analysis")
        if custom_context and custom_context.get('processed_prompt'):
            enhancement_notes.append(f"Aligned with Custom Context ({custom_context.get('context_type', 'general')})")
        
        enhancement = f" ({', '.join(enhancement_notes)})" if enhancement_notes else ""
        
        # Get citation URLs from scraped results or use enhanced fallback citations
        citations = self._prepare_real_citations_from_web_scraping(scraped_results) if scraped_results else []
        
        # Generate properly formatted use case bullet list
        use_case_bullets = self._format_use_cases_as_bullet_list(use_cases)
        
        # Generate comprehensive use case sections with enhanced formatting and better citation distribution
        use_case_sections = []
        for i, uc in enumerate(use_cases, 1):
            # Use different citations for different aspects of each use case
            citation_ref = citations[i % len(citations)] if citations else citations[0] if citations else None
            citation_1 = citations[(i * 2) % len(citations)] if citations else citations[0] if citations else None
            citation_2 = citations[(i * 3) % len(citations)] if citations else citations[1] if citations else None
            citation_3 = citations[(i * 4) % len(citations)] if citations else citations[2] if citations else None
            
            # Create citation tags
            citation_tag = self._get_citation_tag(citations, i) if citations else ""
            citation_tag_1 = self._get_citation_tag(citations, i * 2) if citations else ""
            citation_tag_2 = self._get_citation_tag(citations, i * 3) if citations else ""
            citation_tag_3 = self._get_citation_tag(citations, i * 4) if citations else ""
            
            use_case_section = f"""
                <sub-heading>3.{i}: Use Case - {uc.title}</sub-heading>

                <content><bold>Strategic Overview and Business Context</bold>: <italic>{uc.title}</italic> represents a critical transformation initiative for {company_profile.name}, addressing fundamental business challenges through strategic technology adoption. This initiative aligns with industry best practices for <italic>{company_profile.industry}</italic> transformation {citation_tag} and positions the organization for competitive advantage.</content>

                <paragraph><bold>Current State Assessment and Pain Points</bold>: {uc.current_state} This situation creates <underline>operational inefficiencies</underline> and limits {company_profile.name}'s ability to scale effectively. Industry analysis shows that organizations facing similar challenges experience 20-40% operational inefficiencies {citation_tag_1}.</paragraph>

                <paragraph><bold>Proposed Transformation Solution and Technical Architecture</bold>: {uc.proposed_solution} This comprehensive approach leverages <italic>proven methodologies</italic> and cutting-edge technologies to deliver measurable business outcomes {citation_tag_2}.</paragraph>

                <list>
                <bullet><bold>Technology Architecture and AWS Services</bold>: Utilizes {', '.join(uc.primary_aws_services)} as core components for scalable and reliable implementation</bullet>
                <bullet><bold>Business Value and ROI Projections</bold>: {uc.business_value} with projected ROI of 200-400% within 18-24 months</bullet>
                <bullet><bold>Implementation Strategy and Phases</bold>: {uc.timeline_months}-month phased approach with clear milestones and deliverables</bullet>
                <bullet><bold>Success Metrics and KPIs</bold>: {', '.join(uc.success_metrics)} providing clear performance indicators and accountability mechanisms</bullet>
                <bullet><bold>Risk Assessment and Mitigation</bold>: {uc.risk_level} risk profile with comprehensive mitigation strategies including testing, stakeholder engagement, and phased rollout</bullet>
                <bullet><bold>Resource Requirements and Team Structure</bold>: Cross-functional team with expertise in AWS, business analysis, and change management</bullet>
                </list>

                <paragraph><bold>Implementation Roadmap and Timeline</bold>: The {uc.timeline_months}-month implementation follows a structured approach: {', '.join(uc.implementation_phases)}. Each phase builds upon previous successes while minimizing business disruption and maximizing value realization {citation_tag_3}.</paragraph>

                <paragraph><bold>Expected Business Outcomes and Success Metrics</bold>: Success will be measured through comprehensive KPIs including {', '.join(uc.success_metrics)}, providing clear performance indicators and accountability mechanisms. These metrics align with industry standards for <italic>{company_profile.industry}</italic> transformation initiatives and enable continuous improvement throughout the implementation journey.</paragraph>

                <paragraph><bold>Risk Assessment and Mitigation Strategies</bold>: With a {uc.risk_level} risk profile and <italic>{uc.complexity} complexity level</italic>, this initiative requires careful planning and execution. Mitigation strategies include comprehensive testing, stakeholder engagement, phased rollout approaches, continuous monitoring and adjustment, and robust fallback procedures to ensure business continuity.</paragraph>

                <paragraph><bold>Resource Requirements and Team Structure</bold>: Successful implementation requires a cross-functional team with expertise in AWS services, data science, business analysis, and change management, supported by external consultants and technology partners. The team structure ensures proper governance, accountability, and knowledge transfer throughout the transformation journey.</paragraph>

                <paragraph><bold>Strategic Alignment and Business Impact</bold>: This initiative directly addresses {company_profile.name}'s core business challenges while building long-term competitive advantages. The transformation will create measurable business value through improved operational efficiency, enhanced customer experience, and increased market competitiveness, positioning the organization for sustained growth and success.</paragraph>
            """
                    
            use_case_sections.append(use_case_section)
            
            # Combine all sections into the full report with enhanced formatting and better citation distribution
            full_report = f"""<heading_bold>Comprehensive GenAI Transformation Strategy for {company_profile.name}{enhancement}</heading_bold>

                <content>The convergence of <bold>{company_profile.name}'s</bold> comprehensive operations and rapidly advancing GenAI technologies presents a transformational opportunity to revolutionize their position in the <italic>{company_profile.industry}</italic> sector. With organizations achieving <bold>15-65% improvements</bold> in key metrics through GenAI implementations {self._get_citation_tag(citations, 0)}, {company_profile.name}'s strong foundation creates ideal conditions for high-impact AI adoption.</content>

                <sub-heading-bold>Section 1: Strategic Context and Business Position</sub-heading-bold>

                <content><bold>{company_profile.name}</bold> operates as a premier organization in the <italic>{company_profile.industry}</italic> sector, with significant opportunities for technology-enabled transformation {self._get_citation_tag(citations, 1)}. Their established market presence and operational expertise provide the foundation necessary for comprehensive GenAI deployment.</content>

                <sub-heading>1.1: Market Dynamics and Transformation Imperative</sub-heading>

                <content>The <italic>{company_profile.industry}</italic> sector faces accelerating digital pressure that GenAI can uniquely address. Market volatility creates operational challenges throughout value chains {self._get_citation_tag(citations, 2)}, while technology infrastructure complexities strain traditional operational methods. Industry research indicates that early adopters of AI technologies gain significant competitive advantages {self._get_citation_tag(citations, 3)}.</content>

                <sub-heading-bold>Section 2: Comprehensive Use Case Portfolio Analysis</sub-heading-bold>

                <content>Our analysis has identified <bold>{len(use_cases)} strategic transformation initiatives</bold> specifically designed for {company_profile.name}'s operational context. Each use case addresses core business challenges while building capabilities for sustained competitive advantage {self._get_citation_tag(citations, 4)}. These initiatives are based on industry best practices and proven transformation methodologies {self._get_citation_tag(citations, 5)}.</content>

                <sub-heading>2.1: Identified Use Cases Overview</sub-heading>

                <content>Our comprehensive analysis has identified the following strategic transformation opportunities:</content>

                <list>
                {use_case_bullets}
                </list>

                <sub-heading-bold>Section 3: Detailed Use Case Analysis</sub-heading-bold>

                {''.join(use_case_sections)}

                <sub-heading-bold>Section 4: Implementation Roadmap and Strategic Recommendations</sub-heading-bold>

                <content><bold>Success requires disciplined execution</bold> focusing on quick wins while building capabilities for transformational applications. The phased approach minimizes business disruption while maximizing value creation {self._get_citation_tag(citations, 10)}. Industry research demonstrates that organizations following structured implementation methodologies achieve 40-60% better outcomes {self._get_citation_tag(citations, 11)}.</content>

                <sub-heading>4.1: Priority Implementation Sequence</sub-heading>

                <list>
                <bullet><bold>Phase 1</bold>: Foundation and Quick Wins (Months 1-3) — establish baseline capabilities, pilot key initiatives, and validate success metrics.</bullet>
                <bullet><bold>Phase 2</bold>: Core Transformation Initiatives (Months 4-9) — integrate use cases into enterprise systems, scale pilots, and expand adoption programs.</bullet>
                <bullet><bold>Phase 3</bold>: Advanced Capabilities (Months 10-15) — embed predictive and automation capabilities, strengthen governance, and ensure resilience.</bullet>
                <bullet><bold>Phase 4</bold>: Innovation and Optimization (Months 16-18) — drive continuous improvement, adopt emerging technologies, and explore adjacent opportunities.</bullet>
                </list>

                <sub-heading>4.2: Resource Requirements</sub-heading>
                <list>
                <bullet><bold>Leadership</bold>: Dedicated transformation sponsors to ensure accountability.</bullet>
                <bullet><bold>Technical Experts</bold>: Specialists in automation, data engineering, and AI model operations.</bullet>
                <bullet><bold>Business Analysts</bold>: Domain experts aligning solutions with business priorities.</bullet>
                <bullet><bold>Change Management</bold>: Specialists to lead adoption, training, and communication.</bullet>
                <bullet><bold>Governance</bold>: Risk, compliance, and audit professionals ensuring adherence.</bullet>
                </list>

                <sub-heading>4.3: Enablers</sub-heading>
                <list>
                <bullet><bold>Training</bold>: Role-specific upskilling for executives, analysts, and operators.</bullet>
                <bullet><bold>Data Foundations</bold>: Reliable cataloging, lineage, and quality pipelines.</bullet>
                <bullet><bold>Security</bold>: Policies for identity, encryption, and access management.</bullet>
                <bullet><bold>Governance Structures</bold>: Steering committee and risk review cadence.</bullet>
                </list>

                <sub-heading-bold>Section 5: Financial Analysis and ROI Projections</sub-heading-bold>

                <content>Comprehensive financial modeling demonstrates strong ROI potential across initiatives. Based on benchmarks, {company_profile.name} can achieve significant returns within 18-24 months.</content>

                <sub-heading>5.1: Investment Requirements</sub-heading>
                <paragraph><bold>Total Investment</bold>: Approximately <underline>${sum([uc.monthly_cost_usd * uc.timeline_months for uc in use_cases]):,}</underline> over the implementation period, spanning technology, infrastructure, training, and change management.</paragraph>

                <sub-heading>5.2: Expected Returns</sub-heading>
                <list>
                <bullet><bold>Efficiency</bold>: 25-45% improvements in throughput and productivity.</bullet>
                <bullet><bold>Cost Reduction</bold>: 20-35% savings from reduced rework and overhead.</bullet>
                <bullet><bold>Revenue Growth</bold>: 15-30% uplift from faster delivery and enhanced experience.</bullet>
                <bullet><bold>Risk Mitigation</bold>: Reduction in penalties, delays, and compliance failures.</bullet>
                </list>
    
                <paragraph><bold>Payback Period</bold>: ROI within 12-18 months, full payback within 24-30 months.</paragraph>

                <sub-heading>5.3: Sensitivity Analysis</sub-heading>
                <paragraph>Returns modeled under conservative, base, and aggressive adoption scenarios confirm robust performance across varying adoption levels.</paragraph>

                <sub-heading-bold>Section 6: Success Metrics and Performance Monitoring</sub-heading-bold>

                <content>A robust performance framework ensures transparency, accountability, and continuous improvement throughout the transformation journey.</content>

                <list>
                <bullet><bold>Operational Metrics</bold>: Processing time, throughput per employee, and error rates.</bullet>
                <bullet><bold>Customer Metrics</bold>: NPS, satisfaction surveys, and retention rates.</bullet>
                <bullet><bold>Financial Metrics</bold>: ROI realized, cost savings, and incremental revenue.</bullet>
                <bullet><bold>Technology Metrics</bold>: Uptime, latency, adoption rates, and scalability.</bullet>
                <bullet><bold>Governance Metrics</bold>: Compliance adherence, audit readiness, and policy exceptions.</bullet>
                </list>

                <sub-heading>6.1: Monitoring Framework</sub-heading>
                <paragraph>Dashboards with drill-down capabilities will track performance by function and region. Quarterly executive steering reviews and monthly operational reviews will ensure alignment with objectives.</paragraph>

                <sub-heading>6.2: Feedback Loops</sub-heading>
                <paragraph>Embed continuous feedback from users and stakeholders, with iterative updates each quarter to refine adoption and performance.</paragraph>

                <sub-heading-bold>Section 7: Conclusion and Strategic Imperatives</sub-heading-bold>

                <content><bold>{company_profile.name}'s readiness</bold>, combined with favorable market dynamics and strong technology maturity, create an ideal environment for GenAI transformation {self._get_citation_tag(citations, 12)}. Early adoption ensures outsized competitive advantages {self._get_citation_tag(citations, 13)}.</content>

                <list>
                <bullet><bold>Leadership Commitment</bold>: Sponsorship and alignment from the top.</bullet>
                <bullet><bold>Change Adoption</bold>: User training, communication, and engagement plans.</bullet>
                <bullet><bold>Governance</bold>: Clear accountability, transparency, and risk oversight.</bullet>
                <bullet><bold>Scalability</bold>: Flexible frameworks supporting cross-enterprise expansion.</bullet>
                <bullet><bold>Continuous Improvement</bold>: Iterative cycles ensuring resilience and relevance.</bullet>
                </list>

                <paragraph><bold>Next Steps</bold>: Begin Phase 1 activities including stakeholder alignment, program chartering, pilot launch, and initial governance setup.</paragraph>

                <paragraph><bold>30–60 Day Horizon</bold>: Establish KPIs, identify pilot project, and initiate change communications.</paragraph>

                <paragraph><bold>6–12 Month Horizon</bold>: Scale deployments, refine governance, validate ROI, and expand use case portfolio.</paragraph>
            """

        
        return full_report

    def _generate_and_upload_pdf_from_xml(self, xml_content: str, company_name: str, session_id: str) -> Optional[str]:
        """Generate PDF from enhanced XML content and upload to S3."""
        
        try:
            # Parse XML content with enhanced formatting support
            parsed_content = ReportXMLParser.parse_xml_tags(xml_content)
            
            # Create temp directory
            tmp_dir = os.path.join(LAMBDA_TMP_DIR, session_id)
            os.makedirs(tmp_dir, exist_ok=True)
            
            pdf_filename = os.path.join(tmp_dir, f"transformation_report_{session_id}.pdf")
            
            if REPORTLAB_AVAILABLE:
                # Use ReportLab to create professional PDF with enhanced formatting
                self._create_professional_pdf_with_enhanced_formatting(parsed_content, pdf_filename, company_name)
                logger.info(f"✅ Enhanced PDF generated using ReportLab: {pdf_filename}")
                
            else:
                logger.error("❌ No PDF generation libraries available")
                return None
            
            # Verify PDF was created
            if not os.path.exists(pdf_filename) or os.path.getsize(pdf_filename) == 0:
                logger.error("❌ PDF file was not created or is empty")
                return None
            
            # Save a local copy in ./reports directory
            
         #   try:
                # Create the local reports directory if it doesn't exist
               # local_reports_dir = os.path.join(os.getcwd(), "reports")
               # os.makedirs(local_reports_dir, exist_ok=True)
                # Generate a timestamp for the filename
               # ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                # Sanitize the company name for safe filenames
               # safe_company = re.sub(r"[^A-Za-z0-9_-]+", "_", company_name).strip("_")
                # Build the local PDF path
               # local_pdf_path = os.path.join(local_reports_dir, f"{safe_company}_transformation_report_{session_id}_{ts}.pdf")
                # Copy the generated PDF to the local reports directory
                # shutil.copyfile(pdf_filename, local_pdf_path)
               # logger.info(f"💾 Local PDF saved at: {local_pdf_path}")
           # except Exception as e:
              #  logger.warning(f"Failed to save local PDF copy: {e}")
                
            
            # Upload to S3
            s3_url = self._upload_pdf_to_s3(pdf_filename, session_id, company_name)
            
            # Cleanup
            try:
                if os.path.exists(pdf_filename):
                    os.unlink(pdf_filename)
            except Exception as e:
                logger.warning(f"Failed to cleanup PDF file: {e}")
            
            return s3_url
            
        except Exception as e:
            logger.error(f"❌ Enhanced PDF generation failed: {e}")
            return None

    def _create_professional_pdf_with_enhanced_formatting(self, parsed_content: Dict[str, Any], pdf_filename: str, company_name: str):
        """Create professional PDF using ReportLab with enhanced formatting support."""
        
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import black, blue, HexColor
        from reportlab.platypus.flowables import HRFlowable
        
        # Create PDF document
        doc = SimpleDocTemplate(
            pdf_filename, 
            pagesize=A4,
            rightMargin=0.75*inch, 
            leftMargin=0.75*inch,
            topMargin=0.75*inch, 
            bottomMargin=0.75*inch
        )
        
        # Get base styles
        styles = getSampleStyleSheet()
        
        # Create enhanced custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Title'],
            fontSize=22,
            spaceAfter=30,
            spaceBefore=20,
            textColor=HexColor('#2C3E50'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=26
        )
        
        # Enhanced heading styles
        main_heading_style = ParagraphStyle(
            'MainHeading',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            spaceBefore=28,
            textColor=HexColor('#34495E'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=20
        )
        
        sub_heading_bold_style = ParagraphStyle(
            'SubHeadingBold',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=18,
            spaceBefore=24,
            textColor=HexColor('#2C3E50'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=18
        )
        
        sub_heading_style = ParagraphStyle(
            'SubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=14,
            spaceBefore=18,
            textColor=HexColor('#34495E'),
            fontName='Helvetica-Bold',
            alignment=0,
            leading=16
        )
        
        # Enhanced content styles
        content_style = ParagraphStyle(
            'ContentText',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            spaceBefore=6,
            alignment=4,  # Justified
            textColor=black,
            fontName='Helvetica',
            leading=16,
            leftIndent=0,
            rightIndent=0
        )
        
        paragraph_style = ParagraphStyle(
            'ParagraphText',
            parent=content_style,
            fontSize=11,
            spaceAfter=10,
            spaceBefore=4,
            alignment=4,
            leading=15
        )
        
        # List styles
        bullet_style = ParagraphStyle(
            'BulletText',
            parent=content_style,
            fontSize=11,
            spaceAfter=6,
            spaceBefore=3,
            leftIndent=20,
            bulletIndent=10,
            leading=14
        )
        
        # Build story
        story = []
        
        # Add title
        title = parsed_content.get('title', f'GenAI Transformation Strategy for {company_name}')
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Add horizontal rule
        story.append(HRFlowable(width="100%", thickness=2, color=HexColor('#3498DB')))
        story.append(Spacer(1, 20))
        
        # Process content sections with enhanced formatting
        for section in parsed_content.get('sections', []):
            if section.get('content', '').strip():
                section_type = section.get('type', 'content')
                section_content = section.get('content', '')
                
                # Clean content for PDF and enhance inline citations
                cleaned_content = self._enhance_inline_citations_for_pdf(
                    section_content, 
                    parsed_content.get('citations', {})
                )
                
                # Apply appropriate style based on section type
                if section_type == 'heading_bold':
                    story.append(Paragraph(cleaned_content, main_heading_style))
                elif section_type == 'sub-heading-bold':
                    story.append(Paragraph(cleaned_content, sub_heading_bold_style))
                elif section_type == 'sub-heading':
                    story.append(Paragraph(cleaned_content, sub_heading_style))
                elif section_type == 'paragraph':
                    story.append(Paragraph(cleaned_content, paragraph_style))
                elif section_type == 'content':
                    story.append(Paragraph(cleaned_content, content_style))
                elif section_type == 'list':
                    # Process list items within the list - handle both bullet points and numbered items
                    # Split by bullet points first
                    bullet_items = [item.strip() for item in cleaned_content.split('•') if item.strip()]
                    for item in bullet_items:
                        if item:
                            story.append(Paragraph(f"• {item}", bullet_style))
                    
                    # Also handle numbered items if they exist
                    numbered_items = re.findall(r'\d+\.\s*(.*?)(?=\d+\.|$)', cleaned_content, re.DOTALL)
                    for item in numbered_items:
                        if item.strip():
                            story.append(Paragraph(f"• {item.strip()}", bullet_style))
                else:
                    # Default to content style
                    story.append(Paragraph(cleaned_content, content_style))
                
                story.append(Spacer(1, 8))
        
        # Add citation summary section
        citations = parsed_content.get('citations', {})
        if citations:
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#BDC3C7')))
            story.append(Spacer(1, 15))
            story.append(Paragraph("Citation Sources", sub_heading_bold_style))
            story.append(Spacer(1, 10))
            
            for citation_num, citation_info in citations.items():
                citation_name = citation_info.get('full_name', citation_info.get('name', 'Source'))
                citation_url = citation_info.get('url', '#')
                
                # Create reference entry
                citation_text = f'[{citation_num}] <link href="{citation_url}">{citation_url}</link>'
                story.append(Paragraph(citation_text, content_style))
                story.append(Spacer(1, 4))
        
        # Build PDF
        doc.build(story)

    def _enhance_inline_citations_for_pdf(self, content: str, citations: Dict[str, Any]) -> str:
        """Enhance inline citations and formatting tags for PDF generation with better distribution."""
        
        # Remove any remaining XML content tags
        content = re.sub(r'</?content>', '', content)
        content = re.sub(r'</?paragraph>', '', content)
        content = re.sub(r'</?section>', '', content)
        
        # Enhance existing link tags to have round appearance
        def enhance_citation_link(match):
            href = match.group(1)
            citation_num = match.group(2)
            
            # Find citation info
            citation_info = citations.get(citation_num, {})
            citation_name = citation_info.get('name', 'Source')
            
            # Create enhanced round citation with background color
            return f'<link href="{href}"><b><font face="Helvetica-Bold" size="8">&nbsp;[{citation_num}]&nbsp;</font></b></link>'
        
        # Pattern to find existing citation links
        citation_link_pattern = r'<link href="([^"]*)"><u>\[(\d+)\]</u></link>'
        content = re.sub(citation_link_pattern, enhance_citation_link, content)
        
        # Clean up extra whitespace and formatting
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Ensure proper spacing around citations
        content = re.sub(r'(\w)\[(\d+)\]', r'\1 [\2]', content)
        content = re.sub(r'\[(\d+)\](\w)', r'[\1] \2', content)
        
        return content

    def _upload_pdf_to_s3(self, pdf_path: str, session_id: str, company_name: str) -> Optional[str]:
        """Upload PDF to S3 and return object URL."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"transformation-reports/{session_id}/comprehensive-analysis/{timestamp}_transformation_report.pdf"
            
            # Upload to S3
            s3_client.upload_file(
                pdf_path,
                S3_BUCKET,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf',
                    'Metadata': {
                        'session_id': session_id,
                        'company_name': company_name,
                        'report_type': 'comprehensive_transformation_analysis_with_enhanced_formatting',
                        'generated_at': timestamp
                    }
                }
            )
            
            # Generate object URL
            s3_object_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"✅ Enhanced PDF uploaded to S3: {s3_key}")
            return s3_object_url
            
        except Exception as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return None