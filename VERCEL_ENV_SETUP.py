#!/usr/bin/env python3
"""
MedTag Backend - Vercel Environment Variables Generator
Generates the exact environment variables needed for your Vercel deployment
"""

import json
from datetime import datetime

def generate_env_json():
    """Generate environment variables in JSON format for Vercel"""
    
    env_vars = {
        "ENVIRONMENT": {
            "value": "production",
            "description": "Set Django to production mode"
        },
        "SECRET_KEY": {
            "value": "🔑 GENERATE NEW (see instructions below)",
            "description": "Django secret key - MUST generate new one"
        },
        "DEBUG": {
            "value": "False",
            "description": "Disable debug mode in production"
        },
        "ALLOWED_HOSTS": {
            "value": "yourdomain.vercel.app,yourdomain.com",
            "description": "Comma-separated list of allowed domains"
        },
        
        # Database
        "DB_NAME": {
            "value": "verceldb_xxxxx",
            "description": "From Vercel Postgres dashboard"
        },
        "DB_USER": {
            "value": "default",
            "description": "Vercel Postgres default user"
        },
        "DB_PASSWORD": {
            "value": "🔑 From Vercel Postgres",
            "description": "Database password - get from Vercel"
        },
        "DB_HOST": {
            "value": "ep-xxxxx.us-east-1.postgres.vercel-storage.com",
            "description": "Database host - get from Vercel Postgres"
        },
        "DB_PORT": {
            "value": "5432",
            "description": "PostgreSQL default port"
        },
        
        # Frontend
        "CORS_ALLOWED_ORIGINS": {
            "value": "https://yourdomain.com",
            "description": "Comma-separated list of allowed origins"
        },
        "REACTAPP_RESET_URL": {
            "value": "https://yourdomain.com/reset-password/",
            "description": "Frontend password reset URL"
        },
        "LOGIN_URI": {
            "value": "https://yourdomain.com/login",
            "description": "Frontend login URL"
        },
        "PUBLIC_BASE_URL": {
            "value": "https://yourdomain.vercel.app",
            "description": "Your Vercel backend URL"
        },
        
        # Email
        "EMAIL_HOST": {
            "value": "smtp.gmail.com",
            "description": "Gmail SMTP server"
        },
        "EMAIL_PORT": {
            "value": "587",
            "description": "SMTP port for TLS"
        },
        "EMAIL_USE_TLS": {
            "value": "True",
            "description": "Use TLS encryption"
        },
        "EMAIL_HOST_USER": {
            "value": "your-email@gmail.com",
            "description": "Gmail address to send from"
        },
        "EMAIL_HOST_PASSWORD": {
            "value": "🔑 Gmail App Password (NOT main password)",
            "description": "Generated from https://myaccount.google.com/apppasswords"
        },
        
        # AWS S3
        "USE_S3": {
            "value": "True",
            "description": "Use S3 for file storage"
        },
        "AWS_ACCESS_KEY_ID": {
            "value": "🔑 NEW AWS Access Key",
            "description": "Generate new key from AWS IAM"
        },
        "AWS_SECRET_ACCESS_KEY": {
            "value": "🔑 NEW AWS Secret Key",
            "description": "Generate new secret from AWS IAM"
        },
        "AWS_STORAGE_BUCKET_NAME": {
            "value": "your-bucket-name",
            "description": "S3 bucket name (no spaces)"
        },
        "AWS_S3_REGION_NAME": {
            "value": "eu-north-1",
            "description": "AWS region"
        },
        
        # Stripe
        "STRIPE_SECRET_KEY": {
            "value": "sk_live_🔑 Your production secret key",
            "description": "Stripe production secret key (NOT test key)"
        },
        "STRIPE_PUBLISHABLE_KEY": {
            "value": "pk_live_🔑 Your production publishable key",
            "description": "Stripe production publishable key (NOT test key)"
        },
        "STRIPE_WEBHOOK_SECRET": {
            "value": "whsec_🔑 Your webhook secret",
            "description": "Stripe webhook signing secret"
        },
        
        # Optional
        "GEMINI_API_KEY": {
            "value": "your-gemini-api-key",
            "description": "Google Gemini API key (optional)"
        },
    }
    
    return env_vars

