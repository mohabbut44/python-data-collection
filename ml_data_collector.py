import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import os
import time
import math

# API Keys
WEATHER_CHANNEL_API_KEY = os.getenv("WEATHER_CHANNEL_API_KEY", "")
AMBEE_API_KEY = "041abfe46b41ab94f68238e447ee1b87f9198d02c7109b1a310d908791b29d39"

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

# --- Error Handling Helper ---
def safe_round(val, digits=2):
    if val is None:
        return None
    try:
        return round(float(val), digits)
    except (ValueError, TypeError):
        return None

def fetch_api_data(url, api_name, retries=5, delay=5, headers=None):
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                wait_time = delay * attempt * 2 
                print(f"      ⚠ {api_name} Rate Limited (429). Waiting {wait_time}s before retry {attempt}/{retries}...")
                time.sleep(wait_time)
            else:
                # 🛠 Added res.text so you can see exact error from Ambee in Github Actions logs
                print(f"      ⚠ {api_name} API Error (Status {res.status_code}): {res.text}. Retrying {attempt}/{retries} in {delay}s...")
                time.sleep(delay)
        except requests.exceptions.RequestException as e:
            print(f"      ⚠ {api_name} Network Error: {e}. Retrying {attempt}/{retries} in {delay}s...")
            time.sleep(delay)
    return None

# --- USA AQI Calculation Logic ---
def calculate_sub_index(conc, breakpoints):
    if conc is None or conc < 0:
        return 0
    for bp in breakpoints:
        if conc >= bp['cLow'] and conc <= bp['cHigh']:
            return round(((bp['iHigh'] - bp['iLow']) / (bp['cHigh'] - bp['cLow'])) * (conc - bp['cLow']) + bp['iLow'])
    return 500 if conc > 0 else 0

def calculate_usa_aqi(pm25, pm10, o3, no2, so2, co):
    pm25_bp = [{'cLow': 0.0, 'cHigh': 12.0, 'iLow': 0, 'iHigh': 50}, {'cLow': 12.1, 'cHigh': 35.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 35.5, 'cHigh': 55.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 55.5, 'cHigh': 150.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 150.5, 'cHigh': 250.4, 'iLow': 201, 'iHigh': 300}, {'cLow': 250.5, 'cHigh': 350.4, 'iLow': 301, 'iHigh': 400}, {'cLow': 350.5, 'cHigh': 500.4, 'iLow': 401, 'iHigh': 500}]
    pm10_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 154, 'iLow': 51, 'iHigh': 100}, {'cLow': 155, 'cHigh': 254, 'iLow': 101, 'iHigh': 150}, {'cLow': 255, 'cHigh': 354, 'iLow': 151, 'iHigh': 200}, {'cLow': 355, 'cHigh': 424, 'iLow': 201, 'iHigh': 300}, {'cLow': 425, 'cHigh': 504, 'iLow': 301, 'iHigh': 400}, {'cLow': 505, 'cHigh': 604, 'iLow': 401, 'iHigh': 500}]
    o3_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 70, 'iLow': 51, 'iHigh': 100}, {'cLow': 71, 'cHigh': 85, 'iLow': 101, 'iHigh': 150}, {'cLow': 86, 'cHigh': 105, 'iLow': 151, 'iHigh': 200}, {'cLow': 106, 'cHigh': 200, 'iLow': 201, 'iHigh': 300}, {'cLow': 201, 'cHigh': 400, 'iLow': 301, 'iHigh': 400}, {'cLow': 401, 'cHigh': 600, 'iLow': 401, 'iHigh': 500}]
    no2_bp = [{'cLow': 0, 'cHigh': 53, 'iLow': 0, 'iHigh': 50}, {'cLow': 54, 'cHigh': 100, 'iLow': 51, 'iHigh': 100}, {'cLow': 101, 'cHigh': 360, 'iLow': 101, 'iHigh': 150}, {'cLow': 361, 'cHigh': 649, 'iLow': 151, 'iHigh': 200}, {'cLow': 650, 'cHigh': 1249, 'iLow': 201, 'iHigh': 300}, {'cLow': 1250, 'cHigh': 1649, 'iLow': 301, 'iHigh': 400}, {'cLow': 1650, 'cHigh': 2049, 'iLow': 401, 'iHigh': 500}]
    so2_bp = [{'cLow': 0, 'cHigh': 35, 'iLow': 0, 'iHigh': 50}, {'cLow': 36, 'cHigh': 75, 'iLow': 51, 'iHigh': 100}, {'cLow': 76, 'cHigh': 185, 'iLow': 101, 'iHigh': 150}, {'cLow': 186, 'cHigh': 304, 'iLow': 151, 'iHigh': 200}, {'cLow': 305, 'cHigh': 604, 'iLow': 201, 'iHigh': 300}, {'cLow': 605, 'cHigh': 804, 'iLow': 301, 'iHigh': 400}, {'cLow': 805, 'cHigh': 1004, 'iLow': 401, 'iHigh': 500}]
    co_bp = [{'cLow': 0.0, 'cHigh': 4.4, 'iLow': 0, 'iHigh': 50}, {'cLow': 4.5, 'cHigh': 9.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 9.5, 'cHigh': 12.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 12.5, 'cHigh': 15.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 15.5, 'cHigh': 30.4, 'iLow': 201, 'iHigh': 300}, {'cLow': 30.5, 'cHigh': 40.4, 'iLow': 301, 'iHigh': 400}, {'cLow': 40.5, 'cHigh': 50.4, 'iLow': 401, 'iHigh': 500}]

    def js_round(val, decimals=0):
        if val is None: return 0
        factor = 10 ** decimals
        return math.floor(float(val) * factor + 0.5) / factor

    indices = [
        calculate_sub_index(js_round(pm25, 1), pm25_bp),
        calculate_sub_index(js_round(pm10, 0), pm10_bp),
        calculate_sub_index(js_round(o3, 0), o3_bp),
        calculate_sub_index(js_round(no2, 0), no2_bp),
        calculate_sub_index(js_round(so2, 0), so2_bp),
        calculate_sub_index(js_round(co, 1), co_bp)
    ]
    return max(indices)

