import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="miguelveigamacedo",
        password="123456",
        database="mes_core"
    )
