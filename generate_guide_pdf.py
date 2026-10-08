"""Script to generate a comprehensive, professional PDF user guide and documentation."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total pages dynamically."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748b"))
        # Header rule & text
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "Tiruchirappalli City Transit - Operations & User Guide")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, page_str)
        self.drawString(54, 36, "Confidential - Project Documentation & Deployment Guide")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()


def build_pdf(filename="Project_Documentation_and_User_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom typography
    c_primary = colors.HexColor("#0284c7")
    c_dark = colors.HexColor("#0f172a")
    c_slate = colors.HexColor("#334155")
    c_sub = colors.HexColor("#64748b")
    c_accent = colors.HexColor("#f97316")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_dark,
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceAfter=15
    )
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_dark,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=c_slate,
        spaceAfter=6
    )
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a")
    )
    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.white
    )

    story = []

    # Title Banner
    story.append(Paragraph("Tiruchirappalli City Transit Portal", title_style))
    story.append(Paragraph("Comprehensive Deployment, User Manual & Architectural Reference", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primary, spaceAfter=15))

    # Executive Overview
    story.append(Paragraph("1. Project Executive Overview", h1_style))
    overview_text = (
        "The <b>Tiruchirappalli City Transit Portal</b> is an enterprise day pass management and real-time fleet "
        "tracking application tailored specifically for the public bus network of Tiruchirappalli (Trichy), Tamil Nadu, India. "
        "It integrates cryptographic QR-code ticketing with a dual-mode telemetry engine: an innovative <b>device-clock transit "
        "simulation</b> matching authentic bus schedules, and a <b>smartphone GPS telemetry cockpit</b> streaming genuine satellite "
        "telemetry via HTML5 geolocation with automatic 30-second disconnect fallbacks."
    )
    story.append(Paragraph(overview_text, body_style))

    # Prerequisites Table
    story.append(Paragraph("2. Prerequisites & System Requirements", h1_style))
    prereq_data = [
        [Paragraph("<b>Component</b>", body_style), Paragraph("<b>Minimum Requirement</b>", body_style), Paragraph("<b>Recommended</b>", body_style)],
        [Paragraph("Operating System", body_style), Paragraph("Windows 10/11, macOS 11+, Linux", body_style), Paragraph("Any modern 64-bit OS", body_style)],
        [Paragraph("Python Version", body_style), Paragraph("Python 3.9+", body_style), Paragraph("Python 3.11 / 3.12 / 3.14", body_style)],
        [Paragraph("Web Browser", body_style), Paragraph("Chrome 90+, Edge 90+, Firefox, Safari", body_style), Paragraph("Latest Chrome or Edge with GPS enabled", body_style)],
        [Paragraph("Git", body_style), Paragraph("Git 2.25+", body_style), Paragraph("Latest Git CLI", body_style)],
        [Paragraph("Network Port", body_style), Paragraph("TCP Port 5000 free", body_style), Paragraph("Localhost / Wi-Fi LAN", body_style)]
    ]
    t_prereq = Table(prereq_data, colWidths=[130, 180, 194])
    t_prereq.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_prereq)
    story.append(Spacer(1, 10))

    # How to Start the Project
    story.append(Paragraph("3. How to Start the Project (Quickstart Guide)", h1_style))
    
    steps = [
        "<b>Step 1: Clone or Open the Repository:</b><br/>"
        "<code>git clone https://github.com/gsk37690-tech/Bus-Pass-and-Live-Tracking-Software.git</code><br/>"
        "<code>cd Bus-Pass-and-Live-Tracking-Software</code>",
        
        "<b>Step 2: Install Python Dependencies:</b><br/>"
        "<code>pip install -r requirements.txt</code><br/>"
        "<i>(Packages: Flask, qrcode, Pillow, gunicorn, reportlab)</i>",

        "<b>Step 3: Run the Web Server:</b><br/>"
        "<code>python web_app.py</code><br/>"
        "The server will start on <b>http://127.0.0.1:5000</b>.",

        "<b>Step 4: Run Automated System Tests (Optional Self-Check):</b><br/>"
        "<code>python -m unittest tests/test_system.py</code><br/>"
        "Executes all 21 automated integration tests (Auth, Routing, Telemetry, Ticketing, Deletion)."
    ]
    for s in steps:
        story.append(Paragraph(s, body_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 10))

    # Core Features & Operations
    story.append(Paragraph("4. Core Features & Usage Instructions", h1_style))

    features = [
        ("A. Dual-Portal Authentication (/login)",
         "Separates Passengers and Bus Drivers with session management. "
         "Features 1-click quick logins:<br/>"
         "• <b>Passenger</b>: <code>P001234</code> / <code>pass123</code> (John Doe - Active Pass)<br/>"
         "• <b>Driver</b>: <code>DRV-101</code> / <code>drv123</code> (R. Murugan - Central Depot)<br/>"
         "Directs commuters to the Commuter Dashboard and drivers to the mobile Cockpit."),

        ("B. Tiruchirappalli (Trichy) Route Network",
         "Localized with authentic GPS coordinates and stops:<br/>"
         "• <b>Route 101</b>: Central Bus Stand (CBS) ⟷ Chathiram Bus Stand (Palakkarai, Thillai Nagar, Main Guard Gate)<br/>"
         "• <b>Route 204</b>: CBS ⟷ Srirangam Rajagopuram (HPO, Anna Statue, Cauvery Bridge, Thiruvanaikoil)<br/>"
         "• <b>Route 305</b>: CBS ⟷ NIT Trichy / BHEL (TVS Tollgate, Golden Rock, Thiruverumbur)<br/>"
         "• <b>Route 402</b>: Chathiram ⟷ Tiruchirappalli International Airport TRZ (Mannarpuram)"),

        ("C. Device-Clock Transit Simulation Engine",
         "Replaces artificial sleep-interval loops with mathematical progression. Reads device local time (HH:MM:SS) "
         "and calculates the exact interpolated coordinates (lat, lng), remaining distance, and ETA between stops along the schedule."),

        ("D. Mobile Driver Cockpit & Smartphone Satellite GPS (/driver)",
         "Mobile-optimized dashboard mount interface:<br/>"
         "• <b>Start/Stop Trip toggle</b>: Streams HTML5 geolocation (watchPosition) high-accuracy coordinates.<br/>"
         "• <b>HUD Metrics</b>: Live Speed (km/h), GPS Precision (± meters), Ping counter, Geodesic coords.<br/>"
         "• <b>Haversine Stop Detection</b>: Automatically identifies the nearest station and distance in meters.<br/>"
         "• <b>Screen Wake-Lock API</b>: Prevents mobile screen sleep during driving.<br/>"
         "• <b>30-Second Fallback</b>: Gracefully transitions back to clock schedule if driver stream stops.<br/>"
         "• <b>Onboard Ticket Inspector</b>: Drivers can scan/enter pass tokens at boarding doors."),

        ("E. Commuter Live Fleet Map & Stop Progression Timeline (/)",
         "Interactive Leaflet map centered at Trichy (10.7956, 78.6856). Displays dynamic status badges:<br/>"
         "• <code>🟢 SATELLITE GPS BROADCAST (Phone Active)</code> when a driver is streaming phone GPS.<br/>"
         "• <code>⏰ REAL-TIME CLOCK SYNC (Trichy Timetable)</code> when in schedule mode."),

        ("F. Digital Day Pass Management & QR Wallet",
         "Issue Day Passes, 24-Hour Tourist Passes, Student and Weekend passes. Generates cryptographically verifiable QR codes with PNG rendering and Base64 embedding."),

        ("G. QR Ticket Inspector (/ & Ticket Tab)",
         "Validates QR tokens against pass status, issue date, and expiration timestamp. Records validation audit events."),

        ("H. Audit Ledger & Pass Expiry Management",
         "Full transaction and boarding ledger with live validity checks (Active, Expiring Soon, Expired). "
         "Features dedicated single-click <b>🗑️ Delete Row</b> inside the Check Pass popup modal next to Renew Pass.")
    ]

    for title, desc in features:
        story.append(Paragraph(title, h2_style))
        story.append(Paragraph(desc, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 10))

    # Testing & Verification Table
    story.append(Paragraph("5. System Verification & Key URLs", h1_style))
    urls_data = [
        [Paragraph("<b>Interface / Endpoint</b>", body_style), Paragraph("<b>URL</b>", body_style), Paragraph("<b>Function</b>", body_style)],
        [Paragraph("Commuter Dashboard", body_style), Paragraph("http://127.0.0.1:5000/", body_style), Paragraph("Interactive Map, Passes, Ledger", body_style)],
        [Paragraph("Login Portal", body_style), Paragraph("http://127.0.0.1:5000/login", body_style), Paragraph("Role auth (Passenger / Driver)", body_style)],
        [Paragraph("Driver Cockpit", body_style), Paragraph("http://127.0.0.1:5000/driver", body_style), Paragraph("Smartphone GPS broadcast & HUD", body_style)],
        [Paragraph("Live Telemetry API", body_style), Paragraph("http://127.0.0.1:5000/api/bus-live/BUS-101", body_style), Paragraph("JSON coordinates & timeline", body_style)],
        [Paragraph("Health Diagnostic", body_style), Paragraph("http://127.0.0.1:5000/api/health", body_style), Paragraph("Fleet counts & DB integrity", body_style)]
    ]
    t_urls = Table(urls_data, colWidths=[130, 210, 164])
    t_urls.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_urls)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated PDF successfully: {filename}")


if __name__ == '__main__':
    build_pdf()
