from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CourierGenerateCnWizard(models.TransientModel):
    _name = 'courier.generate.cn.wizard'
    _description = 'Generate Courier CN'

    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Courier', required=True)
    fragile = fields.Boolean(string='Fragile')
    remarks = fields.Char(string='Remarks')
    shipment_id = fields.Many2one('courier.shipment', readonly=True, copy=False)
    tracking_number = fields.Char(related='shipment_id.tracking_number', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('booked', 'Booked')], default='draft')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        order_id = vals.get('sale_order_id') or self.env.context.get('default_sale_order_id')
        if order_id and 'carrier_id' in fields_list:
            order = self.env['sale.order'].browse(order_id)
            if order.carrier_id:
                vals.setdefault('carrier_id', order.carrier_id.id)
        return vals

    def action_book(self):
        self.ensure_one()
        order = self.sale_order_id
        if order.active_shipment_id and order.active_shipment_id.state == 'booked':
            raise UserError(_('A CN is already booked for this order.'))
        order.carrier_id = self.carrier_id.id
        shipment = self.env['courier.shipment'].create({
            'sale_order_id': order.id,
            'carrier_id': self.carrier_id.id,
            'cod_amount': order.amount_total,
            'fragile': self.fragile,
            'remarks': self.remarks,
        })
        shipment.action_book()
        self.write({'shipment_id': shipment.id, 'state': 'booked'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'courier.generate.cn.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print(self):
        self.ensure_one()
        if not self.shipment_id:
            raise UserError(_('No CN has been generated yet.'))
        return self.shipment_id.action_print_slip()
