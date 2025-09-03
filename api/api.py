from flask import Flask, request

from services.schedule_service import ScheduleService
from services.database_service import DatabaseService

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello, World!'

db_service = DatabaseService()
schedule_service = ScheduleService()

@app.route('/get_free_floors', methods=['GET'])
def get_free_floors():

    building = request.args.get('building').lower()
    floor = int(request.args.get('floor'))
    day = request.args.get('day').lower()
    min_free_time = int(request.args.get('min_free_time'))

    time_table = db_service.get_free_floors(building, floor, day)
    free_times = schedule_service.get_schedule_floor_inverse(time_table, min_free_time)

    return free_times

@app.route('/get_free_room', methods=['GET'])
def get_free_room():
    building = request.args.get('building').lower()
    room = request.args.get('room').lower()
    day = request.args.get('day').lower()
    min_free_time = int(request.args.get('min_free_time'))


    time_table = db_service.get_free_room(building, room, day)
    free_times = schedule_service.get_schedule_room_inverse(time_table, min_free_time)

    return free_times

if __name__ == '__main__':
    app.run(debug=True)
