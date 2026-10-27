import os
import sys
import django
import pika
import json
import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer



sys.path.append('/app')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

channel_layer = get_channel_layer()

credentials = pika.PlainCredentials("admin", "admin")

while True:
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='rabbitmq',
                port=5672,
                credentials=credentials
            )
        )

        print("Connected to RabbitMQ")
        break

    except pika.exceptions.AMQPConnectionError:
        print("RabbitMQ not ready, retrying in 5 sec...")
        time.sleep(5)

channel = connection.channel()



channel.exchange_declare(
    exchange='vdo_notifications',
    exchange_type='topic'
)

channel.queue_declare(
    queue='vdo_notification_queue',
    exclusive=True
)


channel.queue_bind(
    exchange='vdo_notifications',
    queue="vdo_notification_queue",
    routing_key='notification.video.*' #notification.video.like , receive all the message about video 
)

def on_message(ch, method, properties, body):

    response = json.loads(body)
    send_to = f"user_{response['data']['send_to']}"
    data = response['data']

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        send_to,
        {
            'type': 'notify_message',
            'data': data
        }
    )

    print(f'Notification sent to {send_to}')

channel.basic_consume(
    queue='vdo_notification_queue',
    on_message_callback=on_message,
    auto_ack=True
)

print("Waiting for messages...")

channel.start_consuming()