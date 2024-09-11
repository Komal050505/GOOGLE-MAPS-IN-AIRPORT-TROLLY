"""
This module is for establishing connection to the Database
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# Database configuration
DATABASE_URL = "postgresql://postgres:1995@localhost:5432/postgres"


# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(url=DATABASE_URL, echo=True)
conn = engine.connect()
Session = sessionmaker(bind=engine)
session = Session()
