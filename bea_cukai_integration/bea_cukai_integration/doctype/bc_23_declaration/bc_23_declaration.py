# Copyright (c) 2026, Nabila and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BC_23_Declaration(Document):
	def before_insert(self):
		settings = frappe.get_single("Bea Cukai Settings")
		if settings.auto_generate_no_aju:
			from bea_cukai_integration.api.bc_23 import assemble_nomor_aju
			assembled = assemble_nomor_aju(self.doc_type or "BC 2.3", self.tgl_aju, self.no_urut)
			self.no_urut = assembled["no_urut"]
			self.no_aju = assembled["no_aju"]

	def validate(self):
		self.validate_po_reference()
		self.validate_no_aju()
		self.validate_ex_bc_261()
		self.calculate_totals()

	def validate_ex_bc_261(self):
		if self.doc_type == "BC 2.6.2" and not self.ref_bc_asal:
			if self.docstatus == 1:
				frappe.throw(
					_("Dokumen BC 2.6.2 (Masuk Setelah Diperbaiki) WAJIB mencantumkan referensi dokumen asal BC 2.6.1 (Ex 2.6.1) pada field 'No Aju / No Daftar BC 2.6.1 Asal'."),
					title=_("Wajib Dokumen Asal Ex 2.6.1"),
				)
			else:
				frappe.msgprint(
					_("Perhatian: Dokumen BC 2.6.2 wajib mencantumkan referensi dokumen pengeluaran sementara BC 2.6.1 asal."),
					alert=True,
				)
	def validate_po_reference(self):
		if self.erp_bc_reference:
			po_status = frappe.db.get_value("Purchase Order", self.erp_bc_reference, "docstatus")
			if po_status is None:
				frappe.throw(_("Purchase Order {0} tidak ditemukan").format(self.erp_bc_reference))

	def validate_no_aju(self):
		settings = frappe.get_single("Bea Cukai Settings")
		if settings.auto_generate_no_aju:
			from bea_cukai_integration.api.bc_23 import assemble_nomor_aju
			assembled = assemble_nomor_aju(self.doc_type or "BC 2.3", self.tgl_aju, self.no_urut)
			self.no_urut = assembled["no_urut"]
			self.no_aju = assembled["no_aju"]
		elif self.no_aju:
			from bea_cukai_integration.api.bc_23 import parse_and_validate_no_aju
			res = parse_and_validate_no_aju(self.no_aju)
			if not res["is_valid"]:
				if self.docstatus == 1:
					frappe.throw(_("Nomor Aju tidak valid: {0}").format(res["message"]))
				else:
					frappe.msgprint(_("Peringatan: {0}").format(res["message"]), alert=True)
	def calculate_totals(self):
		total_amount = sum(flt(item.amount) for item in self.detail_item)
		if not self.cif_value or self.cif_value == 0:
			self.cif_value = total_amount + flt(self.freight)

	def on_submit(self):
		self.is_final = 1

	@frappe.whitelist()
	def make_purchase_receipt(self):
		from bea_cukai_integration.api.bc_23 import make_purchase_receipt_from_bc
		return make_purchase_receipt_from_bc(self.name)
