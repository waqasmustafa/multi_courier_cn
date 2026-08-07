import json
import subprocess
from urllib.parse import urlencode

from odoo import _

from .base import BaseCourierService, CourierAPIError, redact_text

STATUS_MARKER = '__HTTP_STATUS__:'


class _FakeResponse:
    """Minimal stand-in for a requests.Response, just enough for status checks."""

    def __init__(self, status_code):
        self.status_code = status_code
        self.ok = status_code is not None and 200 <= status_code < 300


class ZoomService(BaseCourierService):
    """
    ZoomCOD (portal.zoomcod.com).
    Book:   POST /API/CreateOrder.php  (JSON body incl. auth_key)
    Cancel: GET  /API/CancelOrder.php?auth_key=...&tracking_no=...

    Field names below are confirmed from two independent sources: Zoom's official API
    guide (Zoom_COD_API_Documentation.pdf) and this merchant's own working production
    code (Edentalmart-Courier-Code-Implementation.pdf). The production code never
    sends "profile_id" - it's optional (falls back to the account's default profile) -
    so we only include it if explicitly configured.

    IMPORTANT: Zoom's server returns a 403 (serving its own login page) for requests
    made with Python's requests/urllib3 - even with a spoofed User-Agent - while curl
    from the exact same server/IP succeeds reliably every time (confirmed by repeated
    live testing). This looks like a TLS-fingerprint-based check on their end that
    only allows through clients that look like curl. Calls are therefore made by
    shelling out to curl instead of the shared requests-based _request().
    """

    def _curl_request(self, method, url, shipment=None, action='book', json_body=None, params=None):
        full_url = url
        if params:
            full_url = '%s?%s' % (url, urlencode(params))
        cmd = ['curl', '-s', '-S', '-X', method, full_url,
               '-w', '\n%s%%{http_code}' % STATUS_MARKER, '--max-time', '20']
        if json_body is not None:
            cmd += ['-H', 'Content-Type: application/json', '-H', 'Accept: application/json',
                    '-d', json.dumps(json_body)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        except Exception as e:  # noqa: BLE001
            self._log(shipment, action, full_url, request_data=redact_text(json_body or params),
                       response_data=str(e), status_code=None, success=False)
            raise CourierAPIError(_('Network error contacting Zoom: %s') % e)

        output = result.stdout or ''
        status_code = None
        body_text = output
        if STATUS_MARKER in output:
            body_text, _sep, status_part = output.rpartition(STATUS_MARKER)
            try:
                status_code = int(status_part.strip())
            except ValueError:
                status_code = None
        body_text = body_text.rstrip('\n')
        try:
            data = json.loads(body_text) if body_text else None
        except ValueError:
            data = body_text

        resp = _FakeResponse(status_code)
        self._log(shipment, action, full_url, request_data=redact_text(json_body or params),
                   response_data=data, status_code=status_code, success=resp.ok)
        if status_code is None:
            raise CourierAPIError(_('Zoom did not return a response (curl error): %s') % result.stderr)
        return resp, data

    def book(self, payload, shipment=None):
        order = payload['order']
        carrier = self.carrier
        url = '%s/API/CreateOrder.php' % carrier.zoom_api_url.rstrip('/')
        body = {
            'auth_key': carrier.zoom_auth_key,
            'client_code': carrier.zoom_client_code,
            'product': carrier.zoom_product or 'Overnight',
            'service_type': carrier.zoom_service_type or 'Regular',
            'origin': (carrier.env.company.city or '').upper(),
            'destination': payload['city'] or '',
            'receiver_name': payload['customer_name'],
            'receiver_phone': payload['phone'],
            'receiver_email': payload.get('email') or '',
            'receiver_address': payload['address'],
            'weight': str(payload['weight']),
            'pieces': payload.get('items') or 1,
            'collection_amount': str(int(round(payload['cod_amount']))),
            'product_description': payload['products'] or order.name,
            'special_instruction': '',
            'order_id': payload['reference'],
        }
        if carrier.zoom_profile_id:
            body['profile_id'] = carrier.zoom_profile_id
        resp, data = self._curl_request('POST', url, shipment=shipment, action='book', json_body=body)
        tracking_number = data.get('tracking_no') if isinstance(data, dict) else None
        if not tracking_number:
            message = data.get('message') if isinstance(data, dict) else data
            raise CourierAPIError(_('Zoom booking failed: %s') % (message or data))
        slip_url = data.get('invoice_link') if isinstance(data, dict) else None
        return {'tracking_number': tracking_number, 'slip_url': slip_url, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/API/CancelOrder.php' % self.carrier.zoom_api_url.rstrip('/')
        params = {'auth_key': self.carrier.zoom_auth_key, 'tracking_no': tracking_number}
        resp, data = self._curl_request('GET', url, shipment=shipment, action='cancel', params=params)
        if not isinstance(data, dict) or data.get('response') != 1:
            message = data.get('message') if isinstance(data, dict) else data
            raise CourierAPIError(_('Zoom cancel failed: %s') % message)
        return {'raw_response': data}

    def test_connection(self):
        if not self.carrier.zoom_auth_key:
            return False, _('Zoom auth key is not configured.')
        url = '%s/API/CancelOrder.php' % self.carrier.zoom_api_url.rstrip('/')
        params = {'auth_key': self.carrier.zoom_auth_key, 'tracking_no': 'TEST-CONNECTION'}
        try:
            resp, data = self._curl_request('GET', url, action='test', params=params)
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid Zoom auth key.')
        return True, _('Zoom API reachable, credentials accepted. Response: %s') % str(data)[:200]
