import json
import pika
import os

from cfenv import AppEnv

class Publisher:
    EXCHANGE='robot-shop'
    TYPE='direct'
    ROUTING_KEY = 'orders'

    def __init__(self, logger):
        self._logger = logger

        if 'VCAP_SERVICES' in os.environ:
            self._logger.info('Cloud Foundry detected')

            env = AppEnv()
            amqp_service = env.get_service(binding_name='dispatch_queue')

            self._logger.info('Service binding \'{binding_name}\' found'.format(binding_name='dispatch_queue'))

            self._uri = amqp_service.credentials.get('uri')
        else:
            self._uri = 'ampq://{user}:{pwd}@{host}:{port}/{vhost}'.format(
                host=os.getenv('AMQP_HOST', 'rabbitmq'),
                port=os.getenv('AMQP_PORT', '5672'),
                vhost='/',
                user=os.getenv('AMQP_USER', 'guest'),
                pwd=os.getenv('AMQP_PWD', 'guest'))

        self._params = pika.URLParameters(self._uri)
        self._conn = None
        self._channel = None

    def _connect(self):
        if not self._conn or self._conn.is_closed:
            self._conn = pika.BlockingConnection(self._params)
            self._channel = self._conn.channel()
            self._channel.exchange_declare(exchange=self.EXCHANGE, exchange_type=self.TYPE, durable=True)
            self._logger.info('connected to broker')

    def _publish(self, msg, headers):
        self._channel.basic_publish(exchange=self.EXCHANGE,
                                    routing_key=self.ROUTING_KEY,
                                    properties=pika.BasicProperties(headers=headers),
                                    body=json.dumps(msg).encode())
        self._logger.info('message sent')

    #Publish msg, reconnecting if necessary.
    def publish(self, msg, headers):
        if self._channel is None:
            self._connect()
        try:
            self._publish(msg, headers)
        except pika.exceptions.ConnectionClosed:
            self._logger.info('reconnecting to queue')
            self._connect()
            self._publish(msg, headers)

    def close(self):
        if self._conn and self._conn.is_open:
            self._logger.info('closing queue connection')
            self._conn.close()

