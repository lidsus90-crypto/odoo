# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LaundryMakeInvoice(models.TransientModel):
    _name = 'laundry.make.invoice'
    _description = 'Facturación Órdenes Lavandería'

    grouped = fields.Boolean(
        'Agrupar facturas',
        help='Las órdenes de servicio deben pertenecer al mismo cliente')
    invoice_date = fields.Date(
        'Fecha Factura', default=fields.Date.today)

    def make_invoices(self):
        active_ids = self.env.context.get('active_ids', [])
        orders = self.env['laundry.management'].browse(active_ids)

        # Validar que ninguna tenga ya factura
        for order in orders:
            if order.invoice_ref_id:
                raise ValidationError(
                    _('La orden %s ya está facturada.') % order.tag_asignado)

        # Crear facturas
        new_invoices = self.env['account.move']
        if self.grouped:
            # Agrupar por cliente
            by_partner = {}
            for order in orders:
                by_partner.setdefault(order.partner_id.id, []).append(order)
            for partner_id, partner_orders in by_partner.items():
                invoice = self._make_invoice_grouped(partner_orders)
                new_invoices |= invoice
        else:
            for order in orders:
                invoice = order.view_invoice()
                # view_invoice returns action; re-browse
                new_invoices |= self.env['account.move'].browse(
                    order.invoice_ref_id.id)

        return {
            'name': _('Facturas Lavandería'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', new_invoices.ids)],
        }

    def _make_invoice_grouped(self, orders):
        """Crea una factura agrupando varias órdenes del mismo cliente."""
        first = orders[0]
        journal = self.env['account.journal'].search([
            ('company_id', '=', first.company_id.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not journal:
            raise ValidationError(_('No se encontró un diario de ventas.'))

        invoice_lines = []
        for order in orders:
            for line in order.service_lines:
                product = line.product_id
                account = (
                    product.property_account_income_id or
                    product.categ_id.property_account_income_categ_id)
                if not account:
                    raise ValidationError(
                        _('El producto "%s" no tiene cuenta de ingresos.')
                        % product.display_name)
                taxes = line.tax_id.filtered(
                    lambda t: t.company_id == order.company_id)
                invoice_lines.append((0, 0, {
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
            'partner_id': first.partner_id.id,
            'invoice_date': self.invoice_date or fields.Date.today(),
            'journal_id': journal.id,
            'currency_id': first.currency_id.id,
            'invoice_origin': ', '.join(o.tag_asignado for o in orders),
            'company_id': first.company_id.id,
            'user_id': first.user_id.id,
            'invoice_line_ids': invoice_lines,
            'laundry_grouped': True,
        })
        for order in orders:
            order.write({'invoice_ref_id': invoice.id, 'facturado': True})
            order.invoice_ids = [(4, invoice.id)]
        return invoice
