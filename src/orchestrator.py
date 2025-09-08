"""
Main orchestrator for the Business Transformation Agent.
"""
import logging
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Any, List, Optional

from strands import Agent

from src.agents.company_research import CompanyResearchSwarm
from src.agents.report_generator import ConsolidatedReportGenerator
from src.agents.use_case_generator import DynamicUseCaseGenerator, OutputParser
from src.core.bedrock_manager import EnhancedModelManager
from src.core.models import CompanyProfile, UseCase, CompanyInfo
from src.services.web_scraper import WEB_SCRAPING_AVAILABLE
from src.utils.cache_manager import CacheManager
from src.utils.file_parser import FileParser
from src.utils.prompt_processor import CustomPromptProcessor
from src.utils.session_manager import SessionManager
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenticWAFROrchestrator:
    """Enhanced orchestrator with web scraping, custom prompt processing, file parsing, personalized use case generation, and comprehensive reporting."""

    def __init__(self):
        self.model_manager = EnhancedModelManager()
        self.research_swarm = CompanyResearchSwarm(self.model_manager)
        self.dynamic_use_case_generator = DynamicUseCaseGenerator(self.model_manager)
        self.consolidated_report_generator = ConsolidatedReportGenerator(self.model_manager)
        self.session_store = {}

        # Add session manager for duplicate prevention
        self.session_manager = SessionManager()

        # Business analysis extractor agent
        self.profile_extractor = Agent(
            model=self.model_manager.research_model,
            system_prompt="""You are a Senior Business Intelligence Analyst specializing in extracting actionable company insights.
                Analyze the provided business research data and extract key company information for strategic transformation planning. Focus on practical business context that enables strategic decision-making and transformation initiatives.

                When web-scraped content is provided, use it as primary market intelligence.
                When document content is provided, use it as internal operational intelligence.
                When custom context or specific requirements are provided, ensure analysis aligns with those priorities and focus areas.

                Extract insights about:
                - Core business operations and value creation
                - Strategic challenges and growth opportunities  
                - Technology readiness and transformation capacity
                - Market position and competitive dynamics
                - Specific operational processes and departments mentioned
                - Geographic markets and regulatory context
                - Team size and organizational structure implications
             """
        )
    logger.info("✅ Ocestrator Initialized")

    def process_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process transformation request with web scraping, custom prompt, file parsing, personalized use case generation, and consolidated reporting."""
        try:
            company_name = payload.get('company_name', '').strip()
            company_url = payload.get('company_url', '').strip()
            session_id = payload.get('session_id', str(uuid.uuid4()))
            action = payload.get('action', 'start')
            selected_use_case_ids = payload.get('selected_use_case_ids', [])
            project_id = payload.get('project_id', 'default_project')
            user_id = payload.get('user_id', 'default_user')
            files = payload.get('files', [])  # S3 URLs to PDF/DOCX files
            custom_prompt = payload.get('prompt', '')  # Custom prompt for additional context

            if not company_name:
                return {'status': 'error', 'message': 'company_name is required'}

            # Default URL if not provided
            if not company_url:
                company_url = f"https://www.{company_name.lower().replace(' ', '')}.com"

            # Initialize status tracker
            status_tracker = StatusTracker(session_id)

            # Handle fetch action for polling
            if action == 'fetch':
                fetch_type = payload.get('fetch_type', 'status')
                if fetch_type == 'status':
                    # Return current processing status
                    current_status = status_tracker.get_current_status()
                    return {
                        'status': 'status_check',
                        'session_id': session_id,
                        'current_status': current_status,
                        'polling_recommended': True,
                        'next_poll_seconds': 5
                    }
                else:
                    # Handle other fetch types (use_cases, wafr_report, etc.)
                    return self._handle_fetch(
                        company_name,
                        company_url,
                        fetch_type,
                        selected_use_case_ids=selected_use_case_ids
                    )

            # Update initial status
            status_tracker.update_status(
                StatusCheckpoints.INITIATED,
                {
                    'company_name': company_name,
                    'company_url': company_url,
                    'action': action,
                    'session_id': session_id,
                    'project_id': project_id,
                    'user_id': user_id,
                    'files_provided': len(files),
                    'custom_prompt_provided': bool(custom_prompt and custom_prompt.strip()),
                    'web_scraping_enabled': WEB_SCRAPING_AVAILABLE
                }
            )

            # Process custom prompt if provided
            custom_context = None
            if custom_prompt and custom_prompt.strip():
                status_tracker.update_status(
                    StatusCheckpoints.CUSTOM_PROMPT_PROCESSING,
                    {'prompt_length': len(custom_prompt)},
                    current_agent='prompt_processor'
                )

                custom_context = CustomPromptProcessor.process_custom_prompt(
                    custom_prompt,
                    company_name,
                    f"Industry: {company_name} company analysis"
                )

                logger.info(
                    f"Custom prompt processed: {custom_context.get('context_type', 'unknown')} with {len(custom_context.get('focus_areas', []))} focus areas")

            # Generate session key for duplicate detection
            session_key = self.session_manager.generate_session_key(payload)

            # Check if this exact request is already being processed
            if self.session_manager.is_session_active(session_key):
                session_info = self.session_manager.get_session_info(session_key)
                return {
                    'status': 'in_progress',
                    'message': f'Request with identical payload is already being processed. Started at: {session_info.get("started_at")}',
                    'session_key': session_key,
                    'session_id': session_id,
                    'started_at': session_info.get('started_at'),
                    'estimated_completion': 'Please poll using fetch action with fetch_type: status',
                    'polling_info': {
                        'poll_action': 'fetch',
                        'poll_fetch_type': 'status',
                        'poll_interval_seconds': 5,
                        'session_id': session_id
                    }
                }

            # Start new session
            if not self.session_manager.start_session(session_key, payload):
                # Race condition - session was started between check and start
                return {
                    'status': 'in_progress',
                    'message': 'Request is already being processed by another instance',
                    'session_key': session_key,
                    'session_id': session_id,
                    'polling_info': {
                        'poll_action': 'fetch',
                        'poll_fetch_type': 'status',
                        'poll_interval_seconds': 5,
                        'session_id': session_id
                    }
                }

            try:
                # Process the request with status tracking
                if action == 'start':
                    result = self._handle_start(company_name, company_url, session_id, status_tracker, files,
                                                project_id, user_id, custom_context)
                elif action == 'select_use_cases':
                    result = self._handle_select_use_cases(company_name, company_url, session_id,
                                                           selected_use_case_ids, status_tracker)
                else:
                    result = {'status': 'error', 'message': f'Unknown action: {action}'}

                # Update final status
                if result.get('status') == 'completed':
                    status_tracker.update_status(StatusCheckpoints.COMPLETED)
                elif result.get('status') in ['use_cases_generated']:
                    status_tracker.update_status(StatusCheckpoints.USE_CASES_GENERATED)

                # Mark session as complete
                self.session_manager.complete_session(session_key, result)

                # Add session tracking info to result
                result['session_key'] = session_key
                result['session_id'] = session_id
                result['processing_completed_at'] = datetime.now().isoformat()
                result['project_id'] = project_id
                result['user_id'] = user_id
                result['status_tracking'] = {
                    'final_status': result.get('status'),
                    'session_id': session_id,
                    'checkpoint_completed': True
                }

                return result

            except Exception as e:
                # Mark session as complete even on error
                status_tracker.update_status(
                    StatusCheckpoints.ERROR,
                    {'error_type': type(e).__name__, 'error_message': str(e)}
                )
                error_result = {
                    'status': 'error',
                    'message': str(e),
                    'error_type': type(e).__name__,
                    'session_id': session_id
                }
                self.session_manager.complete_session(session_key, error_result)
                raise

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'message': str(e),
                'error_type': type(e).__name__,
                'session_id': payload.get('session_id', 'unknown')
            }

    def _handle_start(self, company_name: str, company_url: str, session_id: str, status_tracker: StatusTracker,
                      files: List[str], project_id: str, user_id: str, custom_context: Dict[str, str] = None) -> \
            Dict[str, Any]:
        """Handle start action with web scraping, custom prompt, file parsing, personalized use case generation, and comprehensive reporting."""
        logger.info(
            f"Starting transformation process for {company_name} with {len(files)} files, custom context: {bool(custom_context)}, and web scraping enabled: {WEB_SCRAPING_AVAILABLE}")

        # Parse uploaded files if provided
        parsed_files_content = None
        logger.info(f"✅ File: files: {files}")
        if files:
            parsed_files_content = self._parse_uploaded_files(files, status_tracker)

        logger.info(f"✅ File files parsed_files_content: {parsed_files_content}")
        # Conduct comprehensive business research with web scraping, custom context and file content integration
        research_data = self.research_swarm.conduct_comprehensive_research(
            company_name, company_url, status_tracker, parsed_files_content, custom_context
        )

        # Update status for agent analysis
        status_tracker.update_status(
            StatusCheckpoints.AGENT_ANALYZING,
            {
                'phase': 'company_profile_extraction',
                'enhanced_with_files': bool(parsed_files_content),
                'enhanced_with_custom_context': bool(custom_context),
                'enhanced_with_web_scraping': bool(research_data.get('web_research_data'))
            },
            current_agent='profile_extractor'
        )

        # Extract business-focused company profile
        company_profile = self._extract_company_profile(company_name, company_url, research_data,
                                                        parsed_files_content, custom_context)

        # Generate transformation use cases with web scraping, custom prompt and file content integration
        structured_use_cases = self.dynamic_use_case_generator.generate_dynamic_use_cases(
            company_profile, research_data, status_tracker, parsed_files_content, custom_context
        )

        # Generate consolidated comprehensive report with web scraping citations
        report_url = self.consolidated_report_generator.generate_consolidated_report(
            company_profile, structured_use_cases, research_data, session_id, status_tracker, parsed_files_content,
            custom_context
        )

        # Convert to legacy format
        legacy_use_cases = []
        available_use_case_ids = []

        for structured_uc in structured_use_cases:
            context_id = getattr(structured_uc, 'dynamic_id', f"transformation-{len(legacy_use_cases)}")
            available_use_case_ids.append(context_id)

            citations = ["Business Analysis", "Transformation Strategy"]
            if research_data.get('web_research_data'):
                citations.append("Web Intelligence")
            if parsed_files_content:
                citations.append("Document Analysis")
            if custom_context:
                citations.append("Custom Context Analysis")

            legacy_uc = UseCase(
                id=context_id,
                title=structured_uc.title,
                description=structured_uc.proposed_solution,
                business_value=structured_uc.business_value,
                technical_requirements=structured_uc.primary_aws_services,
                priority=structured_uc.priority,
                complexity=structured_uc.complexity,
                citations=citations,
                aws_services=structured_uc.primary_aws_services,
                implementation_approach="; ".join(structured_uc.implementation_phases),
                estimated_timeline=f"{structured_uc.timeline_months} months",
                cost_estimate=f"\${structured_uc.monthly_cost_usd}/month",
                current_implementation=structured_uc.current_state,
                proposed_solution=structured_uc.proposed_solution,
                url=report_url or ""  # Add report URL to each use case
            )
            legacy_use_cases.append(legacy_uc)

        # Store session data
        self.session_store[session_id] = {
            'company_name': company_name,
            'company_url': company_url,
            'company_profile': company_profile,
            'research_data': research_data,
            'structured_use_cases': structured_use_cases,
            'legacy_use_cases': legacy_use_cases,
            'dynamic_use_case_ids': available_use_case_ids,
            'report_url': report_url,
            'project_id': project_id,
            'user_id': user_id,
            'files_processed': len(files) if files else 0,
            'parsed_files_content': parsed_files_content,
            'custom_context': custom_context,
            'timestamp': datetime.now().isoformat()
        }

        enhancement_notes = []
        if research_data.get('web_research_data', {}).get('successful_scrapes', 0) > 0:
            enhancement_notes.append(
                f"web intelligence from {research_data['web_research_data']['successful_scrapes']} sources")
        if parsed_files_content:
            enhancement_notes.append(f"analysis of {len(files)} uploaded document(s)")
        if custom_context:
            enhancement_notes.append(
                f"custom context focusing on {', '.join(custom_context.get('focus_areas', []))}")

        enhancement_note = f" (Enhanced with {' and '.join(enhancement_notes)})" if enhancement_notes else ""

        return {
            "status": "use_cases_generated",
            "session_id": session_id,
            "project_id": project_id,
            "user_id": user_id,
            "company_profile": asdict(self._convert_profile_to_legacy(company_profile)),
            "structured_company_profile": asdict(company_profile),
            "research_metadata": {
                "method": research_data.get('research_method', 'web_scraping_with_beautiful_soup'),
                "timestamp": research_data.get('research_timestamp', ''),
                "company_url_analyzed": company_url,
                "urls_scraped": research_data.get('urls_scraped', []),
                "total_urls_processed": research_data.get('total_urls_processed', 1),
                "successful_web_scrapes": research_data.get('successful_web_scrapes', 0),
                "files_processed": len(files) if files else 0,
                "file_content_used": bool(parsed_files_content),
                "custom_context_used": bool(custom_context),
                "custom_context_type": custom_context.get('context_type') if custom_context else None,
                "custom_focus_areas": custom_context.get('focus_areas') if custom_context else [],
                "use_case_generation": "business_transformation_with_web_scraping_and_custom_context",
                "web_scraping_enabled": WEB_SCRAPING_AVAILABLE
            },
            "use_cases": [asdict(uc) for uc in legacy_use_cases],
            "structured_use_cases": [asdict(uc) for uc in structured_use_cases],
            "available_use_case_ids": available_use_case_ids,
            "total_use_cases": len(structured_use_cases),
            "report_url": report_url,
            "custom_context_summary": {
                "context_type": custom_context.get('context_type') if custom_context else None,
                "focus_areas": custom_context.get('focus_areas') if custom_context else [],
                "specific_requirements": custom_context.get('specific_requirements') if custom_context else "",
                "integration_notes": custom_context.get(
                    'integration_notes') if custom_context else "No custom context provided"
            },
            "web_scraping_summary": {
                "enabled": WEB_SCRAPING_AVAILABLE,
                "urls_scraped": len(research_data.get('urls_scraped', [])),
                "successful_scrapes": research_data.get('successful_web_scrapes', 0),
                "method": "google_search_with_beautiful_soup"
            },
            "message": f"Generated {len(structured_use_cases)} transformation use cases for {company_name}{enhancement_note}. Report provides comprehensive analysis of ALL use cases with enhanced formatting and strategic recommendations.",
            "next_action": "select_use_cases",
            "instructions": f"Select use case IDs from 'available_use_case_ids' for WAFR assessment",
            "status_tracking": {
                "checkpoints_completed": [
                    StatusCheckpoints.INITIATED,
                    StatusCheckpoints.CUSTOM_PROMPT_PROCESSING if custom_context else "skipped",
                    StatusCheckpoints.FILE_PARSING_STARTED if files else "skipped",
                    StatusCheckpoints.FILE_PARSING_COMPLETED if files else "skipped",
                    StatusCheckpoints.WEB_SCRAPING_STARTED if WEB_SCRAPING_AVAILABLE else "skipped",
                    StatusCheckpoints.WEB_SCRAPING_COMPLETED if WEB_SCRAPING_AVAILABLE else "skipped",
                    StatusCheckpoints.RESEARCH_STARTED,
                    StatusCheckpoints.RESEARCH_IN_PROGRESS,
                    StatusCheckpoints.RESEARCH_COMPLETED,
                    StatusCheckpoints.AGENT_ANALYZING,
                    StatusCheckpoints.USE_CASES_GENERATING,
                    StatusCheckpoints.USE_CASES_GENERATED,
                    StatusCheckpoints.REPORT_GENERATION_STARTED,
                    StatusCheckpoints.REPORT_GENERATION_COMPLETED
                ],
                "processing_method": "web_scraping_with_custom_context_and_file_integration_enhanced_formatting"
            }
        }

    def _handle_select_use_cases(self, company_name: str, company_url: str, session_id: str,
                                 selected_use_case_ids: List[str], status_tracker: StatusTracker) -> Dict[str, Any]:
        """Handle use case selection with personalized context."""

        if not selected_use_case_ids:
            return {'status': 'error', 'message': 'No transformation use cases selected'}

        # Update status for WAFR assessment start
        status_tracker.update_status(
            StatusCheckpoints.WAFR_ASSESSMENT_STARTED,
            {
                'selected_use_cases': len(selected_use_case_ids),
                'use_case_ids': selected_use_case_ids
            }
        )

        # For this integrated version, we'll return a success with the report URL
        session_data = self.session_store.get(session_id)
        if not session_data:
            return {'status': 'error', 'message': 'Session not found. Please start with action: "start"'}

        company_profile = session_data['company_profile']
        legacy_use_cases = session_data['legacy_use_cases']
        context_aligned_ids = session_data.get('dynamic_use_case_ids', [])
        report_url = session_data.get('report_url', '')
        project_id = session_data.get('project_id')
        user_id = session_data.get('user_id')
        files_processed = session_data.get('files_processed', 0)
        custom_context = session_data.get('custom_context')
        research_data = session_data.get('research_data', {})

        # Validate selected IDs
        valid_selected_ids = [id for id in selected_use_case_ids if id in context_aligned_ids]

        if not valid_selected_ids:
            return {
                'status': 'error',
                'message': f'No valid transformation use case IDs. Available IDs: {context_aligned_ids}',
                'provided_ids': selected_use_case_ids
            }

        # Filter selected use cases
        selected_use_cases = [uc for uc in legacy_use_cases if uc.id in valid_selected_ids]

        logger.info(f"Processing {len(selected_use_cases)} selected use cases for {company_name}")

        # Update completion status
        status_tracker.update_status(
            StatusCheckpoints.COMPLETED,
            {
                'selected_use_cases_processed': True,
                'report_available': bool(report_url),
                'custom_context_used': bool(custom_context),
                'web_enhanced': bool(research_data.get('web_research_data'))
            }
        )

        # Update session with selected use cases
        self.session_store[session_id]['selected_use_case_ids'] = valid_selected_ids

        return {
            'status': 'completed',
            'session_id': session_id,
            'project_id': project_id,
            'user_id': user_id,
            'company_profile': asdict(self._convert_profile_to_legacy(company_profile)),
            'selected_use_case_ids': valid_selected_ids,
            'selected_use_cases': [asdict(uc) for uc in selected_use_cases],
            'report_url': report_url,
            'business_transformation_summary': {
                'method': 'transformation_assessment_with_consolidated_report_and_web_scraping',
                'company_aligned_use_cases': True,
                'web_enhanced_analysis': bool(research_data.get('web_research_data')),
                'file_enhanced_analysis': files_processed > 0,
                'custom_context_alignment': bool(custom_context),
                'consolidated_report_generated': bool(report_url),
                'comprehensive_use_case_analysis': True,
                'enhanced_formatting': True
            },
            'web_scraping_summary': {
                'enabled': WEB_SCRAPING_AVAILABLE,
                'urls_scraped': len(research_data.get('urls_scraped', [])),
                'successful_scrapes': research_data.get('successful_web_scrapes', 0),
                'citations_in_report': True
            },
            'custom_context_summary': {
                'context_type': custom_context.get('context_type') if custom_context else None,
                'focus_areas': custom_context.get('focus_areas') if custom_context else [],
                'alignment_achieved': True
            },
            'status_tracking': {
                'checkpoints_completed': [
                    StatusCheckpoints.USE_CASES_GENERATED,
                    StatusCheckpoints.REPORT_GENERATION_COMPLETED,
                    StatusCheckpoints.COMPLETED
                ],
                'final_status': StatusCheckpoints.COMPLETED,
                'processing_method': 'web_scraping_with_custom_context_and_file_integration_enhanced_formatting'
            }
        }

    def _handle_fetch(self, company_name: str, company_url: str, fetch_type: str, **kwargs) -> Dict[str, Any]:
        """Enhanced fetch action with better error handling."""
        try:
            logger.info(f"Fetching {fetch_type} for {company_name} at {company_url}")

            if fetch_type == 'status':
                session_id = kwargs.get('session_id')
                if not session_id:
                    return {
                        'status': 'error',
                        'message': 'session_id is required for status fetch',
                        'timestamp': datetime.now().isoformat()
                    }

                status_tracker = StatusTracker(session_id)
                current_status = status_tracker.get_current_status()

                return {
                    'status': 'status_check',
                    'session_id': session_id,
                    'current_status': current_status,
                    'polling_recommended': current_status.get('current_status') not in [
                        StatusCheckpoints.COMPLETED,
                        StatusCheckpoints.ERROR,
                        StatusCheckpoints.USE_CASES_GENERATED,
                        StatusCheckpoints.REPORT_GENERATION_COMPLETED
                    ],
                    'next_poll_seconds': 5,
                    'timestamp': datetime.now().isoformat()
                }

            elif fetch_type == 'use_cases':
                return self._fetch_use_cases_enhanced(company_name, company_url)
            elif fetch_type == 'wafr_report':
                selected_use_case_ids = kwargs.get('selected_use_case_ids')
                return self._fetch_wafr_report_enhanced(company_name, company_url, selected_use_case_ids)
            elif fetch_type == 'all':
                return self._fetch_all_data_enhanced(company_name, company_url)
            else:
                return {
                    'status': 'error',
                    'message': f'Invalid fetch_type: {fetch_type}. Valid types: status, use_cases, wafr_report, all',
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error in fetch handler: {e}")
            return {
                'status': 'error',
                'message': f'Failed to fetch {fetch_type}: {str(e)}',
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            }

    def _fetch_use_cases_enhanced(self, company_name: str, company_url: str) -> Dict[str, Any]:
        """Enhanced use cases fetch with web scraping and custom context integration."""

        # Strategy 1: Check session store
        matching_sessions = []
        for session_id, session_data in self.session_store.items():
            try:
                if (session_data.get('company_name', '').lower() == company_name.lower() and
                        'structured_use_cases' in session_data):
                    matching_sessions.append((session_id, session_data))
            except Exception as e:
                logger.warning(f"Error checking session {session_id}: {e}")
                continue

        if matching_sessions:
            # Return the most recent session
            try:
                latest_session = max(matching_sessions, key=lambda x: x[1].get('timestamp', '1970-01-01'))
                session_id, session_data = latest_session

                custom_context = session_data.get('custom_context')
                research_data = session_data.get('research_data', {})

                return {
                    'status': 'found_cached_use_cases',
                    'session_id': session_id,
                    'company_name': company_name,
                    'company_url': company_url,
                    'company_profile': asdict(
                        self._convert_profile_to_legacy(session_data['company_profile'])) if session_data.get(
                        'company_profile') else {},
                    'use_cases': [asdict(uc) for uc in session_data.get('legacy_use_cases', [])],
                    'available_use_case_ids': session_data.get('dynamic_use_case_ids', []),
                    'total_use_cases': len(session_data.get('structured_use_cases', [])),
                    'report_url': session_data.get('report_url', ''),
                    'files_processed': session_data.get('files_processed', 0),
                    'custom_context_used': bool(custom_context),
                    'custom_context_type': custom_context.get('context_type') if custom_context else None,
                    'custom_focus_areas': custom_context.get('focus_areas') if custom_context else [],
                    'web_scraping_summary': {
                        'enabled': WEB_SCRAPING_AVAILABLE,
                        'urls_scraped': len(research_data.get('urls_scraped', [])),
                        'successful_scrapes': research_data.get('successful_web_scrapes', 0)
                    },
                    'cached_timestamp': session_data.get('timestamp'),
                    'message': f"Retrieved cached transformation use cases for {company_name}" +
                               (
                                   f" (enhanced with {session_data.get('files_processed', 0)} files)" if session_data.get(
                                       'files_processed', 0) > 0 else "") +
                               (
                                   f" (custom context: {custom_context.get('context_type', 'general')})" if custom_context else "") +
                               (
                                   f" (web scraping: {research_data.get('successful_web_scrapes', 0)} sources)" if research_data.get(
                                       'successful_web_scrapes', 0) > 0 else "") +
                               " - Report includes comprehensive analysis of ALL use cases with enhanced formatting",
                    'next_action': "select_use_cases",
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error processing cached session: {e}")

        # Strategy 2: Check cache table directly
        try:
            cache_key = self._generate_cache_key_for_company(company_name, company_url)
            cached_result = CacheManager.get_from_cache(cache_key)
            if cached_result and cached_result.get('status') == 'use_cases_generated':
                return {
                    'status': 'found_cached_use_cases_from_cache',
                    'cache_key': cache_key,
                    'company_name': company_name,
                    'company_url': company_url,
                    'cached_data': cached_result,
                    'message': f"Retrieved cached data from cache table for {company_name}",
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.warning(f"Error checking cache table: {e}")

        # No data found
        return {
            'status': 'no_cached_data',
            'company_name': company_name,
            'company_url': company_url,
            'message': f'No cached transformation use cases found for {company_name}',
            'suggestion': 'Use action: "start" to generate new use cases with optional custom prompt, file upload, and web scraping',
            'available_actions': ['start'],
            'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }

    def _fetch_wafr_report_enhanced(self, company_name: str, company_url: str,
                                    selected_use_case_ids: List[str] = None) -> Dict[str, Any]:
        """Enhanced consolidated report fetch with web scraping and custom context integration."""

        # Check session store for reports
        matching_report_sessions = []
        for session_id, session_data in self.session_store.items():
            try:
                if (session_data.get('company_name', '').lower() == company_name.lower() and
                        session_data.get('company_url', '') == company_url and
                        'report_url' in session_data):
                    matching_report_sessions.append((session_id, session_data))
            except Exception as e:
                logger.warning(f"Error checking report session {session_id}: {e}")
                continue

        if matching_report_sessions:
            # Return matching reports
            reports = []
            for session_id, session_data in matching_report_sessions:
                try:
                    files_processed = session_data.get('files_processed', 0)
                    custom_context = session_data.get('custom_context')
                    research_data = session_data.get('research_data', {})

                    report_info = {
                        'session_id': session_id,
                        'report_url': session_data.get('report_url', ''),
                        'company_name': company_name,
                        'company_url': company_url,
                        'use_case_count': len(session_data.get('structured_use_cases', [])),
                        'available_use_case_ids': session_data.get('dynamic_use_case_ids', []),
                        'created_at': session_data.get('timestamp'),
                        'report_type': 'comprehensive_analysis_with_enhanced_formatting_and_web_citations',
                        'files_processed': files_processed,
                        'file_enhanced': files_processed > 0,
                        'custom_context_used': bool(custom_context),
                        'custom_context_type': custom_context.get('context_type') if custom_context else None,
                        'custom_focus_areas': custom_context.get('focus_areas') if custom_context else [],
                        'web_scraping_summary': {
                            'enabled': WEB_SCRAPING_AVAILABLE,
                            'urls_scraped': len(research_data.get('urls_scraped', [])),
                            'successful_scrapes': research_data.get('successful_web_scrapes', 0),
                            'citations_included': True
                        },
                        'comprehensive_use_case_analysis': True,
                        'enhanced_formatting': True
                    }
                    reports.append(report_info)
                except Exception as e:
                    logger.warning(f"Error processing report for session {session_id}: {e}")
                    continue

            # Sort by creation date (most recent first)
            reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)

            return {
                'status': 'found_cached_reports',
                'company_name': company_name,
                'company_url': company_url,
                'total_reports': len(reports),
                'reports': reports,
                'latest_report': reports[0] if reports else None,
                'message': f"Retrieved {len(reports)} consolidated report(s) with enhanced formatting, comprehensive use case analysis and web citations for {company_name}",
                'available_actions': ['start', 'select_use_cases'],
                'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
                'timestamp': datetime.now().isoformat()
            }

        return {
            'status': 'no_cached_reports',
            'company_name': company_name,
            'company_url': company_url,
            'message': f'No consolidated reports found for {company_name}',
            'suggestion': 'Use action: "start" to begin the transformation process with optional custom prompt, file upload, and web scraping',
            'available_actions': ['start'],
            'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }

    def _fetch_all_data_enhanced(self, company_name: str, company_url: str) -> Dict[str, Any]:
        """Enhanced fetch all data with web scraping and custom context integration."""

        # Get use cases
        use_cases_result = self._fetch_use_cases_enhanced(company_name, company_url)

        # Get reports
        reports_result = self._fetch_wafr_report_enhanced(company_name, company_url)

        # Compile comprehensive response
        all_sessions = []
        for session_id, session_data in self.session_store.items():
            try:
                if (session_data.get('company_name', '').lower() == company_name.lower()):
                    files_processed = session_data.get('files_processed', 0)
                    custom_context = session_data.get('custom_context')
                    research_data = session_data.get('research_data', {})

                    session_summary = {
                        'session_id': session_id,
                        'timestamp': session_data.get('timestamp'),
                        'has_use_cases': 'structured_use_cases' in session_data,
                        'has_report': 'report_url' in session_data,
                        'use_case_count': len(session_data.get('structured_use_cases', [])),
                        'selected_use_cases': session_data.get('selected_use_case_ids', []),
                        'report_url': session_data.get('report_url', ''),
                        'files_processed': files_processed,
                        'file_enhanced': files_processed > 0,
                        'custom_context_used': bool(custom_context),
                        'custom_context_type': custom_context.get('context_type') if custom_context else None,
                        'custom_focus_areas': custom_context.get('focus_areas') if custom_context else [],
                        'web_scraping_summary': {
                            'enabled': WEB_SCRAPING_AVAILABLE,
                            'urls_scraped': len(research_data.get('urls_scraped', [])),
                            'successful_scrapes': research_data.get('successful_web_scrapes', 0)
                        },
                        'company_profile': asdict(
                            session_data.get('company_profile')) if session_data.get('company_profile') else None,
                        'comprehensive_use_case_analysis': True,
                        'enhanced_formatting': True
                    }
                    all_sessions.append(session_summary)
            except Exception as e:
                logger.warning(f"Error processing session {session_id}: {e}")
                continue

        # Sort sessions by timestamp (most recent first)
        all_sessions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        if all_sessions:
            return {
                'status': 'found_cached_data',
                'company_name': company_name,
                'company_url': company_url,
                'total_sessions': len(all_sessions),
                'sessions_summary': all_sessions,
                'use_cases_status': use_cases_result.get('status'),
                'reports_status': reports_result.get('status'),
                'detailed_use_cases': use_cases_result if use_cases_result.get(
                    'status') == 'found_cached_use_cases' else None,
                'detailed_reports': reports_result if reports_result.get(
                    'status') == 'found_cached_reports' else None,
                'latest_session': all_sessions[0] if all_sessions else None,
                'message': f"Retrieved all cached transformation data for {company_name} ({len(all_sessions)} sessions) with enhanced formatting and comprehensive use case analysis",
                'available_actions': ['start', 'select_use_cases'],
                'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
                'timestamp': datetime.now().isoformat()
            }

        return {
            'status': 'no_cached_data',
            'company_name': company_name,
            'company_url': company_url,
            'message': f'No cached transformation data found for {company_name}',
            'suggestion': 'Use action: "start" to begin the transformation process with optional custom prompt, file upload, and web scraping',
            'available_actions': ['start'],
            'web_scraping_enabled': WEB_SCRAPING_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }

    def _generate_cache_key_for_company(self, company_name: str, company_url: str) -> str:
        """Generate cache key for company lookup."""
        return CacheManager.generate_cache_key({
            'company_name': company_name,
            'company_url': company_url,
            'action': 'start'
        })

    def _parse_uploaded_files(self, files: List[str], status_tracker: StatusTracker) -> Optional[str]:
        """Parse uploaded S3 files and return combined content."""
        logger.warning(f"✅ File: files _parse_uploaded_files : {files}")

        if not files:
            return None

        status_tracker.update_status(
            StatusCheckpoints.FILE_PARSING_STARTED,
            {'files_to_parse': len(files)},
            current_agent='file_parser'
        )

        combined_content = []
        successful_parses = 0

        for i, file_url in enumerate(files):
            try:
                logger.info(f"Parsing file {i + 1}/{len(files)}: {file_url}")

                content = FileParser.parse_s3_file(file_url)
                if content:
                    combined_content.append(f"=== Document {i + 1} ===\n{content}\n")
                    successful_parses += 1
                    logger.info(f"Successfully parsed file {i + 1}: {len(content)} characters")
                else:
                    logger.warning(f"Failed to parse file {i + 1}: {file_url}")

            except Exception as e:
                logger.error(f"Error parsing file {i + 1}: {e}")
                continue

        status_tracker.update_status(
            StatusCheckpoints.FILE_PARSING_COMPLETED,
            {
                'total_files': len(files),
                'successful_parses': successful_parses,
                'failed_parses': len(files) - successful_parses
            }
        )

        if combined_content:
            result = "\n".join(combined_content)
            logger.info(f"Combined file content: {len(result)} total characters from {successful_parses} files")
            return result

        logger.warning("No content could be extracted from any files")
        return None

    def _extract_company_profile(self, company_name: str, company_url: str, research_data: Dict[str, Any],
                                 parsed_files_content: str = None,
                                 custom_context: Dict[str, str] = None) -> CompanyProfile:
        """Extract structured company profile from business research with web scraping, custom context and file content integration."""

        web_context = ""
        if research_data.get('web_research_data', {}).get('research_content'):
            web_context = f"""
            
