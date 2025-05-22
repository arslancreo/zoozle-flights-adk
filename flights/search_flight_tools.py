import os
from dotenv import load_dotenv
import requests
from google.adk.tools import ToolContext

from flights.custom_session import CustomSession
load_dotenv() 

typesense_key = os.getenv("TYPESENSE_KEY")

def get_cities(city: str): 
    """
    This tool is used to get the cities from the typesense database.
    Args:
        city: The city to search for.
    Returns:
        A list of cities.
    """

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

    data = response.json()
    return data

def _build_payload(tool_context: ToolContext):
    """
    Build the payload for the search flights tool.
    """

    origin = tool_context.state.get("source_city_code")
    destination = tool_context.state.get("destination_city_code")
    departure_date = tool_context.state.get("departure_date")
    return_date = tool_context.state.get("return_date")
    return_date = return_date if return_date else None
    adults = int(tool_context.state.get("number_of_adults"))
    children = int(tool_context.state.get("number_of_children") or 0)
    infants = int(tool_context.state.get("number_of_infants") or 0)

    print(origin, destination, departure_date, return_date, adults, children, infants, "--------------------------------------------------")

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
            "AirTripType": "OneWay" if return_date is None else "Return",
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
    if return_date is not None and not return_date:
        payload["OriginDestinationInformations"].append({
            "DepartureDateTime": f"{return_date}T00:00:00",
            "OriginLocationCode": destination,
            "DestinationLocationCode": origin
        })
    
    return payload


def search_flights_tool(tool_context: ToolContext = None):
    """
    Search for flights between the given origin and destination on the given departure and return dates. this will take upto 1minute to complete.

    Args:
        tool_context: Automatically provided by ADK. do not specify when calling.

    Returns:
        Dict[str, str]: A dictionary of key-value pairs.
            -status: A status message.
            -no_of_flights: The number of flights found.
            -lowest_price_trip: The lowest price trip. 
                -here for price you have to check AirItineraryPricingInfo.ItinTotalFare.TotalPriceAfterDiscount.Amount (in INR)

    """

    if not tool_context.state.get("source_city_code") or not tool_context.state.get("destination_city_code") or not tool_context.state.get("departure_date") or not tool_context.state.get("number_of_adults"):
        return {
            "status": "error",
            "message": "Please provide atleast the source city code, destination city code, departure date and number of adults"
        }

    payload = _build_payload(tool_context)

    # Make the API request
    response = requests.post(
        'https://zoozle.dev/api/v5/booking/flight/search/?page=1&limit=1',
        headers={
            'Content-Type': 'application/json',
        },
        json=payload
    )

    response_json = response.json()

    print(response_json, "=========================================================")

    state = tool_context.state
    
    state["facets"] = response_json.get("facets", {})
    state["airline_code_map"] = response_json.get("airline_info", {})
    state["airport_code_map"] = response_json.get("airport_info", {})

    if response_json.get("Success") == True:
        return {
            "status": "success",
            "no_of_flights": response_json.get("count", 0),
            "lowest_price_trip": response_json.get("Data", {}).get("PricedItineraries", [])[0]
        }
    else:
        return {
            "status": "error",
            "message": response_json.get("message", "Something went wrong Please try again later")
        }
    
def get_filters(tool_context: ToolContext):
    """
    Get the filters for the search flights tool.
    
    Args:
        tool_context: The ADK tool context.

    Returns:
        Dict[str, str]: 
            -facets: A dictionary of facets.
            -airline_code_map: A dictionary of airline code map.
            -airport_code_map: A dictionary of airport code map.

    """
    state = tool_context.state

    data = {
        "facets": state.get("facets", {}),
        "airline_code_map": state.get("airline_code_map", {}),
        "airport_code_map": state.get("airport_code_map", {})
    }

    return data
    

