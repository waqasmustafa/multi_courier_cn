import json

from odoo import _

from .base import BaseCourierService, CourierAPIError

# Numeric terminal IDs confirmed from the merchant's production code. Only these
# 6 are known - any other terminal name below has no confirmed numeric ID yet.
TERMINAL_IDS = {
    'LAHORE': '18',
    'KARACHI': '16',
    'FAISALABAD': '10',
    'MULTAN': '23',
    'PESHAWAR': '27',
    'RAWALPINDI': '29',
}

# Which main terminal each city/location routes through, from the merchant-provided
# terminal map spreadsheet. Terminal *names* here do not all have a confirmed numeric
# ID yet (see TERMINAL_IDS) - cities under an unconfirmed terminal will still raise a
# clear "book manually" error rather than guess a wrong ID.
TERMINAL_GROUPS = {
    'SWAT': ['MARDAN', 'NOWSHERA', 'PESHAWAR', 'BATKHELA', 'SWAT'],
    'ABBOTTABAD': ['ABBOTTABAD', 'MANSEHRA', 'HARIPUR'],
    'RAWALPINDI': ['JHELUM', 'RAWALPINDI', 'TAXILA', 'WAH CANTT', 'KAMRA CANTT',
                   'HASSANABDAAL', 'HATTAR', 'MURREE', 'CHAKWAL', 'ATTOCK'],
    'AZAD JAMMU KASHMIR': ['MUZAFFARABAD', 'MIRPUR', 'BAGH', 'KOTLI', 'RAWLA KOT'],
    'SIALKOT': ['SIALKOT', 'DASKA', 'SAMBRIAL'],
    'GUJRAT': ['GUJRAT', 'LALAMUSA', 'JALAL PUR JATTA', 'KUNJAN', 'KOTLA ARAB ALI KHAN'],
    'GUJRANWALA': ['GUJRANWALA', 'KAMOKI', 'MOR AIMANABAD', 'GHAKHAR',
                   'MUGHAL CHAK KALAN', 'UGGO CHAK', 'QILA DIDAR SING'],
    'LAHORE': ['LAHORE', 'RAIWIND', 'SHAIKHUPURA'],
    'DERA ISMAIL KHAN': ['BHAKKAR', 'DERA ISMAIL KHAN'],
    'FAISALABAD': ['MIANWALI', 'FAISALABAD', 'JARANWALA', 'SHAHKOT', 'JHUMDRA'],
    'MIANWALI': ['JHANG', 'ESA KHEL', 'KALABAGH', 'ISKANDRABAD', 'KUNDIAN',
                 'WAN BHACHRAN', 'MUSAKHEL', 'CHASHMA'],
    'JHANG': ['TOBA TEK SINGH', 'SHORKOT', 'GOJRA'],
    'SARGODHA': ['BHALWAL', 'SARGODHA'],
    'BAHAWALPUR': ['BAHAWALPUR'],
    'KHANEWAL': ['KHANEWAL', 'KABIRWALA'],
    'CHOWK BAHADURPUR': ['RAHIM YAR KHAN', 'SADIQABAD', 'KHANPUR'],
    'DERA GHAZI KHAN': ['DERA GHAZI KHAN', 'KOTCHUTA', 'MANA AHMDANI',
                        'CHOTI ZAHREEN', 'JAMPUR', 'SHADANLUND'],
    'MULTAN': ['MULTAN', 'BANN BOSAN', 'MIANCHANU', 'MUZAFARGARH'],
    'SAHIWAL': ['OKARA', 'SAHIWAL', 'CHICHAWATNI', 'PEERMAHAL'],
    'KARACHI': ['KAMALIA', 'KARACHI', 'HYDERABAD'],
    'HYDERABAD': ['JAMSHORO', 'PETARO', 'KOTRI', 'MIRPURKHAS'],
    'SAKRAND': ['SAKRAND', 'NAWABSHAH', 'SUKKUR', 'KHAIRPUR', 'LARKANA'],
    'SUKKAR': ['GHOTKI', 'SHIKARPUR', 'PANOAQIL', 'JACCOBAAD'],
    'MORO': ['MORO', 'DADU', 'NOWSHEROFEROZ'],
}

# Flatten to city -> terminal group name (first occurrence wins where a city is
# listed under more than one group in the source spreadsheet).
CITY_TO_TERMINAL = {}
for _terminal_name, _cities in TERMINAL_GROUPS.items():
    for _city in _cities:
        CITY_TO_TERMINAL.setdefault(_city, _terminal_name)


