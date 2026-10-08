"""Flask web server providing a hosted, interactive portal and REST API for the Day Pass Transportation System."""
import logging
import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory, session, redirect, url_for
from database import Database
from services import PassService
from bus_service import BusTrackingService

ROOT = Path(__file__).parent
app = Flask(__name__, template_folder=str(ROOT / 'templates'), static_folder=str(ROOT / 'static'))
app.secret_key = 'trichy-transit-live-secure-key-2026'

db = Database(ROOT / 'data' / 'daypass.db')
db.ensure_demo()
service = PassService(db, ROOT)
bus_service = BusTrackingService(db)


@app.route('/')
def index():
    user = session.get('user', {'passenger_id': 'P001234', 'name': 'John Doe', 'role': 'PASSENGER'})
    return render_template('index.html', user=user)


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/driver')
def driver_cockpit():
    user = session.get('user')
    if not user or user.get('role') != 'DRIVER':
        # Auto-assign driver demo session if accessed directly for frictionless usability
        session['user'] = {
            'passenger_id': 'DRV-101',
            'name': 'R. Murugan (Trichy Central Depot)',
            'role': 'DRIVER',
            'phone': '+91-98421-01234',
            'email': 'murugan.driver@trichytransit.in'
        }
    return render_template('driver.html', user=session['user'])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json(force=True) if request.is_json else {}
        identifier = data.get('identifier', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'PASSENGER').upper()

        if not identifier:
            # Fallback to demo credentials based on requested role
            if role == 'DRIVER':
                identifier = 'DRV-101'
            else:
                identifier = 'P001234'

        user = db.authenticate_user(identifier, password)
        if not user:
            # If user does not exist in DB yet, create or allow seamless passenger login
            if role == 'DRIVER':
                user = {
                    'passenger_id': identifier if identifier.startswith('DRV-') else f'DRV-{identifier}',
                    'name': f'Driver {identifier}',
                    'role': 'DRIVER',
                    'email': f'{identifier.lower()}@trichytransit.in',
                    'phone': '+91-94431-88100'
                }
            else:
                user = {
                    'passenger_id': identifier,
                    'name': data.get('name', f'Passenger {identifier}'),
                    'role': 'PASSENGER',
                    'email': data.get('email', f'{identifier.lower()}@transit.org'),
                    'phone': data.get('phone', '+91-98421-00000')
                }

        session['user'] = {
            'passenger_id': user['passenger_id'],
            'name': user['name'],
            'role': user.get('role', role),
            'email': user.get('email', ''),
            'phone': user.get('phone', '')
        }
        return jsonify({'ok': True, 'user': session['user']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/me', methods=['GET'])
def api_me():
    user = session.get('user', {'passenger_id': 'P001234', 'name': 'John Doe', 'role': 'PASSENGER'})
    return jsonify({'ok': True, 'user': user})


@app.route('/api/logout', methods=['POST'])
def api_logout_post():
    session.clear()
    return jsonify({'ok': True})



@app.route('/qr/<filename>')
def serve_qr(filename):
    return send_from_directory(str(service.qr_dir), filename)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        analytics = service.get_analytics()
        return jsonify({'ok': True, 'data': analytics})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/passes', methods=['GET'])
def list_passes():
    try:
        status = request.args.get('status')
        query = request.args.get('q')
        passes = service.list_passes(status=status, query=query, limit=100)
        return jsonify({'ok': True, 'data': passes})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/passes', methods=['POST'])
def create_pass():
    try:
        data = request.get_json(force=True)
        name = data.get('name', '').strip()
        passenger_id = data.get('passenger_id', '').strip()
        expiry = data.get('expiry', '').strip()
        pass_type = data.get('pass_type', 'Day Pass')
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        fare = float(data.get('fare', 5.00))

        if not name or not passenger_id or not expiry:
            return jsonify({'ok': False, 'error': 'Name, Passenger ID, and Expiry date are required.'}), 400

        created = service.create_pass(
            name=name,
            passenger_id=passenger_id,
            expiry=expiry,
            pass_type=pass_type,
            phone=phone,
            email=email,
            fare=fare
        )
        qr_b64 = service.generate_qr_base64(created['pass_id'])
        created['qr_image_url'] = f"/qr/{created['pass_id']}.png"
        created['qr_base64'] = qr_b64
        return jsonify({'ok': True, 'data': created}), 201
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/passes/<pass_id>', methods=['GET'])
def get_pass_details(pass_id):
    try:
        history = service.get_pass_history(pass_id)
        history['pass']['qr_image_url'] = f"/qr/{pass_id}.png"
        history['pass']['qr_base64'] = service.generate_qr_base64(pass_id)
        return jsonify({'ok': True, 'data': history})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/passes/<pass_id>/renew', methods=['POST'])
def renew_pass(pass_id):
    try:
        data = request.get_json(force=True) if request.is_json else {}
        expiry = data.get('expiry')
        if not expiry:
            return jsonify({'ok': False, 'error': 'New expiry date (YYYY-MM-DD) is required.'}), 400
        renewed = service.renew(pass_id, expiry)
        return jsonify({'ok': True, 'data': renewed})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/passes/<pass_id>/cancel', methods=['POST'])
def cancel_pass(pass_id):
    try:
        data = request.get_json(force=True) if request.is_json else {}
        reason = data.get('reason', 'Cancelled by administrator')
        cancelled = service.cancel_pass(pass_id, reason=reason)
        return jsonify({'ok': True, 'data': cancelled})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/validate', methods=['POST'])
def validate_qr():
    try:
        data = request.get_json(force=True)
        payload = data.get('payload', '')
        location = data.get('location', 'Main Gate')
        result = service.validate(payload, location=location)
        if result.get('pass'):
            result['pass']['qr_image_url'] = f"/qr/{result['pass']['pass_id']}.png"
        return jsonify({'ok': True, 'data': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/track', methods=['POST'])
def track_event():
    try:
        data = request.get_json(force=True)
        pass_id = data.get('pass_id', '').strip()
        event = data.get('event', 'Boarded Bus').strip()
        location = data.get('location', 'Main Station').strip()
        if not pass_id:
            return jsonify({'ok': False, 'error': 'Pass ID is required.'}), 400
        service.track(pass_id, event, location)
        return jsonify({'ok': True, 'message': f'Event {event} logged successfully at {location}.'})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/tracking', methods=['GET'])
def get_tracking():
    try:
        pass_id = request.args.get('pass_id')
        rows = db.list_tracking(pass_id=pass_id, limit=50)
        return jsonify({'ok': True, 'data': rows})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        pass_id = request.args.get('pass_id')
        rows = service.get_transactions(pass_id=pass_id, limit=100)
        return jsonify({'ok': True, 'data': rows})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    try:
        service.delete_transaction(tx_id)
        return jsonify({'ok': True, 'message': f'Transaction #{tx_id} deleted.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/validations', methods=['GET'])
def get_validations():
    try:
        rows = db.list_validations(limit=50)
        return jsonify({'ok': True, 'data': rows})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        alerts = service.get_alerts(unread_only=unread_only, limit=50)
        return jsonify({'ok': True, 'data': alerts})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/alerts/mark-read', methods=['POST'])
def mark_alerts():
    try:
        data = request.get_json(force=True) if request.is_json else {}
        alert_id = data.get('alert_id')
        mark_all = data.get('mark_all', False)
        service.mark_alert_read(alert_id=alert_id, mark_all=mark_all)
        return jsonify({'ok': True, 'message': 'Alerts updated.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
def delete_single_alert(alert_id):
    try:
        service.delete_alert(alert_id)
        return jsonify({'ok': True, 'message': f'Alert #{alert_id} deleted.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/alerts/delete-all', methods=['POST'])
def delete_all_alerts():
    try:
        service.clear_all_alerts()
        return jsonify({'ok': True, 'message': 'All alerts cleared.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ==========================================
# LIVE BUS TRACKING & TIMELINE API
# ==========================================

ROUTE_DATA = {
    "BUS-101": {
        "route_name": "Route 101 - Central Bus Stand ⟷ Chathiram Bus Stand",
        "stops": [
            {"id": "S101-1", "name": "Central Bus Stand (CBS)", "km": 0.0, "lat": 10.7956, "lng": 78.6856, "sched": "08:00 AM"},
            {"id": "S101-2", "name": "Palakkarai Roundana", "km": 2.3, "lat": 10.8120, "lng": 78.6920, "sched": "08:06 AM"},
            {"id": "S101-3", "name": "Thillai Nagar Main Road", "km": 4.1, "lat": 10.8220, "lng": 78.6850, "sched": "08:13 AM"},
            {"id": "S101-4", "name": "Main Guard Gate", "km": 6.0, "lat": 10.8280, "lng": 78.6940, "sched": "08:20 AM"},
            {"id": "S101-5", "name": "Chathiram Bus Stand", "km": 7.2, "lat": 10.8294, "lng": 78.6925, "sched": "08:25 AM"},
        ]
    },
    "BUS-204": {
        "route_name": "Route 204 - Central Bus Stand ⟷ Srirangam Rajagopuram",
        "stops": [
            {"id": "S204-1", "name": "Central Bus Stand (CBS)", "km": 0.0, "lat": 10.7956, "lng": 78.6856, "sched": "08:10 AM"},
            {"id": "S204-2", "name": "Head Post Office & Court", "km": 1.8, "lat": 10.8080, "lng": 78.6890, "sched": "08:16 AM"},
            {"id": "S204-3", "name": "Anna Statue & Chathiram", "km": 5.2, "lat": 10.8294, "lng": 78.6925, "sched": "08:26 AM"},
            {"id": "S204-4", "name": "Cauvery Bridge North", "km": 7.6, "lat": 10.8450, "lng": 78.6930, "sched": "08:33 AM"},
            {"id": "S204-5", "name": "Thiruvanaikoil Temple", "km": 9.4, "lat": 10.8530, "lng": 78.7050, "sched": "08:39 AM"},
            {"id": "S204-6", "name": "Srirangam Rajagopuram", "km": 11.5, "lat": 10.8624, "lng": 78.6908, "sched": "08:45 AM"},
        ]
    },
    "BUS-305": {
        "route_name": "Route 305 - Central Bus Stand ⟷ NIT Trichy / BHEL",
        "stops": [
            {"id": "S305-1", "name": "Central Bus Stand (CBS)", "km": 0.0, "lat": 10.7956, "lng": 78.6856, "sched": "07:30 AM"},
            {"id": "S305-2", "name": "TVS Tollgate", "km": 3.2, "lat": 10.7850, "lng": 78.7050, "sched": "07:38 AM"},
            {"id": "S305-3", "name": "Ponmalai / Golden Rock", "km": 6.5, "lat": 10.7780, "lng": 78.7250, "sched": "07:47 AM"},
            {"id": "S305-4", "name": "Thiruverumbur Junction", "km": 12.0, "lat": 10.7720, "lng": 78.7620, "sched": "08:02 AM"},
            {"id": "S305-5", "name": "BHEL Main Complex", "km": 16.5, "lat": 10.7650, "lng": 78.7880, "sched": "08:14 AM"},
            {"id": "S305-6", "name": "NIT Trichy Main Gate", "km": 20.0, "lat": 10.7588, "lng": 78.8132, "sched": "08:20 AM"},
        ]
    },
    "BUS-402": {
        "route_name": "Route 402 - Chathiram ⟷ Tiruchirappalli International Airport",
        "stops": [
            {"id": "S402-1", "name": "Chathiram Bus Stand", "km": 0.0, "lat": 10.8294, "lng": 78.6925, "sched": "08:00 AM"},
            {"id": "S402-2", "name": "Central Bus Stand (CBS)", "km": 7.2, "lat": 10.7956, "lng": 78.6856, "sched": "08:16 AM"},
            {"id": "S402-3", "name": "Mannarpuram Junction", "km": 9.5, "lat": 10.7820, "lng": 78.7010, "sched": "08:22 AM"},
            {"id": "S402-4", "name": "Trichy International Airport (TRZ)", "km": 14.8, "lat": 10.7654, "lng": 78.7118, "sched": "08:35 AM"},
        ]
    }
}


@app.route("/api/bus-live/<bus_id>", methods=['GET'])
def get_bus_telemetry(bus_id):
    """Live telemetry endpoint providing live transit status and GPS coordinates."""
    try:
        telemetry = bus_service.get_live_telemetry(bus_id, ROUTE_DATA)
        return jsonify(telemetry)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/buses', methods=['GET'])
def list_buses():
    try:
        buses = bus_service.list_buses()
        return jsonify({'ok': True, 'data': buses})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/buses/<bus_id>/timeline', methods=['GET'])
def get_bus_timeline(bus_id):
    try:
        timeline = bus_service.get_bus_timeline(bus_id)
        return jsonify({'ok': True, 'data': timeline})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/buses/<bus_id>/advance', methods=['POST'])
def advance_bus(bus_id):
    try:
        data = request.get_json(force=True) if request.is_json else {}
        direction = int(data.get('direction', 1))
        timeline = bus_service.advance_bus(bus_id, direction=direction)
        return jsonify({'ok': True, 'data': timeline})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/buses/<bus_id>/set_stop', methods=['POST'])
def set_bus_stop(bus_id):
    try:
        data = request.get_json(force=True)
        stop_index = int(data.get('stop_index', 0))
        timeline = bus_service.set_bus_stop(bus_id, stop_index)
        return jsonify({'ok': True, 'data': timeline})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/buses/telemetry', methods=['POST'])
def post_telemetry():
    """Ingests live smartphone GPS coordinates or simulation updates."""
    try:
        data = request.get_json(force=True)
        bus_id = data.get('bus_id')
        if not bus_id:
            return jsonify({'ok': False, 'error': 'bus_id is required.'}), 400

        lat = data.get('lat') or data.get('latitude')
        lng = data.get('lng') or data.get('longitude')
        speed = data.get('speed')
        heading = data.get('heading')
        accuracy = data.get('accuracy')
        stop_index = data.get('stop_index')
        occupancy = data.get('occupancy')
        status = data.get('status')

        if lat is not None and lng is not None:
            updated = bus_service.ingest_driver_telemetry(
                bus_id=bus_id,
                lat=float(lat),
                lng=float(lng),
                speed=int(speed) if speed is not None else 35,
                heading=float(heading) if heading is not None else 0.0,
                accuracy=float(accuracy) if accuracy is not None else 5.0
            )
        else:
            updated = bus_service.update_telemetry(
                bus_id=bus_id,
                stop_index=int(stop_index) if stop_index is not None else None,
                speed=int(speed) if speed is not None else None,
                occupancy=occupancy,
                status=status
            )
        return jsonify({'ok': True, 'data': updated})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500



@app.route('/api/buses/simulation/toggle', methods=['POST'])
def toggle_simulation():
    try:
        data = request.get_json(force=True) if request.is_json else {}
        enable = data.get('enable')
        active = bus_service.toggle_simulation(enable)
        return jsonify({'ok': True, 'simulation_active': active})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'tables': db.counts(),
        'qr_storage': str(service.qr_dir),
        'bus_fleet': len(bus_service.list_buses())
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Day Pass Transportation Portal on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=False)
