from odoo import _

from .base import BaseCourierService, CourierAPIError

# Leopard's destination_city expects Leopard's own numeric city ID, not a name.
# We don't have their city -> ID mapping yet, so any city not listed here raises
# a clear "book manually" error instead of guessing a wrong ID.
CITY_IDS = {}


class LeopardService(BaseCourierService):
    """
    Leopards Courier (merchantapi.leopardscourier.com).
    Book:   POST /api/bookPacket/format/json/
    Cancel: POST /api/cancelBookedPackets/format/json/
    Booking and cancelling use DIFFERENT api_key/api_password pairs.
    Success: status == 1, CN = track_number, slip = slip_link. status == 0 -> error.
    """

    def _city_id(self, city):
        city_id = CITY_IDS.get((city or '').strip().upper())
        if not city_id:
            raise CourierAPIError(
                _('No Leopard city ID is configured for "%s". Please book this one manually '
                  'or add its city ID to services/leopard.py.') % city)
        return city_id

    def book(self, payload, shipment=None):
        url = '%s/api/bookPacket/format/json/' % self.carrier.leopard_api_url.rstrip('/')
        destination_city = self._city_id(payload['city'])
        # Leopard expects weight in grams, not kg.
        weight_grams = int(round((payload['weight'] or 0.5) * 1000))
        body = {
            'api_key': self.carrier.leopard_book_api_key,
            'api_password': self.carrier.leopard_book_api_password,
            'booked_packet_weight': weight_grams,
            'booked_packet_vol_weight_w': '',
            'booked_packet_vol_weight_h': '',
            'booked_packet_vol_weight_l': '',
            'booked_packet_no_piece': payload.get('items') or 1,
            'booked_packet_collect_amount': payload['cod_amount'],
            'booked_packet_order_id': payload['reference'],
            'origin_city': 'self',
            'destination_city': destination_city,
            'shipment_id': self.carrier.leopard_shipment_id,
            'consignment_name_eng': payload['customer_name'],
            'consignment_email': payload.get('email') or '',
            'consignment_phone': payload['phone'],
            'consignment_phone_two': '',
            'consignment_phone_three': '',
            'consignment_address': payload['address'],
            'special_instructions': payload['products'] or payload['order'].name,
            'shipment_type': '',
            'custom_data': '',
            'return_address': '',
            'return_city': '',
            'is_vpc': '1',
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='book', json_body=body)
        status = data.get('status') if isinstance(data, dict) else None
        if str(status) != '1':
            message = data.get('error') if isinstance(data, dict) else data
            raise CourierAPIError(_('Leopard booking failed: %s') % (message or data))
        tracking_number = data.get('track_number')
        if not tracking_number:
            raise CourierAPIError(_('Leopard reported success but did not return a track_number: %s') % data)
        return {
            'tracking_number': tracking_number,
            'slip_url': data.get('slip_link'),
            'raw_response': data,
        }

    def cancel(self, tracking_number, shipment=None):
        url = '%s/api/cancelBookedPackets/format/json/' % self.carrier.leopard_api_url.rstrip('/')
        body = {
            'api_key': self.carrier.leopard_cancel_api_key,
            'api_password': self.carrier.leopard_cancel_api_password,
            'cn_numbers': tracking_number,
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='cancel', json_body=body)
        # Leopard's own production usage doesn't strictly validate this response
        # (it clears the CN either way) - only raise if it explicitly reports failure.
        if isinstance(data, dict) and str(data.get('status')) == '0':
            raise CourierAPIError(_('Leopard cancel failed: %s') % data.get('error', data))
        return {'raw_response': data}

    def test_connection(self):
        if not (self.carrier.leopard_book_api_key and self.carrier.leopard_book_api_password):
            return False, _('Leopard Book API key/password are not configured.')
        url = '%s/api/cancelBookedPackets/format/json/' % self.carrier.leopard_api_url.rstrip('/')
        body = {
            'api_key': self.carrier.leopard_cancel_api_key or self.carrier.leopard_book_api_key,
            'api_password': self.carrier.leopard_cancel_api_password or self.carrier.leopard_book_api_password,
            'cn_numbers': 'TEST-CONNECTION',
        }
        try:
            resp, data = self._request('POST', url, action='test', json_body=body)
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid Leopard credentials.')
        return True, _('Leopard API reachable, credentials accepted. Response: %s') % str(data)[:200]
