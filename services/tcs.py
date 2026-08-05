from odoo import _

from .base import BaseCourierService, CourierAPIError


class TcsService(BaseCourierService):
    """
    TCS (ociconnect.tcscourier.com).
    Book:   POST /ecom/api/booking/create
    Cancel: POST /ecom/api/booking/cancel
    Auth: header Authorization: Bearer <JWT> AND body field accesstoken (both required).

    NOTE: TCS's exact booking response field names were not confirmed against a live
    sandbox at build time - only the auth mechanism and endpoints were provided.
    _extract() tries several common key names and always logs the raw response
    (see courier.shipment > API Logs) so the mapping can be corrected quickly if the
    real field name differs.
    """

    def _headers(self):
        return {
            'Authorization': 'Bearer %s' % self.carrier.tcs_bearer_token,
            'Content-Type': 'application/json',
        }

    def _extract(self, data, keys):
        if isinstance(data, dict):
            for key in keys:
                if data.get(key):
                    return data.get(key)
            nested = data.get('data')
            if isinstance(nested, dict):
                return self._extract(nested, keys)
        return None

    def book(self, payload, shipment=None):
        order = payload['order']
        url = '%s/ecom/api/booking/create' % self.carrier.tcs_api_url.rstrip('/')
        # TCS expects three nested objects rather than flat fields - confirmed from a
        # live "field is required" error response. Sub-field names inside each object
        # are a best-guess following TCS's observed lowercase-no-camelCase convention
        # (e.g. consignmentnumber, accesstoken) and may need one more round of
        # correction from the next live error response.
        body = {
            'accesstoken': self.carrier.tcs_access_token,
            'shipperinfo': {
                'accountnumber': self.carrier.tcs_account_number,
                'costcentercode': self.carrier.tcs_cost_center,
                'clientid': self.carrier.tcs_client_id,
            },
            'consigneeinfo': {
                'consigneename': payload['customer_name'],
                'consigneephone': payload['phone'],
                'consigneeaddress': payload['address'],
                'consigneecity': payload['city'],
            },
            'shipmentinfo': {
                'pieces': 1,
                'weight': payload['weight'],
                'codamount': payload['cod_amount'],
                'productdetail': payload['products'] or order.name,
                'reference': payload['reference'],
            },
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='book', headers=self._headers(), json_body=body)
        if not resp.ok:
            raise CourierAPIError(_('TCS booking failed: %s') % data)
        tracking_number = self._extract(
            data, ['consignmentnumber', 'trackingNumber', 'cnNumber', 'consignmentNumber', 'cn_no'])
        if not tracking_number:
            raise CourierAPIError(
                _('TCS did not return a recognisable tracking number. Check the API log '
                  'for the raw response and adjust services/tcs.py field mapping: %s') % data)
        slip_url = self._extract(data, ['slipurl', 'slipUrl', 'labelUrl', 'invoiceUrl', 'printUrl', 'consignmentcopy'])
        return {'tracking_number': tracking_number, 'slip_url': slip_url, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/ecom/api/booking/cancel' % self.carrier.tcs_api_url.rstrip('/')
        body = {'accesstoken': self.carrier.tcs_access_token, 'consignmentnumber': tracking_number}
        resp, data = self._request(
            'POST', url, shipment=shipment, action='cancel', headers=self._headers(), json_body=body)
        if not resp.ok:
            raise CourierAPIError(_('TCS cancel failed: %s') % data)
        return {'raw_response': data}

    def test_connection(self):
        if not self.carrier.tcs_bearer_token or not self.carrier.tcs_access_token:
            return False, _('TCS bearer token / access token is not configured.')
        url = '%s/ecom/api/booking/cancel' % self.carrier.tcs_api_url.rstrip('/')
        body = {'accesstoken': self.carrier.tcs_access_token, 'consignmentnumber': 'TEST-CONNECTION'}
        try:
            resp, data = self._request('POST', url, action='test', headers=self._headers(), json_body=body)
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid TCS credentials.')
        return True, _('TCS API reachable, credentials accepted. Response: %s') % str(data)[:200]
