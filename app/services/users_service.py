import mysql

class UsersService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection

    def get_users(self):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        result = cursor.fetchall()
        cursor.close()
        return result
