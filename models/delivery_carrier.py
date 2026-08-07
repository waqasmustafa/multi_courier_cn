from odoo import _, fields, models
from odoo.exceptions import UserError

COURIER_TYPES = ('postex', 'tcs', 'zoomcod', 'daewoo', 'leopard', 'manual')


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[
            ('postex', 'PostEx'),
            ('tcs', 'TCS'),
            ('zoomcod', 'ZoomCOD'),
            ('daewoo', 'Daewoo'),
            ('leopard', 'Leopards Courier'),
            ('manual', 'Manual / No API'),
        ],
        ondelete={
            'postex': 'set default', 'tcs': 'set default', 'zoomcod': 'set default',
            'daewoo': 'set default', 'leopard': 'set default', 'manual': 'set default',
        },
    )

    # PostEx
    postex_token = fields.Char(string='PostEx Token', password=True)
    postex_api_url = fields.Char(string='PostEx API URL', default='https://api.postex.pk')
    postex_pickup_address_code = fields.Char(string='PostEx Pickup Address Code', default='001')

    # TCS
    tcs_bearer_token = fields.Char(string='TCS Bearer Token', password=True)
    tcs_access_token = fields.Char(string='TCS Access Token', password=True)
    tcs_cost_center = fields.Char(string='TCS Cost Center')
    tcs_client_id = fields.Char(string='TCS Client ID')
    tcs_account_number = fields.Char(string='TCS Account Number', help='This is the "tcsaccount" value TCS gave you (e.g. LGC1251).')
    tcs_shipper_city_code = fields.Char(string='TCS Shipper City Code', default='LHE', help='TCS city code for your pickup/origin city (e.g. LHE for Lahore).')
    tcs_service_code = fields.Selection([
        ('O', 'Overnight'),
    ], string='TCS Service', default='O',
        help='Required by the booking API (shipmentinfo.servicecode). Only Overnight is used currently.')
    tcs_api_url = fields.Char(string='TCS API URL', default='https://ociconnect.tcscourier.com')

    # ZoomCOD
    zoom_auth_key = fields.Char(string='Zoom Auth Key', password=True)
    zoom_client_code = fields.Char(string='Zoom Client Code', default='2199')
    zoom_profile_id = fields.Char(string='Zoom Profile ID', help='Optional - only needed if you want to pick a specific shipper/pickup profile instead of the account default.')
    zoom_product = fields.Char(string='Zoom Product', default='Overnight')
    zoom_service_type = fields.Char(string='Zoom Service Type', default='Regular')
    zoom_api_url = fields.Char(string='Zoom API URL', default='https://portal.zoomcod.com')

    # Daewoo
    daewoo_api_key = fields.Char(string='Daewoo API Key', password=True)
    daewoo_api_user = fields.Char(string='Daewoo API User')
    daewoo_api_password = fields.Char(string='Daewoo API Password', password=True)
    daewoo_source_terminal_id = fields.Char(string='Daewoo Source Terminal ID', default='18', help='Your pickup terminal (default 18 = Lahore).')
    daewoo_api_url = fields.Char(string='Daewoo API URL', default='https://codapi.daewoo.net.pk')
    daewoo_terminal_cache = fields.Text(string='Daewoo Terminal Cache (JSON)', help='Populated automatically from Daewoo\'s getLocations API. Use "Sync Terminal List" to refresh.')

    # Leopards Courier
    leopard_book_api_key = fields.Char(string='Leopard Book API Key', password=True)
    leopard_book_api_password = fields.Char(string='Leopard Book API Password', password=True)
    leopard_cancel_api_key = fields.Char(string='Leopard Cancel API Key', password=True,
        help='Leopard uses a DIFFERENT key/password pair for cancelling than for booking.')
    leopard_cancel_api_password = fields.Char(string='Leopard Cancel API Password', password=True)
    leopard_shipment_id = fields.Char(string='Leopard Shipment ID', default='705134',
        help='Account-specific value from Leopard. Confirm with Leopard support if bookings fail.')
    leopard_api_url = fields.Char(string='Leopard API URL', default='https://merchantapi.leopardscourier.com')

    def _get_courier_service(self):
        self.ensure_one()
        if self.delivery_type == 'postex':
            from ..services.postex import PostexService
            return PostexService(self)
        if self.delivery_type == 'tcs':
            from ..services.tcs import TcsService
            return TcsService(self)
        if self.delivery_type == 'zoomcod':
            from ..services.zoom import ZoomService
            return ZoomService(self)
        if self.delivery_type == 'daewoo':
            from ..services.daewoo import DaewooService
            return DaewooService(self)
        if self.delivery_type == 'leopard':
            from ..services.leopard import LeopardService
            return LeopardService(self)
        if self.delivery_type == 'manual':
            from ..services.manual import ManualService
            return ManualService(self)
        raise UserError(_('%s is not a supported courier integration.') % (self.delivery_type or ''))

    def action_sync_daewoo_terminals(self):
        self.ensure_one()
        if self.delivery_type != 'daewoo':
            raise UserError(_('This is only available for Daewoo.'))
        service = self._get_courier_service()
        try:
            terminal_map = service.sync_terminal_list()
            success, message = True, _('Fetched %s terminals from Daewoo.') % len(terminal_map)
        except Exception as e:  # noqa: BLE001
            success, message = False, str(e)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Successful') if success else _('Sync Failed'),
                'message': message,
                'type': 'success' if success else 'danger',
                'sticky': not success,
            },
        }

    def action_test_connection(self):
        self.ensure_one()
        if self.delivery_type not in COURIER_TYPES:
            raise UserError(_('Test Connection is only available for the couriers this module supports.'))
        service = self._get_courier_service()
        try:
            success, message = service.test_connection()
        except Exception as e:  # noqa: BLE001 - surface any adapter failure as a notification
            success, message = False, str(e)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Successful') if success else _('Connection Failed'),
                'message': message,
                'type': 'success' if success else 'danger',
                'sticky': not success,
            },
        }
