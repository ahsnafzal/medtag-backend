# 📋 Pre-Deployment Checklist for Vercel

## Phase 1: Security & Credentials (CRITICAL) ✋

Before deploying, you MUST complete these items:

### Credential Rotation
- [ ] AWS IAM Access Key ID & Secret Key **REGENERATED** and old keys deleted
  - Regenerate in AWS Console: IAM → Users → Create new access keys
  - Delete old credentials
- [ ] Stripe API Keys **ROTATED** (use new sk_live and pk_live keys for production)
  - Go to Stripe Dashboard → Developers → API Keys → Rotate
- [ ] Email password **UPDATED** (Use Gmail App Password, not main password)
  - Generate at: https://myaccount.google.com/apppasswords
- [ ] Database password **CHANGED**
  - Create new Vercel Postgres database with new password
- [ ] SECRET_KEY **GENERATED** - Use a new, strong secret key
  - Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### Code Security
- [ ] No hardcoded credentials in any Python files ✓ (Already fixed)
- [ ] No API keys in comments ✓ (Already fixed)
- [ ] DEBUG = False in production environment ✓ (Already fixed)
- [ ] ALLOWED_HOSTS configured correctly ✓ (Already fixed)
- [ ] CORS properly restricted ✓ (Already fixed)
- [ ] .env file NOT committed to Git
  ```bash
  git log --all --oneline --full-history -- .env  # Check history
  ```

### Repository Cleanup
- [ ] `.env` removed from Git history (if previously committed)
  ```bash
  git rm --cached .env
  git commit -m "Remove .env file from version control"
  ```
- [ ] `.gitignore` includes `.env` and `.env.*` ✓ (Already updated)
- [ ] `.env.example` committed with placeholder values ✓ (Already created)
- [ ] No other secret files in repository
  - No private keys (SSH, TLS)
  - No database dumps with real data
  - No API keys in config files

---

## Phase 2: Code & Configuration

### Django Settings
- [ ] `settings.py` uses environment variables for all configuration ✓ (Already fixed)
- [ ] Production database configuration correct
  - [ ] DB_HOST, DB_USER, DB_PASSWORD from Vercel Postgres
  - [ ] DB_PORT = 5432
  - [ ] SSL Mode enabled (sslmode=require)
- [ ] S3/AWS configuration correct
  - [ ] USE_S3 = True in production
  - [ ] AWS bucket is publicly readable (public-read ACL)
  - [ ] CORS configured on S3 bucket (allow all origins for your API domain)
- [ ] Email configuration correct
  - [ ] EMAIL_HOST_USER & EMAIL_HOST_PASSWORD from environment
  - [ ] SMTP port = 587 with TLS

### Static & Media Files
- [ ] Static files configuration ✓ (Already fixed)
  - [ ] STATIC_URL points to S3 CDN
  - [ ] STATIC_ROOT = staticfiles/
  - [ ] WhiteNoise middleware installed ✓
- [ ] Media files configuration ✓ (Already fixed)
  - [ ] DEFAULT_FILE_STORAGE uses S3 in production
  - [ ] MEDIA_URL points to S3 CDN
- [ ] Required packages in requirements.txt ✓
  - [ ] gunicorn
  - [ ] whitenoise
  - [ ] django-storages
  - [ ] boto3

### Database & Migrations
- [ ] All migrations committed to Git
  ```bash
  git status migrations/  # Should show no pending changes
  ```
- [ ] No pending migrations
  ```bash
  python manage.py migrate --dry-run  # Should show no changes
  ```
- [ ] Database can be initialized from migrations
  ```bash
  python manage.py migrate --plan  # Review migration plan
  ```

### API Endpoints
- [ ] Health check endpoint accessible
  ```bash
  python manage.py runserver
  # Test: curl http://localhost:8000/api/health/
  ```
- [ ] Authentication endpoints working
  ```bash
  # Test login endpoint locally
  curl -X POST http://localhost:8000/api/auth/login/ \
    -H "Content-Type: application/json"
  ```
- [ ] CORS headers present in responses
  - Access-Control-Allow-Origin should appear
  - Access-Control-Allow-Methods should include GET, POST, etc.

---

## Phase 3: Vercel Configuration

### Vercel Project Setup
- [ ] Project connected to GitHub repository
- [ ] Build command configured:
  ```
  pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
  ```
- [ ] Output directory set to: `staticfiles`
- [ ] Environment variables added in Vercel:

#### Required Environment Variables
```
✓ ENVIRONMENT=production
✓ SECRET_KEY=<your-new-secret>
✓ DEBUG=False
✓ ALLOWED_HOSTS=yourdomain.com,yourdomain.vercel.app

✓ DB_NAME=<from-vercel-postgres>
✓ DB_USER=<from-vercel-postgres>
✓ DB_PASSWORD=<from-vercel-postgres>
✓ DB_HOST=<from-vercel-postgres>
✓ DB_PORT=5432

✓ CORS_ALLOWED_ORIGINS=https://yourdomain.com

✓ EMAIL_HOST_USER=<new-email>
✓ EMAIL_HOST_PASSWORD=<new-app-password>

✓ USE_S3=True
✓ AWS_ACCESS_KEY_ID=<new-key>
✓ AWS_SECRET_ACCESS_KEY=<new-secret>
✓ AWS_STORAGE_BUCKET_NAME=<bucket-name>
✓ AWS_S3_REGION_NAME=eu-north-1

✓ STRIPE_SECRET_KEY=sk_live_<production-key>
✓ STRIPE_PUBLISHABLE_KEY=pk_live_<production-key>
✓ STRIPE_WEBHOOK_SECRET=whsec_<webhook-secret>

✓ REACTAPP_RESET_URL=https://yourdomain.com/reset-password/
✓ LOGIN_URI=https://yourdomain.com/login
✓ PUBLIC_BASE_URL=https://yourdomain.vercel.app

✓ GEMINI_API_KEY=<your-api-key>
```

