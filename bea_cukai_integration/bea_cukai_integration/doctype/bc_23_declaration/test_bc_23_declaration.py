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

	def test_doctype_sequence_isolation(self):
		from bea_cukai_integration.api.bc_23 import assemble_nomor_aju, get_current_doc_type_sequence

		test_date = "2026-12-31"
		frappe.db.sql("DELETE FROM `tabSeries` WHERE name LIKE %s", "NOAJU%20261231")

		# Buat 2 nomor aju berturut-turut untuk BC 2.3 (000001 dan 000002)
		bc23_1 = assemble_nomor_aju("BC 2.3", tgl_aju=test_date)
		self.assertEqual(bc23_1["no_urut"], "000001")
		bc23_2 = assemble_nomor_aju("BC 2.3", tgl_aju=test_date)
		self.assertEqual(bc23_2["no_urut"], "000002")

		# Buat nomor aju untuk BC 2.7 (harus mulai dari 000001, TIDAK boleh melanjutkan BC 2.3)
		bc27_1 = assemble_nomor_aju("BC 2.7", tgl_aju=test_date)
		self.assertEqual(bc27_1["no_urut"], "000001")
		self.assertNotEqual(bc27_1["no_urut"], bc23_2["no_urut"])

		# Buat nomor aju untuk BC 4.0 (harus mulai dari 000001 secara independen)
		bc40_1 = assemble_nomor_aju("BC 4.0", tgl_aju=test_date)
		self.assertEqual(bc40_1["no_urut"], "000001")

		# Buat nomor aju ke-3 untuk BC 2.3 (harus melanjutkan BC 2.3 sendiri: 000003)
		bc23_3 = assemble_nomor_aju("BC 2.3", tgl_aju=test_date)
		self.assertEqual(bc23_3["no_urut"], "000003")

		# Verifikasi get_current_doc_type_sequence
		seq_info_23 = get_current_doc_type_sequence("BC 2.3", tgl_aju=test_date)
		self.assertEqual(seq_info_23["current_sequence"], 3)
		seq_info_27 = get_current_doc_type_sequence("BC 2.7", tgl_aju=test_date)
		self.assertEqual(seq_info_27["current_sequence"], 1)

		# Cleanup
		frappe.db.sql("DELETE FROM `tabSeries` WHERE name LIKE %s", "NOAJU%20261231")

	def test_is_bc_validation_flow(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
		from bea_cukai_integration.api.bc_23 import validate_purchase_receipt_bc_requirement

		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada PO untuk diuji")

		po_doc = frappe.get_doc("Purchase Order", po[0].name)
		test_item_code = po_doc.items[0].item_code

		# 1. Kasus A: Item NON-BC (custom_is_bc = 0) -> Berjalan normal tanpa BC
		frappe.db.set_value("Item", test_item_code, "custom_is_bc", 0)
		pr_non_bc = make_purchase_receipt(po_doc.name)
		validate_purchase_receipt_bc_requirement(pr_non_bc)

		# 2. Kasus B: Item BC (custom_is_bc = 1) -> Wajib dokumen BC, diblokir jika tanpa BC
		frappe.db.set_value("Item", test_item_code, "custom_is_bc", 1)
		pr_bc_blocked = make_purchase_receipt(po_doc.name)
		pr_bc_blocked.custom_bc_declaration = None
		self.assertRaises(frappe.ValidationError, validate_purchase_receipt_bc_requirement, pr_bc_blocked)

		# 3. Kasus C: Item BC dengan referensi dokumen BC -> Lolos validasi
		pr_bc_blocked.custom_bc_declaration = "BC-TEST-00001"
		validate_purchase_receipt_bc_requirement(pr_bc_blocked)
		# Cleanup state item
		frappe.db.set_value("Item", test_item_code, "custom_is_bc", 0)

	def test_all_inbound_documents(self):
		from bea_cukai_integration.api.bc_23 import (
			make_bc_inbound_from_po,
			make_purchase_receipt_from_bc,
			generate_ceisa_payload,
		)

		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada PO untuk diuji")

		po_name = po[0].name

		# 1. Test BC 4.0 (Pemasukan Lokal TLDDP)
		bc40 = make_bc_inbound_from_po(po_name, doc_type="BC 4.0")
		self.assertEqual(bc40.doc_type, "BC 4.0")
		self.assertTrue("40-" in bc40.no_aju or "40" in bc40.no_aju)
		bc40.no_faktur_pajak = "070.000-26.00000001"
		bc40.tgl_faktur_pajak = "2026-10-26"
		bc40.insert()
		payload40 = generate_ceisa_payload(bc40.name)
		self.assertEqual(payload40["kodeDokumen"], "40")
		self.assertEqual(payload40["dokumen"][0]["kodeDokumen"], "380")
		self.assertEqual(payload40["dokumen"][0]["nomorDokumen"], "070.000-26.00000001")
		bc40.reload()
		bc40.submit()
		pr40 = make_purchase_receipt_from_bc(bc40.name)
		self.assertEqual(pr40.custom_bc_doc_type, "BC 4.0")
		bc40.cancel()
		bc40.delete()

		# 2. Test BC 2.7 (Pemasukan Antar TPB/KB)
		bc27 = make_bc_inbound_from_po(po_name, doc_type="BC 2.7")
		self.assertEqual(bc27.doc_type, "BC 2.7")
		self.assertTrue("27-" in bc27.no_aju or "27" in bc27.no_aju)
		bc27.tpb_asal = "PT Kawasan Berikat Mitra Sejahtera"
		bc27.insert()
		payload27 = generate_ceisa_payload(bc27.name)
		self.assertEqual(payload27["kodeDokumen"], "27")
		self.assertEqual(payload27["entitas"][1]["namaEntitas"], "PT Kawasan Berikat Mitra Sejahtera")
		bc27.reload()
		bc27.submit()
		pr27 = make_purchase_receipt_from_bc(bc27.name)
		self.assertEqual(pr27.custom_bc_doc_type, "BC 2.7")
		bc27.cancel()
		bc27.delete()

		# 3. Test BC 2.6.2 (Pemasukan Kembali setelah Perbaikan)
		bc262 = make_bc_inbound_from_po(po_name, doc_type="BC 2.6.2")
		self.assertEqual(bc262.doc_type, "BC 2.6.2")
		self.assertTrue("26-" in bc262.no_aju or "26" in bc262.no_aju)
		bc262.ref_bc_asal = "040326-000001-20261001-000010"
		bc262.tgl_bc_asal = "2026-10-01"
		bc262.insert()
		payload262 = generate_ceisa_payload(bc262.name)
		self.assertEqual(payload262["kodeDokumen"], "262")
		self.assertEqual(payload262["dokumen"][0]["kodeDokumen"], "261")
		self.assertEqual(payload262["dokumen"][0]["nomorDokumen"], "040326-000001-20261001-000010")
		bc262.reload()
		bc262.submit()
		pr262 = make_purchase_receipt_from_bc(bc262.name)
		self.assertEqual(pr262.custom_bc_doc_type, "BC 2.6.2")
		bc262.cancel()
		bc262.delete()

	def test_ceisa_client_connector(self):
		from bea_cukai_integration.api.ceisa_client import get_ceisa_config, login_ceisa

		config = get_ceisa_config()
		self.assertTrue("https://" in config["base_url"])

		# Uji validasi kredensial kosong
		settings = frappe.get_single("Bea Cukai Settings")
		old_user = settings.ceisa_username
		settings.ceisa_username = None
		settings.ceisa_access_token = None
		settings.save()

		self.assertRaises(frappe.ValidationError, login_ceisa, force=True)

		# Uji penggunaan token aktif
		settings.ceisa_access_token = "mock-active-jwt-token"
		settings.ceisa_token_expiry = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=2)
		settings.save()

		res = login_ceisa(force=False)
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["token"], "mock-active-jwt-token")

		# Cleanup
		settings.ceisa_username = old_user
		settings.ceisa_access_token = None
		settings.save()
