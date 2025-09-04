from flask import Flask, request, jsonify

from services.schedule_service import ScheduleService
from services.database_service import DatabaseService
from services.db_constants import VALID_BUILDINGS, VALID_DAYS

app = Flask(__name__)


@app.route('/')
def index():
    return 'Hello!'

db_service = DatabaseService()
schedule_service = ScheduleService()

@app.route('/get_free_floors', methods=['GET'])
def get_free_floors():

    building = request.args.get('building').lower()
    floor = int(request.args.get('floor'))
    day = request.args.get('day').lower()
    min_free_time = int(request.args.get('min_free_time'))

    if building not in VALID_BUILDINGS:
        return jsonify({'error': f'Invalid building name. Valid buildings are: {", ".join(VALID_BUILDINGS)}'.title()}), 400
    if day not in VALID_DAYS:
        return jsonify({'error': f'Invalid day. Valid days are: {", ".join(VALID_DAYS)}'.title()}), 400

    time_table = db_service.get_free_floors(building, floor, day)
    free_times = schedule_service.get_schedule_floor_inverse(time_table, min_free_time)

    return jsonify(free_times)

@app.route('/get_free_room', methods=['GET'])
def get_free_room():
    building = request.args.get('building').lower()
    room = request.args.get('room').lower()
    day = request.args.get('day').lower()
    min_free_time = int(request.args.get('min_free_time'))

    if building not in VALID_BUILDINGS:
        return jsonify({'error': f'Invalid building name. Valid buildings are: {", ".join(VALID_BUILDINGS)}'.title()}), 400
    if day not in VALID_DAYS:
        return jsonify({'error': f'Invalid day. Valid days are: {", ".join(VALID_DAYS)}'.title()}), 400
    if not db_service.check_room_exists(building, room):
        return jsonify({'error': f'Room {room.upper()} does not exist in building {building.capitalize()}.'}), 400

    time_table = db_service.get_free_room(building, room, day)
    free_times = schedule_service.get_schedule_room_inverse(time_table, min_free_time)

    return jsonify(free_times)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000,debug=True)
