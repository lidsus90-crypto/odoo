# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LaundryDeliveryGuide(models.Model):
    _name = 'laundry.delivery.guide'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Guía de Entrega Lavandería"
    _order = 'fecha_recepcion desc, id desc'

    def _compute_display_name(self):
        for r in self:
            seq = r.codigo_auto or '/'
            r.display_name = '%s - %s' % (seq, r.partner_id.name) if r.partner_id else seq

    @api.depends('guia_lines')
    def _compute_prendas_ge(self):
        for rec in self:
            rec.num_prendas_ge = sum(l.num_prendas for l in rec.guia_lines)

    @api.depends('guia_lines.service_order_id.state')
    def _compute_tiene_os_pendientes(self):
        for rec in self:
            rec.tiene_os_pendientes = any(
                line.service_order_id and line.service_order_id.state != 'delivered'
                for line in rec.guia_lines
            )

    company_id = fields.Many2one(
        'res.company',
        'Empresa',
        required=True,
        default=lambda self: self.env.company,
        readonly=True
    )
    companypl_id = fields.Many2one(
        'res.company',
        'EmprPL'
    )
    planta_id = fields.Many2one(
        'stock.warehouse',
        'Planta',
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
        'Transportista'
    )
    codigo_auto = fields.Char(
        'Secuencial',
        required=True,
        copy=False,
        readonly=True,
        default='/'
    )
    guia_lines = fields.One2many(
        'laundry.delivery.guide.lines',
        'e_list_id',
        'Detalle Guía de Entrega',
        copy=True
    )
    codigo_guia_entrega = fields.Char(
        'Guía',
    )
    fecha_recepcion = fields.Date(
        'Fecha Elaboración',
        required=True,
        default=fields.Date.today
    )
    fecha_entrega = fields.Date(
        'Fecha Entrega',
        default=lambda self: (
                datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    )
    num_prendas_ge = fields.Integer(
        'Prendas',
        store=True,
        readonly=True,
        compute='_compute_prendas_ge',
        tracking=True
    )
    tiene_os_pendientes = fields.Boolean(
        'Tiene OS Pendientes',
        store=True,
        readonly=True,
        compute='_compute_tiene_os_pendientes',
    )
    dispatch_guide_id = fields.Many2one(
        'laundry.dispatch.guide',
        'Guía de Despacho',
        readonly=True,
        copy=False
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
         'La guía de entrega debe ser única por Compañía.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        today = datetime.now().strftime('%Y%m%d')
        for vals in vals_list:
            if vals.get('codigo_auto', '/') == '/':
                vals['codigo_auto'] = (
                        self.env['ir.sequence'].next_by_code(
                            'laundry.delivery.guide') or '/')
            if not vals.get('codigo_guia_entrega'):
                vals['codigo_guia_entrega'] = '%s-%s' % (vals['codigo_auto'], today)
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft',):
                raise ValidationError(
                    _('No puede borrar Guías de Entrega en estado '
                      'diferente a "Borrador".'))
        return super().unlink()

    @api.constrains('fecha_recepcion', 'fecha_entrega')
    def _check_dates(self):
        for rec in self:
            if (rec.fecha_recepcion and rec.fecha_entrega and
                    rec.fecha_recepcion >= rec.fecha_entrega):
                raise ValidationError(
                    _('La fecha de elaboración debe ser menor que la '
                      'fecha de entrega.'))

    def action_set_to_recept(self):
        for rec in self:
            if rec.state == 'partial':
                rec.write({'state': 'recept'})

    def laundry_delivery_borrador(self):
        self.write({'state': 'draft'})

    def laundry_delivery_enviado(self):
        for rec in self:
            if rec.state == 'draft':
                rec.write({'state': 'send'})

    def laundry_delivery_recibido(self):
        for rec in self:
            if rec.state == 'send':
                rec.write({'state': 'recept'})

    def laundry_delivery_parcial(self):
        for rec in self:
            if rec.state == 'send':
                rec.write({'state': 'partial'})

    def confirmar_ge_lines(self):
        self.ensure_one()
        if not self.guia_lines:
            raise ValidationError(
                _('El detalle no puede estar vacío '
                  '(Seleccionar Orden de Servicio).'))
        for line in self.guia_lines:
            laundry_id = line.service_order_id
            claim_id = line.service_claim_id
            if claim_id:
                if claim_id.state != 'received':
                    raise ValidationError(
                        _('El reclamo "%s" debe estar en estado "Recibido" '
                          'para poder confirmar el envío.')
                        % claim_id.codigo_orden_reclamo)
                claim_id.laundry_claim_enviado()
                laundry_id.laundry_reclamo()
                laundry_id.write({'estado_rcl': 'e'})
                claim_id.write({'delivery_guide_ref': self.id})
            else:
                if laundry_id.state != 'received':
                    raise ValidationError(
                        _('La orden "%s" debe estar en estado "Recibido" '
                          'para poder confirmar el envío.')
                        % laundry_id.tag_asignado)
                laundry_id.laundry_enviado()
                laundry_id.write({'delivery_guide_ref': self.id})
        self.laundry_delivery_enviado()

    def confirmar(self):
        self.ensure_one()
        p = 0
        for line in self.guia_lines:
            laundry_id = line.service_order_id
            claim_id = line.service_claim_id
            if line.check:
                if claim_id:
                    claim_id.laundry_claim_enproceso()
                    laundry_id.laundry_reclamo()
                    laundry_id.write({'estado_rcl': 'ep'})
                else:
                    laundry_id.laundry_enproceso()
            else:
                p += 1
                line.write({'partial': True})
        if p == 0:
            self.laundry_delivery_recibido()
        else:
            self.laundry_delivery_parcial()

    def recibir(self):
        self.ensure_one()
        if not any(l.partial and l.check for l in self.guia_lines):
            raise ValidationError(
                _('Debe marcar el check Listo en al menos una línea '
                  'pendiente antes de recibir.'))
        for line in self.guia_lines:
            if line.partial and line.check:
                laundry_id = line.service_order_id
                claim_id = line.service_claim_id
                if claim_id:
                    claim_id.laundry_claim_enproceso()
                    laundry_id.laundry_reclamo()
                    laundry_id.write({'estado_rcl': 'ep'})
                else:
                    laundry_id.laundry_enproceso()
            line.write({'partial': False})
        self.action_set_to_recept()
