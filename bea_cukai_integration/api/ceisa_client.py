import json
import requests
import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, add_to_date


def get_ceisa_config():
	settings = frappe.get_single("Bea Cukai Settings")
	base_url = (settings.ceisa_gateway_url or "https://apis-gw.beacukai.go.id").rstrip("/")
	username = settings.ceisa_username
	password = settings.get_password("ceisa_password", raise_exception=False) if hasattr(settings, "get_password") else None
	return {
		"settings": settings,
		"base_url": base_url,
		"username": username,
		"password": password,
		"token": settings.ceisa_access_token,
		"expiry": settings.ceisa_token_expiry,
		"environment": settings.ceisa_environment or "Production",
	}


@frappe.whitelist()
def login_ceisa(force=False):
	"""
	Login ke API Gateway CEISA 4.0 Bea Cukai untuk memperoleh Access Token (JWT Bearer).
	Endpoint resmi DJBC: POST https://apis-gw.beacukai.go.id/nle-oauth/v1/user/login
	"""
	config = get_ceisa_config()
	settings = config["settings"]

	# Dukungan Demo / Presentation Mode (Presentasi ke Calon Klien)
	if config["environment"] == "Demo / Presentation Mode":
		demo_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vX2NlaXNhIiwiaXNzIjoiZGpib19jZWlzYTRfMCIsImV4cCI6MTc5MzIwMDAwMH0.DEMO_SIMULATION_SIGNATURE"
		expiry_dt = add_to_date(now_datetime(), hours=8)
		settings.ceisa_access_token = demo_token
		settings.ceisa_token_expiry = expiry_dt
		settings.ceisa_last_status = "Terkoneksi (CEISA 4.0 Demo Gateway Aktif)"
		settings.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"status": "success",
			"message": "Autentikasi Gateway CEISA 4.0 Berhasil (Demo Mode)",
			"token": demo_token,
			"expiry": str(expiry_dt),
			"environment": "Demo / Presentation Mode",
		}

	# Jika token masih ada dan belum kadaluarsa (Production/Sandbox)
	if not force and config["token"] and config["expiry"]:
		if get_datetime(config["expiry"]) > now_datetime():
			return {
				"status": "success",
				"message": "Token CEISA 4.0 masih aktif",
				"token": config["token"],
				"expiry": str(config["expiry"]),
			}
	if not config["username"] or not config["password"]:
		frappe.throw(
			_(
				"Kredensial CEISA 4.0 belum lengkap.<br>"
				"Silakan isi <b>CEISA Username</b> dan <b>CEISA Password</b> perusahaan Anda pada menu <b>Bea Cukai Settings</b>."
			),
			title=_("Kredensial Belum Terisi"),
		)

	login_url = f"{config['base_url']}/nle-oauth/v1/user/login"
	headers = {"Content-Type": "application/json"}
	payload = {
		"username": config["username"],
		"password": config["password"],
	}

	try:
		resp = requests.post(login_url, json=payload, headers=headers, timeout=20)
		resp_json = resp.json() if resp.status_code == 200 else {}

		if resp.status_code == 200 and resp_json.get("item", {}).get("access_token"):
			access_token = resp_json["item"]["access_token"]
			expires_in = resp_json.get("item", {}).get("expires_in", 3600 * 4)
			expiry_dt = add_to_date(now_datetime(), seconds=int(expires_in))

			settings.ceisa_access_token = access_token
			settings.ceisa_token_expiry = expiry_dt
			settings.ceisa_last_status = "Terkoneksi (Login Berhasil)"
			settings.save(ignore_permissions=True)
			frappe.db.commit()

			return {
				"status": "success",
				"message": "Login ke CEISA 4.0 berhasil",
				"token": access_token,
				"expiry": str(expiry_dt),
			}
		else:
			error_msg = resp_json.get("message") or resp.text or f"HTTP {resp.status_code}"
			settings.ceisa_last_status = f"Gagal: {error_msg[:100]}"
			settings.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.throw(
				_("Gagal login ke Gateway CEISA 4.0 Bea Cukai: {0}").format(error_msg),
				title=_("Autentikasi CEISA Gagal"),
			)
	except requests.RequestException as e:
		settings.ceisa_last_status = f"Error Koneksi: {str(e)[:100]}"
		settings.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(
			_("Gagal terhubung ke Server CEISA 4.0 ({0}): {1}").format(config["base_url"], str(e)),
			title=_("Koneksi Server Gagal"),
		)


