from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="user")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    image_settings = relationship("ImageSettings", back_populates="user", uselist=False)

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(String)
    role = Column(String)  # 'user' or 'assistant'
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="messages")

class UserSettings(Base):
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    base_url = Column(String, default="https://api.openai.com/v1")
    model = Column(String, default="gpt-3.5-turbo")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1000)
    assistant_url = Column(String, nullable=True)
    use_assistant = Column(Boolean, default=False)
    
    # Relationship
    user = relationship("User", back_populates="settings")

class ImageSettings(Base):
    __tablename__ = 'image_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    base_url = Column(String, default="https://api.openai.com/v1")
    model = Column(String, default="dall-e-3")
    size = Column(String, default="1024x1024")
    quality = Column(String, default="standard")
    style = Column(String, default="natural")
    hdr = Column(Boolean, default=False)
    
    # Relationship
    user = relationship("User", back_populates="image_settings")

# Database initialization
def init_db():
    database_url = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine) 