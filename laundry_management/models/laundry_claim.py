# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LaundryClaim(models.Model):
    _name = 'laundry.claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Orden Reclamo Lavandería"
    _order = 'clean_start_time desc, id desc'

    def _compute_display_name(self):
        for r in self:
            seq = r.codigo_orden_reclamo or '/'
            r.display_name = '%s - %s' % (seq, r.partner_id.name) if r.partner_id else seq

    @api.depends('service_claim_lines.price_subtotal',
                 'service_claim_lines.price_tax')
    def _compute_amount(self):
        for rec in self:
            rec.amount_untaxed = sum(
                l.price_subtotal for l in rec.service_claim_lines)
            rec.amount_tax = sum(
                l.price_tax for l in rec.service_claim_lines)
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    @api.depends('service_claim_lines')
    def _compute_total_prendas(self):
        for rec in self:
            rec.total_prendas = sum(
                l.product_uom_qty for l in rec.service_claim_lines)

    company_id = fields.Many2one(
        'res.company',
        'Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users',
        'Encargado',
        required=True,
        default=lambda self: self.env.user,
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Cliente',
        tracking=True)
    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Dirección de Entrega',
        tracking=True,
        domain="['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]",
    )
    fiscal_position = fields.Many2one(
        'account.fiscal.position',
        'Posición Fiscal')
    cod_asignado = fields.Char(
        'Secuencial',
        required=True,
        copy=False,
        readonly=True,
        default='/'
    )
    codigo_orden_reclamo = fields.Char(
        'Etiqueta'
    )
    clean_start_time = fields.Datetime(
        'Fecha Recepción',
        default=fields.Datetime.now
    )
    clean_end_time = fields.Datetime(
        'Fecha Entrega'
    )
    invoice_ref_id = fields.Many2one(
        'account.move',
        'Nº Factura',
        ondelete='set null',
        readonly=True
    )
    service_claim_lines = fields.One2many(
        'laundry.claim.line',
        'order_claim_id',
        'Líneas de Reclamo',
        copy=True)
    state = fields.Selection([
        ('received',   'Recibido'),
        ('sent',       'Enviado'),
        ('in_process', 'En proceso'),
        ('in_transit', 'En tránsito'),
        ('ready',      'Listo'),
        ('delivered',  'Entregado'),
    ], 'Estado',
        tracking=True,
        readonly=True,
        default='received'
    )
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Tarifa'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='pricelist_id.currency_id',
        store=True,
        readonly=True
    )
    informacion = fields.Text(
        'Observación'
    )
    porcentaje_iva_aplicado = fields.Selection([
        ('auto', 'Automático'),
        ('iva12', 'IVA 12%'),
        ('iva14', 'IVA 14%'),
    ], '% IVA aplicado',
        default='auto',
        copy=True
    )
    amount_untaxed = fields.Float(
        'Subtotal', digits='Account',
        store=True,
        readonly=True,
        compute='_compute_amount',
        tracking=True
    )
    amount_tax = fields.Float(
        'Impuestos',
        digits='Account',
        store=True,
        readonly=True,
        compute='_compute_amount'
    )
    amount_total = fields.Float(
        'Total',
        digits='Account',
        store=True,
        readonly=True,
        compute='_compute_amount')
    total_prendas = fields.Integer(
        'Total Prendas',
        store=True,
        readonly=True,
        compute='_compute_total_prendas',
        tracking=True
    )
    delivery_guide_ref = fields.Many2one(
        'laundry.delivery.guide',
        'Guía Entrega',
        readonly=True
    )
    dispatch_guide_ref = fields.Many2one(
        'laundry.dispatch.guide',
        'Guía Despacho',
        readonly=True
    )
    lorder_id = fields.Many2one(
        'laundry.management',
        'Orden Servicio',
        required=False,
        readonly=True
    )

    _sql_constraints = [
        ('name_uniq', 'unique(cod_asignado, company_id)',
         'El secuencial del reclamo debe ser único por Compañía.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('cod_asignado', '/') == '/':
                vals['cod_asignado'] = (
                        self.env['ir.sequence'].next_by_code(
                            'laundry.claim') or '/')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('received',):
                raise ValidationError(
                    _('No puede borrar Reclamos en estado diferente '
                      'a "Recibido".'))
        self.desvincular()
        return super().unlink()

    @api.constrains('clean_start_time', 'clean_end_time')
    def _check_dates(self):
        for rec in self:
            if (rec.clean_start_time and rec.clean_end_time and
                    rec.clean_start_time >= rec.clean_end_time):
                raise ValidationError(
                    _('La fecha de inicio debe ser menor que la '
                      'fecha de entrega.'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.fiscal_position = False
            self.partner_shipping_id = False
            return
        addr = self.partner_id.address_get(['delivery'])
        self.partner_shipping_id = addr['delivery']
        pricelist = self.partner_id.property_product_pricelist
        if pricelist:
            self.pricelist_id = pricelist

    def desvincular(self):
        for rec in self:
            if rec.lorder_id:
                rec.lorder_id.desvincular()

    def confirmar(self):
        for rec in self:
            if rec.lorder_id:
                rec.lorder_id.confirmar()
            else:
                if not rec.invoice_ref_id:
                    raise ValidationError(
                        _('El reclamo no puede ser entregado sin '
                          'haber sido facturado.'))
                rec.laundry_claim_entregado()

    def laundry_claim_entransito(self):
        for rec in self:
            if rec.state == 'in_process':
                rec.write({'state': 'in_transit'})

    def laundry_claim_enproceso(self):
        for rec in self:
            if rec.state == 'sent':
                rec.write({'state': 'in_process'})

    def laundry_claim_listo(self):
        for rec in self:
            if rec.state == 'in_transit':
                rec.write({'state': 'ready'})

    def laundry_claim_entregado(self):
        for rec in self:
            if rec.state == 'ready':
                rec.write({'state': 'delivered'})

    def laundry_claim_enviado(self):
        for rec in self:
            if rec.state == 'received':
                rec.write({'state': 'sent'})

    def button_dummy(self):
        return True