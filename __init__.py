from . import models


def post_init_hook(env):
    """Create default PostEx/TCS/ZoomCOD/Daewoo delivery methods, mirroring how core
    delivery modules (e.g. FedEx) ship ready-made carrier records."""
    Carrier = env['delivery.carrier']
    if Carrier.search([('delivery_type', 'in', ['postex', 'tcs', 'zoomcod', 'daewoo'])], limit=1):
        return

    Product = env['product.template']
    vals = {
        'name': 'Courier Delivery Charges',
        'type': 'service',
        'invoice_policy': 'order',
        'list_price': 0.0,
        'sale_ok': False,
        'purchase_ok': False,
    }
    # Some customized instances add extra required fields to product.template
    # (e.g. via third-party barcode/unit modules) - satisfy them if present.
    if 'base_unit_count' in Product._fields:
        vals['base_unit_count'] = 1
    product = Product.create(vals)
    product_variant_id = product.product_variant_id.id

    Carrier.create([
        {'name': 'PostEx', 'delivery_type': 'postex', 'product_id': product_variant_id},
        {'name': 'TCS', 'delivery_type': 'tcs', 'product_id': product_variant_id},
        {'name': 'ZoomCOD', 'delivery_type': 'zoomcod', 'product_id': product_variant_id},
        {'name': 'Daewoo', 'delivery_type': 'daewoo', 'product_id': product_variant_id},
    ])
