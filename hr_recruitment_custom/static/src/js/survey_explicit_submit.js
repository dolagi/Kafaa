/** @odoo-module **/

import SurveyFormWidget from "@survey/js/survey_form";

SurveyFormWidget.include({
    _onSubmit(event) {
        const target = event.currentTarget;
        if (target.value === "finish" && target.dataset.explicitExamSubmit === "1") {
            event.preventDefault();
            return this._submitForm({ isFinish: true, explicitExamSubmit: true });
        }
        return this._super(...arguments);
    },

    _submitForm(options = {}) {
        const finishButton = this.el.querySelector(
            'button[value="finish"][data-explicit-exam-submit="1"]'
        );
        // Keyboard shortcuts and automatic choice navigation must leave the
        // last answer available for review. The exam timer still submits on expiry.
        if (finishButton && !options.previousPageId && !options.skipValidation
            && !options.explicitExamSubmit) {
            finishButton.focus();
            return;
        }
        return this._super(...arguments);
    },
});
