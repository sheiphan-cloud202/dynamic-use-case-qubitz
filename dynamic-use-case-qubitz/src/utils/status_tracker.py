"""
Enhanced status tracking with PowerPoint presentation support.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from src.services.aws_clients import status_table

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StatusCheckpoints:
    """Enhanced status checkpoints including PowerPoint generation phases."""
    
    # Initialization and setup
    INITIATED = "initiated"
    CUSTOM_PROMPT_PROCESSING = "custom_prompt_processing"
    FILE_PARSING_STARTED = "file_parsing_started"
    FILE_PARSING_COMPLETED = "file_parsing_completed"
    
    # Research and analysis phases
    RESEARCH_STARTED = "research_started"
    WEB_SCRAPING_STARTED = "web_scraping_started"
    WEB_SCRAPING_COMPLETED = "web_scraping_completed"
    RESEARCH_IN_PROGRESS = "research_in_progress"
    RESEARCH_COMPLETED = "research_completed"
    
    # Agent processing phases
    AGENT_ANALYZING = "agent_analyzing"
    USE_CASE_GENERATION_STARTED = "use_case_generation_started"
    USE_CASE_GENERATION_IN_PROGRESS = "use_case_generation_in_progress"
    USE_CASES_GENERATED = "use_cases_generated"
    
    # Output generation phases - PDF
    REPORT_GENERATION_STARTED = "report_generation_started"
    REPORT_GENERATION_IN_PROGRESS = "report_generation_in_progress"
    REPORT_GENERATION_COMPLETED = "report_generation_completed"
    
    # Output generation phases - PowerPoint (NEW)
    TEMPLATE_SELECTED = "template_selected"
    PRESENTATION_GENERATING = "presentation_generating"
    PRESENTATION_ANALYZING = "presentation_analyzing"
    PRESENTATION_STRUCTURING = "presentation_structuring"
    PRESENTATION_CREATING = "presentation_creating"
    PRESENTATION_STYLING = "presentation_styling"
    PRESENTATION_SAVING = "presentation_saving"
    PRESENTATION_UPLOADING = "presentation_uploading"
    PRESENTATION_COMPLETED = "presentation_completed"
    
    # Final states
    COMPLETED = "completed"
    ERROR = "error"
    
    # Status categories for better organization
    INITIALIZATION_PHASES = [
        INITIATED, CUSTOM_PROMPT_PROCESSING, FILE_PARSING_STARTED, FILE_PARSING_COMPLETED
    ]
    
    RESEARCH_PHASES = [
        RESEARCH_STARTED, WEB_SCRAPING_STARTED, WEB_SCRAPING_COMPLETED, 
        RESEARCH_IN_PROGRESS, RESEARCH_COMPLETED
    ]
    
    ANALYSIS_PHASES = [
        AGENT_ANALYZING, USE_CASE_GENERATION_STARTED, 
        USE_CASE_GENERATION_IN_PROGRESS, USE_CASES_GENERATED
    ]
    
    PDF_GENERATION_PHASES = [
        REPORT_GENERATION_STARTED, REPORT_GENERATION_IN_PROGRESS, REPORT_GENERATION_COMPLETED
    ]
    
    PPT_GENERATION_PHASES = [
        TEMPLATE_SELECTED, PRESENTATION_GENERATING, PRESENTATION_ANALYZING,
        PRESENTATION_STRUCTURING, PRESENTATION_CREATING, PRESENTATION_STYLING,
        PRESENTATION_SAVING, PRESENTATION_UPLOADING, PRESENTATION_COMPLETED
    ]
    
    FINAL_PHASES = [COMPLETED, ERROR]
    
    @classmethod
    def get_phase_category(cls, status: str) -> str:
        """Get the category of a status phase."""
        if status in cls.INITIALIZATION_PHASES:
            return "initialization"
        elif status in cls.RESEARCH_PHASES:
            return "research"
        elif status in cls.ANALYSIS_PHASES:
            return "analysis"
        elif status in cls.PDF_GENERATION_PHASES:
            return "pdf_generation"
        elif status in cls.PPT_GENERATION_PHASES:
            return "ppt_generation"
        elif status in cls.FINAL_PHASES:
            return "final"
        else:
            return "unknown"
    
    @classmethod
    def get_progress_percentage(cls, status: str) -> int:
        """Get approximate progress percentage for a given status."""
        progress_map = {
            # Initialization (0-15%)
            cls.INITIATED: 5,
            cls.CUSTOM_PROMPT_PROCESSING: 10,
            cls.FILE_PARSING_STARTED: 12,
            cls.FILE_PARSING_COMPLETED: 15,
            
            # Research (15-40%)
            cls.RESEARCH_STARTED: 20,
            cls.WEB_SCRAPING_STARTED: 25,
            cls.WEB_SCRAPING_COMPLETED: 30,
            cls.RESEARCH_IN_PROGRESS: 35,
            cls.RESEARCH_COMPLETED: 40,
            
            # Analysis (40-60%)
            cls.AGENT_ANALYZING: 45,
            cls.USE_CASE_GENERATION_STARTED: 50,
            cls.USE_CASE_GENERATION_IN_PROGRESS: 55,
            cls.USE_CASES_GENERATED: 60,
            
            # PDF Generation (60-80%)
            cls.REPORT_GENERATION_STARTED: 65,
            cls.REPORT_GENERATION_IN_PROGRESS: 70,
            cls.REPORT_GENERATION_COMPLETED: 80,
            
            # PowerPoint Generation (60-95%)
            cls.TEMPLATE_SELECTED: 62,
            cls.PRESENTATION_GENERATING: 65,
            cls.PRESENTATION_ANALYZING: 70,
            cls.PRESENTATION_STRUCTURING: 75,
            cls.PRESENTATION_CREATING: 80,
            cls.PRESENTATION_STYLING: 85,
            cls.PRESENTATION_SAVING: 90,
            cls.PRESENTATION_UPLOADING: 92,
            cls.PRESENTATION_COMPLETED: 95,
            
            # Final (95-100%)
            cls.COMPLETED: 100,
            cls.ERROR: 0
        }
        
        return progress_map.get(status, 50)
    
    @classmethod
    def get_user_friendly_message(cls, status: str, metadata: Dict[str, Any] = None) -> str:
        """Get user-friendly status message."""
        metadata = metadata or {}
        
        messages = {
            cls.INITIATED: "Starting transformation process...",
            cls.CUSTOM_PROMPT_PROCESSING: "Processing custom requirements...",
            cls.FILE_PARSING_STARTED: "Reading uploaded documents...",
            cls.FILE_PARSING_COMPLETED: "Document analysis complete",
            
            cls.RESEARCH_STARTED: "Beginning business research...",
            cls.WEB_SCRAPING_STARTED: "Gathering market intelligence...",
            cls.WEB_SCRAPING_COMPLETED: "Market research complete",
            cls.RESEARCH_IN_PROGRESS: "Conducting deep business analysis...",
            cls.RESEARCH_COMPLETED: "Business research complete",
            
            cls.AGENT_ANALYZING: "AI agents analyzing business data...",
            cls.USE_CASE_GENERATION_STARTED: "Generating transformation scenarios...",
            cls.USE_CASE_GENERATION_IN_PROGRESS: "Creating strategic use cases...",
            cls.USE_CASES_GENERATED: "Use cases generated successfully",
            
            cls.REPORT_GENERATION_STARTED: "Creating comprehensive PDF report...",
            cls.REPORT_GENERATION_IN_PROGRESS: "Formatting PDF document...",
            cls.REPORT_GENERATION_COMPLETED: "PDF report ready for download",
            
            cls.TEMPLATE_SELECTED: f"Selected {metadata.get('template', 'presentation')} template",
            cls.PRESENTATION_GENERATING: "Generating PowerPoint presentation...",
            cls.PRESENTATION_ANALYZING: "AI analyzing content for slides...",
            cls.PRESENTATION_STRUCTURING: "Structuring presentation flow...",
            cls.PRESENTATION_CREATING: "Creating professional slides...",
            cls.PRESENTATION_STYLING: "Applying template styling...",
            cls.PRESENTATION_SAVING: "Saving PowerPoint file...",
            cls.PRESENTATION_UPLOADING: "Uploading presentation to cloud...",
            cls.PRESENTATION_COMPLETED: "PowerPoint presentation ready",
            
            cls.COMPLETED: "All outputs generated successfully!",
            cls.ERROR: f"Error occurred: {metadata.get('error', 'Unknown error')}"
        }
        
        base_message = messages.get(status, f"Processing: {status}")
        
        # Add context-specific information
        if status == cls.PRESENTATION_GENERATING and metadata.get('template'):
            base_message = f"Creating {metadata['template']} presentation..."
        elif status == cls.RESEARCH_IN_PROGRESS and metadata.get('company'):
            base_message = f"Analyzing {metadata['company']} business operations..."
        elif status == cls.USE_CASE_GENERATION_IN_PROGRESS and metadata.get('use_case_count'):
            base_message = f"Generated {metadata['use_case_count']} transformation scenarios..."
        
        return base_message

class StatusTracker:
    """Enhanced status tracker with PowerPoint presentation tracking capabilities."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.table = status_table
    
    def update_status(self, checkpoint: str, metadata: Dict[str, Any] = None, current_agent: str = None) -> None:
        """Update session status with enhanced PowerPoint tracking."""
        
        if metadata is None:
            metadata = {}
        
        # Add PowerPoint-specific metadata
        enhanced_metadata = {
            **metadata,
            'phase_category': StatusCheckpoints.get_phase_category(checkpoint),
            'progress_percentage': StatusCheckpoints.get_progress_percentage(checkpoint),
            'user_message': StatusCheckpoints.get_user_friendly_message(checkpoint, metadata),
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        
        if current_agent:
            enhanced_metadata['current_agent'] = current_agent
        
        # Add PowerPoint-specific tracking
        if checkpoint in StatusCheckpoints.PPT_GENERATION_PHASES:
            enhanced_metadata.update({
                'output_type': 'powerpoint',
                'generation_phase': 'presentation'
            })
        elif checkpoint in StatusCheckpoints.PDF_GENERATION_PHASES:
            enhanced_metadata.update({
                'output_type': 'pdf',
                'generation_phase': 'report'
            })
        
        # Log with enhanced context
        template_info = f" ({metadata.get('template')} template)" if metadata.get('template') else ""
        company_info = f" for {metadata.get('company')}" if metadata.get('company') else ""
        
        logger.info(f"Status updated to {checkpoint}{template_info}{company_info} for session {self.session_id}")
        
        try:
            # Store in DynamoDB
            item = {
                'session_id': self.session_id,
                'current_status': checkpoint,
                'metadata': enhanced_metadata,
                'updated_at': datetime.now().isoformat(),
                'ttl': int(datetime.now().timestamp()) + (7 * 24 * 3600)  # 7 days TTL
            }
            
            self.table.put_item(Item=item)
            
        except Exception as e:
            logger.error(f"Failed to update status for session {self.session_id}: {e}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current status with PowerPoint context."""
        
        try:
            response = self.table.get_item(Key={'session_id': self.session_id})
            
            if 'Item' in response:
                item = response['Item']
                status_data = {
                    'session_id': self.session_id,
                    'current_status': item.get('current_status'),
                    'metadata': item.get('metadata', {}),
                    'updated_at': item.get('updated_at'),
                    'progress_percentage': item.get('metadata', {}).get('progress_percentage', 0),
                    'user_message': item.get('metadata', {}).get('user_message', 'Processing...'),
                    'phase_category': item.get('metadata', {}).get('phase_category', 'unknown')
                }
                
                # Add PowerPoint-specific status information
                metadata = item.get('metadata', {})
                if metadata.get('output_type') == 'powerpoint':
                    status_data.update({
                        'presentation_template': metadata.get('template'),
                        'presentation_progress': metadata.get('generation_phase'),
                        'slides_count': metadata.get('slides_count'),
                        's3_url': metadata.get('s3_url')
                    })
                
                return status_data
            else:
                return {
                    'session_id': self.session_id,
                    'current_status': 'not_found',
                    'message': 'Session not found',
                    'progress_percentage': 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get status for session {self.session_id}: {e}")
            return {
                'session_id': self.session_id,
                'current_status': 'error',
                'error': str(e),
                'progress_percentage': 0
            }
    
    def mark_presentation_template_selected(self, template: str, company_name: str) -> None:
        """Mark that presentation template has been selected."""
        self.update_status(
            StatusCheckpoints.TEMPLATE_SELECTED,
            {
                'template': template,
                'company': company_name,
                'template_description': self._get_template_description(template)
            }
        )
    
    def mark_presentation_phase(self, phase: str, template: str, additional_metadata: Dict[str, Any] = None) -> None:
        """Mark specific presentation generation phase."""
        metadata = {
            'template': template,
            **(additional_metadata or {})
        }
        self.update_status(phase, metadata)
    
    def _get_template_description(self, template: str) -> str:
        """Get description for presentation template."""
        descriptions = {
            'first_deck': 'Executive overview for strategic partnership calls',
            'marketing': 'Persuasive presentation focused on benefits and transformation',
            'use_case': 'Detailed implementation scenarios with problem-solution-benefit structure',
            'technical': 'Architecture and technical specifications presentation',
            'strategy': 'Strategic planning and roadmap presentation'
        }
        return descriptions.get(template, f'{template} presentation')
    
    def is_completed(self) -> bool:
        """Check if process is completed."""
        current = self.get_current_status()
        return current.get('current_status') in [StatusCheckpoints.COMPLETED, StatusCheckpoints.ERROR]
    
    def is_presentation_ready(self) -> bool:
        """Check if PowerPoint presentation is ready."""
        current = self.get_current_status()
        return current.get('current_status') == StatusCheckpoints.PRESENTATION_COMPLETED
    
    def get_output_urls(self) -> Dict[str, Optional[str]]:
        """Get URLs for generated outputs."""
        current = self.get_current_status()
        metadata = current.get('metadata', {})
        
        return {
            'report_url': metadata.get('report_url'),
            'presentation_url': metadata.get('s3_url'),
            'output_format': metadata.get('output_format'),
            'presentation_template': metadata.get('template')
        }

# Export for use in other modules
__all__ = ['StatusTracker', 'StatusCheckpoints']