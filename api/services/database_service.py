
import sqlite3
from datetime import datetime
import os


class DatabaseService:
    def __init__(self, db_path=None):
        if db_path is None:
            # Get to the root GS_Scraper folder
            current_file = os.path.abspath(__file__)  # .../api/services/database_service.py
            services_dir = os.path.dirname(current_file)  # .../api/services/
            api_dir = os.path.dirname(services_dir)  # .../api/
            root_dir = os.path.dirname(api_dir)  # .../GS_Scraper/
            self.db_path = os.path.join(root_dir, 'class_time_DB.db')
        else:
            self.db_path = db_path
    
        print(f"Database path: {self.db_path}")

    def check_DB(self):
        return os.path.exists(f'{self.db_path}')

    def get_connection(self):
        if not self.check_DB():
            raise FileNotFoundError(f"Database file not found at {self.db_path}. Please run the scraper to create the database.")

        print(f"Connecting to: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        return conn

    def get_free_floors(self, building, floor, day):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT room, start_time, end_time 
        FROM times 
        WHERE building = ? AND floor = ? AND day = ? 
        ORDER BY room, start_time 
        """, (building, floor, day))

        occupied_times = cursor.fetchall()

        print(f"raw DB response: {occupied_times}")

        conn.close()
        return occupied_times

    def get_free_room(self, building, room, day):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT room, start_time, end_time 
            FROM times 
            WHERE building = ? AND room = ? AND day = ? 
            ORDER BY room, start_time
        """, (building, room, day))

        occupied_times = cursor.fetchall()
        print(f" raw DB for {building, room, day}: {occupied_times}")

        conn.close()
        return occupied_times
