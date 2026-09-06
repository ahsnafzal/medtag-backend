# 🚀 Vercel Deployment Guide for MedTag Backend

## Overview

This guide will walk you through deploying your Django MedTag backend to Vercel. The application is now production-ready with all necessary security configurations and optimizations.

## Prerequisites

Before you start, make sure you have:

1. ✅ Vercel account (https://vercel.com)
2. ✅ Git repository pushed to GitHub (https://github.com)
3. ✅ Rotated all credentials (AWS, Stripe, etc.) - **CRITICAL**
4. ✅ Created a PostgreSQL database (Vercel Postgres or external provider)
5. ✅ AWS S3 bucket for media file storage
6. ✅ Stripe account configured
7. ✅ Email service configured (Gmail App Password)

## Step 1: Prepare Your Repository

### 1.1 Verify .env is ignored
```bash
# Make sure .env is in .gitignore
cat .gitignore | grep "\.env"

# If .env was previously committed, remove it
git rm --cached .env
git commit -m "Remove .env file from version control"
git push
```

### 1.2 Ensure all files are updated
```bash
# Check that all production files exist
ls -la vercel.json          # Should exist
ls -la .env.example         # Should exist
ls -la SECURITY_NOTICE.md   # Should exist
ls -la build.sh             # Should exist
```

## Step 2: Set Up Vercel PostgreSQL Database

### 2.1 Create Vercel Postgres Database
1. Go to Vercel Dashboard → Storage → Create → Postgres
2. Choose your project region
3. Note down the connection string

### 2.2 Get connection credentials
```
Database URL format:
postgresql://[user]:[password]@[host]:[port]/[database]?sslmode=require
```

Extract:
- DB_HOST
- DB_PORT
- DB_USER
- DB_PASSWORD
- DB_NAME

## Step 3: Deploy to Vercel

### 3.1 Connect your GitHub repository
1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repository
4. Vercel will detect it's a Python/Django project

### 3.2 Configure build and output settings
**Build Command:**
```
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
```

**Output Directory:**
```
staticfiles
```

**Install Command:**
```
pip install -r requirements.txt
```

### 3.3 Add Environment Variables

Click "Environment Variables" and add ALL variables from your `.env` file:

```
ENVIRONMENT=production
SECRET_KEY=your-new-production-secret-key (generate a new one!)
DEBUG=False
ALLOWED_HOSTS=yourdomain.vercel.app,yourdomain.com

DB_NAME=verceldb_xxxxx (from Vercel Postgres)
DB_USER=default (from Vercel Postgres)
DB_PASSWORD=your-password (from Vercel Postgres)
DB_HOST=ep-xxxxx.us-east-1.postgres.vercel-storage.com
DB_PORT=5432

CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://yourdomain.vercel.app

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-new-app-password (from Gmail)

USE_S3=True
AWS_ACCESS_KEY_ID=your-new-aws-key
AWS_SECRET_ACCESS_KEY=your-new-aws-secret
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=eu-north-1

STRIPE_SECRET_KEY=sk_live_your-production-key
STRIPE_PUBLISHABLE_KEY=pk_live_your-production-key
STRIPE_WEBHOOK_SECRET=whsec_your-production-webhook

REACTAPP_RESET_URL=https://yourdomain.com/reset-password/
LOGIN_URI=https://yourdomain.com/login
PUBLIC_BASE_URL=https://yourdomain.vercel.app

GEMINI_API_KEY=your-api-key
```

⚠️ **Important**: Use different API keys for production (sk_live for Stripe, not sk_test)

### 3.4 Deploy

Click "Deploy" and wait for the build to complete.

## Step 4: Verify Deployment

### 4.1 Check deployment logs
1. Go to Vercel Dashboard → Your Project → Deployments
2. Click on the latest deployment
3. Check "Build Logs" for any errors

### 4.2 Test API endpoints
```bash
# Test health check
curl https://yourdomain.vercel.app/api/health/

# Test authentication endpoints
curl https://yourdomain.vercel.app/api/auth/login/
```

### 4.3 Check static files
- CSS/JS should load from S3 CDN
- Images should load from S3

### 4.4 Test database connection
```bash
# Create a superuser via Vercel CLI
vercel env pull
python manage.py createsuperuser
```

## Step 5: Configure Custom Domain (Optional)

1. Go to Vercel Dashboard → Your Project → Domains
2. Add your custom domain
3. Update DNS records as instructed by Vercel
4. Wait for SSL certificate to be generated (~24 hours)

## Step 6: Post-Deployment Checklist

- ✅ Health check endpoint responds
- ✅ API endpoints working
- ✅ Static files served (CSS, JS, images)
- ✅ Media files upload to S3
- ✅ Email sending works
- ✅ Payment gateway working (Stripe/JazzCash)
- ✅ Database migrations completed
- ✅ No DEBUG messages in console logs
- ✅ HTTPS is enforced
- ✅ CORS working with frontend

## Common Issues & Solutions

### Issue 1: "ModuleNotFoundError" during build
**Solution**: Make sure all dependencies are in `requirements.txt`
```bash
pip freeze > requirements.txt
git add requirements.txt
git push
```

### Issue 2: Database connection timeout
**Solution**: Check that DB_HOST includes the full Vercel Postgres URL with port 5432

### Issue 3: Static files not found (404 on CSS/JS)
**Solution**: Ensure S3 is configured correctly
```bash
# Run locally to test
python manage.py collectstatic --noinput
```

### Issue 4: Email not sending
**Solution**: Verify EMAIL_HOST_PASSWORD is an App Password (not your main Gmail password)
- Generate App Password: https://myaccount.google.com/apppasswords

### Issue 5: CORS errors from frontend
**Solution**: Check CORS_ALLOWED_ORIGINS in Vercel environment variables
- Make sure your frontend URL is included
- Don't use wildcard (*) in production

## Monitoring & Maintenance

### Enable Error Tracking
Add this to your project for better error monitoring:
```bash
pip install sentry-sdk
```

### Monitor Database
1. Go to Vercel Dashboard → Storage → Your Database
2. Check "Usage" for performance metrics
3. Review "Logs" for any connection issues

### View Logs
```bash
# Stream logs from Vercel
vercel logs --follow
```

## Rollback Plan

If something goes wrong:
```bash
# Revert to previous deployment
vercel rollback

# Or redeploy from a specific commit
git checkout <commit-hash>
git push
```

## Support Resources

- [Vercel Django Documentation](https://vercel.com/guides/deploying-django-to-vercel)
- [Vercel Postgres Documentation](https://vercel.com/docs/storage/vercel-postgres)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [AWS S3 Django Setup](https://django-storages.readthedocs.io/en/latest/)

---

**Last Updated**: 2024
**Status**: Production Ready