### Files Created ✓
- [ ] `vercel.json` ✓
- [ ] `.env.example` ✓
- [ ] `build.sh` ✓
- [ ] `VERCEL_DEPLOYMENT_GUIDE.md` ✓
- [ ] `SECURITY_NOTICE.md` ✓
- [ ] `PRE_DEPLOYMENT_CHECKLIST.md` (this file) ✓

---

## Phase 4: Testing Before Deployment

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Test with production settings
export ENVIRONMENT=production
export SECRET_KEY=test-secret-key
export DEBUG=False
export ALLOWED_HOSTS=localhost,127.0.0.1

python manage.py runserver
```

- [ ] Local server starts without errors
- [ ] Static files served correctly (check /static/)
- [ ] API endpoints respond correctly
- [ ] No missing imports or ModuleNotFoundErrors

### Production Simulation
```bash
# Test with gunicorn (production server)
gunicorn med_backend.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 60
```

- [ ] Application runs with gunicorn
- [ ] No errors in WSGI configuration
- [ ] Response times acceptable

---

## Phase 5: Vercel Deployment

### Pre-Deployment
- [ ] All changes committed to Git
- [ ] Latest code pushed to main/master branch
- [ ] GitHub repository is connected to Vercel

### Deploy
- [ ] Click "Deploy" in Vercel Dashboard
- [ ] Monitor build logs for errors
- [ ] Wait for build to complete

### Post-Deployment Validation
- [ ] Build completed successfully
- [ ] Check Vercel build logs (no errors or warnings)
- [ ] Test live endpoints:

```bash
# Test health check
curl https://yourdomain.vercel.app/api/health/

# Test CORS headers
curl -i https://yourdomain.vercel.app/api/health/
# Should see: Access-Control-Allow-Origin header

# Test static files
curl https://yourdomain.vercel.app/static/admin/css/base.css
# Should return CSS content, not 404

# Test media files
curl https://yourdomain.s3.region.amazonaws.com/media/
# Should list S3 bucket contents or return appropriate response
```

### API Functionality
- [ ] Login endpoint works
- [ ] Authentication tokens generate
- [ ] Protected endpoints require valid token
- [ ] File uploads save to S3
- [ ] Email sending works (check spam folder)
- [ ] Payment processing works (test with Stripe test card)

### Monitoring
- [ ] Check Vercel Analytics for performance
- [ ] Check Vercel Logs for any errors
- [ ] Monitor database queries (no N+1 problems)
- [ ] Check S3 CloudWatch metrics

---

## Phase 6: Post-Deployment (First 24 Hours)

### Monitoring
- [ ] Check deployment logs every 1-2 hours
- [ ] Monitor application for errors
- [ ] Verify all integrations working (Stripe, Email, AWS)
- [ ] Check database connection stability

### User Validation
- [ ] Have test users try the application
- [ ] Verify authentication flows work
- [ ] Test file uploads and downloads
- [ ] Test payment processing
- [ ] Check that password resets send emails

### Security Verification
- [ ] HTTPS enforced (no mixed content warnings)
- [ ] Security headers present:
  ```
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Strict-Transport-Security (HSTS)
  ```
- [ ] No DEBUG information leaking in error pages
- [ ] API doesn't expose sensitive data

### Performance
- [ ] Page load times acceptable
- [ ] No 500 errors in logs
- [ ] Database queries optimized
- [ ] Static files cached properly (long Cache-Control headers)

---

## Troubleshooting

### Common Issues

**Build fails with "ModuleNotFoundError"**
- Solution: Add missing package to requirements.txt
- Rebuild and redeploy

**Database connection timeout**
- Solution: Verify DB_HOST is correct Vercel Postgres URL
- Check SSL mode is enabled in connection string

**Static files return 404**
- Solution: Run `python manage.py collectstatic --noinput` locally
- Verify S3 credentials are correct
- Check S3 bucket permissions

**CORS errors**
- Solution: Verify CORS_ALLOWED_ORIGINS in Vercel env vars
- Check your frontend URL is included
- Restart deployment

**Emails not sending**
- Solution: Verify EMAIL_HOST_PASSWORD is App Password (not main Gmail password)
- Check Gmail account for "Less secure apps" is disabled (use App Passwords instead)
- Verify email address in SMTP settings

**Migrations not running**
- Solution: Check build logs for migration errors
- Verify database connection is working
- Check for migration conflicts or circular imports

---

## Rollback Plan

If deployment fails:

```bash
# Option 1: Revert to previous deployment
vercel rollback

# Option 2: Redeploy from specific commit
git revert <bad-commit-hash>
git push
# Vercel auto-triggers new deployment

# Option 3: Manual redeploy
vercel --prod
```

---

## Sign-Off

Once everything is verified working, you can mark this checklist as complete:

- Date Deployed: _______________
- Deployed By: _______________
- All Tests Passed: ✓ Yes ☐ No
- Production URL: https://_______________

---

**Keep this checklist for future deployments!**
