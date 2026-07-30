import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://ghg_user:ghg_password@localhost:5432/ghg_inventory",
    )
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))
    MAX_PROOF_UPLOAD_BYTES = int(os.getenv("MAX_PROOF_UPLOAD_BYTES", MAX_CONTENT_LENGTH))