@frappe.whitelist()
def send_document_to_ceisa(doctype, docname):
	"""
	Mengirimkan dokumen pabean (Pemasukan atau Pengeluaran) ke API Gateway CEISA 4.0 DJBC.
	Endpoint resmi DJBC: POST https://apis-gw.beacukai.go.id/tpb/v1/dokumen
	"""
	if doctype not in ["BC_23_Declaration", "BC_Outbound_Declaration"]:
		frappe.throw(_("DocType {0} tidak didukung untuk pengiriman CEISA").format(doctype))

	doc = frappe.get_doc(doctype, docname)
	if doc.docstatus != 1:
		frappe.throw(_("Dokumen {0} harus dalam status Submitted sebelum dikirim ke CEISA").format(docname))

	# Pastikan payload JSON sudah digenerate
	if not doc.json_payload:
		if doctype == "BC_23_Declaration":
			from bea_cukai_integration.api.bc_23 import generate_ceisa_payload
			generate_ceisa_payload(doc.name)
		else:
			from bea_cukai_integration.api.bc_outbound import generate_outbound_ceisa_payload
			generate_outbound_ceisa_payload(doc.name)
		doc.reload()

	payload_dict = json.loads(doc.json_payload)
	config = get_ceisa_config()

	# Dapatkan Token Login CEISA
	auth_info = login_ceisa()
	token = auth_info["token"]

	# Jika dalam Mode Demo / Presentasi
	if config["environment"] == "Demo / Presentation Mode":
		msg = f"Dokumen {doc.doc_type} (No Aju: {doc.no_aju}) berhasil dikirim & tervalidasi di Gateway CEISA 4.0 DJBC."
		frappe.msgprint(
			_(
				"<b>Sukses Kirim CEISA 4.0 (Demo Mode)</b><br>"
				"Nomor Aju: <b>{0}</b><br>"
				"Jenis Dokumen: <b>{1}</b><br>"
				"Status: <b>Dokumen Diterima oleh Sistem CEISA 4.0 DJBC</b><br>"
				"Waktu Pengiriman: {2}<br><br>"
				"<i>Silakan klik 'Cek Status CEISA' untuk simulasi penarikan Nopen / SPPB resmi.</i>"
			).format(doc.no_aju, doc.doc_type, str(now_datetime())),
			indicator="green",
			title=_("CEISA 4.0 Gateway"),
		)
		return {
			"status": "success",
			"message": msg,
			"nomorAju": doc.no_aju,
			"statusPabean": "Dokumen Diterima oleh Sistem CEISA 4.0 DJBC",
		}

	send_url = f"{config['base_url']}/tpb/v1/dokumen"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	try:
		resp = requests.post(send_url, json=payload_dict, headers=headers, timeout=30)
		resp_json = resp.json() if resp.status_code in [200, 201] else {}

		if resp.status_code in [200, 201]:
			msg = resp_json.get("message") or "Dokumen pabean berhasil dikirim ke CEISA 4.0"
			frappe.msgprint(
				_("<b>Sukses Kirim CEISA 4.0</b><br>Nomor Aju: <b>{0}</b><br>Status: {1}").format(
					doc.no_aju, msg
				),
				indicator="green",
				title=_("CEISA 4.0 Response"),
			)
			return {
				"status": "success",
				"message": msg,
				"data": resp_json,
			}
		else:
			err_msg = resp_json.get("message") or resp.text or f"HTTP {resp.status_code}"
			frappe.throw(
				_("CEISA 4.0 menolak pengiriman dokumen: {0}").format(err_msg),
				title=_("Ditolak CEISA 4.0"),
			)
	except requests.RequestException as e:
		frappe.throw(
			_("Gagal mengirim payload ke Gateway CEISA ({0}): {1}").format(send_url, str(e)),
			title=_("Koneksi Gagal"),
		)


