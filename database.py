import os
from sqlalchemy import create_engine, Column, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserProfile(Base):
    __tablename__ = "user_profiles"
    phone_number = Column(String, primary_key=True, index=True)
    profile_text = Column(String)
    profession = Column(Text)
    skills = Column(Text)
    location = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    last_interaction = Column(DateTime, default=datetime.utcnow)

# This creates both user_profiles AND the memory table needed by the agent
Base.metadata.create_all(bind=engine)

def update_user_data(phone_number, profession=None, skills=None, location=None, raw_text=None, lat=None, lon=None):
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
        if not user:
            user = UserProfile(phone_number=phone_number)
            db.add(user)
        
        if profession: user.profession = profession
        if skills: user.skills = skills
        if location: user.location = location
        if raw_text: user.profile_text = raw_text
        if lat is not None and lon is not None:
            user.latitude = lat
            user.longitude = lon
            
        user.last_interaction = datetime.utcnow()
        db.commit()
    except Exception as e:
        print(f"❌ DB Error: {e}")
        db.rollback()
    finally:
        db.close()

def get_user_profile(phone_number):
    db = SessionLocal()
    try:
        return db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
    finally:
        db.close()