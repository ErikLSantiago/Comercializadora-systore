
/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import VariantMixin from "@website_sale/js/sale_variant_mixin";
import publicWidget from "@web/legacy/js/public/public_widget";
import { WebsiteSale } from '@website_sale/js/website_sale';

     publicWidget.registry.WebsiteSale.include({

        _onChangeCombination: function (ev, $parent, combination) {
     			this.get_status_quote = combination.quote_variant
     			this._super(...arguments);
     		},
        _toggleDisable: function ($parent, isCombinationPossible) {
        		this._super.apply(this, arguments);
            VariantMixin._toggleDisable.apply(this, arguments);
            if (this.get_status_quote){
        			$parent.find("#product_quote_price").show()
        		}
        		else{
        			$parent.find("#product_quote_price").hide()
        		}
            $parent.find("#add_to_cart_quote").toggleClass('disabled', !this.get_status_quote);
            $parent.find("#add_to_cart").toggleClass('disabled', !this.get_status_quote);
            // $parent.find("#product_quote_price").toggleClass('disabled', !this.get_status_quote);
            $parent.find("#buy_now").toggleClass('disabled', !this.get_status_quote);
            $parent.find("#request_quote").toggleClass('disabled', this.get_status_quote);
        },
    });


	publicWidget.registry.websiteQuote=publicWidget.Widget.extend({
		 selector: '.oe_website_sale',
		read_events: {
			'change #txt': '_onClickQuote',
			'click #bt_non':'_onNonlogin',
			'click .request_quote_btn':'_onRequestQuoteBtn',
			'change select[name="country_id"]': '_onCountryChange',
		},

		start() {
        this._super(...arguments);
		
        this.rpc = rpc;
        this.dialog = this.bindService("dialog");
        this.$state = this.$('select[name="state_id"]');
   		this.$stateOptions = this.$state.filter(':enabled').find('option:not(:first)');
   		this._adaptAddressForm();
    },
		_onClickQuote: function () {
				var jsonObj = [];
				$('#tbl tbody tr').each(function(){
					var in_val = $(this).find("#txt > input[type=text]").val();
					var x = $(this).find('#txt').attr('line_id');
					var item = {}
					item [x] = in_val;
					jsonObj.push(item);

				});
				var user = session.uid
				this.rpc('/quote/cart/update_json', {
						jsdata: jsonObj,
					},
				).then(function (data) {
					window.location.href = '/quote/cart';
				});
		},
		_onNonlogin: function () {
			var id1 = document.getElementById("txt1").value
			var obj = document.getElementById("obj").value
			rpc("/shop/product/quote/confirm/nonlogin","call",{
				'id1' : id1,
				'obj':obj,
			}).then(function (data) {
				window.location.href = '/thank_you';
			});
		},
		_onRequestQuoteBtn: function () {
			var product_id = $(".product_id").val();
			$('form').attr('action','/quote/product/selected/'+product_id);
  			$('form').submit();
		},
		_adaptAddressForm: function () {
			   var $country = this.$('select[name="country_id"]');
			   var countryID = $country.val() || 0;

			   this.$state = this.$('select[name="state_id"]');
			   this.$stateOptions = this.$state.filter(':enabled').find('option:not(:first)');

			   if (this.$state && this.$stateOptions) {
			      this.$stateOptions.detach();
			      var $displayedState = this.$stateOptions.filter('[data-country_id=' + countryID + ']');
			      var nb = $displayedState.appendTo(this.$state).show().length;
			      this.$state.parent().toggle(nb >= 1);
			   }
			},


	    //--------------------------------------------------------------------------
	    // Handlers
	    //--------------------------------------------------------------------------

	    /**
	     * @private
	     */
		_onCountryChange: function () {
		     this._adaptAddressForm();
		},

	});

	

