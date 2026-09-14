import asyncio
import html
import json
import logging
import os
import sys
from typing import Dict, Any
import aio_pika
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("notification_service")

QUEUE_NAME = "notifications"
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
# Leave SMTP_SERVER unset to log emails instead of sending them
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME") or None
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or None
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@example.com")
CONNECT_RETRY_SECONDS = 5

async def send_email(to: str, subject: str, body: str) -> None:
    """Send an email notification"""
    if not SMTP_SERVER:
        logger.info("SMTP_SERVER not configured; would send %r to %s", subject, to)
        return

    try:
        message = MIMEMultipart()
        message["From"] = EMAIL_FROM
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))

        # Port 465 uses implicit TLS; other ports (587) upgrade with STARTTLS
        await aiosmtplib.send(
            message,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            username=SMTP_USERNAME,
            password=SMTP_PASSWORD,
            use_tls=SMTP_PORT == 465,
            start_tls=None if SMTP_PORT == 465 else True,
        )

        logger.info(f"Email sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def get_notification_content(notification: Dict[str, Any]) -> tuple:
    """Generate email subject and body based on notification type"""
    notification_type = notification.get("type")
    patient_name = html.escape(notification.get("patient_name", "Patient"))
    doctor_name = html.escape(notification.get("doctor_name", "Doctor"))
    appointment_time = html.escape(notification.get("appointment_time", ""))

    if notification_type == "created":
        subject = "Appointment Confirmation"
        body = f"""
        <h2>Appointment Confirmation</h2>
        <p>Dear {patient_name},</p>
        <p>Your appointment with Dr. {doctor_name} has been scheduled for {appointment_time}.</p>
        <p>Please arrive 15 minutes before your appointment time.</p>
        <p>If you need to reschedule or cancel, please contact us at least 24 hours in advance.</p>
        <p>Thank you for choosing our healthcare services.</p>
        """
    elif notification_type == "updated":
        subject = "Appointment Update"
        body = f"""
        <h2>Appointment Update</h2>
        <p>Dear {patient_name},</p>
        <p>Your appointment with Dr. {doctor_name} has been updated to {appointment_time}.</p>
        <p>Please arrive 15 minutes before your appointment time.</p>
        <p>If you need to reschedule or cancel, please contact us at least 24 hours in advance.</p>
        <p>Thank you for choosing our healthcare services.</p>
        """
    elif notification_type == "cancelled":
        subject = "Appointment Cancellation"
        body = f"""
        <h2>Appointment Cancellation</h2>
        <p>Dear {patient_name},</p>
        <p>Your appointment with Dr. {doctor_name} scheduled for {appointment_time} has been cancelled.</p>
        <p>If you would like to reschedule, please contact our office.</p>
        <p>Thank you for choosing our healthcare services.</p>
        """
    elif notification_type == "status_updated":
        status = str(notification.get("status", "updated"))
        subject = f"Appointment Status: {status.replace('_', ' ').capitalize()}"
        status = html.escape(status.replace("_", " "))
        body = f"""
        <h2>Appointment Status Update</h2>
        <p>Dear {patient_name},</p>
        <p>Your appointment with Dr. {doctor_name} scheduled for {appointment_time} has been marked as {status}.</p>
        <p>If you have any questions, please contact our office.</p>
        <p>Thank you for choosing our healthcare services.</p>
        """
    else:
        subject = "Healthcare Appointment Notification"
        body = f"""
        <h2>Appointment Notification</h2>
        <p>Dear {patient_name},</p>
        <p>This is a notification regarding your appointment with Dr. {doctor_name} scheduled for {appointment_time}.</p>
        <p>If you have any questions, please contact our office.</p>
        <p>Thank you for choosing our healthcare services.</p>
        """

    return subject, body

async def process_notification(notification: Dict[str, Any]) -> None:
    """Process a notification message"""
    try:
        patient_email = notification.get("patient_email")
        if not patient_email:
            logger.error("No patient email in notification")
            return

        subject, body = get_notification_content(notification)
        await send_email(patient_email, subject, body)

    except Exception as e:
        logger.error(f"Error processing notification: {e}")

async def connect_with_retry() -> aio_pika.abc.AbstractRobustConnection:
    while True:
        try:
            return await aio_pika.connect_robust(RABBITMQ_URL)
        except Exception as e:
            logger.warning(f"RabbitMQ unavailable ({e}); retrying in {CONNECT_RETRY_SECONDS}s")
            await asyncio.sleep(CONNECT_RETRY_SECONDS)

async def main() -> None:
    """Main function to consume messages from RabbitMQ"""
    connection = await connect_with_retry()

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue(QUEUE_NAME, durable=True)

        logger.info("Notification service started. Waiting for messages...")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        notification = json.loads(message.body.decode())
                        logger.info(
                            "Received %s notification for appointment %s",
                            notification.get("type"), notification.get("appointment_id")
                        )
                        await process_notification(notification)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(main())
