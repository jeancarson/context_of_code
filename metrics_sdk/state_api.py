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
        Register a handler function for a specific state value
        
        Args:
            state_value: The state value to trigger this handler (e.g., "B")
            handler: The function to call when this state is detected
        """
        self._action_handlers[state_value] = handler
        logger.info(f"Registered handler for state '{state_value}'")
        
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
        Check for state changes and execute the appropriate handler
        
        Returns:
            True if a handler was executed, False otherwise
        """
        state = await self.check_state()
        
        if not state or not state.get("value") or not state.get("timestamp"):
            return False
            
        # Get the current state value
        current_state_value = state["value"]
        
        # Check if this is a new state change
        if (self._last_checked_timestamp is None or 
                state["timestamp"] > self._last_checked_timestamp):
            
            # Update the last checked timestamp
            self._last_checked_timestamp = state["timestamp"]
            
            # Check if the state value has changed
            if current_state_value != self._last_state_value:
                logger.info(f"State changed from {self._last_state_value} to {current_state_value}")
                
                # Get the handler for this state value
                handler = self._action_handlers.get(current_state_value)
                
                if handler:
                    # Check debounce
                    current_time = time.time()
                    if current_time - self._last_action_time >= self._debounce_seconds:
                        # Execute the handler
                        logger.info(f"Executing handler for state '{current_state_value}'")
                        try:
                            handler()
                            self._last_action_time = current_time
                            # Update the last state value
                            self._last_state_value = current_state_value
                            return True
                        except Exception as e:
                            logger.error(f"Error executing handler for state '{current_state_value}': {e}")
                    else:
                        logger.info(f"Skipping action due to debounce ({self._debounce_seconds}s)")
            
            # Always update the last state value, even if no handler was executed
            self._last_state_value = current_state_value
                    
        return False
        
    async def monitor_state(self, interval_seconds: float = 1.0):
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