from config.env_loader import load_env
from bot.handlers import start_bot_sync
from http_server import start_server_in_background
import os
import threading

if __name__ == "__main__":
    load_env()

    # Configuration pour Replit Always On
    replit_port = int(os.environ.get('PORT', 8080))
    os.environ['PORT'] = str(replit_port)
    
    # Log deployment success message
    print("🚀 bot déployé avec succès")

    # Start HTTP server in background
    server_thread = start_server_in_background()
    
    # Start the bot (main process)
    start_bot_sync()