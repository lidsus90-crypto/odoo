# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    laundry = fields.Boolean('Producto/Lavandería', default=False)
    method_id = fields.Many2one(
        'laundry.method.catalogue', string='Método de Lavado')
    tiempo = fields.Char('Tiempo de Entrega', default='2')
    num_prendas_servicio = fields.Integer('Nº Piezas', default=1)