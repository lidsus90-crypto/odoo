# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    isservicetype = fields.Boolean(
        'Es actividad de Lavandería', default=False)