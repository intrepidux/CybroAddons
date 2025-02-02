odoo.define('theme_autofly.all_type', function(require){
    'use strict';
    const publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');

    publicWidget.registry.all_type = publicWidget.Widget.extend({
        selector : '.all_type',
        /**Function for fetching the details of car types**/
        start: function(){
            var self = this;
            ajax.jsonRpc('/get_all_type', 'call', {})
            .then(function (data) {
                if(data){
                    self.$el.html(data);
                }
            });
        }
    });
});