# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta
from dateutil import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class LaundryManagement(models.Model):
    _name = 'laundry.management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Orden de Servicio Lavandería"
    _order = 'clean_start_time desc, id desc'

    def _compute_display_name(self):
        for record in self:
            seq = record.tag_asignado or '/'
            record.display_name = '%s - %s' % (seq, record.partner_id.name) if record.partner_id else seq

    # ── Campos computados ────────────────────────────────────────────────

    @api.depends('service_lines.price_subtotal', 'service_lines.price_tax')
    def _compute_amount(self):
        for rec in self:
            rec.amount_untaxed = sum(
                l.price_subtotal for l in rec.service_lines)
            rec.amount_tax = sum(
                l.price_tax for l in rec.service_lines)
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    @api.depends('service_lines')
    def _compute_total_prendas(self):
        for rec in self:
            rec.total_prendas = sum(
                l.product_uom_qty * l.cantp for l in rec.service_lines)

    @api.depends('service_lines')
    def _compute_max_dias(self):
        for rec in self:
            max_d = 1
            for line in rec.service_lines:
                try:
                    dias = int(line.tiempo or 1)
                except (ValueError, TypeError):
                    dias = 1
                if dias > max_d:
                    max_d = dias
            rec.aux = max_d

    @api.depends('clean_start_time', 'service_lines')
    def _compute_fecha_entrega(self):
        for rec in self:
            rec.clean_end_time = datetime.now() + relativedelta.relativedelta(
                days=+(rec.aux or 1))

    # ── Definición de campos ─────────────────────────────────────────────

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
        string='Cliente',
        change_default=True,
        required=True,
        tracking=True
    )
    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Dirección de Entrega',
        tracking=True,
        domain="['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]",
    )
    fiscal_position = fields.Many2one(
        'account.fiscal.position',
        'Posición Fiscal'
    )
    tag_asignado = fields.Char(
        'Secuencial',
        required=True,
        copy=False,
        readonly=True,
        default='/'
    )
    codigo_orden_servicio = fields.Char(
        'Etiqueta',
        copy=False,
        readonly=True,
        default='/',
    )
    clean_start_time = fields.Datetime(
        'Fecha Recepción',
        required=True,
        default=fields.Datetime.now
    )
    clean_end_time = fields.Datetime(
        'Fecha Entrega',
        compute='_compute_fecha_entrega',
        store=True
    )
    invoice_ref_id = fields.Many2one(
        'account.move',
        'Nº Factura',
        ondelete='set null',
        readonly=True
    )
    service_lines = fields.One2many(
        'laundry.management.line',
        'order_laundry_id',
        'Líneas de Servicio',
        copy=True
    )
    state = fields.Selection([
        ('received',   'Recibido'),
        ('sent',       'Enviado'),
        ('in_process', 'En proceso'),
        ('in_transit', 'En tránsito'),
        ('ready',      'Listo'),
        ('delivered',  'Entregado'),
        ('claim',      'Reclamo'),
    ], string='Estado',
        required=True,
        readonly=True,
        default='received',
        tracking=True
    )
    pricelist_id = fields.Many2one(
        'product.pricelist',
        'Tarifa'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='pricelist_id.currency_id',
        store=True,
        readonly=True
    )
    informacion = fields.Text(
        'Observación',
    )
    whatsapp_mobile = fields.Char(
        'WhatsApp',
        tracking=True,
        help='Número WhatsApp del cliente para enviar la Orden de Servicio. '
             'Se llena automáticamente desde el celular del contacto.',
    )
    porcentaje_iva_aplicado = fields.Selection([
        ('auto', 'Automático'),
        ('iva12', 'IVA 12%'),
        ('iva14', 'IVA 14%'),
    ], '% IVA aplicado',
        required=True,
        default='auto',
        copy=True
    )
    amount_untaxed = fields.Float(
        string='Subtotal', digits='Account',
        store=True, readonly=True, compute='_compute_amount', tracking=True)
    amount_tax = fields.Float(
        string='Impuestos', digits='Account',
        store=True, readonly=True, compute='_compute_amount')
    amount_total = fields.Float(
        string='Total', digits='Account',
        store=True, readonly=True, compute='_compute_amount')
    total_prendas = fields.Integer(
        string='Prendas', store=True, readonly=True,
        compute='_compute_total_prendas', tracking=True)
    aux = fields.Integer(
        'Max días', store=True, readonly=True, compute='_compute_max_dias')
    delivery_guide_ref = fields.Many2one(
        'laundry.delivery.guide', 'Guía Entrega', readonly=True)
    dispatch_guide_ref = fields.Many2one(
        'laundry.dispatch.guide', 'Guía Despacho', readonly=True)
    claim_ref = fields.Many2one(
        'laundry.claim', 'Nº Reclamo', readonly=True)
    planta_id = fields.Many2one(
        'stock.warehouse', 'Planta/PA')
    facturado = fields.Boolean('Factura Generada', default=False)
    reclamo = fields.Boolean('Reclamo', default=False)
    estado_rcl = fields.Char('Estado de Reclamo', default='ep')
    invoice_ids = fields.Many2many(
        'account.move',
        'laundry_order_invoice_rel',
        'order_laundry_id', 'invoice_id',
        'Facturas', readonly=True, copy=False)

    _sql_constraints = [
        ('name_uniq', 'unique(tag_asignado, company_id)',
         'El secuencial de la orden debe ser único por Compañía.'),
    ]

    # ── ORM ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        today = datetime.now().strftime('%Y%m%d')
        for vals in vals_list:
            if vals.get('tag_asignado', '/') == '/':
                vals['tag_asignado'] = (
                        self.env['ir.sequence'].next_by_code(
                            'laundry.management') or '/')
            if not vals.get('codigo_orden_servicio') or vals.get('codigo_orden_servicio') == '/':
                vals['codigo_orden_servicio'] = '%s-%s' % (vals['tag_asignado'], today)
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('received',):
                raise ValidationError(
                    _('No puede borrar Órdenes de Servicio en estado '
                      'diferente a "Recibido".'))
        return super().unlink()

    # ── Constrains ───────────────────────────────────────────────────────

    @api.constrains('clean_start_time', 'clean_end_time')
    def _check_dates(self):
        for rec in self:
            if (rec.clean_start_time and rec.clean_end_time and
                    rec.clean_start_time >= rec.clean_end_time):
                raise ValidationError(
                    _('La fecha de recepción debe ser menor que la '
                      'fecha de entrega.'))

    # ── Cambios de estado ─────────────────────────────────────────────────

    def laundry_entransito(self):
        for rec in self:
            if rec.state == 'in_process':
                rec.write({'state': 'in_transit'})

    def laundry_enproceso(self):
        for rec in self:
            if rec.state == 'sent':
                rec.write({'state': 'in_process'})

    def laundry_listo(self):
        for rec in self:
            if rec.state == 'in_transit':
                rec.write({'state': 'ready'})

    def laundry_entregado(self):
        for rec in self:
            if rec.state not in ('ready', 'claim'):
                continue
            if rec.delivery_guide_ref and rec.delivery_guide_ref.state != 'recept':
                raise ValidationError(
                    _('La orden "%s" no puede marcarse como Entregada: '
                      'la Guía de Entrega no está en estado Recibido.')
                    % rec.tag_asignado)
            if rec.dispatch_guide_ref and rec.dispatch_guide_ref.state != 'recept':
                raise ValidationError(
                    _('La orden "%s" no puede marcarse como Entregada: '
                      'la Guía de Despacho no está en estado Recibido.')
                    % rec.tag_asignado)
            rec.write({'state': 'delivered'})

    def laundry_reclamo(self):
        self.write({'state': 'claim'})

    def set_to_l(self):
        for rec in self:
            if rec.state == 'claim':
                rec.write({'state': 'ready'})

    def laundry_enviado(self):
        for rec in self:
            if rec.state == 'received':
                rec.write({'state': 'sent'})

    # ── Onchange ─────────────────────────────────────────────────────────

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
        if not self.whatsapp_mobile:
            self.whatsapp_mobile = (
                self.partner_id.mobile or self.partner_id.phone or False
            )

    @api.onchange('whatsapp_mobile')
    def _onchange_whatsapp_mobile(self):
        if self.partner_id and self.whatsapp_mobile:
            self.partner_id.mobile = self.whatsapp_mobile

    # ── Acciones ─────────────────────────────────────────────────────────

    def view_invoice(self):
        """Crea factura de la orden de servicio."""
        self.ensure_one()
        if self.invoice_ref_id:
            raise ValidationError(
                _('No puede generar otra factura; la orden ya está '
                  'vinculada a una factura.'))

        partner = self.partner_id
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not journal:
            raise UserError(_('No se encontró un diario de ventas.'))

        invoice_lines_vals = []
        for line in self.service_lines:
            product = line.product_id
            account = (
                    product.property_account_income_id or
                    product.categ_id.property_account_income_categ_id
            )
            if not account:
                raise UserError(
                    _('El producto "%s" no tiene cuenta de ingresos '
                      'definida.') % product.display_name)
            taxes = line.tax_id.filtered(
                lambda t: t.company_id == self.company_id)
            invoice_lines_vals.append((0, 0, {
                'product_id': product.id,
                'name': line.name or product.display_name,
                'quantity': line.product_uom_qty,
                'product_uom_id': line.product_uom.id,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, taxes.ids)],
                'account_id': account.id,
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': self.clean_start_time.date()
            if self.clean_start_time else fields.Date.today(),
            'journal_id': journal.id,
            'fiscal_position_id': self.fiscal_position.id
            if self.fiscal_position else False,
            'invoice_origin': self.tag_asignado,
            'narration': self.informacion,
            'user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'invoice_line_ids': invoice_lines_vals,
        })
        self.write({'invoice_ref_id': invoice.id, 'facturado': True})
        self.invoice_ids = [(4, invoice.id)]

        return {
            'name': _('Factura Lavandería'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def crear_reclamo(self):
        """Crea un registro de reclamo vinculado a la orden."""
        self.ensure_one()
        self.laundry_reclamo()

        vals = {
            'partner_id': self.partner_id.id,
            'partner_shipping_id': self.partner_shipping_id.id
            if self.partner_shipping_id else False,
            'fiscal_position': self.fiscal_position.id
            if self.fiscal_position else False,
            'clean_start_time': self.clean_start_time,
            'clean_end_time': self.clean_end_time,
            'user_id': self.user_id.id,
            'codigo_orden_reclamo': (self.tag_asignado or '') + 'R',
            'invoice_ref_id': self.invoice_ref_id.id
            if self.invoice_ref_id else False,
            'state': 'received',
            'currency_id': self.currency_id.id,
            'informacion': self.informacion,
            'porcentaje_iva_aplicado': self.porcentaje_iva_aplicado,
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'total_prendas': self.total_prendas,
            'lorder_id': self.id,
            'company_id': self.company_id.id,
        }
        claim = self.env['laundry.claim'].create(vals)

        # 1. Preparamos una lista de diccionarios
        vals_list = []

        for line in self.service_lines:
            vals_list.append({
                'order_claim_id': claim.id,
                'product_id': line.product_id.id,
                'name': line.name,
                'color': line.color,
                'discount': line.discount,
                'company_id': line.company_id.id,
                'order_laundry_id': line.order_laundry_id.id,
                'product_uom_qty': line.product_uom_qty,
                'observacion': line.observacion,
            })

        # 2. Creamos todos los registros en una sola transacción SQL
        if vals_list:
            self.env['laundry.claim.line'].create(vals_list)

        self.write({'claim_ref': claim.id, 'reclamo': True,
                    'estado_rcl': 'ep'})
        return {
            'name': _('Orden Reclamo'),
            'type': 'ir.actions.act_window',
            'res_model': 'laundry.claim',
            'view_mode': 'form',
            'res_id': claim.id,
        }

    def desvincular(self):
        self.set_to_l()
        self.write({'reclamo': False})

    def confirmar(self):
        """Cambia estado a Entregado; exige factura y guías recibidas."""
        self.ensure_one()
        if not self.invoice_ref_id:
            raise ValidationError(
                _('La orden de servicio no puede ser entregada sin '
                  'haber sido facturada.'))
        if self.delivery_guide_ref and self.delivery_guide_ref.state != 'recept':
            raise ValidationError(
                _('La Guía de Entrega debe estar en estado "Recibido" '
                  'para poder entregar la orden.'))
        if self.dispatch_guide_ref and self.dispatch_guide_ref.state != 'recept':
            raise ValidationError(
                _('La Guía de Despacho debe estar en estado "Recibido" '
                  'para poder entregar la orden.'))
        self.laundry_entregado()
        if self.claim_ref:
            self.claim_ref.laundry_claim_entregado()

    def action_send_whatsapp(self):
        """Genera el PDF de la Orden de Servicio, lo adjunta al registro
        y abre WhatsApp con el número configurado."""
        self.ensure_one()

        if not self.whatsapp_mobile:
            raise UserError(
                _('Ingrese el número de WhatsApp del cliente antes de enviar.'))

        # ── Limpiar número: solo dígitos y el + inicial ─────────────────
        raw = self.whatsapp_mobile.strip()
        wa_number = re.sub(r'[^\d+]', '', raw)
        if wa_number.startswith('+'):
            wa_number = wa_number[1:]
        if not wa_number:
            raise UserError(_('El número de WhatsApp "%s" no es válido.') % raw)

        # ── Generar PDF ──────────────────────────────────────────────────
        pdf_content, _report_type = self.env['ir.actions.report']._render_qweb_pdf(
            'laundry_management.action_report_laundry_order',
            res_ids=[self.id],
        )
        filename = 'Orden_Servicio_%s.pdf' % (self.tag_asignado or self.id)

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': pdf_content,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        self.message_post(
            body=_('PDF de Orden de Servicio generado para envío por WhatsApp.'),
            attachment_ids=[attachment.id],
        )

        # ── Abrir WhatsApp Web con el número ─────────────────────────────
        wa_url = 'https://wa.me/%s' % wa_number
        return {
            'type': 'ir.actions.act_url',
            'url': wa_url,
            'target': 'new',
        }

    def button_dummy(self):
        return True