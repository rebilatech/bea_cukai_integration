import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate


OUTBOUND_DOC_TYPE_CODE_MAP = {
	"BC 3.0": "30",
	"BC 2.5": "25",
	"BC 2.7 Keluar": "27",
	"BC 2.6.1": "26",
	"BC 4.1": "41",
}


@frappe.whitelist()
def assemble_outbound_nomor_aju(doc_type="BC 3.0", tgl_aju=None, no_urut=None, with_hyphen=None):
	"""
	Merakit 26 digit Nomor Aju pengeluaran pabean resmi (DJBC / CEISA 4.0):
	Format: KKKK (4 digit Kantor) + DD (2 digit Dokumen) + EEEEEE (6 digit Perusahaan) + YYYYMMDD (8 digit Tanggal) + SSSSSS (6 digit Urut)
	"""
	settings = frappe.get_single("Bea Cukai Settings")
	kode_kantor = (settings.kode_kantor or "0403").strip()[:4].zfill(4)
	doc_code = OUTBOUND_DOC_TYPE_CODE_MAP.get(doc_type, "30")[:2].zfill(2)
	kode_perusahaan = (settings.kode_perusahaan or "000001").strip()[:6].zfill(6)

	if not tgl_aju:
		tgl_aju = nowdate()
	date_obj = getdate(tgl_aju)
	date_str = date_obj.strftime("%Y%m%d")

	if not no_urut:
		series_key = f"NOAJU.{doc_code}.{date_str}..######"
		raw_series = str(frappe.model.naming.make_autoname(series_key))
		clean_urut = raw_series[-6:].zfill(6)
	else:
		digits_only = "".join(filter(str.isdigit, str(no_urut)))
		clean_urut = digits_only[:6].zfill(6) if digits_only else "000001"

	if with_hyphen is None:
		with_hyphen = bool(settings.no_aju_with_hyphen)

	if with_hyphen:
		no_aju = f"{kode_kantor}{doc_code}-{kode_perusahaan}-{date_str}-{clean_urut}"
	else:
		no_aju = f"{kode_kantor}{doc_code}{kode_perusahaan}{date_str}{clean_urut}"

	return {
		"no_urut": clean_urut,
		"no_aju": no_aju,
	}


@frappe.whitelist()
def get_inbound_history_for_item(item_code):
	"""
	Mencari riwayat dokumen pemasukan pabean untuk suatu item.
	Menelusuri dari BC_23_Declaration dan Purchase Receipt Item.
	Mengembalikan list riwayat pemasukan beserta No PO, No BC, Tanggal, dan Harga Perolehan.
	"""
	if not item_code:
		return []

	results = []

	# 1. Cari dari detail item BC_23_Declaration yang telah submitted atau disimpan
	bc_inbounds = frappe.db.sql(
		"""
		SELECT 
			b.name AS bc_declaration,
			b.doc_type,
			b.no_aju,
			b.tgl_aju,
			b.no_daftar,
			b.tgl_daftar,
			b.erp_bc_reference AS po_reference,
			b.currency,
			i.rate,
			i.amount,
			b.supplier_name
		FROM `tabBC_23_Declaration` b
		INNER JOIN `tabPurchase Order Item` i ON i.parent = b.name AND i.parenttype = 'BC_23_Declaration'
		WHERE i.item_code = %s
		ORDER BY b.creation DESC
		LIMIT 10
		""",
		(item_code,),
		as_dict=True,
	)

	for row in bc_inbounds:
		results.append({
			"bc_declaration": row.bc_declaration,
			"doc_type": row.doc_type,
			"no_aju": row.no_aju,
			"tgl_aju": str(row.tgl_aju or ""),
			"no_daftar": row.no_daftar or "",
			"tgl_daftar": str(row.tgl_daftar or ""),
			"po_reference": row.po_reference or "",
			"rate": flt(row.rate),
			"currency": row.currency or "IDR",
			"cif_amount": flt(row.amount),
			"supplier_name": row.supplier_name or "",
		})

	# 2. Jika tidak ada di detail_item langsung, cari dari Purchase Receipt yang memiliki referensi BC
	if not results:
		pr_items = frappe.db.sql(
			"""
			SELECT 
				pr.custom_bc_declaration AS bc_declaration,
				pr.custom_bc_doc_type AS doc_type,
				pr.custom_bc_no_aju AS no_aju,
				pr.custom_bc_tgl_aju AS tgl_aju,
				pr.custom_bc_no_daftar AS no_daftar,
				pr.custom_bc_tgl_daftar AS tgl_daftar,
				pri.purchase_order AS po_reference,
				pr.currency,
				pri.rate,
				pri.amount,
				pr.supplier_name
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE pri.item_code = %s AND pr.docstatus = 1 AND pr.custom_bc_declaration IS NOT NULL
			ORDER BY pr.creation DESC
			LIMIT 10
			""",
			(item_code,),
			as_dict=True,
		)

		for row in pr_items:
			results.append({
				"bc_declaration": row.bc_declaration,
				"doc_type": row.doc_type or "BC 2.3",
				"no_aju": row.no_aju or "",
				"tgl_aju": str(row.tgl_aju or ""),
				"no_daftar": row.no_daftar or "",
				"tgl_daftar": str(row.tgl_daftar or ""),
				"po_reference": row.po_reference or "",
				"rate": flt(row.rate),
				"currency": row.currency or "IDR",
				"cif_amount": flt(row.amount),
				"supplier_name": row.supplier_name or "",
			})

	return results


