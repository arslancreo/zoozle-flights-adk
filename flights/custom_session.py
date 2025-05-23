from datetime import datetime
from google.adk.sessions import InMemorySessionService, Session
from typing import List, Optional, Dict, Any, TypedDict
import asyncio
import pytz


IST = pytz.timezone("Asia/Kolkata")

class UserPreferences(TypedDict):
    source_city_code: Optional[str]
    destination_city_code: Optional[str]
    departure_date: Optional[str]
    return_date: Optional[str]
    number_of_adults: Optional[int]
    number_of_children: Optional[int]
    number_of_infants: Optional[int]

class CustomSession(Session):
    def __init__(self, app_name: str, user_id: str, session_id: str, state: Optional[Dict[str, Any]] = None):
        # Initialize the base Session class with required fields
        super().__init__(
            id=session_id,  # Use session_id as the id
            app_name=app_name,
            user_id=user_id,
            state=state or {}
        )
        self._preference_changed = asyncio.Event()

        self._last_preferences: UserPreferences = {
            "source_city_code": None,
            "destination_city_code": None,
            "departure_date": None,
            "return_date": None,
            "number_of_adults": None,
            "number_of_children": None,
            "number_of_infants": None,
        }

    def get_preferences(self) -> UserPreferences:
        """
        Get the current user preferences from the session state.

        Returns:
            UserPreferences: Dictionary containing current preferences
        """

        return {
            "source_city_code": self.state.get("source_city_code"),
            "destination_city_code": self.state.get("destination_city_code"),
            "departure_date": self.state.get("departure_date"),
            "return_date": self.state.get("return_date"),
            "number_of_adults": self.state.get("number_of_adults"),
            "number_of_children": self.state.get("number_of_children"),
            "number_of_infants": self.state.get("number_of_infants"),
        }

    async def wait_for_preference_change(self) -> UserPreferences:
        """
        Wait for any user preference to change.

        Returns:
            UserPreferences: Dictionary containing updated preferences
        """
        await self._preference_changed.wait()
        self._preference_changed.clear()
        return self.get_preferences()

    async def wait_for_end_call(self) -> bool:
        """
        Wait for end call signal.

        Returns:
            bool: True when end call is triggered
        """
        await self._end_call_event.wait()
        self._end_call_event.clear()
        return True
    
    
    def update_state(self) -> None:
        """
        Override update_state to detect preference changes and end call.
        Triggers appropriate events when state changes.

        Args:
            state: New state to update
        """
        old_preferences = self._last_preferences
        new_preferences = self.get_preferences()

        print(old_preferences, new_preferences, "*********************************************")

        if old_preferences != new_preferences:
            self._preference_changed.set()
            self._last_preferences = new_preferences
            
class CustomSessionService(InMemorySessionService):
    def create_session(
        self, app_name: str, user_id: str, session_id: str, state: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new session with the given parameters.

        Args:
            app_name: The name of the application
            user_id: The ID of the user
            session_id: The ID of the session
            state: The state of the session
        """ 
        session = CustomSession(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=state
        )
        from flights.memory import _set_initial_states
        session.state["today_datetime"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        _set_initial_states(session.state, session.state)
        
        return session


    