def get_open_meteo_data(lat, lon):
    lat_str, lon_str = f"{lat:.4f}", f"{lon:.4f}"
    
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_str}&longitude={lon_str}&current=temperature_2m,relative_humidity_2m,surface_pressure,uv_index"
    a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat_str}&longitude={lon_str}&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
    
    w_data = fetch_api_data(w_url, "Open-Meteo (Weather)", retries=5, delay=5)
    time.sleep(2)  
    a_data = fetch_api_data(a_url, "Open-Meteo (AQI)", retries=5, delay=5)
    
    w_res = w_data.get('current', {}) if w_data else {}
    a_res = a_data.get('current', {}) if a_data else {}
    
    o3 = a_res.get('ozone')
    no2 = a_res.get('nitrogen_dioxide')
    so2 = a_res.get('sulphur_dioxide')
    co = a_res.get('carbon_monoxide')
    pm10 = a_res.get('pm10')
    pm2_5 = a_res.get('pm2_5')
    
    o3_ppb = (o3 / 1.96) if o3 is not None else 0
    no2_ppb = (no2 / 1.88) if no2 is not None else 0
    so2_ppb = (so2 / 2.62) if so2 is not None else 0
    co_ppm = (co / 1145) if co is not None else 0
    
    calc_aqi = calculate_usa_aqi(
        pm2_5 if pm2_5 is not None else 0, 
        pm10 if pm10 is not None else 0, 
        o3_ppb, no2_ppb, so2_ppb, co_ppm
    )

    if w_data and a_data:
        print(f"    ✓ Open-Meteo: OK")

    return {
        "OM_Temp_C": safe_round(w_res.get('temperature_2m')),
        "OM_Humidity_%": safe_round(w_res.get('relative_humidity_2m')),
        "OM_Pressure_hPa": safe_round(w_res.get('surface_pressure')),
        "OM_UV_Index": safe_round(w_res.get('uv_index')),
        "OM_AQI_(USA)": calc_aqi,
        "OM_PM2.5_(µg/m3)": safe_round(pm2_5),
        "OM_PM10_(µg/m3)": safe_round(pm10),
        "OM_O3_(ppb)": safe_round(o3_ppb),
        "OM_NO2_(ppb)": safe_round(no2_ppb),
        "OM_SO2_(ppb)": safe_round(so2_ppb),
        "OM_CO_(ppm)": safe_round(co_ppm)
    }

# 🛠 Helper function to safely extract keys from Ambee response regardless of naming
def get_ambee_val(obj, possible_keys):
    for k in possible_keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None

