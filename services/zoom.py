from odoo import _

from .base import BaseCourierService, CourierAPIError


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
    """

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
            'destination': (payload['city'] or '').upper(),
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
        resp, data = self._request('POST', url, shipment=shipment, action='book', json_body=body)
        tracking_number = data.get('tracking_no') if isinstance(data, dict) else None
        if not tracking_number:
            message = data.get('message') if isinstance(data, dict) else data
            raise CourierAPIError(_('Zoom booking failed: %s') % (message or data))
        slip_url = data.get('invoice_link') if isinstance(data, dict) else None
        return {'tracking_number': tracking_number, 'slip_url': slip_url, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/API/CancelOrder.php' % self.carrier.zoom_api_url.rstrip('/')
        params = {'auth_key': self.carrier.zoom_auth_key, 'tracking_no': tracking_number}
        resp, data = self._request('GET', url, shipment=shipment, action='cancel', params=params)
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
            resp, data = self._request('GET', url, action='test', params=params)
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid Zoom auth key.')
        return True, _('Zoom API reachable, credentials accepted. Response: %s') % str(data)[:200]
