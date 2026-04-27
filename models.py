from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    vehicle_no = Column(String)
    vehicle_type = Column(String)

    time_in = Column(DateTime, default=datetime.utcnow)
    time_out = Column(DateTime, nullable=True)

    status = Column(String)

    in_image = Column(String)
    out_image = Column(String)
