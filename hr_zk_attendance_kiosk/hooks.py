# -*- coding: utf-8 -*-

from .models.machine_analysis import _zk_report_daily_attendance_init


def post_init_hook(cr, registry):
    _zk_report_daily_attendance_init(cr)
