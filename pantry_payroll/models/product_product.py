# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Bhagyadev K P(<https://www.cybrosys.com>)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
################################################################################
from odoo import fields, models


class ProductProduct(models.Model):
    """Class for adding quantity button on product kanban view."""
    _inherit = "product.product"

    quantity = fields.Integer(string="Quantity", help="Quantity", default=1)

    def action_quantity_decrement(self):
        """Function for increment the quantity of product"""
        if self.quantity > 1:
            self.quantity -= 1

    def action_quantity_increment(self):
        """Function for decrement the quantity of product"""
        self.quantity += 1

    def action_buy_pantry(self):
        """Make a quotation while purchasing a product from the pantry."""
        quotation = self.env['pantry.order'].search(
            [('partner_id', '=', self.env.user.partner_id.id),
             ('state', '=', 'draft')])
        val_list = {
            'product_id': self.id,
            'unit_price': self.lst_price,
            'quantity': self.quantity,
        }
        if quotation:
            val_list['pantry_order_id'] = quotation[0].id
            product = quotation.order_line_ids.filtered(
                lambda sol: sol.product_id == self)
            if product:
                product[0].quantity += self.quantity
            else:
                quotation.write(
                    {'order_line_ids': [fields.Command.create(val_list)]})
        else:
            quotation = self.env['pantry.order'].create({
                'partner_id': self.env.user.partner_id.id,
                'order_line_ids': [fields.Command.create(val_list)]
            })
        self.quantity = 1
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pantry.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
            'views': [[False, "form"]],
        }
