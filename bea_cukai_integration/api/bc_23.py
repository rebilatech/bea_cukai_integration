import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt as erpnext_make_purchase_receipt

DOC_TYPE_CODE_MAP = {
	"BC 2.3": "23",
	"BC 2.7": "27",
	"BC 4.0": "40",
	"BC 2.6.2": "26",
}


@frappe.whitelist()
def assemble_nomor_aju(doc_type="BC 2.3", tgl_aju=None, no_urut=None, with_hyphen=None):
	"""
	Merakit 26 digit Nomor Aju dari acuan:
	1. kode_kantor (Master Bea Cukai Settings - hanya IT/Admin)
	2. doc_type (Select Dokumen: BC 2.3 -> 23)
	3. kode_perusahaan (Master Bea Cukai Settings - hanya IT/Admin)
	4. tgl_aju (Date) -> YYYYMMDD
	5. no_urut (6 digit yang dapat diedit oleh user)
	"""
	settings = frappe.get_single("Bea Cukai Settings")
	kode_kantor = (settings.kode_kantor or "0403").strip()[:4].zfill(4)
	doc_code = DOC_TYPE_CODE_MAP.get(doc_type, "23")[:2].zfill(2)
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
def generate_nomor_aju(doc_type="BC 2.3", tgl_aju=None, with_hyphen=None):
	"""
	Menghasilkan 26 digit Nomor Aju pabean resmi (DJBC / CEISA 4.0)
	"""
	return assemble_nomor_aju(doc_type=doc_type, tgl_aju=tgl_aju, no_urut=None, with_hyphen=with_hyphen)["no_aju"]
@frappe.whitelist()
def get_current_doc_type_sequence(doc_type="BC 2.3", tgl_aju=None):
	"""
	Melihat nomor urut terakhir yang sedang berjalan untuk jenis dokumen ini pada tanggal tertentu
	"""
	if not tgl_aju:
		tgl_aju = nowdate()
	date_str = getdate(tgl_aju).strftime("%Y%m%d")
	doc_code = DOC_TYPE_CODE_MAP.get(doc_type, "23")[:2].zfill(2)
	series_name = f"NOAJU{doc_code}{date_str}"
	res = frappe.db.sql("SELECT current FROM `tabSeries` WHERE name = %s", series_name)
	current = res[0][0] if res and res[0] else 0
	return {
		"doc_type": doc_type,
		"doc_code": doc_code,
		"date": date_str,
		"current_sequence": int(current),
		"next_sequence": int(current) + 1,
		"next_no_urut": str(int(current) + 1).zfill(6),
	}


@frappe.whitelist()
def parse_and_validate_no_aju(no_aju):
	"""
	Memeriksa dan membedah format 26 digit Nomor Aju Bea Cukai:
	- 4 digit: Kode Kantor Pabean
	- 2 digit: Kode Dokumen
	- 6 digit: Kode Perusahaan
	- 8 digit: Tanggal (YYYYMMDD)
	- 6 digit: Nomor Urut
	"""
	from datetime import datetime

	if not no_aju:
		return {
			"is_valid": False,
			"message": _("Nomor Aju masih kosong."),
		}

	clean_no = str(no_aju).replace("-", "").replace(" ", "").strip()
	length = len(clean_no)
	if length != 26:
		return {
			"is_valid": False,
			"clean_no": clean_no,
			"length": length,
			"message": _("Nomor Aju harus terdiri dari 26 karakter (saat ini {0} karakter).").format(length),
		}

	kode_kantor = clean_no[0:4]
	kode_dok = clean_no[4:6]
	kode_pers = clean_no[6:12]
	tgl_str = clean_no[12:20]
	no_urut = clean_no[20:26]

	try:
		date_obj = datetime.strptime(tgl_str, "%Y%m%d")
		tgl_formatted = date_obj.strftime("%d-%m-%Y")
	except Exception:
		return {
			"is_valid": False,
			"clean_no": clean_no,
			"message": _("Segmen tanggal '{0}' tidak valid (harus format YYYYMMDD).").format(tgl_str),
		}

	settings = frappe.get_single("Bea Cukai Settings")
	nama_kantor = settings.nama_kantor if settings.kode_kantor == kode_kantor else f"KPPBC {kode_kantor}"
	doc_type_name = (
		"BC 2.3"
		if kode_dok == "23"
		else ("BC 2.7" if kode_dok == "27" else ("BC 4.0" if kode_dok == "40" else f"BC {kode_dok}"))
	)

	return {
		"is_valid": True,
		"clean_no": clean_no,
		"length": 26,
		"kode_kantor": kode_kantor,
		"nama_kantor": nama_kantor,
		"kode_dokumen": kode_dok,
		"doc_type_name": doc_type_name,
		"kode_perusahaan": kode_pers,
		"tanggal_aju": tgl_formatted,
		"tanggal_raw": tgl_str,
		"nomor_urut": no_urut,
		"formatted": f"{kode_kantor}{kode_dok}-{kode_pers}-{tgl_str}-{no_urut}",
		"tracking_url": f"https://www.beacukai.go.id/tracking?noaju={clean_no}",
	}
