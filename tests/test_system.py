import json
import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta

from database import Database
from services import PassService
from socket_server import LocalSocketServer, socket_request
from bus_service import BusTrackingService
from web_app import app


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / 'test.db')
        self.svc = PassService(self.db, self.root)
        self.bus_svc = BusTrackingService(self.db)
        self.bus_svc.simulation_active = False  # Keep deterministic during unit tests

    def tearDown(self):
        self.tmp.cleanup()

    def newpass(self, expiry=None, pass_type='Day Pass'):
        return self.svc.create_pass(
            'Test Passenger',
            'PTEST',
            (expiry or date.today() + timedelta(days=2)).isoformat(),
            pass_type=pass_type,
            phone='+1-555-0100',
            email='test@example.com'
        )

    def test_initialization_and_passenger(self):
        p = self.newpass()
        self.assertEqual(p['name'], 'Test Passenger')
        self.assertEqual(self.db.counts()['users'], 1)
        self.assertEqual(p['phone'], '+1-555-0100')
        self.assertEqual(p['email'], 'test@example.com')

    def test_pass_id_and_token(self):
        a = self.newpass()
        b = self.svc.create_pass(
            'Test Passenger',
            'PTEST2',
            (date.today() + timedelta(days=2)).isoformat()
        )
        self.assertTrue(a['pass_id'].startswith('P' + date.today().strftime('%Y%m%d')))
        self.assertNotEqual(a['pass_id'], b['pass_id'])
        self.assertGreaterEqual(len(a['qr_token']), 24)

    def test_valid_and_invalid_qr(self):
        p = self.newpass()
        payload = self.svc.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
        self.assertEqual(self.svc.validate(payload)['result'], 'VALID PASS')
        self.assertEqual(self.svc.validate(payload.replace(p['qr_token'], 'bad'))['result'], 'INVALID PASS')

    def test_expired_validation_and_expiry_math(self):
        p = self.newpass(date.today() - timedelta(days=1))
        payload = self.svc.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
        self.assertEqual(self.svc.validate(payload)['result'], 'PASS EXPIRED')
        self.assertEqual(self.svc.expiry_state(p['expiry_date'])[0], 'EXPIRED')

    def test_tracking_and_alerts(self):
        p = self.newpass()
        self.svc.track(p['pass_id'], 'Entered Bus', 'Bus Stop')
        self.assertGreaterEqual(self.db.counts()['tracking_events'], 1)
        self.assertGreaterEqual(self.db.counts()['alerts'], 1)

    def test_qr_file_and_socket_request(self):
        p = self.newpass()
        self.assertTrue(self.svc.generate_qr(p['pass_id']).exists())
        server = LocalSocketServer(self.svc)
        server.start()
        try:
            payload = self.svc.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
            r = socket_request(server.port, {'action': 'VALIDATE_QR', 'payload': payload})
            self.assertEqual(r['result'], 'VALID PASS')
            
            renewed = socket_request(server.port, {
                'action': 'RENEW_PASS',
                'pass_id': p['pass_id'],
                'expiry': (date.today() + timedelta(days=10)).isoformat()
            })
            self.assertEqual(renewed['expiry_date'], (date.today() + timedelta(days=10)).isoformat())

            cancelled = socket_request(server.port, {
                'action': 'CANCEL_PASS',
                'pass_id': p['pass_id'],
                'reason': 'Lost pass'
            })
            self.assertEqual(cancelled['status'], 'CANCELLED')

            stats = socket_request(server.port, {'action': 'GET_STATS'})
            self.assertIn('active_passes', stats)
        finally:
            server.stop()

    def test_create_alert_transaction_and_renewal(self):
        p = self.newpass()
        self.assertEqual(self.db.counts()['transactions'], 1)
        self.assertEqual(self.db.counts()['alerts'], 1)
        self.svc.renew(p['pass_id'], (date.today() + timedelta(days=5)).isoformat())
        self.assertEqual(self.svc.get_pass(p['pass_id'])['expiry_date'], (date.today() + timedelta(days=5)).isoformat())

    def test_cancellation_and_validation(self):
        p = self.newpass()
        payload = self.svc.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
        self.assertEqual(self.svc.validate(payload)['result'], 'VALID PASS')
        self.svc.cancel_pass(p['pass_id'], 'Refund requested')
        self.assertEqual(self.svc.get_pass(p['pass_id'])['status'], 'CANCELLED')
        self.assertEqual(self.svc.validate(payload)['result'], 'PASS CANCELLED')

    def test_base64_qr_and_history(self):
        p = self.newpass()
        b64 = self.svc.generate_qr_base64(p['pass_id'])
        self.assertTrue(b64.startswith('data:image/png;base64,'))
        history = self.svc.get_pass_history(p['pass_id'])
        self.assertEqual(history['pass']['pass_id'], p['pass_id'])
        self.assertGreaterEqual(len(history['transactions']), 1)

    def test_alerts_deletion(self):
        p = self.newpass()
        alerts = self.svc.get_alerts()
        self.assertGreaterEqual(len(alerts), 1)
        first_id = alerts[0]['id']
        self.svc.delete_alert(first_id)
        remaining = [a for a in self.svc.get_alerts() if a['id'] == first_id]
        self.assertEqual(len(remaining), 0)

    def test_audit_ledger_pass_expiry(self):
        p = self.newpass()
        txs = self.svc.get_transactions(pass_id=p['pass_id'])
        self.assertGreaterEqual(len(txs), 1)
        self.assertEqual(txs[0]['pass_validity'], 'ACTIVE')
        self.assertFalse(txs[0]['is_expired'])
        self.assertGreaterEqual(txs[0]['days_left'], 1)

    def test_bus_tracking_linear_timeline(self):
        buses = self.bus_svc.list_buses()
        self.assertGreaterEqual(len(buses), 1)
        bus_id = buses[0]['bus_id']
        timeline = self.bus_svc.get_bus_timeline(bus_id)
        
        stops = timeline['stops']
        self.assertGreater(len(stops), 3)

        # Check that EXACTLY ONE stop is current (Green) and ALL others are (Red)
        green_stops = [s for s in stops if s['is_current'] and s['highlight_color'] == 'green']
        red_stops = [s for s in stops if not s['is_current'] and s['highlight_color'] == 'red']
        
        self.assertEqual(len(green_stops), 1)
        self.assertEqual(len(red_stops), len(stops) - 1)

        # Advance bus and verify the green stop moved
        orig_stop_idx = green_stops[0]['stop_index']
        advanced = self.bus_svc.advance_bus(bus_id, direction=1)
        new_green = [s for s in advanced['stops'] if s['is_current']]
        self.assertGreaterEqual(len(new_green), 1)

    def test_trichy_route_coordinates(self):
        route = self.bus_svc.get_route('R101')
        self.assertIn('Central Bus Stand', route['stops'][0]['name'])
        # Verify coordinates are in Tiruchirappalli (approx 10.79 to 10.83 N, 78.68 to 78.70 E)
        self.assertAlmostEqual(route['stops'][0]['lat'], 10.7956, places=3)
        self.assertAlmostEqual(route['stops'][0]['lng'], 78.6856, places=3)


class FlaskWebTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.testing = True
        self.client = self.app.test_client()

    def test_index_route(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'DAY PASS TRANSPORTATION PORTAL', res.data)
        self.assertIn(b'Tiruchirappalli', res.data)

    def test_login_and_roles(self):
        # 1. Passenger Login
        p_res = self.client.post('/api/login', json={'identifier': 'P001234', 'role': 'PASSENGER'})
        self.assertEqual(p_res.status_code, 200)
        p_data = p_res.get_json()
        self.assertTrue(p_data['ok'])
        self.assertEqual(p_data['user']['role'], 'PASSENGER')

        # 2. Driver Login
        d_res = self.client.post('/api/login', json={'identifier': 'DRV-101', 'role': 'DRIVER'})
        self.assertEqual(d_res.status_code, 200)
        d_data = d_res.get_json()
        self.assertTrue(d_data['ok'])
        self.assertEqual(d_data['user']['role'], 'DRIVER')

        # 3. View Driver Cockpit
        driver_page = self.client.get('/driver')
        self.assertEqual(driver_page.status_code, 200)
        self.assertIn(b'Driver Mobile Cockpit', driver_page.data)

    def test_api_health(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertGreater(data['bus_fleet'], 0)

    def test_api_buses_and_timeline(self):
        res = self.client.get('/api/buses')
        self.assertEqual(res.status_code, 200)
        buses = res.get_json()['data']
        self.assertGreater(len(buses), 0)
        bus_id = buses[0]['bus_id']

        # Get bus timeline
        t_res = self.client.get(f'/api/buses/{bus_id}/timeline')
        self.assertEqual(t_res.status_code, 200)
        t_data = t_res.get_json()['data']
        self.assertIn('stops', t_data)
        
        # Advance bus
        adv_res = self.client.post(f'/api/buses/{bus_id}/advance', json={'direction': 1})
        self.assertEqual(adv_res.status_code, 200)

    def test_api_bus_live_telemetry_and_driver_streaming(self):
        res = self.client.get('/api/bus-live/BUS-101')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['bus_id'], 'BUS-101')
        self.assertIn('lat', data)
        self.assertIn('lng', data)
        self.assertIn('speed_kmh', data)
        # Lat/lng should be Trichy coordinates
        self.assertGreater(data['lat'], 10.0)
        self.assertLess(data['lat'], 11.5)
        self.assertGreater(data['lng'], 78.0)
        self.assertLess(data['lng'], 79.5)

        # Stream real GPS from driver smartphone
        post_res = self.client.post('/api/buses/telemetry', json={
            'bus_id': 'BUS-101',
            'latitude': 10.8220,
            'longitude': 78.6850,
            'speed': 42,
            'accuracy': 3.8
        })
        self.assertEqual(post_res.status_code, 200)
        telem = post_res.get_json()['data']
        self.assertTrue(telem['is_live_driver'])
        self.assertEqual(telem['lat'], 10.8220)
        self.assertEqual(telem['lng'], 78.6850)

    def test_api_alert_deletion(self):
        alerts_res = self.client.get('/api/alerts')
        self.assertEqual(alerts_res.status_code, 200)
        alerts = alerts_res.get_json()['data']
        if alerts:
            aid = alerts[0]['id']
            del_res = self.client.delete(f'/api/alerts/{aid}')
            self.assertEqual(del_res.status_code, 200)
            self.assertTrue(del_res.get_json()['ok'])

    def test_api_transactions_ledger_expiry(self):
        tx_res = self.client.get('/api/transactions')
        self.assertEqual(tx_res.status_code, 200)
        txs = tx_res.get_json()['data']
        self.assertGreater(len(txs), 0)
        self.assertIn('pass_validity', txs[0])

    def test_api_transaction_deletion(self):
        tx_res = self.client.get('/api/transactions')
        self.assertEqual(tx_res.status_code, 200)
        txs = tx_res.get_json()['data']
        if txs:
            tid = txs[0]['id']
            del_res = self.client.delete(f'/api/transactions/{tid}')
            self.assertEqual(del_res.status_code, 200)
            self.assertTrue(del_res.get_json()['ok'])



if __name__ == '__main__':
    unittest.main()
