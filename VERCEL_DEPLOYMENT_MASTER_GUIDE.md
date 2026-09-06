# 🚀 MedTag Backend - Vercel Deployment Master Guide

**For User**: ahsnafzal  
**Project**: MedTag Backend  
**Status**: ✅ Ready to Deploy  
**Estimated Time**: 40 minutes (WITHOUT AWS)

---

## 📍 Your Deployment Journey

This is YOUR personalized deployment guide. Follow these steps in order.

### ⏰ Timeline (WITHOUT AWS)
- Step 1-2: Generate Credentials (15 min)
- Step 3-4: Setup Gmail & Stripe (10 min)
- Step 5-6: Deploy to Vercel (15 min)
- Step 7: Verify (5 min)

---

## 🔴 STEP 1: Generate Secret Key (5 minutes)

**What to do:**
Open Terminal/PowerShell and run:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Expected output:**
```
h)o#z6i=-w!j0_9$%&*-k@!x+z-9h#5%^&*-k@!x+z
```

✅ **Save this SECRET_KEY somewhere safe!** (You'll need it for Vercel)

---

## 🔴 STEP 2: Get Vercel Postgres Database (7 minutes)

**What to do:**

1. Go to: **https://vercel.com/dashboard**
2. Click: **Storage** → **Create** → **Postgres**
3. Enter name: `medtag-db`
4. Select your region
5. Click: **Create**

**You'll see:**
```
Database URL: postgresql://[user]:[password]@[host]:[port]/[database]?sslmode=require
```

Extract and save:
- `DB_NAME`: verceldb_xxxxx
- `DB_USER`: default
- `DB_PASSWORD`: [random password]
- `DB_HOST`: ep-xxxxx.postgres.vercel-storage.com
- `DB_PORT`: 5432

✅ **Copy all 5 values - you need them for Vercel environment variables!**

---

## 🟡 STEP 3: File Storage Setup (2 minutes) ✅ NO AWS NEEDED

Good news! You don't need AWS for this deployment! 

**Here's why you can skip AWS:**
- ✅ Vercel works perfectly with local file storage
- ✅ Your Django app is configured to work without AWS
- ✅ No bank card required!
- ✅ You can always add AWS S3 later if you want CDN

**What happens without AWS:**
- Files are stored locally on Vercel
- They work just fine for normal usage
- Upgrade to S3 anytime in the future

**No action needed for this step!** Continue to Step 4.

---

## 🟡 STEP 4: Generate Gmail App Password (2 minutes)

1. Go to: **https://myaccount.google.com/apppasswords**
2. Select: **Mail**
3. Select: **Windows Computer** (or your OS)
4. Click: **Generate**

You'll see a 16-character password:
```
hrcm yqgq ynwq bhnb
```

✅ **Copy this password (it's your EMAIL_HOST_PASSWORD)**

---

## 🟡 STEP 5: Get Stripe Production Keys (3 minutes)

1. Go to: **https://dashboard.stripe.com**
2. Click: **Developers** → **API Keys**
3. Toggle OFF: "Show test data" (to see production keys)

You'll see:
```
Secret key: sk_live_...
Publishable key: pk_live_...
```

✅ **Copy both**

Then:
1. Click: **Webhooks**
2. Find your webhook
3. Click it and copy: **Signing secret** (starts with whsec_)

✅ **Copy the webhook secret**

---

## 🟢 STEP 6: Connect Repository to Vercel (5 minutes)

**What to do:**

1. Go to: **https://vercel.com/new?teamSlug=ahsan-afzal**
2. Click: **Import Git Repository**
3. Search & Select: **medtag-backend**
4. Click: **Import**

**Configure build settings:**

- Build Command:
  ```
  pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
  ```

- Output Directory: `staticfiles`

- Install Command: `pip install -r requirements.txt`

✅ **Settings configured!**

---

## 🟢 STEP 7: Add Environment Variables to Vercel (10 minutes)

**What to do:**

1. In the Vercel import screen, click: **Environment Variables**
2. Add EACH variable below by:
   - Entering Name
   - Entering Value
   - Clicking Add

### Copy & Paste These Exact Variables:

**CORE SETTINGS:**
```
ENVIRONMENT = production
SECRET_KEY = [Your generated key from STEP 1]
DEBUG = False
ALLOWED_HOSTS = yourdomain.vercel.app,yourdomain.com
```

**DATABASE (from STEP 2):**
```
DB_NAME = [from Vercel Postgres]
DB_USER = default
DB_PASSWORD = [from Vercel Postgres]
DB_HOST = [from Vercel Postgres]
DB_PORT = 5432
```

**FRONTEND:**
```
CORS_ALLOWED_ORIGINS = https://yourdomain.com
REACTAPP_RESET_URL = https://yourdomain.com/reset-password/
LOGIN_URI = https://yourdomain.com/login
PUBLIC_BASE_URL = https://yourdomain.vercel.app
```

**EMAIL (from STEP 4):**
```
EMAIL_HOST = smtp.gmail.com
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = your-email@gmail.com
EMAIL_HOST_PASSWORD = [Gmail App Password from STEP 4]
```

**FILE STORAGE (WITHOUT AWS):**
```
USE_S3 = False
```

**STRIPE (from STEP 5):**
```
STRIPE_SECRET_KEY = sk_live_[from STEP 5]
STRIPE_PUBLISHABLE_KEY = pk_live_[from STEP 5]
STRIPE_WEBHOOK_SECRET = whsec_[from STEP 5]
```

**OPTIONAL:**
```
GEMINI_API_KEY = [if you have it]
```

✅ **All environment variables added!**

---

## 🟢 STEP 8: Deploy!

**What to do:**

1. After adding ALL environment variables, click: **Deploy**
2. Wait for build to complete (5-10 minutes)
3. You'll see: "Congratulations! Your project is deployed"
4. Copy your live URL: `https://medtag-backend-xyz.vercel.app`

✅ **Your backend is now live!**

---

## ✅ STEP 9: Verify Deployment (5 minutes)

### Test 1: Health Check
```bash
curl https://your-url.vercel.app/api/health/
```
Should return JSON response.

### Test 2: Static Files
```bash
curl https://your-url.vercel.app/static/admin/css/base.css
```
Should return CSS content (not 404 error).

### Test 3: Check Logs
1. Go to: **Vercel Dashboard** → **Deployments**
2. Click latest deployment → **Logs**
3. Look for: "Successfully ran migrations"
4. No red errors?

### Test 4: API Response
```bash
curl -X POST https://your-url.vercel.app/api/auth/login/ \
  -H "Content-Type: application/json"
```
Should return proper JSON response.

✅ **All tests passing! You're done!**

---

## 🎯 Post-Deployment

### First 24 Hours:
- [ ] Monitor logs for errors
- [ ] Test user authentication
- [ ] Test file uploads
- [ ] Test email sending
- [ ] Test payment processing

### Setup Custom Domain (Optional):
1. Vercel Dashboard → Domains
2. Add your custom domain
3. Update DNS records
4. Wait for SSL certificate (~24 hours)

### Enable Monitoring (Optional):
1. Vercel Dashboard → Analytics
2. Monitor performance metrics
3. Check error rates

---

## 🆘 Common Issues & Fixes

### ❌ Issue: Build fails with "ModuleNotFoundError"
**Fix:**
1. Check `requirements.txt` has the package
2. Rebuild in Vercel: Deployments → Redeploy

### ❌ Issue: "404 Not Found" on static files
**Fix:**
1. Verify static files are collected properly
2. Check `STATIC_ROOT = staticfiles` in settings
3. Rebuild and redeploy

### ❌ Issue: Database connection timeout
**Fix:**
1. Verify DB_HOST is complete Vercel Postgres URL
2. Check DB_PASSWORD is correct
3. Verify sslmode=require is included
4. Rebuild and redeploy

### ❌ Issue: CORS errors from frontend
**Fix:**
1. Add your frontend domain to CORS_ALLOWED_ORIGINS
2. Use https:// prefix
3. Example: `https://yourdomain.com`
4. Rebuild and redeploy

### ❌ Issue: Email not sending
**Fix:**
1. Use Gmail App Password (16 chars), NOT main password
2. Verify EMAIL_HOST_USER is correct
3. Test locally first: `python manage.py shell`
4. Then: `from django.core.mail import send_mail; send_mail(...)`

### ❌ Issue: Migrations not running
**Fix:**
1. Check Vercel build logs for migration errors
2. Verify database connection is working
3. Rebuild and redeploy

### ❌ Issue: File uploads not working
**Fix:**
1. Files are stored locally on Vercel's filesystem
2. This works for normal usage
3. For permanent file storage across deploys, add AWS S3 later

---

## 📞 Need Help?

**Documentation Files:**
- `VERCEL_DEPLOYMENT_GUIDE.md` - Detailed deployment guide
- `PRE_DEPLOYMENT_CHECKLIST.md` - Verification checklist
- `SECURITY_NOTICE.md` - Security details
- `PRODUCTION_READY_ANALYSIS.md` - Technical details
- `DEPLOYMENT_CARD.txt` - Quick reference

**Quick Commands:**

Test Django deployment config:
```bash
python manage.py check --deploy
```

Test database connection locally:
```bash
python manage.py dbshell
```

Collect static files:
```bash
python manage.py collectstatic --noinput
```

---

## 📊 Deployment Checklist

### Before Step 1:
- [ ] Read this entire guide
- [ ] Have terminal/PowerShell ready
- [ ] Vercel account logged in
- [ ] Gmail account ready
- [ ] Stripe account ready

### Before Step 6 (Vercel Deploy):
- [ ] ✅ Step 1: SECRET_KEY generated and saved
- [ ] ✅ Step 2: Vercel Postgres created, credentials saved
- [ ] ✅ Step 3: File storage setup (no action needed)
- [ ] ✅ Step 4: Gmail App Password generated and saved
- [ ] ✅ Step 5: Stripe keys copied and saved

### After Step 8 (Deployment):
- [ ] Build completed successfully
- [ ] No errors in build logs
- [ ] Live URL obtained
- [ ] ✅ Step 9: All verification tests passed

### After Step 9 (Verification):
- [ ] Health check working
- [ ] Static files loading
- [ ] No 500 errors
- [ ] API responding correctly
- [ ] CORS headers present
- [ ] Monitoring enabled

---

## 🎉 Success!

Your MedTag backend is now deployed to Vercel and live!

**Your live URL:**
```
https://medtag-backend-[random].vercel.app
```

**Without AWS:**
- ✅ Files are stored locally (works perfectly on Vercel)
- ✅ No bank card required!
- ✅ You can upgrade to AWS S3 later if needed
- ✅ Everything else is fully functional

**Next Steps:**
1. Share URL with your team
2. Connect your frontend
3. Monitor for issues
4. Celebrate! 🎉

---

## 📈 Performance Metrics

Check your deployment performance:
- Vercel Dashboard → Analytics
- Monitor response times
- Check error rates
- Optimize if needed

---

## 🔄 Redeployment

To redeploy after making code changes:
1. Push code to GitHub
2. Vercel automatically redeploys
3. Check logs for build status
4. Verify changes are live

To manually redeploy:
1. Vercel Dashboard → Deployments
2. Click latest → Redeploy

---

## ➕ Adding AWS S3 Later (Optional)

If you later want to add AWS S3 for better file storage/CDN:
1. Get a bank card
2. Set up AWS S3 bucket
3. Create IAM access keys
4. Add to Vercel environment variables:
   - `USE_S3 = True`
   - AWS credentials
5. Redeploy in Vercel

Your app is ready for this upgrade anytime!

---

## 🎓 Why Local Storage Works Without AWS

1. **Vercel has filesystem**: You can write files temporarily
2. **Good for testing**: File uploads work during development
3. **Upgrade anytime**: Switch to S3 when you're ready
4. **No downtime required**: Can add AWS without restarting
5. **Cost-effective**: No storage costs initially

---

**Congratulations! Your backend is now production-ready on Vercel! 🚀**

For any issues, check the documentation files or review the troubleshooting section above.

Happy deploying! 🎯
