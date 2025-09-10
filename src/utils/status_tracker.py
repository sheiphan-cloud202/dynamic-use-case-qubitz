"""
Status tracking for the Business Transformation Agent.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from src.services.aws_clients import status_table

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StatusCheckpoints:
    INITIATED = "initiated"
    CUSTOM_PROMPT_PROCESSING = "custom_prompt_processing"
    FILE_PARSING_STARTED = "file_parsing_started"
    FILE_PARSING_COMPLETED = "file_parsing_completed"
    WEB_SCRAPING_STARTED = "web_scraping_started"
    WEB_SCRAPING_IN_PROGRESS = "web_scraping_in_progress"
    WEB_SCRAPING_COMPLETED = "web_scraping_completed"
    RESEARCH_STARTED = "research_started"
    RESEARCH_IN_PROGRESS = "research_in_progress"
    RESEARCH_COMPLETED = "research_completed"
    AGENT_ANALYZING = "agent_analyzing"
    USE_CASES_GENERATING = "use_cases_generating"
    USE_CASES_GENERATED = "use_cases_generated"
    WAFR_ASSESSMENT_STARTED = "wafr_assessment_started"
    WAFR_PROCESSING = "wafr_processing"
    WAFR_COMPLETED = "wafr_completed"
    REPORT_GENERATION_STARTED = "report_generation_started"
    REPORT_GENERATION_COMPLETED = "report_generation_completed"
    COMPLETED = "completed"
    ERROR = "error"


class StatusTracker:
    """Comprehensive status tracking for all processing stages with DynamoDB Decimal support."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status_table = status_table
        self.start_time = datetime.now()

    def _convert_floats_to_decimal(self, obj):
        """Convert float values to Decimal for DynamoDB compatibility."""
        if isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        else:
            return obj

    def update_status(
        self,
        checkpoint: str,
        details: Dict[str, Any] = None,
        current_agent: str = None,
        urls_scraped: List[str] = None,
    ):
        """Update processing status with detailed checkpoint information."""
        try:
            now = datetime.now()
            elapsed_seconds = (now - self.start_time).total_seconds()

            status_data = {
                "session_id": self.session_id,
                "current_status": checkpoint,
                "last_updated": now.isoformat(),
                "elapsed_time_seconds": Decimal(str(elapsed_seconds)),
                "elapsed_time_formatted": self._format_elapsed_time(elapsed_seconds),
                "details": details or {},
                "checkpoint_history": self._get_checkpoint_history() + [checkpoint],
                "timestamp": now.isoformat(),
            }

            if current_agent:
                status_data["current_agent"] = current_agent
                status_data["agent_activity"] = {
                    "active_agent": current_agent,
                    "activity_started_at": now.isoformat(),
                    "task_description": self._get_agent_task_description(
                        checkpoint, current_agent
                    ),
                }

            if urls_scraped:
                status_data["web_scraping_progress"] = {
                    "urls_scraped": len(urls_scraped),
                    "scraped_urls": urls_scraped,
                    "scraping_method": "beautiful_soup_google_search",
                    "scraping_status": "active"
                    if checkpoint
                    in [
                        StatusCheckpoints.WEB_SCRAPING_IN_PROGRESS,
                        StatusCheckpoints.RESEARCH_IN_PROGRESS,
                    ]
                    else "completed",
                }

            status_data.update(self._get_checkpoint_specific_data(checkpoint, details))

            status_data = self._convert_floats_to_decimal(status_data)

            self.status_table.put_item(Item=status_data)

            logger.info(f"Status updated to {checkpoint} for session {self.session_id}")

        except Exception as e:
            logger.error(f"Error updating status: {e}")
            try:
                simple_status = {
                    "session_id": self.session_id,
                    "current_status": checkpoint,
                    "last_updated": datetime.now().isoformat(),
                    "checkpoint_history": [checkpoint],
                }
                self.status_table.put_item(Item=simple_status)
                logger.info(f"Simplified status update successful for {checkpoint}")
            except Exception as fallback_error:
                logger.error(f"Even simplified status update failed: {fallback_error}")

    def _format_elapsed_time(self, seconds: float) -> str:
        """Format elapsed time in human-readable format."""
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"

    def _get_checkpoint_history(self) -> List[str]:
        """Get checkpoint history from DynamoDB."""
        try:
            response = self.status_table.get_item(Key={"session_id": self.session_id})
            if "Item" in response:
                return response["Item"].get("checkpoint_history", [])
        except Exception as e:
            logger.warning(f"Could not retrieve checkpoint history: {e}")
        return []

    def _get_agent_task_description(self, checkpoint: str, agent: str) -> str:
        """Get task description for agent activity."""
        descriptions = {
            StatusCheckpoints.CUSTOM_PROMPT_PROCESSING: "Processing custom prompt and extracting context",
            StatusCheckpoints.FILE_PARSING_STARTED: "Parsing uploaded documents",
            StatusCheckpoints.WEB_SCRAPING_STARTED: "Initiating web scraping with Google search",
            StatusCheckpoints.WEB_SCRAPING_IN_PROGRESS: "Scraping web content with Beautiful Soup",
            StatusCheckpoints.WEB_SCRAPING_COMPLETED: "Web scraping completed",
            StatusCheckpoints.RESEARCH_STARTED: "Initiating comprehensive business research",
            StatusCheckpoints.RESEARCH_IN_PROGRESS: "Analyzing business operations and market position",
            StatusCheckpoints.RESEARCH_COMPLETED: "Business research completed",
            StatusCheckpoints.USE_CASES_GENERATING: "Generating business-aligned transformation use cases",
            StatusCheckpoints.USE_CASES_GENERATED: "Transformation use cases completed",
            StatusCheckpoints.WAFR_PROCESSING: "Processing WAFR assessment",
            StatusCheckpoints.REPORT_GENERATION_STARTED: "Generating comprehensive report with citations",
            StatusCheckpoints.REPORT_GENERATION_COMPLETED: "Report generation completed",
        }
        return descriptions.get(checkpoint, f"Processing {checkpoint}")

    def _get_checkpoint_specific_data(
        self, checkpoint: str, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get checkpoint-specific data for status tracking."""
        specific_data = {}

        if checkpoint == StatusCheckpoints.CUSTOM_PROMPT_PROCESSING:
            specific_data["custom_prompt_processing"] = {
                "processing_stage": "analyzing_custom_requirements",
                "focus_extraction": True,
                "context_integration": True,
            }
        elif checkpoint == StatusCheckpoints.WEB_SCRAPING_COMPLETED:
            specific_data["web_scraping_capabilities"] = {
                "google_search_enabled": True,
                "beautiful_soup_parsing": True,
                "concurrent_scraping": True,
                "citation_ready": True,
            }
        elif checkpoint == StatusCheckpoints.USE_CASES_GENERATED:
            specific_data["transformation_capabilities"] = {
                "business_focused": True,
                "company_aligned": True,
                "strategic_value": True,
                "web_enhanced": details.get("web_enhanced", False)
                if details
                else False,
                "custom_context_aligned": details.get("custom_context_aligned", False)
                if details
                else False,
            }
        elif checkpoint == StatusCheckpoints.REPORT_GENERATION_COMPLETED:
            specific_data["report_details"] = {
                "report_type": "consolidated_comprehensive_analysis",
                "quality_level": "professional_consulting_grade",
                "format": "pdf_with_clickable_citations",
                "citation_source": "web_scraping_with_beautiful_soup",
                "custom_context_integrated": details.get(
                    "content_enhanced_with_files", False
                )
                if details
                else False,
            }

        return specific_data

    def get_current_status(self) -> Dict[str, Any]:
        """Get current status from DynamoDB."""
        try:
            response = self.status_table.get_item(Key={"session_id": self.session_id})
            if "Item" in response:
                item = response["Item"]
                # Convert Decimal back to float for JSON serialization
                return self._convert_decimals_to_float(dict(item))
            return {"current_status": "unknown", "session_id": self.session_id}
        except Exception as e:
            logger.error(f"Error retrieving status: {e}")
            return {
                "current_status": "error",
                "session_id": self.session_id,
                "error": str(e),
            }

    def _convert_decimals_to_float(self, obj):
        """Convert Decimal values back to float for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_decimals_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals_to_float(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj
