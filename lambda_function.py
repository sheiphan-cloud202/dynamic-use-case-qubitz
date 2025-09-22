"""
Bare minimum Lambda handler.
"""

# 🔧 Set EFS package path FIRST, before any imports
import sys
sys.path.insert(0, "/mnt/efs/dynamic_usecase/myenv/lib/python3.11/site-packages")

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
    personalized transformation, caching, status tracking, and consolidated report generation.
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        # Log prompt and files if available
        if body.get('prompt'):
            logger.info(f"Custom prompt provided: {len(body['prompt'])} characters")
        
        if body.get('files'):
            logger.info(f"Files provided: {len(body['files'])} files")

        # Handle polling action
        if body.get('action') == 'fetch' and body.get('fetch_type') == 'status':
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
                            StatusCheckpoints.REPORT_GENERATION_COMPLETED
                        ]
                    }, default=str)
                }

        # Generate and check cache
        cache_key = CacheManager.generate_cache_key(body)
        if body.get('action') != 'fetch' or body.get('fetch_type') != 'status':
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

        # Run orchestrator
        logger.info(f"Cache miss for key: {cache_key}, processing transformation request.")
        orchestrator = AgenticWAFROrchestrator()
        result = orchestrator.process_request(body)

        # Cache result
        if body.get('action') != 'fetch' or body.get('fetch_type') != 'status':
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
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'message': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            })
        }
