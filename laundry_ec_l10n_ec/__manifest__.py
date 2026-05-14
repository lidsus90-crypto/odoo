# -*- coding: utf-8 -*-
{
    'name': 'Laundry EC - Localización Ecuador',
    'version': '18.0.1.0.0',
    'category': 'Services/Laundry',
    'author': 'LeadSolutions Cia. Ltda.',
    'website': 'https://lidsus.com/',
    'support': 'info@leadsolutions.ec',
    'license': 'LGPL-3',
    'price': 0,
    'currency': 'USD',
    'summary': 'Integración Laundry EC con la localización ecuatoriana (l10n_ec_edi)',
    'depends': [
        'laundry_management_lidsus',
        'l10n_ec_edi',
    ],
    'data': [],
    'installable': True,
    # Se instala automáticamente cuando laundry_management y l10n_ec_edi
    # están presentes. En instancias fuera de Ecuador no se instala.
    'auto_install': True,
    'application': False,
}