"""
ASGI config for med_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/

NOTE: Vercel has limited WebSocket support. This file uses channels
for WebSocket support in development, but falls back to standard WSGI
in production on Vercel.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'med_backend.settings')

# Get the base ASGI application
django_asgi_app = get_asgi_application()

# Try to import Channels for WebSocket support (only in development)
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from decouple import config
    
    # Only use Channels if not in production
    IS_PRODUCTION = config('ENVIRONMENT', default='development') == 'production'
    
    if not IS_PRODUCTION:
        # Development: Use Channels with WebSocket support
        try:
            import accounts.routing
            
            application = ProtocolTypeRouter({
                "http": django_asgi_app,
                "websocket": AuthMiddlewareStack(
                    URLRouter(
                        accounts.routing.websocket_urlpatterns
                    )
                ),
            })
        except (ImportError, AttributeError):
            # If routing is not available, fall back to standard ASGI
            application = django_asgi_app
    else:
        # Production on Vercel: Use standard WSGI via ASGI
        application = django_asgi_app
        
except ImportError:
    # Channels not available, use standard ASGI
    application = django_asgi_app


