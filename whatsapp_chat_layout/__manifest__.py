# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Yadhukrishnan K (odoo@cybrosys.com)
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
################################################################################
{
    'name': 'Whatsapp Chat Layout in Odoo Discuss',
    'version': '15.0.1.0.0',
    'category': 'Discuss',
    'summary': 'Redesigned the discuss module into whatsapp chat layout',
    'description': """User customize the layout of odoo discuss module like 
     whatsapp""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['mail'],
    'data': ['views/res_config_settings_views.xml'],
    'assets': {
        'web.assets_backend': [
            'whatsapp_chat_layout/static/src/css/whatsapp_chat_layout.css',
            'whatsapp_chat_layout/static/src/js/discuss_sidebar.js',
            'whatsapp_chat_layout/static/src/js/discuss_container.js',
        ],
        'web.assets_qweb': [
            'whatsapp_chat_layout/static/src/xml/discuss_sidebar.xml',
            'whatsapp_chat_layout/static/src/xml/discuss_content.xml',
            'whatsapp_chat_layout/static/src/xml/discuss_sidebar_category.xml',
            'whatsapp_chat_layout/static/src/xml/composer.xml',
        ]
    },
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
