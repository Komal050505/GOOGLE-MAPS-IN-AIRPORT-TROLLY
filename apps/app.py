# Flask Imports
from flask import Flask, jsonify, request

# SQLAlchemy Imports
from sqlalchemy import func

# Third-Party Library Imports
import googlemaps
from sqlalchemy.exc import SQLAlchemyError

# Project-Specific Imports
from db_connections.configurations import session, DATABASE_URL, YOUR_GOOGLE_MAPS_API_KEY
from email_setup.email_config import ERROR_HANDLING_GROUP_EMAIL, RECEIVER_EMAIL
from email_setup.email_operations import (notify_clear_failure, notify_clear_success, notify_failure,
                                          notify_success, format_steps,
                                          format_facility_details_with_distance_for_email,
                                          format_geocode_error_response, send_email, prepare_geocode_success_message,
                                          format_reverse_geocode_error_response,
                                          prepare_reverse_geocode_success_message)
from logging_package.logging_utility import log_error, log_info, log_warning, log_debug
from user_models.tables import AirportFacility
from utilities.reusables import calculate_distance

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

gmaps = googlemaps.Client(key=YOUR_GOOGLE_MAPS_API_KEY)


@app.route('/route', methods=['POST'])
def get_route():
    try:
        # Get data from request
        data = request.get_json()
        current_location = data.get('current_location')
        destination = data.get('destination')

        if not current_location or not destination:
            log_error("Missing required parameters: current_location and/or destination")
            notify_failure("Route Request Failed", "Missing required parameters: current_location and/or destination")
            return jsonify({"error": "Missing required parameters: current_location and/or destination"}), 400

        # Convert current location to tuple
        origin = (current_location['lat'], current_location['lng'])

        # Get directions from Google Maps API
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            mode="walking"  # Change to "driving" or other modes if needed
        )

        if not directions_result:
            log_error("No directions found")
            notify_failure("Route Request Failed", "No directions found")
            return jsonify({"error": "No directions found"}), 404

        # Extract route details
        route_data = {
            "start_address": directions_result[0]['legs'][0]['start_address'],
            "end_address": directions_result[0]['legs'][0]['end_address'],
            "waypoints": [
                {
                    "lat": step['end_location']['lat'],
                    "lng": step['end_location']['lng']
                }
                for step in directions_result[0]['legs'][0]['steps']
            ]
        }

        log_info(f"Route successfully fetched: {route_data}")
        notify_success("Route Request Successful", "The route was successfully fetched.",
                       count=len(route_data['waypoints']))
        return jsonify(route_data), 200

    except Exception as e:
        log_error(f"Exception occurred: {str(e)}")
        notify_failure("Route Request Failed", f"Exception occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/navigate', methods=['GET'])
def navigate():
    """
    API to get navigation directions from the current location to a facility in the airport.
    Query Parameters:
        current_lat (float): Current latitude of the trolley.
        current_lng (float): Current longitude of the trolley.
        facility_id (int): ID of the facility to navigate to.
    Returns:
        JSON response with navigation steps and distance.
    """
    # Here current lat and current lng is given to trolly and facility id is the destination
    current_lat = request.args.get('current_lat')
    current_lng = request.args.get('current_lng')
    facility_id = request.args.get('facility_id')

    if not current_lat or not current_lng or not facility_id:
        error_message = "Missing required parameters: current_lat, current_lng, and/or facility_id"
        log_error(error_message)
        notify_failure("Navigation API Error", error_message)
        return jsonify({"error": error_message}), 400

    try:
        facility = session.get(AirportFacility, facility_id)
        if not facility:
            error_message = f"Facility with ID {facility_id} not found"
            log_error(error_message)
            notify_failure("Navigation API Error", error_message)
            return jsonify({"error": error_message}), 404

        destination_coords = facility.coordinates.split(',')
        if len(destination_coords) != 2:
            error_message = "Invalid coordinates format in the facility record"
            log_error(error_message)
            notify_failure("Navigation API Error", error_message)
            return jsonify({"error": error_message}), 400

        # Usees Google Maps API to get directions from current location to the facility
        directions_result = gmaps.directions(
            origin=(float(current_lat), float(current_lng)),
            destination=(float(destination_coords[0]), float(destination_coords[1])),
            mode="walking"
        )

        steps = []
        if directions_result and 'legs' in directions_result[0]:
            for step in directions_result[0]['legs'][0]['steps']:
                steps.append({
                    "distance": step['distance']['text'],
                    "duration": step['duration']['text'],
                    "instruction": step['html_instructions'],
                    "start_location": step['start_location'],
                    "end_location": step['end_location']
                })

            success_message = "Navigation directions fetched successfully"
            log_info(success_message)
            notify_success(
                "Navigation API Success",
                f"{success_message}<br><br>Facility: {facility.to_dict()}<br><br>Steps: {format_steps(steps)}"
            )
            return jsonify({
                "facility": facility.to_dict(),
                "navigation_steps": steps,
                "total_distance": directions_result[0]['legs'][0]['distance']['text'],
                "total_duration": directions_result[0]['legs'][0]['duration']['text']
            }), 200

        error_message = "No directions found"
        log_error(error_message)
        notify_failure("Navigation API Error", error_message)
        return jsonify({"error": error_message}), 404

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        log_error(error_message)
        notify_failure("Navigation API Error", error_message)
        return jsonify({"error": error_message}), 500


@app.route('/nearby-facilities', methods=['GET'])
def nearby_facilities():
    """
    API to find nearby facilities from the current location within a specified radius.
    Query Parameters:
        current_lat (float): Current latitude of the location.
        current_lng (float): Current longitude of the location.
        radius (int): Search radius in meters.
    Returns:
        JSON response with a list of nearby facilities.
    """
    log_info("Starting /nearby_facilities API call")

    current_lat = request.args.get('current_lat')
    current_lng = request.args.get('current_lng')
    radius = request.args.get('radius', default=1000, type=int)

    if not current_lat or not current_lng:
        error_message = "Missing required parameters: current_lat and current_lng"
        log_error(error_message)
        notify_failure("Nearby Facilities API Error", error_message)
        return jsonify({"error": error_message}), 400

    try:
        places_result = gmaps.places_nearby(
            location=(float(current_lat), float(current_lng)),
            radius=radius
        )

        if places_result and 'results' in places_result:
            facilities = []
            for place in places_result['results']:
                place_lat = place.get('geometry', {}).get('location', {}).get('lat', 'N/A')
                place_lng = place.get('geometry', {}).get('location', {}).get('lng', 'N/A')

                distance = calculate_distance(float(current_lat), float(current_lng), float(place_lat),
                                              float(place_lng))

                facility = {
                    "id": place.get('place_id', 'N/A'),
                    "name": place.get('name', 'N/A'),
                    "category": place.get('types', ['N/A'])[0],
                    "coordinates": f"{place_lat}, {place_lng}",
                    "description": place.get('vicinity', 'N/A'),
                    "distance": f"{distance:.2f} km",
                    "created_at": "N/A"
                }
                facilities.append(facility)

            success_message = "Nearby facilities fetched successfully"
            log_info(success_message)
            formatted_facilities = format_facility_details_with_distance_for_email(facilities)

            notify_success(
                "Nearby Facilities API Success",
                f"{success_message}<br><br>Facilities:<br>{formatted_facilities}"
            )
            return jsonify({"facilities": facilities}), 200

        error_message = "No nearby facilities found"
        log_error(error_message)
        notify_failure("Nearby Facilities API Error", error_message)
        return jsonify({"error": error_message}), 404

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        log_error(error_message)
        notify_failure("Nearby Facilities API Error", error_message)
        return jsonify({"error": error_message}), 500

    finally:
        log_info("Ending /nearby_facilities API call")


@app.route('/geocode', methods=['GET'])
def geocode():
    """
    API to get latitude and longitude coordinates for a given address.
    Query Parameters:
        address (str): The address to be geocoded.
    Returns:
        JSON response with latitude and longitude coordinates or error details.
    """
    log_info("Starting /geocode API call")

    address = request.args.get('address')

    if not address:
        error_message = "Missing required parameter: address"
        log_error(error_message)
        send_email(
            to_email=ERROR_HANDLING_GROUP_EMAIL,
            subject="Geocode API Error",
            body=format_geocode_error_response({"error": error_message})
        )
        return jsonify({"error": error_message}), 400

    try:
        geocode_result = gmaps.geocode(address)

        log_debug(f"API Response: {geocode_result}")

        if geocode_result and len(geocode_result) > 0:
            location = geocode_result[0]['geometry']['location']
            success_message = prepare_geocode_success_message(address, location['lat'], location['lng'])
            log_info("Geocoding successful")
            send_email(
                to_email=RECEIVER_EMAIL,
                subject="Geocode API Success",
                body=success_message
            )
            return jsonify({
                "Given Address:": address,
                "latitude": location['lat'],
                "longitude": location['lng']
            }), 200
        else:
            error_message = "Geocoding result is empty or invalid."
            formatted_error = format_geocode_error_response({
                "error": error_message,
                "api_response": str(geocode_result)
            })
            log_error(formatted_error)
            send_email(
                to_email=ERROR_HANDLING_GROUP_EMAIL,
                subject="Geocode API Error",
                body=formatted_error
            )
            return jsonify({"error": error_message}), 404

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        formatted_error = format_geocode_error_response({"error": error_message})
        log_error(formatted_error)
        send_email(
            to_email=ERROR_HANDLING_GROUP_EMAIL,
            subject="Geocode API Error",
            body=formatted_error
        )
        return jsonify({"error": error_message}), 500

    finally:
        log_info("Ending /geocode API call")


@app.route('/reverse-geocode', methods=['GET'])
def reverse_geocode():
    """
    API to get a human-readable address for given latitude and longitude coordinates.
    Query Parameters:
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
    Returns:
        JSON response with the address or error details.
    """
    log_info("Starting /reverse_geocode API call")

    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')

    if not latitude or not longitude:
        error_message = "Missing required parameters: latitude and longitude"
        log_error(error_message)
        send_email(
            to_email=ERROR_HANDLING_GROUP_EMAIL,
            subject="Reverse Geocode API Error",
            body=format_reverse_geocode_error_response({"error": error_message})
        )
        return jsonify({"error": error_message}), 400

    try:
        reverse_geocode_result = gmaps.reverse_geocode((float(latitude), float(longitude)))

        log_debug(f"API Response: {reverse_geocode_result}")

        if reverse_geocode_result and len(reverse_geocode_result) > 0:
            address = reverse_geocode_result[0]['formatted_address']
            success_message = prepare_reverse_geocode_success_message(latitude, longitude, address)

            log_info("Reverse geocoding successful")
            send_email(
                to_email=RECEIVER_EMAIL,
                subject="Reverse Geocode API Success",
                body=success_message
            )
            return jsonify({"address": address, "Given latitude": latitude, "Given longitude": longitude}), 200
        else:
            error_message = "Reverse geocoding failed for the provided coordinates"
            formatted_error = format_reverse_geocode_error_response({
                "error": error_message,
                "api_response": str(reverse_geocode_result)
            })

            log_error(formatted_error)
            send_email(
                to_email=ERROR_HANDLING_GROUP_EMAIL,
                subject="Reverse Geocode API Error",
                body=formatted_error
            )
            return jsonify({"error": error_message}), 404

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        formatted_error = format_reverse_geocode_error_response({"error": error_message})

        log_error(formatted_error)
        send_email(
            to_email=ERROR_HANDLING_GROUP_EMAIL,
            subject="Reverse Geocode API Error",
            body=formatted_error
        )
        return jsonify({"error": error_message}), 500

    finally:
        log_info("Ending /reverse_geocode API call")


@app.route('/get-distance', methods=['GET'])
def get_distance():
    """
    API to calculate the distance between two points given their latitude and longitude coordinates.
    Query Parameters:
        lat1 (float): Latitude of the first location.
        lng1 (float): Longitude of the first location.
        lat2 (float): Latitude of the second location.
        lng2 (float): Longitude of the second location.
    Returns:
        JSON response with the distance between the two points, including the coordinates and formatted message.
    """
    log_info("Starting /distance API call")

    lat1 = request.args.get('lat1')
    lng1 = request.args.get('lng1')
    lat2 = request.args.get('lat2')
    lng2 = request.args.get('lng2')

    if not lat1 or not lng1 or not lat2 or not lng2:
        error_message = "Missing required parameters: lat1, lng1, lat2, and/or lng2"
        log_error(error_message)
        notify_failure("Distance API Error", error_message)
        return jsonify({"error": error_message}), 400

    try:
        distance_result = gmaps.distance_matrix(
            origins=[(float(lat1), float(lng1))],
            destinations=[(float(lat2), float(lng2))]
        )

        if distance_result and 'rows' in distance_result and distance_result['rows']:
            distances = distance_result['rows'][0]['elements'][0]['distance']['text']
            success_message = f"Distance calculation successful"

            log_info(success_message)

            formatted_message = (f"Coordinates:<br>Start: Latitude: {lat1}, Longitude: {lng1}<br>"
                                 f"End: Latitude: {lat2}, Longitude: {lng2}<br>Distance: {distances}")

            notify_success(
                "Distance API Success",
                f"{success_message}<br><br>{formatted_message}"
            )

            return jsonify({
                "message": success_message,
                "start_coordinates": {"latitude": lat1, "longitude": lng1},
                "end_coordinates": {"latitude": lat2, "longitude": lng2},
                "distance": distances
            }), 200

        error_message = "Failed to calculate distance"
        log_error(error_message)
        notify_failure("Distance API Error", error_message)
        return jsonify({"error": error_message}), 404

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        log_error(error_message)
        notify_failure("Distance API Error", error_message)
        return jsonify({"error": error_message}), 500

    finally:
        log_info("Ending /distance API call")


# ......................................................................................................................
@app.route('/airport/facilities/search', methods=['GET'])
def search_facilities():
    """
    Search for airport facilities by name, category, or coordinates.

    Query Parameters:
        - name (str, optional): Facility name to search for.
        - category (str, optional): Facility category to search for.
        - coordinates (str, optional): Facility coordinates to search for.

    Returns:
        - JSON with total_count and facility_details.
    """
    log_info("GET /airport/facilities/search - Start")
    try:
        name = request.args.get('name')
        category = request.args.get('category')
        coordinates = request.args.get('coordinates')

        query = session.query(AirportFacility)

        if name:
            query = query.filter(AirportFacility.name.ilike(f'%{name}%'))
        if category:
            query = query.filter(AirportFacility.category.ilike(f'%{category}%'))
        if coordinates:
            query = query.filter(AirportFacility.coordinates.ilike(f'%{coordinates}%'))

        facilities = query.all()
        count = len(facilities)
        facility_details = [facility.to_dict() for facility in facilities]

        log_info("GET /airport/facilities/search - End: Searched facilities successfully.")
        notify_success("Facilities Searched", "Facilities searched successfully.",
                       facilities=facility_details, count=count)

        response_data = {
            "total_count": count,
            "facility_details": facility_details
        }
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"GET /airport/facilities/search - Error: {str(e)}")
        notify_failure("Failed to Search Facilities", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities/stats', methods=['GET'])
def get_facility_stats():
    """
        Retrieve statistics for airport facilities.

        Returns:
            - JSON with total_facilities, category_stats, and latest_facility.

    """
    log_info("GET /api/airport/facilities/stats - Start")
    try:
        total_facilities = session.query(AirportFacility).count()

        category_counts = (session.query(AirportFacility.category, func.count(AirportFacility.id)).
                           group_by(AirportFacility.category).all())
        category_stats = {category: count for category, count in category_counts}

        category_stats_details = "<br><br>Category Stats:<br>"
        category_stats_details += "<br>".join([f"{category}: {count}" for category, count in category_stats.items()])

        latest_facility = session.query(AirportFacility).order_by(AirportFacility.id.desc()).first()
        latest_facility_details = latest_facility.to_dict() if latest_facility else None

        body = "Facility statistics retrieved successfully."
        body += category_stats_details
        notify_success(
            "Facility Statistics Retrieved",
            body,
            facilities=[latest_facility_details] if latest_facility else None,
            count=total_facilities
        )

        response_data = {
            "total_facilities": total_facilities,
            "category_stats": category_stats,
            "latest_facility": latest_facility_details
        }
        log_info("GET /airport/facilities/stats - End: Retrieved facility statistics successfully.")
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"GET /airport/facilities/stats - Error: {str(e)}")
        notify_failure("Failed to Retrieve Facility Statistics", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities/batch', methods=['POST'])
def add_multiple_facilities_batch():
    try:
        facilities_data = request.json

        # Validate input format
        if not isinstance(facilities_data, list):
            error_msg = "Invalid input format, expected a list."
            log_error(error_msg)
            notify_failure("Batch Facility Addition Failed", error_msg)
            return jsonify({"error": error_msg}), 400

        new_facilities = []
        for facility in facilities_data:
            # Extract fields
            name = facility.get('name')
            category = facility.get('category')
            coordinates = facility.get('coordinates')
            description = facility.get('description')

            # Validate mandatory fields
            if not name or not category or not coordinates:
                error_msg = f"Missing required fields for facility: {facility}"
                log_error(error_msg)
                notify_failure("Batch Facility Addition Failed", error_msg)
                return jsonify({"error": error_msg}), 400

            # Create a new AirportFacility instance
            new_facility = AirportFacility(
                name=name,
                category=category,
                coordinates=coordinates,
                description=description
            )
            session.add(new_facility)
            new_facilities.append(new_facility)

        # Commit the batch insert
        session.commit()

        success_msg = "Facilities added successfully."
        log_info(success_msg)

        # Prepare response data for email and return statement
        facility_details = [facility.to_dict() for facility in new_facilities]
        facility_count = len(new_facilities)  # Calculate the total count

        # Send success notification with the facilities and total count
        notify_success("Batch Facility Addition Success", success_msg, facilities=facility_details,
                       count=facility_count)

        # Return response with facility details and total count
        return jsonify({
            "message": success_msg,
            "facilities": facility_details,
            "total_facilities": facility_count
        }), 201

    except SQLAlchemyError as e:
        session.rollback()
        error_msg = f"Database error: {str(e)}"
        log_error(error_msg)
        notify_failure("Batch Facility Addition Failed", error_msg)
        return jsonify({"error": error_msg}), 500

    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        log_error(error_msg)
        notify_failure("Batch Facility Addition Failed", error_msg)
        return jsonify({"error": error_msg}), 500


@app.route('/airport/facilities/batch-update', methods=['PUT'])
def batch_update_facilities():
    """
       Update multiple airport facilities in batch.

       Returns:
           - JSON with message and updated_facilities.

    """
    log_info("PUT /airport/facilities/batch-update - Start")
    try:
        data = request.json
        ids = data.get('ids', [])
        update_data = data.get('update_data', {})

        if not ids:
            log_warning("PUT /airport/facilities/batch-update - Warning: No IDs provided for batch update.")
            return jsonify({"error": "At least one ID is required for batch update."}), 400

        facilities = session.query(AirportFacility).filter(AirportFacility.id.in_(ids)).all()

        if not facilities:
            log_warning("PUT /airport/facilities/batch-update - Warning: No facilities found for provided IDs.")
            return jsonify({"error": "No facilities found for the provided IDs."}), 404

        for facility in facilities:
            for key, value in update_data.items():
                setattr(facility, key, value)

        session.commit()
        updated_facility_details = [facility.to_dict() for facility in facilities]

        category_counts = session.query(
            AirportFacility.category,
            func.count(AirportFacility.id)
        ).group_by(AirportFacility.category).all()
        category_stats = {category: count for category, count in category_counts}

        category_stats_details = "<br><br>Category Stats:<br>"
        category_stats_details += "<br>".join([f"{category}: {count}" for category, count in category_stats.items()])

        body = "Batch update of facilities completed successfully."
        body += category_stats_details
        notify_success(
            "Batch Update Successful",
            body,
            facilities=updated_facility_details
        )

        response_data = {
            "message": "Batch update successful",
            "updated_facilities": updated_facility_details
        }
        log_info("PUT /airport/facilities/batch-update - End: Batch update successful.")
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"PUT /airport/facilities/batch-update - Error: {str(e)}")
        notify_failure("Failed to Batch Update Facilities", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/all/airport/facilities', methods=['GET'])
def get_all_facilities():
    """
       Retrieve all airport facilities.

       Returns:
           - JSON with total_facilities and a list of facility details.

    """
    log_info("GET /airport/facilities - Start")
    try:
        facilities = session.query(AirportFacility).all()
        count = len(facilities)
        facility_details = [facility.to_dict() for facility in facilities]
        log_info("GET /airport/facilities - End: Retrieved all facilities successfully.")
        notify_success("Facilities Retrieved", "Retrieved all facilities successfully.",
                       facilities=facility_details, count=count)

        response_data = {
            "total_count": count,
            "facility_details": facility_details
        }
        return jsonify(response_data), 200
    except Exception as e:
        log_error(f"GET /airport/facilities - Error: {str(e)}")
        notify_failure("Failed to Retrieve Facilities", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 50


@app.route('/airport/facilities', methods=['GET'])
def get_facility_by_id():
    """
       Retrieve a specific airport facility by ID.

       Query Parameters:
           - id (str): The ID of the facility to retrieve.

       Returns:
           - JSON with total_count and facility_details for the specified ID.

    """
    log_info("GET /airport/facilities - Start")
    try:
        facility_id = request.args.get('id')

        if not facility_id:
            log_warning("GET /airport/facilities - Warning: No ID provided in query parameters.")
            return jsonify({"error": "ID is required in the query parameters."}), 400

        facility = session.query(AirportFacility).get(facility_id)
        if facility is None:
            log_warning(f"GET /airport/facilities/{facility_id} - Warning: Facility not found.")
            notify_failure("Facility Not Found", f"Facility with ID {facility_id} not found.")
            return jsonify({"error": "Facility not found"}), 404

        facility_details = facility.to_dict()
        count = 1

        log_info(f"GET /airport/facilities/{facility_id} - End: Retrieved facility successfully.")
        notify_success("Facility Retrieved", f"Retrieved facility details: Successful",
                       [facility_details], count)

        response_data = {
            "total_count": count,
            "facility_details": facility_details
        }
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"GET /airport/facilities - Error: {str(e)}")
        notify_failure("Failed to Retrieve Facility", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities', methods=['POST'])
def add_facility():
    """
       Add a new airport facility.

       Request Body (JSON):
           - name (str): The name of the facility.
           - category (str): The category of the facility.
           - coordinates (str): The coordinates of the facility.

       Returns:
           - JSON with the ID of the newly added facility.

    """
    log_info("POST /airport/facilities - Start")
    try:
        data = request.json
        new_facility = AirportFacility(
            name=data['name'],
            category=data['category'],
            coordinates=data['coordinates'],
            description=data.get('description', '')
        )
        session.add(new_facility)
        session.commit()
        facility_details = new_facility.to_dict()
        log_info(f"POST /airport/facilities - End: Added new facility: {facility_details}")
        notify_success("New Facility Added", "Facility added successfully.", [facility_details])
        return jsonify(facility_details), 201
    except Exception as e:
        log_error(f"POST /airport/facilities - Error: {str(e)}")
        notify_failure("Failed to Add Facility", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities', methods=['PUT'])
def update_facility():
    """
        Update an existing airport facility.

        Request Body (JSON):
            - name (str, optional): The updated name of the facility.
            - category (str, optional): The updated category of the facility.
            - coordinates (str, optional): The updated coordinates of the facility.

        URL Parameters:
            - facility_id (int): The ID of the facility to update.

        Returns:
            - JSON with the updated facility details.

    """
    log_info(f"PUT /airport/facilities/{id} - Start")
    try:
        data = request.json
        id_from_body = data.get('id', id)

        facility = session.query(AirportFacility).filter_by(id=id_from_body).first()
        if facility is None:
            log_warning(f"PUT /airport/facilities/{id_from_body} - Warning: Facility not found for update.")
            notify_failure("Facility Not Found", f"Facility with ID {id_from_body} not found for update.")
            return jsonify({"error": "Facility not found"}), 404

        for key, value in data.items():
            setattr(facility, key, value)

        session.commit()
        updated_details = facility.to_dict()
        log_info(f"PUT /airport/facilities/{id_from_body} - End: Updated facility successfully.")
        notify_success("Facility Updated", "Facility updated successfully.", [updated_details])
        return jsonify(updated_details), 200
    except Exception as e:
        log_error(f"PUT /airport/facilities/{id} - Error: {str(e)}")
        notify_failure("Failed to Update Facility", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities', methods=['DELETE'])
def delete_facility():
    """
      Delete an airport facility by ID.

      URL Parameters:
          - facility_id (int): The ID of the facility to delete.

      Returns:
          - JSON with a success message or error details.

    """
    log_info("DELETE /airport/facilities - Start")
    try:
        facility_id = request.args.get('id')

        if not facility_id:
            log_warning("DELETE /airport/facilities - Warning: No ID provided in query parameters.")
            return jsonify({"error": "ID is required in the query parameters."}), 400

        facility_id = int(facility_id)

        facility = session.query(AirportFacility).get(facility_id)
        if facility is None:
            log_warning(f"DELETE /airport/facilities/{facility_id} - Warning: Facility not found for deletion.")
            notify_failure("Facility Not Found", f"Facility with ID {facility_id} not found for deletion.")
            return jsonify({"error": "Facility not found"}), 404

        facility_details = facility.to_dict()
        session.delete(facility)
        session.commit()
        log_info(f"DELETE /airport/facilities/{facility_id} - End: Deleted facility successfully.")
        notify_clear_success("Facility Deleted", "Facility deleted successfully.",
                             [facility_details])

        response_data = {
            "message": "Facility deleted successfully",
            "facility_details": facility_details
        }
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"DELETE /airport/facilities - Error: {str(e)}")
        notify_clear_failure("Failed to Delete Facility", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/airport/facilities/clear', methods=['DELETE'])
def clear_facilities():
    """
       Delete all airport facilities from the database.

       Returns:
           - JSON with a success message, total count of cleared facilities, or error details.

    """
    log_info("DELETE /airport/facilities/clear - Start")
    try:
        facilities = session.query(AirportFacility).all()
        count = len(facilities)

        if count == 0:
            log_warning("DELETE /airport/facilities/clear - Warning: No facilities to clear.")
            return jsonify({"message": "No facilities to clear."}), 404

        facility_details_list = [facility.to_dict() for facility in facilities]

        session.query(AirportFacility).delete()
        session.commit()

        log_info("DELETE /airport/facilities/clear - End: Cleared all facilities successfully.")
        notify_clear_success("All Facilities Cleared",
                             "All airport facilities have been cleared successfully.",
                             facility_details_list)

        response_data = {
            "message": "All facilities cleared successfully",
            "total_count": count,
            "cleared_facilities": facility_details_list
        }
        return jsonify(response_data), 200

    except Exception as e:
        log_error(f"DELETE /airport/facilities/clear - Error: {str(e)}")
        notify_clear_failure("Failed to Clear All Facilities", f"Error details: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    app.run(debug=True)
