#!/usr/bin/env python3
import netforce

modules=[
    "netforce_ui",
    "netforce_report",
    "netforce_xmlrpc",
    "netforce_jsonrpc",
    "netforce_general",
    "netforce_contact",
    "netforce_service",
    "netforce_support",
    "netforce_product",
    "netforce_account",
    "netforce_account_report",
    "netforce_stock",
    "netforce_stock_cost",
    "netforce_sale",
    "netforce_purchase",
    "netforce_mfg",
    "netforce_marketing",
    "netforce_delivery",
    "netforce_hr",
    "netforce_document",
    "netforce_messaging",
    "netforce_cms", 
    "netforce_ecom",
]

netforce.load_modules(modules)
netforce.run_server()