@frappe.whitelist()
def make_bc_outbound_from_sales_order(source_name, doc_type="BC 3.0", target_doc=None):
	"""
	Membuat draft dokumen pengeluaran Bea Cukai dari Sales Order di UI.
	Otomatis menelusuri dan melekatkan riwayat dokumen masuk per baris item.
	"""
	so = frappe.get_doc("Sales Order", source_name)
	if so.docstatus != 1:
		frappe.throw(_("Sales Order {0} harus dalam status Submitted").format(source_name))

	bc = frappe.new_doc("BC_Outbound_Declaration")
	bc.sales_order_ref = so.name
	bc.doc_type = doc_type
	bc.tgl_aju = nowdate()
	bc.customer_name = so.customer_name or so.customer
	bc.currency = so.currency

	settings = frappe.get_single("Bea Cukai Settings")
	if settings.auto_generate_no_aju:
		assembled = assemble_outbound_nomor_aju(bc.doc_type, bc.tgl_aju)
		bc.no_urut = assembled["no_urut"]
		bc.no_aju = assembled["no_aju"]

	total_out = 0.0
	for item in so.items:
		qty_out = flt(item.qty) - flt(item.delivered_qty)
		qty_out = qty_out if qty_out > 0 else flt(item.qty)
		row_amount = qty_out * flt(item.rate)
		total_out += row_amount

		# Cari riwayat dokumen masuk untuk item ini
		inbound_list = get_inbound_history_for_item(item.item_code)
		latest_inbound = inbound_list[0] if inbound_list else {}

		hs_code = frappe.db.get_value("Item", item.item_code, "custom_hs_code") or ""

		bc.append("items", {
			"item_code": item.item_code,
			"item_name": item.item_name,
			"hs_code": hs_code,
			"qty": qty_out,
			"uom": item.uom,
			"rate": flt(item.rate),
			"amount": row_amount,
			# Pelekatan History Dokumen Masuk Asal
			"inbound_bc_declaration": latest_inbound.get("bc_declaration"),
			"inbound_bc_type": latest_inbound.get("doc_type"),
			"inbound_no_aju": latest_inbound.get("no_aju"),
			"inbound_tgl_aju": latest_inbound.get("tgl_aju"),
			"inbound_no_daftar": latest_inbound.get("no_daftar"),
			"inbound_tgl_daftar": latest_inbound.get("tgl_daftar"),
			"inbound_po_reference": latest_inbound.get("po_reference"),
			"inbound_item_rate": flt(latest_inbound.get("rate") or 0),
			"inbound_currency": latest_inbound.get("currency"),
			"inbound_cif_amount": flt(latest_inbound.get("cif_amount") or 0),
		})

	bc.total_amount = total_out
	return bc


