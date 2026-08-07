{
    'name': 'Multi Courier CN - PostEx, TCS, ZoomCOD, Daewoo & Leopards Courier',

    'summary': 'Generate, print and cancel courier consignment notes (CN) from Sale Orders across multiple Pakistani couriers.',

    'description': '''
        Book, print and cancel courier consignment notes (CN) directly from the
        Sale Order - no separate courier portal or manual entry needed.

        Supported Couriers:
        • PostEx
        • TCS
        • ZoomCOD
        • Daewoo
        • Leopards Courier
        • Manual / No API (Self Pickup, riders, Bykea, etc.)

        Features:
        • One "Generate CN" wizard on the Sale Order - pick the courier, mark
          Fragile, add Remarks, then Book
        • Live booking against each courier's real API, with the tracking
          number and slip captured automatically
        • A single, consistent CN slip design (barcode, shipper/consignee,
          COD amount, product detail) printed the same way for every courier
        • Full Courier Shipment history per order - every booking attempt is
          kept for audit, not overwritten
        • Complete API request/response logging per shipment for fast
          troubleshooting when a courier rejects a booking
        • Cancellation handled from the Courier Shipment record, calling the
          courier's own cancel API
        • City/terminal ID mapping for couriers that require it (Daewoo,
          Leopards Courier), with a clear "book manually" error instead of a
          silently wrong destination when a city isn't mapped yet
        • Manual/No-API couriers (Self Pickup, riders, etc.) need zero
          configuration - just add a Delivery Method record

        Configuration:
        • All credentials and settings are configured per Delivery Method
          under Inventory > Configuration > Shipping Methods
        • "Test Connection" button validates credentials before you rely on
          them for a real booking
    ''',

    'author': 'Waqas Mustafa',
    'website': 'https://www.linkedin.com/in/waqas-mustafa-ba5701209/',
    'support': 'mustafawaqas0@gmail.com',

    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Inventory/Delivery',

    'depends': ['sale', 'delivery'],
    'external_dependencies': {'python': ['requests']},

    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/courier_shipment_views.xml',
        'wizard/courier_generate_cn_wizard_views.xml',
        'report/courier_slip_report.xml',
    ],

      'images': [
        'static/description/banner.gif',
        'static/description/icon.png',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
