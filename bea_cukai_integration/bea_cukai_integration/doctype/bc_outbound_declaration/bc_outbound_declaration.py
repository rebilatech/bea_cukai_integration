# Copyright (c) 2026, Nabila and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class BC_Outbound_Declaration(Document):
	def before_insert(self):
		settings = frappe.get_single("Bea Cukai Settings")
		if settings.auto_generate_no_aju:
			from bea_cukai_integration.api.bc_outbound import assemble_outbound_nomor_aju
			assembled = assemble_outbound_nomor_aju(self.doc_type or "BC 3.0", self.tgl_aju, self.no_urut)
			self.no_urut = assembled["no_urut"]
			self.no_aju = assembled["no_aju"]

	def validate(self):
		self.validate_no_aju()
		self.validate_inbound_history()
		self.calculate_totals()

	def validate_no_aju(self):
		settings = frappe.get_single("Bea Cukai Settings")
		if settings.auto_generate_no_aju:
			from bea_cukai_integration.api.bc_outbound import assemble_outbound_nomor_aju
			assembled = assemble_outbound_nomor_aju(self.doc_type or "BC 3.0", self.tgl_aju, self.no_urut)
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

	def validate_inbound_history(self):
		"""
		Memastikan setiap baris item pengeluaran WAJIB memiliki riwayat dokumen masuknya
		(No PO, Dokumen BC Masuk, Harga Masuk).
		"""
		missing_history = []
		for idx, item in enumerate(self.items, start=1):
			if not item.inbound_bc_declaration:
				missing_history.append(f"Baris {idx}: Item {item.item_code} belum memiliki Dokumen BC Masuk Asal")

		if missing_history:
			bullet = "<br>• " + "<br>• ".join(missing_history)
			if self.docstatus == 1:
				frappe.throw(
					_("Setiap item pengeluaran wajib melekatkan riwayat dokumen masuknya (No PO, No BC, Harga):{0}").format(bullet),
					title=_("Wajib History Dokumen Masuk"),
				)
			else:
				frappe.msgprint(
					_("Peringatan: Beberapa item belum memiliki riwayat dokumen masuk:{0}").format(bullet),
					alert=True,
				)

	def calculate_totals(self):
		total = 0.0
		for item in self.items:
			if not item.amount and item.qty and item.rate:
				item.amount = flt(item.qty) * flt(item.rate)
			total += flt(item.amount)
		self.total_amount = total

	def on_submit(self):
		self.is_final = 1
