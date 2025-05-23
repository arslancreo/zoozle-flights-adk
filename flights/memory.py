# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The 'memorize' tool for several agents to affect session states."""

from datetime import datetime
import json
import os
import time
from typing import Dict, Any, Tuple

from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions.state import State
from google.adk.tools import ToolContext

from flights import constants
from flights.custom_session import CustomSession

SAMPLE_SCENARIO_PATH = os.getenv(
    "PREFERENCES", "flights/preferences.json"
)


def memorize(key: str, value: str, tool_context: ToolContext):
    """
    Memorize pieces of information, one key-value pair at a time.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be stored.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    mem_dict[key] = value.strip()
    session = tool_context._invocation_context.session
    
    if isinstance(session, CustomSession):
        session.update_state()

    return {"status": f'Stored "{key}": "{value}"'}

def get_state(key: str, tool_context: ToolContext):
    return tool_context.state[key]


def forget(key: str, value: str, tool_context: ToolContext):
    """
    Forget pieces of information.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be removed.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    if tool_context.state[key] is None:
        tool_context.state[key] = []
    if value in tool_context.state[key]:
        tool_context.state[key].remove(value)
    return {"status": f'Removed "{key}": "{value}"'}


def _set_initial_states(source: Dict[str, Any], target: State | dict[str, Any]):
    """
    Setting the initial session state given a JSON object of states.

    Args:
        source: A JSON object of states.
        target: The session state object to insert into.
    """


    
    target["source_city_code"] = target.get("source_city_code") or source.get("source_city_code", "")
    target["destination_city_code"] = target.get("destination_city_code") or source.get("destination_city_code", "")
    target["departure_date"] = target.get("departure_date") or source.get("departure_date", "")
    target["return_date"] = target.get("return_date") or source.get("return_date", "")
    target["number_of_adults"] = target.get("number_of_adults") or source.get("number_of_adults", "")
    target["number_of_children"] = target.get("number_of_children") or source.get("number_of_children", "")
    target["number_of_infants"] = target.get("number_of_infants") or source.get("number_of_infants", "")

    



def _load_precreated_itinerary(callback_context: CallbackContext):
    """
    Sets up the initial state.
    Set this as a callback as before_agent_call of the root_agent.
    This gets called before the system instruction is contructed.

    Args:
        callback_context: The callback context.
    """    

    data = {}
    with open(SAMPLE_SCENARIO_PATH, "r") as file:
        print(file)
        data = json.load(file)
        print(f"\nLoading Initial State: {data}\n")

    _set_initial_states(data["state"], callback_context.state)