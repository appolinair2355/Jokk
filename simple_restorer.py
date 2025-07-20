"""
Système de restauration simple et robuste des redirections
Fonctionne sans dépendance à PostgreSQL
"""

import logging
import asyncio
import os
import json
from telethon import TelegramClient
from config.settings import API_ID, API_HASH

logger = logging.getLogger(__name__)

class SimpleRedirectionRestorer:
    """Système de restauration simple et efficace"""
    
    def __init__(self):
        self.active_clients = {}
        self.restored_redirections = 0
        self.message_mapping = {}  # Maps original message ID to redirected message ID
        
    async def restore_all_redirections(self):
        """Restaure toutes les redirections depuis PostgreSQL"""
        try:
            logger.info("🔄 Démarrage de la restauration simple des redirections")
            
            # Utiliser PostgreSQL au lieu de user_data.json
            from database_manager import database_manager
            
            # Obtenir toutes les redirections actives
            redirections = database_manager.get_all_active_redirections()
            
            if not redirections:
                logger.info("Aucune redirection active à restaurer")
                return
            
            # Grouper par utilisateur
            user_redirections = {}
            for redir in redirections:
                user_id = int(redir[1])  # user_id
                if user_id not in user_redirections:
                    user_redirections[user_id] = {}
                
                user_redirections[user_id][redir[2]] = {  # name
                    'source_id': redir[5],  # source_id
                    'destination_id': redir[6],  # destination_id
                    'phone_number': redir[3],  # phone_number
                    'active': True
                }
            
            # Restaurer pour chaque utilisateur
            for user_id, user_redirs in user_redirections.items():
                await self._restore_user_redirections_postgres(user_id, user_redirs)
            
            logger.info(f"✅ Restauration terminée: {self.restored_redirections} redirections actives")
            
        except Exception as e:
            logger.error(f"Erreur lors de la restauration: {e}")
    
    async def _restore_user_redirections_postgres(self, user_id, user_redirections):
        """Restaure les redirections d'un utilisateur"""
        try:
            # Filtrer les redirections actives
            active_redirections = {
                name: data for name, data in user_redirections.items()
                if data.get('active', True) and data.get('source_id') and data.get('destination_id')
            }
            
            if not active_redirections:
                return
                
            logger.info(f"Restauration de {len(active_redirections)} redirections pour utilisateur {user_id}")
            
            # Obtenir le numéro de téléphone depuis la première redirection
            phone_number = None
            for redir_data in active_redirections.values():
                if redir_data.get('phone_number'):
                    phone_number = redir_data['phone_number']
                    break
            
            if not phone_number:
                logger.warning(f"Aucun numéro trouvé pour utilisateur {user_id}")
                return
            
            # Créer le client Telegram
            client = await self._create_telegram_client(user_id, phone_number)
            if not client:
                logger.warning(f"Impossible de créer le client pour {user_id}")
                return
            
            # Configurer les redirections
            await self._setup_message_handlers(client, user_id, active_redirections)
            
            # Stocker le client actif
            self.active_clients[user_id] = {
                'client': client,
                'phone': phone_number,
                'redirections': len(active_redirections)
            }
            
            self.restored_redirections += len(active_redirections)
            logger.info(f"✅ {len(active_redirections)} redirections configurées pour {user_id}")
            
        except Exception as e:
            logger.error(f"Erreur restauration utilisateur {user_id}: {e}")
    
    def _get_user_phone(self, user_id, connections):
        """Obtient le numéro de téléphone d'un utilisateur"""
        try:
            user_connections = connections.get(str(user_id), [])
            if user_connections:
                # Prendre la connexion la plus récente active
                for conn in reversed(user_connections):
                    if conn.get('active', True):
                        phone = conn.get('phone', '')
                        return phone.replace('+', '') if phone.startswith('+') else phone
            return None
        except:
            return None
    
    async def _create_telegram_client(self, user_id, phone_number):
        """Crée un client Telegram"""
        try:
            # Vérifier si un client existe déjà
            from bot.connection import active_connections
            if user_id in active_connections:
                existing_client = active_connections[user_id].get('client')
                if existing_client and existing_client.is_connected():
                    logger.info(f"Utilisation du client existant pour {user_id}")
                    return existing_client
            
            # Chercher les fichiers de session possibles
            session_files = [
                f"session_{user_id}_{phone_number}.session",
                f"session_1190237801_22995501564.session",  # Session connue
                f"session_1190237801_22967924076.session",  # Autre session connue
                f"{user_id}_{phone_number}.session",
                f"session_{phone_number}.session"
            ]
            
            session_file = None
            for session_name in session_files:
                if os.path.exists(session_name):
                    session_file = session_name
                    break
            
            if not session_file:
                logger.warning(f"Aucune session trouvée pour {user_id}:{phone_number}")
                return None
            
            # Attendre un moment pour éviter les conflits de base de données
            await asyncio.sleep(1)
            
            # Créer le client
            client = TelegramClient(session_file, API_ID, API_HASH)
            
            # Démarrer la session avec timeout
            try:
                await asyncio.wait_for(client.start(phone=f"+{phone_number}"), timeout=30)
            except asyncio.TimeoutError:
                logger.error(f"Timeout lors de la connexion pour {user_id}")
                return None
            
            if client.is_connected():
                logger.info(f"Client connecté pour {user_id} avec session {session_file}")
                return client
            else:
                logger.error(f"Échec de connexion pour {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur création client {user_id}:{phone_number}: {e}")
            return None
    
    async def _setup_message_handlers(self, client, user_id, redirections):
        """Configure les gestionnaires de messages"""
        try:
            from telethon import events
            
            # Vérifier que le client est connecté
            if not client.is_connected():
                logger.error(f"Client non connecté pour utilisateur {user_id}")
                return
            
            # Stocker le client dans active_connections pour éviter les conflits
            from bot.connection import active_connections
            active_connections[user_id] = {
                'client': client,
                'phone': self._get_user_phone_from_redirections(redirections),
                'active': True
            }
            
            for name, redir_data in redirections.items():
                source_id = int(redir_data['source_id'])
                destination_id = int(redir_data['destination_id'])
                
                # Créer le gestionnaire de messages
                @client.on(events.NewMessage(chats=source_id))
                async def message_handler(event, dest_id=destination_id, redirect_name=name, u_id=user_id):
                    try:
                        await self._forward_message(event, dest_id, redirect_name, u_id)
                    except Exception as e:
                        logger.error(f"Erreur redirection {redirect_name}: {e}")
                
                # Créer le gestionnaire d'édition
                @client.on(events.MessageEdited(chats=source_id))
                async def edit_handler(event, dest_id=destination_id, redirect_name=name, u_id=user_id):
                    try:
                        await self._forward_message(event, dest_id, redirect_name, u_id, is_edit=True)
                    except Exception as e:
                        logger.error(f"Erreur édition {redirect_name}: {e}")
                
                logger.info(f"Gestionnaire configuré: {name} ({source_id} → {destination_id})")
                
        except Exception as e:
            logger.error(f"Erreur configuration gestionnaires: {e}")
    
    def _get_user_phone_from_redirections(self, redirections):
        """Obtient le numéro de téléphone depuis les redirections"""
        for redir_data in redirections.values():
            if redir_data.get('phone'):
                return redir_data['phone']
        return None
    
    async def _forward_message(self, event, destination_id, redirect_name, user_id, is_edit=False):
        """Transfère un message"""
        try:
            message = event.message
            original_msg_id = message.id
            mapping_key = f"{event.chat_id}_{original_msg_id}_{destination_id}"
            
            if is_edit:
                # Vérifier si nous avons une correspondance pour ce message
                if mapping_key in self.message_mapping:
                    redirected_msg_id = self.message_mapping[mapping_key]
                    try:
                        # Modifier le message existant
                        if message.text:
                            await event.client.edit_message(int(destination_id), redirected_msg_id, message.text)
                            logger.info(f"Message modifié: {redirect_name}")
                            return
                        elif message.media:
                            # Pour les médias modifiés, supprimer et renvoyer
                            try:
                                await event.client.delete_messages(int(destination_id), redirected_msg_id)
                            except:
                                pass
                            # Continuer pour envoyer le nouveau message
                        else:
                            # Message supprimé, supprimer aussi le message redirigé
                            try:
                                await event.client.delete_messages(int(destination_id), redirected_msg_id)
                                del self.message_mapping[mapping_key]
                                logger.info(f"Message supprimé: {redirect_name}")
                                return
                            except:
                                return
                    except Exception as edit_error:
                        # Si l'édition échoue, continuer pour envoyer un nouveau message
                        if "Content of the message was not modified" in str(edit_error):
                            logger.info(f"Contenu inchangé pour {redirect_name}")
                            return
                        logger.warning(f"Échec édition message {redirected_msg_id}: {edit_error}")
                else:
                    # Édition d'un message non mappé, ne rien faire
                    logger.info(f"Édition d'un message non mappé: {original_msg_id}")
                    return
            
            # Envoyer un nouveau message (première fois ou remplacement)
            sent_message = None
            if message.text:
                sent_message = await event.client.send_message(int(destination_id), message.text)
            elif message.media:
                sent_message = await event.client.forward_messages(int(destination_id), message)
            else:
                return
            
            # Stocker la correspondance pour les futures éditions
            if sent_message and not is_edit:
                if hasattr(sent_message, 'id'):
                    self.message_mapping[mapping_key] = sent_message.id
                elif isinstance(sent_message, list) and len(sent_message) > 0:
                    self.message_mapping[mapping_key] = sent_message[0].id
            elif sent_message and is_edit:
                # Mettre à jour la correspondance pour les remplacements de médias
                if hasattr(sent_message, 'id'):
                    self.message_mapping[mapping_key] = sent_message.id
                elif isinstance(sent_message, list) and len(sent_message) > 0:
                    self.message_mapping[mapping_key] = sent_message[0].id
            
            action = "modifié et redirigé" if is_edit else "transféré"
            logger.info(f"Message {action}: {redirect_name}")
            
        except Exception as e:
            logger.error(f"Erreur transfert message: {e}")
    
    async def _get_channel_name(self, client, chat_id):
        """Obtient le nom d'un canal"""
        try:
            entity = await client.get_entity(chat_id)
            return getattr(entity, 'title', getattr(entity, 'username', str(chat_id)))
        except:
            return str(chat_id)

# Instance globale
simple_restorer = SimpleRedirectionRestorer()