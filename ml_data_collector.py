import requests
import pandas as pd
from datetime import datetime
import os
import time

# API Keys (এগুলো এখন GitHub Secrets থেকে আসবে)
AMBEE_API_KEY = os.getenv("AMBEE_API_KEY")
WEATHER_CHANNEL_API_KEY = os.getenv("WEATHER_CHANNEL_API_KEY")

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

# --- USA AQI Calculation Logic ---
def calculate_sub_index(conc, breakpoints):
    """Calculate AQI sub-index for a pollutant"""
    if conc is None or conc < 0:
        return 0
    
    for bp in breakpoints:
        if conc >= bp['cLow'] and conc <= bp['cHigh']:
            return round(
                ((bp['iHigh'] - bp['iLow']) / (bp['cHigh'] - bp['cLow'])) * (conc - bp['cLow']) + bp['iLow']
            )
    
    return 500 if conc > 0 else 0

def calculate_usa_aqi(pm25, pm10, o3, no2, so2, co):
    """Calculate USA AQI from pollutant concentrations"""
    
    pm25_bp = [
        {'cLow': 0.0, 'cHigh': 12.0, 'iLow': 0, 'iHigh': 50},
        {'cLow': 12.1, 'cHigh': 35.4, 'iLow': 51, 'iHigh': 100},
        {'cLow': 35.5, 'cHigh': 55.4, 'iLow': 101, 'iHigh': 150},
        {'cLow': 55.5, 'cHigh': 150.4, 'iLow': 151, 'iHigh': 200},
        {'cLow': 150.5, 'cHigh': 250.4, 'iLow': 201, 'iHigh': 300},
        {'cLow': 250.5, 'cHigh': 350.4, 'iLow': 301, 'iHigh': 400},
        {'cLow': 350.5, 'cHigh': 500.4, 'iLow': 401, 'iHigh': 500}
    ]
    
    pm10_bp = [
        {'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50},
        {'cLow': 55, 'cHigh': 154, 'iLow': 51, 'iHigh': 100},
        {'cLow': 155, 'cHigh': 254, 'iLow': 101, 'iHigh': 150},
        {'cLow': 255, 'cHigh': 354, 'iLow': 151, 'iHigh': 200},
        {'cLow': 355, 'cHigh': 424, 'iLow': 201, 'iHigh': 300},
        {'cLow': 425, 'cHigh': 504, 'iLow': 301, 'iHigh': 400},
        {'cLow': 505, 'cHigh': 604, 'iLow': 401, 'iHigh': 500}
    ]
    
    o3_bp = [
        {'cLow': 0, 'cHigh': 54, 'iLow': 0, 'iHigh': 50},
        {'cLow': 55, 'cHigh': 70, 'iLow': 51, 'iHigh': 100},
        {'cLow': 71, 'cHigh': 85, 'iLow': 101, 'iHigh': 150},
        {'cLow': 86, 'cHigh': 105, 'iLow': 151, 'iHigh': 200},
        {'cLow': 106, 'cHigh': 200, 'iLow': 201, 'iHigh': 300}
    ]
    
    no2_bp = [
        {'cLow': 0, 'cHigh': 53, 'iLow': 0, 'iHigh': 50},
        {'cLow': 54, 'cHigh': 100, 'iLow': 51, 'iHigh': 100},
        {'cLow': 101, 'cHigh': 360, 'iLow': 101, 'iHigh': 150},
        {'cLow': 361, 'cHigh': 649, 'iLow': 151, 'iHigh': 200}
    ]
    
    so2_bp = [
        {'cLow': 0, 'cHigh': 35, 'iLow': 0, 'iHigh': 50},
        {'cLow': 36, 'cHigh': 75, 'iLow': 51, 'iHigh': 100},
        {'cLow': 76, 'cHigh': 185, 'iLow': 101, 'iHigh': 150},
        {'cLow': 186, 'cHigh': 304, 'iLow': 151, 'iHigh': 200}
    ]
    
    co_bp = [
        {'cLow': 0.0, 'cHigh': 4.4, 'iLow': 0, 'iHigh': 50},
        {'cLow': 4.5, 'cHigh': 9.4, 'iLow': 51, 'iHigh': 100},
        {'cLow': 9.5, 'cHigh': 12.4, 'iLow': 101, 'iHigh': 150},
        {'cLow': 12.5, 'cHigh': 15.4, 'iLow': 151, 'iHigh': 200}
    ]

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
        
        w_res = requests.get(w_url, timeout=15).json()['current']
        a_res = requests.get(a_url, timeout=15).json()['current']
        
        o3_ppb = a_res['ozone'] / 1.96 if a_res.get('ozone') else 0
        no2_ppb = a_res['nitrogen_dioxide'] / 1.88 if a_res.get('nitrogen_dioxide') else 0
        so2_ppb = a_res['sulphur_dioxide'] / 2.62 if a_res.get('sulphur_dioxide') else 0
        co_ppm = a_res['carbon_monoxide'] / 1145 if a_res.get('carbon_monoxide') else 0
        
        calc_aqi = calculate_usa_aqi(
            a_res['pm2_5'], 
            a_res['pm10'], 
            o3_ppb, 
            no2_ppb, 
            so2_ppb, 
            co_ppm
        )

        return {
            "app_temp": round(w_res['temperature_2m'], 2),
            "app_humidity": w_res['relative_humidity_2m'],
            "app_pressure": round(w_res['surface_pressure'], 2),
            "app_uv": round(w_res['uv_index'], 2),
            "app_aqi": calc_aqi,
            "app_pm10": round(a_res['pm10'], 2),
            "app_pm2_5": round(a_res['pm2_5'], 2)
        }
    except Exception as e:
        print(f"  ⚠ OpenMeteo Error: {e}")
        return {
            "app_temp": None, "app_humidity": None, "app_pressure": None,
            "app_uv": None, "app_aqi": None, "app_pm10": None, "app_pm2_5": None
        }

def get_std_data(lat, lon):
    """Fetch data from Standard APIs (Weather Channel & Ambee)"""
    results = {
        "std_temp": None, 
        "std_humidity": None, 
        "std_pressure": None,
        "std_aqi": None, 
        "std_pm10": None, 
        "std_pm2_5": None
    }
    
    try:
        # ===== Weather Channel API =====
        wc_url = f"https://api.weather.com/v3/wx/observations/current?geocode={lat},{lon}&format=json&units=m&language=en-US&apiKey={WEATHER_CHANNEL_API_KEY}"
        
        try:
            wc_res = requests.get(wc_url, timeout=15)
            if wc_res.status_code == 200:
                wc = wc_res.json()
                results.update({
                    "std_temp": round(wc.get('temperature'), 2) if wc.get('temperature') else None,
                    "std_humidity": wc.get('relativeHumidity'),
                    "std_pressure": round(wc.get('pressureMeanSeaLevel'), 2) if wc.get('pressureMeanSeaLevel') else None
                })
                print(f"    ✓ Weather Channel: OK")
            else:
                print(f"    ⚠ Weather Channel: Status {wc_res.status_code} - {wc_res.text}")
        except Exception as e:
            print(f"    ⚠ Weather Channel Error: {e}")
        
        # ===== Ambee API =====
        headers = {
            'x-api-key': AMBEE_API_KEY,
            'Content-type': 'application/json'
        }
        amb_url = f"https://api.ambeedata.com/latest/by-lat-lng?lat={lat}&lng={lon}"
        
        try:
            amb_res = requests.get(amb_url, headers=headers, timeout=15)
            if amb_res.status_code == 200:
                amb = amb_res.json()
                data_list = amb.get('data') or amb.get('stations')
                if data_list and len(data_list) > 0:
                    aqi_data = data_list[0]
                    results.update({
                        "std_aqi": aqi_data.get('AQI'),
                        "std_pm10": round(aqi_data.get('PM10'), 2) if aqi_data.get('PM10') else None,
                        "std_pm2_5": round(aqi_data.get('PM25'), 2) if aqi_data.get('PM25') else None
                    })
                    print(f"    ✓ Ambee: OK")
                else:
                    print(f"    ⚠ Ambee: No data array in response.")
            else:
                print(f"    ⚠ Ambee: Status {amb_res.status_code} - {amb_res.text}")
        except Exception as e:
            print(f"    ⚠ Ambee Error: {e}")
    
    except Exception as e:
        print(f"  ⚠ Standard APIs Error: {e}")
    
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
