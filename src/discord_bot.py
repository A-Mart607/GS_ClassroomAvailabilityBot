import aiohttp
import logging
import os
import platform
import re
import sqlite3
import time
from datetime import datetime

import discord
from colorama import Back, Fore, Style
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import get_temp_connection, initialize_tables, over_write_old_DB
from scraper import Scraper

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS]
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')

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

@client.tree.command(name="scrape", description="Scrape Global Search and Update DB")
@is_admin()
async def scrape(interaction: discord.Interaction):
    await interaction.response.send_message('Starting to scrape...this may take a moment.')
    await perform_scrape()  # Call the separate scraping function
    await interaction.followup.send("Scraping completed.")

def check_DB():
    return os.path.exists('../class_time_DB.db')


def parse_time_input(time_str: str) -> int:
    """
    Converts a time string like '1h30m', '1h 30m', '70m', '3h' into total minutes.
    Returns the number of minutes as an integer.
    """
    time_str = time_str.lower().replace(" ", "")  # Normalize input (remove spaces & lowercase)
    pattern = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?")  # Match hours and minutes

    match = pattern.fullmatch(time_str)
    if not match:
        raise ValueError("Invalid time format. Use formats like '1h30m', '1h 30m', '70m', '3h'.")

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0

    return hours * 60 + minutes


@client.tree.command(name="get_floor_times", description="Get free times for any floor in any building")
async def free_floors(interaction: discord.Interaction, building: str, floor: int, day: str, min_free_time: str = '30m'):

    try:
        min_free_time = parse_time_input(min_free_time)
    except ValueError as e:
        await interaction.response.send_message(str(e))

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                'building': building,
                'floor': floor,
                'day': day,
                'min_free_time': min_free_time
            }
            async with session.get(f'{API_BASE_URL}/get_free_floors', params=params) as response:
                if response.status != 200:
                    await interaction.response.send_message(f"API request failed with status code {response.status}")
                    return
                free_slots = await response.json()

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

@client.tree.command(name="help", description="Get help with the bot")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏫 Classroom Availability Bot Help",
        description="Find free classrooms at Queens College",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📅 Commands",
        value="`/get_floor_times` - Schedule for entire floor\n`/get_room_time` - Schedule for specific room",
        inline=False
    )
    
    embed.add_field(
        name="🏢 Buildings",
        value="Campbell, Colwin, Delany, G Building, Gymnasium, Honors, I Building, Kiely Hall, King Hall, Kissena, Klapper, Music, Powdermker, QueensHall, Rathaus, Remsen, Rosenthal, Science",
        inline=False
    )
    
    embed.add_field(
        name="📆 Days",
        value="Mo (Monday), Tu (Tuesday), We (Wednesday), Th (Thursday), Fri (Friday)",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="get_room_time", description="Get free times for any individual room in any building")
async def free_room(interaction: discord.Interaction, building: str, room: str, day: str, min_free_time : str = '30m'):
    if not check_DB():
        interaction.response.send_message("Database not initliazed yet!, try scraping or waiting :)")
        return
    try:
        min_free_time = parse_time_input(min_free_time)
    except ValueError as e:
        await interaction.response.send_message(str(e))

    try:

        async with aiohttp.ClientSession() as session:
            params = {
                'building': building,
                'room': room,
                'day': day,
                'min_free_time': min_free_time
            }
            async with session.get(f'{API_BASE_URL}/get_free_room', params=params) as response:
                if response.status != 200:
                    await interaction.response.send_message(f"API request failed with status code {response.status}")
                    return
                free_slots = await response.json()

                if free_slots:
                    print(f"Success on finding classes for {building, room, day}: {free_slots}")

                    embed = discord.Embed(
                        title=f"Free Times for {building} {room} on {day}",
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
                    await interaction.response.send_message(f"""Couldn't find free time for this room with this minimum time. Either the room number is wrong or the room is completly free today!""")

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

    if os.path.exists('../class_time_DB.db'):
        print('DB Exists')
    else:
        await perform_scrape()



#client.run(os.getenv("TOKEN2"))

# dev version
client.run(os.getenv("TEST_TOKEN"))