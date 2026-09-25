import base64
import requests

# ================================================
#   Settings
# ================================================
SERVER_URL = "http://127.0.0.1:5000"


# ================================================
#   Get data names
# ================================================
response =requests.get(
    f"{SERVER_URL}/data-names",
    timeout=10,
)

response.raise_for_status()

data_names = response.json()

print(data_names)


# ================================================
#   Get date range
# ================================================
response = requests.get(
    f"{SERVER_URL}/date-range",
    timeout=10,
)

response.raise_for_status()

date_range = response.json()

print(date_range)


# ================================================
#   Get measurements
# ================================================
params = {
    "data_name": "Chuck_Air_Pressure",
    "judge": "OK",
}

response = requests.get(
    f"{SERVER_URL}/measurements",
    params=params,
    timeout=10,
)

measurements = response.json()

blob_data = base64.b64decode(measurements[0]["data"])

print(type(blob_data))
print(len(blob_data))

print(len(measurements))
print(measurements[0])





