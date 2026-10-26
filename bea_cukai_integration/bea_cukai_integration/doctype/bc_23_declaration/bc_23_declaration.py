# Copyright (c) 2026, Nabila and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BC_23_Declaration(Document):
	def validate(self):
		self.validate_po_reference()
		self.calculate_totals()

	def validate_po_reference(self):
		if self.erp_bc_reference:
			po_status = frappe.db.get_value("Purchase Order", self.erp_bc_reference, "docstatus")
			if po_status is None:
				frappe.throw(_("Purchase Order {0} tidak ditemukan").format(self.erp_bc_reference))

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
