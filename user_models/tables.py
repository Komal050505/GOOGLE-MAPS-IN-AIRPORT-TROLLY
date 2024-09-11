from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime

from db_connections.configurations import Base


class AirportFacility(Base):
    """
    The AirportFacility class represents different facilities within an airport.

    This class maps to the 'airport_facilities' table and includes information about various facilities in the airport.

    Attributes:
        id (int): The unique identifier for each facility (Primary Key).
        name (str): The name of the facility (e.g., Gate 1, Lounge A).
        category (str): The type of facility (e.g., Gate, Lounge, Washroom).
        coordinates (str): The latitude and longitude coordinates of the facility.
        description (str): A brief description of the facility.
        created_at (datetime): The date and time when the facility was added.
    """
    __tablename__ = 'airport_facilities'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    coordinates = Column(String(50), nullable=False)
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Converts the AirportFacility instance into a dictionary with formatted date and time.

        Returns:
            dict: A dictionary containing the facility's details such as id, name, category, coordinates, description,
                  and created_at with a 12-hour time format.
        """
        created_at_formatted = self.created_at.strftime("%I:%M %p") if self.created_at else None
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "coordinates": self.coordinates,
            "description": self.description,
            "created_at": created_at_formatted
        }
