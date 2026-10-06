odoo.define('hr_zk_attendance_kiosk.kiosk_token_utils', function () {
    'use strict';

    var MACHINE_TOKEN_KEY = 'hr_attendance_kiosk_machine_token';
    var MACHINE_ID_KEY = 'hr_attendance_kiosk_machine_id';

    function normalizeToken(token) {
        if (!token) {
            return null;
        }
        token = String(token).trim();
        var hashIdx = token.indexOf('#');
        if (hashIdx !== -1) {
            token = token.substring(0, hashIdx);
        }
        return token || null;
    }

    function parseMachineTokenFromLocation() {
        var search = window.location.search || '';
        var match = search.match(/[?&]machine_token=([^&]+)/);
        if (match) {
            return normalizeToken(decodeURIComponent(match[1]));
        }
        var hash = window.location.hash || '';
        match = hash.match(/machine_token=([^&]+)/);
        return match ? normalizeToken(decodeURIComponent(match[1])) : null;
    }

    function storeKioskSession(data) {
        if (data && data.machine_token) {
            window.sessionStorage.setItem(
                MACHINE_TOKEN_KEY,
                normalizeToken(data.machine_token)
            );
        }
        if (data && data.machine_id) {
            window.sessionStorage.setItem(MACHINE_ID_KEY, String(data.machine_id));
        }
    }

    function getKioskRpcKwargs(geo) {
        var kwargs = Object.assign({}, geo || {});
        kwargs.machine_token = normalizeToken(
            window.sessionStorage.getItem(MACHINE_TOKEN_KEY)
        );
        var machineId = window.sessionStorage.getItem(MACHINE_ID_KEY);
        if (machineId) {
            kwargs.machine_id = parseInt(machineId, 10);
        }
        return kwargs;
    }

    return {
        MACHINE_TOKEN_KEY: MACHINE_TOKEN_KEY,
        MACHINE_ID_KEY: MACHINE_ID_KEY,
        normalizeToken: normalizeToken,
        parseMachineTokenFromLocation: parseMachineTokenFromLocation,
        storeKioskSession: storeKioskSession,
        getKioskRpcKwargs: getKioskRpcKwargs,
    };
});
