"""
Centralized AWS client and table initialization.
"""

import os
import boto3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS session configuration
session = boto3.Session(region_name="us-east-1")

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
CACHE_TABLE_NAME = os.environ.get("CACHE_TABLE_NAME", "WAFRCache")
STATUS_TABLE_NAME = os.environ.get("STATUS_TABLE_NAME", "WAFRStatusTracking")
S3_BUCKET = os.environ.get("S3_BUCKET", "qubitz-customer-prod")
LAMBDA_TMP_DIR = "/tmp"

# Initialize AWS clients for report generation
s3_client = boto3.client("s3", region_name="us-east-1")


# Create cache table if it doesn't exist
def ensure_cache_table_exists():
    try:
        existing_tables = dynamodb.meta.client.list_tables()["TableNames"]
        if CACHE_TABLE_NAME not in existing_tables:
            logger.info(f"Creating cache table: {CACHE_TABLE_NAME}")
            table = dynamodb.create_table(
                TableName=CACHE_TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "cache_key", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "cache_key", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            # Wait for table creation
            table.meta.client.get_waiter("table_exists").wait(
                TableName=CACHE_TABLE_NAME
            )
            logger.info(f"Cache table created: {CACHE_TABLE_NAME}")
        return dynamodb.Table(CACHE_TABLE_NAME)
    except Exception as e:
        logger.error(f"Error ensuring cache table exists: {e}")
        return dynamodb.Table(CACHE_TABLE_NAME)


# Ensure status tracking table exists
def ensure_status_table_exists():
    try:
        existing_tables = dynamodb.meta.client.list_tables()["TableNames"]
        if STATUS_TABLE_NAME not in existing_tables:
            logger.info(f"Creating status tracking table: {STATUS_TABLE_NAME}")
            table = dynamodb.create_table(
                TableName=STATUS_TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 10,
                    "WriteCapacityUnits": 10,
                },
            )
            # Wait for table creation
            table.meta.client.get_waiter("table_exists").wait(
                TableName=STATUS_TABLE_NAME
            )
            logger.info(f"Status tracking table created: {STATUS_TABLE_NAME}")
        return dynamodb.Table(STATUS_TABLE_NAME)
    except Exception as e:
        logger.error(f"Error ensuring status table exists: {e}")
        return dynamodb.Table(STATUS_TABLE_NAME)


# Get table references
cache_table = ensure_cache_table_exists()
status_table = ensure_status_table_exists()
