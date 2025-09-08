"""
Enhanced company research agent with web scraping, custom prompt processing, and file content integration.
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from strands import Agent, tool
from strands_tools import retrieve, http_request
from strands.agent.conversation_manager import SlidingWindowConversationManager

from src.core.bedrock_manager import EnhancedModelManager
from src.services.web_scraper import WEB_SCRAPING_AVAILABLE, WebScraper
from src.utils.status_tracker import StatusTracker, StatusCheckpoints
from src.utils.prompt_processor import CustomPromptProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompanyResearchSwarm:
    """Enhanced research coordinator with web scraping, custom prompts, and document analysis capabilities."""
    
    def __init__(self, model_manager: EnhancedModelManager):
        self.model_manager = model_manager
        self.conversation_manager = SlidingWindowConversationManager(window_size=20)
        
        # Initialize web scraper if available
        if WEB_SCRAPING_AVAILABLE:
            self.web_scraper = WebScraper()
            logger.info("✅ Web scraper initialized")
        else:
            self.web_scraper = None
            logger.warning("⚠️ Web scraping not available")

        # Research coordination agent with enhanced capabilities
        self.coordinator = Agent(
            model=model_manager.research_model,
            system_prompt="""You are a Senior Business Research Analyst specializing in comprehensive company analysis and strategic market intelligence.

                Your expertise includes:
                - Deep business model analysis and operational assessment
                - Industry dynamics and competitive landscape evaluation
                - Technology infrastructure and digital maturity analysis
                - Financial performance and growth trajectory assessment
                - Regulatory environment and compliance requirements
                - Organizational structure and talent capabilities
                - Market positioning and customer base analysis
                - Strategic challenges and transformation opportunities

                When provided with web-scraped content, use it as primary intelligence alongside document analysis.

                Focus on practical business insights that enable strategic decision-making and transformation planning that aligns with any custom context provided.
            """,
            tools=[http_request, retrieve],
            conversation_manager=self.conversation_manager
        )

    def conduct_comprehensive_research(self, company_name: str, company_url: str, 
                                     status_tracker: StatusTracker = None, 
                                     parsed_files_content: str = None,
                                     custom_context: Dict[str, str] = None) -> Dict[str, Any]:
        """Conduct enhanced business research with web scraping, custom prompt and file content integration."""
        
        if status_tracker:
            status_tracker.update_status(
                StatusCheckpoints.RESEARCH_STARTED,
                {
                    'company_name': company_name, 
                    'company_url': company_url, 
                    'has_files': bool(parsed_files_content),
                    'has_custom_context': bool(custom_context and custom_context.get('processed_prompt')),
                    'web_scraping_enabled': WEB_SCRAPING_AVAILABLE
                },
                current_agent='research_coordinator'
            )
        
        # Perform web scraping research
        web_research_data = None
        if WEB_SCRAPING_AVAILABLE:
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.WEB_SCRAPING_STARTED,
                    {'scraping_method': 'beautiful_soup_google_search'},
                    current_agent='web_scraper'
                )
            
            web_research_data = self.web_scraper.comprehensive_research(
                company_name, company_url, custom_context
            )
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.WEB_SCRAPING_COMPLETED,
                    {
                        'urls_scraped_count': len(web_research_data.get('urls_scraped', [])),
                        'urls_scraped_list': web_research_data.get('urls_scraped', []),
                        'successful_scrapes': web_research_data.get('successful_scrapes', 0),
                        'total_attempts': web_research_data.get('total_urls_attempted', 0)
                    },
                    current_agent='web_scraper'
                )
        
        # Create contextual prompt with web content, file content and custom context
        web_context = ""
        if web_research_data and web_research_data.get('research_content'):
            web_context = f"""
            
                WEB-SCRAPED BUSINESS INTELLIGENCE:
                The following content was scraped from {web_research_data.get('successful_scrapes', 0)} websites using Google Search and Beautiful Soup:

                {web_research_data['research_content'][:6000]}

                This provides comprehensive market intelligence and business context from multiple authoritative sources.
            """

        file_context = ""
        if parsed_files_content:
            file_context = f"""
            
                DOCUMENT ANALYSIS INTELLIGENCE:
                The following content was extracted from uploaded company documents:

                {parsed_files_content[:6000]}

                This provides internal operational intelligence and company-specific context from official documents.
            """

        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""
            
                CUSTOM RESEARCH CONTEXT:
                {custom_context['processed_prompt'][:2000]}
                
                Focus Areas: {', '.join(custom_context.get('focus_areas', []))}
                Context Type: {custom_context.get('context_type', 'general')}
            """

        base_research_prompt = f"""
        Conduct a comprehensive business analysis for {company_name} ({company_url}).

        RESEARCH SCOPE:
        Analyze the company's business model, operations, industry position, strategic challenges, and transformation opportunities.

        ANALYSIS FRAMEWORK:
        1. Business Model & Revenue Streams
        2. Market Position & Competitive Dynamics  
        3. Technology Infrastructure & Digital Maturity
        4. Operational Processes & Efficiency
        5. Financial Performance & Growth Trajectory
        6. Strategic Challenges & Pain Points
        7. Transformation Opportunities & Innovation Potential
        8. Regulatory Environment & Compliance Requirements
        9. Organizational Structure & Talent Capabilities
        10. Customer Base & Market Segments

        {web_context}
        {file_context}
        {custom_context_section}

        Provide actionable business intelligence that enables strategic transformation planning and competitive advantage development.
        """

        # Integrate custom context if provided
        if custom_context and custom_context.get('processed_prompt'):
            research_prompt = CustomPromptProcessor.integrate_prompt_into_research(base_research_prompt, custom_context)
            logger.info(f"Research prompt enhanced with custom context: {custom_context.get('context_type', 'unknown')}")
        else:
            research_prompt = base_research_prompt
        
        try:
            logger.info(f"Starting comprehensive business analysis for {company_name}")
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.RESEARCH_IN_PROGRESS,
                    {
                        'research_phase': 'analyzing_business_model_and_operations', 
                        'using_web_content': bool(web_research_data),
                        'using_file_content': bool(parsed_files_content),
                        'using_custom_context': bool(custom_context and custom_context.get('processed_prompt'))
                    },
                    current_agent='research_coordinator'
                )
            
            # Conduct business-focused research
            research_result = self.coordinator(research_prompt)
            
            # Get URLs from web research
            scraped_urls = web_research_data.get('urls_scraped', []) if web_research_data else []
            if company_url not in scraped_urls:
                scraped_urls.append(company_url)
            
            # Enhanced business analysis findings
            enhancement_notes = []
            if web_research_data:
                enhancement_notes.append(f"Web Intelligence from {web_research_data.get('successful_scrapes', 0)} sources")
            if parsed_files_content:
                enhancement_notes.append("Document Analysis")
            if custom_context and custom_context.get('processed_prompt'):
                enhancement_notes.append(f"Custom Context ({custom_context.get('context_type', 'general')})")
            
            enhancement_note = f" - Enhanced with: {', '.join(enhancement_notes)}" if enhancement_notes else ""
            
            enhanced_findings = f"""
            COMPREHENSIVE BUSINESS ANALYSIS FOR {company_name}{enhancement_note}
            
            {str(research_result)}
            """
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.RESEARCH_COMPLETED,
                    {
                        'total_urls_scraped': len(scraped_urls),
                        'scraped_urls_list': scraped_urls,
                        'successful_web_scrapes': web_research_data.get('successful_scrapes', 0) if web_research_data else 0,
                        'research_method': 'web_scraping_with_beautiful_soup_and_google_search',
                        'web_enhanced': bool(web_research_data),
                        'custom_context_integrated': bool(custom_context and custom_context.get('processed_prompt'))
                    },
                    current_agent='research_coordinator'
                )
            
            return {
                'research_findings': enhanced_findings,
                'research_timestamp': datetime.now().isoformat(),
                'research_method': 'web_scraping_with_beautiful_soup_and_google_search',
                'company_url_analyzed': company_url,
                'urls_scraped': scraped_urls,
                'total_urls_processed': len(scraped_urls),
                'web_research_data': web_research_data,
                'successful_web_scrapes': web_research_data.get('successful_scrapes', 0) if web_research_data else 0,
                'file_content_used': bool(parsed_files_content),
                'file_content_length': len(parsed_files_content) if parsed_files_content else 0,
                'custom_context_used': bool(custom_context and custom_context.get('processed_prompt')),
                'custom_context_type': custom_context.get('context_type') if custom_context else None,
                'custom_focus_areas': custom_context.get('focus_areas') if custom_context else []
            }
            
        except Exception as e:
            logger.error(f"Research error: {e}")
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.ERROR,
                    {'error_type': 'research_error', 'error_message': str(e)}
                )
            return self._create_fallback_research(company_name, company_url, parsed_files_content, custom_context, web_research_data)

    def _create_fallback_research(self, company_name: str, company_url: str, 
                                 parsed_files_content: str = None,
                                 custom_context: Dict[str, str] = None,
                                 web_research_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create fallback research with web scraping, custom context and file content."""
        
        web_insight = ""
        if web_research_data and web_research_data.get('successful_scrapes', 0) > 0:
            web_insight = f"\nWeb Intelligence: Analysis enhanced with insights from {web_research_data['successful_scrapes']} web sources using Google Search and Beautiful Soup."
        
        file_insight = ""
        if parsed_files_content:
            file_insight = f"\nDocument Analysis: Based on uploaded documents, business context and operational insights have been incorporated."
        
        custom_insight = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_insight = f"\nCustom Context Integration: Analysis has been tailored to focus on {', '.join(custom_context.get('focus_areas', []))} as specified in the custom requirements."
        
        fallback_research = f"""
        BUSINESS TRANSFORMATION ANALYSIS FOR {company_name}
        
        Based on available information and industry best practices, this analysis provides strategic transformation insights for {company_name} ({company_url}).
        
        STRATEGIC BUSINESS ASSESSMENT:
        
        1. BUSINESS MODEL ANALYSIS
        - Revenue diversification opportunities through digital channels
        - Operational efficiency improvements via automation and process optimization
        - Customer experience enhancement through technology integration
        - Market expansion potential in adjacent segments
        
        2. TECHNOLOGY TRANSFORMATION OPPORTUNITIES
        - Cloud infrastructure modernization for scalability and cost optimization
        - Data analytics and business intelligence implementation
        - AI/ML integration for predictive insights and automation
        - Digital workflow optimization and collaboration tools
        
        3. OPERATIONAL EXCELLENCE INITIATIVES
        - Process standardization and automation opportunities
        - Supply chain optimization and visibility improvements
        - Quality management system enhancements
        - Performance monitoring and KPI dashboard implementation
        
        4. STRATEGIC GROWTH ENABLERS
        - Digital marketing and customer acquisition optimization
        - Partnership and ecosystem development opportunities
        - Innovation programs and R&D investment areas
        - Talent development and organizational capability building
        
        5. COMPETITIVE POSITIONING
        - Market differentiation through technology adoption
        - Customer value proposition enhancement
        - Operational cost reduction and margin improvement
        - Speed-to-market acceleration through digital tools
        
        {web_insight}
        {file_insight}
        {custom_insight}
        
        This analysis provides a foundation for strategic transformation planning and competitive advantage development.
        """
        
        scraped_urls = web_research_data.get('urls_scraped', []) if web_research_data else []
        if company_url not in scraped_urls:
            scraped_urls.append(company_url)
        
        return {
            'research_findings': fallback_research,
            'research_timestamp': datetime.now().isoformat(),
            'research_method': 'fallback_with_web_enhancement',
            'company_url_analyzed': company_url,
            'urls_scraped': scraped_urls,
            'total_urls_processed': len(scraped_urls),
            'web_research_data': web_research_data,
            'successful_web_scrapes': web_research_data.get('successful_scrapes', 0) if web_research_data else 0,
            'file_content_used': bool(parsed_files_content),
            'file_content_length': len(parsed_files_content) if parsed_files_content else 0,
            'custom_context_used': bool(custom_context and custom_context.get('processed_prompt')),
            'custom_context_type': custom_context.get('context_type') if custom_context else None,
            'custom_focus_areas': custom_context.get('focus_areas') if custom_context else [],
            'fallback_reason': 'primary_research_failed'
        }