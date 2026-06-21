# -*- coding: utf-8 -*-
from . import models
from .hooks import run_migration


def post_init(env):
    """Post-install hook: migrate budget.move → budget.transaction."""
    run_migration(env)