@frappe.whitelist()
def make_bc_inbound_from_po(source_name, doc_type="BC 2.3", target_doc=None):
	"""
	Membuat draft dokumen pabean pemasukan dari Purchase Order di UI:
	- BC 2.3 (Impor)
	- BC 4.0 (Pemasukan Lokal TLDDP)
	- BC 2.7 (Pemasukan Antar TPB/KB)
	- BC 2.6.2 (Pemasukan Kembali setelah Perbaikan/Subkontrak)
	"""
	po = frappe.get_doc("Purchase Order", source_name)
	if po.docstatus != 1:
		frappe.throw(_("Purchase Order {0} harus dalam status Submitted").format(source_name))

	valid_types = ["BC 2.3", "BC 4.0", "BC 2.7", "BC 2.6.2"]
	if doc_type not in valid_types:
		frappe.throw(_("Jenis dokumen {0} tidak valid. Pilihan: {1}").format(doc_type, ", ".join(valid_types)))

	bc = frappe.new_doc("BC_23_Declaration")
	bc.erp_bc_reference = po.name
	bc.doc_type = doc_type
	bc.tgl_aju = nowdate()
	settings = frappe.get_single("Bea Cukai Settings")
	if settings.auto_generate_no_aju:
		assembled = assemble_nomor_aju(bc.doc_type, bc.tgl_aju)
		bc.no_urut = assembled["no_urut"]
		bc.no_aju = assembled["no_aju"]
	bc.supplier_name = po.supplier_name or po.supplier
	bc.currency = po.currency

	has_bc_items = any(
		frappe.db.get_value("Item", item.item_code, "custom_is_bc") for item in po.items if item.item_code
	)

	total_cif = 0.0
	for item in po.items:
		is_bc = frappe.db.get_value("Item", item.item_code, "custom_is_bc")
		if has_bc_items and not is_bc:
			continue

		pending_qty = flt(item.qty) - flt(item.received_qty)
		qty_to_declare = pending_qty if pending_qty > 0 else flt(item.qty)
		row_amount = qty_to_declare * flt(item.rate)
		total_cif += row_amount

		conversion_rate = flt(po.conversion_rate or 1.0)
		base_rate = flt(item.base_rate or (flt(item.rate) * conversion_rate))
		base_amount = row_amount * conversion_rate
		schedule_date = item.schedule_date or po.schedule_date or nowdate()

		bc.append("detail_item", {
			"item_code": item.item_code,
			"item_name": item.item_name,
			"description": item.description,
			"qty": qty_to_declare,
			"uom": item.uom,
			"stock_uom": item.stock_uom or item.uom,
			"conversion_factor": item.conversion_factor or 1.0,
			"stock_qty": qty_to_declare * flt(item.conversion_factor or 1.0),
			"rate": flt(item.rate),
			"amount": row_amount,
			"base_rate": base_rate,
			"base_amount": base_amount,
			"schedule_date": schedule_date,
			"warehouse": item.warehouse,
		})

	bc.cif_value = total_cif
	return bc


