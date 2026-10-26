import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Purchase Receipt": [
		{
			"fieldname": "custom_bc_section",
			"label": "Bea Cukai Reference",
			"fieldtype": "Section Break",
			"insert_after": "transporter_info",
		},
		{
			"fieldname": "custom_bc_declaration",
			"label": "BC Declaration",
			"fieldtype": "Link",
			"options": "BC_23_Declaration",
			"insert_after": "custom_bc_section",
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "custom_bc_doc_type",
			"label": "BC Doc Type",
			"fieldtype": "Data",
			"insert_after": "custom_bc_declaration",
			"read_only": 1,
			"fetch_from": "custom_bc_declaration.doc_type",
		},
		{
			"fieldname": "custom_bc_no_aju",
			"label": "No Aju BC",
			"fieldtype": "Data",
			"insert_after": "custom_bc_doc_type",
			"read_only": 1,
			"fetch_from": "custom_bc_declaration.no_aju",
		},
		{
			"fieldname": "custom_bc_col_break",
			"fieldtype": "Column Break",
			"insert_after": "custom_bc_no_aju",
		},
		{
			"fieldname": "custom_bc_tgl_aju",
			"label": "Tanggal Aju BC",
			"fieldtype": "Date",
			"insert_after": "custom_bc_col_break",
			"read_only": 1,
			"fetch_from": "custom_bc_declaration.tgl_aju",
		},
		{
			"fieldname": "custom_bc_no_daftar",
			"label": "Nomor Pendaftaran BC",
			"fieldtype": "Data",
			"insert_after": "custom_bc_tgl_aju",
			"read_only": 1,
			"fetch_from": "custom_bc_declaration.no_daftar",
		},
		{
			"fieldname": "custom_bc_tgl_daftar",
			"label": "Tanggal Pendaftaran BC",
			"fieldtype": "Date",
			"insert_after": "custom_bc_no_daftar",
			"read_only": 1,
			"fetch_from": "custom_bc_declaration.tgl_daftar",
		},
	],
	"Purchase Receipt Item": [
		{
			"fieldname": "custom_hs_code",
			"label": "HS Code",
			"fieldtype": "Data",
			"insert_after": "item_code",
			"read_only": 1,
			"fetch_from": "item_code.custom_hs_code",
			"in_list_view": 1,
		}
	],
}

def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, update=True)