@frappe.whitelist()
def make_bc_outbound_from_delivery_note(source_name, doc_type="BC 3.0", target_doc=None):
	"""
	Membuat draft dokumen pengeluaran Bea Cukai dari Delivery Note di UI.
	"""
	dn = frappe.get_doc("Delivery Note", source_name)
	if dn.docstatus != 1:
		frappe.throw(_("Delivery Note {0} harus dalam status Submitted").format(source_name))

	bc = frappe.new_doc("BC_Outbound_Declaration")
	bc.delivery_note_ref = dn.name
	bc.doc_type = doc_type
	bc.tgl_aju = nowdate()
	bc.customer_name = dn.customer_name or dn.customer
	bc.currency = dn.currency

	settings = frappe.get_single("Bea Cukai Settings")
	if settings.auto_generate_no_aju:
		assembled = assemble_outbound_nomor_aju(bc.doc_type, bc.tgl_aju)
		bc.no_urut = assembled["no_urut"]
		bc.no_aju = assembled["no_aju"]

	total_out = 0.0
	for item in dn.items:
		qty_out = flt(item.qty)
		row_amount = flt(item.amount) or (qty_out * flt(item.rate))
		total_out += row_amount

		inbound_list = get_inbound_history_for_item(item.item_code)
		latest_inbound = inbound_list[0] if inbound_list else {}
		hs_code = frappe.db.get_value("Item", item.item_code, "custom_hs_code") or ""

		bc.append("items", {
			"item_code": item.item_code,
			"item_name": item.item_name,
			"hs_code": hs_code,
			"qty": qty_out,
			"uom": item.uom,
			"rate": flt(item.rate),
			"amount": row_amount,
			# History Dokumen Masuk Asal
			"inbound_bc_declaration": latest_inbound.get("bc_declaration"),
			"inbound_bc_type": latest_inbound.get("doc_type"),
			"inbound_no_aju": latest_inbound.get("no_aju"),
			"inbound_tgl_aju": latest_inbound.get("tgl_aju"),
			"inbound_no_daftar": latest_inbound.get("no_daftar"),
			"inbound_tgl_daftar": latest_inbound.get("tgl_daftar"),
			"inbound_po_reference": latest_inbound.get("po_reference"),
			"inbound_item_rate": flt(latest_inbound.get("rate") or 0),
			"inbound_currency": latest_inbound.get("currency"),
			"inbound_cif_amount": flt(latest_inbound.get("cif_amount") or 0),
		})

	bc.total_amount = total_out
	return bc


