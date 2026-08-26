import os
import sys
from django.core.wsgi import get_wsgi_application
from waitress import serve

def main():
    # Set default settings module for Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    # Get WSGI application
    application = get_wsgi_application()
    
    print("=" * 60)
    print("  SIMAP Django Production Server (Waitress)")
    print("=" * 60)
    print("  Listening host    : 127.0.0.1")
    print("  Listening port    : 8000")
    print("  Thread pool size  : 16")
    print("  Connection limit : 1000")
    print("=" * 60)
    print("  Press Ctrl+C to stop the server.\n")
    
    serve(
        application,
        host='127.0.0.1',
        port=8000,
        threads=16,
        connection_limit=1000
    )

if __name__ == '__main__':
    main()
