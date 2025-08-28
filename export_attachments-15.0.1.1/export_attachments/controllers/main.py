# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo.addons.http_routing.models.ir_http import slug, unslug
from odoo.http import Controller, request, route, content_disposition

_logger = logging.getLogger(__name__)


class ExportAttachmentController(Controller):

    @route('/download_attachments/<export_id>', type='http', auth='user')
    def download_attachments_control(self, export_id, **kwargs):
        record_ids = eval(kwargs.get('record_ids', '[]'))
        try:
            filename, t_zip = request.env['export.attachments'].browse(int(export_id))._get_data_file(record_ids)
        except Exception as e:
            auto_goBack = "<script>setTimeout(function(){window.history.back();}, 2000);</script>"
            return f"{auto_goBack}<center><h1 style='color:red'>{e.name}</h1><br><button onclick='window.history.back();'>Back</button></center>"
        headers = [
            ('Content-Type', 'application/octet-stream; charset=binary'),
            ('Content-Disposition', content_disposition('%s.zip' % filename))
            ]
        _logger.info('Download Attachments zip: %s', filename)
        return request.make_response(t_zip, headers=headers)
