#!/usr/bin/env python3
"""Setup script for the pharmacy voice agent."""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False

def check_requirements():
    """Check if required tools are installed."""
    print("🔍 Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ is required")
        return False
    print("✅ Python version is compatible")
    
    # Check for required commands
    commands = ["pip", "ngrok"]
    for cmd in commands:
        if subprocess.run(f"which {cmd}", shell=True, capture_output=True).returncode != 0:
            print(f"❌ {cmd} is not installed or not in PATH")
            if cmd == "ngrok":
                print("   Install ngrok from: https://ngrok.com/download")
            return False
        print(f"✅ {cmd} is available")
    
    return True

def setup_environment():
    """Set up the development environment."""
    print("\n🚀 Setting up pharmacy voice agent...")
    
    # Check requirements first
    if not check_requirements():
        print("\n❌ Requirements check failed. Please install missing dependencies.")
        return False
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        if not run_command("cp env.example .env", "Creating .env file"):
            return False
        print("📝 Please edit .env file with your API keys and configuration")
    else:
        print("✅ .env file already exists")
    
    # Initialize database
    if not run_command("python -m server.persistence.init_db", "Initializing database"):
        return False
    
    # Seed database with test data
    if not run_command("python -m server.persistence.seed_data", "Seeding test data"):
        return False
    
    # Create static directories
    Path("static/tts").mkdir(parents=True, exist_ok=True)
    print("✅ Created static directories")
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your API keys:")
    print("   - TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    print("   - DEEPGRAM_API_KEY")
    print("   - ELEVENLABS_API_KEY")
    print("   - GOOGLE_API_KEY")
    print("   - STATIC_SIGNING_SECRET (generate a random string)")
    print("\n2. Start the development server:")
    print("   make dev")
    print("\n3. In another terminal, start ngrok:")
    print("   make tunnel")
    print("\n4. Update PUBLIC_HOST in .env with your ngrok URL")
    print("\n5. Configure your Twilio phone number webhooks:")
    print("   - Voice URL: https://your-ngrok-url.ngrok.io/twilio/voice")
    print("   - Status callback: https://your-ngrok-url.ngrok.io/twilio/status")
    print("\n6. Test by calling your Twilio number!")
    
    return True

if __name__ == "__main__":
    success = setup_environment()
    sys.exit(0 if success else 1)
