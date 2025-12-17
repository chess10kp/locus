# pyright: reportMissingImports=false
try:
    import python_weather  # pyright: ignore
except ImportError:
    python_weather = None
from core.exceptions import WeatherUnavailableException
import asyncio
import os
from core.config import CITY


async def get_weather():
    # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
    async with python_weather.Client(unit=python_weather.IMPERIAL) as client:
        # fetch a weather forecast from a city
        try:
            weather = await client.get(str(CITY) if CITY else "New York")
        except Exception:
            return "00"

        if not weather:
            raise WeatherUnavailableException("Weather unavailable")

        # returns the current day's forecast temperature (int)
        return weather.temperature


if __name__ == "__main__":
    # see https://stackoverflow.com/questions/45600579/asyncio-event-loop-is-closed-when-getting-loop
    # for more details
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(get_weather())
