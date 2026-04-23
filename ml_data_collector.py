import requests
import pandas as pd
from datetime import datetime
import os
import time

# API Keys (GitHub Secrets থেকে আসবে)
WEATHER_CHANNEL_API_KEY = os.getenv("WEATHER_CHANNEL_API_KEY", "")

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
    """Safely round a value that might be missing (None)."""
    if val is None:
        return None
    try:
        return round(float(val), digits)
    except (ValueError, TypeError):
        return None

# --- USA AQI Calculation Logic (For Open-Meteo) ---
def calculate_sub_index(conc, breakpoints):
    if conc is None or conc < 0:
        return 0
    for bp in breakpoints:
        if conc >= bp['cLow'] and conc <= bp['cHigh']:
            return round(
                ((bp['iHigh'] - bp['iLow']) / (bp['cHigh'] - bp['cLow'])) * (conc - bp['cLow']) + bp['iLow']
            )
    return 500 if conc > 0 else 0

def calculate_usa_aqi(pm25, pm10, o3, no2, so2, co):
    pm25_bp = [{'cLow': 0.0, 'cHigh': 12.0, 'iLow': 0, 'iHigh': 50}, {'cLow': 12.1, 'cHigh': 35.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 35.5, 'cHigh': 55.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 55.5, 'cHigh': 150.4, 'iLow': 151, 'iHigh': 200}, {'cLow': 150.5, 'cHigh': 250.4, 'iLow': 201, 'iHigh': 300}, {'cLow': 250.5, 'cHigh': 350.4, 'iLow': 301, 'iHigh': 400}, {'cLow': 350.5, 'cHigh': 500.4, 'iLow': 401, 'iHigh': 500}]
    pm10_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 154, 'iLow': 51, 'iHigh': 100}, {'cLow': 155, 'cHigh': 254, 'iLow': 101, 'iHigh': 150}, {'cLow': 255, 'cHigh': 354, 'iLow': 151, 'iHigh': 200}, {'cLow': 355, 'cHigh': 424, 'iLow': 201, 'iHigh': 300}, {'cLow': 425, 'cHigh': 504, 'iLow': 301, 'iHigh': 400}, {'cLow': 505, 'cHigh': 604, 'iLow': 401, 'iHigh': 500}]
    o3_bp = [{'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50}, {'cLow': 55, 'cHigh': 70, 'iLow': 51, 'iHigh': 100}, {'cLow': 71, 'cHigh': 85, 'iLow': 101, 'iHigh': 150}, {'cLow': 86, 'cHigh': 105, 'iLow': 151, 'iHigh': 200}, {'cLow': 106, 'cHigh': 200, 'iLow': 201, 'iHigh': 300}]
    no2_bp = [{'cLow': 0, 'cHigh': 53, 'iLow': 0, 'iHigh': 50}, {'cLow': 54, 'cHigh': 100, 'iLow': 51, 'iHigh': 100}, {'cLow': 101, 'cHigh': 360, 'iLow': 101, 'iHigh': 150}, {'cLow': 361, 'cHigh': 649, 'iLow': 151, 'iHigh': 200}]
    so2_bp = [{'cLow': 0, 'cHigh': 35, 'iLow': 0, 'iHigh': 50}, {'cLow': 36, 'cHigh': 75, 'iLow': 51, 'iHigh': 100}, {'cLow': 76, 'cHigh': 185, 'iLow': 101, 'iHigh': 150}, {'cLow': 186, 'cHigh': 304, 'iLow': 151, 'iHigh': 200}]
    co_bp = [{'cLow': 0.0, 'cHigh': 4.4, 'iLow': 0, 'iHigh': 50}, {'cLow': 4.5, 'cHigh': 9.4, 'iLow': 51, 'iHigh': 100}, {'cLow': 9.5, 'cHigh': 12.4, 'iLow': 101, 'iHigh': 150}, {'cLow': 12.5, 'cHigh': 15.4, 'iLow': 151, 'iHigh': 200}]

    indices = [
        calculate_sub_index(pm25, pm25_bp),
        calculate_sub_index(pm10, pm10_bp),
        calculate_sub_index(o3, o3_bp),
        calculate_sub_index(no2, no2_bp),
        calculate_sub_index(so2, so2_bp),
        calculate_sub_index(co, co_bp)
    ]
    return max(indices)

def get_open_meteo_data(lat, lon):
    """Fetch data from Open-Meteo API"""
    try:
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,uv_index"
        a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
        
        w_res = requests.get(w_url, timeout=15).json().get('current', {})
        a_res = requests.get(a_url, timeout=15).json().get('current', {})
        
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

        return {
            "app_temp": safe_round(w_res.get('temperature_2m')),
            "app_humidity": safe_round(w_res.get('relative_humidity_2m')),
            "app_pressure": safe_round(w_res.get('surface_pressure')),
            "app_uv": safe_round(w_res.get('uv_index')),
            "app_aqi": calc_aqi,
            "app_pm10": safe_round(pm10),
            "app_pm2_5": safe_round(pm2_5)
        }
    except Exception as e:
        print(f"  ⚠ OpenMeteo Error: {e}")
        return {
            "app_temp": None, "app_humidity": None, "app_pressure": None,
            "app_uv": None, "app_aqi": None, "app_pm10": None, "app_pm2_5": None
        }

def get_std_data(lat, lon):
    """Fetch data from Standard APIs (Only Weather Channel)"""
    results = {
        "std_temp": None, 
        "std_humidity": None, 
        "std_pressure": None,
        "std_aqi": None, 
        "std_pm10": None, 
        "std_pm2_5": None
    }
    
    # 1. Weather Channel: Current Observations (Temp, Humidity, Pressure)
    try:
        wx_url = f"https://api.weather.com/v3/wx/observations/current?geocode={lat},{lon}&format=json&units=m&language=en-US&apiKey={WEATHER_CHANNEL_API_KEY}"
        wx_res = requests.get(wx_url, timeout=15)
        if wx_res.status_code == 200:
            wx = wx_res.json()
            results.update({
                "std_temp": safe_round(wx.get('temperature')),
                "std_humidity": safe_round(wx.get('relativeHumidity')),
                "std_pressure": safe_round(wx.get('pressureMeanSeaLevel'))
            })
            print(f"    ✓ Weather Channel (Wx): OK")
        else:
            print(f"    ⚠ Weather Channel (Wx): Status {wx_res.status_code}")
    except Exception as e:
        print(f"    ⚠ Weather Channel (Wx) Error: {e}")

    # 2. Weather Channel: Air Quality (AQI, PM2.5, PM10)
    try:
        aqi_url = f"https://api.weather.com/v3/wx/globalAirQuality?geocode={lat},{lon}&format=json&language=en-US&apiKey={WEATHER_CHANNEL_API_KEY}"
        aqi_res = requests.get(aqi_url, timeout=15)
        if aqi_res.status_code == 200:
            aqi_data = aqi_res.json()
            # The Weather Channel provides a globalAQI object containing pollutant details
            if 'globalairquality' in aqi_data:
                gaq = aqi_data['globalairquality']
                results.update({
                    "std_aqi": safe_round(gaq.get('airQualityIndex')),
                    "std_pm10": safe_round(gaq.get('pm10')),
                    "std_pm2_5": safe_round(gaq.get('pm25'))
                })
                print(f"    ✓ Weather Channel (AQI): OK")
            else:
                print(f"    ⚠ Weather Channel (AQI): Data structure unexpected.")
        else:
            print(f"    ⚠ Weather Channel (AQI): Status {aqi_res.status_code}")
    except Exception as e:
        print(f"    ⚠ Weather Channel (AQI) Error: {e}")
    
    return results

def collect():
    """Main collection function"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🌍 Collection started at {now}")
    print(f"{'='*60}\n")
    
    final_rows = []
    
    for idx, (city, coord) in enumerate(divisions.items(), 1):
        print(f"[{idx}/8] Processing {city}...")
        
        row = {"Timestamp": now, "Division": city}
        
        print(f"  → Fetching OpenMeteo...")
        row.update(get_open_meteo_data(coord['lat'], coord['lon']))
        
        print(f"  → Fetching Standard APIs...")
        row.update(get_std_data(coord['lat'], coord['lon']))
        
        final_rows.append(row)
        print(f"  ✓ {city} Complete\n")
        
        if idx < 8:
            time.sleep(2)

    df = pd.DataFrame(final_rows)
    file = "app_vs_standard_ml_data.csv"
    
    if not os.path.isfile(file):
        df.to_csv(file, index=False)
        print(f"✅ New file created: {file}")
    else:
        df.to_csv(file, mode='a', header=False, index=False)
        print(f"✅ Data appended to: {file}")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    print("🚀 Starting single collection run via GitHub Actions...")
    try:
        collect()
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
