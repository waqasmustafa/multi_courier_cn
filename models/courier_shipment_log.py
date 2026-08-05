from odoo import fields, models


class CourierShipmentLog(models.Model):
    _name = 'courier.shipment.log'
    _description = 'Courier API Log'
    _order = 'create_date desc'

    shipment_id = fields.Many2one('courier.shipment', required=True, ondelete='cascade', index=True)
    action = fields.Selection([
        ('book', 'Book'),
        ('cancel', 'Cancel'),
        ('test', 'Test Connection'),
    ], required=True)
    endpoint = fields.Char()
    request = fields.Text()
    response = fields.Text()
    status_code = fields.Char()
    success = fields.Boolean()
