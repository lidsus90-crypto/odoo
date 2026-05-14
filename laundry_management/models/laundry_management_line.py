# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

# ── Líneas de Orden ───────────────────────────────────────────────────────────

class LaundryManagementLine(models.Model):
    _name = 'laundry.management.line'
    _inherit = ['mail.thread']
    _description = "Líneas de Orden de Lavandería"
    _order = 'order_laundry_id desc, sequence, id'

    @api.depends('price_unit', 'discount', 'tax_id',
                 'product_uom_qty', 'product_id',
                 'order_laundry_id.partner_id',
                 'order_laundry_id.currency_id')
    def _compute_price(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price, line.order_laundry_id.currency_id,
                line.product_uom_qty,
                product=line.product_id,
                partner=line.order_laundry_id.partner_id)
            line.price_subtotal = taxes['total_excluded']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']

    order_laundry_id = fields.Many2one(
        'laundry.management',
        string='Pedido',
        required=True, ondelete='cascade',
        readonly=True
    )
    sequence = fields.Integer(
        'Secuencia', default=10)
    product_id = fields.Many2one(
        'product.product',
        'Prenda',
        change_default=True
    )
    name = fields.Text('Descripción', required=True)
    color = fields.Selection([
        ('amarillo', 'Amarillo'),
        ('blue', 'Azul'),
        ('beige', 'Beige'),
        ('white', 'Blanco'),
        ('brown', 'Café'),
        ('gris', 'Gris'),
        ('mostaza', 'Mostaza'),
        ('black', 'Negro'),
        ('perla', 'Perla'),
        ('red', 'Rojo'),
        ('green', 'Verde'),
        ('red1', 'Vino'),
        ('otros', 'Otros'),
    ], string='Color',
        required=True,
        default='otros'
    )
    price_unit = fields.Float(
        'Precio Unitario', digits='Product Price', required=True, default=0.0)
    price_subtotal = fields.Float(
        string='Subtotal', digits='Account', compute='_compute_price',
        store=True)
    price_tax = fields.Float(
        string='Impuesto', digits='Account', compute='_compute_price',
        store=True)
    tax_id = fields.Many2many(
        'account.tax',
        'laundry_management_line_tax',
        'laundry_management_line_id',
        'tax_id',
        'Taxes'
    )
    product_uom_qty = fields.Float(
        'Cantidad',
        digits='Product Unit of Measure',
        required=True,
        default=1
    )
    product_uom = fields.Many2one(
        'uom.uom', 'Unidad de Medida',
        default=lambda self: self.env.ref(
            'uom.product_uom_unit', raise_if_not_found=False))
    discount = fields.Float(
        'Descuento (%)', digits='Discount', default=0.0)
    method_id = fields.Many2one(
        'laundry.method.catalogue', string='Método Lavado')
    tiempo = fields.Char('Tiempo Entrega')
    cantp = fields.Integer('Nº Prendas', store=True)
    method_type_id = fields.Many2many(
        'laundry.method.type.catalogue',
        'laundry_method_type_catalogue_line',
        'laundry_method_type_catalogue_id', 'method_type_id',
        'Bandera')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente',
        related='order_laundry_id.partner_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        related='order_laundry_id.company_id', store=True, readonly=True)
    claim_id = fields.Many2one(
        'laundry.claim', string='Reclamo',
        related='order_laundry_id.claim_ref', store=True, readonly=True)
    observacion = fields.Char('Observación')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        tmpl = self.product_id.product_tmpl_id
        self.name = self.product_id.display_name
        self.method_id = tmpl.method_id
        self.tiempo = tmpl.tiempo
        self.cantp = tmpl.num_prendas_servicio
        self.product_uom = self.product_id.uom_id
        # Impuestos según posición fiscal
        taxes = self.product_id.taxes_id.filtered(
            lambda t: t.company_id == self.order_laundry_id.company_id)
        fpos = self.order_laundry_id.fiscal_position
        if fpos:
            taxes = fpos.map_tax(taxes)
        self.tax_id = taxes
        # Precio
        if self.order_laundry_id.pricelist_id:
            price = self.order_laundry_id.pricelist_id._get_product_price(
                self.product_id, self.product_uom_qty or 1.0,
                currency=self.order_laundry_id.currency_id)
            self.price_unit = price
        else:
            self.price_unit = self.product_id.lst_price
