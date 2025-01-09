from flask import Flask, request, jsonify, render_template, session, abort
import requests
import psycopg2
import os
import OTPLessAuthSDK
from datetime import datetime
from flask_cors import CORS

# Create the Flask app
app = Flask(__name__)
CORS(app, origins=["*"])

app.config['SECRET_KEY'] = os.urandom(24)

# Use environment variables for sensitive information
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
WEATHER_BASE_URL = os.getenv('WEATHER_BASE_URL')

AIR_QUALITY_API_KEY = os.getenv('AIR_QUALITY_API_KEY')
AIR_QUALITY_BASE_URL = os.getenv('AIR_QUALITY_BASE_URL')

POPULATION_API_KEY = os.getenv('POPULATION_API_KEY')
POPULATION_API_URL = os.getenv('POPULATION_API_URL')

weather_d = []
health_data = []

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')


def get_db_connection():
    try:
        conn = psycopg2.connect(dbname=os.getenv('PGDATABASE'),
                                user=os.getenv('PGUSER'),
                                password=os.getenv('PGPASSWORD'),
                                host=os.getenv('PGHOST'),
                                port=os.getenv('PGPORT'),
                                sslmode=os.getenv('PGSSLMODE'))
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None


@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error
    print(f"An error occurred: {str(e)}")
    print(traceback.format_exc())
    # Return JSON instead of HTML for HTTP errors
    return jsonify(error=str(e)), 500


# Set up the initial database connection
conn = get_db_connection()
cur = conn.cursor()

# Create the data table if it doesn't exist
cur.execute('''
CREATE TABLE IF NOT EXISTS info (
    id SERIAL PRIMARY KEY,
    age INTEGER,
    gender TEXT,
    city TEXT,
    state VARCHAR(50),
    phone CHAR(15),
    order_id VARCHAR(85),
    otp_timestamp TIMESTAMP DEFAULT current_timestamp
)
''')
conn.commit()

cur.execute('''
    ALTER TABLE info 
    ADD COLUMN IF NOT EXISTS aqi INTEGER,
    ADD COLUMN IF NOT EXISTS temperature FLOAT,
    ADD COLUMN IF NOT EXISTS weather_conditions TEXT,
    ADD COLUMN IF NOT EXISTS population INTEGER,
    ADD COLUMN IF NOT EXISTS diseases TEXT,
    ADD COLUMN IF NOT EXISTS health_checkups TEXT
''')
conn.commit()


@app.route('/')
def home():
    return render_template('base.html')


# Function to submit info
@app.route('/submit_info', methods=['POST'])
def submit_info():
    data = request.json
    age = int(data.get('age'))
    gender = data.get('gender')
    city = data.get('city')
    state = data.get('state')
    weather_d.append(city)

    # Use the database connection function
    conn = get_db_connection()
    with conn.cursor() as cur:
        try:
            cur.execute(
                '''
                INSERT INTO info (age, gender, city, state)
                VALUES (%s, %s, %s, %s)
            ''', (age, gender, city, state))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
        finally:
            conn.close()

    return jsonify({
        "status": "success",
        "message": "Information stored successfully"
    })


# Function to send OTP by OTPLess
def send_otp_to_user(phoneNumber,
                     email,
                     channel='SMS',
                     otpLength=6,
                     orderId=None,
                     hash=None,
                     expiry=300):
    try:
        otp_details = OTPLessAuthSDK.OTP.send_otp(phoneNumber, email, channel,
                                                  hash, orderId, expiry,
                                                  otpLength, client_id,
                                                  client_secret)
        print(otp_details)  # Keep this for debugging
        return otp_details  # Add this line to return the otp_details
    except Exception as e:
        raise Exception(f"Failed to send OTP: {str(e)}")


