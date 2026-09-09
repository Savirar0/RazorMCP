from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    MAX_DISCOUNT_PERCENTAGE: float = 20.0
    MAX_TRANSACTION_LIMIT_INR: float = 10000.0
    ENVIRONMENT: str = "development"

    # LLM Provider (Groq — OpenAI-compatible endpoint)
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "gpt-oss-120b"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Deployment controls
    # Set DEMO_MODE=true on a public portfolio deployment. It returns a
    # deterministic, guardrail-checked simulated order and never calls Groq or
    # Razorpay, keeping public visitors from consuming secrets or API credit.
    DEMO_MODE: bool = False
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
