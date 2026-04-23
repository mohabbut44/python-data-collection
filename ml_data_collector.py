import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import os
import time
import math

# API Keys
WEATHER_CHANNEL_API_KEY = os.getenv("WEATHER_CHANNEL_API_KEY", "")
AMBEE_API_KEY = "041abfe46b41ab94f68238e447ee1b87f9198d02c7109b1a310d908791b29d39"

# Coordinates with 4 decimal precision
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

# --- USA EPA AQI Calculation Logic ---
def calculate_sub_index(conc, breakpoints):
    if conc is None or conc < 0: return 0
    for bp in breakpoints:
        if conc >= bp['cLow'] and conc <= bp['cHigh']:
            return round(((bp['iHigh'] - bp['iLow']) / (bp['cHigh'] - bp['cLow'])) * (conc - bp['cLow']) + bp['iLow'])
    return 500 if conc > 0 else 0

def calculate_usa_aqi(pm25, pm10, o3, no2, so2, co):
    """
    Calculates AQI based on US EPA 2012/2013 standard.
    Units: PM2.5 (ug/m3), PM10 (ug/m3), O3 (ppb), NO2 (ppb), SO2 (ppb), CO (ppm)
    """
    pm25_bp = [{'cLow': 0.0, 'cHigh': 12.0, 'iLow': 0, 'iHigh': 50}, {'cLow': 12.1, 'cHigh': 35.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 35.5, 'cHigh': 55.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 55.5, 'cHigh': 150.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 150.5, 'cHigh': 250.4, 'iLow': 201, 'iHigh': 300}, {'cLow': 250.5, 'cHigh': 350.4, 'iLow': 301, 'iHigh': 400}, {'cLow': 350.5, 'cHigh': 500.4, 'iLow': 401, 'iHigh': 500}]
    pm10_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 154, 'iLow': 51, 'iHigh': 100}, {'cLow': 155, 'cHigh': 254, 'iLow': 101, 'iHigh': 150}, {'cLow': 255, 'cHigh': 354, 'iLow': 151, 'iHigh': 200}, {'cLow': 355, 'cHigh': 424, 'iLow': 201, 'iHigh': 300}, {'cLow': 425, 'cHigh': 504, 'iLow': 301, 'iHigh': 400}, {'cLow': 505, 'cHigh': 604, 'iLow': 401, 'iHigh': 500}]
    o3_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 70, 'iLow': 51, 'iHigh': 100}, {'cLow': 71, 'cHigh': 85, 'iLow': 101, 'iHigh': 150}, {'cLow': 86, 'cHigh': 105, 'iLow': 151, 'iHigh': 200}, {'cLow': 106, 'cHigh': 200, 'iLow': 201, 'iHigh': 300}]
    no2_bp = [{'cLow': 0, 'cHigh': 53, 'iLow': 0, 'iHigh': 50}, {'cLow': 54, 'cHigh': 100, 'iLow': 51, 'iHigh': 100}, {'cLow': 101, 'cHigh': 360, 'iLow': 101, 'iHigh': 150}, {'cLow': 361, 'cHigh': 649, 'iLow': 151, 'iHigh': 200}, {'cLow': 650, 'cHigh': 1249, 'iLow': 201, 'iHigh': 300}]
    so2_bp = [{'cLow': 0, 'cHigh': 35, 'iLow': 0, 'iHigh': 50}, {'cLow': 36, 'cHigh': 75, 'iLow': 51, 'iHigh': 100}, {'cLow': 76, 'cHigh': 185, 'iLow': 101, 'iHigh': 150}, {'cLow': 186, 'cHigh': 304, 'iLow': 151, 'iHigh': 200}]
    co_bp = [{'cLow': 0.0, 'cHigh': 4.4, 'iLow': 0, 'iHigh': 50}, {'cLow': 4.5, 'cHigh': 9.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 9.5, 'cHigh': 12.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 12.5, 'cHigh': 15.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 15.5, 'cHigh': 30.4, 'iLow': 201, 'iHigh': 300}]

    indices = [
        calculate_sub_index(round(pm25, 1) if pm25 else 0, pm25_bp),
        calculate_sub_index(int(round(pm10)) if pm10 else 0, pm10_bp),
        calculate_sub_index(int(round(o3)) if o3 else 0, o3_bp),
        calculate_sub_index(int(round(no2)) if no2 else 0, no2_bp),
        calculate_sub_index(int(round(so2)) if so2 else 0, so2_bp),
        calculate_sub_index(round(co, 1) if co else 0, co_bp)
    ]
    return max(indices)

# --- Helper Functions ---
def safe_round(val, digits=2):
    try: return round(float(val), digits) if val is not None else None
    except: return None

def fetch_api_data(url, api_name, headers=None):
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200: return res.json()
        print(f"      ⚠ {api_name} Error: {res.status_code}")
    except Exception as e:
        print(f"      ⚠ {api_name} Network Error: {e}")
    return None

# --- Data Fetching ---

