# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError

# ── Herencia account.move ─────────────────────────────────────────────────────

class AccountMove(models.Model):
    _inherit = 'account.move'

    laundry_id = fields.Many2one(
        'laundry.management', 'Nº Orden Servicio', readonly=True)
    laundry_grouped = fields.Boolean('Facturas agrupadas')

    def unlink(self):
        for inv in self:
            if inv.state not in ('draft', 'cancel'):
                raise UserError(
                    _('No puede borrar una factura que no esté en '
                      'borrador o cancelada.'))
            if inv.laundry_id or inv.laundry_grouped:
                raise UserError(
                    _('La factura no puede borrarse: la Orden de '
                      'Servicio ya fue procesada.'))
        return super().unlink()
