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
from flights.search_flight_tools import apply_filters_on_search_results, book_flight, confirm_flight_tool, get_cities, get_filters, search_flights_tool



    

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

        Note: 
        - return date is optional

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

        Whatever you generate will be converted to speech and sent to the user. So text should be able to be converted to speech and should be more like a human.

        Tools Available:
            - get_cities: to get the iata code of the city
            - search_flights_tool: to search for flights
            - memorize: to store the state
            - get_filters: to get the filters available for the search results
            - apply_filters_on_search_results: to apply the filters on the search results

        <today_datetime>
        {today_datetime}
        </today_datetime>

        Use today_datetime to calculate the departure and return dates if user tells relative dates.

        Step 1:
            Begin by asking the user the source city they want to fly from.
            As they provide an answer call the get_cities tool to validate it get iata_code and store it in state using memorize tool

        Step 2:
            Then ask the user the destination city they want to fly to.
            As they provide an answer call the get_cities tool to validate it get iata_code and store it in state using memorize tool

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
            then use the search_flights_tool to search for flights between the given origin and destination 
            on the given departure and return dates. this will take upto 20 seconds to complete.

        Step 9:
            if user asks for more detail check the result of the search_flights_tool and respond with relevant details
            if user asks to filter the result check the filters available using tool get_filters and then use the apply_filters_on_search_results tool to apply the filters on the search results to get user desired results
             - you should user field_name as the key and value should be from one of the counts[]. if more than one value for a key send it in list format

        Step 10:
            make the user to select the flight they want to book, store the FareSourceCode with the key fare_source_code in state using memorize tool

    
        Step 11:
            confirm the flight using the confirm_flight_tool and its not the end of the booking process.

        Step 12: 
            ask the user for the details to book the flight, you should just tell them to provide the details and you should not ask for the details, 
            user will type the details and he will say its done. after that you have to call book_flight tool to book the flight. and wait for the user to complete the payment.


        Note:
            - return date is optional
            - if user provide all the input in one go, do not follow the steps in the order, got to relevant step and ask the user the question. In this case use memorize tool to store the input in state with multiple calls
              (for example if user says from bengaluru to delhi on 21 may for one adult, do not ask for number of children, infants, return date, etc just take confirmation and call the search_flights_tool)
            - take confirmation from the user before moving to next step

        <source_city_code>
        {source_city_code}
        </source_city_code>

        <destination_city_code>
        {destination_city_code}
        </destination_city_code>

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
    tools=[get_cities,  search_flights_tool, memorize, get_filters, apply_filters_on_search_results, confirm_flight_tool, book_flight],
)
