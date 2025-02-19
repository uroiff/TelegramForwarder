"""
Telegram Message Forwarder.
Author: uroiff.
Version: 1.0.
"""

import os
import re
import json
import logging
import asyncio
from glob import glob
from pathlib import Path
from datetime import datetime, time
from typing import List, Dict, Any, Union, Pattern

from telethon import TelegramClient, events
from telethon.tl.types import (
    Message, MessageMediaPhoto, MessageMediaDocument,
    MessageMediaGeo, MessageMediaContact, MessageMediaGame,
    MessageMediaPoll, MessageMediaUnsupported, PeerChannel
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('telegram_forwarder.log', encoding='utf-8')  # Log file
    ]
)
logger = logging.getLogger(__name__)

# Default paths
CONFIG_PATH = 'config.json'
SESSIONS_DIR = 'sessions'

class SessionManager:
    """Manages Telegram session files."""
    
    def __init__(self, sessions_dir: str = SESSIONS_DIR):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        
    def list_sessions(self) -> List[str]:
        """List available session files."""
        session_files = glob(str(self.sessions_dir / "*.session"))
        return [Path(f).stem for f in session_files]
    
    def get_session_path(self, session_name: str) -> Path:
        """Get full path for a session file."""
        return self.sessions_dir / f"{session_name}.session"
    
    def session_exists(self, session_name: str) -> bool:
        """Check if a session file exists."""
        return self.get_session_path(session_name).exists()


