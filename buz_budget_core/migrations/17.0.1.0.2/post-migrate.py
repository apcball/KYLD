# -*- coding: utf-8 -*-
"""Post-migration: convert budget.move → budget.transaction.

On first install, the post_init_hook handles this. This script covers
future upgrades from older buz_budget_core versions.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.buz_budget_core.hooks import run_migration

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    run_migration(env)
