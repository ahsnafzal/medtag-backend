#!/usr/bin/env python3
"""
MedTag Backend - Vercel Deployment Helper
This script helps you set up environment variables for Vercel deployment
"""

import json
import os
from pathlib import Path

def generate_env_template():
    """Generate the environment variables template for Vercel"""
    
    env_vars = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "🔑 GENERATE NEW: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\"",
        "DEBUG": "False",
        "ALLOWED_HOSTS": "yourdomain.vercel.app,yourdomain.com",
        
        # Database (Vercel Postgres)
        "DB_NAME": "verceldb_xxxxx",
        "DB_USER": "default",
        "DB_PASSWORD": "🔑 From Vercel Postgres dashboard",
        "DB_HOST": "ep-xxxxx.us-east-1.postgres.vercel-storage.com",
        "DB_PORT": "5432",
        
        # Frontend
        "CORS_ALLOWED_ORIGINS": "https://yourdomain.com",
        "REACTAPP_RESET_URL": "https://yourdomain.com/reset-password/",
        "LOGIN_URI": "https://yourdomain.com/login",
        "PUBLIC_BASE_URL": "https://yourdomain.vercel.app",
        
        # Email
        "EMAIL_HOST": "smtp.gmail.com",
        "EMAIL_PORT": "587",
        "EMAIL_USE_TLS": "True",
        "EMAIL_HOST_USER": "🔑 Your email",
        "EMAIL_HOST_PASSWORD": "🔑 Your Gmail App Password",
        
        # AWS S3
        "USE_S3": "True",
        "AWS_ACCESS_KEY_ID": "🔑 New AWS access key",
        "AWS_SECRET_ACCESS_KEY": "🔑 New AWS secret key",
        "AWS_STORAGE_BUCKET_NAME": "your-bucket-name",
        "AWS_S3_REGION_NAME": "eu-north-1",
        
        # Stripe
        "STRIPE_SECRET_KEY": "sk_live_🔑 Production key",
        "STRIPE_PUBLISHABLE_KEY": "pk_live_🔑 Production key",
        "STRIPE_WEBHOOK_SECRET": "whsec_🔑 Webhook secret",
        
        # Optional
        "GEMINI_API_KEY": "🔑 Your Gemini API key",
    }
    
    return env_vars

def print_deployment_instructions():
    """Print step-by-step deployment instructions"""
    
    instructions = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   MEDTAG BACKEND - VERCEL DEPLOYMENT GUIDE                   ║
