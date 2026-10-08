"""Tkinter entry point for the Day Pass Management System."""
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta
from database import Database
from services import PassService
from socket_server import LocalSocketServer, socket_request

ROOT = Path(__file__).parent
(ROOT / 'logs').mkdir(exist_ok=True)
logging.basicConfig(
    filename=ROOT / 'logs' / 'app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)


class DayPassApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('DAY PASS MANAGEMENT SYSTEM')
        self.geometry('1366x768')
        self.minsize(1050, 650)
        self.configure(bg='#eef2f7')

        self.db = Database()
        self.db.ensure_demo()
        self.service = PassService(self.db, ROOT)
        self.server = LocalSocketServer(self.service)
        try:
            self.server.start()
        except OSError:
            logging.exception('Socket server startup failed')

        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('Treeview', rowheight=28, font=('Segoe UI', 10))
        self.style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))

        self.sidebar = tk.Frame(self, bg='#102a43', width=235)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar, text='◈  DAY PASS', bg='#102a43', fg='white', font=('Segoe UI', 20, 'bold')
        ).pack(anchor='w', padx=20, pady=(26, 2))
        tk.Label(
            self.sidebar, text='TRANSPORTATION SECTOR', bg='#102a43', fg='#9fb3c8', font=('Segoe UI', 9, 'bold')
        ).pack(anchor='w', padx=22, pady=(0, 28))

        self.content = tk.Frame(self, bg='#eef2f7')
        self.content.pack(fill='both', expand=True)

        self.current_page = 'DASHBOARD'
        for label in [
            'DASHBOARD',
            'DAY PASS MANAGEMENT',
            'QR VALIDATION',
            'USER TRACKING',
            'EXPIRY REMINDER',
            'SYSTEM STATUS',
            'EXIT'
        ]:
            tk.Button(
                self.sidebar,
                text=label,
                anchor='w',
                padx=18,
                relief='flat',
                bg='#102a43',
                fg='white',
                activebackground='#1976d2',
                activeforeground='white',
                font=('Segoe UI', 10, 'bold'),
                command=lambda x=label: self.navigate(x)
            ).pack(fill='x', ipady=13, padx=8, pady=2)

        self.navigate('DASHBOARD')
        self.protocol('WM_DELETE_WINDOW', self.close)

    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def header(self, title, sub='Transportation Sector'):
        top = tk.Frame(self.content, bg='#eef2f7')
        top.pack(fill='x', padx=28, pady=(24, 16))
        tk.Label(top, text=title, bg='#eef2f7', fg='#102a43', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
        tk.Label(top, text=sub, bg='#eef2f7', fg='#627d98', font=('Segoe UI', 11)).pack(anchor='w', pady=(3, 0))

    def button(self, parent, text, fn, color='#1976d2'):
        return tk.Button(
            parent,
            text=text,
            command=fn,
            bg=color,
            fg='white',
            activebackground=color,
            activeforeground='white',
            relief='flat',
            font=('Segoe UI', 10, 'bold'),
            padx=16,
            pady=10,
            cursor='hand2'
        )

    def navigate(self, page):
        if page == 'EXIT':
            self.close()
            return
        self.current_page = page
        self.clear()
        mapping = {
            'DASHBOARD': 'dashboard',
            'DAY PASS MANAGEMENT': 'passes',
            'QR VALIDATION': 'validation',
            'USER TRACKING': 'tracking',
            'EXPIRY REMINDER': 'expiry',
            'SYSTEM STATUS': 'status'
        }
        getattr(self, mapping.get(page, 'dashboard'))()

    def dashboard(self):
        self.header('DAY PASS MANAGEMENT SYSTEM', 'Transportation Sector  •  Local demonstration prototype')
        analytics = self.service.get_analytics()
        counts = analytics['counts']
        today_tx = analytics['today_transactions']
        active_cnt = analytics['active_passes']

        vals = [
            ('ACTIVE PASSES', active_cnt, '#1976d2'),
            ("TODAY'S TRANSACTIONS", today_tx, '#159a80'),
            ('QR VALIDATIONS', counts['qr_validations'], '#725ac1'),
            ('UNREAD ALERTS', analytics['unread_alerts'], '#e19b2c')
        ]
        cards = tk.Frame(self.content, bg='#eef2f7')
        cards.pack(fill='x', padx=28)
        for title, value, color in vals:
            box = tk.Frame(cards, bg='white', highlightbackground='#d9e2ec', highlightthickness=1)
            box.pack(side='left', fill='both', expand=True, padx=(0, 14), ipady=17)
            tk.Label(box, text=title, bg='white', fg='#627d98', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(18, 6))
            tk.Label(box, text=str(value), bg='white', fg=color, font=('Segoe UI', 26, 'bold')).pack(anchor='w', padx=20, pady=(0, 12))

        body = tk.Frame(self.content, bg='#eef2f7')
        body.pack(fill='both', expand=True, padx=28, pady=22)

        left = tk.Frame(body, bg='white')
        left.pack(side='left', fill='both', expand=True, padx=(0, 12))
        tk.Label(left, text='Quick actions', bg='white', fg='#102a43', font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=20, pady=18)
        for label, page in [
            ('Create a day pass', 'DAY PASS MANAGEMENT'),
            ('Validate demo QR', 'QR VALIDATION'),
            ('Record a passenger event', 'USER TRACKING'),
            ('Review pass expiry', 'EXPIRY REMINDER')
        ]:
            self.button(left, label, lambda p=page: self.navigate(p)).pack(anchor='w', padx=20, pady=6, fill='x')

        right = tk.Frame(body, bg='white', width=420)
        right.pack(side='left', fill='both', expand=True)
        tk.Label(right, text='Recent alerts', bg='white', fg='#102a43', font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=18, pady=18)
        for a in self.db.rows('SELECT alert_type, message, created_at FROM alerts ORDER BY id DESC LIMIT 5'):
            tk.Label(
                right,
                text=f"{a['alert_type']}  •  {a['created_at'][:16]}\n{a['message']}",
                bg='white',
                fg='#486581',
                font=('Segoe UI', 9),
                justify='left',
                wraplength=380
            ).pack(anchor='w', padx=18, pady=8)

    def passes(self):
        self.header('DAY PASS MANAGEMENT', 'Create a passenger day pass and its database-linked QR code')
        shell = tk.Frame(self.content, bg='#eef2f7')
        shell.pack(fill='both', expand=True, padx=28, pady=2)

        form = tk.Frame(shell, bg='white')
        form.pack(side='left', fill='y', padx=(0, 16), ipadx=18, ipady=18)
        preview = tk.Frame(shell, bg='white')
        preview.pack(side='left', fill='both', expand=True)

        tk.Label(form, text='Passenger details', bg='white', fg='#102a43', font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=20, pady=18)

        self.name = tk.StringVar(value='John Doe')
        self.pid = tk.StringVar(value='P001234')
        self.exp = tk.StringVar(value=(date.today() + timedelta(days=2)).isoformat())
        self.selected = None

        for label, var in [
            ('Passenger Name', self.name),
            ('Passenger ID', self.pid),
            ('Valid / Expiry Date (YYYY-MM-DD)', self.exp)
        ]:
            tk.Label(form, text=label, bg='white', fg='#486581', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(6, 3))
            tk.Entry(form, textvariable=var, width=34, font=('Segoe UI', 11), relief='solid', bd=1).pack(padx=20, pady=(0, 5), ipady=6)

        tk.Label(form, text='Pass Type', bg='white', fg='#486581', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=20, pady=(6, 3))
        self.ptype_var = tk.StringVar(value=PassService.PASS_TYPES[0])
        tk.OptionMenu(form, self.ptype_var, *PassService.PASS_TYPES).pack(padx=20, pady=(0, 10), fill='x')

        self.button(form, 'GENERATE PASS', self.create_pass).pack(fill='x', padx=20, pady=(10, 6))
        self.button(form, 'GENERATE QR', self.generate_qr, '#159a80').pack(fill='x', padx=20, pady=5)

        self.preview = preview
        tk.Label(preview, text='PASS PREVIEW', bg='white', fg='#102a43', font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=24, pady=20)
        self.preview_text = tk.Label(
            preview,
            text='Create or select a pass to preview details.',
            bg='white',
            fg='#627d98',
            justify='left',
            font=('Segoe UI', 11)
        )
        self.preview_text.pack(anchor='w', padx=26)
        self.qr_label = tk.Label(preview, bg='white')
        self.qr_label.pack(anchor='w', padx=25, pady=8)

        rows = self.db.rows('SELECT p.pass_id, u.name FROM passes p JOIN users u USING(passenger_id) ORDER BY p.id DESC')
        if rows:
            options = [x['pass_id'] for x in rows]
            self.pick = tk.StringVar(value=options[0])
            tk.Label(form, text='Select Existing Pass:', bg='white', fg='#486581', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=20, pady=(12, 2))
            tk.OptionMenu(form, self.pick, *options, command=lambda x: self.show_pass(x)).pack(padx=20, pady=2, fill='x')
            self.show_pass(options[0])

    def show_pass(self, pid):
        try:
            p = self.service.get_pass(pid)
            self.selected = p
            state, days = self.service.expiry_state(p['expiry_date'], p['status'])
            self.preview_text.config(
                text=(
                    f"Passenger Name: {p['name']}\n"
                    f"Passenger ID:   {p['passenger_id']}\n"
                    f"Pass ID:        {p['pass_id']}\n"
                    f"Pass Type:      {p['pass_type']}\n"
                    f"Valid Date:     {p['expiry_date']}\n"
                    f"Status:         {state} ({days} days left)"
                )
            )
            # Auto-display QR image if file exists
            path = self.service.qr_dir / (pid + '.png')
            if path.exists():
                img = tk.PhotoImage(file=str(path))
                self.qr_label.config(image=img)
                self.qr_label.image = img
        except Exception:
            logging.exception('Preview failed')

    def create_pass(self):
        try:
            p = socket_request(
                self.server.port,
                {
                    'action': 'CREATE_PASS',
                    'name': self.name.get(),
                    'passenger_id': self.pid.get(),
                    'expiry': self.exp.get(),
                    'pass_type': self.ptype_var.get()
                }
            )
            self.selected = p
            self.show_pass(p['pass_id'])
            messagebox.showinfo('Pass created', f"Pass {p['pass_id']} was saved successfully.")
        except Exception as e:
            logging.exception('Create pass failed')
            messagebox.showerror('Unable to create pass', str(e))

    def generate_qr(self):
        if not self.selected:
            messagebox.showwarning('Select a pass', 'Create or select a pass first.')
            return
        try:
            path = self.service.generate_qr(self.selected['pass_id'])
            img = tk.PhotoImage(file=str(path))
            self.qr_label.config(image=img)
            self.qr_label.image = img
            self.qr_path = path
        except Exception as e:
            logging.exception('QR generation failed')
            messagebox.showerror('QR error', str(e))

    def validation(self):
        self.header('QR VALIDATION', 'Validate a generated QR payload against the live SQLite database')
        area = tk.Frame(self.content, bg='white')
        area.pack(fill='both', expand=True, padx=28, pady=4)

        tk.Label(area, text='QR payload / data', bg='white', fg='#102a43', font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=22, pady=(18, 6))
        self.payload = tk.Text(area, height=7, font=('Consolas', 10), relief='solid', bd=1)
        self.payload.pack(fill='x', padx=22)

        self.result = tk.Label(area, text='Ready to validate', bg='white', fg='#627d98', font=('Segoe UI', 16, 'bold'))
        self.result.pack(anchor='w', padx=22, pady=16)

        self.detail = tk.Label(area, text='Pass details will appear here.', bg='white', fg='#486581', font=('Segoe UI', 11), justify='left')
        self.detail.pack(anchor='w', padx=22)

        bar = tk.Frame(area, bg='white')
        bar.pack(anchor='w', padx=22, pady=20)
        self.button(bar, 'VALIDATE DEMO QR', self.demo_validate).pack(side='left', padx=(0, 10))
        self.button(bar, 'LOAD / VALIDATE QR DATA', self.load_validate, '#159a80').pack(side='left')

    def demo_validate(self):
        rows = self.db.rows("SELECT * FROM passes WHERE status='ACTIVE' AND expiry_date>=? ORDER BY id DESC LIMIT 1", (date.today().isoformat(),))
        if not rows:
            messagebox.showwarning('No active pass', 'Create an active pass first.')
            return
        p = rows[0]
        self.payload.delete('1.0', 'end')
        self.payload.insert('1.0', self.service.payload(p['pass_id'], p['passenger_id'], p['qr_token'], p['expiry_date']))
        self.validate_current()

    def load_validate(self):
        chosen = filedialog.askopenfilename(
            title='Choose QR payload text',
            filetypes=[('Text / JSON', '*.txt *.json'), ('All files', '*.*')]
        )
        if chosen:
            try:
                self.payload.delete('1.0', 'end')
                self.payload.insert('1.0', Path(chosen).read_text(encoding='utf-8'))
                self.validate_current()
            except Exception as e:
                messagebox.showerror('Load error', str(e))
        elif not self.payload.get('1.0', 'end').strip():
            messagebox.showinfo('Enter payload', 'Paste the QR text payload into the box, then click Load / Validate again.')
        else:
            self.validate_current()

    def validate_current(self):
        try:
            res = socket_request(self.server.port, {'action': 'VALIDATE_QR', 'payload': self.payload.get('1.0', 'end').strip()})
            good = res['result'] == 'VALID PASS'
            self.result.config(text=f"{res['result']}  •  {res['message']}", fg='#16805d' if good else '#c0392b')
            p = res.get('pass')
            self.detail.config(
                text=(
                    f"Passenger:   {p['name']}\n"
                    f"Pass ID:     {p['pass_id']}\n"
                    f"Pass Type:   {p['pass_type']}\n"
                    f"Expiry Date: {p['expiry_date']}"
                    if p else 'No matching pass record.'
                )
            )
            self.refresh_dashboard_later()
        except Exception as e:
            logging.exception('QR validation failed')
            messagebox.showerror('Validation error', str(e))

    def tracking(self):
        self.header('USER TRACKING', 'Passenger activity events recorded locally; this is not GPS tracking')
        panel = tk.Frame(self.content, bg='white')
        panel.pack(fill='both', expand=True, padx=28, pady=4)

        rows = self.db.rows('SELECT timestamp, pass_id, event_type, location, status FROM tracking_events ORDER BY id DESC LIMIT 100')
        self.table(panel, ('timestamp', 'pass_id', 'event_type', 'location', 'status'), ('TIME', 'PASS ID', 'ACTIVITY', 'LOCATION', 'STATUS'), rows)

        bar = tk.Frame(panel, bg='white')
        bar.pack(anchor='w', padx=14, pady=15)
        self.track_pass = tk.StringVar(value=(rows[0]['pass_id'] if rows else 'DEMO-ACTIVE'))
        tk.Label(bar, text='Pass ID', bg='white', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=6)
        tk.Entry(bar, textvariable=self.track_pass, width=22, font=('Segoe UI', 10)).pack(side='left', padx=6)

        for ev in ['Entered Bus', 'Entered Metro', 'Light Rail Boarding', 'Pass Checked', 'Exited Station']:
            self.button(bar, ev.upper(), lambda x=ev: self.track(x), '#159a80').pack(side='left', padx=4)

    def track(self, event):
        try:
            loc = (
                'Bus Stop 42' if 'Bus' in event
                else 'Metro Central' if 'Metro' in event
                else 'Transit Platform' if 'Rail' in event
                else 'Turnstile 2' if 'Exited' in event
                else 'Main Gate'
            )
            socket_request(self.server.port, {'action': 'TRACK_EVENT', 'pass_id': self.track_pass.get(), 'event': event, 'location': loc})
            self.tracking()
        except Exception as e:
            messagebox.showerror('Tracking error', str(e))

    def expiry(self):
        self.header('PASS EXPIRY REMINDER', 'Review active, expiring soon, and expired demonstration passes')
        panel = tk.Frame(self.content, bg='white')
        panel.pack(fill='both', expand=True, padx=28, pady=4)

        rows = self.db.rows('SELECT p.pass_id, u.name, p.expiry_date, p.status, p.pass_type FROM passes p JOIN users u USING(passenger_id) ORDER BY p.expiry_date')
        enriched = []
        for r in rows:
            state, days = self.service.expiry_state(r['expiry_date'], r['status'])
            enriched.append({**r, 'status': state, 'days': days})

        self.table(panel, ('pass_id', 'name', 'pass_type', 'expiry_date', 'status', 'days'), ('PASS ID', 'PASSENGER NAME', 'PASS TYPE', 'EXPIRY DATE', 'CURRENT STATUS', 'DAYS LEFT'), enriched)

        tk.Label(
            panel,
            text='PASS EXPIRY REMINDER\nReview passes that are active or expiring. Select a pass to renew or cancel.',
            bg='white',
            fg='#b7791f',
            justify='left',
            font=('Segoe UI', 11, 'bold')
        ).pack(anchor='w', padx=20, pady=10)

        bar = tk.Frame(panel, bg='white')
        bar.pack(anchor='w', padx=20, pady=7)
        self.renew_id = tk.StringVar(value=rows[0]['pass_id'] if rows else '')
        self.renew_exp = tk.StringVar(value=(date.today() + timedelta(days=2)).isoformat())

        tk.Label(bar, text='Pass ID:', bg='white', font=('Segoe UI', 10)).pack(side='left', padx=4)
        tk.Entry(bar, textvariable=self.renew_id, width=22, font=('Segoe UI', 10)).pack(side='left', padx=5)
        tk.Label(bar, text='New Expiry:', bg='white', font=('Segoe UI', 10)).pack(side='left', padx=4)
        tk.Entry(bar, textvariable=self.renew_exp, width=14, font=('Segoe UI', 10)).pack(side='left', padx=5)
        self.button(bar, 'RENEW PASS', self.renew, '#159a80').pack(side='left', padx=5)
        self.button(bar, 'CANCEL PASS', self.cancel_selected, '#c0392b').pack(side='left', padx=5)

    def renew(self):
        try:
            self.service.renew(self.renew_id.get(), self.renew_exp.get())
            self.expiry()
            messagebox.showinfo('Renewed', 'Pass expiry updated in the database.')
        except Exception as e:
            messagebox.showerror('Renewal error', str(e))

    def cancel_selected(self):
        try:
            pid = self.renew_id.get()
            if not pid:
                messagebox.showwarning('Select Pass', 'Enter a pass ID to cancel.')
                return
            if messagebox.askyesno('Confirm Cancel', f'Are you sure you want to cancel pass {pid}?'):
                self.service.cancel_pass(pid, 'Cancelled by administrator')
                self.expiry()
                messagebox.showinfo('Cancelled', f'Pass {pid} status updated to CANCELLED.')
        except Exception as e:
            messagebox.showerror('Cancel error', str(e))

    def status(self):
        self.header('SYSTEM STATUS', 'Live status and database totals')
        panel = tk.Frame(self.content, bg='white')
        panel.pack(fill='both', expand=True, padx=28, pady=4)

        checks = [
            ('DATABASE', 'CONNECTED'),
            ('SOCKET SERVER', f'RUNNING (PORT {self.server.port})' if self.server.running else 'STOPPED'),
            ('QR SERVICE', 'READY'),
            ('WEB API', 'READY'),
            ('APPLICATION', 'RUNNING')
        ]
        for k, v in checks:
            color = '#16805d' if 'RUNNING' in v or v in ('CONNECTED', 'READY') else '#c0392b'
            tk.Label(panel, text=f'{k:<22}  {v}', bg='white', fg=color, font=('Consolas', 14, 'bold')).pack(anchor='w', padx=25, pady=8)

        tk.Label(panel, text='DATABASE TOTALS', bg='white', fg='#102a43', font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=25, pady=(16, 8))
        for k, v in self.db.counts().items():
            tk.Label(panel, text=f'{k.replace("_", " ").title():<22}  {v}', bg='white', fg='#334e68', font=('Consolas', 11)).pack(anchor='w', padx=25, pady=3)

    def table(self, parent, keys, labels, rows):
        frame = tk.Frame(parent, bg='white')
        frame.pack(fill='both', expand=True, padx=14, pady=14)
        tree = ttk.Treeview(frame, columns=keys, show='headings')
        for key, label in zip(keys, labels):
            tree.heading(key, text=label)
            tree.column(key, width=160, anchor='w')
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        for row in rows:
            tree.insert('', 'end', values=[row.get(k, '') for k in keys])

    def refresh_dashboard_later(self):
        if self.current_page == 'DASHBOARD':
            self.after(100, self.dashboard)

    def close(self):
        if self.server:
            self.server.stop()
        self.destroy()


if __name__ == '__main__':
    try:
        DayPassApp().mainloop()
    except Exception:
        logging.exception('Application startup failed')
        raise
