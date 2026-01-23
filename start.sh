#!/bin/bash
# GradeSync Quick Start Script

set -e

echo "🚀 GradeSync Service Startup Script"
echo "================================"
echo ""

# Check if in correct directory
if [ ! -f "api/app.py" ]; then
    echo "❌ Error: Please run this script from the GradeSync root directory"
    exit 1
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Please create .env and configure the following environment variables:"
    echo "   - GRADESCOPE_EMAIL"
    echo "   - GRADESCOPE_PASSWORD"
    echo "   - PL_API_TOKEN"
    echo "   - ICLICKER_USERNAME"
    echo "   - ICLICKER_PASSWORD"
    echo "   - SERVICE_ACCOUNT_CREDENTIALS"
    echo "   - DATABASE_URL"
    echo ""
fi

# Check database connection
echo "📦 Checking database connection..."
python3 <<EOF
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL', 'postgresql://gradesync:changeme@localhost:5432/gradesync')
print(f"   Database: {db_url}")
EOF

echo ""

# Start FastAPI
echo "🌐 Starting FastAPI service..."
echo "   Visit http://localhost:8000/docs to view API documentation"
echo ""
echo "Press Ctrl+C to stop the service"
echo "================================"
echo ""

# Start with uvicorn, supports auto-reload
exec uvicorn api.app:app --host 0.0.0.0 --port 8001 --reload
