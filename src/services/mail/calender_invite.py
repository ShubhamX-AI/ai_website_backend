import smtplib
import datetime as dt
import uuid
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import icalendar
import pytz
from src.core.config import settings

logger = logging.getLogger(__name__)

def send_calendar_invite(
    recipient_email: str, 
    subject: str, 
    description: str, 
    location: str, 
    start_time: dt.datetime, 
    duration_hours: float = 1.0,
    sender_email: str = None,
    sender_password: str = None
):
    """
    Sends a 'Proper' iCalendar invite that works across Gmail, Outlook, and Apple Mail.
    """
    # Use settings if not provided
    sender_email = sender_email or settings.SENDER_EMAIL
    sender_password = sender_password or settings.SENDER_PASSWORD

    if not sender_email or not sender_password:
        logger.error("Sender email or password not configured.")
        return False

    try:
        # Timezone setup
        request_tz = pytz.timezone("Asia/Kolkata")
        utc_tz = pytz.utc
        
        # Ensure start_time has timezone info
        if start_time.tzinfo is None:
            start_dt = request_tz.localize(start_time)
        else:
            start_dt = start_time.astimezone(request_tz)

        end_dt = start_dt + dt.timedelta(hours=duration_hours)
        now_utc = dt.datetime.now(utc_tz)
        
        # --- 1. Create iCalendar Objects ---
        cal = icalendar.Calendar()
        cal.add('prodid', '-//AI Website Backend//Invite//EN')
        cal.add('version', '2.0')
        cal.add('method', 'REQUEST')
        
        event = icalendar.Event()
        event.add('summary', subject)
        event.add('description', description)
        event.add('location', location)
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('dtstamp', now_utc)
        event.add('uid', str(uuid.uuid4()))
        event.add('organizer', f"MAILTO:{sender_email}")
        
        # Add attendee with RSVP=TRUE for buttons
        attendee = icalendar.vCalAddress(f"MAILTO:{recipient_email}")
        attendee.params['RSVP'] = icalendar.vText('TRUE')
        attendee.params['ROLE'] = icalendar.vText('REQ-PARTICIPANT')
        event.add('attendee', attendee, encode=0)
        
        event.add('sequence', 0)
        event.add('status', 'CONFIRMED')
        event.add('transp', 'OPAQUE')
        
        # Add alarm (15-min reminder)
        alarm = icalendar.Alarm()
        alarm.add('action', 'DISPLAY')
        alarm.add('description', 'Reminder')
        alarm.add('trigger', dt.timedelta(minutes=-15))
        event.add_component(alarm)
        
        cal.add_component(event)
        
        # --- 2. Build Email ---
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Content-class'] = 'urn:content-classes:calendarmessage'

        alt_part = MIMEMultipart('alternative')
        msg.attach(alt_part)

        # Body
        body_text = f"You have an invitation for: {subject}\n\n{description}\n\nLocation: {location}\nTime: {start_dt.strftime('%Y-%m-%d %H:%M %Z')}"
        alt_part.attach(MIMEText(body_text, 'plain'))

        # Calendar part (CRITICAL for buttons)
        ics_string = cal.to_ical().decode("utf-8")
        cal_part = MIMEText(ics_string, "calendar; method=REQUEST", "utf-8")
        cal_part.add_header('Content-class', 'urn:content-classes:calendarmessage')
        alt_part.attach(cal_part)
        
        # ICS attachment backup
        attachment = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
        attachment.set_payload(cal.to_ical())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
        msg.attach(attachment)
        
        # --- 3. Send via SMTP ---
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        server.quit()
        
        logger.info(f"Invite sent to {recipient_email} successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to send invite: {e}")
        return False

