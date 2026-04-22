import requests
import pandas as pd
from datetime import datetime
import os

# API Keys
AMBEE_API_KEY = "041abfe46b41ab94f68238e447ee1b87f9198d02c7109b1a310d908791b29d39"
WEATHER_CHANNEL_API_KEY = "7bfe01b2027b4094be01b2027b709468"

# Bangladesh er 8 ti division
divisions = {
    "Dhaka": {"lat": 23.8103, "lon": 90.4125},
    "Chattogram": {"lat": 22.3569, "lon": 91.7832},
    "Rajshahi": {"lat": 24.3745, "lon": 88.6042},
    "Khulna": {"lat": 22.8456, "lon": 89.5403},
    "Barishal": {"lat": 22.7010, "lon": 90.3535},
    "Sylhet": {"lat": 24.8949, "lon": 91.8687},
    "Rangpur": {"lat": 25.7439, "lon": 89.2752},
    "Mymensingh": {"lat": 24.7471, "lon": 90.4203}
}

def calculate_sub_index(conc, breakpoints):
    if conc is None or conc < 0: return 0
    for bp in breakpoints:
        if conc >= bp['cLow'] and conc <= bp['cHigh']:
            return round(((bp['iHigh'] - bp['iLow']) / (bp['cHigh'] - bp['cLow'])) * (conc - bp['cLow']) + bp['iLow'])
    return 500

def calculate_usa_aqi(pm25, pm10, o3_ppb, no2_ppb, so2_ppb, co_ppm):
    # EPA (USA) Breakpoints for PM2.5 and PM10
    pm25_bp = [{'cLow': 0.0, 'cHigh': 12.0, 'iLow': 0, 'iHigh': 50}, {'cLow': 12.1, 'cHigh': 35.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 35.5, 'cHigh': 55.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 55.5, 'cHigh': 150.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 150.5, 'cHigh': 250.4, 'iLow': 201, 'iHigh': 300}]
    pm10_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 154, 'iLow': 51, 'iHigh': 100}, {'cLow': 155, 'cHigh': 254, 'iLow': 101, 'iHigh': 150}, {'cLow': 255, 'cHigh': 354, 'iLow': 151, 'iHigh': 200}]
    
    aqi_pm25 = calculate_sub_index(pm25, pm25_bp)
    aqi_pm10 = calculate_sub_index(pm10, pm10_bp)
    
    # Return highest index as main AQI
    return max(aqi_pm25, aqi_pm10)

def get_open_meteo_data(lat, lon):
    """Amar App er data source (Open-Meteo)"""
    try:
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,uv_index&timezone=auto"
        a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
        
        # 10 second timeout added
        w_res = requests.get(w_url, timeout=10).json().get('current', {})
        a_res = requests.get(a_url, timeout=10).json().get('current', {})
        
        if not w_res or not a_res: return {}

        # Converted units like in your HTML
        o3_ppb = a_res.get('ozone', 0) / 1.96
        no2_ppb = a_res.get('nitrogen_dioxide', 0) / 1.88
        so2_ppb = a_res.get('sulphur_dioxide', 0) / 2.62
        co_ppm = a_res.get('carbon_monoxide', 0) / 1145
        
        calc_aqi = calculate_usa_aqi(a_res.get('pm2_5'), a_res.get('pm10'), o3_ppb, no2_ppb, so2_ppb, co_ppm)

        return {
            "app_temp": w_res.get('temperature_2m'), 
            "app_humidity": w_res.get('relative_humidity_2m'),
            "app_pressure": w_res.get('surface_pressure'), 
            "app_uv": w_res.get('uv_index'),
            "app_aqi": calc_aqi, 
            "app_pm10": a_res.get('pm10'), 
            "app_pm2_5": a_res.get('pm2_5')
        }
    except Exception as e:
        print(f"Open-Meteo Error: {e}")
        return {}

def get_std_data(lat, lon):
    """Standard Source (Ambee & Weather Channel)"""
    results = {
        "std_temp": None, "std_humidity": None, "std_pressure": None,
        "std_aqi": None, "std_pm10": None, "std_pm2_5": None
    }
    try:
        # Weather Channel Data (10s timeout)
        wc_url = f"https://api.weather.com/v3/wx/observations/current?geocode={lat},{lon}&format=json&units=m&apiKey={WEATHER_CHANNEL_API_KEY}"
        wc = requests.get(wc_url, timeout=10).json()
        results.update({
            "std_temp": wc.get('temperature'),
            "std_humidity": wc.get('relativeHumidity'),
            "std_pressure": wc.get('pressureMeanSeaLevel')
        })

        # Ambee Data (10s timeout)
        headers = {'x-api-key': AMBEE_API_KEY, 'Content-type': 'application/json'}
        amb_url = f"https://api.ambeedata.com/latest/by-lat-lng?lat={lat}&lng={lon}"
        amb_res = requests.get(amb_url, headers=headers, timeout=10).json()
        
        if amb_res.get('data'):
            aqi_data = amb_res['data'][0]
            results.update({
                "std_aqi": aqi_data.get('AQI'),
                "std_pm10": aqi_data.get('PM10'),
                "std_pm2_5": aqi_data.get('PM25')
            })
    except Exception as e:
        print(f"Standard API Error: {e}")
    return results

def collect():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Starting data collection...")
    final_rows = []
    
    for city, coord in divisions.items():
        print(f"Fetching {city}...")
        row = {"Timestamp": now, "Division": city}
        
        # Merge data from both app and standard sources
        row.update(get_open_meteo_data(coord['lat'], coord['lon']))
        row.update(get_std_data(coord['lat'], coord['lon']))
        
        final_rows.append(row)
    
    # Save to CSV
    df = pd.DataFrame(final_rows)
    file = "app_vs_standard_ml_data.csv"
    
    # Check if file exists to manage header
    file_exists = os.path.isfile(file)
    df.to_csv(file, mode='a', header=not file_exists, index=False)
    print(f"[{now}] Collection successful and saved.")

if __name__ == "__main__":
    collect()
