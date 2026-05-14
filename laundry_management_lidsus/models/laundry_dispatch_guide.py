# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LaundryDispatchGuide(models.Model):
    _name = 'laundry.dispatch.guide'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Guía de Despacho Lavandería"
    _order = 'fecha_recepcion desc, id desc'

    def _compute_display_name(self):
        for r in self:
            seq = r.codigo_auto or '/'
            r.display_name = '%s - %s' % (seq, r.partner_id.name) if r.partner_id else seq

    @api.depends('despacho_lines')
    def _compute_prendas_gd(self):
        for rec in self:
            rec.num_prendas_gd = sum(
                l.num_prendas for l in rec.despacho_lines)

    company_id = fields.Many2one(
        'res.company',
        'Destino',
        required=True,
        default=lambda self: self.env.company
    )
    companypl_id = fields.Many2one(
        'res.company',
        'EmprPL'
    )
    planta_id = fields.Many2one(
        'stock.warehouse',
        'Origen',
        required=True
    )
    user_id = fields.Many2one(
        'res.users',
        'Encargado',
        required=True,
        default=lambda self: self.env.user
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Transportista',
        required=True,
    )
    delivery_guide_id = fields.Many2one(
        'laundry.delivery.guide',
        'Guía de Entrega',
        ondelete='set null',
        domain=[('state', 'in', ['recept', 'partial']), ('tiene_os_pendientes', '=', True)],
    )
    codigo_auto = fields.Char(
        'Secuencial',
        required=True,
        copy=False,
        readonly=True,
        default='/'
    )
    despacho_lines = fields.One2many(
        'laundry.dispatch.guide.lines',
        'd_list_id',
        'Detalle Guía Despacho',
        copy=True
    )
    codigo_guia_despacho = fields.Char(
        'Guía',
    )
    fecha_recepcion = fields.Date(
        'Fecha',
        required=True,
        default=fields.Date.today
    )
    fecha_entrega = fields.Date(
        'Fecha Recepción',
        default=lambda self: (
                datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    )
    num_prendas_gd = fields.Integer(
        'Prendas',
        store=True,
        readonly=True,
        compute='_compute_prendas_gd',
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('send', 'Enviado'),
        ('partial', 'Parcialmente Recibido'),
        ('recept', 'Recibido'),
    ], 'Estado',
        tracking=True,
        readonly=True,
        default='draft'
    )

    _sql_constraints = [
        ('name_uniq', 'unique(codigo_auto, company_id)',
         'La guía de despacho debe ser única por Compañía.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        today = datetime.now().strftime('%Y%m%d')
        for vals in vals_list:
            if vals.get('codigo_auto', '/') == '/':
                vals['codigo_auto'] = (
                        self.env['ir.sequence'].next_by_code(
                            'laundry.dispatch.guide') or '/')
            if not vals.get('codigo_guia_despacho'):
                vals['codigo_guia_despacho'] = '%s-%s' % (vals['codigo_auto'], today)
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft',):
                raise ValidationError(
                    _('No puede borrar Guías de Despacho en estado '
                      'diferente a "Borrador".'))
        return super().unlink()

    @api.constrains('fecha_recepcion', 'fecha_entrega')
    def _check_dates(self):
        for rec in self:
            if (rec.fecha_recepcion and rec.fecha_entrega and
                    rec.fecha_recepcion >= rec.fecha_entrega):
                raise ValidationError(
                    _('La fecha de despacho debe ser menor que la '
                      'fecha de recepción.'))

    @api.onchange('delivery_guide_id')
    def _onchange_delivery_guide_id(self):
        self.despacho_lines = [(5, 0, 0)]
        if not self.delivery_guide_id:
            return
        ge = self.delivery_guide_id
        if ge.planta_id:
            self.planta_id = ge.planta_id
        if ge.partner_id:
            self.partner_id = ge.partner_id
        lines = []
        for ge_line in ge.guia_lines:
            order = ge_line.service_order_id
            if not order:
                continue
            claim = order.claim_ref
            if order.state == 'in_process' or (
                    order.state == 'claim' and claim and claim.state == 'in_process'):
                lines.append((0, 0, {'service_order_id': order.id}))
        self.despacho_lines = lines

    def action_set_to_recept(self):
        for rec in self:
            if rec.state == 'partial':
                rec.write({'state': 'recept'})

    def laundry_dispatch_enviado(self):
        for rec in self:
            if rec.state == 'draft':
                rec.write({'state': 'send'})

    def laundry_dispatch_recibido(self):
        for rec in self:
            if rec.state == 'send':
                rec.write({'state': 'recept'})

    def laundry_dispatch_parcial(self):
        for rec in self:
            if rec.state == 'send':
                rec.write({'state': 'partial'})

    def confirmar_gd_lines(self):
        self.ensure_one()
        if not self.despacho_lines:
            raise ValidationError(
                _('El detalle no puede estar vacío '
                  '(Seleccionar Orden de Servicio).'))
        for line in self.despacho_lines:
            laundry_id = line.service_order_id
            claim_id = line.service_claim_id
            if claim_id:
                if claim_id.state != 'in_process':
                    raise ValidationError(
                        _('El reclamo "%s" debe estar en estado "En Proceso" '
                          'para poder confirmar el despacho.')
                        % claim_id.codigo_orden_reclamo)
                claim_id.laundry_claim_entransito()
                laundry_id.laundry_reclamo()
                laundry_id.write({'estado_rcl': 'et'})
                claim_id.write({'dispatch_guide_ref': self.id})
            else:
                if laundry_id.state != 'in_process':
                    raise ValidationError(
                        _('La orden "%s" debe estar en estado "En Proceso" '
                          'para poder confirmar el despacho.')
                        % laundry_id.tag_asignado)
                laundry_id.laundry_entransito()
                laundry_id.write({'dispatch_guide_ref': self.id})
        self.laundry_dispatch_enviado()

    def confirmar(self):
        self.ensure_one()
        p = 0
        for line in self.despacho_lines:
            laundry_id = line.service_order_id
            claim_id = line.service_claim_id
            if line.check:
                if claim_id:
                    claim_id.laundry_claim_listo()
                    laundry_id.laundry_reclamo()
                    laundry_id.write({'estado_rcl': 'l'})
                else:
                    laundry_id.laundry_listo()
            else:
                p += 1
                line.write({'partial': True})
        if p == 0:
            self.laundry_dispatch_recibido()
        else:
            self.laundry_dispatch_parcial()

    def recibir(self):
        self.ensure_one()
        if not any(l.partial and l.check for l in self.despacho_lines):
            raise ValidationError(
                _('Debe marcar el check Listo en al menos una línea '
                  'pendiente antes de recibir.'))
        for line in self.despacho_lines:
            if line.partial and line.check:
                laundry_id = line.service_order_id
                claim_id = line.service_claim_id
                if claim_id:
                    claim_id.laundry_claim_listo()
                    laundry_id.laundry_reclamo()
                    laundry_id.write({'estado_rcl': 'l'})
                else:
                    laundry_id.laundry_listo()
            line.write({'partial': False})
        self.action_set_to_recept()
