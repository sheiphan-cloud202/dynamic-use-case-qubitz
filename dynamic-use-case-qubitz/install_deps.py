#!/usr/bin/env python3
"""
Install dependencies for PDF to PowerPoint system
"""
import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"Installed {package}")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}")
        return False

def main():
    print("Installing PDF to PowerPoint dependencies...")
    
    packages = [
        "python-pptx",
        "PyMuPDF", 
        "PyPDF2",
        "boto3"
    ]
    
    for pkg in packages:
        install_package(pkg)
    
    print("\nInstallation complete!")
    print("Make sure AWS credentials are configured:")
    print("aws configure")

if __name__ == "__main__":
    main()