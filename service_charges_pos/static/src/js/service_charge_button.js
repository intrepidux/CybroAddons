odoo.define('service_charges_pos.ServiceChargeButton', function(require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');
    const {useListener} = require("@web/core/utils/hooks");

    class ServiceChargeButton extends PosComponent {
        setup() {
            super.setup();
            useListener('click', this._onClick);
        }
        // Click event for button service charge
        async _onClick() {
            if (this.env.pos.config.has_service_charge){
                var global_selection = this.env.pos.config.config_selection
                var global_charge = this.env.pos.config.config_charge
                var visibility = this.env.pos.config.config_visibility
                var global_product = this.env.pos.config.config_product_id[0]

                var order = this.env.pos.get_order();
                var lines = order.get_orderlines();
                if (visibility == 'global') {
                    var product = this.env.pos.db.get_product_by_id(global_product)
                    if (product === undefined) {
                        await this.showPopup('ErrorPopup', {
                            title: this.env._t("No service product found"),
                            body: this.env._t("The service product seems misconfigured. Make sure it is flagged as 'Can be Sold' and 'Available in Point of Sale'."),
                        });
                        return;
                    }
                    // Remove existing discounts
                    lines.filter(line => line.get_product() === product)
                        .forEach(line => order.remove_orderline(line));
                    const {
                        confirmed,
                        payload
                    } = await this.showPopup('NumberPopup', {
                        title: this.env._t('Service Charge'),
                        startingValue: parseInt(global_charge),
                        isInputSelected: true
                    });
                    if (confirmed)
                        if (payload > 0) {
                            if (global_selection == 'amount') {
                                order.add_product(product, {
                                    price: payload
                                });
                            } else {
                                var total_amount = order.get_total_with_tax()
                                var per_amount = payload / 100 * total_amount
                                order.add_product(product, {
                                    price: per_amount
                                });
                            }
                        }

                } else {
                    var type = this.env.pos.config.charge_type
                    var product = this.env.pos.db.get_product_by_id(this.env.pos.config.service_product_id[0]);
                    if (product === undefined) {
                        await this.showPopup('ErrorPopup', {
                            title: this.env._t("No service product found"),
                            body: this.env._t("The service product seems misconfigured. Make sure it is flagged as 'Can be Sold' and 'Available in Point of Sale'."),
                        });
                        return;
                    }
                    // Remove existing discounts
                    lines.filter(line => line.get_product() === product)
                        .forEach(line => order.remove_orderline(line));
                    const {
                        confirmed,
                        payload
                    } = await this.showPopup('NumberPopup', {
                        title: this.env._t('Service Charge'),
                        startingValue: this.env.pos.config.service_charge,
                        isInputSelected: true
                    });
                    if (confirmed){
                        if (payload > 0) {
                            if (type == 'amount') {
                                order.add_product(product, {
                                    price: payload
                                });
                            } else {
                                var total_amount = order.get_total_with_tax()
                                var per_amount = payload / 100 * total_amount
                                order.add_product(product, {
                                    price: per_amount
                                });
                            }
                        }
                    }
                }
            }
        }
    }
    ServiceChargeButton.template = 'service_charges_pos.ServiceChargeButton';
    ProductScreen.addControlButton({
        component: ServiceChargeButton,
        condition: function() {
            return true
        },
    });
    Registries.Component.add(ServiceChargeButton);
    return ServiceChargeButton;
});