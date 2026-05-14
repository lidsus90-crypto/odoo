# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LaundryDispatchGuideLines(models.Model):
    _name = 'laundry.dispatch.guide.lines'
    _inherit = ['mail.thread']
    _description = "Detalle Guía de Despacho Lavandería"

    @api.depends('service_order_id')
    def _compute_amount(self):
        for line in self:
            order = line.service_order_id
            line.total = order.amount_total
            line.num_prendas = order.total_prendas
            line.ge_id = order.delivery_guide_ref.codigo_auto or ''
            line.service_claim_id = order.claim_ref
            line.company_id = order.company_id
            if line.service_claim_id:
                line.total = 0.0
                line.num_prendas = order.claim_ref.total_prendas

    d_list_id = fields.Many2one(
        'laundry.dispatch.guide',
        'Guía Despacho',
        required=True,
        ondelete='cascade',
        readonly=True
    )
    service_order_id = fields.Many2one(
        'laundry.management',
        'Nº Orden',
        required=True,
        domain=['|',
                ('state', '=', 'in_process'),
                '&', ('state', '=', 'claim'), ('claim_ref.state', '=', 'in_process')],
    )
    service_claim_id = fields.Many2one(
        'laundry.claim',
        'Reclamo',
        compute='_compute_amount',
        store=True
    )
    num_prendas = fields.Integer(
        'Prendas',
        store=True,
        readonly=True,
        compute='_compute_amount'
    )
    total = fields.Float(
        'Total',
        digits='Account',
        store=True,
        readonly=True,
        compute='_compute_amount'
    )
    company_id = fields.Many2one(
        'res.company',
        'Punto de Atención',
        compute='_compute_amount',
        store=True
    )
    planta_id = fields.Many2one(
        'stock.warehouse',
        'Planta',
        related='d_list_id.planta_id',
        store=True,
        readonly=True
    )
    ge_id = fields.Char(
        'Guía Entrega',
        store=True,
        readonly=True,
        compute='_compute_amount'
    )
    observacion = fields.Char('Observación')
    check = fields.Boolean(
        'Listo', default=True
    )
    partial = fields.Boolean(
        'Parcial',
        default=False
    )

    def unlink(self):
        for line in self:
            if line.d_list_id.state not in ('draft',):
                raise ValidationError(
                    _('No puede borrar el detalle de guías de despacho.'))
        return super().unlink()
