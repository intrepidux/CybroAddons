# -*- coding: utf-8 -*-

import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrAttendanceGeofence(models.Model):
    _name = 'hr.attendance.geofence'
    _description = 'Attendance Geofence'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Working Address',
        help='Linked work location / site.',
    )
    center_latitude = fields.Float(string='Latitude', digits=(10, 7), required=True)
    center_longitude = fields.Float(string='Longitude', digits=(10, 7), required=True)
    radius_m = fields.Float(string='Radius (m)', required=True, default=100.0)

    @api.constrains('radius_m')
    def _check_radius(self):
        for rec in self:
            if rec.radius_m <= 0:
                raise ValidationError(_('Geofence radius must be positive.'))

    @api.model
    def _haversine_m(self, lat1, lon1, lat2, lon2):
        radius_earth = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * radius_earth * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @api.model
    def resolve_for_machine(self, machine, latitude=None, longitude=None, geo_accuracy_m=None):
        """
        Resolve geofence among machine.geofence_ids only (phase 1: never block).
        Returns dict with geofence_id, address_id, geofence_match.
        """
        empty = {
            'geofence_id': False,
            'address_id': False,
            'geofence_match': 'no_gps',
            'latitude': latitude,
            'longitude': longitude,
            'geo_accuracy_m': geo_accuracy_m,
        }
        if latitude is None or longitude is None:
            if machine.default_address_id:
                empty['address_id'] = machine.default_address_id.id
            empty['geofence_match'] = 'no_gps'
            return empty

        candidates = machine.geofence_ids.filtered('active')
        if not candidates:
            empty['geofence_match'] = 'no_config'
            if machine.default_address_id:
                empty['address_id'] = machine.default_address_id.id
            return empty

        inside = []
        for fence in candidates:
            dist = self._haversine_m(latitude, longitude, fence.center_latitude, fence.center_longitude)
            if dist <= fence.radius_m:
                inside.append((dist, fence))

        if not inside:
            result = dict(empty)
            result['geofence_match'] = 'outside'
            if machine.default_address_id:
                result['address_id'] = machine.default_address_id.id
            return result

        inside.sort(key=lambda item: (item[0], item[1].sequence, item[1].id))
        fence = inside[0][1]
        address = fence.partner_id or machine.default_address_id
        return {
            'geofence_id': fence.id,
            'address_id': address.id if address else False,
            'geofence_match': 'matched',
            'latitude': latitude,
            'longitude': longitude,
            'geo_accuracy_m': geo_accuracy_m,
        }
