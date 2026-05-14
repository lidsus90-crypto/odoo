# -*- coding: utf-8 -*-
from odoo import fields, models


class LaundryMethodTypeCatalogue(models.Model):
    _name = 'laundry.method.type.catalogue'
    _inherit = ['mail.thread']
    _description = "Catálogo tipo de método de lavado"
    _rec_name = 'descripcion_tipo_metodo'

    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s-%s' % (record.codigo or '', record.descripcion_tipo_metodo or '')

    codigo = fields.Char('Código')
    descripcion_tipo_metodo = fields.Char('Descripción')
