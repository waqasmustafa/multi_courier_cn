from odoo import _

from .base import BaseCourierService, CourierAPIError


class ZoomService(BaseCourierService):
    """
    ZoomCOD (portal.zoomcod.com).
    Book:   POST /API/CreateOrder.php  (JSON body incl. auth_key)
    Cancel: GET  /API/CancelOrder.php?auth_key=...&tracking_no=...
    Success keyed off tracking_no in the response; slip returned as invoice_link.
    """

    def book(self, payload, shipment=None):
        order = payload['order']
        url = '%s/API/CreateOrder.php' % self.carrier.zoom_api_url.rstrip('/')
        body = {
            'auth_key': self.carrier.zoom_auth_key,
            'consignee_name': payload['customer_name'],
            'consignee_phone': payload['phone'],
            'consignee_address': payload['address'],
            'consignee_city': payload['city'],
            'cod_amount': payload['cod_amount'],
            'order_id': payload['reference'],
            'product_details': payload['products'] or order.name,
            'weight': payload['weight'],
        }
        resp, data = self._request('POST', url, shipment=shipment, action='book', json_body=body)
        tracking_number = data.get('tracking_no') if isinstance(data, dict) else None
        if not tracking_number:
            raise CourierAPIError(_('Zoom booking failed, no tracking_no in response: %s') % data)
        slip_url = data.get('invoice_link') if isinstance(data, dict) else None
        return {'tracking_number': tracking_number, 'slip_url': slip_url, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/API/CancelOrder.php' % self.carrier.zoom_api_url.rstrip('/')
        params = {'auth_key': self.carrier.zoom_auth_key, 'tracking_no': tracking_number}
        resp, data = self._request('GET', url, shipment=shipment, action='cancel', params=params)
        if not resp.ok:
            raise CourierAPIError(_('Zoom cancel failed: %s') % data)
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
