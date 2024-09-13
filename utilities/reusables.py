import math


def calculate_distance(lat1, lng1, lat2, lng2):
    """
    Calculate the distance between two points on the Earth (specified in decimal degrees).
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lng2 - lng1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    # Radius of Earth in kilometers (mean radius = 6,371 km)
    km = 6371 * c
    return km