import os
from sqlalchemy import create_engine, Column, String, DateTime, Text, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserProfile(Base):
    """
    Stores the CURRENT state of the user (used for context).
    """
    __tablename__ = "user_profiles"
    phone_number = Column(String, primary_key=True, index=True)
    profession = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    last_interaction = Column(DateTime, default=datetime.utcnow)

class InteractionLog(Base):
    """
    PERMANENT record of all interactions.
    Data here is NEVER deleted or updated (Insert Only).
    """
    __tablename__ = "interaction_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String, index=True)
    ip_address = Column(String, nullable=True)
    user_message = Column(Text)
    bot_response = Column(Text)
    detected_profession = Column(String, nullable=True)
    detected_location = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def log_interaction(phone_number, user_message, bot_response, ip_address=None, detected_profession=None, detected_location=None):
    """
    Saves a permanent record of the interaction.
    """
    db = SessionLocal()
    try:
        log = InteractionLog(
            phone_number=phone_number,
            ip_address=ip_address,
            user_message=user_message,
            bot_response=bot_response,
            detected_profession=detected_profession,
            detected_location=detected_location
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"❌ Logging Error: {e}")
        db.rollback()
    finally:
        db.close()

def update_user_profile(phone_number, profession=None, skills=None, location=None, lat=None, lon=None):
    """
    Updates the user's CURRENT profile context. 
    """
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
        if not user:
            user = UserProfile(phone_number=phone_number)
            db.add(user)
        
        # Only update fields if new data is provided
        if profession: user.profession = profession
        if skills: user.skills = skills
        if location: user.location = location
        if lat is not None and lon is not None:
            user.latitude = lat
            user.longitude = lon
            
        user.last_interaction = datetime.utcnow()
        db.commit()
    except Exception as e:
        print(f"❌ Profile Update Error: {e}")
        db.rollback()
    finally:
        db.close()

def get_user_profile(phone_number):
    db = SessionLocal()
    try:
        return db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
    finally:
        db.close()