def print_setup_guide():
    """Print the complete setup guide"""
    
    guide = """
╔═════════════════════════════════════════════════════════════════════════════╗
║          MEDTAG BACKEND - VERCEL ENVIRONMENT VARIABLES SETUP               ║
║                          For: ahsnafzal                                    ║
╚═════════════════════════════════════════════════════════════════════════════╝


📋 STEP 1: GENERATE NEW SECRET_KEY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open a terminal and run:

    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

Copy the output and save it. This is your SECRET_KEY.

Example output:
    h)o#z6i=-w!j0_9$%&*-k@!x+z-9h#5%^&*-k@!x+z


📋 STEP 2: CREATE VERCEL POSTGRES DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://vercel.com/dashboard
2. Click: Storage → Create → Postgres
3. Name: medtag-db
4. Select your region
5. Click: Create

You'll see:
    DB_NAME: verceldb_xxxxx
    DB_USER: default
    DB_PASSWORD: [random password]
    DB_HOST: ep-xxxxx.postgres.vercel-storage.com
    DB_PORT: 5432

Copy all these values - you'll need them.


📋 STEP 3: CREATE AWS S3 BUCKET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://console.aws.amazon.com
2. Search: S3 → Click S3
3. Click: Create Bucket
4. Bucket Name: medtag-backend (or your name)
5. Region: eu-north-1 (MUST match your .env)
6. Uncheck: "Block all public access"
7. Check: "I acknowledge that this bucket will be public"
8. Click: Create Bucket

Then:
1. Go to: IAM → Users → Create User
2. Name: medtag-backend
3. Click: Create
4. Go to: Security Credentials → Create Access Key
5. Copy: Access Key ID and Secret Access Key

Save all these values.


📋 STEP 4: GENERATE GMAIL APP PASSWORD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://myaccount.google.com/apppasswords
2. Select: Mail
3. Select: Windows Computer (or your OS)
4. Click: Generate
5. Copy the 16-character password

This is your EMAIL_HOST_PASSWORD (not your Gmail password!)


📋 STEP 5: GET STRIPE PRODUCTION KEYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://dashboard.stripe.com
2. Click: Developers → API Keys
3. Toggle: "Show test data" (turn OFF for production keys)
4. Copy: Secret key (starts with sk_live_)
5. Copy: Publishable key (starts with pk_live_)
6. Go to: Webhooks
7. Copy: Webhook signing secret (starts with whsec_)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 READY TO DEPLOY? FOLLOW THESE STEPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://vercel.com/new?teamSlug=ahsan-afzal

2. Click: "Import Git Repository"

3. Select: medtag-backend (your GitHub repo)

4. Configure Build Settings:
   
   Build Command:
   ┌─────────────────────────────────────────────────────────────┐
   │ pip install -r requirements.txt && python manage.py migrate │
   │ && python manage.py collectstatic --noinput                 │
   └─────────────────────────────────────────────────────────────┘
   
   Output Directory: staticfiles
   
   Install Command: pip install -r requirements.txt

5. Click: "Environment Variables"

6. Add ALL these variables (copy from the list below):

COPY & PASTE THESE INTO VERCEL ENVIRONMENT VARIABLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


CRITICAL VARIABLES (Must fill in):
──────────────────────────────────────────────────────────────────────────

Name: ENVIRONMENT
Value: production

Name: SECRET_KEY
Value: [Your generated SECRET_KEY from Step 1]

Name: DEBUG
Value: False

Name: ALLOWED_HOSTS
Value: yourdomain.vercel.app,yourdomain.com


DATABASE VARIABLES (From Vercel Postgres):
──────────────────────────────────────────────────────────────────────────

Name: DB_NAME
Value: [From Vercel Postgres]

Name: DB_USER
Value: default

Name: DB_PASSWORD
Value: [From Vercel Postgres]

Name: DB_HOST
Value: [From Vercel Postgres]

Name: DB_PORT
Value: 5432


FRONTEND VARIABLES:
──────────────────────────────────────────────────────────────────────────

Name: CORS_ALLOWED_ORIGINS
Value: https://yourdomain.com

Name: REACTAPP_RESET_URL
Value: https://yourdomain.com/reset-password/

Name: LOGIN_URI
Value: https://yourdomain.com/login

Name: PUBLIC_BASE_URL
Value: https://yourdomain.vercel.app


EMAIL VARIABLES (Gmail):
──────────────────────────────────────────────────────────────────────────

Name: EMAIL_HOST
Value: smtp.gmail.com

Name: EMAIL_PORT
Value: 587

Name: EMAIL_USE_TLS
Value: True

Name: EMAIL_HOST_USER
Value: your-email@gmail.com

Name: EMAIL_HOST_PASSWORD
Value: [Gmail App Password from Step 4 - 16 characters]


AWS S3 VARIABLES (New Credentials):
──────────────────────────────────────────────────────────────────────────

Name: USE_S3
Value: True

Name: AWS_ACCESS_KEY_ID
Value: [New Access Key from Step 3]

Name: AWS_SECRET_ACCESS_KEY
Value: [New Secret Key from Step 3]

Name: AWS_STORAGE_BUCKET_NAME
Value: [Your bucket name]

Name: AWS_S3_REGION_NAME
Value: eu-north-1


STRIPE VARIABLES (Production - sk_live_):
──────────────────────────────────────────────────────────────────────────

Name: STRIPE_SECRET_KEY
Value: sk_live_[Your production key from Step 5]

Name: STRIPE_PUBLISHABLE_KEY
Value: pk_live_[Your production key from Step 5]

Name: STRIPE_WEBHOOK_SECRET
Value: whsec_[Your webhook secret from Step 5]


OPTIONAL:
──────────────────────────────────────────────────────────────────────────

Name: GEMINI_API_KEY
Value: [Your API key if using Gemini]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7. After adding ALL environment variables, click: "Deploy"

8. Wait for build to complete (5-10 minutes)

9. Check "Build Logs" for any errors

10. Once deployed, you'll get a live URL like:
    https://medtag-backend-xyz.vercel.app


✅ AFTER DEPLOYMENT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test your API:

1. Health Check:
   curl https://medtag-backend-xyz.vercel.app/api/health/

2. Authentication:
   curl -X POST https://medtag-backend-xyz.vercel.app/api/auth/login/ \\
     -H "Content-Type: application/json"

3. Static Files:
   curl https://medtag-backend-xyz.vercel.app/static/admin/css/base.css

4. Check Logs:
   Vercel Dashboard → Deployments → Your deployment → Logs


⚠️ TROUBLESHOOTING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: Build fails
→ Check build logs for specific error
→ Common: Missing package in requirements.txt

Issue: 404 on static files
→ Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
→ Check S3 bucket exists and is public-read

Issue: Database connection error
→ Verify DB_HOST from Vercel Postgres
→ Check DB_PASSWORD is correct

Issue: CORS errors
→ Add your frontend domain to CORS_ALLOWED_ORIGINS
→ Make sure https:// prefix is included

Issue: Email not sending
→ Use Gmail App Password (16 chars), NOT main Gmail password
→ Check email address in EMAIL_HOST_USER


═════════════════════════════════════════════════════════════════════════════

Need help?
- VERCEL_DEPLOYMENT_GUIDE.md (Detailed guide)
- PRE_DEPLOYMENT_CHECKLIST.md (Checklist & troubleshooting)
- SECURITY_NOTICE.md (Credential rotation details)

Your backend is production-ready!
Time to deploy: ~60 minutes

═════════════════════════════════════════════════════════════════════════════
"""
    print(guide)

if __name__ == "__main__":
    print_setup_guide()
