from odoo import _

from .base import BaseCourierService, CourierAPIError


class PostexService(BaseCourierService):
    """
    PostEx (api.postex.pk).
    Book:   POST /services/integration/api/order/v3/create-order  (header: token)
    Cancel: PUT  /services/integration/api/order/v1/cancel-order  (header: Token)
    Success: res.statusCode == 200 ; CN = res.dist.trackingNumber
    """

    def _headers(self, token_key):
        return {
            token_key: self.carrier.postex_token,
            'Content-Type': 'application/json',
        }

    def book(self, payload, shipment=None):
        url = '%s/services/integration/api/order/v3/create-order' % self.carrier.postex_api_url.rstrip('/')
        # Payload matches a confirmed-working production integration (see OrPrController.php).
        body = {
            'cityName': payload['city'],
            'customerName': payload['customer_name'],
            'customerPhone': payload['phone'],
            'deliveryAddress': payload['address'],
            'invoiceDivision': 0,
            'invoicePayment': payload['cod_amount'],
            'items': payload.get('items') or 1,
            'orderRefNumber': payload['reference'],
            'orderType': 'Normal',
            'pickupAddressCode': self.carrier.postex_pickup_address_code or '001',
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='book',
            headers=self._headers('token'), json_body=body)
        if not isinstance(data, dict) or str(data.get('statusCode')) != '200':
            message = data.get('statusMessage') if isinstance(data, dict) else data
            raise CourierAPIError(_('PostEx booking failed: %s') % (message or data))
        dist = data.get('dist') or {}
        tracking_number = dist.get('trackingNumber')
        if not tracking_number:
            raise CourierAPIError(_('PostEx did not return a tracking number: %s') % data)
        return {
            'tracking_number': tracking_number,
            'slip_url': dist.get('invoiceUrl') or dist.get('labelUrl'),
            'raw_response': data,
        }

    def cancel(self, tracking_number, shipment=None):
        url = '%s/services/integration/api/order/v1/cancel-order' % self.carrier.postex_api_url.rstrip('/')
        body = {'trackingNumber': tracking_number}
        resp, data = self._request(
            'PUT', url, shipment=shipment, action='cancel',
            headers=self._headers('Token'), json_body=body)
        if not isinstance(data, dict) or str(data.get('statusCode')) != '200':
            raise CourierAPIError(_('PostEx cancel failed: %s') % data)
        return {'raw_response': data}

    def test_connection(self):
        if not self.carrier.postex_token:
            return False, _('PostEx token is not configured.')
        url = '%s/services/integration/api/order/v1/get-order-status' % self.carrier.postex_api_url.rstrip('/')
        try:
            resp, data = self._request(
                'GET', url, action='test', headers=self._headers('token'),
                params={'trackingNumber': 'TEST-CONNECTION'})
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid PostEx credentials.')
        return True, _('PostEx API reachable, credentials accepted. Response: %s') % str(data)[:200]