@frappe.whitelist()
def make_bc_23_from_po(source_name, target_doc=None):
	return make_bc_inbound_from_po(source_name, doc_type="BC 2.3", target_doc=target_doc)

@frappe.whitelist()
def make_purchase_receipt_from_bc(source_name, target_doc=None):
	"""
	Dipanggil dari BC_23_Declaration untuk membuat draft Purchase Receipt di UI
	"""
	bc = frappe.get_doc("BC_23_Declaration", source_name)
	if bc.docstatus != 1:
		frappe.throw(_("Dokumen Bea Cukai {0} harus di-submit terlebih dahulu sebelum dibuatkan Purchase Receipt").format(source_name))

	if not bc.erp_bc_reference:
		frappe.throw(_("Dokumen Bea Cukai {0} tidak memiliki referensi Purchase Order").format(source_name))

	# Buat Purchase Receipt dari PO referensi menggunakan helper standar ERPNext
	pr = erpnext_make_purchase_receipt(bc.erp_bc_reference)

	# Tautkan referensi dokumen Bea Cukai
	pr.custom_bc_declaration = bc.name
	pr.custom_bc_doc_type = bc.doc_type or "BC 2.3"
	pr.custom_bc_no_aju = str(bc.no_aju or "")
	pr.custom_bc_tgl_aju = bc.tgl_aju
	pr.custom_bc_no_daftar = bc.no_daftar
	pr.custom_bc_tgl_daftar = bc.tgl_daftar

	# Sesuaikan kuantitas item dengan yang dideklarasikan di BC 2.3
	bc_item_qtys = {}
	for item in bc.detail_item:
		if item.item_code:
			bc_item_qtys[item.item_code] = flt(item.qty)

	matched_items = []
	for pr_item in pr.items:
		# Ambil HS Code dari master Item jika tersedia
		hs_code = frappe.db.get_value("Item", pr_item.item_code, "custom_hs_code")
		if hs_code:
			pr_item.custom_hs_code = hs_code

		if pr_item.item_code in bc_item_qtys:
			declared_qty = bc_item_qtys[pr_item.item_code]
			pr_item.qty = declared_qty
			pr_item.stock_qty = declared_qty * flt(pr_item.conversion_factor or 1.0)
			pr_item.amount = declared_qty * flt(pr_item.rate)
			pr_item.base_amount = pr_item.amount * flt(pr.conversion_rate or 1.0)
			matched_items.append(pr_item)

	if matched_items:
		pr.items = matched_items

	return pr


