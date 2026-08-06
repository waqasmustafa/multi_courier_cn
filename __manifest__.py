{
    'name': 'Multi Courier CN (PostEx, TCS, ZoomCOD, Daewoo)',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Generate, print and cancel courier consignment notes (CN) from Sale Orders for PostEx, TCS, ZoomCOD and Daewoo.',
    'description': """
Multi Courier CN
=================
Book, print and cancel consignment notes with PostEx, TCS, ZoomCOD and Daewoo
directly from the Sale Order, with full API request/response logging
and a per-order shipment history.
""",
    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': ['sale', 'delivery'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/courier_shipment_views.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
