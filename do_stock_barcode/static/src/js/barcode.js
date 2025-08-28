odoo.define('do_stock_barcode.barcode', function(require) {
  "use strict";

  var core = require('web.core');
  var BasicModel = require('web.BasicModel');
  var BarcodeFromView = require('barcodes.FormView');
  var FormController = require('web.FormController');
  var _t = core._t;

  BasicModel.include({
    async _performOnChange(record, fields, options = {}) {
      const firstOnChange = options.firstOnChange;
      let { hasOnchange, onchangeSpec } = this._buildOnchangeSpecs(record, options.viewType);
      if (!firstOnChange && !hasOnchange) {
        return;
      }
      var idList = record.data.id ? [record.data.id] : [];
      const ctxOptions = {
        full: true,
      };
      if (fields.length === 1) {
        fields = fields[0];
        // if only one field changed, add its context to the RPC context
        ctxOptions.fieldName = fields;
      }
      var context = this._getContext(record, ctxOptions);
      var currentData = this._generateOnChangeData(record, {
        changesOnly: false,
        firstOnChange,
      });

      const result = await this._rpc({
        model: record.model,
        method: 'onchange',
        args: [idList, currentData, fields, onchangeSpec],
        context: context,
      });
      if (!record._changes) {
        // if the _changes key does not exist anymore, it means that
        // it was removed by discarding the changes after the rpc
        // to onchange. So, in that case, the proper response is to
        // ignore the onchange.
        return;
      }
      if (result.warning) {
        if (fields === '_barcode_scanned' || fields === 'product_barcode_scan') {
          if (result.warning.title === "Successfully Added") {
            this.displayNotification({
              type: 'success',
              title: _t(result.warning.title),
              message: _t(result.warning.message),
              sticky: false
            });
            this.__parentedParent.saveRecord();
          } else {
            this.displayNotification({
              type: 'warning',
              title: _t(result.warning.title),
              message: _t(result.warning.message),
              sticky: false
            });
            $('body').append('<audio src="/do_stock_barcode/static/src/sounds/error.wav" autoplay="true"></audio>');
          }
        } else {
          $('.o_notification_manager').removeClass('success');
          $('.o_notification_manager').removeClass('notification_center');
          this.trigger_up('warning', result.warning);
        }
        record._warning = true;
      }
      if (result.domain) {
        record._domains = Object.assign(record._domains, result.domain);
      }
      await this._applyOnChange(result.value, record, { firstOnChange });
      return result;
    },
  });
  FormController.include({
    _barcodeAddX2MQuantity: function(barcode, activeBarcode) {
      if (this.mode === 'readonly') {
        if (activeBarcode.name == '_barcode_scanned') {
          this._setMode('edit');
        } else {
          this.do_warn(_t('Error: Document not editable'),
            _t('To modify this document, please first start edition.'));
          return Promise.reject();
        }
      }

      var record = this.model.get(this.handle);
      var candidate = this._getBarCodeRecord(record, barcode, activeBarcode);
      if (candidate) {
        return this._barcodeSelectedCandidate(candidate, record, barcode, activeBarcode);
      } else {
        return this._barcodeWithoutCandidate(record, barcode, activeBarcode);
      }
    },
    _barcodeScanned: function(barcode, target) {
      var self = this;
      var resource = this._super.apply(this, arguments);
      if (self.modelName === "stock.picking") {
        self.saveRecord();
      }
      return resource;
    },
  });
});