@frappe.whitelist(methods=["POST"])
def api_create_inbound_bc():
	"""
	REST API Endpoint terpadu untuk semua dokumen pemasukan pabean:
	- BC 2.3 (Impor)
	- BC 4.0 (Pemasukan Lokal TLDDP)
	- BC 2.7 (Pemasukan Antar TPB/KB)
	- BC 2.6.2 (Pemasukan Kembali Perbaikan/Subkontrak)
	"""
	data = frappe.request.get_json() if frappe.request and frappe.request.data else frappe.form_dict
	if isinstance(data, str):
		data = json.loads(data)

	po_name = data.get("purchase_order") or data.get("erp_bc_reference")
	if not po_name:
		frappe.throw(_("Parameter 'purchase_order' wajib diisi"), exc=frappe.MandatoryError)

	po = frappe.get_doc("Purchase Order", po_name)
	if po.docstatus != 1:
		frappe.throw(_("Purchase Order {0} belum di-submit").format(po_name))

	doc_type = data.get("doc_type", "BC 2.3")
	bc = frappe.new_doc("BC_23_Declaration")
	bc.erp_bc_reference = po.name
	bc.doc_type = doc_type
	bc.tgl_aju = data.get("tgl_aju") or nowdate()

	# Field spesifik per jenis dokumen
	bc.no_faktur_pajak = data.get("no_faktur_pajak")
	bc.tgl_faktur_pajak = data.get("tgl_faktur_pajak")
	bc.tpb_asal = data.get("tpb_asal")
	bc.ref_bc_asal = data.get("ref_bc_asal")
	bc.tgl_bc_asal = data.get("tgl_bc_asal")

	settings = frappe.get_single("Bea Cukai Settings")
	if data.get("no_urut"):
		bc.no_urut = str(data.get("no_urut"))
	if data.get("no_aju"):
		bc.no_aju = str(data.get("no_aju"))
	elif settings.auto_generate_no_aju:
		assembled = assemble_nomor_aju(bc.doc_type, bc.tgl_aju, bc.no_urut)
		bc.no_urut = assembled["no_urut"]
		bc.no_aju = assembled["no_aju"]
	else:
		bc.no_aju = ""
	bc.no_daftar = data.get("no_daftar")
	bc.tgl_daftar = data.get("tgl_daftar")
	bc.supplier_name = data.get("supplier_name") or po.supplier_name or po.supplier
	bc.currency = data.get("currency") or po.currency

	bc.uom_name = data.get("uom_name")
	bc.qty_pack = int(data.get("qty_pack") or 0)
	bc.freight = flt(data.get("freight") or 0)
	bc.bruto = flt(data.get("bruto") or 0)
	bc.bm = flt(data.get("bm") or 0)
	bc.ppn = flt(data.get("ppn") or 0)
	bc.ppn_bm = flt(data.get("ppn_bm") or 0)

	if data.get("json_payload"):
		bc.json_payload = (
			json.dumps(data.get("json_payload"), indent=2)
			if isinstance(data.get("json_payload"), (dict, list))
			else str(data.get("json_payload"))
		)

	# Items: jika di-specify di payload, gunakan itu; jika tidak, tarik dari PO
	custom_items = data.get("items")
	total_cif = 0.0

	if custom_items and isinstance(custom_items, list):
		po_items_map = {item.item_code: item for item in po.items}
		for c_item in custom_items:
			item_code = c_item.get("item_code")
			ref_po_item = po_items_map.get(item_code)
			qty = flt(c_item.get("qty"))
			rate = flt(c_item.get("rate") or (ref_po_item.rate if ref_po_item else 0))
			amount = qty * rate
			total_cif += amount

			conversion_rate = flt(po.conversion_rate or 1.0)
			base_rate = flt(c_item.get("base_rate") or (rate * conversion_rate))
			base_amount = amount * conversion_rate
			schedule_date = c_item.get("schedule_date") or (ref_po_item.schedule_date if ref_po_item else None) or nowdate()
			uom = c_item.get("uom") or (ref_po_item.uom if ref_po_item else "Nos")
			stock_uom = c_item.get("stock_uom") or (ref_po_item.stock_uom if ref_po_item else uom)
			conv_factor = flt(c_item.get("conversion_factor") or (ref_po_item.conversion_factor if ref_po_item else 1.0))

			bc.append("detail_item", {
				"item_code": item_code,
				"item_name": c_item.get("item_name") or (ref_po_item.item_name if ref_po_item else item_code),
				"qty": qty,
				"uom": uom,
				"stock_uom": stock_uom,
				"conversion_factor": conv_factor,
				"stock_qty": qty * conv_factor,
				"rate": rate,
				"amount": amount,
				"base_rate": base_rate,
				"base_amount": base_amount,
				"schedule_date": schedule_date,
				"warehouse": c_item.get("warehouse") or (ref_po_item.warehouse if ref_po_item else ""),
			})
	else:
		has_bc_items = any(
			frappe.db.get_value("Item", item.item_code, "custom_is_bc") for item in po.items if item.item_code
		)
		for item in po.items:
			is_bc = frappe.db.get_value("Item", item.item_code, "custom_is_bc")
			if has_bc_items and not is_bc:
				continue

			pending_qty = flt(item.qty) - flt(item.received_qty)
			qty = pending_qty if pending_qty > 0 else flt(item.qty)
			amount = qty * flt(item.rate)
			total_cif += amount
			conversion_rate = flt(po.conversion_rate or 1.0)
			base_rate = flt(item.base_rate or (flt(item.rate) * conversion_rate))
			base_amount = amount * conversion_rate
			schedule_date = item.schedule_date or po.schedule_date or nowdate()

			bc.append("detail_item", {
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": qty,
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": item.conversion_factor or 1.0,
				"stock_qty": qty * flt(item.conversion_factor or 1.0),
				"rate": flt(item.rate),
				"amount": amount,
				"base_rate": base_rate,
				"base_amount": base_amount,
				"schedule_date": schedule_date,
				"warehouse": item.warehouse,
			})

	bc.cif_value = flt(data.get("cif_value")) or total_cif

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
			"erp_bc_reference": bc.erp_bc_reference,
			"cif_value": bc.cif_value,
		}
	}


