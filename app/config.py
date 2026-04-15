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

    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_db_name: str = "companies_db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
