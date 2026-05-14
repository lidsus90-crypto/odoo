# -*- coding: utf-8 -*-
from odoo import fields, models


class LaundryClaimCatalogue(models.Model):
    _name = 'laundry.claim.catalogue'
    _description = "Catálogo de motivos de reclamo"
    _rec_name = 'descripcion_reclamo'

    codigo = fields.Char('Código')
    descripcion_reclamo = fields.Char('Descripción')