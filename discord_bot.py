import os
import sqlite3
from collections import defaultdict
from sqlite3.dbapi2 import sqlite_version_info

import discord
import asyncio
import time
from datetime import datetime
import platform
from discord.ext import commands
from database import get_temp_connection, initialize_tables, over_write_old_DB
from scraper import Scraper
from dotenv import load_dotenv
from colorama import Back, Fore, Style
from discord import app_commands, Interaction
import logging


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS]

client = commands.Bot(command_prefix='%', intents=discord.Intents.all())
def is_admin():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id not in ADMIN_IDS:
            # Log unauthorized attempt
            logging.warning(
                f"Unauthorized admin command attempt by {interaction.user} (ID: {interaction.user.id}) on command '{interaction.command.name}'"
            )
            raise app_commands.CheckFailure("User is not an admin.")  # Raise error only
        return True
    return app_commands.check(predicate)


@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        # Avoid sending another response if one has already been sent
        if not interaction.response.is_done():
            await interaction.response.send_message("You do not have permission to use this command. Contact @amart if the bot is out of date", ephemeral=True)

    else:
        # Log unexpected errors, but prevent duplicate responses
        logging.error(f"Unexpected error in command '{interaction.command.name}': {error}")

        if not interaction.response.is_done():
            await interaction.response.send_message("⚠ An unexpected error occurred.", ephemeral=True)


async def perform_scrape():
    print("Starting to scrape...this may take a moment.")
    start_time = time.time()
    scraper = Scraper()

    conn = await get_temp_connection()
    await initialize_tables(conn)
    try:
        majors_list = await scraper.get_majors()
        await scraper.scrape_all_schedules(majors_list)
        print("Scraping complete! Data has been saved to the database.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await conn.close()
        over_write_old_DB()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Scraping completed in {elapsed_time:.2f} seconds.")

def get_free_floors(building, floor, day):

    conn = sqlite3.connect('class_time_DB.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT room, start_time, end_time 
        FROM times 
        WHERE building = ? AND floor = ? AND day = ? 
        ORDER BY room, start_time
    """, (building, floor, day))

    occupied_times = cursor.fetchall()
    print(f" raw DB: {occupied_times}")
    # day starts at 7 AM and ends at 10 PM
    day_start = datetime.strptime("07:00", "%H:%M")
    day_end = datetime.strptime("22:00", "%H:%M")

    # room : [] times
    free_times = dict()

    for room in set(room for room, _, _ in occupied_times):
        free_times[room] = []
        current_time = day_start

        # Filter occupied times for this specific room
        room_times = [(start, end) for r, start, end in occupied_times if r == room]

        for start, end in room_times:
            start_time = datetime.strptime(start, "%H:%M")
            end_time = datetime.strptime(end, "%H:%M")

            if current_time < start_time:
                free_times[room].append(f"{current_time.strftime('%H:%M')} - {start_time.strftime('%H:%M')}")
            current_time = max(current_time, end_time)

        # Check for any remaining free time until the end of the day
        if current_time < day_end:
            free_times[room].append(f"{current_time.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")

    conn.close()
    return free_times

@client.tree.command(name="scrape", description="Scrape Global Search and Update DB")
@is_admin()
async def scrape(interaction: discord.Interaction):
    await interaction.response.send_message('Starting to scrape...this may take a moment.')
    await perform_scrape()  # Call the separate scraping function
    await interaction.followup.send("Scraping completed.")

def check_DB():
    return os.path.exists('class_time_DB.db')

@client.tree.command(name="get_floor_times", description="Get free times for any floor in any building")
async def free_floors(interaction: discord.Interaction, building: str, floor: int, day: str):
    if not check_DB():
        await interaction.response.send_message("Database not initliazed yet!, try scraping or waiting :)")
        return

    try:
        free_slots = get_free_floors(building, floor, day)
        if free_slots:
            print(f"Success on finding classes for {building, floor, day}: {free_slots}")

            embed = discord.Embed(
                title=f"Free Times for {building} Floor {floor} on {day}",
                color=discord.Color.blue()
            )

            for room in sorted(free_slots):
                # Convert each time slot to standard AM/PM format
                converted_times = [
                    f"{convert_to_standard_time(start)} - {convert_to_standard_time(end)}"
                    for start, end in (time_slot.split(" - ") for time_slot in free_slots[room])
                ]
                embed.add_field(name=f"Room {room}", value='\n'.join(converted_times), inline=False)

            await interaction.response.send_message(embed=embed)

        else:
            await interaction.response.send_message(
                f"No free times found for {building} floor {floor} on {day}."
            )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

def get_free_room(building, room, day):

    conn = sqlite3.connect('class_time_DB.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT room, start_time, end_time 
        FROM times 
        WHERE building = ? AND room = ? AND day = ? 
        ORDER BY room, start_time
    """, (building, room, day))

    occupied_times = cursor.fetchall()
    print(f" raw DB for {building, room, day}: {occupied_times}")

    free_times = []
    day_start = datetime.strptime("07:00", "%H:%M")
    day_end = datetime.strptime("22:00", "%H:%M")
    curr_time = day_start

    if not occupied_times:
        return []

    for room, start, end in occupied_times:
        start_time = datetime.strptime(start, "%H:%M")
        end_time = datetime.strptime(end, "%H:%M")

        if curr_time < start_time:
            free_times.append(f"{curr_time.strftime('%H:%M')} - {start_time.strftime('%H:%M')}")
        curr_time = max(curr_time, end_time)
    if curr_time < day_end:
        free_times.append(f"{curr_time.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")
    conn.close()
    return free_times

@client.tree.command(name="get_room_time", description="Get free times for any individual room in any building")
async def free_room(interaction: discord.Interaction, building: str, room: str, day: str):
    if not check_DB():
        interaction.response.send_message("Database not initliazed yet!, try scraping or waiting :)")
        return
    try:
        free_slots = get_free_room(building, room, day)
        if free_slots:
            print(f"Success on finding classes {free_slots}")
            embed = discord.Embed(
                title = f"Free times for {building} {room} on {day}",
                color=discord.Color.blue()
            )
            # Convert each time slot to standard AM/PM format
            converted_slots = [
                f"{convert_to_standard_time(start)} - {convert_to_standard_time(end)}"
                for start, end in (slot.split(" - ") for slot in free_slots)
            ]
            print(converted_slots)

            embed.add_field(name='Available Times', value= "\n".join(converted_slots))
            await interaction.response.send_message(embed=embed)

        else:
            await interaction.response.send_message(f"""Couldn't find free time for this room. Either the room number is wrong or the room is completly free today!""")

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

def convert_to_standard_time(military_time):
    # Convert military time to standard AM/PM format
    time_object = datetime.strptime(military_time, "%H:%M")
    return time_object.strftime("%I:%M %p")


@client.event
async def on_ready():
    prfx = prfx = (Back.BLACK + Fore.GREEN +
                   time.strftime("%H:%M:%S UTC", time.gmtime()) + Back.RESET + Fore.WHITE +
                   Style.BRIGHT)
    print(prfx + " Logged in as " + Fore.YELLOW + client.user.name)
    print(prfx + " BOT ID " + Fore.YELLOW + str(client.user.id))
    print(prfx + " Discord Version " + Fore.YELLOW)
    print(prfx + " Python Version " + Fore.YELLOW + str(platform.python_version()))
    print(f"Logged in as {client.user}")

    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} commands successfully.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    if os.path.exists('class_time_DB.db'):
        print('DB Exists')
    else:
        await perform_scrape()



client.run(os.getenv("TOKEN2"))