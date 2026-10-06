# -*- coding: utf-8 -*-
{
    'name': 'HR ZK Attendance Kiosk',
    'version': '15.0.1.0.1',
    'category': 'Human Resources',
    'summary': 'Unified kiosk punches with ZK pairing, geofences, and device ACL',
    'depends': [
        'hr_zk_attendance',
        'hr_attendance',
        'barcodes',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_attendance_geofence_views.xml',
        'views/zk_machine_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/res_users_views.xml',
        'views/zk_report_daily_attendance_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_zk_attendance_kiosk/static/src/js/kiosk_token_utils.js',
            'hr_zk_attendance_kiosk/static/src/js/kiosk_mode.js',
            'hr_zk_attendance_kiosk/static/src/scss/kiosk_feedback.scss',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'post_init_hook': 'hooks.post_init_hook',
}