@frappe.whitelist(methods=["POST"])
def api_create_bc_23():
	"""REST API Endpoint khusus BC 2.3 (Pemasukan Impor)"""
	frappe.form_dict.setdefault("doc_type", "BC 2.3")
	return api_create_inbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_40():
	"""REST API Endpoint khusus BC 4.0 (Pemasukan Lokal TLDDP)"""
	frappe.form_dict["doc_type"] = "BC 4.0"
	return api_create_inbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_27():
	"""REST API Endpoint khusus BC 2.7 (Pemasukan Antar TPB / Kawasan Berikat)"""
	frappe.form_dict["doc_type"] = "BC 2.7"
	return api_create_inbound_bc()


@frappe.whitelist(methods=["POST"])
def api_create_bc_262():
	"""REST API Endpoint khusus BC 2.6.2 (Pemasukan Kembali setelah Perbaikan/Subkontrak)"""
	frappe.form_dict["doc_type"] = "BC 2.6.2"
	return api_create_inbound_bc()


@frappe.whitelist(methods=["POST"])
def api_make_purchase_receipt():
	"""
	REST API Endpoint: POST /api/method/bea_cukai_integration.api.bc_23.api_make_purchase_receipt
	Menerima bc_name untuk men-generate Purchase Receipt dari BC 2.3.
	"""
	data = frappe.request.get_json() if frappe.request and frappe.request.data else frappe.form_dict
	if isinstance(data, str):
		data = json.loads(data)

	bc_name = data.get("bc_name") or data.get("name")
	if not bc_name:
		frappe.throw(_("Parameter 'bc_name' wajib diisi"), exc=frappe.MandatoryError)

	pr = make_purchase_receipt_from_bc(bc_name)
	pr.insert(ignore_permissions=True)

	if data.get("submit"):
		pr.submit()

	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Purchase Receipt {0} berhasil dibuat dari {1}").format(pr.name, bc_name),
		"data": {
			"purchase_receipt": pr.name,
			"docstatus": pr.docstatus,
			"purchase_order": pr.custom_bc_declaration,
			"grand_total": pr.grand_total,
		}
	}


