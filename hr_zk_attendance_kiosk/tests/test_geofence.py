# -*- coding: utf-8 -*-

from odoo.tests import common


class TestGeofenceResolve(common.TransactionCase):

    def test_haversine_zero_distance(self):
        Geofence = self.env['hr.attendance.geofence']
        dist = Geofence._haversine_m(18.5, -69.9, 18.5, -69.9)
        self.assertAlmostEqual(dist, 0.0, places=1)

    def test_resolve_inside_device_subset(self):
        company = self.env.company
        fence_a = self.env['hr.attendance.geofence'].create({
            'name': 'Site A',
            'company_id': company.id,
            'center_latitude': 18.4861,
            'center_longitude': -69.9312,
            'radius_m': 500,
        })
        fence_b = self.env['hr.attendance.geofence'].create({
            'name': 'Site B',
            'company_id': company.id,
            'center_latitude': 19.0,
            'center_longitude': -70.0,
            'radius_m': 500,
        })
        machine = self.env['zk.machine'].create({
            'name': 'Tablet 1',
            'device_kind': 'kiosk',
            'port_no': 0,
            'company_id': company.id,
            'geofence_ids': [(6, 0, [fence_a.id])],
        })
        geo = self.env['hr.attendance.geofence'].resolve_for_machine(
            machine, latitude=18.4861, longitude=-69.9312,
        )
        self.assertEqual(geo['geofence_match'], 'matched')
        self.assertEqual(geo['geofence_id'], fence_a.id)

        geo_out = self.env['hr.attendance.geofence'].resolve_for_machine(
            machine, latitude=19.0, longitude=-70.0,
        )
        self.assertEqual(geo_out['geofence_match'], 'outside')
