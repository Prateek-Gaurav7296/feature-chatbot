import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # GitHub
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "")
    GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

    # Google Chat
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "./service_account.json")
    GOOGLE_CHAT_VERIFICATION_TOKEN = os.getenv("GOOGLE_CHAT_VERIFICATION_TOKEN", "")

    # Email
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "bot@example.com")

    # DB
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./featurebot.db")


settings = Settings()
