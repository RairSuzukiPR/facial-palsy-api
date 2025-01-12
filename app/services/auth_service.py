import bcrypt
import mysql

from app.db.models import User
from app.db.models.User import UserEdit


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
        cursor.execute("SELECT id, name, last_name, email, password_hash, eyelid_surgery, nasolabial_fold, nasolabial_fold_only_paralyzed_side FROM users WHERE users.email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def get_user_by_id(self, user_id: int):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, last_name, email, password_hash, eyelid_surgery, nasolabial_fold, nasolabial_fold_only_paralyzed_side FROM users WHERE users.id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def create_user(self, user: User):
        password_hash = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (name, last_name, email, password_hash, eyelid_surgery, nasolabial_fold, nasolabial_fold_only_paralyzed_side)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user.name, user.last_name, user.email, password_hash, user.eyelid_surgery, user.nasolabial_fold, user.nasolabial_fold_only_paralyzed_side)
            )
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def edit_user(self, user: UserEdit):
        password_hash = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET 
                    name = %s,
                    last_name = %s,
                    email = %s,
                    password_hash = %s,
                    eyelid_surgery = %s,
                    nasolabial_fold = %s,
                    nasolabial_fold_only_paralyzed_side = %s
                WHERE id = %s
                """,
                (
                    user.name,
                    user.last_name,
                    user.email,
                    password_hash,
                    user.eyelid_surgery,
                    user.nasolabial_fold,
                    user.nasolabial_fold_only_paralyzed_side,
                    user.id,
                )
            )
            self.connection.commit()
            return user.id
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()