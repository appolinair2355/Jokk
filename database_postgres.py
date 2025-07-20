"""
PostgreSQL database operations for TeleFeed Bot
Replaces the JSON-based database.py with PostgreSQL functionality
"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from database_manager import database_manager

logger = logging.getLogger(__name__)


async def store_license(user_id, license_code):
    """Store validated license using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import db, User
            
            user = User.query.filter_by(user_id=str(user_id)).first()
            if user:
                user.license_code = license_code
                user.validated_at = datetime.now()
                user.active = True
            else:
                user = User(
                    user_id=str(user_id),
                    license_code=license_code,
                    validated_at=datetime.now(),
                    active=True
                )
                db.session.add(user)
            
            db.session.commit()
            logger.info(f"License stored for user {user_id}")
    except Exception as e:
        logger.error(f"Error storing license: {e}")


async def is_user_licensed(user_id):
    """Check if user has valid license using PostgreSQL"""
    return database_manager.is_user_licensed(str(user_id))


async def store_connection(user_id, phone_number):
    """Store successful phone connection using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import db, User, Connection
            
            # Ensure user exists
            user = User.query.filter_by(user_id=str(user_id)).first()
            if not user:
                user = User(user_id=str(user_id), active=False)
                db.session.add(user)
                db.session.flush()
            
            # Remove existing connection for same phone
            existing = Connection.query.filter_by(
                user_id=str(user_id), 
                phone_number=phone_number
            ).first()
            if existing:
                db.session.delete(existing)
            
            # Add new connection
            connection = Connection(
                user_id=str(user_id),
                phone_number=phone_number,
                connected_at=datetime.now(),
                active=True,
                replaced_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            )
            db.session.add(connection)
            db.session.commit()
            logger.info(f"Connection stored/replaced for user {user_id}: {phone_number}")
            
    except Exception as e:
        logger.error(f"Error storing connection: {e}")


async def get_user_connections(user_id):
    """Get user's phone connections using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import Connection
            
            connections = Connection.query.filter_by(user_id=str(user_id)).all()
            return [
                {
                    "phone": conn.phone_number,
                    "connected_at": conn.connected_at.isoformat(),
                    "active": conn.active,
                    "replaced_at": conn.replaced_at
                }
                for conn in connections
            ]
    except Exception as e:
        logger.error(f"Error getting user connections: {e}")
        return []


async def store_redirection(user_id, name, phone_number, action, channel_name=None, source_id=None, destination_id=None):
    """Store redirection rule using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import db, User, Redirection
            
            # Ensure user exists
            user = User.query.filter_by(user_id=str(user_id)).first()
            if not user:
                user = User(user_id=str(user_id), active=False)
                db.session.add(user)
                db.session.flush()
            
            if action == "add":
                # Check if redirection with same phone already exists and replace it
                existing_redirection = Redirection.query.filter_by(
                    user_id=str(user_id),
                    phone_number=phone_number,
                    active=True
                ).first()
                
                replaced_info = ""
                if existing_redirection:
                    replaced_info = f" (remplacé: {existing_redirection.name})"
                    db.session.delete(existing_redirection)
                
                redirection = Redirection(
                    user_id=str(user_id),
                    name=name,
                    phone_number=phone_number,
                    channel_name=channel_name or name,
                    source_id=source_id,
                    destination_id=destination_id,
                    created_at=datetime.now(),
                    replaced_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    active=True,
                    replacement_info=replaced_info
                )
                db.session.add(redirection)
                
            elif action == "remove":
                redirection = Redirection.query.filter_by(
                    user_id=str(user_id),
                    name=name
                ).first()
                if redirection:
                    db.session.delete(redirection)
                    
            elif action == "change":
                redirection = Redirection.query.filter_by(
                    user_id=str(user_id),
                    name=name
                ).first()
                if redirection:
                    redirection.phone_number = phone_number
                    redirection.channel_name = channel_name or name
                    redirection.source_id = source_id
                    redirection.destination_id = destination_id
                    redirection.updated_at = datetime.now()
            
            db.session.commit()
            logger.info(f"Redirection {action} for user {user_id}: {name} -> {channel_name or name}")
            
    except Exception as e:
        logger.error(f"Error storing redirection: {e}")


async def get_user_redirections(user_id, phone_number):
    """Get user redirections for a phone number using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import Redirection
            
            redirections = Redirection.query.filter_by(
                user_id=str(user_id),
                phone_number=phone_number,
                active=True
            ).all()
            
            return [
                {
                    "name": redir.name,
                    "channel_name": redir.channel_name,
                    "status": "Actif"
                }
                for redir in redirections
            ]
    except Exception as e:
        logger.error(f"Error getting user redirections: {e}")
        return []


async def store_pending_redirection(user_id, name, phone_number):
    """Store pending redirection waiting for channel IDs using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import db, PendingRedirection
            
            # Remove existing pending redirection for user
            existing = PendingRedirection.query.filter_by(user_id=str(user_id)).first()
            if existing:
                db.session.delete(existing)
            
            pending = PendingRedirection(
                user_id=str(user_id),
                name=name,
                phone_number=phone_number,
                created_at=datetime.now()
            )
            db.session.add(pending)
            db.session.commit()
            logger.info(f"Pending redirection stored for user {user_id}: {name} on {phone_number}")
            
    except Exception as e:
        logger.error(f"Error storing pending redirection: {e}")


async def get_pending_redirection(user_id):
    """Get pending redirection for user using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import PendingRedirection
            
            pending = PendingRedirection.query.filter_by(user_id=str(user_id)).first()
            if pending:
                return {
                    "name": pending.name,
                    "phone_number": pending.phone_number,
                    "created_at": pending.created_at.isoformat()
                }
            return None
    except Exception as e:
        logger.error(f"Error getting pending redirection: {e}")
        return None


async def clear_pending_redirection(user_id):
    """Clear pending redirection for user using PostgreSQL"""
    try:
        with database_manager.app.app_context():
            from models import db, PendingRedirection
            
            pending = PendingRedirection.query.filter_by(user_id=str(user_id)).first()
            if pending:
                db.session.delete(pending)
                db.session.commit()
                logger.info(f"Pending redirection cleared for user {user_id}")
                
    except Exception as e:
        logger.error(f"Error clearing pending redirection: {e}")


def load_data():
    """Load data from PostgreSQL in format compatible with existing code"""
    try:
        return database_manager.export_redirections_for_deployment()
    except Exception as e:
        logger.error(f"Error loading data from PostgreSQL: {e}")
        return {
            "licenses": {},
            "connections": {},
            "redirections": {},
            "transformations": {},
            "whitelists": {},
            "blacklists": {},
            "chats": {},
            "pending_redirections": {}
        }


def save_data(data):
    """Save data to PostgreSQL - compatibility function"""
    # This function is kept for compatibility but actual saving
    # is handled by individual store_* functions
    logger.info("PostgreSQL save_data called - data is automatically saved by individual operations")


async def get_user_chats_data(user_id, phone_number, chat_type=None):
    """Get user chats data from the original database.py implementation"""
    # Import the original function to maintain compatibility
    from bot.database import get_user_chats_data as original_get_chats
    return await original_get_chats(user_id, phone_number, chat_type)