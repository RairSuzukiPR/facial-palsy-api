import mysql.connector
from app.core.config import settings


def get_connection():
    connection = mysql.connector.connect(
        host=settings.database_host,
        user=settings.database_user,
        password=settings.database_password,
        database=settings.database_name,
        port=settings.database_port,
    )
    return connection
