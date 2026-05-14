# -*- coding: utf-8 -*-
from odoo import fields, models


class LaundryMethodCatalogue(models.Model):
    _name = 'laundry.method.catalogue'
    _description = "Catálogo método de lavado"
    _rec_name = 'descripcion_mtd'

    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s-%s' % (record.codigo_mtd or '', record.descripcion_mtd or '')

    codigo_mtd = fields.Char('Código')
    descripcion_mtd = fields.Char('Descripción')