import bcrypt
import mysql

from app.db.models import User


class AuthService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection

    def get_users(self):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        result = cursor.fetchall()
        cursor.close()
        return result

    def get_user_by_email(self, email: str):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, last_name, email, password_hash FROM users WHERE users.email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def create_user(self, user: User):
        password_hash = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (name, last_name, email, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (user.name, user.last_name, user.email, password_hash)
            )
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()