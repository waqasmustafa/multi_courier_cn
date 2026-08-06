from .base import BaseCourierService


class ManualService(BaseCourierService):
    """
    Manual / No API couriers (e.g. Self Pickup, a named rider, Bykea) - matches the
    old CRM's fallback: CN = first 3 letters of the courier's name (uppercase) + the
    order's ID. No real network call is made.
    """

    def _generate_cn(self, order):
        prefix = (self.carrier.name or 'CN')[:3].upper()
        return '%s%s' % (prefix, order.id)

    def book(self, payload, shipment=None):
        order = payload['order']
        tracking_number = self._generate_cn(order)
        self._log(shipment, 'book', 'manual', request_data=payload.get('reference'),
                   response_data={'tracking_number': tracking_number}, status_code=200, success=True)
        return {'tracking_number': tracking_number, 'slip_url': None, 'raw_response': {'message': 'Manual CN, no API call made.'}}

    def cancel(self, tracking_number, shipment=None):
        self._log(shipment, 'cancel', 'manual', request_data=tracking_number,
                   response_data={'message': 'cleared'}, status_code=200, success=True)
        return {'raw_response': {'message': 'Manual CN, no API call made.'}}

    def test_connection(self):
        return True, 'No API required for manual couriers - always available.'
