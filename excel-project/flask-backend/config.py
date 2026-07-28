"""
Configuration for Excel Group of Schools Management System
============================================================
Set environment variables or modify this file for your deployment.
"""

import os

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'excel-schools-change-this-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///excel_schools.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHOOL_NAME = 'Excel Group of Schools'
    SCHOOL_MOTTO = 'Wea Sono la Cremma Della Terra'
    DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'offline')  # online or offline
    SYNC_ENDPOINT = os.environ.get('SYNC_ENDPOINT', '')  # URL of online system API
    SYNC_API_KEY = os.environ.get('SYNC_API_KEY', '')    # API key for sync
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

class OfflineConfig(Config):
    """Configuration for offline (local) deployment."""
    DEPLOYMENT_MODE = 'offline'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///excel_schools.db'

class OnlineConfig(Config):
    """Configuration for online (production) deployment.
    
    For MySQL/MariaDB:
        DATABASE_URL = mysql+pymysql://user:password@localhost/excel_schools
    
    For PostgreSQL:
        DATABASE_URL = postgresql://user:password@localhost/excel_schools
    """
    DEPLOYMENT_MODE = 'online'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///excel_schools.db')
    # For production, always set SECRET_KEY via environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY', None)
    
    @classmethod
    def validate(cls):
        if cls.SECRET_KEY is None:
            raise ValueError("SECRET_KEY must be set via environment variable for online deployment")
