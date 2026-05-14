# -*- coding: utf-8 -*-
{
    'name': 'Laundry - Setup',
    'version': '18.0.1.0.0',
    "author": "LeadSolutions Cia. Ltda.",
    "website": "https://lidsus.com/",
    "support": "info@leadsolutions.ec",
    "license": "LGPL-3",
    'category': 'Services/Laundry',
    'summary': 'Módulo instalador global del sistema de lavandería ecuatoriana',
    'depends': [
        'laundry_configuration',
        'laundry_management',
    ],
    'data': [
        'data/laundry_setup_data.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'images': [
        'static/description/service_order.png',
        'static/description/laundry_ec.png',
        'static/description/laundry_ec_1.png',
        'static/description/delivery_guide.png',
        'static/description/dispatch_guide.png',
    ],
    'price': 0,
    'currency': 'USD',
    'installable': True,
    'auto_install': False,
    'application': True,
}