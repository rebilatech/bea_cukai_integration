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
			"inbound_bc_declaration": None,
		})
		empty_hist_bc.insert()
		empty_hist_bc.docstatus = 1
		self.assertRaises(frappe.ValidationError, empty_hist_bc.validate_inbound_history)
		empty_hist_bc.delete()
		out_bc.cancel()
		out_bc.delete()
		bc_in.cancel()
		bc_in.delete()

	def test_bom_manufactured_goods_traceability(self):
		from bea_cukai_integration.api.bc_outbound import explode_bom_for_outbound

		# 1. Pastikan ada BOM untuk _Test FG Item
		bom_name = frappe.db.get_value("BOM", {"item": "_Test FG Item", "is_active": 1}, "name")
		if not bom_name:
			self.skipTest("BOM untuk _Test FG Item tidak ditemukan")

		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		po_name = po[0].name

		# 2. Siapkan dokumen masuk pabean untuk bahan baku _Test Item
		raw_in_bc = frappe.new_doc("BC_23_Declaration")
		raw_in_bc.doc_type = "BC 2.3"
		raw_in_bc.tgl_aju = "2026-10-26"
		raw_in_bc.no_aju = "040323-000001-20261026-000999"
		raw_in_bc.no_daftar = "INB-999"
		raw_in_bc.tgl_daftar = "2026-10-26"
		raw_in_bc.erp_bc_reference = po_name
		raw_in_bc.append("detail_item", {
			"item_code": "_Test Item",
			"item_name": "_Test Item",
			"qty": 500,
			"uom": "Nos",
			"stock_uom": "Nos",
			"conversion_factor": 1.0,
			"rate": 50.0,
			"amount": 25000.0,
			"base_rate": 50.0,
			"base_amount": 25000.0,
			"schedule_date": "2026-10-26",
		})
		raw_in_bc.insert()
		raw_in_bc.submit()

		# 3. Buat dokumen pengeluaran ekspor BC 3.0 untuk Barang Jadi (_Test FG Item)
		fg_out_bc = frappe.new_doc("BC_Outbound_Declaration")
		fg_out_bc.doc_type = "BC 3.0"
		fg_out_bc.tgl_aju = "2026-10-26"
		fg_out_bc.customer_name = "Overseas Buyer Corp."
		fg_out_bc.append("items", {
			"item_code": "_Test FG Item",
			"qty": 10,
			"rate": 500.0,
			"amount": 5000.0,
		})
		fg_out_bc.insert()

		# 4. Uji explode_bom_for_outbound
		explode_res = explode_bom_for_outbound(fg_out_bc.name)
		self.assertTrue(explode_res["count"] > 0)

		fg_out_bc.reload()
		self.assertTrue(len(fg_out_bc.raw_materials) > 0)
		rm_row = [r for r in fg_out_bc.raw_materials if r.raw_material_item == "_Test Item"][0]
		self.assertEqual(rm_row.finished_good_item, "_Test FG Item")
		self.assertEqual(rm_row.bom_no, bom_name)
		self.assertEqual(rm_row.qty_consumed, 10.0)
		self.assertEqual(rm_row.inbound_bc_declaration, raw_in_bc.name)
		self.assertEqual(rm_row.inbound_po_reference, po_name)
		self.assertEqual(rm_row.inbound_item_rate, 50.0)

		# 5. Uji CEISA 4.0 Payload dengan array bahanBaku
		ceisa_payload = generate_outbound_ceisa_payload(fg_out_bc.name)
		self.assertEqual(ceisa_payload["kodeDokumen"], "30")
		fg_ceisa_item = ceisa_payload["barang"][0]
		self.assertEqual(fg_ceisa_item["kodeBarang"], "_Test FG Item")
		self.assertTrue("bahanBaku" in fg_ceisa_item)
		self.assertTrue(len(fg_ceisa_item["bahanBaku"]) > 0)
		ceisa_bb = [bb for bb in fg_ceisa_item["bahanBaku"] if bb["kodeBahanBaku"] == "_Test Item"][0]
		self.assertEqual(ceisa_bb["jumlahPemakaian"], 10.0)
		self.assertEqual(ceisa_bb["dokumenAsal"]["bcMasuk"], raw_in_bc.name)
		self.assertEqual(ceisa_bb["dokumenAsal"]["noPoAsal"], po_name)
		self.assertEqual(ceisa_bb["dokumenAsal"]["hargaSatuanMasuk"], 50.0)

		# Cleanup
		fg_out_bc.delete()
		raw_in_bc.cancel()
		raw_in_bc.delete()
	def test_customs_document_pairing_matrix(self):
		from bea_cukai_integration.api.bc_23 import make_bc_inbound_from_po

		po = frappe.get_all(
			"Purchase Order",
			filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]},
			order_by="creation asc",
			limit=1,
		)
		if not po:
			self.skipTest("Tidak ada PO untuk diuji")

		po_name = po[0].name

		# 1. Dokumen Masuk BC 2.3 (Impor)
		bc23_in = make_bc_inbound_from_po(po_name, doc_type="BC 2.3")
		bc23_in.insert()
		bc23_in.submit()

		# 2. Dokumen Masuk BC 4.0 (Lokal)
		bc40_in = make_bc_inbound_from_po(po_name, doc_type="BC 4.0")
		bc40_in.no_faktur_pajak = "070.000-26.00000099"
		bc40_in.insert()
		bc40_in.submit()

		test_item = bc23_in.detail_item[0].item_code

		# ATURAN 1: BC 2.3 in -> BC 3.0 export (VALID)
		out_bc30 = frappe.new_doc("BC_Outbound_Declaration")
		out_bc30.doc_type = "BC 3.0"
		out_bc30.tgl_aju = "2026-10-26"
		out_bc30.append("items", {
			"item_code": test_item,
			"qty": 1,
			"rate": 100,
			"inbound_bc_declaration": bc23_in.name,
			"inbound_bc_type": "BC 2.3",
		})
		out_bc30.insert()
		out_bc30.validate_inbound_history()

		# ATURAN 2: BC 2.3 in -> BC 2.5 scrap/lokal (VALID)
		out_bc25 = frappe.new_doc("BC_Outbound_Declaration")
		out_bc25.doc_type = "BC 2.5"
		out_bc25.tgl_aju = "2026-10-26"
		out_bc25.append("items", {
			"item_code": test_item,
			"qty": 1,
			"rate": 100,
			"inbound_bc_declaration": bc23_in.name,
			"inbound_bc_type": "BC 2.3",
		})
		out_bc25.insert()
		out_bc25.validate_inbound_history()

		# ATURAN 3: BC 4.0 in -> BC 4.1 (VALID)
		out_bc41 = frappe.new_doc("BC_Outbound_Declaration")
		out_bc41.doc_type = "BC 4.1"
		out_bc41.tgl_aju = "2026-10-26"
		out_bc41.append("items", {
			"item_code": test_item,
			"qty": 1,
			"rate": 100,
			"inbound_bc_declaration": bc40_in.name,
			"inbound_bc_type": "BC 4.0",
		})
		out_bc41.insert()
		out_bc41.validate_inbound_history()

		# ATURAN 4: CROSS-CONTAMINATION REJECTION:
		# Coba pasangkan BC 4.1 dengan BC 2.3 impor -> HARUS DITOLAK
		mismatched_bc = frappe.new_doc("BC_Outbound_Declaration")
		mismatched_bc.doc_type = "BC 4.1"
		mismatched_bc.tgl_aju = "2026-10-26"
		mismatched_bc.append("items", {
			"item_code": test_item,
			"qty": 1,
			"rate": 100,
			"inbound_bc_declaration": bc23_in.name,
			"inbound_bc_type": "BC 2.3",
		})
		self.assertRaises(frappe.ValidationError, mismatched_bc.insert)

		# ATURAN 5: BC 2.6.2 WAJIB ada Ex BC 2.6.1 asal
		bc262_in = make_bc_inbound_from_po(po_name, doc_type="BC 2.6.2")
		bc262_in.ref_bc_asal = None
		bc262_in.docstatus = 1
		self.assertRaises(frappe.ValidationError, bc262_in.validate_ex_bc_261)

		# Cleanup
		out_bc41.delete()
		out_bc25.delete()
		out_bc30.delete()
		bc40_in.cancel()
		bc40_in.delete()
		bc23_in.cancel()
		bc23_in.delete()
