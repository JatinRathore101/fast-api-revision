from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = "postgres"
    server_port: int = 52243

    redis_host: str = "localhost"
    redis_port: int = 6379

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