@frappe.whitelist(methods=["POST"])
def api_create_outbound_bc():
	"""
	REST API Endpoint terpadu untuk membuat dokumen pengeluaran pabean:
	- BC 3.0 (Ekspor)
	- BC 2.5 (Pengeluaran Lokal TLDDP)
	- BC 2.7 Keluar (Antar TPB)
	- BC 2.6.1 (Keluar Sementara Subkontrak/Perbaikan)
	- BC 4.1 (Pengeluaran Hasil Olahan Bahan Baku Lokal)
	"""
	data = frappe.request.get_json() if frappe.request and frappe.request.data else frappe.form_dict
	if isinstance(data, str):
		data = json.loads(data)

	doc_type = data.get("doc_type", "BC 3.0")
	bc = frappe.new_doc("BC_Outbound_Declaration")
	bc.doc_type = doc_type
	bc.sales_order_ref = data.get("sales_order_ref") or data.get("sales_order")
	bc.delivery_note_ref = data.get("delivery_note_ref") or data.get("delivery_note")
	bc.tgl_aju = data.get("tgl_aju") or nowdate()
	bc.customer_name = data.get("customer_name")
	bc.currency = data.get("currency", "USD")

	# Field-field spesifik pengeluaran
	bc.country_destination = data.get("country_destination")
	bc.pelabuhan_muat = data.get("pelabuhan_muat")
	bc.pelabuhan_bongkar = data.get("pelabuhan_bongkar")
	bc.no_faktur_pajak = data.get("no_faktur_pajak")
	bc.tgl_faktur_pajak = data.get("tgl_faktur_pajak")
	bc.tpb_tujuan = data.get("tpb_tujuan")
	bc.alasan_pengeluaran = data.get("alasan_pengeluaran")
	bc.perkiraan_tgl_kembali = data.get("perkiraan_tgl_kembali")

	settings = frappe.get_single("Bea Cukai Settings")
	if data.get("no_urut"):
		bc.no_urut = str(data.get("no_urut"))
	if data.get("no_aju"):
		bc.no_aju = str(data.get("no_aju"))
	elif settings.auto_generate_no_aju:
		assembled = assemble_outbound_nomor_aju(bc.doc_type, bc.tgl_aju, bc.no_urut)
		bc.no_urut = assembled["no_urut"]
		bc.no_aju = assembled["no_aju"]
	else:
		bc.no_aju = ""

	bc.no_daftar = data.get("no_daftar")
	bc.tgl_daftar = data.get("tgl_daftar")
	bc.freight = flt(data.get("freight") or 0)
	bc.asuransi = flt(data.get("asuransi") or 0)
	bc.bruto = flt(data.get("bruto") or 0)
	bc.netto = flt(data.get("netto") or 0)
	bc.qty_pack = int(data.get("qty_pack") or 0)
	bc.uom_name = data.get("uom_name")

	items_data = data.get("items") or []
	total_amount = 0.0

	for item_dict in items_data:
		item_code = item_dict.get("item_code")
		qty = flt(item_dict.get("qty") or 1)
		rate = flt(item_dict.get("rate") or 0)
		amount = qty * rate
		total_amount += amount

		# Cari inbound history jika tidak disuplai di payload
		inbound_ref = item_dict.get("inbound_bc_declaration")
		inbound_po = item_dict.get("inbound_po_reference")
		inbound_rate = flt(item_dict.get("inbound_item_rate") or 0)

		if not inbound_ref:
			inbound_hist = get_inbound_history_for_item(item_code)
			if inbound_hist:
				inbound_ref = inbound_hist[0].get("bc_declaration")
				inbound_po = inbound_hist[0].get("po_reference")
				inbound_rate = inbound_hist[0].get("rate")

		hs_code = item_dict.get("hs_code") or (frappe.db.get_value("Item", item_code, "custom_hs_code") or "")

		bc.append("items", {
			"item_code": item_code,
			"item_name": item_dict.get("item_name") or frappe.db.get_value("Item", item_code, "item_name"),
			"hs_code": hs_code,
			"qty": qty,
			"uom": item_dict.get("uom") or (frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"),
			"rate": rate,
			"amount": amount,
			# History Dokumen Masuk
			"inbound_bc_declaration": inbound_ref,
			"inbound_no_aju": item_dict.get("inbound_no_aju"),
			"inbound_tgl_aju": item_dict.get("inbound_tgl_aju"),
			"inbound_no_daftar": item_dict.get("inbound_no_daftar"),
			"inbound_po_reference": inbound_po,
			"inbound_item_rate": inbound_rate,
			"inbound_currency": item_dict.get("inbound_currency"),
		})

	bc.total_amount = total_amount
	bc.insert(ignore_permissions=True)

	if data.get("submit"):
		bc.submit()

	frappe.db.commit()

	return {
		"status": "success",
		"message": _("{0} Declaration {1} berhasil dibuat").format(bc.doc_type, bc.name),
		"data": {
			"name": bc.name,
			"doc_type": bc.doc_type,
			"docstatus": bc.docstatus,
			"no_aju": bc.no_aju,
			"no_urut": bc.no_urut,
			"total_amount": bc.total_amount,
		}
	}


# Dedicated REST endpoints
@frappe.whitelist(methods=["POST"])
def api_create_bc_30():
	"""REST API Khusus BC 3.0 (PEB Ekspor)"""
	frappe.form_dict["doc_type"] = "BC 3.0"
	return api_create_outbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_25():
	"""REST API Khusus BC 2.5 (Pengeluaran Lokal TLDDP)"""
	frappe.form_dict["doc_type"] = "BC 2.5"
	return api_create_outbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_27_out():
	"""REST API Khusus BC 2.7 Keluar (Pengeluaran Antar TPB)"""
	frappe.form_dict["doc_type"] = "BC 2.7 Keluar"
	return api_create_outbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_261():
	"""REST API Khusus BC 2.6.1 (Pengeluaran Sementara Perbaikan/Subkontrak)"""
	frappe.form_dict["doc_type"] = "BC 2.6.1"
	return api_create_outbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_41():
	"""REST API Khusus BC 4.1 (Pengeluaran Hasil Olahan Bahan Baku Lokal)"""
	frappe.form_dict["doc_type"] = "BC 4.1"
	return api_create_outbound_bc()

@frappe.whitelist()
def explode_bom_for_outbound(bc_name):
	"""
	Mendeteksi item barang jadi (Finished Goods) di tabel items yang memiliki BOM,
	lalu mem-breakdown bahan baku penyusunnya dan otomatis menelusuri riwayat dokumen masuknya
	(No PO Asal, No BC Masuk, Harga Perolehan Masuk) ke dalam tabel raw_materials.
	"""
	bc = frappe.get_doc("BC_Outbound_Declaration", bc_name) if isinstance(bc_name, str) else bc_name

	raw_materials_added = []
	bc.raw_materials = []

	for item in bc.items:
		bom_name = frappe.db.get_value("BOM", {"item": item.item_code, "is_active": 1, "is_default": 1}, "name")
		if not bom_name:
			bom_name = frappe.db.get_value("BOM", {"item": item.item_code, "is_active": 1}, "name")

		if bom_name:
			bom = frappe.get_doc("BOM", bom_name)
			bom_qty = flt(bom.quantity) or 1.0
			ratio = flt(item.qty) / bom_qty

			for b_item in bom.items:
				qty_consumed = flt(b_item.qty) * ratio
				inbound_list = get_inbound_history_for_item(b_item.item_code)
				latest_inbound = inbound_list[0] if inbound_list else {}
				hs_code = frappe.db.get_value("Item", b_item.item_code, "custom_hs_code") or ""

				row_dict = {
					"finished_good_item": item.item_code,
					"bom_no": bom_name,
					"raw_material_item": b_item.item_code,
					"raw_material_name": b_item.item_name or b_item.item_code,
					"hs_code": hs_code,
					"qty_consumed": qty_consumed,
					"uom": b_item.uom or b_item.stock_uom,
					"inbound_bc_declaration": latest_inbound.get("bc_declaration"),
					"inbound_bc_type": latest_inbound.get("doc_type"),
					"inbound_no_aju": latest_inbound.get("no_aju"),
					"inbound_tgl_aju": latest_inbound.get("tgl_aju"),
					"inbound_no_daftar": latest_inbound.get("no_daftar"),
					"inbound_po_reference": latest_inbound.get("po_reference"),
					"inbound_item_rate": flt(latest_inbound.get("rate") or 0),
					"inbound_currency": latest_inbound.get("currency"),
					"inbound_cif_amount": qty_consumed * flt(latest_inbound.get("rate") or 0),
				}
				bc.append("raw_materials", row_dict)
				raw_materials_added.append(row_dict)

	if isinstance(bc_name, str):
		bc.save(ignore_permissions=True)
		frappe.db.commit()

	return {
		"count": len(raw_materials_added),
		"raw_materials": raw_materials_added,
	}


@frappe.whitelist()
def generate_outbound_ceisa_payload(bc_name):
	"""
	Menghasilkan skema JSON CEISA 4.0 resmi untuk dokumen pengeluaran kepabeanan
	beserta rincian dokumen asal pabean per itemnya (atau bahan baku jika hasil produksi).
	"""
	bc = frappe.get_doc("BC_Outbound_Declaration", bc_name) if isinstance(bc_name, str) else bc_name
	settings = frappe.get_single("Bea Cukai Settings")

	ceisa_code = "30"
	if bc.doc_type == "BC 2.5":
		ceisa_code = "25"
	elif bc.doc_type == "BC 2.7 Keluar":
		ceisa_code = "27"
	elif bc.doc_type == "BC 2.6.1":
		ceisa_code = "261"
	elif bc.doc_type == "BC 4.1":
		ceisa_code = "41"

	raw_materials_by_fg = {}
	if bc.raw_materials:
		for rm in bc.raw_materials:
			raw_materials_by_fg.setdefault(rm.finished_good_item, []).append({
				"kodeBahanBaku": rm.raw_material_item,
				"uraianBahanBaku": rm.raw_material_name or rm.raw_material_item,
				"posTarif": rm.hs_code or "",
				"jumlahPemakaian": flt(rm.qty_consumed),
				"satuan": rm.uom or "PCE",
				"dokumenAsal": {
					"bcMasuk": rm.inbound_bc_declaration or "",
					"jenisBcMasuk": rm.inbound_bc_type or "",
					"nomorAjuMasuk": rm.inbound_no_aju or "",
					"tanggalAjuMasuk": str(rm.inbound_tgl_aju or ""),
					"nomorDaftarMasuk": rm.inbound_no_daftar or "",
					"noPoAsal": rm.inbound_po_reference or "",
					"hargaSatuanMasuk": flt(rm.inbound_item_rate or 0),
				}
			})

	barang_list = []
	for idx, item in enumerate(bc.items, start=1):
		item_dict = {
			"seriBarang": idx,
			"kodeBarang": item.item_code,
			"uraian": item.item_name or item.item_code,
			"posTarif": item.hs_code or "",
			"jumlahSatuan": flt(item.qty),
			"kodeSatuanBarang": item.uom or "PCE",
			"fob": flt(item.amount),
			"hargaPenyerahan": flt(item.amount),
		}

		# Jika ada bahan baku penyusun dari konversi BOM
		if item.item_code in raw_materials_by_fg:
			item_dict["bahanBaku"] = raw_materials_by_fg[item.item_code]
		elif item.inbound_bc_declaration:
			item_dict["dokumenAsal"] = {
				"bcMasuk": item.inbound_bc_declaration or "",
				"jenisBcMasuk": item.inbound_bc_type or "",
				"nomorAjuMasuk": item.inbound_no_aju or "",
				"tanggalAjuMasuk": str(item.inbound_tgl_aju or ""),
				"nomorDaftarMasuk": item.inbound_no_daftar or "",
				"noPoAsal": item.inbound_po_reference or "",
				"hargaSatuanMasuk": flt(item.inbound_item_rate or 0),
			}

		barang_list.append(item_dict)
	payload = {
		"nomorAju": bc.no_aju or "",
		"tanggalAju": str(bc.tgl_aju or ""),
		"kodeDokumen": ceisa_code,
		"kodeKantor": settings.kode_kantor or "0403",
		"entitas": [
			{
				"kodeEntitas": "1",  # Eksportir / Pengusaha TPB
				"namaEntitas": settings.nama_perusahaan or "",
				"nomorIdentitas": settings.npwp_perusahaan or "",
			},
			{
				"kodeEntitas": "2",  # Penerima / Pembeli / TPB Tujuan
				"namaEntitas": bc.tpb_tujuan if bc.doc_type == "BC 2.7 Keluar" else (bc.customer_name or ""),
			}
		],
		"barang": barang_list,
	}

	bc.json_payload = json.dumps(payload, indent=2)
	bc.save(ignore_permissions=True)
	return payload
