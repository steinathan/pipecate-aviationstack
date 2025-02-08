import os
import httpx
import asyncio


async def make_flight_request(flight_iata=None):
    API_KEY = os.getenv("AVIATION_API_KEY")
    if not API_KEY:
        return "Error: AVIATION_API_KEY is not set in environment variables."

    params = {"access_key": API_KEY}
    if flight_iata:
        params["flight_iata"] = flight_iata

    url = "https://api.aviationstack.com/v1/flights"

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()

            api_response = response.json()
            flights = api_response.get("data", [])

            if not flights:
                return f"No data found for flight {flight_iata}."

            results = []
            for flight in flights:
                airline_name = flight["airline"]["name"]
                flight_code = flight["flight"]["iata"]
                departure_airport = flight["departure"]["airport"]
                departure_iata = flight["departure"]["iata"]
                arrival_airport = flight["arrival"]["airport"]
                arrival_iata = flight["arrival"]["iata"]
                flight_status = flight["flight_status"]
                is_grounded = True

                is_live = flight.get("live", {})
                if is_live is not None:
                    is_grounded = is_live.get("is_ground", True)

                status_message = (
                    f"✈️ {airline_name} Flight {flight_code}\n"
                    f"🛫 Departure: {departure_airport} ({departure_iata})\n"
                    f"🛬 Arrival: {arrival_airport} ({arrival_iata})\n"
                    f"📌 Status: {'🟢 In the Air' if not is_grounded else '🔴 On the Ground'} ({flight_status.capitalize()})\n"
                    "---------------------------"
                )
                results.append(status_message)

            return "\n".join(results)

        except httpx.HTTPStatusError as e:
            return f"HTTP error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error parsing API response: {e}"
