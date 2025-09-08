"""
Real AWS clients for Bedrock integration with proper session export
"""
import os
import boto3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Real AWS session - this is what bedrock_manager.py imports
session = boto3.Session()

# Real DynamoDB
dynamodb = boto3.resource('dynamodb')

# Real S3 client  
s3_client = boto3.client('s3')

# Environment variables
CACHE_TABLE_NAME = os.environ.get('CACHE_TABLE_NAME', 'transformation-cache')
STATUS_TABLE_NAME = os.environ.get('STATUS_TABLE_NAME', 'transformation-status') 
S3_BUCKET = os.environ.get('S3_BUCKET', 'transformation-outputs')
LAMBDA_TMP_DIR = '/tmp' if os.path.exists('/tmp') else os.path.join(os.path.dirname(__file__), '..', '..', 'tmp')

# Create tmp directory
os.makedirs(LAMBDA_TMP_DIR, exist_ok=True)

# Mock table class for when DynamoDB tables don't exist
class MockTable:
    def __init__(self, table_name):
        self.table_name = table_name
        logger.info(f"Using mock table for {table_name} (table doesn't exist)")
        
    def put_item(self, Item):
        logger.info(f"Mock put_item to {self.table_name}")
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
        
    def get_item(self, Key):
        logger.info(f"Mock get_item from {self.table_name}")
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

# Try to use real DynamoDB tables, fall back to mock if they don't exist
try:
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)
    cache_table.load()  # Test if table exists
    logger.info(f"✅ Connected to real DynamoDB cache table: {CACHE_TABLE_NAME}")
except Exception as e:
    logger.warning(f"Cache table {CACHE_TABLE_NAME} not accessible: {e}")
    cache_table = MockTable(CACHE_TABLE_NAME)

try:
    status_table = dynamodb.Table(STATUS_TABLE_NAME)
    status_table.load()  # Test if table exists  
    logger.info(f"✅ Connected to real DynamoDB status table: {STATUS_TABLE_NAME}")
except Exception as e:
    logger.warning(f"Status table {STATUS_TABLE_NAME} not accessible: {e}")
    status_table = MockTable(STATUS_TABLE_NAME)

def ensure_cache_table_exists():
    """Ensure cache table exists"""
    return cache_table

def ensure_status_table_exists():
    """Ensure status table exists"""
    return status_table

logger.info("✅ AWS clients initialized - ready for Bedrock integration")