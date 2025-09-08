"""
Bedrock Model Manager for the Business Transformation Agent.
"""
import random
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from src.services.aws_clients import session

class EnhancedModelManager:
    """Advanced model manager with multiple fallback models and load balancing."""
    
    def __init__(self):
        self.boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=60,
            max_pool_connections=50
        )
        
        # Primary model pool for load balancing
        self.primary_models = [
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                temperature=0.1,
                max_tokens=40000,
                boto_session=session,
                boto_client_config=self.boto_config
            ),
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                temperature=0.2,
                max_tokens=40000,
                boto_session=session,
                boto_client_config=self.boto_config
            ),
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                temperature=0.15,
                max_tokens=40000,
                boto_session=session,
                boto_client_config=self.boto_config
            )
        ]
        
        # Research and business analysis models
        self.research_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.2,
            max_tokens=40000,
            boto_session=session,
            boto_client_config=self.boto_config
        )
        
        self.creative_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.5,
            max_tokens=40000,
            boto_session=session,
            boto_client_config=self.boto_config
        )
        
        # Fallback models with different configurations
        self.fallback_models = [
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                temperature=0.1,
                max_tokens=35000,
                boto_session=session,
                boto_client_config=self.boto_config
            ),
            BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                temperature=0.1,
                max_tokens=35000,
                boto_session=session,
                boto_client_config=self.boto_config
            )
        ]
        
        # Ultra-fast emergency model
        self.emergency_model = BedrockModel(
            model_id="us.amazon.nova-lite-v1:0",
            temperature=0.0,
            max_tokens=35000,
            boto_session=session,
            boto_client_config=self.boto_config
        )

    def get_random_primary_model(self):
        """Get random primary model for load balancing."""
        return random.choice(self.primary_models)

    def get_fallback_model(self, attempt: int):
        """Get fallback model based on attempt number."""
        if attempt < len(self.fallback_models):
            return self.fallback_models[attempt]
        return self.emergency_model
