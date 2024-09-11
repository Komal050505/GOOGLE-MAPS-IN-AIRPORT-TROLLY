from flask import Flask, jsonify, request
from sqlalchemy import func

from db_connections.configurations import session, DATABASE_URL
from email_setup.email_operations import notify_clear_failure, notify_clear_success, notify_failure, notify_success
from logging_package.logging_utility import log_error, log_info, log_warning
from user_models.tables import AirportFacility

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL


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
