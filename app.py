import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, request, jsonify
import requests
import polyline
from datetime import datetime
import openai
from transformers import BertTokenizer
from geopy.geocoders import Nominatim
import openai
import google.generativeai as genai
import os
from io import BytesIO
import base64
import qrcode

from supabase import create_client, Client
load_dotenv()

# Initialize Supabase client
url = os.getenv("SUPABASE_PROJECT_URL")
key = os.getenv("SUPABASE_PUBLIC_API_KEY")
supabase: Client = create_client(url, key)

genai.configure(api_key=env.get('GEMINI_API_KEY'))
# Create the model
# See https://ai.google.dev/api/python/google/generativeai/GenerativeModel
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "application/json",
}

if ENV_FILE := find_dotenv():
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")

openai.api_key = env.get("OPENAI_API_KEY")
oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
)

def truncate_text(text, max_tokens=15000):
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')  # replace 'bert-base-uncased' with a model that suits your needs
    tokens = tokenizer.encode(text, return_tensors='pt')[0]
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        text = tokenizer.decode(tokens)
    return text

# Controllers API
@app.route("/")
def home():
    return render_template(
        "welcome.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )


@app.route("/home")
def test():
    given_name = ''
    if 'user' in session and 'userinfo' in session['user']:
        given_name = session['user']['userinfo'].get('given_name', '')
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
        google_maps_key=env.get("GOOGLE_API_KEY"),
        given_name=given_name
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    user_info = token['userinfo']
    print(user_info)
    user_id = user_info['sub']
    session["user_id"] = user_id

    return redirect("/home")


@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    start = data.get('start')
    end = data.get('end')

    print(f"Start Location: {start}")
    print(f"End Location: {end}")

    if not start or not end:
        return jsonify({'error': 'Missing start or end location'}), 400

    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial&origins={start}&destinations={end}&mode=bicycling&key={env.get('GOOGLE_API_KEY')}"

    response = requests.get(url)
    data = response.json()

    distance = data.get('rows', [])[0].get('elements', [])[0].get('distance', {}).get('text', 'unknown')

    session['start'] = start
    session['end'] = end

    return jsonify({
        'start': start,
        'end': end,
        'distance': distance
    })

@app.route("/directions")
def directions():
    start = session.get('start')
    end = session.get('end')
    return render_template(
        "directions.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
        google_maps_key=env.get("GOOGLE_API_KEY"),
        start=start,
        end=end
    )

@app.route('/route_info', methods=['GET'])
def route_info():
    start = session.get('start')
    end = session.get('end')

    # Initialize data
    directions_data = places_data = elevation_data = weather_data = traffic_data = roadworks_data = None

    try:
        # Get route from Google Directions API
        directions_response = requests.get(f'https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&key={env.get("GOOGLE_API_KEY")}')
        directions_data = directions_response.json()
        print("Directions Data:", directions_data)
        # Check if the response contains the expected data
        if 'routes' not in directions_data or not directions_data['routes']:
            return jsonify({'error': 'No routes found from Google Directions API'})

        # Get points of interest near the midpoint from Google Places API
        mid_index = len(directions_data['routes'][0]['legs'][0]['steps']) // 2
        mid_step = directions_data['routes'][0]['legs'][0]['steps'][mid_index]
        mid_point = polyline.decode(mid_step['polyline']['points'])[0]

        places_response = requests.get(f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={mid_point[0]},{mid_point[1]}&radius=5000&key={env.get("GOOGLE_API_KEY")}')
        places_json = places_response.json()
        places_data = places_json.get('results', [])[:20]
        print("Places Data:", places_data)

        # Get latitude and longitude of start location from Google Geocoding API
        geocoding_response = requests.get(f'https://maps.googleapis.com/maps/api/geocode/json?address={start}&key={env.get("GOOGLE_API_KEY")}')
        geocoding_data = geocoding_response.json()
        start_lat = geocoding_data['results'][0]['geometry']['location']['lat']
        start_lng = geocoding_data['results'][0]['geometry']['location']['lng']
        # Get latitude and longitude of end location from Google Geocoding API
        geocoding_response_end = requests.get(f'https://maps.googleapis.com/maps/api/geocode/json?address={end}&key={env.get("GOOGLE_API_KEY")}')
        geocoding_data_end = geocoding_response_end.json()
        end_lat = geocoding_data_end['results'][0]['geometry']['location']['lat']
        end_lng = geocoding_data_end['results'][0]['geometry']['location']['lng']

        # Get elevation data from Google Elevation API
        elevation_response = requests.get(f'https://maps.googleapis.com/maps/api/elevation/json?path=enc:{polyline.encode([(start_lat, start_lng), (end_lat, end_lng)])}&samples=100&key={env.get("GOOGLE_API_KEY")}')
        elevation_data = elevation_response.json()

        # Calculate average elevation
        elevations = [result['elevation'] for result in elevation_data['results']]
        average_elevation = sum(elevations) / len(elevations)
        print("Elevation Data:", elevation_data)

        # Get weather data from OpenWeatherMap API
        weather_response = requests.get(f'http://api.openweathermap.org/data/2.5/weather?lat={start_lat}&lon={start_lng}&appid={env.get("OPENWEATHERMAP_API_KEY")}')
        weather_data = weather_response.json()

        # Get traffic data from Bing Maps API
        traffic_response = requests.get(f'http://dev.virtualearth.net/REST/v1/Traffic/Incidents/{start_lat},{start_lng}?key={env.get("BING_MAPS_API_KEY")}')
        traffic_data = traffic_response.json()
        print("Traffic Data:", traffic_data)

        # Get roadworks data from Sydney Roadwork API
        roadworks_response = requests.get(
            'https://api.transport.nsw.gov.au/v1/live/hazards/roadwork/all',
            headers={'Authorization': f'Bearer {env.get("SYDNEY_API_KEY")}'},
        )
        roadworks_data = roadworks_response.json()
        print("Roadworks Data:", roadworks_data)

    except Exception as e:
        return jsonify({'error': str(e)})

    # Calculate health metrics
    distance = directions_data['routes'][0]['legs'][0]['distance']['value'] / 1000  # Distance in km
    calories_burned = distance * 50  # Rough estimate of calories burned per km

    user_id = session.get('user_id')
    
    # Retrieve the user's health data from Supabase
    health_data_response = supabase.table('user_health_data').select('health_data').eq('user_id', user_id).order('created_at', desc=True).limit(1).execute()
    health_data = health_data_response.data[0]['health_data'] if health_data_response.data else ''
    
    # Prepare the data for the Gemini API
    data = f"I have collected the following data for a route from {start} to {end}. Can you summarize this information with a focus on health benefits of cycling? What about cycling on this route given its elevation? Give as much information about these as possible. Talk about the weather. Talk about the traffic. Give a fun fact about cycling as well. Format your response in plain English. Your response must be separeted into paragraphs: {directions_data}, {places_data}, {elevation_data}, {weather_data}, {traffic_data}, {roadworks_data}. Also, consider the following health data for the user if it is available: {health_data}."
    
    # Truncate the data to fit within the token limit
    # data = truncate_text(data)

    # Generate a summary with Gemini 1.5 Flash
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        # safety_settings = Adjust safety settings
        # See https://ai.google.dev/gemini-api/docs/safety-settings
    )

    response_text = model.generate_content(data).candidates[0].content.parts[0].text
    print("AI-generated response:", response_text)

    # Split the response text into paragraphs and wrap each with <p> tags
    try:
        response_json = json.loads(response_text)
        response_html = ''.join(f'<p>{value}</p>' for value in response_json.values())
    except json.JSONDecodeError:
        response_html = ''.join(f'<p>{line.strip()}</p>' for line in response_text.split('\n') if line.strip())

    # Get the user ID from the session
    user_id = session.get('user_id')

    # Store the additional data in Supabase
    supabase_data = {
        'user_id': user_id,
        'start': start,
        'end': end,
        'elevation': int(average_elevation),
        'weather': weather_data,
        'traffic': traffic_data,
        'roadworks': roadworks_data,
        'calories_burned': int(calories_burned),
        'response': response_html
    }
    supabase.table('trips').insert(supabase_data).execute()

    return jsonify({
        'start': start,
        'end': end,
        'elevation': int(average_elevation),
        'weather': weather_data,
        'traffic': traffic_data,
        'roadworks': roadworks_data,
        'calories_burned': int(calories_burned),
        'response': response_html,
    })

@app.route('/popular-spots', methods=['GET'])
def popular_spots():
    try:
        # Check if the user has granted location permission
        if request.args.get('lat') and request.args.get('lng'):
            lat = request.args.get('lat')
            lng = request.args.get('lng')
        else:
            # Use Google Maps Geolocation API for IP-based geolocation
            url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={env.get('GOOGLE_API_KEY')}"
            payload = {
                'considerIp': 'true'
            }
            response = requests.post(url, json=payload)
            data = response.json()

            if 'location' in data:
                lat = data['location']['lat']
                lng = data['location']['lng']
            else:
                # Fallback to default location if geolocation fails
                lat, lng = 37.7749, -122.4194  # Example: San Francisco coordinates
    except Exception as e:
        print(f"Error in geolocation: {str(e)}")
        # Fallback to default location if an exception occurs
        lat, lng = 37.7749, -122.4194  # Example: San Francisco coordinates

    try:
        # Make a request to the Google Maps Places API
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=5000&type=tourist_attraction&key={env.get('GOOGLE_API_KEY')}"
        response = requests.get(url)
        data = response.json()

        # Extract the place names from the API response
        place_names = [result['name'] for result in data['results']]

        movies = []
        # Generate a description of the spots with Gemini 1.5 Flash
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            # safety_settings = Adjust safety settings
            # See https://ai.google.dev/gemini-api/docs/safety-settings
        )
        for i, place_name in enumerate(place_names[:4]):  # Limit to 4 places
            response = model.generate_content("Write a very short summary of the following place not exceeding 1 line: " + place_name)
            description = json.loads(response.candidates[0].content.parts[0].text)
            movies.append({
                'id': i + 1,
                'title': place_name,
                'image': '',
                'desc': description['summary']
            })

        return jsonify({'movies': movies})
    except Exception as e:
        print(f"Error in fetching popular spots: {str(e)}")
        return jsonify({'error': 'Failed to fetch popular spots'}), 500

