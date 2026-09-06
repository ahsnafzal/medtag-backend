#!/bin/bash
# Build script for Vercel deployment

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate
