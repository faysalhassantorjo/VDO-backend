import json
import pika


def publish_video_like_notification(data):

    credentials = pika.PlainCredentials(
        username="admin",
        password="admin"
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='rabbitmq',
            port=5672,
            credentials=credentials
        )
    )

    channel = connection.channel()

    channel.exchange_declare(
        exchange='vdo_notifications',
        exchange_type='topic',
        durable=False
    )

    channel.basic_publish(
        exchange='vdo_notifications',
        routing_key='notification.video.like',
        body=json.dumps(data),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    print('Notification sent')

    connection.close()