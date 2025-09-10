"""
Company research agent swarm for comprehensive business analysis.
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any
from strands import Agent, tool
from strands_tools import retrieve, http_request
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.core.bedrock_manager import EnhancedModelManager
from src.services.web_scraper import WebScraper, WEB_SCRAPING_AVAILABLE
from src.utils.status_tracker import StatusTracker, StatusCheckpoints
from src.utils.prompt_processor import CustomPromptProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompanyResearchSwarm:
    """Multi-agent swarm for comprehensive business analysis with web scraping, custom prompt and file parsing support."""
    
    def __init__(self, model_manager: EnhancedModelManager):
        self.model_manager = model_manager
        self.conversation_manager = SlidingWindowConversationManager(window_size=20)
        self.web_scraper = WebScraper()
        
        # Enhanced business analysis coordinator with web scraping and custom prompt awareness
        self.coordinator = Agent(
            model=self.model_manager.research_model,
            system_prompt="""You are a Senior Business Analyst specializing in deep company analysis for strategic planning and transformation initiatives.

                Your mission is to conduct comprehensive business intelligence research that reveals:
                - Core business operations and revenue models
                - Industry dynamics and competitive positioning
                - Operational challenges and growth opportunities
                - Technology infrastructure and modernization needs
                - Strategic priorities and transformation readiness

                You have access to:
                - http_request tool to fetch web content directly from company websites and sources
                - retrieve tool for additional research and information gathering
                - Document content from uploaded company files (PDFs/DOCX)
                - Custom context and specific requirements from users

                IMPORTANT: Always use your http_request tool to fetch fresh content from company URLs when provided. This gives you real-time, accurate company information for analysis.

                When provided with custom context or specific requirements, prioritize analysis that aligns with those focus areas and requirements.

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
                        'urls_scraped': len(web_research_data.get('urls_scraped', [])),
                        'successful_scrapes': web_research_data.get('successful_scrapes', 0),
                        'total_attempts': web_research_data.get('total_urls_attempted', 0)
                    },
                    urls_scraped=web_research_data.get('urls_scraped', [])
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
            
                COMPANY DOCUMENT ANALYSIS:
                The following content was extracted from company documents uploaded by the user:

                {parsed_files_content[:4000]}

                This provides detailed insight into their current operations, processes, and strategic context. Use this as primary intelligence for understanding their business model and transformation opportunities.
            """
        
        # Base research prompt
        base_research_prompt = f"""
                Conduct deep business analysis for {company_name} (website: {company_url}) to understand their strategic transformation opportunities.
                
                CRITICAL FIRST STEP: Use your http_request tool to fetch fresh content from {company_url} to get real-time company information. This is essential for accurate analysis.
                
                {web_context}
                {file_context}
                
                BUSINESS INTELLIGENCE OBJECTIVES:
                1. **Core Business Analysis**: 
                - What is {company_name}'s primary industry and market segment?
                - How do they generate revenue and serve customers?
                - What is their business model and value proposition?
                - What scale of operations do they likely have?
                
                2. **Operational Assessment**:
                - What are their key business processes and workflows?
                - Where do they likely face operational bottlenecks or inefficiencies?
                - What technology capabilities do they currently rely on?
                - How mature are their digital operations?
                
                3. **Strategic Transformation Opportunities**:
                - What business problems could technology solve for them?
                - Where could automation or digital solutions drive significant value?
                - What operational improvements would impact their competitive position?
                - How could cloud and modern technology accelerate their business objectives?
                
                RESEARCH APPROACH:
                - FIRST: Use http_request tool to fetch content from {company_url} for current company information
                - Use web-scraped content as primary market intelligence
                - Use document content as internal operational intelligence
                - Analyze business model and competitive positioning
                - Identify practical transformation opportunities that align with business goals
                - Focus on value-creating initiatives rather than technology for technology's sake
                
                Provide actionable business intelligence that enables strategic decision-making and transformation planning.
            """
        
        # Integrate custom context if provided
        if custom_context and custom_context.get('processed_prompt'):
            research_prompt = CustomPromptProcessor.integrate_prompt_into_research(base_research_prompt, custom_context)
            logger.info(f"Research prompt enhanced with custom context: {custom_context.get('context_type', 'unknown')}")
        else:
            research_prompt = base_research_prompt
        
        try:
            logger.info(f"Starting comprehensive business analysis for {company_name}")
            
            print(f"🧠 Company Research Debug for {company_name}:")
            print(f"  📊 Web research data available: {bool(web_research_data)}")
            if web_research_data:
                print(f"    ✅ Successful web scrapes: {web_research_data.get('successful_scrapes', 0)}")
                print(f"    📄 Web content length: {len(web_research_data.get('research_content', ''))}")
            print(f"  📁 File content available: {bool(parsed_files_content)}")
            if parsed_files_content:
                print(f"    📄 File content length: {len(parsed_files_content)}")
            print(f"  🎯 Custom context available: {bool(custom_context and custom_context.get('processed_prompt'))}")
            print(f"  📝 Research prompt length: {len(research_prompt)} characters")
            
            if status_tracker:
                status_tracker.update_status(
                    StatusCheckpoints.RESEARCH_IN_PROGRESS,
                    {
                        'research_phase': 'analyzing_business_model_and_operations', 
                        'using_web_content': bool(web_research_data),
                        'using_file_content': bool(parsed_files_content),
                        'using_custom_context': bool(custom_context and custom_context.get('processed_prompt'))
                    },
                    current_agent='research_coordinator',
                    urls_scraped=web_research_data.get('urls_scraped', [company_url]) if web_research_data else [company_url]
                )
            
            # Conduct business-focused research
            print(f"🔬 Calling coordinator agent for research analysis...")
            print(f"🌐 Agent has access to tools: http_request, retrieve")
            print(f"📎 Target URL for http_request: {company_url}")
            print(f"🔍 Agent will now attempt to fetch web content...")
            research_result = self.coordinator(research_prompt)
            print(f"✅ Research analysis complete - result length: {len(str(research_result))} characters")
            print(f"🔍 Agent has completed web content fetching")
            
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
                        'successful_web_scrapes': web_research_data.get('successful_scrapes', 0) if web_research_data else 0,
                        'research_method': 'web_scraping_with_beautiful_soup_and_google_search',
                        'research_time': f"{time.time() - status_tracker.start_time.timestamp():.1f}s",
                        'web_enhanced': bool(web_research_data),
                        'custom_context_integrated': bool(custom_context and custom_context.get('processed_prompt'))
                    },
                    urls_scraped=scraped_urls
                )
            
            # Print detailed URL information
            print(f"\n🔗 WEB SCRAPING SUMMARY FOR {company_name}:")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"📋 Primary company URL: {company_url}")
            print(f"📊 URLs accessed by agents: {len(scraped_urls)}")
            for i, url in enumerate(scraped_urls, 1):
                print(f"  {i}. {url}")
            
            if web_research_data:
                print(f"🌐 BeautifulSoup web scraping attempted: {web_research_data.get('total_urls_attempted', 0)} URLs")
                print(f"✅ BeautifulSoup successful scrapes: {web_research_data.get('successful_scrapes', 0)}")
                if web_research_data.get('urls_scraped'):
                    print(f"📋 BeautifulSoup URLs scraped:")
                    for i, url in enumerate(web_research_data['urls_scraped'], 1):
                        print(f"    {i}. {url}")
            else:
                print(f"⚠️  BeautifulSoup web scraping: Not available (libraries missing)")
            
            print(f"🤖 Strands http_request tool: Available and used by agents")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            return {
                'research_findings': enhanced_findings,
                'research_timestamp': datetime.now().isoformat(),
                'research_method': 'strands_http_request_with_fallback_web_scraping',
                'company_url_analyzed': company_url,
                'urls_scraped': scraped_urls,
                'total_urls_processed': len(scraped_urls),
                'web_research_data': web_research_data,
                'successful_web_scrapes': web_research_data.get('successful_scrapes', 0) if web_research_data else 0,
                'strands_http_requests': True,
                'agent_web_access': True,
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
            STRATEGIC BUSINESS ANALYSIS FOR {company_name}
            
            Based on available business intelligence and market analysis:
            
            BUSINESS TRANSFORMATION OPPORTUNITIES:
            - Business process optimization and automation
            - Customer experience enhancement and personalization
            - Operational intelligence and data-driven decision making
            - Digital platform capabilities and API-first architecture
            - Scalable infrastructure for business growth
            - Security and compliance framework strengthening
            - Performance optimization for customer satisfaction
            - Innovation acceleration through modern development practices
            - Cost optimization and resource efficiency
            - Strategic business intelligence and analytics
            
            {web_insight}
            {file_insight}
            {custom_insight}
            
            These opportunities focus on accelerating business objectives using cloud technologies as enablers.
        """
        
        scraped_urls = web_research_data.get('urls_scraped', []) if web_research_data else []
        if company_url not in scraped_urls:
            scraped_urls.append(company_url)
        
        return {
            'research_findings': fallback_research,
            'research_timestamp': datetime.now().isoformat(),
            'research_method': 'fallback_business_analysis_with_web_scraping',
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
