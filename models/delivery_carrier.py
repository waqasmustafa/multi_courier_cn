from odoo import _, fields, models
from odoo.exceptions import UserError

COURIER_TYPES = ('postex', 'tcs', 'zoomcod')


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[
            ('postex', 'PostEx'),
            ('tcs', 'TCS'),
            ('zoomcod', 'ZoomCOD'),
        ],
        ondelete={'postex': 'set default', 'tcs': 'set default', 'zoomcod': 'set default'},
    )

    # PostEx
    postex_token = fields.Char(string='PostEx Token', password=True)
    postex_api_url = fields.Char(string='PostEx API URL', default='https://api.postex.pk')

    # TCS
    tcs_bearer_token = fields.Char(string='TCS Bearer Token', password=True)
    tcs_access_token = fields.Char(string='TCS Access Token', password=True)
    tcs_cost_center = fields.Char(string='TCS Cost Center')
    tcs_client_id = fields.Char(string='TCS Client ID')
    tcs_account_number = fields.Char(string='TCS Account Number', help='This is the "tcsaccount" value TCS gave you (e.g. LGC1251).')
    tcs_service_code = fields.Char(string='TCS Service Code', help='Provided by TCS for your account, required by the booking API (shipmentinfo.servicecode).')
    tcs_api_url = fields.Char(string='TCS API URL', default='https://ociconnect.tcscourier.com')

    # ZoomCOD
    zoom_auth_key = fields.Char(string='Zoom Auth Key', password=True)
    zoom_api_url = fields.Char(string='Zoom API URL', default='https://portal.zoomcod.com')

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
        raise UserError(_('%s is not a supported courier integration.') % (self.delivery_type or ''))

    def action_test_connection(self):
        self.ensure_one()
        if self.delivery_type not in COURIER_TYPES:
            raise UserError(_('Test Connection is only available for PostEx, TCS and ZoomCOD.'))
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
