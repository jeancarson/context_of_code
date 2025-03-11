"""
State Toggle API for interacting with the server's state toggle system.
This module provides a clean interface for checking and handling state changes.
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
import time

logger = logging.getLogger(__name__)

class StateAPI:
    """Class for interacting with the state toggle system"""
    
    def __init__(self, base_url: str):
        """
        Initialize the StateAPI
        
        Args:
            base_url: The base URL of the server
        """
        self.base_url = base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_checked_timestamp: Optional[str] = None
        self._action_handlers: Dict[str, Callable] = {}
        self._last_action_time = 0  # Track when the last action was performed
        self._debounce_seconds = 5  # Default debounce time
        self._last_state_value = None  # Track the last state value
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        logger.info("StateAPI closed via context manager")
        
    async def connect(self):
        """Create a new session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            logger.info("StateAPI connected")
            
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("StateAPI session closed")
            
    def _ensure_session(self):
        """Ensure we have an active session"""
        if self._session is None or self._session.closed:
            raise RuntimeError("Session is not initialized. Call connect() first or use as async context manager.")
            
    def register_action_handler(self, state_value: str, handler: Callable):
        """
        Register a handler to be called when the state changes to a specific value
        
        Args:
            state_value: The state value to trigger the handler for.
                         Use "*" to trigger the handler for any state change.
            handler: The function to call when the state changes to the specified value
        """
        logger.info(f"Registering handler for state '{state_value}'")
        self._action_handlers[state_value] = handler
        
    def set_debounce_time(self, seconds: int):
        """
        Set the debounce time for actions
        
        Args:
            seconds: The number of seconds to wait between actions
        """
        self._debounce_seconds = seconds
        logger.info(f"Set action debounce time to {seconds} seconds")
        
    async def check_state(self) -> Optional[Dict[str, Any]]:
        """
        Check the current state from the server
        
        Returns:
            The state object or None if there was an error
        """
        self._ensure_session()
        
        try:
            async with self._session.get(f"{self.base_url}/check-state") as response:
                if response.status == 200:
                    state = await response.json()
                    return state
                else:
                    logger.error(f"Error checking state: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Exception checking state: {e}")
            return None
            
    async def handle_state_change(self):
        """
        Check for state changes and execute the appropriate handler if a change is detected.
        This method is more responsive to state changes and includes debounce handling.
        """
        try:
            state = await self.check_state()
            if not state or 'value' not in state:
                return
            
            current_state_value = state['value']
            current_time = time.time()
            
            # Check if the state has changed since the last check
            if self._last_state_value is not None and current_state_value != self._last_state_value:
                logger.info(f"State changed from {self._last_state_value} to {current_state_value}")
                
                # Check if enough time has passed since the last action (debounce)
                if current_time - self._last_action_time >= self._debounce_seconds:
                    # Check for wildcard handler first
                    if "*" in self._action_handlers:
                        logger.info(f"Executing wildcard handler for state change to {current_state_value}")
                        self._action_handlers["*"]()
                        self._last_action_time = current_time
                    # Then check for specific state handler
                    elif current_state_value in self._action_handlers:
                        logger.info(f"Executing handler for state {current_state_value}")
                        self._action_handlers[current_state_value]()
                        self._last_action_time = current_time
                    else:
                        logger.info(f"No handler registered for state {current_state_value}")
                else:
                    logger.info(f"Debouncing action for state {current_state_value} " +
                               f"({current_time - self._last_action_time:.2f}s < {self._debounce_seconds}s)")
            
            # Update the last state value and timestamp
            self._last_state_value = current_state_value
            self._last_checked_timestamp = state.get('timestamp')
            
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
        
    async def monitor_state(self, interval_seconds: float = 0.5):
        """
        Continuously monitor the state and execute handlers when changes are detected
        
        Args:
            interval_seconds: How often to check the state (in seconds)
        """
        self._ensure_session()
        
        logger.info(f"Starting state monitoring (interval: {interval_seconds}s)")
        
        try:
            while True:
                try:
                    await self.handle_state_change()
                except Exception as e:
                    logger.error(f"Error in state monitoring: {e}")
                    
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("State monitoring cancelled")
            raise  # Re-raise to propagate cancellation