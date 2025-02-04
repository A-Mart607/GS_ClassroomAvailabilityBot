import aiosqlite
import os

async def get_temp_connection():
    conn = await aiosqlite.connect('temp_DB.db')
    return conn

async def initialize_tables(conn):
    try:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS classrooms (
                    building TEXT,
                    floor INTEGER,
                    room TEXT,
                    PRIMARY KEY (building, floor, room)
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS times (
                    building TEXT REFERENCES classrooms(building) ON DELETE CASCADE,
                    floor INTEGER REFERENCES classrooms(floor) ON DELETE CASCADE,
                    room TEXT REFERENCES classrooms(room) ON DELETE CASCADE,
                    day TEXT,
                    start_time text,
                    end_time text,
                    PRIMARY KEY (building, floor, room, day, start_time, end_time)
                )
            """)

            await conn.commit()
            print("Database sucessfully initialized.")

    except Exception as e:
        print(f"Error occurred while initializing database: {e}")

async def insertRoom(conn, building_tuple):
    # Classroom (building, floor, room #)
    try:
        await conn.execute(
            'INSERT OR REPLACE INTO classrooms VALUES (?, ?, ?)', building_tuple
        )
        await conn.commit()
    except Exception as e:
        print(f'DB error occurred while attempting to add classroom info {building_tuple}: {e}')

async def insertTime(conn, building_tuple, date_time_tuple):
    # Times (classroom tuple + day + start time + end time)
    try:
        await conn.execute(
            'INSERT OR REPLACE INTO times VALUES (?, ?, ?, ?, ?, ?)',
            building_tuple + date_time_tuple
        )
        await conn.commit()
    except Exception as e:
        print(f'DB error occurred while attempting to add date and time info {date_time_tuple}: {e}')

def over_write_old_DB():
    old_name = 'temp_DB.db'
    new_name = 'class_time_DB.db'

    # Check if the old database (temp) exists
    if os.path.exists(old_name):
        # If the new database already exists, remove it before renaming
        if os.path.exists(new_name):
            os.remove(new_name)
            print(f"Existing {new_name} removed.")

        # Now safely rename the file
        os.rename(old_name, new_name)
        print(f"Database renamed from {old_name} to {new_name}.")
    else:
        print(f"{old_name} does not exist.")