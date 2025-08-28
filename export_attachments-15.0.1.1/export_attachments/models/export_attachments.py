# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import tempfile
import zipfile
from odoo import api, models, fields
from odoo.addons.http_routing.models.ir_http import slug, unslug
from odoo.exceptions import ValidationError


class ExportAttachments(models.Model):
	_name = 'export.attachments'
	_description = 'Export Attachments Action'
	_rec_name = 'model_id'

	model_id = fields.Many2one('ir.model', string='Model')
	server_action_id = fields.Many2one('ir.actions.server', string='Server Action')
	bind_model_id = fields.Many2one(related='server_action_id.binding_model_id', string='Binding Model')
	active = fields.Boolean('Active', default=True)
	export_field_line = fields.One2many('export.field.line', 'export_id', string='Field Lines')
	is_attachment = fields.Boolean("Download Related Documents from Attachments", default=True, help='Download related documents from attachments')
	groups_id = fields.Many2many('res.groups', string='Allowed Groups')

	def get_server_action_data(self):
		# Server Action Data Generation
		model_id = self.model_id
		if not model_id:
			raise ValidationError('Please Fill Model !!!')
		return {
			'name': 'Export Attachments',
			'model_id': model_id.id,
			'binding_model_id': model_id.id,
			'state': 'code',
			'code': """
				if records:
					action = env['export.attachments'].with_context({'record_ids': records.ids}).browse(%s).download_attachments()
			""" % (self.id)
		}

	def create_server_action(self):
		# Create Server Action
		if self.server_action_id:
			raise ValidationError('Already Server Action Created !!!')
		self.server_action_id = self.env['ir.actions.server'].create(self.get_server_action_data())
	
	def update_server_action(self):
		# Update Created Server Action
		if not self.server_action_id:
			raise ValidationError('Please Create Server action, and try again !!!')
		self.server_action_id.write(self.get_server_action_data())

	def create_action(self):
		# Add Action Menu
		if not self.server_action_id:
			raise ValidationError('Please Create Server action, and try again !!!')
		self.server_action_id.create_action()

	def unlink_action(self):
		# Remove Action Menu
		if self.server_action_id:
			self.server_action_id.unlink_action()

	def download_attachments(self):
		# Download Attachment trigger based on configuration
		context = self.env.context
		if self.groups_id:
			user_groups = self.env.user.groups_id
			allow = any([True for x in self.groups_id.ids if x in user_groups.ids])
			if not allow:
				raise ValidationError('You Are Not allowed to export Attachments !!!')
		url = '/download_attachments/%s?record_ids=%s' % (
				str(self.id),
				context.get('record_ids'))
		return {
			'name': ("Download Attachments"),
			'type': 'ir.actions.act_url',
			'url': url,
			'target': 'self',
		}
	
	def _get_data_file(self, record_ids):
		# Create Zip file
		model = self.model_id.model
		attach_obj = self.env['ir.attachment']
		filename = model.replace('.', '_') + '-Data'
		t_zip = tempfile.TemporaryFile()
		with zipfile.ZipFile(t_zip, 'a', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
			if self.is_attachment:
				records = attach_obj.search([('res_model', '=', model), ('res_id', 'in', record_ids), ('type', '=', 'binary')])
				if records:
					for file_name, datas in [('[{0}-{1}]{2}'.format(attach.res_model.replace('.', '_'), attach.res_id, attach.name), attach.datas) for attach in records]:
						if datas:
							zipf.writestr(file_name, base64.b64decode(datas))
				else:
					raise ValidationError('No Attachments found !!!')
			elif self.export_field_line:
				records = self.env[model].browse(record_ids)
				if records:
					field_data = {line.bname_field_id.name: line.binary_field_id.name for line in self.export_field_line}
					for record in records:
						for fname_field, datas_field in field_data.items():
							file_name = '[{0}-{1}-{2}]{3}'.format(model.replace('.', '_'), record.id, datas_field, getattr(record, fname_field))
							if '.' not in file_name[-5:]:  # For image widget fields doesn't need a filename field , mostly compute image fields 
								file_name = file_name + '.png'
							datas = getattr(record, datas_field)
							if datas:
								zipf.writestr(file_name, base64.b64decode(datas))
							else:
								raise ValidationError('No Attachments found !!!')
		a = t_zip.seek(0)
		return filename, t_zip
	
	def unlink(self):
		for rec in self:
			if rec.server_action_id:
				# Explicitly unlink export attachment so we have to delete that the related server action
				rec.server_action_id.unlink()
		return super(ExportAttachments, self).unlink()


class ExportFieldLine(models.Model):
	_name = 'export.field.line'
	_description = 'Export Field Lines'
	_rec_name = 'export_id'

	export_id = fields.Many2one('export.attachments', string='Export Attachment')
	binary_field_id = fields.Many2one('ir.model.fields', string='Binary Data Field')
	bname_field_id = fields.Many2one('ir.model.fields', string='Binary Filename Field')
