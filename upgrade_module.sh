#!/bin/bash
cd /opt/instance1/odoo17
source venv/bin/activate
python odoo-bin -c /etc/instance1.conf -d KYLD-LIVE -u employee_purchase_requisition --stop-after-init
sudo systemctl restart instance1
