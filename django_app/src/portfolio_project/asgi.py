"""
ASGI config for portfolio_project.
Pure async Django ASGI application with native async I/O support.
Uses channels for WebSocket and advanced async features.
NO pseudo-concurrency (greenlet) - native async only.
"""

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

# Initialize Django ASGI application early
django.setup()
django_asgi_app = get_asgi_application()

# Pure async ASGI application with channels support
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    # Add WebSocket support when needed
    # 'websocket': URLRouter([...]),
})