class DaewooService(BaseCourierService):
    """
    Daewoo (codapi.daewoo.net.pk).
    Book:   POST /api/booking/quickBook   (auth in query string, JSON body)
    Cancel: POST /api/booking/quickCancel (auth + trackingNo in query string, empty body)
    Success: TrackNo present, Success == true, Error == false/empty.
    """

    def _auth_params(self):
        return {
            'apiKey': self.carrier.daewoo_api_key,
            'apiUser': self.carrier.daewoo_api_user,
            'apiPassword': self.carrier.daewoo_api_password,
        }

    def fetch_terminal_list(self):
        """Calls Daewoo's official getLocations API and returns {CITY_NAME: 'terminal_id'}."""
        url = '%s/api/cargo/getLocations' % self.carrier.daewoo_api_url.rstrip('/')
        resp, data = self._request('GET', url, action='sync_cities', params=self._auth_params())
        success = isinstance(data, dict) and str(data.get('Success')).lower() == 'true'
        if not success:
            message = data.get('Response') if isinstance(data, dict) else data
            raise CourierAPIError(_('Fetching Daewoo terminal list failed: %s') % (message or data))
        terminal_map = {}
        for row in (data.get('Data') or []):
            name = (row.get('terminal_name') or '').strip().upper()
            terminal_id = row.get('terminal_id')
            if name and terminal_id is not None:
                terminal_map[name] = str(terminal_id)
        return terminal_map

    def sync_terminal_list(self):
        """Fetches the live terminal list from Daewoo and caches it on the carrier record."""
        terminal_map = self.fetch_terminal_list()
        self.carrier.daewoo_terminal_cache = json.dumps(terminal_map)
        return terminal_map

    def _cached_terminal_map(self):
        raw = self.carrier.daewoo_terminal_cache
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def _terminal_id(self, city):
        city_key = (city or '').strip().upper()

        # 1) Live list fetched from Daewoo's own getLocations API (authoritative, complete).
        #    Fetched on first use and cached on the carrier record.
        terminal_map = self._cached_terminal_map()
        if terminal_map is None:
            try:
                terminal_map = self.sync_terminal_list()
            except CourierAPIError:
                terminal_map = {}
        if city_key in terminal_map:
            return terminal_map[city_key]

        # 2) Fallback: hardcoded confirmed IDs, in case the live fetch is unavailable.
        terminal_id = TERMINAL_IDS.get(city_key)
        if terminal_id:
            return terminal_id
        terminal_name = CITY_TO_TERMINAL.get(city_key)
        if terminal_name:
            if terminal_name in terminal_map:
                return terminal_map[terminal_name]
            terminal_id = TERMINAL_IDS.get(terminal_name)
            if terminal_id:
                return terminal_id
            raise CourierAPIError(
                _('"%s" routes via Daewoo terminal "%s", but that terminal\'s numeric ID is not '
                  'confirmed yet. Please book this one manually.') % (city, terminal_name))
        raise CourierAPIError(
            _('No Daewoo terminal is configured for city "%s". Please book this one manually, '
              'or use "Sync Terminal List" to refresh the list from Daewoo.') % city)

    def book(self, payload, shipment=None):
        url = '%s/api/booking/quickBook' % self.carrier.daewoo_api_url.rstrip('/')
        destination_terminal_id = self._terminal_id(payload['city'])
        body = {
            'order_no': str(payload['reference']),
            'source_terminal_id': self.carrier.daewoo_source_terminal_id or '18',
            'destination_terminal_id': destination_terminal_id,
            'receiver_name': payload['customer_name'],
            'receiver_address': payload['address'],
            'receiver_mobile': payload['phone'],
            'receiver_city': payload['city'],
            'receiver_email': payload.get('email') or '',
            'remarks': '',
            'qty': str(payload.get('items') or 1),
            'weight': str(payload['weight']),
            'cod_amount': str(payload['cod_amount']),
            'barcode': '0',
            'receiver_cnic': '',
            'source_location_point': '0.0',
            'destination_location_point': '0.0',
            'source_location_address': '',
            'destination_location_address': payload['address'],
            'item_description': payload['products'] or payload['order'].name,
        }
        resp, data = self._request(
            'POST', url, shipment=shipment, action='book', params=self._auth_params(), json_body=body)
        tracking_number = data.get('TrackNo') if isinstance(data, dict) else None
        success = isinstance(data, dict) and str(data.get('Success')).lower() == 'true'
        has_error = isinstance(data, dict) and str(data.get('Error')).lower() not in ('false', '', 'none')
        if not tracking_number or not success or has_error:
            message = data.get('Response') if isinstance(data, dict) else data
            raise CourierAPIError(_('Daewoo booking failed: %s') % (message or data))
        return {'tracking_number': tracking_number, 'slip_url': None, 'raw_response': data}

    def cancel(self, tracking_number, shipment=None):
        url = '%s/api/booking/quickCancel' % self.carrier.daewoo_api_url.rstrip('/')
        params = dict(self._auth_params(), trackingNo=tracking_number)
        resp, data = self._request('POST', url, shipment=shipment, action='cancel', params=params, json_body=None)
        success = isinstance(data, dict) and str(data.get('Success')).lower() == 'true'
        has_error = isinstance(data, dict) and str(data.get('Error')).lower() not in ('false', '', 'none')
        if not success or has_error:
            message = data.get('Response') if isinstance(data, dict) else data
            raise CourierAPIError(_('Daewoo cancel failed: %s') % (message or data))
        return {'raw_response': data}

    def test_connection(self):
        if not (self.carrier.daewoo_api_key and self.carrier.daewoo_api_user and self.carrier.daewoo_api_password):
            return False, _('Daewoo API key/user/password are not fully configured.')
        url = '%s/api/booking/quickCancel' % self.carrier.daewoo_api_url.rstrip('/')
        params = dict(self._auth_params(), trackingNo='TEST-CONNECTION')
        try:
            resp, data = self._request('POST', url, action='test', params=params, json_body=None)
        except CourierAPIError as e:
            return False, str(e)
        if resp.status_code in (401, 403):
            return False, _('Invalid Daewoo credentials.')
        return True, _('Daewoo API reachable, credentials accepted. Response: %s') % str(data)[:200]
