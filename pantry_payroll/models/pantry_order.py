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
from odoo import api, fields, models


class PantryOrder(models.Model):
    """A class that represents a new model pantry order"""
    _name = 'pantry.order'
    _description = 'Pantry Order'
    _inherit = 'mail.thread'

    name = fields.Char(string='Order Sequence', readonly=True,
                       help='Sequence of the order')
    partner_id = fields.Many2one('res.partner', string='Order User',
                                 readonly=True,
                                 default=lambda self: self.env.user.partner_id,
                                 help='The user who is ordering')
    state = fields.Selection(string='Status', required=True, selection=[
        ('draft', 'Draft'), ('confirmed', 'Confirmed')], default='draft',
                             help='The current status of the order')
    date_order = fields.Datetime(string='Order Date',
                                 default=fields.Datetime.now, readonly=True,
                                 help='The date order')
    order_line_ids = fields.One2many('pantry.order.line',
                                     'pantry_order_id',
                                     string='Order Line')
    amount_total = fields.Float(string='Total', compute='_compute_amount_total',
                                help='The total amount of the order')

    @api.model
    def create(self, vals):
        """Sequence for the order"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'pantry.order') or 'New'
        res = super(PantryOrder, self).create(vals)
        return res

    @api.depends('order_line_ids')
    def _compute_amount_total(self):
        """Calculates the amount_total"""
        for rec in self:
            rec.amount_total = sum(
                rec.mapped('order_line_ids').mapped('subtotal'))

    def action_confirm_pantry_order(self):
        """Change the state to confirmed"""
        self.state = 'confirmed'