@frappe.whitelist()
def check_ceisa_status(doctype, docname):
	"""
	Mengecek status respon terbaru dari server CEISA 4.0 Bea Cukai berdasarkan Nomor Aju.
	Jika nomor pendaftaran (Nopen) atau SPPB/NPE sudah terbit, otomatis mengupdate dokumen di ERPNext.
	Endpoint resmi DJBC: GET https://apis-gw.beacukai.go.id/tpb/v1/dokumen/status/{nomorAju}
	"""
	doc = frappe.get_doc(doctype, docname)
	if not doc.no_aju:
		frappe.throw(_("Dokumen {0} belum memiliki Nomor Aju").format(docname))

	clean_no_aju = str(doc.no_aju).replace("-", "").strip()
	config = get_ceisa_config()

	# Jika dalam Mode Demo / Presentasi
	if config["environment"] == "Demo / Presentation Mode":
		settings = config["settings"]
		from frappe.utils import nowdate
		clean_digits = "".join(filter(str.isdigit, str(doc.no_aju)))
		seq_suffix = clean_digits[-4:] if len(clean_digits) >= 4 else "0001"
		kantor = getattr(settings, "kode_kantor", "0403") or "0403"
		demo_nopen = f"00{seq_suffix}/KPPBC.{kantor}/{now_datetime().year}"

		if not doc.no_daftar:
			doc.no_daftar = demo_nopen
			doc.tgl_daftar = nowdate()
			doc.save(ignore_permissions=True)
			frappe.db.commit()

		frappe.msgprint(
			_(
				"<b>Status Terkini CEISA 4.0 DJBC (Demo Mode):</b><br>"
				"Nomor Aju: <b>{0}</b><br>"
				"Jenis Dokumen: <b>{1}</b><br>"
				"Status Pabean: <span class='badge badge-success' style='font-size: 13px;'>Persetujuan Pabean (SPPB / NPE Terbit)</span><br>"
				"Nomor Pendaftaran: <b>{2}</b><br>"
				"Tanggal Pendaftaran: <b>{3}</b><br><br>"
				"<i>Kolom No Daftar & Tanggal Daftar otomatis diperbarui di ERPNext. Barang siap direalisasikan ke gudang.</i>"
			).format(doc.no_aju, doc.doc_type, doc.no_daftar, doc.tgl_daftar),
			indicator="blue",
			title=_("Status Terkini CEISA 4.0"),
		)
		return {
			"status": "success",
			"status_dokumen": "Persetujuan Pabean (SPPB / NPE Terbit)",
			"nomor_daftar": doc.no_daftar,
			"tanggal_daftar": str(doc.tgl_daftar),
		}

	auth_info = login_ceisa()
	status_url = f"{config['base_url']}/tpb/v1/dokumen/status/{clean_no_aju}"
	headers = {
		"Authorization": f"Bearer {token}",
	}

	try:
		resp = requests.get(status_url, headers=headers, timeout=20)
		resp_json = resp.json() if resp.status_code == 200 else {}

		if resp.status_code == 200:
			item_data = resp_json.get("item") or resp_json.get("data") or {}
			nomor_daftar = item_data.get("nomorDaftar") or item_data.get("noDaftar")
			tanggal_daftar = item_data.get("tanggalDaftar") or item_data.get("tglDaftar")
			status_dok = item_data.get("status") or item_data.get("namaStatus") or "Dalam Proses Pabean"

			if nomor_daftar and not doc.no_daftar:
				doc.no_daftar = nomor_daftar
				if tanggal_daftar:
					doc.tgl_daftar = tanggal_daftar
				doc.save(ignore_permissions=True)
				frappe.db.commit()

			frappe.msgprint(
				_(
					"<b>Status Dokumen CEISA 4.0:</b><br>"
					"Nomor Aju: <b>{0}</b><br>"
					"Status Pabean: <b>{1}</b><br>"
					"Nomor Pendaftaran: <b>{2}</b><br>"
					"Tanggal Pendaftaran: <b>{3}</b>"
				).format(doc.no_aju, status_dok, nomor_daftar or "-", tanggal_daftar or "-"),
				indicator="blue",
				title=_("Status Terkini CEISA 4.0"),
			)

			return {
				"status": "success",
				"status_dokumen": status_dok,
				"nomor_daftar": nomor_daftar,
				"tanggal_daftar": tanggal_daftar,
				"raw": resp_json,
			}
		else:
			err_msg = resp_json.get("message") or resp.text or f"HTTP {resp.status_code}"
			frappe.msgprint(_("Status pabean: {0}").format(err_msg), indicator="orange")
			return {"status": "error", "message": err_msg}
	except requests.RequestException as e:
		frappe.throw(
			_("Gagal memeriksa status ke Server CEISA: {0}").format(str(e)),
			title=_("Koneksi Gagal"),
		)
