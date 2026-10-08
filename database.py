"""SQLite persistence for the local day pass prototype."""
from pathlib import Path
import sqlite3
from datetime import date, datetime, timedelta


class _ClosingConnection(sqlite3.Connection):
    """Connection context manager that also releases the file handle."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


class Database:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).parent / "data" / "daypass.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        con = sqlite3.connect(str(self.path), timeout=10, factory=_ClosingConnection)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def initialize(self):
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                passenger_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS passes(
                id INTEGER PRIMARY KEY,
                pass_id TEXT UNIQUE NOT NULL,
                passenger_id TEXT NOT NULL REFERENCES users(passenger_id),
                pass_type TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                status TEXT NOT NULL,
                qr_token TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions(
                id INTEGER PRIMARY KEY,
                pass_id TEXT,
                passenger_id TEXT,
                activity TEXT NOT NULL,
                location TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'SUCCESS'
            );
            CREATE TABLE IF NOT EXISTS qr_validations(
                id INTEGER PRIMARY KEY,
                pass_id TEXT,
                qr_token TEXT,
                validation_time TEXT NOT NULL,
                result TEXT NOT NULL,
                location TEXT DEFAULT 'Main Gate'
            );
            CREATE TABLE IF NOT EXISTS alerts(
                id INTEGER PRIMARY KEY,
                passenger_id TEXT,
                pass_id TEXT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tracking_events(
                id INTEGER PRIMARY KEY,
                passenger_id TEXT,
                pass_id TEXT,
                event_type TEXT NOT NULL,
                location TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bus_routes(
                id INTEGER PRIMARY KEY,
                route_id TEXT UNIQUE NOT NULL,
                route_name TEXT NOT NULL,
                total_stops INTEGER NOT NULL,
                stops_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS live_buses(
                id INTEGER PRIMARY KEY,
                bus_id TEXT UNIQUE NOT NULL,
                route_id TEXT NOT NULL,
                current_stop_index INTEGER DEFAULT 0,
                current_stop_name TEXT NOT NULL,
                status TEXT DEFAULT 'ON_ROUTE',
                speed INTEGER DEFAULT 35,
                occupancy TEXT DEFAULT '24 / 50 seats',
                last_updated TEXT NOT NULL
            );
            ''')
            for col, col_type in (
                ('lat', 'REAL'), 
                ('lng', 'REAL'), 
                ('delay_minutes', 'INTEGER DEFAULT 0'),
                ('is_live_driver', 'INTEGER DEFAULT 0'),
                ('last_telemetry_time', 'REAL DEFAULT 0'),
                ('accuracy', 'REAL DEFAULT 0'),
                ('heading', 'REAL DEFAULT 0'),
                ('last_ping', 'TEXT DEFAULT NULL')
            ):
                try:
                    c.execute(f"ALTER TABLE live_buses ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            for col, col_type in (
                ('role', "TEXT DEFAULT 'PASSENGER'"),
                ('password', "TEXT DEFAULT 'pass123'")
            ):
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

    def counts(self):
        with self.connect() as c:
            return {
                t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ('users', 'passes', 'transactions', 'qr_validations', 'alerts', 'tracking_events', 'live_buses')
            }

    def ensure_demo(self):
        with self.connect() as c:
            # Check if demo users exist; if not or if driver accounts are missing, seed them
            has_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            if not has_users:
                today = date.today()
                # Seed Passengers
                c.execute(
                    "INSERT INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                    ('P001234', 'John Doe', '+91-98421-01234', 'john.doe@trichytransit.in', 'PASSENGER', 'pass123')
                )
                c.execute(
                    "INSERT INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                    ('P004321', 'Sarah Connor', '+91-98421-04567', 'sarah.connor@trichytransit.in', 'PASSENGER', 'pass123')
                )
                # Seed Drivers
                c.execute(
                    "INSERT INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                    ('DRV-101', 'R. Murugan (Trichy Central Depot)', '+91-94431-88101', 'murugan.driver@trichytransit.in', 'DRIVER', 'drv123')
                )
                c.execute(
                    "INSERT INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                    ('DRV-204', 'S. Karthik (Chathiram Depot)', '+91-94431-88204', 'karthik.driver@trichytransit.in', 'DRIVER', 'drv123')
                )

                demos = [
                    ('DEMO-ACTIVE', 'P001234', 'Day Pass', 2, 'ACTIVE'),
                    ('DEMO-SOON', 'P001234', '24-Hour Tourist Pass', 0, 'ACTIVE'),
                    ('DEMO-EXPIRED', 'P001234', 'Student Transit Pass', -1, 'EXPIRED'),
                    ('DEMO-METRO', 'P004321', 'Weekend Pass', 3, 'ACTIVE'),
                ]
                for pid, uid, ptype, offset, status in demos:
                    exp = (today + timedelta(days=offset)).isoformat()
                    c.execute(
                        "INSERT INTO passes(pass_id,passenger_id,pass_type,issue_date,expiry_date,status,qr_token,created_at) VALUES(?,?,?,?,?,?,?,datetime('now'))",
                        (pid, uid, ptype, today.isoformat(), exp, status, f'demo-{pid.lower()}')
                    )
                    c.execute(
                        "INSERT INTO transactions(pass_id,passenger_id,activity,location,timestamp,status) VALUES(?,?,?,?,datetime('now'),?)",
                        (pid, uid, f'Pass Created: {ptype}', 'Trichy Central Bus Stand', 'DEMO')
                    )
                    c.execute(
                        "INSERT INTO alerts(passenger_id,pass_id,alert_type,message,created_at) VALUES(?,?,?,?,datetime('now'))",
                        (uid, pid, 'SYSTEM DEMO', f'Demonstration record generated for {pid}.')
                    )
                    c.execute(
                        "INSERT INTO tracking_events(passenger_id,pass_id,event_type,location,timestamp,status) VALUES(?,?,?,?,datetime('now'),?)",
                        (uid, pid, 'Pass Generated', 'Trichy Central Bus Stand', 'DEMO')
                    )
            else:
                # Ensure driver accounts exist even if passenger demo was previously seeded
                driver_exists = c.execute("SELECT COUNT(*) FROM users WHERE role = 'DRIVER'").fetchone()[0]
                if not driver_exists:
                    c.execute(
                        "INSERT OR IGNORE INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                        ('DRV-101', 'R. Murugan (Trichy Central Depot)', '+91-94431-88101', 'murugan.driver@trichytransit.in', 'DRIVER', 'drv123')
                    )
                    c.execute(
                        "INSERT OR IGNORE INTO users(passenger_id,name,phone,email,role,password,created_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                        ('DRV-204', 'S. Karthik (Chathiram Depot)', '+91-94431-88204', 'karthik.driver@trichytransit.in', 'DRIVER', 'drv123')
                    )

    def rows(self, sql, args=()):
        with self.connect() as c:
            return [dict(x) for x in c.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.connect() as c:
            cursor = c.execute(sql, args)
            return cursor.lastrowid

    def list_passes(self, status=None, query=None, limit=100):
        sql = '''
            SELECT p.*, u.name, u.phone, u.email 
            FROM passes p 
            JOIN users u USING(passenger_id)
            WHERE 1=1
        '''
        params = []
        if status:
            sql += ' AND p.status = ?'
            params.append(status)
        if query:
            sql += ' AND (p.pass_id LIKE ? OR u.name LIKE ? OR p.passenger_id LIKE ?)'
            pattern = f'%{query}%'
            params.extend([pattern, pattern, pattern])
        sql += ' ORDER BY p.id DESC LIMIT ?'
        params.append(limit)
        return self.rows(sql, params)

    def list_transactions(self, pass_id=None, limit=100):
        sql = '''
            SELECT t.*, 
                   p.expiry_date, 
                   p.status AS pass_status, 
                   p.pass_type,
                   u.name AS passenger_name
            FROM transactions t
            LEFT JOIN passes p ON t.pass_id = p.pass_id
            LEFT JOIN users u ON t.passenger_id = u.passenger_id
            WHERE 1=1
        '''
        params = []
        if pass_id:
            sql += ' AND t.pass_id = ?'
            params.append(pass_id)
        sql += ' ORDER BY t.id DESC LIMIT ?'
        params.append(limit)
        return self.rows(sql, params)

    def list_tracking(self, pass_id=None, limit=100):
        if pass_id:
            return self.rows(
                'SELECT * FROM tracking_events WHERE pass_id = ? ORDER BY id DESC LIMIT ?',
                (pass_id, limit)
            )
        return self.rows('SELECT * FROM tracking_events ORDER BY id DESC LIMIT ?', (limit,))

    def list_validations(self, limit=100):
        return self.rows('SELECT * FROM qr_validations ORDER BY id DESC LIMIT ?', (limit,))

    def list_alerts(self, unread_only=False, limit=100):
        if unread_only:
            return self.rows('SELECT * FROM alerts WHERE is_read = 0 ORDER BY id DESC LIMIT ?', (limit,))
        return self.rows('SELECT * FROM alerts ORDER BY id DESC LIMIT ?', (limit,))

    def mark_alert_read(self, alert_id=None, mark_all=False):
        with self.connect() as c:
            if mark_all:
                c.execute('UPDATE alerts SET is_read = 1 WHERE is_read = 0')
            elif alert_id:
                c.execute('UPDATE alerts SET is_read = 1 WHERE id = ?', (alert_id,))
        return True

    def delete_alert(self, alert_id):
        with self.connect() as c:
            c.execute('DELETE FROM alerts WHERE id = ?', (alert_id,))
        return True

    def clear_all_alerts(self):
        with self.connect() as c:
            c.execute('DELETE FROM alerts')
        return True

    def delete_transaction(self, tx_id):
        with self.connect() as c:
            c.execute('DELETE FROM transactions WHERE id = ?', (tx_id,))
        return True

    def get_analytics(self):
        today = date.today().isoformat()
        counts = self.counts()
        today_tx = self.rows('SELECT COUNT(*) n FROM transactions WHERE date(timestamp)=?', (today,))[0]['n']
        
        all_passes = self.rows('SELECT status, expiry_date, pass_type FROM passes')
        active_cnt = 0
        expiring_cnt = 0
        expired_cnt = 0
        cancelled_cnt = 0
        types_breakdown = {}

        for p in all_passes:
            ptype = p.get('pass_type', 'Day Pass')
            types_breakdown[ptype] = types_breakdown.get(ptype, 0) + 1
            if p.get('status') == 'CANCELLED':
                cancelled_cnt += 1
                continue
            exp = p.get('expiry_date', '')
            try:
                days = (date.fromisoformat(exp) - date.today()).days
                if days < 0 or p.get('status') == 'EXPIRED':
                    expired_cnt += 1
                elif days <= 1:
                    expiring_cnt += 1
                else:
                    active_cnt += 1
            except Exception:
                active_cnt += 1

        val_rows = self.rows('SELECT result, COUNT(*) n FROM qr_validations GROUP BY result')
        validations_by_result = {r['result']: r['n'] for r in val_rows}

        recent_alerts = self.list_alerts(limit=5)
        unread_alerts_count = len(self.rows('SELECT id FROM alerts WHERE is_read = 0'))

        return {
            'counts': counts,
            'today_transactions': today_tx,
            'active_passes': active_cnt,
            'expiring_passes': expiring_cnt,
            'expired_passes': expired_cnt,
            'cancelled_passes': cancelled_cnt,
            'pass_types': types_breakdown,
            'validations_breakdown': validations_by_result,
            'unread_alerts': unread_alerts_count,
            'recent_alerts': recent_alerts,
        }

    def get_user(self, passenger_id):
        rows = self.rows('SELECT * FROM users WHERE passenger_id = ?', (passenger_id,))
        return rows[0] if rows else None

    def authenticate_user(self, identifier, password=''):
        """Authenticate by passenger_id or email with optional password check."""
        rows = self.rows(
            'SELECT * FROM users WHERE passenger_id = ? OR email = ?',
            (identifier.strip(), identifier.strip())
        )
        if not rows:
            return None
        user = rows[0]
        # In prototype demo, if password matches or default password is accepted
        user_pw = user.get('password') or 'pass123'
        if not password or password == user_pw or password in ('pass123', 'drv123', 'demo'):
            return user
        return None

    def list_drivers(self):
        return self.rows("SELECT * FROM users WHERE role = 'DRIVER'")

