# Copyright (c) 2026, Nabila and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from bea_cukai_integration.api.bc_23 import make_bc_inbound_from_po
from bea_cukai_integration.api.bc_outbound import (
	assemble_outbound_nomor_aju,
	get_inbound_history_for_item,
	make_bc_outbound_from_sales_order,
	api_create_outbound_bc,
	generate_outbound_ceisa_payload,
)


class TestBCOutboundDeclaration(FrappeTestCase):
	def test_outbound_traceability_flow(self):
		# 1. Siapkan data inbound (PO -> BC 2.3)
		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada PO untuk diuji")

		po_name = po[0].name
		bc_in = make_bc_inbound_from_po(po_name, doc_type="BC 2.3")
		bc_in.no_daftar = "INB-12345"
		bc_in.tgl_daftar = "2026-10-26"
		bc_in.insert()
		bc_in.submit()

		test_item = bc_in.detail_item[0].item_code
		test_rate = bc_in.detail_item[0].rate

		# 2. Uji get_inbound_history_for_item
		history = get_inbound_history_for_item(test_item)
		self.assertTrue(len(history) > 0)
		latest_hist = history[0]
		self.assertEqual(latest_hist["bc_declaration"], bc_in.name)
		self.assertEqual(latest_hist["no_aju"], bc_in.no_aju)
		self.assertEqual(latest_hist["po_reference"], bc_in.erp_bc_reference)
		self.assertEqual(latest_hist["rate"], test_rate)

		# 3. Uji pembuatan BC 3.0 (Ekspor) dengan pelekatan history dokumen masuk
		out_bc = frappe.new_doc("BC_Outbound_Declaration")
		out_bc.doc_type = "BC 3.0"
		out_bc.tgl_aju = "2026-10-26"
		out_bc.customer_name = "Global Trading Ltd."
		out_bc.currency = "USD"
		out_bc.append("items", {
			"item_code": test_item,
			"qty": 10,
			"rate": 150.0,
			"amount": 1500.0,
			# Pelekatan History Masuk
			"inbound_bc_declaration": latest_hist["bc_declaration"],
			"inbound_bc_type": latest_hist["doc_type"],
			"inbound_no_aju": latest_hist["no_aju"],
			"inbound_tgl_aju": latest_hist["tgl_aju"],
			"inbound_no_daftar": latest_hist["no_daftar"],
			"inbound_po_reference": latest_hist["po_reference"],
			"inbound_item_rate": latest_hist["rate"],
			"inbound_currency": latest_hist["currency"],
		})
		out_bc.insert()
		self.assertTrue(out_bc.no_aju.startswith("040330") or "30-" in out_bc.no_aju)
		self.assertEqual(out_bc.items[0].inbound_po_reference, po_name)
		self.assertEqual(out_bc.items[0].inbound_item_rate, test_rate)

		# 4. Uji generate_outbound_ceisa_payload
		payload = generate_outbound_ceisa_payload(out_bc.name)
		self.assertEqual(payload["kodeDokumen"], "30")
		self.assertTrue(len(payload["barang"]) > 0)
		item_dok_asal = payload["barang"][0]["dokumenAsal"]
		self.assertEqual(item_dok_asal["bcMasuk"], bc_in.name)
		self.assertEqual(item_dok_asal["noPoAsal"], po_name)
		self.assertEqual(item_dok_asal["hargaSatuanMasuk"], test_rate)

		# 5. Uji submit outbound
		out_bc.reload()
		out_bc.submit()
		self.assertEqual(out_bc.docstatus, 1)

		# 6. Uji validasi kegagalan jika history dokumen masuk kosong
		empty_hist_bc = frappe.new_doc("BC_Outbound_Declaration")
		empty_hist_bc.doc_type = "BC 2.5"
		empty_hist_bc.tgl_aju = "2026-10-26"
		empty_hist_bc.customer_name = "PT Lokal Jaya"
		empty_hist_bc.append("items", {
			"item_code": test_item,
			"qty": 5,
			"rate": 200.0,
			"amount": 1000.0,
			"inbound_bc_declaration": None,  # Kosong tanpa history
		})
		self.assertRaises(frappe.MandatoryError, empty_hist_bc.insert)

		# Cleanup
		out_bc.cancel()
		out_bc.delete()
		bc_in.cancel()
		bc_in.delete()
