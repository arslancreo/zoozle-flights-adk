import os
from dotenv import load_dotenv
import requests
from google.adk.tools import ToolContext
load_dotenv() 

typesense_key = os.getenv("TYPESENSE_KEY")

def get_cities(city: str): 
    response = requests.post("https://search.zoozle.dev/multi_search/", json= {
    "searches": [
          {
            "query_by": "search_terms",
            "num_typos": 1,
            "collection": "airports",
            "q": city,
            "page": 1,
            "per_page": 3,
        }
            ]
        },  headers={
        "x-typesense-api-key":  typesense_key,
        "Content-Type": "application/json"
    })
    print(response, "*********************************************")
    data = response.json()
    return data

def search_flights_tool(tool_context: ToolContext = None):
    """
    Search for flights between the given origin and destination on the given departure and return dates. this will take upto 1minute to complete.

    Args:
        tool_context: Automatically provided by ADK. do not specify when calling.

    Returns:
        List of flight options
    """

    origin = tool_context.state.get("source_city")
    destination = tool_context.state.get("destination_city")
    departure_date = tool_context.state.get("departure_date")
    return_date = tool_context.state.get("return_date")
    return_date = None if return_date is "" else return_date
    adults = int(tool_context.state.get("number_of_adults"))
    children = int(tool_context.state.get("number_of_children"))
    infants = int(tool_context.state.get("number_of_infants"))

    print(adults, children, infants, "*********************************************")

    # Construct the search request payload
    payload = {
        "OriginDestinationInformations": [
            {
                "DepartureDateTime": f"{departure_date}T00:00:00",
                "OriginLocationCode": origin,
                "DestinationLocationCode": destination
            }
        ],
        "TravelPreferences": {
            "MaxStopsQuantity": "All", 
            "VendorPreferenceCodes": [],
            "VendorExcludeCodes": [],
            "Preferences": {
                "CabinClassPreference": {
                    "CabinType": "Y",
                    "PreferenceLevel": "Preferred"
                }
            },
            "AirTripType": "OneWay" if return_date is None or return_date is "" else "Return",
            "Filters": {}
        },
        "PricingSourceType": "All",
        "IsRefundable": False,
        "PassengerTypeQuantities": [],
        "RequestOptions": "Fifty",
        "NearByAirports": True,
        "IsResidentFare": False,
        "Nationality": "",
        "Target": "Test",
        "ConversationId": "string",
        "Provider": "All",
        "IsInfantWithSeat": False
    }

    # Add passenger quantities
    if adults:
        payload["PassengerTypeQuantities"].append({
            "Code": "ADT",
            "Quantity": str(adults)
        })
    if children:
        payload["PassengerTypeQuantities"].append({
            "Code": "CHD", 
            "Quantity": str(children)
        })
    if infants:
        payload["PassengerTypeQuantities"].append({
            "Code": "INF",
            "Quantity": str(infants)
        })

    # Add return flight if specified
    if return_date is not None and return_date is not "":
        payload["OriginDestinationInformations"].append({
            "DepartureDateTime": f"{return_date}T00:00:00",
            "OriginLocationCode": destination,
            "DestinationLocationCode": origin
        })

    # Make the API request
    response = requests.post(
        'https://zoozle.dev/api/v5/booking/flight/search/?page=1&limit=5',
        headers={
            'Content-Type': 'application/json',
        },
        json=payload
    )

    response_json = response.json()
    if response_json.get("status") == "success":
        return response_json["Data"]["PricedItineraries"][:5]
    else:
        return response_json
    