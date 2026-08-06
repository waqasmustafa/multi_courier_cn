import re
from datetime import datetime

from odoo import _

from .base import BaseCourierService, CourierAPIError


def _sanitize_phone(phone):
    """TCS rejects phone numbers with spaces/dashes/+92 - normalise to local 03xxxxxxxxx."""
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('0092'):
        digits = '0' + digits[4:]
    elif digits.startswith('92') and len(digits) == 12:
        digits = '0' + digits[2:]
    return digits


class TcsService(BaseCourierService):
    """
    TCS (ociconnect.tcscourier.com).
    Book:   POST /ecom/api/booking/create
    Cancel: POST /ecom/api/booking/cancel
    Auth: header Authorization: Bearer <JWT> AND body field accesstoken (both required).

    Payload structure below is copied from a confirmed-working production integration
    (the merchant's previous Laravel CRM), not guessed - see OrPrController.php.
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

    def _shipper_info(self):
        company = self.carrier.env.company
        return {
            'tcsaccount': self.carrier.tcs_account_number,
            'shippername': company.name or '',
            'address1': company.street or '',
            'countrycode': 'PK',
            'countryname': 'Pakistan',
            'citycode': self.carrier.tcs_shipper_city_code or '',
            'cityname': company.city or '',
            'mobile': _sanitize_phone(company.phone or company.mobile),
        }

    def book(self, payload, shipment=None):
        order = payload['order']
        url = '%s/ecom/api/booking/create' % self.carrier.tcs_api_url.rstrip('/')
        body = {
            'accesstoken': self.carrier.tcs_access_token,
            'consignmentno': '',
            'shipperinfo': self._shipper_info(),
            'consigneeinfo': {
                'firstname': payload['customer_name'] or 'Customer',
                'address1': payload['address'],
                'countrycode': 'PK',
                'countryname': 'Pakistan',
                'citycode': '',
                'cityname': payload['city'],
                'email': payload.get('email') or '',
                'mobile': _sanitize_phone(payload['phone']),
            },
            'shipmentinfo': {
                'costcentercode': self.carrier.tcs_cost_center,
                'referenceno': payload['reference'],
                'servicecode': self.carrier.tcs_service_code or 'O',
                'shipmentdate': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'shippingtype': '',
                'currency': 'PKR',
                'codamount': str(int(round(payload['cod_amount']))),
                'declaredvalue': None,
                'insuredvalue': None,
                'transactiontype': '',
                'dsflag': '',
                'carrierslug': '',
                'weightinkg': float(payload['weight']) or 1.0,
                'pieces': payload.get('items') or 1,
                'fragile': False,
                'remarks': (payload['products'] or order.name)[:499],
            },
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='book', headers=self._headers(), json_body=body)
        message = data.get('message') if isinstance(data, dict) else None
        if message != 'SUCCESS':
            if isinstance(data, dict) and data.get('errorList'):
                message = data['errorList'][0].get('errormessage', message)
            raise CourierAPIError(_('TCS booking failed: %s') % (message or data))
        tracking_number = self._extract(data, ['consignmentNo', 'consignmentnumber'])
        if not tracking_number:
            raise CourierAPIError(
                _('TCS reported success but did not return a tracking number: %s') % data)
        slip_url = self._extract(data, ['slipurl', 'slipUrl', 'labelUrl', 'invoiceUrl', 'printUrl'])
        return {'tracking_number': tracking_number, 'slip_url': slip_url, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/ecom/api/booking/cancel' % self.carrier.tcs_api_url.rstrip('/')
        body = {'accesstoken': self.carrier.tcs_access_token, 'consignmentnumber': tracking_number}
        resp, data = self._request(
            'POST', url, shipment=shipment, action='cancel', headers=self._headers(), json_body=body)
        if not isinstance(data, dict) or data.get('message') != 'SUCCESS':
            message = data.get('message') if isinstance(data, dict) else data
            raise CourierAPIError(_('TCS cancel failed: %s') % message)
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
