/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ImageField, imageField } from "@web/views/fields/image/image_field";

// A shared display fallback covers existing and new sheets without storing
// duplicate attachments or replacing any photo uploaded by the user.
export class ProjectImageField extends ImageField {
    getUrl(previewFieldName) {
        if (!this.props.record.data[this.props.name]) {
            return "/job_costing_management/static/src/img/project_default.png";
        }
        return super.getUrl(previewFieldName);
    }
}

registry.category("fields").add("job_cost_project_image", {
    ...imageField,
    component: ProjectImageField,
    additionalClasses: [...(imageField.additionalClasses || []), "o_field_image"],
});
