/** @odoo-module **/

import SurveyFormWidget from "@survey/js/survey_form";

SurveyFormWidget.include({
    _showExamSubmissionConfirmation() {
        if (this.examSubmissionDialog) {
            return;
        }
        const form = this.el.querySelector('form');
        if (!form || !this._validateForm($(form), new FormData(form))) {
            return;
        }
        const dialog = document.createElement('dialog');
        dialog.className = 'o_exam_submission_confirmation';
        dialog.dir = 'rtl';
        dialog.innerHTML = `
            <h3>تسليم الامتحان</h3>
            <p>وصلت إلى نهاية الأسئلة. اضغط «تسليم وخروج» لإنهاء الامتحان، أو ارجع لمراجعة إجابتك.</p>
            <div class="d-flex gap-3 justify-content-center">
                <button type="button" class="btn btn-secondary" data-action="back">الرجوع للأسئلة</button>
                <button type="button" class="btn btn-primary" data-action="finish">تسليم وخروج</button>
            </div>`;
        dialog.querySelector('[data-action="back"]').addEventListener('click', () => {
            this._closeExamSubmissionConfirmation();
        });
        dialog.querySelector('[data-action="finish"]').addEventListener('click', () => {
            this._closeExamSubmissionConfirmation();
            this._submitForm({ isFinish: true, explicitExamSubmit: true });
        });
        // Escape returns to the last question without submitting any answers.
        dialog.addEventListener('cancel', (event) => {
            event.preventDefault();
            this._closeExamSubmissionConfirmation();
        });
        this.examSubmissionDialog = dialog;
        document.body.appendChild(dialog);
        dialog.showModal();
    },

    _closeExamSubmissionConfirmation() {
        if (this.examSubmissionDialog) {
            this.examSubmissionDialog.close();
            this.examSubmissionDialog.remove();
            this.examSubmissionDialog = null;
        }
    },

    destroy() {
        this._closeExamSubmissionConfirmation();
        return this._super(...arguments);
    },

    _submitForm(options = {}) {
        const finishButton = this.el.querySelector(
            'button[value="finish"][data-explicit-exam-submit="1"]'
        );
        // No RPC is sent from the last question until the candidate confirms.
        // Timer expiry retains Odoo's automatic submission behavior.
        if (finishButton && !options.previousPageId && !options.skipValidation
            && !options.explicitExamSubmit) {
            return this._showExamSubmissionConfirmation();
        }
        this._closeExamSubmissionConfirmation();
        return this._super(...arguments);
    },
});
