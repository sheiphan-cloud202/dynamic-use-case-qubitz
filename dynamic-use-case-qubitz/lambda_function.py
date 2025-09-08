"""
Updated Lambda handler with PowerPoint presentation support.
"""

# 🔧 Set EFS package path FIRST, before any imports
import sys
sys.path.insert(0, "/mnt/efs/envs/strands_lambda/lambda-env")

# ✅ Now safely import everything else
import json
import logging
import traceback
from datetime import datetime

# Local imports (which depend on pdfplumber, PyPDF2, etc.)
from src.orchestrator import AgenticWAFROrchestrator
from src.utils.cache_manager import CacheManager
from src.utils.status_tracker import StatusTracker, StatusCheckpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    """
    AWS Lambda handler with web scraping, custom prompt processing, file parsing, 
    personalized transformation, caching, status tracking, consolidated report generation,
    and PowerPoint presentation generation with multiple templates.
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        # Log request details
        action = body.get('action', 'start')
        output_format = body.get('output_format', 'pdf')
        presentation_style = body.get('presentation_style', 'first_deck')
        
        logger.info(f"Processing request - Action: {action}, Format: {output_format}, Style: {presentation_style}")
        
        if body.get('prompt'):
            logger.info(f"Custom prompt provided: {len(body['prompt'])} characters")
        
        if body.get('files'):
            logger.info(f"Files provided: {len(body['files'])} files")

        # Handle polling action
        if action == 'fetch' and body.get('fetch_type') == 'status':
            session_id = body.get('session_id')
            if session_id:
                status_tracker = StatusTracker(session_id)
                current_status = status_tracker.get_current_status()
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps({
                        'status': 'status_retrieved',
                        'session_id': session_id,
                        'current_status': current_status,
                        'timestamp': datetime.now().isoformat(),
                        'polling_recommended': current_status.get('current_status') not in [
                            StatusCheckpoints.COMPLETED,
                            StatusCheckpoints.ERROR,
                            StatusCheckpoints.USE_CASES_GENERATED,
                            StatusCheckpoints.REPORT_GENERATION_COMPLETED,
                            StatusCheckpoints.PRESENTATION_COMPLETED
                        ]
                    }, default=str)
                }

        # Validate output format and presentation style
        valid_formats = ['pdf', 'ppt', 'both']
        valid_styles = ['first_deck', 'marketing', 'use_case', 'technical', 'strategy']
        
        if output_format not in valid_formats:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': f'Invalid output_format. Must be one of: {valid_formats}',
                    'valid_formats': valid_formats,
                    'valid_styles': valid_styles
                })
            }
        
        if presentation_style not in valid_styles:
            logger.warning(f"Invalid presentation_style '{presentation_style}', will use 'first_deck'")
            # Don't return error, just log warning - orchestrator will handle fallback

        # Generate and check cache (skip for status requests)
        cache_key = CacheManager.generate_cache_key(body)
        if action != 'fetch' or body.get('fetch_type') != 'status':
            cached_result = CacheManager.get_from_cache(cache_key)
            if cached_result:
                logger.info(f"Returning cached result for key: {cache_key}")
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                    },
                    'body': json.dumps(cached_result, default=str)
                }

        # Run orchestrator with PowerPoint support
        logger.info(f"Cache miss for key: {cache_key}, processing transformation request with PowerPoint support.")
        orchestrator = AgenticWAFROrchestrator()
        result = orchestrator.process_request(body)

        # Enhanced logging for PowerPoint generation
        if result.get('status') == 'completed':
            if result.get('presentation_url'):
                logger.info(f"PowerPoint presentation generated: {result['presentation_url']}")
            if result.get('report_url'):
                logger.info(f"PDF report generated: {result['report_url']}")
            
            total_outputs = sum([
                1 if result.get('presentation_url') else 0,
                1 if result.get('report_url') else 0
            ])
            logger.info(f"Successfully generated {total_outputs} output(s) for {body.get('company_name')}")

        # Cache result (skip for status requests)
        if action != 'fetch' or body.get('fetch_type') != 'status':
            CacheManager.save_to_cache(cache_key, body, result)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        logger.error(traceback.format_exc())
        
        # Enhanced error response with PowerPoint context
        error_context = {
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__,
            'timestamp': datetime.now().isoformat(),
            'supported_formats': ['pdf', 'ppt', 'both'],
            'supported_styles': ['first_deck', 'marketing', 'use_case', 'technical', 'strategy']
        }
        
        # Add request context if available
        try:
            if isinstance(event.get('body'), str):
                body = json.loads(event['body'])
            else:
                body = event.get('body', event)
            
            error_context.update({
                'request_action': body.get('action'),
                'request_format': body.get('output_format'),
                'request_style': body.get('presentation_style')
            })
        except:
            pass
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_context)
        }

# Optional: Add a health check endpoint
def health_check_handler(event, context):
    """Health check endpoint for monitoring PowerPoint generation capabilities"""
    
    try:
        # Check if PowerPoint libraries are available
        from src.agents.multi_template_ppt_generator import PPTX_AVAILABLE, TEMPLATE_REGISTRY
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'powerpoint_available': PPTX_AVAILABLE,
                'available_templates': list(TEMPLATE_REGISTRY.keys()),
                'supported_formats': ['pdf', 'ppt', 'both'],
                'timestamp': datetime.now().isoformat()
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }