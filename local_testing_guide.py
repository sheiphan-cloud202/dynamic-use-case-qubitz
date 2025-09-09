#!/usr/bin/env python3
"""
Local Testing Guide for Multi-Template PPT Generation System
This script simulates the Lambda environment locally for testing
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add src to Python path (simulating Lambda environment)
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

def setup_local_environment():
    """Setup local environment to simulate AWS Lambda"""
    
    print("Setting up local testing environment...")
    
    # Set environment variables (replace with your actual values)
    os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
    os.environ.setdefault('CACHE_TABLE_NAME', 'transformation-cache')
    os.environ.setdefault('STATUS_TABLE_NAME', 'transformation-status')
    os.environ.setdefault('S3_BUCKET', 'your-bucket-name')
    
    # Create local tmp directory (simulating Lambda /tmp)
    tmp_dir = project_root / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    os.environ['LAMBDA_TMP_DIR'] = str(tmp_dir)
    
    print(f"✓ Environment setup complete")
    print(f"✓ Project root: {project_root}")
    print(f"✓ Temp directory: {tmp_dir}")

def test_component_imports():
    """Test that all components can be imported"""
    
    print("\nTesting component imports...")
    
    try:
        # Test core imports
        from src.orchestrator import AgenticWAFROrchestrator
        print("✓ Orchestrator imported")
        
        from src.agents.multi_template_ppt_generator import MultiTemplatePPTGenerator, TEMPLATE_REGISTRY
        print(f"✓ PPT Generator imported with {len(TEMPLATE_REGISTRY)} templates")
        
        from src.utils.status_tracker import StatusTracker, StatusCheckpoints
        print("✓ Status Tracker imported")
        
        from src.core.bedrock_manager import EnhancedModelManager
        print("✓ Bedrock Manager imported")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_template_availability():
    """Test PowerPoint template availability"""
    
    print("\nTesting PowerPoint template system...")
    
    try:
        from src.agents.multi_template_ppt_generator import TEMPLATE_REGISTRY, PPTX_AVAILABLE
        
        print(f"✓ PowerPoint library available: {PPTX_AVAILABLE}")
        print(f"✓ Available templates: {list(TEMPLATE_REGISTRY.keys())}")
        
        if PPTX_AVAILABLE:
            # Test template instantiation
            for template_name, template_class in TEMPLATE_REGISTRY.items():
                template = template_class()
                print(f"  - {template_name}: {template.name} template ready")
        
        return PPTX_AVAILABLE
        
    except Exception as e:
        print(f"✗ Template test error: {e}")
        return False

def test_orchestrator_initialization():
    """Test orchestrator initialization"""
    
    print("\nTesting orchestrator initialization...")
    
    try:
        from src.orchestrator import AgenticWAFROrchestrator
        
        orchestrator = AgenticWAFROrchestrator()
        print("✓ Orchestrator initialized successfully")
        print(f"✓ PPT Generator available: {hasattr(orchestrator, 'multi_ppt_generator')}")
        
        return orchestrator
        
    except Exception as e:
        print(f"✗ Orchestrator initialization error: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_test_payload(company_name="Netflix", output_format="both", presentation_style="marketing"):
    """Create test payload for API simulation"""
    
    return {
        "action": "start",
        "company_name": company_name,
        "company_url": f"https://{company_name.lower()}.com",
        "output_format": output_format,
        "presentation_style": presentation_style,
        "session_id": f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "prompt": f"Create a {presentation_style} presentation for {company_name} focusing on digital transformation, AI implementation, and business optimization.",
        "files": [],  # No files for basic test
        "project_id": "local-test",
        "user_id": "test-user"
    }

def test_end_to_end_generation(orchestrator, payload):
    """Test complete end-to-end generation"""
    
    print(f"\nTesting end-to-end generation...")
    print(f"Company: {payload['company_name']}")
    print(f"Output Format: {payload['output_format']}")
    print(f"Presentation Style: {payload['presentation_style']}")
    
    try:
        print("\nProcessing request...")
        result = orchestrator.process_request(payload)
        
        print(f"\nResult Status: {result.get('status')}")
        print(f"Session ID: {result.get('session_id')}")
        print(f"Message: {result.get('message')}")
        
        if result.get('status') == 'completed':
            print(f"\n✓ Generation completed successfully!")
            
            if result.get('report_url'):
                print(f"✓ PDF Report: {result['report_url']}")
            
            if result.get('presentation_url'):
                print(f"✓ PowerPoint: {result['presentation_url']}")
            
            print(f"✓ Use Cases Generated: {result.get('total_use_cases', 0)}")
            
            # Check local files
            check_local_generated_files()
            
        else:
            print(f"✗ Generation failed: {result.get('message')}")
            
        return result
        
    except Exception as e:
        print(f"✗ End-to-end test error: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_local_generated_files():
    """Check for locally generated files"""
    
    print(f"\nChecking for generated files...")
    
    # Check temp directory
    tmp_dir = Path(os.environ.get('LAMBDA_TMP_DIR', './tmp'))
    
    if tmp_dir.exists():
        files = list(tmp_dir.rglob('*'))
        print(f"Files in temp directory: {len(files)}")
        
        for file_path in files:
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"  - {file_path.name}: {size:,} bytes")
    
    # Check current directory for any PPT files
    current_dir = Path('.')
    ppt_files = list(current_dir.glob('*.pptx'))
    
    if ppt_files:
        print(f"\nPowerPoint files in current directory:")
        for ppt_file in ppt_files:
            size = ppt_file.stat().st_size
            print(f"  - {ppt_file.name}: {size:,} bytes")

def test_different_templates():
    """Test all different presentation templates"""
    
    print(f"\nTesting all presentation templates...")
    
    from src.agents.multi_template_ppt_generator import TEMPLATE_REGISTRY
    
    orchestrator = test_orchestrator_initialization()
    if not orchestrator:
        return
    
    test_results = {}
    
    for template_name in TEMPLATE_REGISTRY.keys():
        print(f"\n--- Testing {template_name} template ---")
        
        payload = create_test_payload(
            company_name="TechCorp",
            output_format="ppt", 
            presentation_style=template_name
        )
        
        try:
            result = orchestrator.process_request(payload)
            test_results[template_name] = {
                'status': result.get('status'),
                'presentation_url': result.get('presentation_url'),
                'message': result.get('message')
            }
            
            if result.get('status') == 'completed':
                print(f"✓ {template_name} template generated successfully")
            else:
                print(f"✗ {template_name} template failed: {result.get('message')}")
                
        except Exception as e:
            print(f"✗ {template_name} template error: {e}")
            test_results[template_name] = {'status': 'error', 'error': str(e)}
    
    print(f"\n--- Template Test Summary ---")
    for template, result in test_results.items():
        status = result.get('status', 'unknown')
        print(f"{template}: {status}")
    
    return test_results

def simulate_lambda_handler():
    """Simulate the actual Lambda handler"""
    
    print(f"\nSimulating Lambda handler...")
    
    # Import the actual lambda function
    try:
        from lambda_function import lambda_handler
        
        # Create test event (simulating API Gateway)
        test_event = {
            "body": json.dumps(create_test_payload())
        }
        
        # Create test context
        class TestContext:
            def __init__(self):
                self.function_name = "test-function"
                self.aws_request_id = "test-request-id"
        
        context = TestContext()
        
        print("Calling lambda_handler...")
        response = lambda_handler(test_event, context)
        
        print(f"Lambda Response:")
        print(f"Status Code: {response.get('statusCode')}")
        print(f"Headers: {response.get('headers', {}).keys()}")
        
        # Parse response body
        response_body = json.loads(response.get('body', '{}'))
        print(f"Response Status: {response_body.get('status')}")
        print(f"Response Message: {response_body.get('message')}")
        
        return response
        
    except Exception as e:
        print(f"✗ Lambda simulation error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main testing function"""
    
    print("Local Testing Suite for Multi-Template PPT Generation")
    print("=" * 60)
    
    # Setup
    setup_local_environment()
    
    # Component tests
    if not test_component_imports():
        print("✗ Component import tests failed. Check your imports.")
        return
    
    if not test_template_availability():
        print("✗ PowerPoint template tests failed. Install python-pptx.")
        return
    
    # Orchestrator test
    orchestrator = test_orchestrator_initialization()
    if not orchestrator:
        print("✗ Orchestrator initialization failed.")
        return
    
    # Choose test type
    print(f"\nTest Options:")
    print("1. Quick test (Netflix marketing presentation)")
    print("2. All templates test")
    print("3. Lambda handler simulation")
    print("4. Custom test")
    
    choice = input("Choose test (1-4, default=1): ").strip()
    
    if choice == "2":
        test_different_templates()
    elif choice == "3":
        simulate_lambda_handler()
    elif choice == "4":
        company = input("Company name: ").strip() or "TestCorp"
        format_choice = input("Output format (pdf/ppt/both, default=both): ").strip() or "both"
        style_choice = input("Presentation style (first_deck/marketing/use_case/technical/strategy, default=marketing): ").strip() or "marketing"
        
        payload = create_test_payload(company, format_choice, style_choice)
        test_end_to_end_generation(orchestrator, payload)
    else:
        # Default quick test
        payload = create_test_payload()
        test_end_to_end_generation(orchestrator, payload)
    
    print(f"\n" + "=" * 60)
    print("Testing complete! Check generated files in your directory.")

if __name__ == "__main__":
    main()