# Function for sending OTP
@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    phoneNumber = data.get('phoneNumber')

    try:
        otp_details = send_otp_to_user(phoneNumber, None)

        if not isinstance(otp_details, dict):
            raise Exception(
                f"Unexpected response from OTP service: {otp_details}")

        new_order_id = otp_details.get(
            'orderId') or f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Use the database connection function
        conn = get_db_connection()
        with conn.cursor() as cur:
            try:
                cur.execute(
                    '''
                    UPDATE info 
                    SET phone = %s, order_id = %s, otp_timestamp = current_timestamp
                    WHERE id = (SELECT id FROM info ORDER BY id DESC LIMIT 1)
                ''', (phoneNumber, new_order_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise Exception(f"Failed to update order_id: {str(e)}")
            finally:
                conn.close()

        return jsonify({
            "status": "success",
            "orderId": new_order_id,
            "message": "OTP sent successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# Function for resending OTP
@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    data = request.json
    phoneNumber = data.get('phoneNumber')

    try:
        # Fetch the most recent order_id for this phone number
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT order_id 
                FROM info 
                WHERE phone = %s 
                ORDER BY otp_timestamp DESC 
                LIMIT 1
            ''', (phoneNumber, ))
            result = cur.fetchone()

            if not result:
                return jsonify({
                    "status": "error",
                    "message": "No previous OTP request found"
                }), 400

            order_id = result[0]

        # Use the OTPLessAuthSDK to resend the OTP
        otp_details = OTPLessAuthSDK.OTP.resend_otp(order_id, client_id,
                                                    client_secret)

        # Update the existing entry with the new OTP details
        with conn.cursor() as cur:
            cur.execute(
                '''
                UPDATE info 
                SET otp_timestamp = current_timestamp
                WHERE order_id = %s
            ''', (order_id, ))
            conn.commit()

        return jsonify({
            "status": "success",
            "orderId": order_id,
            "message": "OTP resent successfully"
        })
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        if conn:
            conn.close()


# Function for determining the category and color based on AQI
def get_aqi_category_and_color(aqi):
    if 0 <= aqi <= 50:
        return "Good", "good"
    elif 51 <= aqi <= 100:
        return "Moderate", "moderate"
    elif 101 <= aqi <= 150:
        return "Unhealthy for Sensitive Groups", "unhealthy-sensitive"
    elif 151 <= aqi <= 200:
        return "Unhealthy", "unhealthy"
    elif 201 <= aqi <= 300:
        return "Very Unhealthy", "very-unhealthy"
    elif aqi >= 301:
        return "Hazardous", "hazardous"
    else:
        return "Unknown", "unknown"


# Function to fetch population data from APINinja
def get_population_data(city_name):
    headers = {'X-Api-Key': POPULATION_API_KEY}
    params = {'name': city_name}

    try:
        response = requests.get(POPULATION_API_URL,
                                headers=headers,
                                params=params)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]  # Return the first result
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching population data: {e}")
        return None


@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    try:
        data = request.json
        orderId = data.get('orderId')
        otp = data.get('otp')
        phoneNumber = data.get('phoneNumber')
        city = data.get('city')
        state = data.get('state')

        # Correct method usage
        otp_details = OTPLessAuthSDK.OTP.veriy_otp(orderId, otp, None,
                                                   phoneNumber, client_id,
                                                   client_secret)

        if isinstance(otp_details, dict) and otp_details.get('isOTPVerified'):
            # Fetch weather and air quality data
            weather_air_quality_response = requests.get(
                f"{request.url_root}get_weather_and_air_quality?city={city}&state={state}"
            )
            weather_air_quality_data = weather_air_quality_response.json()

            # Fetch population data
            population_data = get_population_data(city)

            # Fetch health risk data
            health_risk_response = requests.get(
                f"{request.url_root}health_risk")
            health_risk_data = health_risk_response.json()

            # Extract relevant data
            aqi = weather_air_quality_data['air_quality_data']['aqi']
            temperature = weather_air_quality_data['weather_data']['main'][
                'temp']
            weather_conditions = weather_air_quality_data['weather_data'][
                'weather'][0]['description']
            population = population_data[
                'population'] if population_data else None

            # Combine diseases and health checkups from all sources
            diseases = []
            health_checkups = []
            for risk in health_risk_data:
                diseases.extend(risk['diseases'].split(', '))
                health_checkups.extend(risk['health_checkup'].split(', '))

            diseases = ', '.join(set(diseases))
            health_checkups = ', '.join(set(health_checkups))

            # Store the data in the database
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            '''
                            UPDATE info 
                            SET aqi = %s, temperature = %s, weather_conditions = %s, 
                                population = %s, diseases = %s, health_checkups = %s
                            WHERE order_id = %s
                        ''', (aqi, temperature, weather_conditions, population,
                              diseases, health_checkups, orderId))
                        conn.commit()
                finally:
                    conn.close()

            return jsonify({
                "status":
                "success",
                "message":
                "OTP verified and data stored successfully",
                "details":
                otp_details,
                "weather_data":
                weather_air_quality_data['weather_data'],
                "air_quality_data":
                weather_air_quality_data['air_quality_data'],
                "population_data":
                population_data,
                "health_risk_data":
                health_risk_data
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Incorrect OTP",
                "details": otp_details
            }), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/health_risk', methods=['GET'])
def health_risk():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "error",
                "message": "Database connection failed"
            }), 500
        cursor = conn.cursor()

        health_data = []
        # Ensure weather_d has enough elements
        if len(weather_d) < 4:
            return jsonify({
                "status": "error",
                "message": "Insufficient weather data"
            }), 400
        # Air quality data
        cursor.execute(
            "SELECT Diseases, Health_Checkup FROM airquality WHERE category = %s",
            (weather_d[-2], ))
        air_quality_data = cursor.fetchone()
        if air_quality_data:
            health_data.append({
                "type": "Air Quality",
                "diseases": air_quality_data[0],
                "health_checkup": air_quality_data[1]
            })
        # Weather temperature data
        cursor.execute(
            "SELECT Diseases_Caused, Recommended_Health_Checkup FROM weatherdisease WHERE numrange(range) @> %s::numeric",
            (weather_d[-1], ))
        weather_data = cursor.fetchone()
        if weather_data:
            health_data.append({
                "type": "Weather Conditions",
                "diseases": weather_data[0],
                "health_checkup": weather_data[1]
            })
        # City population data
        cursor.execute(
            "SELECT population, common_health_diseases, recommended_health_checkups FROM PopulationData WHERE city = %s",
            (weather_d[-4], ))
        city_data = cursor.fetchone()
        if city_data:
            health_data.append({
                "type": "Population Data",
                "diseases": city_data[1],
                "health_checkup": city_data[2]
            })
        conn.close()
        return jsonify(health_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Function to fetch Weather data and Air Quality info from openweathermap and AirVisual by IQair respectively
@app.route('/get_weather_and_air_quality', methods=['GET'])
def get_weather_and_air_quality():
    city = request.args.get('city')
    state = request.args.get('state')
    country = request.args.get('country', 'India')  # Default to India

    if not city or not state:
        return jsonify({
            "status": "error",
            "message": "City and state are required"
        }), 400

    weather_data = None
    air_quality_data = None

    try:
        # Get weather data
        weather_url = f"{WEATHER_BASE_URL}?q={city}&appid={WEATHER_API_KEY}&units=metric"
        weather_response = requests.get(weather_url)
        if weather_response.status_code == 200:
            weather_data = weather_response.json()
    except Exception as e:
        print(f"Error fetching weather data: {str(e)}")

    try:
        # Get air quality data
        air_quality_url = f"{AIR_QUALITY_BASE_URL}/city?city={city}&state={state}&country={country}&key={AIR_QUALITY_API_KEY}"
        air_quality_response = requests.get(air_quality_url)
        if air_quality_response.status_code == 200:
            air_quality_data = air_quality_response.json()
            if air_quality_data['status'] == 'success':
                aqi = air_quality_data['data']['current']['pollution']['aqius']
                category, color = get_aqi_category_and_color(aqi)
                main_pollutant = air_quality_data['data']['current'][
                    'pollution'].get('mainus', 'Not Available')
                air_quality_data = {
                    "aqi": aqi,
                    "category": category,
                    "color": color,
                    "main_pollutant": main_pollutant
                }
    except Exception as e:
        print(f"Error fetching air quality data: {str(e)}")

    aQi = air_quality_data['aqi']
    weather_d.append(aQi)
    cAt = air_quality_data['category']
    weather_d.append(cAt)
    temp = weather_data['main']['temp']
    weather_d.append(temp)

    print(aQi, cAt, temp)
    print(weather_d)

    return jsonify({
        "status": "success",
        "weather_data": weather_data,
        "air_quality_data": air_quality_data
    })


# Route for history
@app.route('/history', methods=['GET', 'POST'])
def history():
    phone_number = session.get('phone_number') or request.form.get(
        'phone_number')

    if phone_number:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, age, gender, city, state, phone, order_id, otp_timestamp, 
                       aqi, temperature, weather_conditions, population, diseases, health_checkups 
                FROM info 
                WHERE phone = %s 
                ORDER BY otp_timestamp DESC
            """, (phone_number, ))
            url_history = cur.fetchall()
        conn.close()
        return render_template("history.html",
                               url_history=url_history,
                               phone_number=phone_number)
    return render_template("history.html", url_history=None)

@app.route('/master_admin', methods=['GET', 'POST'])
def master_admin():
    # Check if the route is accessed directly
    if request.referrer is None or 'master_admin' in request.referrer:
        search_query = request.args.get('search', '')
        with conn.cursor() as cur:
            if search_query:
                cur.execute("""
                    SELECT phone, otp_timestamp, city, state, aqi, temperature, weather_conditions, population, diseases, health_checkups
                    FROM info
                    WHERE phone LIKE %s OR city ILIKE %s
                    ORDER BY otp_timestamp DESC
                """, (f'%{search_query}%', f'%{search_query}%'))
            else:
                cur.execute("""
                    SELECT phone, otp_timestamp, city, state, aqi, temperature, weather_conditions, population, diseases, health_checkups
                    FROM info
                    ORDER BY otp_timestamp DESC
                """)
            history = cur.fetchall()
        return render_template("master_admin.html", history=history, search_query=search_query)
    else:
        # If not accessed directly, return a 404 error
        abort(404)

# # Function to fetch health risk including disease caused and recommended health checkups
# @app.route('/health_risk', methods=['GET'])
# def health_risk():
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     health_data = []

#     # Air quality data
#     cursor.execute(
#         "SELECT Diseases, Health_Checkup FROM airquality WHERE category = %s",
#         (weather_d[-2], ))
#     air_quality_data = cursor.fetchone()
#     health_data.append({
#         "type": "Air Quality",
#         "diseases": air_quality_data[0],
#         "health_checkup": air_quality_data[1]
#     })

#     # Weather temperature data
#     cursor.execute(
#         "SELECT Diseases_Caused, Recommended_Health_Checkup FROM weatherdisease WHERE numrange(range) @> %s::numeric",
#         (weather_d[-1], ))
#     weather_data = cursor.fetchone()
#     health_data.append({
#         "type": "Weather Conditions",
#         "diseases": weather_data[0],
#         "health_checkup": weather_data[1]
#     })

#     # City population data
#     cursor.execute(
#         "SELECT population, common_health_diseases, recommended_health_checkups FROM PopulationData WHERE city = %s",
#         (weather_d[-4], ))
#     city_data = cursor.fetchone()
#     health_data.append({
#         "type": "Population Data",
#         "diseases": city_data[1],
#         "health_checkup": city_data[2]
#     })

#     conn.close()

#     return jsonify(health_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