def apply_filters_on_search_results(filters: dict, tool_context: ToolContext):
    """
    Apply filters on the search results.
    Args:
        filters: A dictionary of filters to apply. (example:{"no_of_stops": ["Direct", "One Stop"], "timings": "departure_from_BLR_airport_12:00 - 18:00 (12 PM - 6 PM) "})
                 - the field_name should be the same as the field_name in the facets.
                 - if you want to apply multiple filters, you can send a list of filters.
                 - value should also be taken from the related field_name in the facets. (its inside the counts[])


        tool_context: The ADK tool context.
    Returns:
        Dict[str, str]: A dictionary of key-value pairs.
            -status: A status message.
            -no_of_flights: The number of flights found.
    """

    print(filters, "\n\n\n--------------------------------------------------\n\n\n")

    url = f'https://zoozle.dev/api/v5/booking/flight/search/?page=1&limit=1'

    for key, value in filters.items():
        url+=f'&{key}={",".join(value)}' if isinstance(value, list) else f'&{key}={value}'

    print(url, "--------------------------------------------------")
    
    payload = _build_payload(tool_context)

    response = requests.post(
        url,
        headers={
            'Content-Type': 'application/json',
        },
        json=payload
    )

    response_json = response.json()

    if response_json.get("Success") == True:
        return {
            "status": "success",
            "no_of_flights": response_json.get("count", 0),
            "lowest_price_trip": response_json.get("Data", {}).get("PricedItineraries", [])[0]
        }
    else:
        return {
            "status": "error",
            "message": response_json.get("message", "Something went wrong Please try again later")
        }

def confirm_flight_tool(tool_context: ToolContext):
    """
    Confirm flight availability and pricing using the fare source code.
    
    Args:
        fare_source_code: The fare source code for the flight
        tool_context: Tool context containing conversation info
        
    Returns:
        Response from the revalidation API
    """
    state = tool_context.state

    if not state.get("fare_source_code"):
        return {
            "status": "error",
            "message": "I cannot confirm the flight without fare source code"
        }

    payload = {
        "FareSourceCode": state.get("fare_source_code"),
    }

    response = requests.post(
        'https://zoozle.dev/api/v5/booking/flight/revalidate/',
        params={'create_booking': False},
        headers={
            'Content-Type': 'application/json',
        },
        json=payload
    )

    response_json = response.json()

    state["airline_code_map"] = response_json.get("airline_info", {})
    state["airport_code_map"] = response_json.get("airport_info", {})
    state["required_fields_to_book"] = response_json.get("Data", {}).get("PricedItineraries", [{}])[0].get("RequiredFieldsToBook", []) or ["Email","Title","ContactNumber"]
    state["ask_for_passenger_details"] = True
    
    session = tool_context._invocation_context.session
    if isinstance(session, CustomSession):
        session.update_state()

    if response_json.get("Success") == True:
        return response_json.get("Data", {}).get("PricedItineraries", [])[0]
    else:
        return response_json

def book_flight(tool_context: ToolContext):
    """
    Book the flight using the fare source code.
    """
    session = tool_context._invocation_context.session
    passenger_details = tool_context.state.get("passenger_details", {})
    if not passenger_details:
        return {
            "status": "error",
            "message": "I cannot book the flight without passenger details"
        }
    
    payload = {
        "FareSourceCode": tool_context.state.get("fare_source_code"),
    }

    response = requests.post(
        'https://zoozle.dev/api/v5/booking/flight/revalidate/',
        params={'create_payment': True, 'create_booking': True},
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'{tool_context.state.get("token")}'
        },
        json=payload
    )

    if not response.json().get("Success"):
        return {
            "status": "error",
            "message": response.json().get("message", "Something went wrong Please try again later")
        }
    
    print("--------------------------book flight response-------------------", response.json())
    fare_source_code = response.json().get("Data", {}).get("PricedItineraries", [])[0].get("AirItineraryPricingInfo", {}).get("FareSourceCode", "")

    payload = {
        "FareSourceCode": fare_source_code,
        "TravelerInfo": passenger_details
    }

    print("--------------------------book flight payload-------------------", payload)

    response = requests.post(
        'https://zoozle.dev/api/v5/booking/flight/book/',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'{tool_context.state.get("token")}'
        },
        json=payload
    )
    print("--------------------------book flight response-------------------", response.status_code, response.json())

    if response.status_code not in [200, 201]:
        return {
            "status": "error",
            "message": response.json()
        }

    session.state["payment_data"] = response.json().get("payment_data", {})
    session.state["ask_for_payment"] = True
    session.state["payment_status"] = "pending"
    if isinstance(session, CustomSession):
        session.update_state()

    return {
        "status": "success",
        "message": "Payment is pending, please make the payment to complete the booking"
    }
