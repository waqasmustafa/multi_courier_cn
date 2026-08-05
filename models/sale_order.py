from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipment_ids = fields.One2many('courier.shipment', 'sale_order_id', string='Courier Shipments')
    shipment_count = fields.Integer(compute='_compute_shipment_count')
    active_shipment_id = fields.Many2one(
        'courier.shipment', compute='_compute_active_shipment', string='Active Shipment')
    courier_tracking_number = fields.Char(related='active_shipment_id.tracking_number', string='Tracking Number')
    courier_state = fields.Selection(related='active_shipment_id.state', string='Courier Status')
    courier_slip_url = fields.Char(related='active_shipment_id.slip_url', string='Slip URL')

    @api.depends('shipment_ids')
    def _compute_shipment_count(self):
        for order in self:
            order.shipment_count = len(order.shipment_ids)

    @api.depends('shipment_ids.state', 'shipment_ids.create_date')
    def _compute_active_shipment(self):
        for order in self:
            active = order.shipment_ids.filtered(lambda s: s.state in ('booked', 'draft'))
            order.active_shipment_id = active[:1] if active else order.shipment_ids[:1]

    def action_generate_cn(self):
        self.ensure_one()
        if not self.carrier_id:
            raise UserError(_('Please select a Shipping Method (Courier tab) before generating a CN.'))
        if self.active_shipment_id and self.active_shipment_id.state == 'booked':
            raise UserError(_('A CN is already booked for this order. Delete it before generating a new one.'))
        shipment = self.env['courier.shipment'].create({
            'sale_order_id': self.id,
            'carrier_id': self.carrier_id.id,
            'cod_amount': self.amount_total,
        })
        shipment.action_book()
        return True

    def action_delete_cn(self):
        self.ensure_one()
        shipment = self.active_shipment_id
        if not shipment or shipment.state != 'booked':
            raise UserError(_('There is no booked CN to delete for this order.'))
        shipment.action_cancel_shipment()
        return True

    def action_print_cn(self):
        self.ensure_one()
        shipment = self.active_shipment_id
        if not shipment or shipment.state != 'booked':
            raise UserError(_('There is no CN to print for this order.'))
        return shipment.action_print_slip()

    def action_view_shipments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('multi_courier_cn.action_courier_shipment')
        action['domain'] = [('sale_order_id', '=', self.id)]
        action['context'] = {'default_sale_order_id': self.id, 'default_carrier_id': self.carrier_id.id}
        return action
