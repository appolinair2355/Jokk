"""
Système de restauration automatique des redirections
Ce module assure que toutes les redirections actives sont restaurées au démarrage
"""

import logging
import asyncio
import os
from telethon import TelegramClient
from bot.database import load_data
from bot.connection import active_connections, store_connection_client
from config.settings import API_ID, API_HASH

logger = logging.getLogger(__name__)

class RedirectionRestorer:
    """Restaure automatiquement les redirections au démarrage"""
    
    def __init__(self):
        self.restored_count = 0
        self.failed_count = 0
        
    async def restore_all_redirections(self):
        """Restaure toutes les redirections actives"""
        try:
            logger.info("🔄 Démarrage de la restauration automatique des redirections")
            
            # Charger les données
            data = load_data()
            redirections = data.get("redirections", {})
            
            if not redirections:
                logger.info("Aucune redirection à restaurer")
                return
            
            # Restaurer chaque redirection
            for user_id, user_redirections in redirections.items():
                await self._restore_user_redirections(int(user_id), user_redirections)
            
            logger.info(f"✅ Restauration terminée: {self.restored_count} redirections restaurées, {self.failed_count} échecs")
            
        except Exception as e:
            logger.error(f"Erreur lors de la restauration des redirections: {e}")
    
    async def _restore_user_redirections(self, user_id, user_redirections):
        """Restaure les redirections pour un utilisateur"""
        try:
            # Obtenir les redirections actives
            active_redirections = {
                name: data for name, data in user_redirections.items() 
                if data.get('active', True) and data.get('source_id') and data.get('destination_id')
            }
            
            if not active_redirections:
                return
            
            logger.info(f"Restauration de {len(active_redirections)} redirections pour utilisateur {user_id}")
            
            # Obtenir le numéro de téléphone
            phone_number = None
            for redir_data in active_redirections.values():
                if redir_data.get('phone'):
                    phone_number = redir_data['phone']
                    break
            
            if not phone_number:
                logger.warning(f"Aucun numéro de téléphone trouvé pour l'utilisateur {user_id}")
                return
            
            # Restaurer la session Telegram
            client = await self._restore_telegram_session(user_id, phone_number)
            
            if client:
                # Configurer les redirections
                await self._setup_redirections(client, user_id, active_redirections)
                logger.info(f"✅ {len(active_redirections)} redirections restaurées pour utilisateur {user_id}")
                self.restored_count += len(active_redirections)
            else:
                logger.warning(f"❌ Impossible de restaurer la session pour utilisateur {user_id}")
                self.failed_count += len(active_redirections)
                
        except Exception as e:
            logger.error(f"Erreur lors de la restauration pour utilisateur {user_id}: {e}")
            self.failed_count += len(user_redirections)
    
    async def _restore_telegram_session(self, user_id, phone_number):
        """Restaure une session Telegram"""
        try:
            # Vérifier si la session existe déjà
            if user_id in active_connections:
                client = active_connections[user_id].get('client')
                if client and client.is_connected():
                    logger.info(f"Session déjà active pour utilisateur {user_id}")
                    return client
            
            # Chercher le fichier de session
            session_file = f"session_{user_id}_{phone_number}.session"
            if not os.path.exists(session_file):
                # Chercher d'autres formats de session
                possible_sessions = [
                    f"session_{user_id}_{phone_number}.session",
                    f"{user_id}_{phone_number}.session",
                    f"session_{phone_number}.session",
                    f"{phone_number}.session"
                ]
                
                session_file = None
                for session_name in possible_sessions:
                    if os.path.exists(session_name):
                        session_file = session_name
                        break
                
                if not session_file:
                    logger.warning(f"Aucun fichier de session trouvé pour {user_id}:{phone_number}")
                    return None
            
            # Créer le client Telegram
            client = TelegramClient(session_file, API_ID, API_HASH)
            
            # Démarrer la session
            await client.start(phone=phone_number)
            
            if client.is_connected():
                # Stocker la connexion
                await store_connection_client(user_id, phone_number, client)
                logger.info(f"Session restaurée avec succès pour {user_id}:{phone_number}")
                return client
            else:
                logger.error(f"Impossible de se connecter pour {user_id}:{phone_number}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la restauration de session {user_id}:{phone_number}: {e}")
            return None
    
    async def _setup_redirections(self, client, user_id, redirections):
        """Configure les redirections pour un client"""
        try:
            from bot.message_handler import message_redirector
            
            for name, redir_data in redirections.items():
                source_id = int(redir_data['source_id'])
                destination_id = int(redir_data['destination_id'])
                
                # Ajouter le gestionnaire de redirection
                await message_redirector.add_redirection_handler(
                    user_id, name, source_id, destination_id
                )
                
                logger.info(f"Redirection configurée: {name} ({source_id} -> {destination_id})")
                
        except Exception as e:
            logger.error(f"Erreur lors de la configuration des redirections: {e}")

# Instance globale
redirection_restorer = RedirectionRestorer()