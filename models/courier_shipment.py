from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CourierShipment(models.Model):
    _name = 'courier.shipment'
    _description = 'Courier Shipment'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(default='New', copy=False, readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade', index=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Courier', required=True)
    delivery_type = fields.Selection(related='carrier_id.delivery_type', store=True, string='Courier Type')
    tracking_number = fields.Char(string='Tracking Number', copy=False)
    slip_url = fields.Char(string='Slip URL', copy=False)
    slip_attachment_id = fields.Many2one('ir.attachment', string='Slip Attachment', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ], default='draft', copy=False, required=True)
    cod_amount = fields.Monetary(string='COD Amount')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    last_response = fields.Text(string='Last Response', copy=False)
    last_sync = fields.Datetime(string='Last Sync', copy=False)
    active = fields.Boolean(default=True)
    log_ids = fields.One2many('courier.shipment.log', 'shipment_id', string='API Logs')
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('courier.shipment') or 'New'
        return super().create(vals_list)

    def _build_booking_payload(self):
        self.ensure_one()
        order = self.sale_order_id
        partner = order.partner_shipping_id or order.partner_id
        product_lines = order.order_line.filtered(lambda l: l.product_id and not l.display_type)
        weight = sum(
            (line.product_id.weight or 0.0) * line.product_uom_qty
            for line in product_lines
            if line.product_id.type != 'service'
        )
        products_desc = ', '.join(product_lines.mapped('product_id.name'))
        # Delivery addresses are often child contacts without their own phone -
        # fall back to the order's main contact, then the top-level company contact.
        phone = (
            partner.phone or partner.mobile
            or order.partner_id.phone or order.partner_id.mobile
            or partner.commercial_partner_id.phone or partner.commercial_partner_id.mobile
            or ''
        )
        return {
            'order': order,
            'customer_name': partner.name or '',
            'phone': phone,
            'address': ', '.join(filter(None, [partner.street, partner.street2])),
            'city': partner.city or '',
            'products': products_desc,
            'weight': weight or 1.0,
            'amount': order.amount_total,
            'cod_amount': self.cod_amount or order.amount_total,
            'reference': order.name,
        }

    def action_book(self):
        self.ensure_one()
        if self.state == 'booked':
            raise UserError(_('This shipment is already booked.'))
        service = self.carrier_id._get_courier_service()
        payload = self._build_booking_payload()
        missing = []
        if not payload['phone']:
            missing.append(_('Phone number'))
        if not payload['address']:
            missing.append(_('Address'))
        if not payload['city']:
            missing.append(_('City'))
        if missing:
            raise UserError(_(
                'Cannot generate CN: the customer is missing %s. '
                'Add it on the customer or delivery address and try again.'
            ) % ', '.join(missing))
        try:
            result = service.book(payload, shipment=self)
        except Exception as e:  # noqa: BLE001 - convert any adapter/network failure into a visible state
            self.write({
                'state': 'failed',
                'last_response': str(e),
                'last_sync': fields.Datetime.now(),
            })
            raise UserError(_('Booking failed: %s') % e)
        vals = {
            'state': 'booked',
            'tracking_number': result.get('tracking_number'),
            'slip_url': result.get('slip_url'),
            'last_response': result.get('raw_response'),
            'last_sync': fields.Datetime.now(),
        }
        self.write(vals)
        if result.get('slip_pdf_base64'):
            attachment = self.env['ir.attachment'].create({
                'name': '%s.pdf' % (self.tracking_number or self.name),
                'type': 'binary',
                'datas': result.get('slip_pdf_base64'),
                'res_model': 'courier.shipment',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            self.slip_attachment_id = attachment.id
        return True

    def action_cancel_shipment(self):
        self.ensure_one()
        if self.state != 'booked':
            raise UserError(_('Only booked shipments can be cancelled.'))
        service = self.carrier_id._get_courier_service()
        try:
            result = service.cancel(self.tracking_number, shipment=self)
        except Exception as e:  # noqa: BLE001
            raise UserError(_('Cancel failed: %s') % e)
        self.write({
            'state': 'cancelled',
            'last_response': result.get('raw_response'),
            'last_sync': fields.Datetime.now(),
        })
        return True

    def action_print_slip(self):
        self.ensure_one()
        if self.slip_attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % self.slip_attachment_id.id,
                'target': 'new',
            }
        if self.slip_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.slip_url,
                'target': 'new',
            }
        raise UserError(_('No slip is available for this shipment.'))
