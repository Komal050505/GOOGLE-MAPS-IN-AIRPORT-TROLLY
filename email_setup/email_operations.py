# Standard Library Imports
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Project-Specific Imports
from email_setup.email_config import (ERROR_HANDLING_GROUP_EMAIL, RECEIVER_EMAIL, SENDER_EMAIL,
                                      SMTP_SERVER, SMTP_PORT, PASSWORD)


def get_formatted_time():
    """
    Returns the current time in 12-hour format with AM/PM.
    """
    return datetime.now().strftime("%I:%M %p")


def send_email(to_email, subject, body):
    """
    Sends an email to the specified recipients.

    :param to_email: List of email addresses to send the email to.
    :param subject: Subject of the email.
    :param body: Body content of the email.
    :return: None
    """
    if to_email is None:
        to_email = []

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(to_email)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())


def notify_success(subject, body, facilities=None, count=None):
    """
    Sends an email notification for successful operations.

    :param subject: Subject of the success email.
    :param body: Body content of the success email.
    :param facilities: Optional list of facility details to include in the email body.
    :param count: Optional count of the facilities to include in the email body.
    :return: None
    """
    if facilities:
        details = format_facility_details(facilities)
        body += f"<br><br>{details}"
    if count is not None:
        body += f"<br><br>Total Count: {count}"
    current_time = get_formatted_time()
    body += f"<br><br>Timestamp: {current_time}"
    send_email(RECEIVER_EMAIL, subject, body)


def notify_failure(subject, body, details=None):
    """
    Sends an email notification for failed operations.

    :param subject: Subject of the failure email.
    :param body: Body content of the failure email.
    :param details: Optional additional details to include in the email body.
    :return: None
    """
    if details:
        body += f"<br><br>Details:<br>{details}"
    current_time = get_formatted_time()
    body += f"<br><br>Timestamp: {current_time}"
    send_email(ERROR_HANDLING_GROUP_EMAIL, subject, body)


def notify_clear_success(subject, body, facilities=None):
    """
    Sends an email notification for successful clearing operations.

    :param subject: Subject of the clear success email.
    :param body: Body content of the clear success email.
    :param facilities: Optional list of facility details to include in the email body.
    :return: None
    """
    if facilities:
        details = format_facility_details(facilities)
        body += f"<br><br>{details}"
    current_time = get_formatted_time()
    body += f"<br><br>Timestamp: {current_time}"
    send_email(RECEIVER_EMAIL, subject, body)


def notify_clear_failure(subject, body, details=None):
    """
    Sends an email notification for failed clearing operations.

    :param subject: Subject of the clear failure email.
    :param body: Body content of the clear failure email.
    :param details: Optional additional details to include in the email body.
    :return: None
    """
    if details:
        body += f"<br><br>Details:<br>{details}"
    current_time = get_formatted_time()
    body += f"<br><br>Timestamp: {current_time}"
    send_email(ERROR_HANDLING_GROUP_EMAIL, subject, body)


def format_facility_details(facilities):
    """
    Formats facility details into an HTML table and includes the total count.

    :param facilities: List of facility dictionaries.
    :return: HTML formatted string of facility details with total count.
    """
    if not facilities:
        return "<p>No facilities found.</p>"

    # Start with the total count
    total_count = len(facilities)
    html = (f"<h3>Total Facilities: "
            f"{total_count}</h3><h3>Facility Details</h3><table "
            f"border='1'><tr><th>ID</th><th>Name</th><th>Category</th><th>Coordinates</th><th>Description</th><th"
            f">Created At</th></tr>")

    # Add facility details
    for facility in facilities:
        html += (f"<tr><td>{facility['id']}</td><td>{facility['name']}</td><td>{facility['category']}</td>"
                 f"<td>{facility['coordinates']}</td><td>{facility['description']}</td>"
                 f"<td>{facility['created_at']}</td></tr>")

    html += "</table>"
    return html


def format_steps(steps):
    """
    Formats navigation steps into an HTML string.

    :param steps: List of navigation steps.
    :return: HTML formatted string of navigation steps.
    """
    if not steps:
        return "<p>No steps found.</p>"

    html = ("<h3>Navigation Steps</h3><table border='1'><tr><th>Distance</th><th>Duration</th><th>Instruction</th><th"
            ">Start Location</th><th>End Location</th></tr>")
    for step in steps:
        html += (f"<tr><td>{step['distance']}</td><td>{step['duration']}</td>"
                 f"<td>{step['instruction']}</td><td>{step['start_location']}</td>"
                 f"<td>{step['end_location']}</td></tr>")

    html += "</table>"
    return html


def format_facility_details_with_distance_for_email(facilities):
    """
    Formats the facility details including distances for email notifications.
    :param facilities: List of facility dictionaries with distance included
    :return: HTML string with facility details and distances for email
    """
    formatted_details = ""
    for facility in facilities:
        formatted_details += f"""
        <div>
            <h4>{facility['name']} (ID: {facility['id']})</h4>
            <p><strong>Category:</strong> {facility['category']}</p>
            <p><strong>Coordinates:</strong> {facility['coordinates']}</p>
            <p><strong>Description:</strong> {facility['description']}</p>
            <p><strong>Distance:</strong> {facility['distance']}</p>
            <p><strong>Created At:</strong> {facility['created_at']}</p>
            <hr>
        </div>
        """
    return formatted_details


def prepare_geocode_success_message(address, latitude, longitude):
    """Prepare a success message for geocoding."""
    return f"""
        <h2>Geocoding Successful</h2>
        <p><strong>Address:</strong> {address}</p>
        <p><strong>Latitude:</strong> {latitude}</p>
        <p><strong>Longitude:</strong> {longitude}</p>
    """


def format_geocode_error_response(api_response):
    """Format the error response for geocoding failure."""
    if isinstance(api_response, dict):
        api_response = str(api_response)
    return f"Geocoding failed. API Response: {api_response}"


def format_reverse_geocode_error_response(api_response):
    """Format the error response for reverse geocoding failure."""
    if isinstance(api_response, dict):
        api_response = str(api_response)
    return f"Reverse geocoding failed. API Response: {api_response}"


def prepare_reverse_geocode_success_message(latitude, longitude, address):
    """Format the success message for reverse geocoding."""
    return (f"Reverse geocoding successful!<br><br>"
            f"Coordinates: Latitude: {latitude}, Longitude: {longitude}<br>"
            f"Address: {address}")
