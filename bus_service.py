"""Real-time Bus Tracking Service with Trichy localization, device-clock schedule engine, and satellite driver GPS streaming."""
from datetime import datetime
import json
import math
import threading
import time


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates geodesic distance in meters between two lat/lng coordinates."""
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class BusTrackingService:
    ROUTES = [
        {
            'route_id': 'R101',
            'route_name': 'Route 101 - Central Bus Stand ⟷ Chathiram Bus Stand',
            'color': '#0284c7',
            'trip_duration_mins': 25,
            'stops': [
                {'id': 'S101-1', 'stop_id': 'S101-1', 'name': 'Central Bus Stand (CBS)', 'stop_name': 'Central Bus Stand (CBS)', 'platform': 'Bay 1', 'km': 0.0, 'lat': 10.7956, 'lng': 78.6856, 'sched': '08:00 AM', 'time': '08:00 AM'},
                {'id': 'S101-2', 'stop_id': 'S101-2', 'name': 'Palakkarai Roundana', 'stop_name': 'Palakkarai Roundana', 'platform': 'Bay 2', 'km': 2.3, 'lat': 10.8120, 'lng': 78.6920, 'sched': '08:06 AM', 'time': '08:06 AM'},
                {'id': 'S101-3', 'stop_id': 'S101-3', 'name': 'Thillai Nagar Main Road', 'stop_name': 'Thillai Nagar Main Road', 'platform': 'Bay 3', 'km': 4.1, 'lat': 10.8220, 'lng': 78.6850, 'sched': '08:13 AM', 'time': '08:13 AM'},
                {'id': 'S101-4', 'stop_id': 'S101-4', 'name': 'Main Guard Gate', 'stop_name': 'Main Guard Gate', 'platform': 'Bay 2', 'km': 6.0, 'lat': 10.8280, 'lng': 78.6940, 'sched': '08:20 AM', 'time': '08:20 AM'},
                {'id': 'S101-5', 'stop_id': 'S101-5', 'name': 'Chathiram Bus Stand', 'stop_name': 'Chathiram Bus Stand', 'platform': 'Bay 4', 'km': 7.2, 'lat': 10.8294, 'lng': 78.6925, 'sched': '08:25 AM', 'time': '08:25 AM'},
            ]
        },
        {
            'route_id': 'R204',
            'route_name': 'Route 204 - Central Bus Stand ⟷ Srirangam Rajagopuram',
            'color': '#10b981',
            'trip_duration_mins': 35,
            'stops': [
                {'id': 'S204-1', 'stop_id': 'S204-1', 'name': 'Central Bus Stand (CBS)', 'stop_name': 'Central Bus Stand (CBS)', 'platform': 'Bay 2', 'km': 0.0, 'lat': 10.7956, 'lng': 78.6856, 'sched': '08:10 AM', 'time': '08:10 AM'},
                {'id': 'S204-2', 'stop_id': 'S204-2', 'name': 'Head Post Office & Court', 'stop_name': 'Head Post Office & Court', 'platform': 'Bay 1', 'km': 1.8, 'lat': 10.8080, 'lng': 78.6890, 'sched': '08:16 AM', 'time': '08:16 AM'},
                {'id': 'S204-3', 'stop_id': 'S204-3', 'name': 'Anna Statue & Chathiram', 'stop_name': 'Anna Statue & Chathiram', 'platform': 'Bay 3', 'km': 5.2, 'lat': 10.8294, 'lng': 78.6925, 'sched': '08:26 AM', 'time': '08:26 AM'},
                {'id': 'S204-4', 'stop_id': 'S204-4', 'name': 'Cauvery Bridge North', 'stop_name': 'Cauvery Bridge North', 'platform': 'Bay 1', 'km': 7.6, 'lat': 10.8450, 'lng': 78.6930, 'sched': '08:33 AM', 'time': '08:33 AM'},
                {'id': 'S204-5', 'stop_id': 'S204-5', 'name': 'Thiruvanaikoil Temple', 'stop_name': 'Thiruvanaikoil Temple', 'platform': 'Bay 2', 'km': 9.4, 'lat': 10.8530, 'lng': 78.7050, 'sched': '08:39 AM', 'time': '08:39 AM'},
                {'id': 'S204-6', 'stop_id': 'S204-6', 'name': 'Srirangam Rajagopuram', 'stop_name': 'Srirangam Rajagopuram', 'platform': 'Bay 4', 'km': 11.5, 'lat': 10.8624, 'lng': 78.6908, 'sched': '08:45 AM', 'time': '08:45 AM'},
            ]
        },
        {
            'route_id': 'R305',
            'route_name': 'Route 305 - Central Bus Stand ⟷ NIT Trichy / BHEL',
            'color': '#f59e0b',
            'trip_duration_mins': 50,
            'stops': [
                {'id': 'S305-1', 'stop_id': 'S305-1', 'name': 'Central Bus Stand (CBS)', 'stop_name': 'Central Bus Stand (CBS)', 'platform': 'Bay 3', 'km': 0.0, 'lat': 10.7956, 'lng': 78.6856, 'sched': '07:30 AM', 'time': '07:30 AM'},
                {'id': 'S305-2', 'stop_id': 'S305-2', 'name': 'TVS Tollgate', 'stop_name': 'TVS Tollgate', 'platform': 'Bay 1', 'km': 3.2, 'lat': 10.7850, 'lng': 78.7050, 'sched': '07:38 AM', 'time': '07:38 AM'},
                {'id': 'S305-3', 'stop_id': 'S305-3', 'name': 'Ponmalai / Golden Rock', 'stop_name': 'Ponmalai / Golden Rock', 'platform': 'Bay 2', 'km': 6.5, 'lat': 10.7780, 'lng': 78.7250, 'sched': '07:47 AM', 'time': '07:47 AM'},
                {'id': 'S305-4', 'stop_id': 'S305-4', 'name': 'Thiruverumbur Junction', 'stop_name': 'Thiruverumbur Junction', 'platform': 'Bay 2', 'km': 12.0, 'lat': 10.7720, 'lng': 78.7620, 'sched': '08:02 AM', 'time': '08:02 AM'},
                {'id': 'S305-5', 'stop_id': 'S305-5', 'name': 'BHEL Main Complex', 'stop_name': 'BHEL Main Complex', 'platform': 'Bay 3', 'km': 16.5, 'lat': 10.7650, 'lng': 78.7880, 'sched': '08:14 AM', 'time': '08:14 AM'},
                {'id': 'S305-6', 'stop_id': 'S305-6', 'name': 'NIT Trichy Main Gate', 'stop_name': 'NIT Trichy Main Gate', 'platform': 'Bay 1', 'km': 20.0, 'lat': 10.7588, 'lng': 78.8132, 'sched': '08:20 AM', 'time': '08:20 AM'},
            ]
        },
        {
            'route_id': 'R402',
            'route_name': 'Route 402 - Chathiram ⟷ Tiruchirappalli International Airport',
            'color': '#8b5cf6',
            'trip_duration_mins': 35,
            'stops': [
                {'id': 'S402-1', 'stop_id': 'S402-1', 'name': 'Chathiram Bus Stand', 'stop_name': 'Chathiram Bus Stand', 'platform': 'Bay 1', 'km': 0.0, 'lat': 10.8294, 'lng': 78.6925, 'sched': '08:00 AM', 'time': '08:00 AM'},
                {'id': 'S402-2', 'stop_id': 'S402-2', 'name': 'Central Bus Stand (CBS)', 'stop_name': 'Central Bus Stand (CBS)', 'platform': 'Bay 4', 'km': 7.2, 'lat': 10.7956, 'lng': 78.6856, 'sched': '08:16 AM', 'time': '08:16 AM'},
                {'id': 'S402-3', 'stop_id': 'S402-3', 'name': 'Mannarpuram Junction', 'stop_name': 'Mannarpuram Junction', 'platform': 'Bay 2', 'km': 9.5, 'lat': 10.7820, 'lng': 78.7010, 'sched': '08:22 AM', 'time': '08:22 AM'},
                {'id': 'S402-4', 'stop_id': 'S402-4', 'name': 'Trichy International Airport (TRZ)', 'stop_name': 'Trichy International Airport (TRZ)', 'platform': 'Bay 1', 'km': 14.8, 'lat': 10.7654, 'lng': 78.7118, 'sched': '08:35 AM', 'time': '08:35 AM'},
            ]
        }
    ]

    INITIAL_BUSES = [
        {'bus_id': 'BUS-101', 'route_id': 'R101', 'start_stop_index': 1, 'occupancy': '28 / 50 seats', 'speed': 38, 'offset_seconds': 0},
        {'bus_id': 'BUS-101A', 'route_id': 'R101', 'start_stop_index': 0, 'occupancy': '22 / 50 seats', 'speed': 40, 'offset_seconds': 600},
        {'bus_id': 'BUS-204', 'route_id': 'R204', 'start_stop_index': 1, 'occupancy': '34 / 50 seats', 'speed': 32, 'offset_seconds': 300},
        {'bus_id': 'BUS-305', 'route_id': 'R305', 'start_stop_index': 2, 'occupancy': '44 / 50 seats', 'speed': 45, 'offset_seconds': 900},
        {'bus_id': 'BUS-402', 'route_id': 'R402', 'start_stop_index': 1, 'occupancy': '18 / 50 seats', 'speed': 42, 'offset_seconds': 450},
    ]

    def __init__(self, db):
        self.db = db
        self.simulation_active = True
        self.manual_step_offsets = {}  # {bus_id: integer offset for manual advance}
        self.live_telemetry_cache = {}  # {bus_id: {lat, lng, speed, heading, accuracy, timestamp}}
        self._lock = threading.Lock()
        self.initialize_fleet()

    def initialize_fleet(self):
        with self.db.connect() as c:
            now = datetime.now().isoformat(timespec='seconds')
            for r in self.ROUTES:
                c.execute(
                    '''INSERT INTO bus_routes(route_id, route_name, total_stops, stops_data, created_at)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(route_id) DO UPDATE SET 
                         route_name=excluded.route_name,
                         total_stops=excluded.total_stops,
                         stops_data=excluded.stops_data''',
                    (r['route_id'], r['route_name'], len(r['stops']), json.dumps(r['stops']), now)
                )

            for b in self.INITIAL_BUSES:
                route = next((x for x in self.ROUTES if x['route_id'] == b['route_id']), None)
                stop = route['stops'][b['start_stop_index']] if route else {'stop_name': 'Central Bus Stand (CBS)', 'lat': 10.7956, 'lng': 78.6856}
                stop_name = stop.get('stop_name') or stop.get('name')
                lat = float(stop.get('lat', 10.7956))
                lng = float(stop.get('lng', 78.6856))
                c.execute(
                    '''INSERT INTO live_buses(bus_id, route_id, current_stop_index, current_stop_name, status, speed, occupancy, last_updated, lat, lng, delay_minutes, is_live_driver)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,0)
                       ON CONFLICT(bus_id) DO UPDATE SET
                         route_id=excluded.route_id,
                         current_stop_name=excluded.current_stop_name,
                         lat=excluded.lat,
                         lng=excluded.lng''',
                    (b['bus_id'], b['route_id'], b['start_stop_index'], stop_name, 'ON_ROUTE', b['speed'], b['occupancy'], now, lat, lng, 3)
                )

    def list_buses(self):
        sql = '''
            SELECT b.*, r.route_name, r.total_stops
            FROM live_buses b
            JOIN bus_routes r ON b.route_id = r.route_id
            ORDER BY b.bus_id
        '''
        return self.db.rows(sql)

    def get_bus(self, bus_id):
        rows = self.db.rows('SELECT * FROM live_buses WHERE bus_id = ?', (bus_id,))
        if not rows:
            # Autocreate if needed
            route = self.ROUTES[0]
            now = datetime.now().isoformat(timespec='seconds')
            with self.db.connect() as c:
                c.execute(
                    '''INSERT INTO live_buses(bus_id, route_id, current_stop_index, current_stop_name, status, speed, occupancy, last_updated, lat, lng, delay_minutes, is_live_driver)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,0)
                       ON CONFLICT(bus_id) DO NOTHING''',
                    (bus_id, 'R101', 0, route['stops'][0]['name'], 'ON_ROUTE', 38, '24 / 50 seats', now, route['stops'][0]['lat'], route['stops'][0]['lng'], 3)
                )
            rows = self.db.rows('SELECT * FROM live_buses WHERE bus_id = ?', (bus_id,))
        return rows[0]

    def get_route(self, route_id):
        rows = self.db.rows('SELECT * FROM bus_routes WHERE route_id = ?', (route_id,))
        if not rows:
            # Fallback to in-memory definition
            r = next((x for x in self.ROUTES if x['route_id'] == route_id), self.ROUTES[0])
            return r
        route = dict(rows[0])
        route['stops'] = json.loads(route['stops_data'])
        return route

    def compute_device_clock_position(self, route, bus_id):
        """
        Calculates exact vehicle progression and GPS coordinates based on current device clock.
        Deterministic: matches device time without relying on random interval timers.
        """
        stops = route['stops']
        num_stops = len(stops)
        total_trip_mins = route.get('trip_duration_mins', max(15, num_stops * 6))
        total_trip_secs = total_trip_mins * 60

        # Current device local time converted to total seconds from start of day
        now = datetime.now()
        day_seconds = (now.hour * 3600) + (now.minute * 60) + now.second

        # Offset for this bus to stagger departures across the fleet
        bus_cfg = next((b for b in self.INITIAL_BUSES if b['bus_id'] == bus_id), None)
        offset = bus_cfg.get('offset_seconds', 0) if bus_cfg else 0
        manual_shift = self.manual_step_offsets.get(bus_id, 0)

        # Elapsed progress in current cyclical trip
        effective_seconds = day_seconds + offset + (manual_shift * 240)
        cycle_progress = (effective_seconds % total_trip_secs) / float(total_trip_secs)

        # Segment index along stops
        segment_float = cycle_progress * (num_stops - 1)
        curr_idx = int(segment_float)
        if curr_idx >= num_stops - 1:
            curr_idx = num_stops - 2
            sub_progress = 1.0
        else:
            sub_progress = segment_float - curr_idx

        next_idx = min(curr_idx + 1, num_stops - 1)

        stop_a = stops[curr_idx]
        stop_b = stops[next_idx]

        lat_a = float(stop_a['lat'])
        lng_a = float(stop_a['lng'])
        lat_b = float(stop_b['lat'])
        lng_b = float(stop_b['lng'])

        lat = round(lat_a + (lat_b - lat_a) * sub_progress, 6)
        lng = round(lng_a + (lng_b - lng_a) * sub_progress, 6)

        km_a = float(stop_a.get('km', 0.0))
        km_b = float(stop_b.get('km', 5.0))
        seg_dist = max(0.5, abs(km_b - km_a))
        dist_to_next = round(max(0.1, seg_dist * (1.0 - sub_progress)), 1)

        # Realistic transit speed
        speed = 36 + int((now.second % 12) - 4)

        return {
            'curr_idx': curr_idx,
            'next_idx': next_idx,
            'sub_progress': round(sub_progress, 3),
            'lat': lat,
            'lng': lng,
            'dist_to_next': dist_to_next,
            'speed': max(20, speed)
        }

    def get_live_telemetry(self, bus_id, route_data_override=None):
        """Returns live telemetry, giving priority to real driver smartphone GPS or device-clock simulation."""
        with self._lock:
            bus = self.get_bus(bus_id)
            if route_data_override and bus_id in route_data_override:
                route_name = route_data_override[bus_id].get('route_name', 'Trichy Transit Route')
                stops = route_data_override[bus_id].get('stops', [])
                route = {'route_id': bus['route_id'], 'route_name': route_name, 'stops': stops}
            else:
                route = self.get_route(bus['route_id'])
                stops = route['stops']

            total_stops = len(stops)

            # Check if there is an active driver phone GPS stream within the last 30 seconds
            cached_telem = self.live_telemetry_cache.get(bus_id)
            is_active_driver = False
            now_time = time.time()

            if cached_telem and (now_time - cached_telem.get('timestamp', 0) < 30.0):
                # 100% Genuine Satellite GPS Broadcast from Smartphone
                is_active_driver = True
                lat = cached_telem['lat']
                lng = cached_telem['lng']
                speed = cached_telem.get('speed', 35)
                accuracy = cached_telem.get('accuracy', 4.5)
                heading = cached_telem.get('heading', 0)

                # Determine nearest stop using Haversine formula
                closest_idx = 0
                min_meters = float('inf')
                for i, st in enumerate(stops):
                    d = haversine_distance(lat, lng, float(st['lat']), float(st['lng']))
                    if d < min_meters:
                        min_meters = d
                        closest_idx = i

                curr_idx = closest_idx
                next_idx = min(curr_idx + 1, total_stops - 1)
                sub_progress = 0.5
                dist_to_next = round(max(0.1, min_meters / 1000.0), 1)

            else:
                # Innovative Device-Clock Simulation Engine
                accuracy = 3.2
                heading = 45
                clock_data = self.compute_device_clock_position(route, bus_id)
                curr_idx = clock_data['curr_idx']
                next_idx = clock_data['next_idx']
                sub_progress = clock_data['sub_progress']
                lat = clock_data['lat']
                lng = clock_data['lng']
                dist_to_next = clock_data['dist_to_next']
                speed = clock_data['speed']

            stop_a = stops[curr_idx]
            stop_b = stops[next_idx]

            delay_mins = int(bus.get('delay_minutes') or 3)

            enriched_stops = []
            for i, st in enumerate(stops):
                is_curr = (i == curr_idx)
                is_passed = (i < curr_idx)
                st_id = st.get('id') or st.get('stop_id', f'S{i+1}')
                st_name = st.get('name') or st.get('stop_name', f'Stop {i+1}')
                sched_time = st.get('sched') or st.get('time', '08:00 AM')
                actual_time = f"{sched_time} (+{delay_mins}m)" if delay_mins > 0 else sched_time

                enriched_stops.append({
                    'id': st_id,
                    'stop_id': st_id,
                    'name': st_name,
                    'stop_name': st_name,
                    'km': float(st.get('km', 0.0)),
                    'lat': float(st.get('lat', 10.79)),
                    'lng': float(st.get('lng', 78.68)),
                    'sched': sched_time,
                    'scheduled_time': sched_time,
                    'actual_time': actual_time,
                    'platform': st.get('platform', f'Bay {i+1}'),
                    'is_passed': is_passed,
                    'is_current': is_curr,
                    'highlight_color': 'green' if is_curr else 'red',
                    'status_text': 'PASSED' if is_passed else ('CURRENT LOCATION' if is_curr else 'UPCOMING')
                })

            eta_next = stop_b.get('sched') or stop_b.get('time', '08:15 AM')
            if delay_mins > 0:
                eta_next = f"{eta_next} (+{delay_mins}m)"

            return {
                "bus_id": bus_id,
                "route_id": route.get('route_id', 'R101'),
                "route_name": route.get('route_name', 'Trichy Transit Line'),
                "lat": lat,
                "lng": lng,
                "speed_kmh": speed,
                "accuracy_meters": round(accuracy, 1),
                "heading": heading,
                "is_live_driver": is_active_driver,
                "driver_broadcast_active": is_active_driver,
                "last_stop_id": stop_a.get('id') or stop_a.get('stop_id', 'S1'),
                "next_stop_id": stop_b.get('id') or stop_b.get('stop_id', 'S2'),
                "delay_minutes": delay_mins,
                "distance_to_next_km": dist_to_next,
                "eta_next_stop": eta_next,
                "current_stop_index": curr_idx,
                "progress_ratio": sub_progress,
                "occupancy": bus.get('occupancy', '28 / 50 seats'),
                "stops": enriched_stops
            }

    def get_bus_timeline(self, bus_id):
        """Returns stop timeline structure for bus_id, consistent with live telemetry."""
        telemetry = self.get_live_telemetry(bus_id)
        bus = self.get_bus(bus_id)
        route = self.get_route(bus['route_id'])

        timeline_stops = []
        for s in telemetry['stops']:
            is_curr = s['is_current']
            is_passed = s['is_passed']
            timeline_stops.append({
                'stop_index': telemetry['stops'].index(s),
                'id': s['id'],
                'stop_id': s['stop_id'],
                'name': s['name'],
                'stop_name': s['name'],
                'platform': s['platform'],
                'km': s['km'],
                'lat': s['lat'],
                'lng': s['lng'],
                'sched': s['sched'],
                'scheduled_time': s['sched'],
                'actual_time': s['actual_time'],
                'is_current': is_curr,
                'is_passed': is_passed,
                'highlight_color': 'green' if is_curr else 'red',
                'badge_color': '#10b981' if is_curr else '#ef4444',
                'status_text': 'CURRENT LOCATION' if is_curr else ('DEPARTED' if is_passed else 'UPCOMING'),
                'status_desc': 'Bus is currently at this stop' if is_curr else ('Bus has departed' if is_passed else 'Upcoming stop on scheduled route')
            })

        curr_idx = telemetry['current_stop_index']
        next_idx = min(curr_idx + 1, len(timeline_stops) - 1)

        return {
            'bus': bus,
            'route': route,
            'current_stop': timeline_stops[curr_idx] if curr_idx < len(timeline_stops) else timeline_stops[0],
            'next_stop': timeline_stops[next_idx] if next_idx < len(timeline_stops) else None,
            'total_stops': len(timeline_stops),
            'stops': timeline_stops,
            'simulation_active': self.simulation_active,
            'is_live_driver': telemetry['is_live_driver'],
            'lat': telemetry['lat'],
            'lng': telemetry['lng'],
            'delay_minutes': telemetry['delay_minutes'],
            'distance_to_next_km': telemetry['distance_to_next_km'],
            'eta_next_stop': telemetry['eta_next_stop'],
            'progress_ratio': telemetry['progress_ratio']
        }

    def advance_bus(self, bus_id, direction=1):
        """Allows manual progression forward or backward along stops for testing/admin."""
        with self._lock:
            cur = self.manual_step_offsets.get(bus_id, 0)
            self.manual_step_offsets[bus_id] = cur + direction
            # If driver phone telemetry was cached, clear it so manual test advance takes effect
            if bus_id in self.live_telemetry_cache:
                del self.live_telemetry_cache[bus_id]
        return self.get_bus_timeline(bus_id)

    def set_bus_stop(self, bus_id, stop_index):
        with self._lock:
            self.manual_step_offsets[bus_id] = stop_index
        return self.get_bus_timeline(bus_id)

    def ingest_driver_telemetry(self, bus_id, lat, lng, speed=35, heading=0, accuracy=5.0):
        """Ingests live GPS broadcast from a real smartphone running /driver cockpit."""
        with self._lock:
            now_iso = datetime.now().isoformat(timespec='seconds')
            self.live_telemetry_cache[bus_id] = {
                'lat': float(lat),
                'lng': float(lng),
                'speed': int(speed) if speed is not None else 35,
                'heading': float(heading) if heading is not None else 0.0,
                'accuracy': float(accuracy) if accuracy is not None else 5.0,
                'timestamp': time.time()
            }
            # Update database record
            with self.db.connect() as c:
                c.execute(
                    '''UPDATE live_buses 
                       SET lat = ?, lng = ?, speed = ?, is_live_driver = 1, last_telemetry_time = ?, accuracy = ?, heading = ?, last_ping = ?
                       WHERE bus_id = ?''',
                    (float(lat), float(lng), int(speed or 35), time.time(), float(accuracy or 5.0), float(heading or 0), now_iso, bus_id)
                )
        return self.get_live_telemetry(bus_id)

    def update_telemetry(self, bus_id, stop_index=None, speed=None, occupancy=None, status=None, lat=None, lng=None, delay_minutes=None, accuracy=None, heading=None):
        """Backward-compatible telemetry update endpoint."""
        if lat is not None and lng is not None:
            return self.ingest_driver_telemetry(bus_id, lat, lng, speed=speed or 35, heading=heading or 0, accuracy=accuracy or 5.0)

        with self._lock:
            bus = self.get_bus(bus_id)
            route = self.get_route(bus['route_id'])
            stops = route['stops']
            now = datetime.now().isoformat(timespec='seconds')

            idx = stop_index if stop_index is not None else bus['current_stop_index']
            idx = idx % len(stops)
            cur_stop = stops[idx]
            stop_name = cur_stop.get('stop_name') or cur_stop.get('name')
            spd = speed if speed is not None else bus['speed']
            occ = occupancy if occupancy is not None else bus['occupancy']
            st = status if status is not None else bus['status']
            lt = lat if lat is not None else (bus.get('lat') or cur_stop.get('lat', 10.7956))
            lg = lng if lng is not None else (bus.get('lng') or cur_stop.get('lng', 78.6856))
            dl = delay_minutes if delay_minutes is not None else (bus.get('delay_minutes') or 3)

            with self.db.connect() as c:
                c.execute(
                    '''UPDATE live_buses 
                       SET current_stop_index = ?, current_stop_name = ?, speed = ?, occupancy = ?, status = ?, last_updated = ?, lat = ?, lng = ?, delay_minutes = ?
                       WHERE bus_id = ?''',
                    (idx, stop_name, spd, occ, st, now, lt, lg, dl, bus_id)
                )

        return self.get_bus(bus_id)

    def toggle_simulation(self, enable=None):
        if enable is not None:
            self.simulation_active = enable
        else:
            self.simulation_active = not self.simulation_active
        return self.simulation_active
