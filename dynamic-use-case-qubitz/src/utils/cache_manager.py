"""
Cache management for the Business Transformation Agent.
"""
import json
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from src.services.aws_clients import cache_table

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheManager:
    """Enhanced cache manager with custom prompt awareness."""
    
    @staticmethod
    def _convert_for_dynamodb(obj):
        """Convert data types for DynamoDB storage."""
        if isinstance(obj, dict):
            return {k: CacheManager._convert_for_dynamodb(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [CacheManager._convert_for_dynamodb(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    @staticmethod
    def generate_cache_key(payload: Dict) -> str:
        """Generate a unique cache key based on the payload including custom prompt."""
        try:
            # Normalize payload for consistent hashing
            normalized_payload = {
                'company_name': payload.get('company_name', '').strip().lower(),
                'company_url': payload.get('company_url', '').strip().lower(),
                'action': payload.get('action', 'start')
            }
            
            # Include custom prompt in cache key
            if 'prompt' in payload and payload['prompt']:
                normalized_payload['prompt_hash'] = hashlib.md5(payload['prompt'].encode()).hexdigest()[:16]
            
            # Include files in cache key if present
            if 'files' in payload and payload['files']:
                file_hashes = []
                for file_url in payload['files']:
                    file_hashes.append(hashlib.md5(file_url.encode()).hexdigest()[:8])
                normalized_payload['file_hashes'] = sorted(file_hashes)
            
            # For select_use_cases action, include selected use case IDs
            if normalized_payload['action'] == 'select_use_cases' and 'selected_use_case_ids' in payload:
                normalized_payload['selected_use_case_ids'] = sorted(payload.get('selected_use_case_ids', []))
            
            # For fetch action, include fetch type
            if normalized_payload['action'] == 'fetch' and 'fetch_type' in payload:
                normalized_payload['fetch_type'] = payload.get('fetch_type', '')
                # Include selected use case IDs if present
                if 'selected_use_case_ids' in payload:
                    normalized_payload['selected_use_case_ids'] = sorted(payload.get('selected_use_case_ids', []))
            
            # Generate hash
            payload_str = json.dumps(normalized_payload, sort_keys=True)
            return hashlib.md5(payload_str.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            # Fallback to simple key
            return f"{payload.get('company_name', 'unknown')}_{payload.get('action', 'unknown')}"
    
    @staticmethod
    def get_from_cache(cache_key: str) -> Optional[Dict]:
        """Get result from cache if available and not expired."""
        try:
            response = cache_table.get_item(Key={'cache_key': cache_key})
            if 'Item' not in response:
                logger.info(f"Cache miss for key: {cache_key}")
                return None
            
            item = response['Item']
            
            # Check if cache is still valid (within same day)
            try:
                cached_date = datetime.fromisoformat(item.get('cached_at', '1970-01-01T00:00:00'))
                current_date = datetime.now()
                
                # Cache expires at end of day
                if (current_date.date() > cached_date.date()):
                    logger.info(f"Cache expired for key: {cache_key}")
                    return None
            except Exception as date_error:
                logger.warning(f"Error checking cache expiry: {date_error}")
                return None
            
            # Parse cached result
            try:
                result = json.loads(item.get('result', '{}'))
                logger.info(f"Cache hit for key: {cache_key}")
                
                # Add cache metadata
                result['_cache'] = {
                    'hit': True,
                    'cached_at': item.get('cached_at'),
                    'cache_key': cache_key
                }
                
                return result
            except json.JSONDecodeError as json_error:
                logger.error(f"Error parsing cached result: {json_error}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None
    
    @staticmethod
    def save_to_cache(cache_key: str, payload: Dict, result: Dict) -> bool:
        """Save result to cache with TTL until end of day."""
        try:
            # Calculate TTL (seconds until end of day)
            now = datetime.now()
            end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
            ttl_seconds = int((end_of_day - now).total_seconds())
            
            # Prepare data for storage
            cache_data = {
                'cache_key': cache_key,
                'payload': json.dumps(payload, default=str),
                'result': json.dumps(result, default=str),
                'cached_at': now.isoformat(),
                'ttl': ttl_seconds,
                'expires_at': end_of_day.isoformat()
            }
            
            # Convert for DynamoDB
            cache_data = CacheManager._convert_for_dynamodb(cache_data)
            
            # Store in cache
            cache_table.put_item(Item=cache_data)
            logger.info(f"Saved to cache: {cache_key}, expires at {end_of_day.isoformat()}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
            return False
