#!/bin/bash

# RxVoice Assistant Setup Script
echo "🏥 Setting up RxVoice Assistant..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js $(node -v) detected"

# Setup backend
echo "📦 Setting up backend..."
cd backend
if [ ! -f "package.json" ]; then
    echo "❌ Backend package.json not found"
    exit 1
fi

npm install
if [ $? -ne 0 ]; then
    echo "❌ Backend npm install failed"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit backend/.env with your API keys before running the application"
fi

cd ..

# Setup frontend
echo "🎨 Setting up frontend..."
cd frontend
if [ ! -f "package.json" ]; then
    echo "❌ Frontend package.json not found"
    exit 1
fi

npm install
if [ $? -ne 0 ]; then
    echo "❌ Frontend npm install failed"
    exit 1
fi

cd ..

# Create database directory if it doesn't exist
mkdir -p database

echo "✅ Setup complete!"
echo ""
echo "🚀 To start the application:"
echo "1. Edit backend/.env with your API keys"
echo "2. Run 'npm run dev' in the backend directory"
echo "3. Run 'npm start' in the frontend directory"
echo "4. Open http://localhost:3000 in your browser"
echo ""
echo "📚 See README.md for detailed instructions"

