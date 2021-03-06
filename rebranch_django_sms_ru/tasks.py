# -*- coding:utf-8 -*-
from django.conf import settings
from decimal import Decimal
import datetime

from rebranch_sms_ru.api import SMSRuAPI
from .celery import app as celery_app
from rebranch_django_sms_ru.models import Message


@celery_app.task(ignore_results=True, name=u'rebranch_sms_ru.tasks.send_message_momentary')
def send_message_momentary(message_id):
    send_message(message_id)


@celery_app.task(ignore_results=True, name=u'rebranch_sms_ru.tasks.send_messages_periodic')
def send_messages_periodic():
    messages = Message.objects.filter(send_in_periodic=True)
    for message in messages:
        send_message(message.id)


def send_message(message_id):
    message = Message.objects.get(id=message_id)
    client = SMSRuAPI(api_id=settings.SMS_RU_ID)
    api_response = client.send(message.recipient, message.content)
    if getattr(settings, u'SMS_RU_STORE_SMS_COST', False):
        cost_api_response = client.get_cost(message.recipient, message.content)
        if cost_api_response[u'cost'] is not None:
            message.cost = Decimal(cost_api_response[u'cost'])
    message.sent = datetime.datetime.now()
    message.api_id = api_response[u'sms_id']
    message.status = api_response[u'status']
    message.commit_attempt()
    if int(message.status) in [100, 101, 102, 103]:
        message.send_in_periodic = False
    else:
        max_attempts_limit = getattr(settings, u'SMS_RU_MAX_ATTEMPTS_LIMIT', 5)
        if message.number_of_attempts >= max_attempts_limit:
            message.send_in_periodic = False
    message.save()