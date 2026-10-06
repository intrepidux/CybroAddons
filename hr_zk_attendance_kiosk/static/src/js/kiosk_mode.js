odoo.define('hr_zk_attendance_kiosk.kiosk_mode', function (require) {
    'use strict';

    var KioskMode = require('hr_attendance.kiosk_mode');
    var core = require('web.core');
    var kioskToken = require('hr_zk_attendance_kiosk.kiosk_token_utils');

    function _kioskCompanyId(session) {
        var ids = (session.user_context && session.user_context.allowed_company_ids) || [];
        return ids[0] || session.user_context.company_id || session.company_id;
    }

    KioskMode.include({
        start: function () {
            var self = this;
            return Promise.resolve(this._super.apply(this, arguments)).then(function () {
                // Do not block kiosk UI on token RPC (camera/config must render first).
                self._ensureKioskMachineToken();
                self._loadKioskFeedbackDuration();
            });
        },

        KIOSK_FEEDBACK_DEFAULT_SEC: 5,
        KIOSK_FEEDBACK_MIN_SEC: 3,
        KIOSK_FEEDBACK_MAX_SEC: 20,

        _clampFeedbackSeconds: function (seconds) {
            var sec = parseInt(seconds, 10);
            if (isNaN(sec)) {
                sec = this.KIOSK_FEEDBACK_DEFAULT_SEC;
            }
            return Math.min(
                this.KIOSK_FEEDBACK_MAX_SEC,
                Math.max(this.KIOSK_FEEDBACK_MIN_SEC, sec)
            );
        },

        _applyKioskFeedbackSeconds: function (seconds) {
            this._kioskFeedbackSeconds = this._clampFeedbackSeconds(seconds);
        },

        _getPunchFeedbackMs: function () {
            var sec = this._kioskFeedbackSeconds;
            if (sec === undefined) {
                sec = this.KIOSK_FEEDBACK_DEFAULT_SEC;
            }
            return this._clampFeedbackSeconds(sec) * 1000;
        },

        _loadKioskFeedbackDuration: function () {
            var self = this;
            var companyId = _kioskCompanyId(this.session);
            if (!companyId) {
                this._applyKioskFeedbackSeconds(this.KIOSK_FEEDBACK_DEFAULT_SEC);
                return Promise.resolve();
            }
            return this._rpc({
                model: 'res.company',
                method: 'read',
                args: [[companyId], ['attendance_kiosk_feedback_seconds']],
            }).then(function (rows) {
                var sec = rows[0] && rows[0].attendance_kiosk_feedback_seconds;
                self._applyKioskFeedbackSeconds(sec);
            }).catch(function () {
                self._applyKioskFeedbackSeconds(self.KIOSK_FEEDBACK_DEFAULT_SEC);
            });
        },

        _ensureKioskMachineToken: function () {
            var self = this;
            return this._rpc({
                model: 'res.users',
                method: 'get_attendance_kiosk_session_public',
                args: [],
            }).then(function (data) {
                if (data && data.machine_token) {
                    kioskToken.storeKioskSession(data);
                    return data.machine_token;
                }
                var fromUrl = kioskToken.parseMachineTokenFromLocation();
                if (fromUrl) {
                    kioskToken.storeKioskSession({machine_token: fromUrl});
                    return fromUrl;
                }
                return kioskToken.normalizeToken(
                    window.sessionStorage.getItem(kioskToken.MACHINE_TOKEN_KEY)
                );
            }).catch(function () {
                var fromUrl = kioskToken.parseMachineTokenFromLocation();
                if (fromUrl) {
                    kioskToken.storeKioskSession({machine_token: fromUrl});
                    return fromUrl;
                }
                return null;
            });
        },

        _collectGeo: function () {
            var companyId = _kioskCompanyId(this.session);
            return this._rpc({
                model: 'res.company',
                method: 'read',
                args: [[companyId], ['attendance_kiosk_collect_geo']],
            }).then(function (rows) {
                if (!rows[0] || !rows[0].attendance_kiosk_collect_geo) {
                    return {};
                }
                if (!navigator.geolocation) {
                    return {geofence_match_hint: 'no_gps'};
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
            });
        },

        _onBarcodeScanned: function (barcode) {
            var self = this;
            core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
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

        _handleAttendanceScanResult: function (result) {
            if (result && result.success) {
                this._showPunchFeedback(result);
                return;
            }
            if (result && result.action) {
                this.do_action(result.action);
                return;
            }
            if (result && result.warning) {
                this.displayNotification({title: result.warning, type: 'danger'});
            }
            this._resumeKioskAfterScan();
        },

        _showPunchFeedback: function (result) {
            var self = this;
            this.$('.o_hr_kiosk_punch_feedback').remove();
            var $fb = $('<div class="o_hr_kiosk_punch_feedback alert alert-success"/>');
            $fb.append($('<h3 class="mb-1"/>').text(result.employee_name || ''));
            if (result.machine_name) {
                $fb.append(
                    $('<p class="mb-1 text-muted"/>').text(
                        core._t('Device') + ': ' + result.machine_name
                    )
                );
            }
            $fb.append(
                $('<p class="mb-0"/>').text(
                    result.message || core._t('Punch recorded.')
                )
            );
            this.$el.append($fb);
            window.setTimeout(function () {
                $fb.remove();
                self._resumeKioskAfterScan();
            }, self._getPunchFeedbackMs());
        },

        _resumeKioskAfterScan: function () {
            core.bus.on('barcode_scanned', this, this._onBarcodeScanned);
            if (this._onKioskScanResumed) {
                this._onKioskScanResumed();
            }
        },
    });
});
