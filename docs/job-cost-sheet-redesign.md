# Job Cost Sheet redesign

Implemented in `job_costing_management`, version `17.0.1.0.5`.

## Default project photo (17.0.1.0.6)

Generated with the built-in imagegen tool and saved as
`job_costing_management/static/src/img/project_default.png`.
The `job_cost_project_image` field widget displays this shared image whenever
the sheet has no uploaded photo, including existing sheets. Upload and removal
retain native Odoo behavior; uploaded photos take precedence. Removing an upload
restores the default image. No existing image attachments are overwritten.

Generation prompt:

> Use case: photorealistic-natural. Asset type: default project photograph for a Thai construction job costing app. Generate only a landscape photograph, no application interface. A realistic modern two-storey detached house in Thailand, off-white walls, charcoal grey hip roof, large glass windows and balcony, viewed from front three-quarter angle. Neat residential construction nearing completion with subtle unfinished ground level details, tropical greenery around the edges, soft blue sky with white clouds, natural daylight. Professional architectural photography, clean calm composition, whole building centered and fully visible with generous margins suitable for cropping to a wide 1.65:1 project thumbnail. No people, vehicles, signs, text, logos, watermark or border.

Focused widget checks passed for empty images, preserving uploaded photos, and
restoring the default after removal. Asset existence and patch whitespace checks passed.
Deployed to DEV (`KYLD-DEV`) on September 13, 2026: module upgrade exited 0,
Odoo restarted, local/remote SHA-256 hashes matched for the image and widget,
and both the image URL and DEV login returned HTTP 200.

The form follows the supplied mockup with a title and status badge, project metadata and an uploadable photo, Summary / Materials / Labour / Overhead / Notes / Related Documents tabs, four colored KPI cards, a budget usage bar, four cost breakdown panels, and an editable material table. The chatter follows the full-width sheet. Styling is scoped to this form; the installed Odoo navigation and toolbar remain native.

Summary variance is actual minus the BOQ baseline, as labeled in the mockup. Existing stored variance fields and line calculations retain their original semantics. Usage displays an explicit empty state for zero or negative budgets; progress is bounded to 0–100 while the numeric percentage can exceed 100. Amounts use Odoo's currency formatter. The photo belongs to the cost sheet and is optional.

The Summary table uses native Odoo line creation, editing, deletion, and access rules. Open BOQs leads to the existing BOQ workflow for creating/syncing cost lines. The mockup's standalone product search, Import from BOQ button, global sidebar, and global header are not recreated. Related Documents contains the existing purchase, timesheet, invoice, cost line, BOQ, and RFQ actions, with their existing visibility rules.

Validation:

- Fresh isolated Odoo 17 / PostgreSQL 16 database `MOG_TEST`: 66 tests, 0 failed, 0 errors.
- Final inherited view loaded successfully through a module upgrade in the isolated database.
- Python parsing, XML parsing, SCSS compilation, and `git diff --check` passed.
- Playwright against the actual local Odoo form: CSS grid applied, four cards and breakdown panels, six tabs, related-document buttons, zero-budget state, and mobile summary overflow checks passed with no browser exceptions.
- Browser response fixtures using the mockup totals verified 78.3% budget usage and −13,000 variance. These are synthetic figures, not company accounting data.

Local QA script: `/private/tmp/kyld-jcs-design-browser.cjs`.
Screenshots: `/private/tmp/kyld-jcs-design-desktop.png` and `/private/tmp/kyld-jcs-design-mobile.png`.

Deployed to DEV; not deployed to PROD. Installation requires updating `job_costing_management` and restarting Odoo so the new image field, inherited view, and frontend assets load together. Tests must continue to use an isolated database.
