from sqlalchemy import Column, String
from app.database import Base


class User(Base):
    __tablename__ = "user_table"

    username = Column(String(100), primary_key=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