def get_open_meteo_data(lat, lon):
    lat_str, lon_str = f"{lat:.4f}", f"{lon:.4f}"
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_str}&longitude={lon_str}&current=temperature_2m,relative_humidity_2m,surface_pressure,uv_index"
    a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat_str}&longitude={lon_str}&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
    
    w_data = fetch_api_data(w_url, "Open-Meteo Weather")
    a_data = fetch_api_data(a_url, "Open-Meteo AQI")
    
    w_res = w_data.get('current', {}) if w_data else {}
    a_res = a_data.get('current', {}) if a_data else {}
    
    # Standard Conversions from ug/m3 to ppb/ppm (at 25C, 1 atm)
    pm25 = a_res.get('pm2_5')
    pm10 = a_res.get('pm10')
    o3_ppb = (a_res.get('ozone', 0) / 1.96)
    no2_ppb = (a_res.get('nitrogen_dioxide', 0) / 1.88)
    so2_ppb = (a_res.get('sulphur_dioxide', 0) / 2.62)
    co_ppm = (a_res.get('carbon_monoxide', 0) / 1145)

    calc_aqi = calculate_usa_aqi(pm25, pm10, o3_ppb, no2_ppb, so2_ppb, co_ppm)

    return {
        "OM_Temp_C": safe_round(w_res.get('temperature_2m')),
        "OM_Humidity_%": safe_round(w_res.get('relative_humidity_2m')),
        "OM_Pressure_hPa": safe_round(w_res.get('surface_pressure')),
        "OM_UV_Index": safe_round(w_res.get('uv_index')),
        "OM_AQI_(USA)": calc_aqi,
        "OM_PM2.5": safe_round(pm25),
        "OM_PM10": safe_round(pm10),
        "OM_O3": safe_round(o3_ppb),
        "OM_NO2": safe_round(no2_ppb),
        "OM_SO2": safe_round(so2_ppb),
        "OM_CO": safe_round(co_ppm)
    }

def get_ambee_val(obj, keys):
    for k in keys:
        if k in obj and obj[k] is not None: return obj[k]
    return 0

def get_std_data(lat, lon):
    lat_str, lon_str = f"{lat:.4f}", f"{lon:.4f}"
    
    # 1. Weather Channel
    wc_url = f"https://api.weather.com/v3/wx/observations/current?geocode={lat_str},{lon_str}&format=json&units=m&apiKey={WEATHER_CHANNEL_API_KEY}"
    wc_data = fetch_api_data(wc_url, "Weather Channel")
    
    # 2. Ambee
    ambee_url = f"https://api.ambeedata.com/latest/by-lat-lng?lat={lat_str}&lng={lon_str}"
    ambee_data = fetch_api_data(ambee_url, "Ambee", headers={"x-api-key": AMBEE_API_KEY})
    
    res = {
        "WC_Temp_C": safe_round(wc_data.get('temperature')) if wc_data else None,
        "WC_Humidity_%": safe_round(wc_data.get('relativeHumidity')) if wc_data else None,
        "WC_Pressure_hPa": safe_round(wc_data.get('pressureMeanSeaLevel')) if wc_data else None,
        "WC_UV_Index": safe_round(wc_data.get('uvIndex')) if wc_data else None,
    }

    if ambee_data and ambee_data.get('data'):
        # Ambee-র ডাটা লিস্ট বা ডিকশনারি যাই হোক তা হ্যান্ডেল করা
        data = ambee_data['data']
        info = data[0] if isinstance(data, list) else data
        
        # Ambee সাধারণত ug/m3 দেয়, তাই কনভার্সন জরুরি
        a_pm25 = get_ambee_val(info, ['PM25', 'pm25'])
        a_pm10 = get_ambee_val(info, ['PM10', 'pm10'])
        a_o3_ppb = get_ambee_val(info, ['OZONE', 'o3']) / 1.96
        a_no2_ppb = get_ambee_val(info, ['NO2', 'no2']) / 1.88
        a_so2_ppb = get_ambee_val(info, ['SO2', 'so2']) / 2.62
        a_co_ppm = get_ambee_val(info, ['CO', 'co']) / 1145

        # Ambee-র কাঁচা ডেটা থেকে আমরা নিজেরা USA AQI ক্যালকুলেট করছি সামঞ্জস্যের জন্য
        ambee_calc_aqi = calculate_usa_aqi(a_pm25, a_pm10, a_o3_ppb, a_no2_ppb, a_so2_ppb, a_co_ppm)
        
        res.update({
            "Ambee_AQI_(USA)": ambee_calc_aqi,
            "Ambee_PM2.5": safe_round(a_pm25),
            "Ambee_PM10": safe_round(a_pm10),
            "Ambee_O3": safe_round(a_o3_ppb),
            "Ambee_NO2": safe_round(a_no2_ppb),
            "Ambee_SO2": safe_round(a_so2_ppb),
            "Ambee_CO": safe_round(a_co_ppm)
        })
    return res

def collect():
    now = datetime.now(timezone(timedelta(hours=6)))
    date_s, time_s = now.strftime("%Y-%m-%d"), now.strftime("%I:%M:%S %p")
    
    print(f"\n🚀 Collection Started: {date_s} {time_s}")
    final_rows = []
    
    for city, coord in divisions.items():
        print(f"  -> Fetching {city}...")
        row = {"Date": date_s, "Time": time_s, "Division": city}
        row.update(get_open_meteo_data(coord['lat'], coord['lon']))
        row.update(get_std_data(coord['lat'], coord['lon']))
        final_rows.append(row)
        time.sleep(5) # API safety delay

    df = pd.DataFrame(final_rows)
    file = "app_vs_standard_ml_data.csv"
    df.to_csv(file, mode='a', header=not os.path.exists(file), index=False)
    print(f"✅ Data Saved to {file}\n")

if __name__ == "__main__":
    collect()