class MessageFilter:
    """Handles filtering of messages based on configured criteria."""
    
    def __init__(self, mapping_config: Dict[str, Any]):
        self.keyword_filtering_enabled = mapping_config.get('keyword_filtering_enabled', False)
        self.keywords_include = mapping_config.get('keywords_include', [])
        self.keywords_exclude = mapping_config.get('keywords_exclude', [])
        self.number_threshold_enabled = mapping_config.get('number_threshold_enabled', False)
        self.number_threshold_min = mapping_config.get('number_threshold_min', 0)
        self.number_threshold_max = mapping_config.get('number_threshold_max', float('inf'))
        self.number_regex_patterns = mapping_config.get('number_regex_patterns', [
            r'spend\s+(\d+(?:\.\d+)?)'
        ])
        
        # Initialize regex patterns
        self.regex_patterns = [re.compile(pattern) for pattern in self.number_regex_patterns]
    
    def _get_message_text(self, message: Message) -> str:
        """Extract text content from message, including captions."""
        if message.text:
            return message.text
        elif message.caption:
            return message.caption
        return ""
    
    def _check_keywords(self, text: str) -> bool:
        """Check if text contains/excludes specified keywords."""
        text_lower = text.lower()
        
        # Check for excluded keywords
        if self.keywords_exclude:
            if any(keyword.lower() in text_lower for keyword in self.keywords_exclude):
                return False
        
        # Check for included keywords
        if self.keywords_include:
            if not any(keyword.lower() in text_lower for keyword in self.keywords_include):
                return False
        
        return True
    
    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numbers from text using configured regex patterns."""
        numbers = []
        text = text.lower()  # Case-insensitive matching
        
        for pattern in self.number_regex_patterns:
            logger.info(f"Pattern: {pattern}")
            logger.info(f"Text: {text}")
            
            # Remove asterisks from text for proper matching
            cleaned_text = text.replace('*', '')
            matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
            logger.info(f"Cleaned text: {cleaned_text}")
            logger.info(f"Matches found: {matches}")
            
            try:
                numbers.extend(float(num) for num in matches if num)
            except Exception as e:
                logger.error(f"Error converting matches to numbers: {e}")
        
        logger.info(f"Extracted numbers: {numbers}")
        return numbers

    def should_forward(self, message: Message) -> bool:
        """Check if message should be forwarded based on filters."""
        text = self._get_message_text(message)
        logger.info(f"Checking message: {text}")
        
        # Check keywords if keyword filtering is enabled
        if self.keyword_filtering_enabled:
            if not self._check_keywords(text):
                logger.info("Failed keywords check")
                return False
        
        # Check number thresholds if enabled
        if self.number_threshold_enabled:
            numbers = self._extract_numbers(text)
            logger.info(f"Number threshold check - min: {self.number_threshold_min}, max: {self.number_threshold_max}")
            logger.info(f"Found numbers: {numbers}")
            
            if not numbers:
                logger.info("No numbers found in message")
                return False
                
            number_within_range = any(
                self.number_threshold_min <= num <= self.number_threshold_max 
                for num in numbers
            )
            
            if not number_within_range:
                logger.info("No numbers found within threshold range")
                return False
            
            logger.info("Number threshold check passed")
        
        logger.info("Message passed all filters")
        return True


class MessageModifier:
    """Handles modifications to messages before forwarding."""
    
    def __init__(self, mapping_config: Dict[str, Any]):
        self.enabled = mapping_config.get('modification_enabled', False)
        self.prefix_enabled = mapping_config.get('prefix_enabled', False)
        self.suffix_enabled = mapping_config.get('suffix_enabled', False)
        self.prefix = mapping_config.get('prefix', '')
        self.suffix = mapping_config.get('suffix', '')
    
    def modify_message(self, message_text: str) -> str:
        if not self.enabled:
            return message_text

        modified_text = message_text

        if self.prefix_enabled and self.prefix:
            modified_text = f"{self.prefix}\n{modified_text}"

        if self.suffix_enabled and self.suffix:
            modified_text = f"{modified_text}\n{self.suffix}"

        return modified_text



class TelegramAccount:
    """Manages a single Telegram account session."""
    
    def __init__(self, session_name: str, config: Dict[str, Any]):
        self.session_name = session_name
        self.api_id = config['api_id']
        self.api_hash = config['api_hash']
        self.session_dir = config['session_dir']
        self.session_path = os.path.join(self.session_dir, f"{self.session_name}.session")
        self.client = None
        self.mappings = []
        
        # Initialize filters for each mapping
        for mapping in config.get('mappings', []):
            mapping_copy = mapping.copy()
            mapping_copy['filter'] = MessageFilter(mapping)
            
            # Convert source and destination to integers if they're numeric strings
            for field in ['source', 'destination']:
                value = mapping_copy[field]
                if isinstance(value, str) and value.isdigit():
                    mapping_copy[field] = int(value)
            
            self.mappings.append(mapping_copy)

    async def start(self) -> None:
        """Start the Telegram client for this account."""
        self.client = TelegramClient(
            self.session_path,
            self.api_id,
            self.api_hash
        )
        await self.client.start()
        logger.info(f"Started client for account {self.session_name}")
    
    async def stop(self) -> None:
        """Stop the Telegram client."""
        if self.client:
            await self.client.disconnect()
            logger.info(f"Stopped client for account {self.session_name}")
    
    async def handle_message(self, event, mapping: Dict[str, Any]) -> None:
        try:
            # Reload config before processing each message
            try:
                with open(CONFIG_PATH, 'r') as f:
                    new_config = json.load(f)
                    
                # Update mapping with new config
                for new_mapping in new_config.get('mappings', []):
                    if (new_mapping.get('source') == mapping['source'] and 
                        new_mapping.get('destination') == mapping['destination']):
                        # Update filter with new settings
                        mapping.update(new_mapping)
                        mapping['filter'] = MessageFilter(new_mapping)
                        break
                        
            except Exception as e:
                logger.error(f"Error reloading config: {str(e)}")
                # Continue with existing mapping if reload fails
            
            # Log incoming message details
            logger.info(f"Received message from {event.sender_id} in {event.chat_id}")

            # Check if mapping is enabled
            if not mapping.get('enabled', True):
                return

            # Get message text
            message = event.message
            message_text = message.text if message.text else message.caption if message.caption else ""
            
            # Perform filtering
            if not mapping['filter'].should_forward(message):
                logger.info(f"Message filtered out: {message_text[:100]}...")
                return

            # Forward message
            destination = mapping['destination']
            await self.forward_message(message, mapping)
            
            logger.info(f"Message forwarded to {destination}: {message_text[:100]}...")
        
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)

    def _get_message_text(self, message: Message) -> str:
        """Extract text content from message, including captions."""
        if message.text:
            return message.text
        elif message.caption:
            return message.caption
        return ""

    def _should_forward_message(self, message: Message, filter: MessageFilter) -> bool:
        """Check if message should be forwarded based on filters."""
        # Get message text (including captions)
        text = self._get_message_text(message)
        
        # Check text-based filters
        if text:
            if not filter._check_keywords(text):
                return False
            
            if not filter._check_regex(text):
                return False
        
        # Check sender
        if hasattr(message, 'sender_id') and message.sender_id:
            if not filter._check_sender(message.sender_id):
                return False
        
        return True

    async def forward_message(self, message: Message, mapping: dict) -> None:
        try:
            destination = mapping['destination']
            logger.debug(f"Attempting to forward message to {destination}")
            
            # Convert string destination to integer if it's a numeric string
            if isinstance(destination, str):
                if destination.startswith('-100'):
                    destination = int(destination)
                elif destination.startswith('-'):
                    # Convert normal group ID to supergroup ID format
                    destination = int('-100' + destination[1:])
                elif destination.isdigit():
                    destination = int(destination)

            try:
                await self.client.send_message(destination, message)
                logger.info(f"Successfully forwarded message to {destination}")
            except Exception as e:
                logger.error(f"Error in first attempt: {str(e)}")
                # Try with PeerChannel for supergroups
                try:
                    # Remove '-100' prefix if present and convert to positive integer
                    channel_id = int(str(abs(destination)).replace('100', '', 1))
                    peer = PeerChannel(channel_id)
                    await self.client.send_message(peer, message)
                    logger.info(f"Successfully forwarded message to peer {destination}")
                except Exception as e2:
                    logger.error(f"Error in second attempt: {str(e2)}")
                    raise

        except Exception as e:
            logger.error(f"Failed to forward message: {str(e)}", exc_info=True)
            # Continue execution even if forwarding fails
            pass

    async def should_forward_message(self, message: Message, mapping: dict) -> bool:
        try:
            # If filtering is disabled, forward all messages
            if not mapping.get('filtering_enabled', False):
                logger.debug("Filtering disabled, forwarding message")
                return True

            message_text = message.message if message.message else ''
            logger.debug(f"Checking message: {message_text}")

            # Convert message to lowercase for case-insensitive comparison
            message_lower = message_text.lower()
            
            # Check keywords_exclude first
            keywords_exclude = [k.lower() for k in mapping.get('keywords_exclude', [])]
            if any(keyword in message_lower for keyword in keywords_exclude):
                logger.debug(f"Message filtered out: contains excluded keyword")
                return False
            
            # Check keywords_include
            keywords_include = [k.lower() for k in mapping.get('keywords_include', [])]
            if keywords_include and not any(keyword in message_lower for keyword in keywords_include):
                logger.debug(f"Message filtered out: no matching include keywords")
                return False

            # Check for number comparison in phrases if configured
            if mapping.get('number_threshold', 0) > 0:
                import re
                # Look for patterns like "Spend X SOL", "Buy X BTC", etc.
                number_matches = re.findall(r'(?:spend|buy|sell|Total Volume    : $)\s+(\d+(?:\.\d+)?)', message_lower)
                if number_matches:
                    numbers = [float(num) for num in number_matches]
                    max_number = max(numbers)
                    if max_number < mapping['number_threshold']:
                        logger.debug(f"Message filtered out: number {max_number} below threshold {mapping['number_threshold']}")
                        return False
                else:
                    logger.debug("No numbers found in message for comparison")

            logger.debug("Message passed all filters")
            return True
        
        except Exception as e:
            logger.error(f"Error in message filtering: {str(e)}", exc_info=True)
            return False

    async def modify_message(self, message: Message, mapping: dict) -> Message:
        """Apply modifications to message."""
        try:
            if not mapping.get('modification_enabled', False):
                return message

            # Get the original text
            text = message.text if message.text else message.caption if message.caption else ""
            
            # Add prefix and suffix
            prefix = mapping.get('prefix', '')
            suffix = mapping.get('suffix', '')
            modified_text = f"{prefix}{text}{suffix}".strip()
            
            # Create a copy of the message with modified text
            if message.text:
                message.text = modified_text
            elif message.caption:
                message.caption = modified_text
            
            logger.debug(f"Modified message: {modified_text}")
            return message
        
        except Exception as e:
            logger.error(f"Error modifying message: {str(e)}", exc_info=True)
            return message

class MultiAccountForwarder:
    """Manages multiple Telegram accounts and their message forwarding."""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        self.session_dir = self.config.get('session_dir', 'sessions')
        self.accounts: Dict[str, TelegramAccount] = {}
        
        # Create sessions directory if it doesn't exist
        os.makedirs(self.session_dir, exist_ok=True)
        
        self._setup_accounts()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def _setup_accounts(self) -> None:
        """Set up all accounts from configuration."""
        for session_name in self.config.get('sessions', []):
            account = TelegramAccount(session_name, self.config)
            self.accounts[session_name] = account
    
    async def start(self) -> None:
        """Start all account clients and set up message handlers."""
        for account in self.accounts.values():
            try:
                await account.start()
                
                # Set up message handlers for each mapping
                for mapping in account.mappings:
                    @account.client.on(events.NewMessage(chats=mapping['source']))
                    async def handler(event, account=account, mapping=mapping):
                        await account.handle_message(event, mapping)
                
                # Add admin command handler for each account
                @account.client.on(events.NewMessage(pattern="/reload"))
                async def command_handler(event):
                    await self.handle_admin_commands(event)
            
            except Exception as e:
                logger.error(f"Error starting account {account.session_name}: {e}")
    
    async def stop(self) -> None:
        """Stop all account clients."""
        for account in self.accounts.values():
            await account.stop()
    
    async def reload_config(self) -> None:
        """Reload configuration and update accounts without restarting."""
        try:
            logger.info("Reloading configuration...")
            
            # Load new config
            new_config = self._load_config(CONFIG_PATH)
            
            # Stop existing accounts
            await self.stop()
            
            # Update config
            self.config = new_config
            self.session_dir = self.config.get('session_dir', 'sessions')
            
            # Clear existing accounts
            self.accounts.clear()
            
            # Setup accounts with new config
            self._setup_accounts()
            
            # Start accounts with new configuration
            await self.start()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Error reloading configuration: {str(e)}", exc_info=True)
            # Try to restart with existing configuration
            await self.start()
            logger.info("Reverted to previous configuration")

    async def handle_admin_commands(self, event) -> None:
        """Handle admin commands like reload."""
        try:
            if event.raw_text == "/reload":
                await self.reload_config()
                await event.respond("Configuration reloaded successfully!")
        except Exception as e:
            logger.error(f"Error handling admin command: {str(e)}", exc_info=True)
            await event.respond(f"Error: {str(e)}")

    def run(self) -> None:
        """Run the forwarder."""
        try:
            logger.info("Starting Telegram Message Forwarder")
            # Create and run event loop properly
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start())
            
            logger.info("Forwarder is now running. Press Ctrl+C to stop.")
            loop.run_forever()
        
        except KeyboardInterrupt:
            logger.info("Stopping Telegram Message Forwarder")
        except Exception as e:
            logger.error(f"Critical error in forwarder: {str(e)}", exc_info=True)
        finally:
            # Properly cleanup
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stop())
            loop.close()
            logger.info("Forwarder stopped.")

def main():
    try:
        forwarder = MultiAccountForwarder(CONFIG_PATH)
        forwarder.run()
    except Exception as e:
        logger.error(f"Failed to initialize forwarder: {str(e)}", exc_info=True)


if __name__ == '__main__':
    main()