WEB INTELLIGENCE ANALYSIS:
Based on web scraping of {research_data['web_research_data'].get('successful_scrapes', 0)} sources:

{research_data['web_research_data']['research_content'][:2000]}

Use this market intelligence to understand their competitive position and industry context.
            """

        file_context = ""
        if parsed_files_content:
            file_context = f"""
            
COMPANY DOCUMENT ANALYSIS:
The following content was extracted from company documents:

{parsed_files_content[:2000]}

Use this as primary intelligence to understand their actual operations, departments, processes, products, and strategic context.
            """

        custom_context_section = ""
        if custom_context and custom_context.get('processed_prompt'):
            custom_context_section = f"""
            
CUSTOM CONTEXT REQUIREMENTS:
{custom_context['processed_prompt'][:1000]}

Focus Areas: {', '.join(custom_context.get('focus_areas', []))}
Context Type: {custom_context.get('context_type', 'general')}

Ensure profile extraction aligns with these custom requirements and focus areas.
            """

        extraction_prompt = f"""
        Extract strategic business profile from comprehensive research data:
        
        COMPANY: {company_name}
        URL: {company_url}
        
        BUSINESS RESEARCH DATA:
        {research_data.get('research_findings', '')[:2000]}
        {web_context}
        {file_context}
        {custom_context_section}
        
        Analyze and extract key business intelligence naturally based on the provided context and research data.
        Focus on understanding their actual business operations, strategic challenges, and transformation opportunities.
        """

        try:
            response = self.profile_extractor(extraction_prompt)
            response_text = str(response)

            return OutputParser.parse_company_profile(response_text, company_name)

        except Exception as e:
            logger.error(f"Error extracting business profile: {e}")
            return OutputParser.parse_company_profile("", company_name)

    def _convert_profile_to_legacy(self, profile: CompanyProfile) -> CompanyInfo:
        """Convert structured profile to legacy format with business context."""
        return CompanyInfo(
            name=profile.name,
            url="",
            industry=profile.industry,
            description=f"{profile.business_model} operating in {profile.industry}",
            size=profile.company_size,
            technologies=profile.technology_stack,
            business_model=profile.business_model,
            additional_context=f"Transformation readiness: {profile.cloud_maturity}, Business stage: {profile.growth_stage}"
        )
        
        