def get_std_data(lat, lon):
    lat_str, lon_str = f"{lat:.4f}", f"{lon:.4f}"
    
    results = {
        "WC_Temp_C": None, "WC_Humidity_%": None, "WC_Pressure_hPa": None, "WC_UV_Index": None,
        "Ambee_AQI_(USA)": None, "Ambee_PM2.5": None, "Ambee_PM10": None,
        "Ambee_O3": None, "Ambee_NO2": None, "Ambee_SO2": None, "Ambee_CO": None
    }
    
    # 1. Weather Channel (Weather Data Only)
    wx_url = f"https://api.weather.com/v3/wx/observations/current?geocode={lat_str},{lon_str}&format=json&units=m&language=en-US&apiKey={WEATHER_CHANNEL_API_KEY}"
    wx_data = fetch_api_data(wx_url, "Weather Channel (Wx)", retries=5, delay=5)
    time.sleep(1) 
    
    if wx_data:
        results.update({
            "WC_Temp_C": safe_round(wx_data.get('temperature')),
            "WC_Humidity_%": safe_round(wx_data.get('relativeHumidity')),
            "WC_Pressure_hPa": safe_round(wx_data.get('pressureMeanSeaLevel')),
            "WC_UV_Index": safe_round(wx_data.get('uvIndex'))
        })
        print(f"    ✓ Weather Channel (Wx): OK")

    # 2. Ambee API (AQI & Pollutants Data Only)
    ambee_url = f"https://api.ambeedata.com/latest/by-lat-lng?lat={lat_str}&lng={lon_str}"
    ambee_headers = {
        "x-api-key": AMBEE_API_KEY,
        "Content-type": "application/json"
    }
    
    ambee_data = fetch_api_data(ambee_url, "Ambee (AQI)", retries=3, delay=5, headers=ambee_headers)
    
    if ambee_data:
        # Check if data is inside 'data' or 'stations' array
        aqi_source = ambee_data.get('data') or ambee_data.get('stations')
        
        if aqi_source:
            # Handle both list and object responses
            if isinstance(aqi_source, list) and len(aqi_source) > 0:
                aqi_info = aqi_source[0]
            elif isinstance(aqi_source, dict):
                aqi_info = aqi_source
            else:
                aqi_info = None
                
            if aqi_info:
                results.update({
                    "Ambee_AQI_(USA)": safe_round(get_ambee_val(aqi_info, ['AQI', 'aqi', 'airQualityIndex'])),
                    "Ambee_PM2.5": safe_round(get_ambee_val(aqi_info, ['PM25', 'pm25', 'PM2.5', 'pm2.5'])),
                    "Ambee_PM10": safe_round(get_ambee_val(aqi_info, ['PM10', 'pm10'])),
                    "Ambee_O3": safe_round(get_ambee_val(aqi_info, ['OZONE', 'O3', 'ozone', 'o3'])),
                    "Ambee_NO2": safe_round(get_ambee_val(aqi_info, ['NO2', 'no2'])),
                    "Ambee_SO2": safe_round(get_ambee_val(aqi_info, ['SO2', 'so2'])),
                    "Ambee_CO": safe_round(get_ambee_val(aqi_info, ['CO', 'co']))
                })
                print(f"    ✓ Ambee (AQI): Extracted Pollutants Successfully")
            else:
                print(f"    ⚠ Ambee (AQI): Data array is empty.")
        else:
            print(f"    ⚠ Ambee (AQI): Missing 'data' object. Keys returned: {list(ambee_data.keys())}")
    else:
        print(f"    ⚠ Ambee (AQI): Failed to fetch data.")
        
    return results

def collect():
    # Exact BD Time
    bd_timezone = timezone(timedelta(hours=6))
    now_obj = datetime.now(bd_timezone)
    
    date_str = now_obj.strftime("%Y-%m-%d")
    time_str = now_obj.strftime("%I:%M:%S %p")
    
    print(f"\n{'='*60}")
    print(f"🌍 Collection started at {date_str} {time_str} (BD Time)")
    print(f"{'='*60}\n")
    
    final_rows = []
    
    for idx, (city, coord) in enumerate(divisions.items(), 1):
        print(f"[{idx}/8] Processing {city}...")
        
        row = {"Date": date_str, "Time": time_str, "Division": city}
        row.update(get_open_meteo_data(coord['lat'], coord['lon']))
        row.update(get_std_data(coord['lat'], coord['lon']))
        
        final_rows.append(row)
        print(f"  ✓ {city} Complete\n")
        
        if idx < 8:
            print("  ⏳ Waiting 10 seconds before next division to avoid API blocks...")
            time.sleep(10)

    df = pd.DataFrame(final_rows)
    file = "app_vs_standard_ml_data.csv"
    
    if not os.path.isfile(file):
        df.to_csv(file, index=False)
        print(f"✅ New CSV file created: {file}")
    else:
        df.to_csv(file, mode='a', header=False, index=False)
        print(f"✅ Data safely appended to CSV: {file}")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    print("🚀 Starting robust data collection via GitHub Actions...")
    try:
        collect()
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
