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
def generate_nomor_aju(doc_type="BC 2.3", tgl_aju=None, with_hyphen=None):
	"""
	Menghasilkan 26 digit Nomor Aju pabean resmi (DJBC / CEISA 4.0):
	Format: KKKK (4 digit Kantor) + DD (2 digit Dokumen) + EEEEEE (6 digit Perusahaan) + YYYYMMDD (8 digit Tanggal) + SSSSSS (6 digit Urut)
	"""
	settings = frappe.get_single("Bea Cukai Settings")
	kode_kantor = (settings.kode_kantor or "0403").strip()[:4].zfill(4)
	doc_code = DOC_TYPE_CODE_MAP.get(doc_type, "23")[:2].zfill(2)
	kode_perusahaan = (settings.kode_perusahaan or "000001").strip()[:6].zfill(6)

	if not tgl_aju:
		tgl_aju = nowdate()
	date_obj = getdate(tgl_aju)
	date_str = date_obj.strftime("%Y%m%d")

	# Penomoran sekuensial harian atomik via tabSeries
	series_key = f"NOAJU.{doc_code}.{date_str}..######"
	raw_series = str(frappe.model.naming.make_autoname(series_key))
	serial_no = raw_series[-6:].zfill(6)

	if with_hyphen is None:
		with_hyphen = bool(settings.no_aju_with_hyphen)

	if with_hyphen:
		return f"{kode_kantor}{doc_code}-{kode_perusahaan}-{date_str}-{serial_no}"
	else:
		return f"{kode_kantor}{doc_code}{kode_perusahaan}{date_str}{serial_no}"


@frappe.whitelist()
def make_bc_23_from_po(source_name, target_doc=None):
	"""
	Dipanggil dari Purchase Order untuk membuat draft BC_23_Declaration di UI
	"""
	po = frappe.get_doc("Purchase Order", source_name)
	if po.docstatus != 1:
		frappe.throw(_("Purchase Order {0} harus dalam status Submitted").format(source_name))

	bc = frappe.new_doc("BC_23_Declaration")
	bc.erp_bc_reference = po.name
	bc.doc_type = "BC 2.3"
	bc.tgl_aju = nowdate()
	settings = frappe.get_single("Bea Cukai Settings")
	if settings.auto_generate_no_aju:
		bc.no_aju = generate_nomor_aju(bc.doc_type, bc.tgl_aju)

	bc.supplier_name = po.supplier_name or po.supplier
	bc.currency = po.currency

	total_cif = 0.0
	for item in po.items:
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
def api_create_bc_23():
	"""
	REST API Endpoint: POST /api/method/bea_cukai_integration.api.bc_23.api_create_bc_23
	Menerima data JSON untuk membuat dokumen BC 2.3 dari Purchase Order.
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

	bc = frappe.new_doc("BC_23_Declaration")
	bc.erp_bc_reference = po.name
	bc.doc_type = data.get("doc_type", "BC 2.3")
	bc.tgl_aju = data.get("tgl_aju") or nowdate()
	if data.get("no_aju"):
		bc.no_aju = str(data.get("no_aju"))
	else:
		settings = frappe.get_single("Bea Cukai Settings")
		if settings.auto_generate_no_aju:
			bc.no_aju = generate_nomor_aju(bc.doc_type, bc.tgl_aju)
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
		for item in po.items:
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
		"message": _("BC 2.3 Declaration {0} berhasil dibuat").format(bc.name),
		"data": {
			"name": bc.name,
			"docstatus": bc.docstatus,
			"no_aju": bc.no_aju,
			"erp_bc_reference": bc.erp_bc_reference,
			"cif_value": bc.cif_value,
		}
	}


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
	Menghasilkan format JSON CEISA 4.0 Bea Cukai untuk dokumen BC 2.3
	"""
	bc = frappe.get_doc("BC_23_Declaration", bc_name) if isinstance(bc_name, str) else bc_name
	po = frappe.get_doc("Purchase Order", bc.erp_bc_reference) if bc.erp_bc_reference else None

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

	payload = {
		"nomorAju": bc.no_aju or "",
		"tanggalAju": str(bc.tgl_aju or ""),
		"kodeDokumen": "23",
		"kodeKantor": "040300",  # Default KPPBC
		"entitas": [
			{
				"kodeEntitas": "1",  # Importir / Pengusaha TPB
				"namaEntitas": po.company if po else "",
			},
			{
				"kodeEntitas": "2",  # Pemasok Luar Negeri
				"namaEntitas": bc.supplier_name or "",
			}
		],
		"pengangkut": {
			"kodeTutupPu": "11",
		},
		"pungutan": {
			"nilaiCif": flt(bc.cif_value),
			"beaMasuk": flt(bc.bm),
			"ppn": flt(bc.ppn),
			"ppnBm": flt(bc.ppn_bm),
		},
		"barang": barang_list,
	}

	bc.json_payload = json.dumps(payload, indent=2)
	bc.save(ignore_permissions=True)
	frappe.db.commit()

	return payload
