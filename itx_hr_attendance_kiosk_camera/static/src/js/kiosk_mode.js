odoo.define('itx_hr_attendance_kiosk_camera.kiosk_mode', function (require) {
    'use strict';

    var KioskMode = require('hr_attendance.kiosk_mode');
    require('hr_zk_attendance_kiosk.kiosk_mode');
    var KioskCameraScanner = require('itx_hr_attendance_kiosk_camera.KioskCameraScanner');
    var core = require('web.core');
    var kioskToken = require('hr_zk_attendance_kiosk.kiosk_token_utils');

    function _kioskCompanyId(session) {
        var ids = (session.user_context && session.user_context.allowed_company_ids) || [];
        return ids[0] || session.user_context.company_id || session.company_id;
    }

    KioskMode.include({
        events: {
            'click .o_itx_kiosk_camera_toggle': '_onCameraToggleClick',
        },

        start: function () {
            this._cameraScanner = null;
            this._cameraActive = false;
            this._kioskConfig = {};
            var self = this;
            return Promise.resolve(this._super.apply(this, arguments)).then(function () {
                return self._loadKioskCompanyConfig().catch(function (err) {
                    console.warn('Kiosk company config failed', err);
                });
            });
        },

        destroy: function () {
            this._stopCamera();
            return this._super.apply(this, arguments);
        },

        _loadKioskCompanyConfig: function () {
            var self = this;
            var companyId = _kioskCompanyId(this.session);
            if (!companyId) {
                return Promise.resolve();
            }
            return this._rpc({
                model: 'res.company',
                method: 'read',
                args: [[companyId], [
                    'attendance_kiosk_use_camera',
                    'attendance_kiosk_camera_facing',
                    'attendance_kiosk_hide_manual',
                    'attendance_kiosk_collect_geo',
                    'attendance_use_unified_punch',
                    'attendance_kiosk_feedback_seconds',
                ]],
            }).then(function (rows) {
                self._kioskConfig = rows[0] || {};
                self._applyKioskFeedbackSeconds(
                    self._kioskConfig.attendance_kiosk_feedback_seconds
                );
                if (self._kioskConfig.attendance_kiosk_hide_manual) {
                    self.$('.o_hr_attendance_button_employees').closest('.col-sm-5').addClass('d-none');
                    self.$('.o_hr_attendance_kiosk_welcome_row .col-sm-2').addClass('d-none');
                    self.$('h5.text-muted').text(core._t('Scan your badge to register attendance'));
                }
                if (self._kioskConfig.attendance_kiosk_use_camera) {
                    self._initCameraUi();
                }
            });
        },

        _initCameraUi: function () {
            var $wrap = this.$('.o_itx_kiosk_camera_wrap');
            if (!$wrap.length) {
                $wrap = $(
                    '<div class="o_itx_kiosk_camera_wrap mb16 text-center">'
                    + '<button type="button" class="btn btn-primary o_itx_kiosk_camera_toggle mb-2"/>'
                    + '<div class="o_itx_kiosk_camera_preview d-none">'
                    + '<video class="o_itx_kiosk_camera_video" autoplay playsinline muted/>'
                    + '<p class="text-muted text-center mt8 mb0 o_itx_kiosk_camera_hint"/>'
                    + '</div></div>'
                );
                this.$('.o_hr_attendance_kiosk_welcome_row').before($wrap);
            }
            $wrap.removeClass('d-none');
            this._updateCameraToggleLabel();
        },

        _updateCameraToggleLabel: function () {
            var label = this._cameraActive
                ? core._t('Deactivate camera')
                : core._t('Activate camera');
            this.$('.o_itx_kiosk_camera_toggle').text(label);
        },

        _onCameraToggleClick: function (ev) {
            ev.preventDefault();
            if (this._cameraActive) {
                this._deactivateCamera();
            } else {
                this._activateCamera();
            }
        },

        _activateCamera: function () {
            var self = this;
            var $wrap = this.$('.o_itx_kiosk_camera_wrap');
            $wrap.find('.o_itx_kiosk_camera_preview').removeClass('d-none');
            if (!$wrap.find('.o_itx_kiosk_camera_hint').text()) {
                $wrap.find('.o_itx_kiosk_camera_hint').text(
                    core._t('Point the camera at your badge barcode')
                );
            }
            this._stopCamera();
            this._cameraScanner = new KioskCameraScanner({
                $video: $wrap.find('.o_itx_kiosk_camera_video'),
                facingMode: this._kioskConfig.attendance_kiosk_camera_facing || 'environment',
                onDetected: function (barcode) {
                    self._onBarcodeScanned(barcode);
                },
            });
            return this._cameraScanner.start().then(function (result) {
                self._cameraActive = true;
                self._updateCameraToggleLabel();
                if (result && result.hasStream && !result.canAutoScan) {
                    $wrap.find('.o_itx_kiosk_camera_hint').text(
                        core._t(
                            'Camera preview is on. Automatic barcode read works on Chrome Android '
                            + 'or use a USB/Bluetooth scanner on this device.'
                        )
                    );
                }
            }).catch(function (err) {
                self._deactivateCamera();
                var msg = core._t('Allow camera access in the browser, or use a USB barcode scanner.');
                if (err && err.message === 'camera_insecure_context') {
                    msg = core._t('Camera requires HTTPS. Open the site with https://');
                } else if (err && err.message === 'camera_api_missing') {
                    msg = core._t('This browser cannot access the camera. Try Chrome on Android or a USB scanner.');
                } else if (err && err.message === 'camera_timeout') {
                    msg = core._t('Camera permission timed out. Allow the camera or use a USB scanner.');
                }
                self.displayNotification({
                    title: core._t('Camera unavailable'),
                    message: msg,
                    type: 'warning',
                });
            });
        },

        _deactivateCamera: function () {
            this._stopCamera();
            this._cameraActive = false;
            this.$('.o_itx_kiosk_camera_preview').addClass('d-none');
            this._updateCameraToggleLabel();
        },

        _stopCamera: function () {
            if (this._cameraScanner) {
                this._cameraScanner.stop();
                this._cameraScanner = null;
            }
        },

        _onKioskScanResumed: function () {
            if (this._cameraActive) {
                this._activateCamera();
            }
        },

        _collectGeo: function () {
            if (!this._kioskConfig.attendance_kiosk_collect_geo) {
                return Promise.resolve({});
            }
            if (!navigator.geolocation) {
                return Promise.resolve({geofence_match_hint: 'no_gps'});
            }
            return new Promise(function (resolve) {
                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        resolve({
                            latitude: pos.coords.latitude,
                            longitude: pos.coords.longitude,
                            geo_accuracy_m: pos.coords.accuracy,
                        });
                    },
                    function () {
                        resolve({geofence_match_hint: 'denied'});
                    },
                    {enableHighAccuracy: true, timeout: 8000, maximumAge: 60000}
                );
            });
        },

        _onBarcodeScanned: function (barcode) {
            var self = this;
            core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
            this._deactivateCamera();
            return this._ensureKioskMachineToken().then(function () {
                return self._collectGeo();
            }).then(function (geo) {
                return self._rpc({
                    model: 'hr.employee',
                    method: 'attendance_scan',
                    args: [barcode],
                    kwargs: kioskToken.getKioskRpcKwargs(geo),
                });
            }).then(function (result) {
                self._handleAttendanceScanResult(result);
            }, function () {
                self._resumeKioskAfterScan();
            });
        },
    });
});
