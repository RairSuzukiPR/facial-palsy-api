import uuid
import mysql


class SessionService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection

    def new_session(self, user_id: str):
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                """
                    INSERT INTO sessions (session_id, user_id)
                    VALUES (%s, %s)
                """,
                (uuid.uuid4(), user_id)
            )
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