@frappe.whitelist()
def generate_ceisa_payload(bc_name):
	"""
	Menghasilkan format JSON CEISA 4.0 Bea Cukai untuk semua dokumen pemasukan:
	- BC 2.3: kodeDokumen 23 (Impor)
	- BC 4.0: kodeDokumen 40 (Lokal TLDDP)
	- BC 2.7: kodeDokumen 27 (Antar TPB)
	- BC 2.6.2: kodeDokumen 262 (Kembali Perbaikan)
	"""
	bc = frappe.get_doc("BC_23_Declaration", bc_name) if isinstance(bc_name, str) else bc_name
	po = frappe.get_doc("Purchase Order", bc.erp_bc_reference) if bc.erp_bc_reference else None
	settings = frappe.get_single("Bea Cukai Settings")

	ceisa_doc_code = "23"
	if bc.doc_type == "BC 4.0":
		ceisa_doc_code = "40"
	elif bc.doc_type == "BC 2.7":
		ceisa_doc_code = "27"
	elif bc.doc_type == "BC 2.6.2":
		ceisa_doc_code = "262"

	barang_list = []
	for idx, item in enumerate(bc.detail_item, start=1):
		hs_code = frappe.db.get_value("Item", item.item_code, "custom_hs_code") or ""
		barang_list.append({
			"seriBarang": idx,
			"kodeBarang": item.item_code,
			"uraian": item.item_name or item.item_code,
			"posTarif": hs_code,
			"jumlahSatuan": flt(item.qty),
			"kodeSatuanBarang": item.uom or "PCE",
			"hargaPenyerahan": flt(item.amount),
			"cif": flt(item.amount),
		})

	dokumen_tambahan = []
	if bc.doc_type == "BC 4.0" and bc.no_faktur_pajak:
		dokumen_tambahan.append({
			"kodeDokumen": "380",  # Faktur Pajak
			"nomorDokumen": bc.no_faktur_pajak,
			"tanggalDokumen": str(bc.tgl_faktur_pajak or bc.tgl_aju),
		})
	elif bc.doc_type == "BC 2.6.2" and bc.ref_bc_asal:
		dokumen_tambahan.append({
			"kodeDokumen": "261",  # BC 2.6.1 Asal
			"nomorDokumen": bc.ref_bc_asal,
			"tanggalDokumen": str(bc.tgl_bc_asal or bc.tgl_aju),
		})

	entitas_list = [
		{
			"kodeEntitas": "1",  # Pengusaha TPB / Penerima
			"namaEntitas": po.company if po else (settings.nama_perusahaan or ""),
			"nomorIdentitas": settings.npwp_perusahaan or "",
		},
		{
			"kodeEntitas": "2",  # Pengirim / Pemasok
			"namaEntitas": bc.tpb_asal if (bc.doc_type == "BC 2.7" and bc.tpb_asal) else (bc.supplier_name or ""),
		}
	]

	payload = {
		"nomorAju": bc.no_aju or "",
		"tanggalAju": str(bc.tgl_aju or ""),
		"kodeDokumen": ceisa_doc_code,
		"kodeKantor": settings.kode_kantor or "0403",
		"entitas": entitas_list,
		"pungutan": {
			"nilaiCif": flt(bc.cif_value),
			"beaMasuk": flt(bc.bm),
			"ppn": flt(bc.ppn),
			"ppnBm": flt(bc.ppn_bm),
		},
		"dokumen": dokumen_tambahan,
		"barang": barang_list,
	}

	bc.json_payload = json.dumps(payload, indent=2)
	bc.save(ignore_permissions=True)
	return payload


def validate_purchase_receipt_bc_requirement(doc, method=None):
	"""
	Penegakan alur penerimaan barang:
	1. Jika Purchase Receipt sudah memiliki tautan BC (custom_bc_declaration), lolos validasi.
	2. Jika dibuat langsung tanpa dokumen BC, periksa apakah ada item yang bertanda 'Is BC' (custom_is_bc = 1).
	3. Jika ada item 'Is BC', tolak pembuatan Purchase Receipt langsung dan wajibkan dokumen BC.
	4. Jika semua item bukan BC (custom_is_bc = 0), penerimaan barang berjalan normal tanpa dokumen BC.
	"""
	if doc.custom_bc_declaration:
		return

	bc_items = []
	for item in doc.items:
		if not item.item_code:
			continue
		is_bc = frappe.db.get_value("Item", item.item_code, "custom_is_bc")
		if is_bc:
			bc_items.append(f"{item.item_code} ({item.item_name or ''})")

	if bc_items:
		bullet_list = "<br>• " + "<br>• ".join(bc_items)
		frappe.throw(
			_(
				"Penerimaan barang tidak dapat diproses langsung.<br>"
				"Item berikut terdaftar sebagai <b>Barang Pabean (Is BC)</b> dan <b>WAJIB</b> melalui Dokumen Bea Cukai (BC 2.3) terlebih dahulu:{0}<br><br>"
				"Silakan buat dokumen <b>BC 2.3 Declaration</b> dari Purchase Order terkait, lalu tarik menjadi Purchase Receipt."
			).format(bullet_list),
			title=_("Wajib Dokumen Pabean (BC)"),
		)
