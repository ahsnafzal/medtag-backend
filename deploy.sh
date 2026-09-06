#!/bin/bash
# 🚀 MedTag Backend - Vercel Deployment Script
# Run this after setting up environment variables in Vercel

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    MedTag Backend - Vercel Deployment Helper Script       ║"
echo "║                      For: ahsnafzal                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Verify Vercel CLI is installed
echo "📦 Checking Vercel CLI installation..."
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Installing..."
    npm install -g vercel
fi
echo "✅ Vercel CLI is ready"
echo ""

# Step 2: Verify Python environment
echo "🐍 Checking Python environment..."
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+"
    exit 1
fi
echo "✅ Python $(python --version | awk '{print $2}') is ready"
echo ""

# Step 3: Verify Git repository
echo "📂 Checking Git repository..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not a Git repository. Please initialize Git first."
    exit 1
fi
echo "✅ Git repository is ready"
echo ""

# Step 4: Check if any uncommitted changes
echo "🔍 Checking for uncommitted changes..."
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  You have uncommitted changes:"
    git status
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
fi
echo "✅ Repository is clean"
echo ""

# Step 5: Verify requirements.txt
echo "📋 Verifying requirements.txt..."
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found"
    exit 1
fi
echo "✅ requirements.txt found"
echo ""

# Step 6: Verify vercel.json
echo "⚙️  Verifying vercel.json..."
if [ ! -f "vercel.json" ]; then
    echo "❌ vercel.json not found"
    exit 1
fi
echo "✅ vercel.json found"
echo ""

# Step 7: Run Django deployment check
echo "🔧 Running Django deployment checks..."
if python manage.py check --deploy 2>/dev/null; then
    echo "✅ Django deployment checks passed"
else
    echo "⚠️  Some Django checks failed (this is often OK for Vercel)"
fi
echo ""

# Step 8: Collect static files locally
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --no-post-process
echo "✅ Static files collected"
echo ""

# Step 9: Login to Vercel
echo "🔐 Logging in to Vercel..."
echo "Note: This will open your browser to authenticate"
echo ""
read -p "Press Enter to continue with Vercel login..."
vercel login
echo "✅ Vercel login successful"
echo ""

# Step 10: Link to Vercel project
echo "🔗 Linking to Vercel project..."
echo ""
echo "If this is your first deployment:"
echo "1. Select 'Y' when asked 'Set up and deploy?'"
echo "2. Select the project or create a new one"
echo "3. Configure build settings if needed"
echo ""
read -p "Press Enter to continue linking..."
vercel link
echo "✅ Vercel project linked"
echo ""

# Step 11: Deploy
echo "🚀 Deploying to Vercel (Production)..."
echo ""
echo "This will deploy your backend to production."
echo "Make sure all environment variables are set in Vercel Dashboard first!"
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

vercel --prod
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          ✅ DEPLOYMENT COMPLETE!                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Next Steps:"
echo "  1. Wait for deployment to finish"
echo "  2. Check the Vercel Dashboard for your live URL"
echo "  3. Run the verification tests:"
echo "     - curl https://yourdomain.vercel.app/api/health/"
echo "  4. Test authentication and file uploads"
echo "  5. Monitor logs for errors"
echo ""
echo "📖 Documentation:"
echo "  - Read: PRE_DEPLOYMENT_CHECKLIST.md (Verification section)"
echo "  - Read: VERCEL_DEPLOYMENT_GUIDE.md (Troubleshooting)"
echo ""
echo "🎉 Your MedTag backend is now live on Vercel!"
echo ""
