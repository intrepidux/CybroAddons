# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Aysha Shalin (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
{
    'name': 'Point of Sale Stock Transfer',
    'version': '15.0.1.0.0',
    'summary': """Allows to Directly Transfer the Stock From the Current POS
    Session.""",
    'description': """This module Allows to Directly Transfer the Stock From the
    Current POS Session and enables to select the type of transfer, source and
    destination locations based on picking type.""",
    'category': 'Point of Sale',
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'base', 'point_of_sale'
    ],
    'data': [
        'views/res_config_settings_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'stock_transfer_in_pos/static/src/js/stock_transfer.js',
            'stock_transfer_in_pos/static/src/js/transfer_create_popup.js',
            'stock_transfer_in_pos/static/src/js/transfer_ref_popup.js',
        ],
        'web.assets_qweb': [
            'stock_transfer_in_pos/static/src/xml/stock_transfer_button.xml',
            'stock_transfer_in_pos/static/src/xml/transfer_ref_popup.xml',
            'stock_transfer_in_pos/static/src/xml/transfer_create_popup.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
