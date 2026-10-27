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

	def before_save(self):
		if not self.raw_materials:
			from bea_cukai_integration.api.bc_outbound import explode_bom_for_outbound
			explode_bom_for_outbound(self)

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
		Memastikan riwayat dokumen masuk asal melekat dan sesuai matriks pabean:
		- BC 3.0 (Ekspor) -> WAJIB dari BC 2.3 (Impor)
		- BC 2.5 (Scrap/Lokal) -> WAJIB dari BC 2.3 (Impor)
		- BC 4.1 (Hasil Olahan Lokal) -> WAJIB dari BC 4.0 (Pemasukan Lokal)
		- BC 2.7 Keluar (Antar KB) -> WAJIB dari BC 2.7 (Pemasukan Antar KB)
		- BC 2.6.1 (Perbaikan Non-KB) -> dari BC 2.3, BC 4.0, BC 2.7, BC 2.6.2
		"""
		from bea_cukai_integration.api.bc_outbound import INBOUND_MATCH_MATRIX

		allowed_inbounds = INBOUND_MATCH_MATRIX.get(self.doc_type, [])

		missing_history = []
		mismatched_history = []

		check_rows = self.raw_materials if self.raw_materials else self.items
		for idx, row in enumerate(check_rows, start=1):
			inbound_ref = row.inbound_bc_declaration
			inbound_type = row.inbound_bc_type or (
				frappe.db.get_value("BC_23_Declaration", inbound_ref, "doc_type") if inbound_ref else None
			)
			item_label = getattr(row, "raw_material_item", None) or getattr(row, "item_code", "")

			if not inbound_ref:
				missing_history.append(f"Baris {idx}: Item {item_label} belum memiliki Dokumen BC Masuk Asal")
			elif allowed_inbounds and inbound_type and inbound_type not in allowed_inbounds:
				mismatched_history.append(
					f"Baris {idx}: Item {item_label} menggunakan dokumen masuk '{inbound_type}' ({inbound_ref}), "
					f"padahal pengeluaran '{self.doc_type}' hanya boleh menggunakan dokumen masuk: {', '.join(allowed_inbounds)}."
				)

		if mismatched_history:
			bullet = "<br>• " + "<br>• ".join(mismatched_history)
			frappe.throw(
				_(
					"<b>Pelanggaran Matriks Dokumen Pabean (Tidak Boleh Tercampur):</b><br>"
					"Sesuai ketentuan kepabeanan Kawasan Berikat, dokumen pengeluaran tidak boleh menggunakan dokumen pemasukan yang tidak sesuai:{0}"
				).format(bullet),
				title=_("Ketidaksesuaian Pasangan Dokumen Pabean"),
			)

		if missing_history:
			bullet = "<br>• " + "<br>• ".join(missing_history)
			if self.docstatus == 1:
				frappe.throw(
					_("Setiap pengeluaran pabean wajib melekatkan riwayat dokumen masuknya (No PO, No BC, Harga):{0}").format(bullet),
					title=_("Wajib History Dokumen Masuk"),
				)
			else:
				frappe.msgprint(
					_("Peringatan: Beberapa item/bahan baku belum memiliki riwayat dokumen masuk:{0}").format(bullet),
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
