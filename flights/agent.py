import datetime
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from pydantic import BaseModel, Field
import requests

from flights.constants import GEMINI_MODEL, GEMINI_MODEL_2
from flights.memory import _load_precreated_itinerary, memorize
from flights.search_flight_tools import get_cities, search_flights_tool



    

source_agent = Agent(
    name="SourceAgent",
    model=GEMINI_MODEL_2,
    instruction="""

You will be given the source city where the user wants to travel from.
call the get_cities tool with the city user has provided.
store the response in source_city variable, using the memorize tool
respond ONLY with the code of the city without any spaces, TRIM any spaces from the response

<source_city>
{source_city}
</source_city>
""",
    tools=[get_cities, memorize],
)

source_tool = AgentTool(agent=source_agent)

destination_agent = Agent(
    name="DestinationAgent",
    model=GEMINI_MODEL_2,
    instruction="""

You will be given the destination city where the user wants to travel to.
call the get_cities tool with the city user has provided.
store the response in destination_city variable, using the memorize tool
respond ONLY with the code of the city without any spaces, TRIM any spaces from the response

<destination_city>
{destination_city}
</destination_city>
""",
    tools=[get_cities, memorize],
)

destination_tool = AgentTool(agent=destination_agent)

number_of_passengers_agent = Agent(
    name="NumberOfPassengersAgent",
    model=GEMINI_MODEL_2,
    instruction="""
Step 1:
Ask the user the number of adults that are willing to travel.
As the number of passengers is provided store it in the session state number_of_adults using the memorize tool

Step 2:
Ask the user the number of children that are willing to travel.
As the number of passengers is provided store it in the session state number_of_children using the memorize tool

Step 3:
Ask the user the number of infants that are willing to travel.
As the number of passengers is provided store it in the session state number_of_infants using the memorize tool

<number_of_adults>
{number_of_adults}
</number_of_adults>

<number_of_children>
{number_of_children}
</number_of_children>

<number_of_infants>
{number_of_infants}
</number_of_infants>
""",
tools=[memorize]
)

number_of_passengers_tool = AgentTool(agent=number_of_passengers_agent)

search_flights_agent = Agent(
    name="SearchFlightsAgent",
    model=GEMINI_MODEL_2,
    instruction="""
You are a helpful agent who can search flights for the user.
use the search_flights_tool to search for flights between the given origin and destination on the given departure and return dates. this will take upto 10 minutes to complete.

""",
 tools=[search_flights_tool]
)

search_flights_agent_tool = AgentTool(agent=search_flights_agent)


root_agent = Agent(
    name="SearchFlights",
    model=GEMINI_MODEL,
    description=(
        "Search Flights for the user"
    ),
    instruction="""
You are a helpful agent who can search flights for the user.

<today_datetime>
{today_datetime}
</today_datetime>

Use today_datetime to calculate the departure and return dates if user tells relative dates.

Step 1:
Begin by asking the user the source city they want to fly from.
As they provide an answer call the source_tool tool to validate and store it

Step 2:
Then ask the user the destination city they want to fly to.
ask they provide with a response call the destination_tool tool to validate it and store it

Step 3:
Then ask the user the date their journey date
As the date is provided store it in ISO format in departure_date variable using memorize tool

For Example:
21 May should be stored as
2025-05-21

Step 4:
Then ask the user if they want to return back to the source city
if yes, then ask the user the return date
As the date is provided store it in ISO format in return_date variable using memorize tool
if no, then store the value in return_date variable as empty string
REMEMBER return_date is optional

For Example:
21 May should be stored as
2025-05-21


Step 5:
Then ask the user the number of adults that are going to travel
store the the value in number_of_adults variable as integer using memorize tool

Step 6:
Then ask the user the number of children that are going to travel
store the the value in number_of_children variable as integer using memorize tool

Step 7:
Then ask the user the number of infants that are going to travel
store the the value in number_of_infants as integer variable using memorize tool

Step 8:
then use the search_flights_agent_tool to search for flights between the given origin and destination on the given departure and return dates. this will take upto 20 seconds to complete.

<source_city>
{source_city}
</source_city>

<destination_city>
{destination_city}
</destination_city>

<departure_date>
{departure_date}
</departure_date>

<return_date>
{return_date}
</return_date>

<number_of_adults>
{number_of_adults}
</number_of_adults>

<number_of_children>
{number_of_children}
</number_of_children>

<number_of_infants>
{number_of_infants}
</number_of_infants>
""",
    tools=[source_tool, destination_tool,  search_flights_agent_tool, memorize],
)