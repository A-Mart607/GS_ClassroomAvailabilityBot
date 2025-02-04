import asyncio
import random
import time
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from src.database import initialize_tables, get_temp_connection, insertTime, insertRoom, over_write_old_DB


async def main():
    conn = await get_temp_connection()
    await initialize_tables(conn)
    start_time = time.time()
    scrap = Scraper()
    majors_list = await scrap.get_majors()
    # await scrap.scrape_all_schedules(majors_list)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(elapsed_time)
    await conn.close()
    over_write_old_DB()

class Scraper:
    def __init__(self):
        # we'll write paramaters as they become needed
        self.url = 'https://globalsearch.cuny.edu/CFGlobalSearchTool/CFSearchToolController'

        self.college_payload = {
            'selectedInstName': 'Queens College | ',
            'inst_selection': 'QNS01',
            'selectedTermName': '2025 Spring Term',
            'term_value': '1252',
            'next_btn': 'Next'
        }

        self.class_search = {
            'selectedSubjectName': '',
            'subject_name': '',
            'selectedCCareerName': '',
            'courseCareer': '',
            'selectedCAttrName': '',
            'courseAttr': '',
            'selectedCAttrVName': '',
            'courseAttValue': '',
            'selectedReqDName': '',
            'reqDesignation': '',
            'selectedSessionName': '',
            'class_session': '',
            'selectedModeInsName': '',
            'meetingStart': '',
            'selectedMeetingStartName': 'less than',
            'AndMeetingStartText': '',
            'meetingStartText': '',
            'meetingEnd': 'LE',
            'selectedMeetingEndName': 'less than or equal to',
            'meetingEndText': '',
            'AndMeetingEndText': '',
            'daysOfWeek': 'I',
            'selectedDaysOfWeekName': 'include only these days',
            'instructor': 'B',
            'selectedInstructorName': 'begins with',
            'instructorName': '',
            'search_btn_search': 'Search'
        }

    # gets all majors for college in payload
    async def get_majors(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=self.college_payload) as response:
                page = await response.text()
                soup = BeautifulSoup(page, 'html.parser')

                subject_box = soup.find('select', {'class': 'form-search-display'})
                majors_list = subject_box.findAll('option')[1:]
                majors_list = [
                    (major.get_text(), major['value']) for major in majors_list
                ]

        return majors_list

    # feed in a list of majors which scrapes all the info for one major
    async def get_class_schedule(self, major: tuple, graduateLevel, graduateCode) -> None:
        async with aiohttp.ClientSession() as session:
            # load session with university selection cookies
            await session.post(self.url, data=self.college_payload)

            # load class info for payload
            self.update_payload(major[0], major[1], graduateLevel, graduateCode)

            # load next session with search results
            async with session.post(self.url, data=self.class_search) as response:
                class_page = await response.text()
                soup = BeautifulSoup(class_page, 'lxml')

                classes = soup.findAll('table', attrs={'class': 'classinfo'})
                my_classes = {}
                for classname in classes:
                    sections = classname.findAll('tbody')
                    for section in sections:
                        # not a part of schedule
                        if 'Winter' in section.find('td', attrs={'data-label': 'Section'}).get_text():
                            print(section.find('td', attrs={'data-label': 'Section'}).get_text())
                            continue
                        my_classes['times'] = [line.strip() for time in section.find_all('td', attrs={'data-label': 'DaysAndTimes'}) for line in time.stripped_strings]
                        my_classes['rooms'] = [line.strip() for room in section.find_all('td', attrs={'data-label': 'Room'}) for line in room.stripped_strings]
                        await self.split_and_push_data(my_classes)


    def update_payload(self, subjectName, subjectCode, graduateLevel, graduateCode) -> None:
        temp = {'selectedSubjectName': subjectName, 'subject_name': subjectCode,
                'selectedCCareerName': graduateLevel, 'courseCareer': graduateCode}
        self.class_search.update(temp)


    #the get_class_schedule function pushes to the database
    async def scrape_all_schedules (self, majorList):

        for major in majorList:
            await self.get_class_schedule(major, 'Undergraduate', 'UGRD')
            await asyncio.sleep(random.uniform(1, 3)) # does this actually make me look less sus? who knows

            await self.get_class_schedule(major, 'Graduate', 'GRAD')
            await asyncio.sleep(random.uniform(1, 3))


    async def split_and_push_data(self, class_info):
        # example {'time': ['MoWe 10:45AM - 12:00PM', 'MoWe 10:45AM - 12:00PM'], 'room': ['Kiely Hall 150', 'Kiely Hall 150']}
        days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
        for i, room in enumerate(class_info['rooms']):
            if room in ['Online-Asynchronous', 'TBA', 'Off-Campus', 'Online-Synchronous', 'Soccer Field']:
                continue
            building, room_num, floor = self.parse_room(room)
            times = class_info['times'][i].split()
            for day in days:
                if times[0].find(day) != -1:
                    await self.db_push(building, room_num, floor, day, times[-3], times[-1])

    def parse_room(self, room):
        room = room.split()
        building = ' '.join(room[:-1])
        floor = int(room[-1][0]) if not room[-1][0].isalpha() else int(room[-1][1])
        room_num = room[-1]
        return building, room_num, floor

    def convert_to_military_time(self, start_time, end_time):
        def to_military_time(time_str):
            return datetime.strptime(time_str, "%I:%M%p").strftime("%H:%M")

        start_military = to_military_time(start_time)
        end_military = to_military_time(end_time)

        return start_military, end_military


    async def db_push(self, building, room_num, floor, day, start_time, end_time):
        building = ''.join(building)
        start_time, end_time = self.convert_to_military_time(start_time, end_time)
        conn = await get_temp_connection()
        await insertRoom(conn, (building, floor, room_num))
        await insertTime(conn, (building, floor, room_num), (day,start_time, end_time))

        def debug_print():
            print(
                f""" 
                    Building: {building} 
                    Floor number: {floor} 
                    Room Num: {room_num} 
                    Day: {day} 
                    Start_Time: {start_time} 
                    End_Time: {end_time}
                """
            )
        # debug_print()
        await conn.close()
if __name__ == "__main__":
    asyncio.run(main())