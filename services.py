"""Business logic for passes, QR validation, tracking, renewal, alerts and analytics."""
import base64
from datetime import date, datetime
import io
import json
from pathlib import Path
import secrets
import uuid
import qrcode


class PassService:
    PASS_TYPES = [
        'Day Pass',
        '24-Hour Tourist Pass',
        'Student Transit Pass',
        'Senior Transit Pass',
        'Weekend Pass',
    ]

    def __init__(self, db, root=None):
        self.db = db
        self.root = Path(root) if root else db.path.parent.parent
        self.qr_dir = self.root / 'generated_qr'
        self.qr_dir.mkdir(exist_ok=True)

    @staticmethod
    def expiry_state(expiry, status='ACTIVE'):
        if status == 'CANCELLED':
            return ('CANCELLED', 0)
        try:
            days = (date.fromisoformat(expiry) - date.today()).days
        except Exception:
            return ('INVALID DATE', 0)
        if status == 'EXPIRED' or days < 0:
            return ('EXPIRED', days)
        if days <= 1:
            return ('EXPIRING SOON', days)
        return ('ACTIVE', days)

    @staticmethod
    def payload(pass_id, passenger_id, token, expiry):
        return f'PASS_ID={pass_id}\nPASSENGER_ID={passenger_id}\nTOKEN={token}\nEXPIRY={expiry}'

    @staticmethod
    def parse(payload):
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str) and payload.lstrip().startswith('{'):
            try:
                return json.loads(payload)
            except Exception:
                pass
        result = {}
        for line in str(payload).splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                result[k.strip().lower()] = v.strip()
            elif ':' in line:
                k, v = line.split(':', 1)
                result[k.strip().lower()] = v.strip()
        return result

    def create_pass(self, name, passenger_id, expiry, pass_type='Day Pass', phone='', email='', fare=5.00):
        name = name.strip()
        passenger_id = passenger_id.strip()
        if not name or not passenger_id:
            raise ValueError('Passenger name and ID are required.')
        try:
            expiry = date.fromisoformat(expiry).isoformat()
        except (ValueError, TypeError):
            raise ValueError('Enter expiry date as YYYY-MM-DD.')

        now = datetime.now().isoformat(timespec='seconds')
        token = secrets.token_urlsafe(24)

        with self.db.connect() as c:
            c.execute(
                '''INSERT INTO users(passenger_id, name, phone, email, created_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(passenger_id) DO UPDATE SET 
                     name=excluded.name,
                     phone=CASE WHEN excluded.phone != '' THEN excluded.phone ELSE users.phone END,
                     email=CASE WHEN excluded.email != '' THEN excluded.email ELSE users.email END''',
                (passenger_id, name, phone, email, now)
            )
            pass_id = 'P' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6].upper()
            state, _ = self.expiry_state(expiry)
            initial_status = 'EXPIRED' if state == 'EXPIRED' else 'ACTIVE'
            c.execute(
                '''INSERT INTO passes(pass_id, passenger_id, pass_type, issue_date, expiry_date, status, qr_token, created_at)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (pass_id, passenger_id, pass_type, date.today().isoformat(), expiry, initial_status, token, now)
            )
            self._transaction(c, pass_id, passenger_id, f'Pass Generated ({pass_type})', 'Main Gate', 'SUCCESS', now)
            self._alert(c, passenger_id, pass_id, 'PASS GENERATED', f'{pass_type} {pass_id} generated for {name}.', now)

        self.generate_qr(pass_id)
        return self.get_pass(pass_id)

    def get_pass(self, pass_id):
        rows = self.db.rows(
            '''SELECT p.*, u.name, u.phone, u.email 
               FROM passes p 
               JOIN users u USING(passenger_id) 
               WHERE p.pass_id=?''',
            (pass_id,)
        )
        if not rows:
            raise ValueError('Pass was not found.')
        p = dict(rows[0])
        state, days = self.expiry_state(p['expiry_date'], p['status'])
        p['computed_status'] = state
        p['days_left'] = days
        return p

    def list_passes(self, status=None, query=None, limit=100):
        rows = self.db.list_passes(status=status, query=query, limit=limit)
        enriched = []
        for r in rows:
            item = dict(r)
            state, days = self.expiry_state(item['expiry_date'], item['status'])
            item['computed_status'] = state
            item['days_left'] = days
            enriched.append(item)
        return enriched

    def generate_qr(self, pass_id):
        p = self.get_pass(pass_id)
        data = self.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
        path = self.qr_dir / (pass_id + '.png')
        img = qrcode.make(data)
        img.save(path)
        return path

    def generate_qr_base64(self, pass_id):
        p = self.get_pass(pass_id)
        data = self.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date'])
        img = qrcode.make(data)
        buffered = io.BytesIO()
        img.save(buffered, format='PNG')
        encoded = base64.b64encode(buffered.getvalue()).decode('ascii')
        return f'data:image/png;base64,{encoded}'

    def validate(self, payload, location='Main Gate'):
        d = self.parse(payload)
        pid = d.get('pass_id', '') or d.get('pid', '')
        token = d.get('token', '') or d.get('qr_token', '')
        now = datetime.now().isoformat(timespec='seconds')
        
        p = None
        if pid:
            found = self.db.rows('SELECT * FROM passes WHERE pass_id=?', (pid,))
            p = found[0] if found else None

        if not p:
            result = 'INVALID PASS'
        elif not secrets.compare_digest(str(token), str(p['qr_token'])):
            result = 'INVALID PASS'
        elif p['status'] == 'CANCELLED':
            result = 'PASS CANCELLED'
        elif date.fromisoformat(p['expiry_date']) < date.today() or p['status'] == 'EXPIRED':
            result = 'PASS EXPIRED'
        else:
            result = 'VALID PASS'

        passenger = p['passenger_id'] if p else d.get('passenger_id', '')
        with self.db.connect() as c:
            c.execute(
                'INSERT INTO qr_validations(pass_id, qr_token, validation_time, result, location) VALUES(?,?,?,?,?)',
                (pid or None, token, now, result, location)
            )
            self._transaction(c, pid or None, passenger, 'QR Validated', location, result, now)
            c.execute(
                'INSERT INTO tracking_events(passenger_id, pass_id, event_type, location, timestamp, status) VALUES(?,?,?,?,?,?)',
                (passenger or None, pid or None, 'QR Validated', location, now, result)
            )
            self._alert(
                c,
                passenger or None,
                pid or None,
                result,
                'ACCESS APPROVED' if result == 'VALID PASS' else f'ACCESS DENIED: {result}',
                now
            )

        return {
            'result': result,
            'pass': self.get_pass(pid) if p else None,
            'message': 'ACCESS APPROVED' if result == 'VALID PASS' else 'ACCESS DENIED',
            'location': location,
            'timestamp': now
        }

    @staticmethod
    def _transaction(c, pid, passenger, activity, location, status, now):
        c.execute(
            'INSERT INTO transactions(pass_id, passenger_id, activity, location, timestamp, status) VALUES(?,?,?,?,?,?)',
            (pid, passenger, activity, location, now, status)
        )

    @staticmethod
    def _alert(c, passenger, pid, kind, message, now):
        c.execute(
            'INSERT INTO alerts(passenger_id, pass_id, alert_type, message, created_at) VALUES(?,?,?,?,?)',
            (passenger, pid, kind, message, now)
        )

    def track(self, pass_id, event, location):
        p = self.get_pass(pass_id)
        now = datetime.now().isoformat(timespec='seconds')
        with self.db.connect() as c:
            c.execute(
                'INSERT INTO tracking_events(passenger_id, pass_id, event_type, location, timestamp, status) VALUES(?,?,?,?,?,?)',
                (p['passenger_id'], pass_id, event, location, now, 'SUCCESS')
            )
            self._transaction(c, pass_id, p['passenger_id'], event, location, 'SUCCESS', now)
            self._alert(c, p['passenger_id'], pass_id, 'PASSENGER EVENT', f'{event} at {location}.', now)
        return True

    def renew(self, pass_id, expiry):
        try:
            expiry = date.fromisoformat(expiry).isoformat()
        except ValueError:
            raise ValueError('Enter expiry date as YYYY-MM-DD.')
        p = self.get_pass(pass_id)
        now = datetime.now().isoformat(timespec='seconds')
        with self.db.connect() as c:
            c.execute('UPDATE passes SET expiry_date=?, status=? WHERE pass_id=?', (expiry, 'ACTIVE', pass_id))
            self._transaction(c, pass_id, p['passenger_id'], 'Pass Renewed', 'Main Gate', 'SUCCESS', now)
            self._alert(c, p['passenger_id'], pass_id, 'PASS RENEWED', f'Pass renewed through {expiry}', now)
        return self.get_pass(pass_id)

    def cancel_pass(self, pass_id, reason='User Request'):
        p = self.get_pass(pass_id)
        now = datetime.now().isoformat(timespec='seconds')
        with self.db.connect() as c:
            c.execute('UPDATE passes SET status=? WHERE pass_id=?', ('CANCELLED', pass_id))
            self._transaction(c, pass_id, p['passenger_id'], f'Pass Cancelled: {reason}', 'Main Gate', 'CANCELLED', now)
            self._alert(c, p['passenger_id'], pass_id, 'PASS CANCELLED', f'Pass {pass_id} was cancelled. Reason: {reason}', now)
        return self.get_pass(pass_id)

    def get_pass_history(self, pass_id):
        p = self.get_pass(pass_id)
        txs = self.get_transactions(pass_id=pass_id)
        tracking = self.db.list_tracking(pass_id=pass_id)
        validations = self.db.rows('SELECT * FROM qr_validations WHERE pass_id=? ORDER BY id DESC', (pass_id,))
        return {
            'pass': p,
            'transactions': txs,
            'tracking': tracking,
            'validations': validations
        }

    def get_transactions(self, pass_id=None, limit=100):
        rows = self.db.list_transactions(pass_id=pass_id, limit=limit)
        enriched = []
        today = date.today()
        for r in rows:
            item = dict(r)
            exp = item.get('expiry_date')
            p_status = item.get('pass_status')
            if not exp:
                item['pass_validity'] = 'N/A'
                item['is_expired'] = False
                item['days_left'] = None
            else:
                try:
                    exp_date = date.fromisoformat(exp)
                    days = (exp_date - today).days
                    item['days_left'] = days
                    if p_status == 'CANCELLED':
                        item['pass_validity'] = 'CANCELLED'
                        item['is_expired'] = True
                    elif days < 0 or p_status == 'EXPIRED':
                        item['pass_validity'] = 'EXPIRED'
                        item['is_expired'] = True
                    elif days <= 1:
                        item['pass_validity'] = 'EXPIRING SOON'
                        item['is_expired'] = False
                    else:
                        item['pass_validity'] = 'ACTIVE'
                        item['is_expired'] = False
                except Exception:
                    item['pass_validity'] = 'UNKNOWN'
                    item['is_expired'] = False
                    item['days_left'] = None
            enriched.append(item)
        return enriched

    def get_alerts(self, unread_only=False, limit=50):
        return self.db.list_alerts(unread_only=unread_only, limit=limit)

    def mark_alert_read(self, alert_id=None, mark_all=False):
        return self.db.mark_alert_read(alert_id=alert_id, mark_all=mark_all)

    def delete_alert(self, alert_id):
        return self.db.delete_alert(alert_id)

    def clear_all_alerts(self):
        return self.db.clear_all_alerts()

    def delete_transaction(self, tx_id):
        return self.db.delete_transaction(tx_id)

    def get_analytics(self):
        return self.db.get_analytics()
