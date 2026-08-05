import json
import logging
import re

import requests

from odoo import _

_logger = logging.getLogger(__name__)

TIMEOUT = 20
SENSITIVE_KEYS = {'token', 'authorization', 'accesstoken', 'auth_key', 'bearer'}


class CourierAPIError(Exception):
    """Raised whenever a courier API call fails or cannot be reached."""


def _redact(value):
    if isinstance(value, dict):
        return {
            k: ('***REDACTED***' if k.lower() in SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def redact_text(value):
    """Best-effort redaction of credentials before anything is persisted to the API log."""
    if value is None:
        return value
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(_redact(value))
        except (TypeError, ValueError):
            return str(_redact(value))
    text = str(value)
    text = re.sub(r'(auth_key=)[^&\s]+', r'\1***REDACTED***', text)
    text = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_.]+', r'\1***REDACTED***', text)
    return text


class BaseCourierService:

    def __init__(self, carrier):
        self.carrier = carrier
        self.env = carrier.env

    def _log(self, shipment, action, endpoint, request_data=None, response_data=None,
              status_code=None, success=False):
        if not shipment:
            return
        self.env['courier.shipment.log'].sudo().create({
            'shipment_id': shipment.id,
            'action': action,
            'endpoint': endpoint,
            'request': redact_text(request_data),
            'response': redact_text(response_data),
            'status_code': str(status_code) if status_code is not None else False,
            'success': success,
        })

    def _request(self, method, url, shipment=None, action='book', headers=None,
                  json_body=None, params=None):
        try:
            resp = requests.request(
                method, url, headers=headers, json=json_body, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            self._log(shipment, action, url, request_data=json_body or params,
                       response_data=str(e), status_code=None, success=False)
            raise CourierAPIError(_('Network error contacting courier: %s') % e)
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        self._log(shipment, action, url, request_data=json_body or params,
                   response_data=data, status_code=resp.status_code, success=resp.ok)
        return resp, data

    def book(self, payload, shipment=None):
        raise NotImplementedError

    def cancel(self, tracking_number, shipment=None):
        raise NotImplementedError

    def test_connection(self):
        raise NotImplementedError
