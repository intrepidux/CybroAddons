# -*- coding: utf-8 -*-
{
    'name': 'ITX HR Attendance Kiosk Camera',
    'version': '15.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Kiosk camera barcode scan, hide manual identification',
    'depends': [
        'hr_attendance',
        'barcodes',
        'hr_zk_attendance_kiosk',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'itx_hr_attendance_kiosk_camera/static/src/js/kiosk_camera_scanner.js',
            'itx_hr_attendance_kiosk_camera/static/src/js/kiosk_mode.js',
            'itx_hr_attendance_kiosk_camera/static/src/scss/kiosk_camera.scss',
        ],
        'web.assets_qweb': [
            'itx_hr_attendance_kiosk_camera/static/src/xml/kiosk_templates.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
