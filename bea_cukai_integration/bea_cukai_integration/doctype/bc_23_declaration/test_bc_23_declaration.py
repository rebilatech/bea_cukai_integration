# Copyright (c) 2026, Nabila and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from bea_cukai_integration.api.bc_23 import (
	make_bc_23_from_po,
	make_purchase_receipt_from_bc,
	generate_ceisa_payload,
	api_create_bc_23,
	api_make_purchase_receipt,
)


class TestBC_23_Declaration(FrappeTestCase):
	def test_po_to_bc_to_pr_flow(self):
		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada Purchase Order submitted untuk diuji")

		po_name = po[0].name

		# 1. Test mapping PO -> BC 2.3
		bc = make_bc_23_from_po(po_name)
		self.assertEqual(bc.erp_bc_reference, po_name)
		self.assertEqual(bc.doc_type, "BC 2.3")
		self.assertTrue(len(bc.detail_item) > 0)

		# Pastikan nomor aju sudah ter-generate otomatis saat make_bc_23_from_po
		self.assertTrue(bool(bc.no_aju))
		bc.tgl_aju = "2026-10-26"
		bc.no_daftar = "001234"
		bc.tgl_daftar = "2026-10-26"
		bc.qty_pack = 10
		bc.uom_name = "CT"
		bc.insert()
		self.assertTrue(bc.name.startswith("BC-"))

		# 2. Test CEISA payload generation
		payload = generate_ceisa_payload(bc.name)
		self.assertEqual(payload["nomorAju"], bc.no_aju)
		self.assertEqual(payload["kodeDokumen"], "23")
		self.assertTrue(len(payload["barang"]) > 0)

		# 3. Test submit BC 2.3
		bc.reload()
		bc.submit()
		self.assertEqual(bc.docstatus, 1)

		# 4. Test mapping BC 2.3 -> Purchase Receipt
		pr = make_purchase_receipt_from_bc(bc.name)
		self.assertEqual(pr.custom_bc_declaration, bc.name)
		self.assertEqual(pr.custom_bc_doc_type, "BC 2.3")
		self.assertEqual(pr.custom_bc_no_aju, bc.no_aju)
		self.assertEqual(pr.custom_bc_no_daftar, "001234")
		self.assertTrue(len(pr.items) > 0)

		# Cleanup
		bc.cancel()
		bc.delete()

	def test_rest_api_endpoints(self):
		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada Purchase Order submitted untuk diuji")

		po_name = po[0].name

		frappe.form_dict = frappe._dict({
			"purchase_order": po_name,
			"no_aju": "000023-999999-20261026-000002",
			"tgl_aju": "2026-10-26",
			"no_daftar": "999999",
			"tgl_daftar": "2026-10-26",
			"submit": 1,
		})
		res = api_create_bc_23()
		self.assertEqual(res["status"], "success")
		bc_name = res["data"]["name"]
		self.assertEqual(res["data"]["docstatus"], 1)

		frappe.form_dict = frappe._dict({
			"bc_name": bc_name,
			"submit": 0,
		})
		res_pr = api_make_purchase_receipt()
		self.assertEqual(res_pr["status"], "success")
		pr_name = res_pr["data"]["purchase_receipt"]
		self.assertTrue(frappe.db.exists("Purchase Receipt", pr_name))

		# Cleanup
		frappe.delete_doc("Purchase Receipt", pr_name, force=True)
		bc = frappe.get_doc("BC_23_Declaration", bc_name)
		bc.cancel()
		bc.delete()
		frappe.form_dict = frappe._dict()

	def test_generate_nomor_aju(self):
		from bea_cukai_integration.api.bc_23 import generate_nomor_aju

		# Test dengan tanda hubung
		no_aju_hyphen = generate_nomor_aju("BC 2.3", tgl_aju="2026-10-26", with_hyphen=True)
		parts = no_aju_hyphen.split("-")
		self.assertEqual(len(parts), 4)
		self.assertEqual(parts[0], "040323")  # kantor 0403 + doc 23
		self.assertEqual(parts[1], "000001")  # perusahaan
		self.assertEqual(parts[2], "20261026")  # tanggal
		self.assertEqual(len(parts[3]), 6)  # nomor urut

		# Test tanpa tanda hubung (persis 26 karakter)
		no_aju_raw = generate_nomor_aju("BC 2.3", tgl_aju="2026-10-26", with_hyphen=False)
		self.assertEqual(len(no_aju_raw), 26)
		self.assertTrue(no_aju_raw.startswith("04032300000120261026"))

	def test_custom_no_urut_reassembly(self):
		from bea_cukai_integration.api.bc_23 import assemble_nomor_aju

		# Test user memasukkan no_urut custom "42" (otomatis padding jadi 000042)
		res = assemble_nomor_aju("BC 2.3", tgl_aju="2026-10-26", no_urut="42", with_hyphen=True)
		self.assertEqual(res["no_urut"], "000042")
		self.assertEqual(res["no_aju"], "040323-000001-20261026-000042")

		# Test pergantian jenis dokumen ke BC 2.7 dengan no_urut "000123"
		res2 = assemble_nomor_aju("BC 2.7", tgl_aju="2026-10-26", no_urut="000123", with_hyphen=True)
		self.assertEqual(res2["no_urut"], "000123")
		self.assertEqual(res2["no_aju"], "040327-000001-20261026-000123")
