// Copyright (c) 2026, Nabila and contributors
// For license information, please see license.txt

frappe.ui.form.on("BC_Outbound_Declaration", {
	refresh(frm) {
		frm.trigger("render_no_aju_status");

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Delivery Note"),
				function () {
					frappe.model.open_mapped_doc({
						method: "bea_cukai_integration.api.bc_outbound.make_delivery_note_from_outbound_bc",
						frm: frm,
					});
				},
				__("Create")
			);
			frm.page.set_inner_btn_group_as_primary(__("Create"));

			frm.add_custom_button(
				__("Generate CEISA JSON"),
				function () {
					frappe.call({
						method: "bea_cukai_integration.api.bc_outbound.generate_outbound_ceisa_payload",
						args: { bc_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Mengenerate Payload CEISA Pengeluaran..."),
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Payload CEISA Ekspor/Pengeluaran berhasil digenerate"),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				},
				__("Actions")
			);
		}

		frm.add_custom_button(
			__("Cek Rincian No Aju"),
			function () {
				show_outbound_no_aju_dialog(frm);
			},
			__("Actions")
		);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Generate No Urut Baru"),
				function () {
					frappe.call({
						method: "bea_cukai_integration.api.bc_outbound.assemble_outbound_nomor_aju",
						args: {
							doc_type: frm.doc.doc_type || "BC 3.0",
							tgl_aju: frm.doc.tgl_aju,
							no_urut: null,
						},
						callback: function (r) {
							if (r.message) {
								frm.set_value("no_urut", r.message.no_urut);
								frm.set_value("no_aju", r.message.no_aju);
								frappe.show_alert({
									message: __("Nomor Urut Pengeluaran baru berhasil digenerate"),
									indicator: "blue",
								});
								frm.trigger("render_no_aju_status");
							}
						},
					});
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Tarik Bahan Baku (BOM Konversi)"),
				function () {
					frappe.call({
						method: "bea_cukai_integration.api.bc_outbound.explode_bom_for_outbound",
						args: { bc_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Menelusuri bahan baku dan riwayat dokumen masuk asal..."),
						callback: function (r) {
							if (r.message) {
								frm.reload_doc();
								frappe.show_alert({
									message: __("{0} bahan baku berhasil ditarik dan dilekatkan riwayat masuknya", [r.message.count]),
									indicator: "green",
								});
							}
						},
					});
				},
				__("Actions")
			);
		}
	},

	no_urut(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.no_urut) {
			frm.trigger("recalculate_no_aju");
		}
	},

	doc_type(frm) {
		if (frm.doc.docstatus === 0) {
			frappe.call({
				method: "bea_cukai_integration.api.bc_outbound.assemble_outbound_nomor_aju",
				args: {
					doc_type: frm.doc.doc_type || "BC 3.0",
					tgl_aju: frm.doc.tgl_aju,
					no_urut: null,
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("no_urut", r.message.no_urut);
						frm.set_value("no_aju", r.message.no_aju);
						frappe.show_alert({
							message: __("Urutan pengeluaran diperbarui untuk {0}: {1}", [
								frm.doc.doc_type,
								r.message.no_urut,
							]),
							indicator: "blue",
						});
						frm.trigger("render_no_aju_status");
					}
				},
			});
		}
	},

	tgl_aju(frm) {
		if (frm.doc.docstatus === 0) {
			frm.trigger("recalculate_no_aju");
		}
	},

	recalculate_no_aju(frm) {
		frappe.call({
			method: "bea_cukai_integration.api.bc_outbound.assemble_outbound_nomor_aju",
			args: {
				doc_type: frm.doc.doc_type || "BC 3.0",
				tgl_aju: frm.doc.tgl_aju,
				no_urut: frm.doc.no_urut,
			},
			callback: function (r) {
				if (r.message) {
					if (frm.doc.no_urut !== r.message.no_urut) {
						frm.set_value("no_urut", r.message.no_urut);
					}
					frm.set_value("no_aju", r.message.no_aju);
					frm.trigger("render_no_aju_status");
				}
			},
		});
	},

	render_no_aju_status(frm) {
		if (!frm.doc.no_aju) {
			frm.set_df_property(
				"no_aju",
				"description",
				__("Nomor Aju 26 digit dirakit otomatis dari Kantor + Dokumen + Perusahaan + Tanggal + No Urut")
			);
			return;
		}

		frappe.call({
			method: "bea_cukai_integration.api.bc_23.parse_and_validate_no_aju",
			args: { no_aju: frm.doc.no_aju },
			callback: function (r) {
				if (r.message) {
					const d = r.message;
					if (d.is_valid) {
						frm.set_df_property(
							"no_aju",
							"description",
							`<span style="color: #28a745; font-weight: bold;">✔ Valid 26 Digit</span>: Kantor <b>${d.kode_kantor}</b> | Dok <b>${d.kode_dokumen}</b> | Perusahaan <b>${d.kode_perusahaan}</b> | Tgl <b>${d.tanggal_aju}</b> | Urut <b>${d.nomor_urut}</b>`
						);
					} else {
						frm.set_df_property(
							"no_aju",
							"description",
							`<span style="color: #dc3545; font-weight: bold;">✖ Format Tidak Valid</span>: ${d.message}`
						);
					}
				}
			},
		});
	},
});

