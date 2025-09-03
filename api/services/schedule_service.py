from datetime import datetime

class ScheduleService:

    # todo: combine these two functions into one
    def get_schedule_floor_inverse(self, time_table, min_free_time):
        # day starts at 7 AM and ends at 10 PM
        day_start = datetime.strptime("07:00", "%H:%M")
        day_end = datetime.strptime("22:00", "%H:%M")

        # room : [] times
        free_times = dict()

        for room in set(room for room, _, _ in time_table):
            free_times[room] = []
            current_time = day_start

            # Filter occupied times for this specific room
            room_times = sorted([(start, end) for r, start, end in time_table if r == room])

            for start, end in room_times:
                start_time = datetime.strptime(start, "%H:%M")
                end_time = datetime.strptime(end, "%H:%M")

                if current_time < start_time and (start_time - current_time).total_seconds() / 60 >= min_free_time:
                    free_times[room].append(f"{current_time.strftime('%H:%M')} - {start_time.strftime('%H:%M')}")
                current_time = max(current_time, end_time)

            # Check for any remaining free time until the end of the day
            if current_time < day_end and (day_end - current_time).total_seconds() / 60 >= min_free_time:
                free_times[room].append(f"{current_time.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")


        return free_times

    def get_schedule_room_inverse(self, time_table, min_free_time):
        free_times = []
        day_start = datetime.strptime("07:00", "%H:%M")
        day_end = datetime.strptime("22:00", "%H:%M")
        curr_time = day_start

        for room, start, end in sorted(time_table):
            start_time = datetime.strptime(start, "%H:%M")
            end_time = datetime.strptime(end, "%H:%M")

            if curr_time < start_time and (start_time - curr_time).total_seconds() / 60 >= min_free_time:
                free_times.append(f"{curr_time.strftime('%H:%M')} - {start_time.strftime('%H:%M')}")
            curr_time = max(curr_time, end_time)

        # left over
        if curr_time < day_end and (day_end - curr_time).total_seconds() / 60 >= min_free_time:
            free_times.append(f"{curr_time.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")

        return free_times