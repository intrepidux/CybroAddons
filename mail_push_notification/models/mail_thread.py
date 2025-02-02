# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Gokul PI (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from pyfcm import FCMNotification
from odoo import models


class MailThread(models.AbstractModel):
    """Inherits MailThread to send notifications using chatterbox"""
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, notify_by_email=True,
                       **kwargs):
        """Supering the _notify_thread() function to fetch the details of the
         chat message and push that message as a notification """
        msg = message.read()
        res = super(MailThread, self)._notify_thread(
            message, msg_vals=msg_vals, notify_by_email=notify_by_email,
            **kwargs)
        if self.env.company.push_notification and self.env.user.has_group(
                'base.group_user'):
            try:
                push_service = FCMNotification(
                    api_key=self.env.company.server_key)
                domain = []
                receiver_id = False
                if self.is_chat or self.channel_type == 'group':
                    for channel_partners in self.channel_last_seen_partner_ids.filtered(
                            'partner_id'):
                        if channel_partners.partner_id.id != \
                                msg[0]['author_id'][0]:
                            receiver_id = self.env['res.users'].search([(
                                'partner_id',
                                '=',
                                channel_partners.partner_id.id)])
                if receiver_id:
                    domain = [('user_id', '=', receiver_id.id)]
                registration_ids = self.env['push.notification'].search(domain)
                push_service.notify_multiple_devices(
                    registration_ids=[registration_id.register_id for
                                      registration_id in registration_ids],
                    message_title='Send by ' + msg[0]['author_id'][1],
                    message_body=msg[0]['description'],
                    extra_notification_kwargs={
                        'click_action': '/web'
                    })
            except Exception:
                pass
        return res
