import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    storage_backend: str = "sqlite"

    # all: single-process local development; public/admin: split Docker deployment
    app_role: str = "all"
    cors_origins: str = ""

    sqlite_url: str = "sqlite:///./data/bookings.db"

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "lab"
    mysql_password: str = ""
    mysql_database: str = "lab_booking"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "lab"
    postgres_password: str = ""
    postgres_database: str = "lab_booking"

    json_data_dir: str = "./data"

    classrooms: str = "101实验室,102实验室,201机房,202机房,301多媒体教室,302多媒体教室,401研讨室,402研讨室"

    time_slots: str = "08:00-09:35,09:50-11:25,11:40-13:15,13:30-15:05,15:20-16:55,17:10-18:45"

    port: int = 8000
    admin_port: int = 8001

    admin_password: str = ""

    @property
    def classroom_list(self) -> List[str]:
        return [c.strip() for c in self.classrooms.split(",") if c.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def time_slot_list(self) -> List[str]:
        return [t.strip() for t in self.time_slots.split(",") if t.strip()]

    @property
    def database_url(self) -> str:
        backend = self.storage_backend.lower()
        if backend == "sqlite":
            return self.sqlite_url
        elif backend == "mysql":
            return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        elif backend == "postgres":
            return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        return self.sqlite_url

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