frappe.ui.form.on("BC_Outbound_Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.item_code && !row.inbound_bc_declaration) {
			frappe.call({
				method: "bea_cukai_integration.api.bc_outbound.get_inbound_history_for_item",
				args: { item_code: row.item_code },
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						const latest = r.message[0];
						frappe.model.set_value(cdt, cdn, "inbound_bc_declaration", latest.bc_declaration);
						frappe.model.set_value(cdt, cdn, "inbound_bc_type", latest.doc_type);
						frappe.model.set_value(cdt, cdn, "inbound_no_aju", latest.no_aju);
						frappe.model.set_value(cdt, cdn, "inbound_tgl_aju", latest.tgl_aju);
						frappe.model.set_value(cdt, cdn, "inbound_no_daftar", latest.no_daftar);
						frappe.model.set_value(cdt, cdn, "inbound_tgl_daftar", latest.tgl_daftar);
						frappe.model.set_value(cdt, cdn, "inbound_po_reference", latest.po_reference);
						frappe.model.set_value(cdt, cdn, "inbound_item_rate", latest.rate);
						frappe.model.set_value(cdt, cdn, "inbound_currency", latest.currency);
						frappe.model.set_value(cdt, cdn, "inbound_cif_amount", latest.cif_amount);
						frappe.show_alert({
							message: __("Riwayat dokumen masuk otomatis dilekatkan untuk {0}", [row.item_code]),
							indicator: "green",
						});
					}
				},
			});
		}
	},
	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
		frm.trigger("calculate_totals");
	},
	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
		frm.trigger("calculate_totals");
	},
});

function show_outbound_no_aju_dialog(frm) {
	if (!frm.doc.no_aju) {
		frappe.msgprint(__("Nomor Aju masih kosong. Silakan generate terlebih dahulu."));
		return;
	}

	frappe.call({
		method: "bea_cukai_integration.api.bc_23.parse_and_validate_no_aju",
		args: { no_aju: frm.doc.no_aju },
		callback: function (r) {
			if (!r.message) return;
			const data = r.message;

			let htmlContent = "";
			if (data.is_valid) {
				htmlContent = `
					<div style="padding: 10px; border-left: 4px solid #28a745; background-color: #f8fdf9; margin-bottom: 15px;">
						<h5 style="color: #28a745; margin: 0 0 5px 0;">✔ Format Dokumen Pengeluaran Valid 26 Digit</h5>
						<span style="font-family: monospace; font-size: 14px; font-weight: bold;">${data.formatted}</span>
					</div>
					<table class="table table-bordered table-sm" style="font-size: 13px;">
						<tbody>
							<tr><th style="width: 40%;">Kode Kantor Pabean</th><td><b>${data.kode_kantor}</b> (${data.nama_kantor})</td></tr>
							<tr><th>Jenis Dokumen Pengeluaran</th><td><b>${data.kode_dokumen}</b> (${frm.doc.doc_type})</td></tr>
							<tr><th>Kode Unik Perusahaan</th><td><b>${data.kode_perusahaan}</b></td></tr>
							<tr><th>Tanggal Pengajuan</th><td><b>${data.tanggal_aju}</b></td></tr>
							<tr><th>Nomor Urut Pengeluaran</th><td><b>${data.nomor_urut}</b></td></tr>
							<tr><th>26 Digit Murni Pabean</th><td><code>${data.clean_no}</code></td></tr>
						</tbody>
					</table>
				`;
			} else {
				htmlContent = `
					<div style="padding: 10px; border-left: 4px solid #dc3545; background-color: #fdf8f8; margin-bottom: 15px;">
						<h5 style="color: #dc3545; margin: 0 0 5px 0;">✖ Format Nomor Aju Tidak Valid</h5>
						<p style="margin: 0; color: #555;">${data.message}</p>
					</div>
				`;
			}

			const d = new frappe.ui.Dialog({
				title: __("Pemeriksaan Nomor Aju Pengeluaran"),
				fields: [
					{
						fieldname: "html_detail",
						fieldtype: "HTML",
						options: htmlContent,
					},
				],
				primary_action_label: __("Tutup"),
				primary_action: function () {
					d.hide();
				},
			});
			d.show();
		},
	});
}
