odoo.define('itx_hr_attendance_kiosk_camera.KioskCameraScanner', function (require) {
    'use strict';

    var KioskCameraScanner = function (options) {
        this.$video = options.$video;
        this.onDetected = options.onDetected;
        this.facingMode = options.facingMode || 'environment';
        this._stream = null;
        this._interval = null;
        this._detector = null;
        this._noDetector = false;
    };

    KioskCameraScanner.prototype._getUserMedia = function () {
        if (!window.isSecureContext) {
            return Promise.reject(new Error('camera_insecure_context'));
        }
        var nav = window.navigator;
        if (!nav.mediaDevices) {
            nav.mediaDevices = {};
        }
        if (!nav.mediaDevices.getUserMedia) {
            var legacy = nav.getUserMedia || nav.webkitGetUserMedia || nav.mozGetUserMedia;
            if (legacy) {
                nav.mediaDevices.getUserMedia = function (constraints) {
                    return new Promise(function (resolve, reject) {
                        legacy.call(nav, constraints, resolve, reject);
                    });
                };
            }
        }
        if (!nav.mediaDevices.getUserMedia) {
            return Promise.reject(new Error('camera_api_missing'));
        }
        var constraints = {video: {facingMode: {ideal: this.facingMode}}, audio: false};
        return nav.mediaDevices.getUserMedia(constraints).catch(function () {
            return nav.mediaDevices.getUserMedia({
                video: true,
                audio: false,
            });
        });
    };

    KioskCameraScanner.prototype.start = function () {
        var self = this;
        var videoEl = this.$video && this.$video[0];
        if (!videoEl) {
            return Promise.reject(new Error('camera_no_video_element'));
        }
        videoEl.setAttribute('playsinline', 'playsinline');
        videoEl.setAttribute('webkit-playsinline', 'webkit-playsinline');
        videoEl.muted = true;
        videoEl.autoplay = true;

        var mediaPromise = this._getUserMedia();
        mediaPromise = Promise.race([
            mediaPromise,
            new Promise(function (resolve, reject) {
                window.setTimeout(function () {
                    reject(new Error('camera_timeout'));
                }, 12000);
            }),
        ]);
        return mediaPromise.then(function (stream) {
            self._stream = stream;
            videoEl.srcObject = stream;
            return new Promise(function (resolve) {
                var onReady = function () {
                    videoEl.removeEventListener('loadedmetadata', onReady);
                    resolve(videoEl.play());
                };
                if (videoEl.readyState >= 1) {
                    resolve(videoEl.play());
                } else {
                    videoEl.addEventListener('loadedmetadata', onReady);
                }
            });
        }).then(function () {
            if (window.BarcodeDetector) {
                try {
                    self._detector = new BarcodeDetector({
                        formats: ['code_128', 'code_39', 'ean_13', 'ean_8', 'qr_code'],
                    });
                    self._interval = window.setInterval(function () {
                        self._tick();
                    }, 400);
                } catch (e) {
                    self._noDetector = true;
                }
            } else {
                self._noDetector = true;
            }
            return {
                hasStream: true,
                canAutoScan: !!self._detector,
            };
        });
    };

    KioskCameraScanner.prototype._tick = function () {
        var self = this;
        var videoEl = this.$video[0];
        if (!this._detector || !videoEl || !videoEl.videoWidth) {
            return;
        }
        this._detector.detect(videoEl).then(function (codes) {
            if (!codes || !codes.length) {
                return;
            }
            var value = codes[0].rawValue;
            if (value) {
                self.stop();
                self.onDetected(value);
            }
        }).catch(function () {});
    };

    KioskCameraScanner.prototype.stop = function () {
        if (this._interval) {
            window.clearInterval(this._interval);
            this._interval = null;
        }
        if (this._stream) {
            this._stream.getTracks().forEach(function (track) {
                track.stop();
            });
            this._stream = null;
        }
        if (this.$video && this.$video[0]) {
            this.$video[0].srcObject = null;
        }
        this._detector = null;
    };

    return KioskCameraScanner;
});
