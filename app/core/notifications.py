import asyncio
import json
import logging
from typing import Optional

import aio_pika
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.crud_appointment import appointment

logger = logging.getLogger(__name__)

QUEUE_NAME = "notifications"
PUBLISH_TIMEOUT_SECONDS = 10


async def send_to_queue(message: dict) -> None:
    """Send a message to the RabbitMQ notifications queue"""
    connection = await aio_pika.connect(settings.RABBITMQ_URL, timeout=PUBLISH_TIMEOUT_SECONDS)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue.name,
        )


def build_appointment_message(
    db: Session,
    appointment_id: int,
    notification_type: str,
    status: Optional[str] = None,
) -> Optional[dict]:
    """
    Build a notification payload while the request's DB session is still open.
    Call it before deleting an appointment so the details are still available.
    """
    details = appointment.get_with_details(db, id=appointment_id)
    if not details:
        logger.error("Appointment %s not found for notification", appointment_id)
        return None

    message = {
        "type": notification_type,
        "appointment_id": appointment_id,
        "patient_email": details["patient_email"],
        "patient_name": details["patient_name"],
        "doctor_name": details["doctor_name"],
        "appointment_time": details["start_time"].isoformat(),
    }
    if status:
        message["status"] = status
    return message


def publish_notification(message: Optional[dict]) -> None:
    """Publish a notification; meant to run as a FastAPI background task."""
    if not message or not settings.NOTIFICATIONS_ENABLED:
        return
    try:
        asyncio.run(asyncio.wait_for(send_to_queue(message), PUBLISH_TIMEOUT_SECONDS))
        logger.info("Queued %s notification for appointment %s", message["type"], message["appointment_id"])
    except Exception as e:
        logger.error("Failed to send notification to queue: %s", e)
