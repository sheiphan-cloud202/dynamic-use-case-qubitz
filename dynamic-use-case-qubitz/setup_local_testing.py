#!/usr/bin/env python3
"""
Setup script for local testing environment
"""
import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install required Python packages"""
    
    print("Installing Python dependencies...")
    
    packages = [
        "python-pptx==0.6.21",
        "PyPDF2",
        "PyMuPDF", 
        "boto3",
        "strands",
        "strands-tools",
        "reportlab"
    ]
    
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ {package} installed")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")

def setup_aws_credentials():
    """Guide user through AWS setup"""
    
    print("\nAWS Configuration:")
    print("Make sure you have AWS credentials configured.")
    print("Run: aws configure")
    print("Or set environment variables:")
    print("  AWS_ACCESS_KEY_ID=your_access_key")
    print("  AWS_SECRET_ACCESS_KEY=your_secret_key")
    print("  AWS_DEFAULT_REGION=us-east-1")

def create_directories():
    """Create necessary directories"""
    
    print("\nCreating directories...")
    
    dirs = ["tmp", "templates", "logs"]
    
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"✓ Created {dir_name}/ directory")

def main():
    print("Local Testing Environment Setup")
    print("=" * 35)
    
    install_dependencies()
    create_directories()
    setup_aws_credentials()
    
    print("\n✓ Setup complete!")
    print("Run: python local_testing_guide.py")

if __name__ == "__main__":
    main()