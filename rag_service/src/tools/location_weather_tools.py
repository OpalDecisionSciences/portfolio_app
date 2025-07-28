"""
LangChain tools for restaurant location and weather information.
"""
import json
import logging
import requests
from typing import Dict, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LocationWeatherInput(BaseModel):
    """Input for location and weather tools."""
    restaurant_id: str = Field(description="UUID of the restaurant")
    user_latitude: float = Field(description="User's latitude coordinate")
    user_longitude: float = Field(description="User's longitude coordinate")


class GetRestaurantDistanceWeatherTool(BaseTool):
    """Tool to get distance and weather information for a restaurant."""
    
    name = "get_restaurant_distance_weather"
    description = """
    Get the distance from user to restaurant and current weather at restaurant location.
    Use this when user asks about:
    - How far is the restaurant?
    - What's the weather like there?
    - Should I visit today based on weather?
    - Distance and weather information
    
    Input should include restaurant_id, user_latitude, and user_longitude.
    """
    args_schema = LocationWeatherInput
    
    def __init__(self, django_base_url: str = "http://web:8000"):
        super().__init__()
        self.django_base_url = django_base_url.rstrip('/')
    
    def _run(
        self, 
        restaurant_id: str, 
        user_latitude: float, 
        user_longitude: float,
        **kwargs
    ) -> str:
        """Get distance and weather data for restaurant."""
        try:
            # Call Django API endpoint
            url = f"{self.django_base_url}/restaurants/api/{restaurant_id}/location-weather/"
            
            payload = {
                "user_lat": user_latitude,
                "user_lng": user_longitude
            }
            
            response = requests.post(
                url, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_location_weather_response(data)
            else:
                error_msg = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', 'Unknown error')}"
                except:
                    pass
                return f"Sorry, I couldn't get the location and weather information. {error_msg}"
                
        except requests.RequestException as e:
            logger.error(f"Error calling location/weather API: {str(e)}")
            return "Sorry, I couldn't retrieve the location and weather information due to a connection error."
        except Exception as e:
            logger.error(f"Error in location/weather tool: {str(e)}")
            return "Sorry, there was an error getting the location and weather information."
    
    def _format_location_weather_response(self, data: Dict[str, Any]) -> str:
        """Format the API response into a natural language response."""
        restaurant_name = data.get('restaurant_name', 'the restaurant')
        location = data.get('restaurant_location', {})
        distance = data.get('distance', {})
        weather = data.get('weather', {})
        
        response_parts = []
        
        # Add restaurant location context
        if location.get('city') and location.get('country'):
            response_parts.append(f"{restaurant_name} is located in {location['city']}, {location['country']}.")
        
        # Add distance information
        if distance.get('status') == 'calculated' or distance.get('status') == 'geocoded':
            km = distance.get('kilometers', 0)
            miles = distance.get('miles', 0)
            
            if km < 1:
                distance_text = f"It's very close - only {km} km ({miles} miles) away"
            elif km < 5:
                distance_text = f"It's nearby - about {km} km ({miles} miles) away"
            elif km < 20:
                distance_text = f"It's {km} km ({miles} miles) away"
            else:
                distance_text = f"It's {km} km ({miles} miles) away - quite a journey!"
            
            response_parts.append(distance_text)
        elif distance.get('status') == 'geocoding_failed':
            response_parts.append("I couldn't calculate the exact distance.")
        
        # Add weather information
        if weather.get('status') == 'success':
            temp = weather.get('temperature')
            description = weather.get('description', 'unknown conditions')
            feels_like = weather.get('feels_like')
            humidity = weather.get('humidity')
            
            weather_text = f"The current weather there is {description.lower()} with a temperature of {temp}°C"
            
            if feels_like and abs(feels_like - temp) > 2:
                weather_text += f" (feels like {feels_like}°C)"
            
            if humidity:
                if humidity > 80:
                    weather_text += f", quite humid at {humidity}%"
                elif humidity < 30:
                    weather_text += f", quite dry at {humidity}% humidity"
            
            # Add weather advice
            if temp < 0:
                weather_text += ". Bundle up - it's freezing!"
            elif temp < 10:
                weather_text += ". You'll want a warm coat."
            elif temp > 30:
                weather_text += ". Perfect weather for outdoor dining!"
            elif temp > 25:
                weather_text += ". Great weather for a meal out!"
            elif 'rain' in description.lower():
                weather_text += ". You might want to bring an umbrella or plan for indoor seating."
            elif 'sun' in description.lower() or 'clear' in description.lower():
                weather_text += ". Beautiful weather for dining!"
            
            response_parts.append(weather_text)
            
        elif weather.get('status') == 'no_api_key':
            response_parts.append("Weather information is not currently available.")
        elif weather.get('status') == 'error':
            response_parts.append("I couldn't get the current weather information.")
        
        # Combine all parts
        if response_parts:
            return " ".join(response_parts)
        else:
            return f"I found {restaurant_name} but couldn't get detailed location and weather information."


class WeatherAdviceTool(BaseTool):
    """Tool to provide weather-based dining advice."""
    
    name = "get_weather_dining_advice"
    description = """
    Provide dining advice based on weather conditions at restaurant location.
    Use this when user asks about:
    - Should I dine outside/on the terrace?
    - What should I wear to the restaurant?
    - Is it good weather for dining?
    - Weather-based recommendations
    """
    args_schema = LocationWeatherInput
    
    def __init__(self, django_base_url: str = "http://web:8000"):
        super().__init__()
        self.django_base_url = django_base_url.rstrip('/')
    
    def _run(
        self, 
        restaurant_id: str, 
        user_latitude: float, 
        user_longitude: float,
        **kwargs
    ) -> str:
        """Provide weather-based dining advice."""
        try:
            # Get weather data first
            url = f"{self.django_base_url}/restaurants/api/{restaurant_id}/location-weather/"
            payload = {"user_lat": user_latitude, "user_lng": user_longitude}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code != 200:
                return "I couldn't get weather information to provide dining advice."
            
            data = response.json()
            weather = data.get('weather', {})
            restaurant_name = data.get('restaurant_name', 'the restaurant')
            
            if weather.get('status') != 'success':
                return "Weather information isn't available right now for dining advice."
            
            return self._generate_dining_advice(weather, restaurant_name)
            
        except Exception as e:
            logger.error(f"Error in weather advice tool: {str(e)}")
            return "Sorry, I couldn't get weather information for dining advice."
    
    def _generate_dining_advice(self, weather: Dict[str, Any], restaurant_name: str) -> str:
        """Generate weather-based dining advice."""
        temp = weather.get('temperature', 0)
        description = weather.get('description', '').lower()
        wind_speed = weather.get('wind_speed', 0)
        humidity = weather.get('humidity', 0)
        
        advice_parts = []
        
        # Temperature-based advice
        if temp < 5:
            advice_parts.append("It's quite cold outside - I'd recommend indoor seating for comfort.")
        elif temp < 15:
            advice_parts.append("It's a bit chilly - indoor seating would be cozy, but outdoor seating could work with a jacket.")
        elif temp < 25:
            advice_parts.append("The temperature is pleasant - either indoor or outdoor seating would be comfortable!")
        elif temp < 30:
            advice_parts.append("Perfect weather for outdoor dining! The terrace or patio would be lovely.")
        else:
            advice_parts.append("It's quite warm - you might prefer indoor seating with air conditioning, or a shaded outdoor area.")
        
        # Weather condition advice
        if 'rain' in description or 'storm' in description:
            advice_parts.append("There's rain in the area - definitely go for indoor seating.")
        elif 'snow' in description:
            advice_parts.append("It's snowing - indoor seating will be much more comfortable.")
        elif 'sun' in description or 'clear' in description:
            advice_parts.append("Beautiful clear weather - perfect for enjoying any outdoor dining options!")
        elif 'cloud' in description:
            advice_parts.append("Overcast conditions - still good for outdoor dining without too much sun glare.")
        
        # Wind advice
        if wind_speed > 20:  # km/h
            advice_parts.append("It's quite windy - indoor seating might be more comfortable.")
        
        # Clothing advice
        clothing_advice = []
        if temp < 10:
            clothing_advice.append("Bring a warm coat")
        elif temp < 20:
            clothing_advice.append("A light jacket would be smart")
        elif temp > 25:
            clothing_advice.append("Light, breathable clothing is recommended")
        
        if 'rain' in description:
            clothing_advice.append("bring an umbrella")
        
        if clothing_advice:
            advice_parts.append(f"For attire: {', and '.join(clothing_advice)}.")
        
        return f"For dining at {restaurant_name}: {' '.join(advice_parts)}"


# Tool instances for easy import
def get_location_weather_tools(django_base_url: str = "http://web:8000"):
    """Get all location and weather tools."""
    return [
        GetRestaurantDistanceWeatherTool(django_base_url),
        WeatherAdviceTool(django_base_url)
    ]