║                      For: ahsnafzal (Your Vercel Account)                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 STEP 1: PRE-DEPLOYMENT CHECKLIST (Do This First!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECURITY - Rotate These Credentials:
□ AWS Access Key ID (old key exposed; rotate it)
  → Go to: AWS Console → IAM → Users → Create New Access Keys
  → Delete old keys
  
□ Stripe API Keys (use production sk_live_*, not test keys)
  → Go to: Stripe Dashboard → Developers → API Keys → Rotate
  
□ Gmail App Password (generate new one)
  → Go to: https://myaccount.google.com/apppasswords
  → Select "Mail" and "Windows Computer"
  
□ Database Password (will be provided by Vercel Postgres)
  → Create new Vercel Postgres database

□ Generate New SECRET_KEY
  → Run: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  → Save this key (you'll need it for Vercel)

INFRASTRUCTURE:
□ Create Vercel Postgres Database
  → Vercel Dashboard → Storage → Postgres → Create
  → Note down: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
  
□ Create S3 Bucket (for media files)
  → AWS Console → S3 → Create Bucket
  → Region: eu-north-1 (same as in .env)
  → Note down: Bucket name, Access Key, Secret Key
  
□ Generate Gmail App Password
  → https://myaccount.google.com/apppasswords
  → Generate and save the password


📋 STEP 2: VERCEL SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://vercel.com/new
   Or your direct link: https://vercel.com/new?teamSlug=ahsan-afzal

2. Click "Import Git Repository"

3. Select your GitHub repository (medtag-backend)
   → If not shown, connect your GitHub account first
   → Click "Install" if needed
   → Select: medtag-backend

4. Configure Build Settings:
   ✓ Build Command:
     pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
   
   ✓ Output Directory: staticfiles
   
   ✓ Install Command: pip install -r requirements.txt
   
   ✓ Root Directory: . (default)

5. Click "Environment Variables" and add ALL variables below:


📋 STEP 3: ADD ENVIRONMENT VARIABLES TO VERCEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In Vercel Console → Environment Variables, add these:

CORE SETTINGS:
Name: ENVIRONMENT          | Value: production
Name: SECRET_KEY           | Value: [Your new generated SECRET_KEY]
Name: DEBUG                | Value: False
Name: ALLOWED_HOSTS        | Value: yourdomain.vercel.app,yourdomain.com

DATABASE (from Vercel Postgres):
Name: DB_NAME              | Value: [from Vercel Postgres]
Name: DB_USER              | Value: default
Name: DB_PASSWORD          | Value: [from Vercel Postgres]
Name: DB_HOST              | Value: [from Vercel Postgres]
Name: DB_PORT              | Value: 5432

FRONTEND:
Name: CORS_ALLOWED_ORIGINS | Value: https://yourdomain.com
Name: REACTAPP_RESET_URL   | Value: https://yourdomain.com/reset-password/
Name: LOGIN_URI            | Value: https://yourdomain.com/login
Name: PUBLIC_BASE_URL      | Value: https://yourdomain.vercel.app

EMAIL:
Name: EMAIL_HOST           | Value: smtp.gmail.com
Name: EMAIL_PORT           | Value: 587
Name: EMAIL_USE_TLS        | Value: True
Name: EMAIL_HOST_USER      | Value: [your-email@gmail.com]
Name: EMAIL_HOST_PASSWORD  | Value: [Gmail App Password]

AWS S3:
Name: USE_S3               | Value: True
Name: AWS_ACCESS_KEY_ID    | Value: [New AWS Access Key]
Name: AWS_SECRET_ACCESS_KEY| Value: [New AWS Secret Key]
Name: AWS_STORAGE_BUCKET_NAME | Value: [your-bucket-name]
Name: AWS_S3_REGION_NAME   | Value: eu-north-1

STRIPE (Production):
Name: STRIPE_SECRET_KEY    | Value: sk_live_[production key]
Name: STRIPE_PUBLISHABLE_KEY | Value: pk_live_[production key]
Name: STRIPE_WEBHOOK_SECRET| Value: whsec_[webhook secret]

OPTIONAL:
Name: GEMINI_API_KEY       | Value: [your API key]


📋 STEP 4: DEPLOY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After adding all environment variables:

1. Click "Deploy" button
2. Wait for build to complete (5-10 minutes)
3. Check "Build Logs" for any errors
4. Once deployed, you'll see: "Congratulations! Your project is deployed"


📋 STEP 5: POST-DEPLOYMENT VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After deployment succeeds:

□ Test Health Endpoint:
  curl https://yourdomain.vercel.app/api/health/

□ Check Static Files:
  Visit: https://yourdomain.vercel.app/static/admin/css/base.css
  Should NOT return 404

□ Check Logs:
  Vercel Dashboard → Your Project → Deployments → Latest → Logs
  Should show: "Successfully ran migrations" (if any migrations pending)

□ Test Authentication:
  POST https://yourdomain.vercel.app/api/auth/login/
  Should return proper JSON response (not error page)

□ Test CORS:
  From your frontend, try an API call
  Should see: Access-Control-Allow-Origin header in response

□ Monitor for 24 Hours:
  Check logs for errors
  Test file uploads
  Test email sending
  Test payment processing


🎯 COMMON ISSUES & SOLUTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: Build fails with "ModuleNotFoundError"
Solution: 
  - Check requirements.txt has all packages
  - Rebuild and redeploy

Issue: Database connection timeout
Solution:
  - Verify DB_HOST includes full Vercel Postgres URL
  - Ensure sslmode=require is set
  - Check DB credentials in Vercel environment

Issue: Static files return 404
Solution:
  - Run locally: python manage.py collectstatic --noinput
  - Verify S3 credentials are correct
  - Check bucket exists and is public-read

Issue: CORS errors from frontend
Solution:
  - Verify CORS_ALLOWED_ORIGINS in Vercel env
  - Include your frontend domain (https://yourdomain.com)
  - Don't use wildcard (*)

Issue: Email not sending
Solution:
  - Verify EMAIL_HOST_PASSWORD is Gmail App Password (not main password)
  - Check Gmail allows "Less Secure Apps" OR use App Password
  - Test with: python manage.py shell → from django.core.mail import send_mail

Issue: Migrations not running
Solution:
  - Check build logs for migration errors
  - Verify database connection is working
  - Look for migration conflicts


📊 PROJECT STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Django Settings:      ✅ Production Ready
Security Headers:     ✅ Configured
Static Files:         ✅ WhiteNoise + S3
Media Files:          ✅ S3/AWS Integration
Database:             ✅ PostgreSQL Ready
Email:                ✅ SMTP Configured
Payments:             ✅ Stripe + JazzCash
WebSockets:           ✅ Fallback Configured
Vercel Config:        ✅ vercel.json Ready
Build Scripts:        ✅ build.sh Ready
Documentation:        ✅ Complete

DEPLOYMENT STATUS:    🟢 READY TO DEPLOY


🔗 USEFUL LINKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Vercel New Project:        https://vercel.com/new?teamSlug=ahsan-afzal
Vercel Dashboard:          https://vercel.com/dashboard
Vercel Postgres:           https://vercel.com/storage/postgres
AWS Console:               https://console.aws.amazon.com
Gmail App Passwords:       https://myaccount.google.com/apppasswords
Stripe Dashboard:          https://dashboard.stripe.com
Django Deployment Check:   python manage.py check --deploy


📞 SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Documentation Files in Your Project:
- DEPLOYMENT_SUMMARY.md           (Quick reference)
- SECURITY_NOTICE.md              (Credential details)
- VERCEL_DEPLOYMENT_GUIDE.md      (Detailed guide)
- PRE_DEPLOYMENT_CHECKLIST.md     (Pre-flight checklist)
- PRODUCTION_READY_ANALYSIS.md    (Technical details)


═══════════════════════════════════════════════════════════════════════════════

⏱️  ESTIMATED TIME: ~60 minutes
    - Credential rotation: 20 min
    - Infrastructure setup: 20 min
    - Environment variables: 10 min
    - Deployment & testing: 10 min

🎯 Next Step: Start with "PRE-DEPLOYMENT CHECKLIST" section above ↑

═══════════════════════════════════════════════════════════════════════════════
"""
    print(instructions)

if __name__ == "__main__":
    print_deployment_instructions()