@app.route('/generate_image', methods=['POST'])
def generate_image():
    try:
        data = request.get_json()
        prompt = data.get('prompt')

        if not prompt:
            return jsonify({'error': 'Missing prompt'}), 400

        client = openai.OpenAI(api_key=env.get("OPENAI_API_KEY"))
        response = client.images.generate(
            model="dall-e-2",
            prompt="A beautiful image of " + prompt,
            size="512x512",
            n=1,
        )

        image_url = response.data[0].url

        return jsonify({'image_url': image_url})
    except Exception as e:
        print(f"Error in generating image: {str(e)}")
        return jsonify({'error': 'Failed to generate image'}), 500

@app.route('/trips', methods=['GET'])
def get_trips():
    user_id = session.get('user_id')
    trips = supabase.table('trips').select('*').eq('user_id', user_id).limit(4).execute()
    return jsonify(trips.data)

@app.route('/generate_qr_code', methods=['GET'])
def generate_qr_code():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401

    user_info = session.get('user')
    user_name = user_info.get('userinfo', {}).get('name', '')

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(user_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return jsonify({'qr_code_url': f'data:image/png;base64,{img_str}', 'user_name': user_name, 'user_id': user_id})

@app.route('/linking')
def linking():
    qr_code_url = request.args.get('qrCodeUrl')
    user_name = request.args.get('userName')
    user_id = request.args.get('userId')
    return render_template('qrcode.html', qr_code_url=qr_code_url, user_name=user_name, user_id=user_id)

@app.errorhandler(500)
def server_error(e):
    return jsonify(error=str(e)), 500


@app.route('/api/weather', methods=['GET'])
def get_weather():
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    api_key = os.environ.get('OPENWEATHERMAP_API_KEY')

    try:
        response = requests.get(
            f'https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric'
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to fetch weather data'}), 500

@app.route('/api/places', methods=['GET'])
def get_places():
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    api_key = os.environ.get('GOOGLE_API_KEY')

    try:
        response = requests.get(
            f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={latitude},{longitude}&radius=5000&type=tourist_attraction&key={api_key}'
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to fetch places data'}), 500

@app.route('/api/reverse_geocode', methods=['GET'])
def reverse_geocode():
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    api_key = os.environ.get('GOOGLE_API_KEY')

    print(f"Reverse geocoding for latitude: {latitude}, longitude: {longitude}")

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={api_key}"
        response = requests.get(url)
        data = response.json()

        if data["status"] == "OK":
            address = data["results"][0]["formatted_address"]
            print(f"Reverse geocoded address: {address}")
            return jsonify({'address': address})
        else:
            print(f"Reverse geocoding failed with status: {data['status']}")
            return jsonify({'error': 'Failed to fetch address'}), 500
    except Exception as e:
        print(f"Error in reverse geocoding: {str(e)}")
        return jsonify({'error': 'Failed to fetch address'}), 500
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    api_key = os.environ.get('GOOGLE_API_KEY')

    print(f"Reverse geocoding for latitude: {latitude}, longitude: {longitude}")

    try:
        geolocator = Nominatim(user_agent="myGeocoder")
        location = geolocator.reverse(f"{latitude}, {longitude}")
        address = location.address
        print(f"Reverse geocoded address: {address}")
        return jsonify({'address': address})
    except Exception as e:
        print(f"Error in reverse geocoding: {str(e)}")
        return jsonify({'error': 'Failed to fetch address'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=env.get("PORT", 3000), debug=True)
