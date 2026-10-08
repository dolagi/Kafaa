/** @odoo-module **/

import SurveyFormWidget from "@survey/js/survey_form";

SurveyFormWidget.include({
    start() {
        return this._super(...arguments).then(() => {
            this.examStartClick = (event) => {
                const button = event.target.closest('button[type="submit"]');
                if (!this.options.isStartScreen || !button || !this.el.contains(button)) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                this._submitForm({});
            };
            this.examStartKey = (event) => {
                if (event.key !== 'Enter' || !this.options.isStartScreen
                    || event.target.closest('textarea')) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                this._submitForm({});
            };
            this.el.addEventListener('click', this.examStartClick, true);
            document.addEventListener('keydown', this.examStartKey, true);
        });
    },

    async _nextScreen(nextScreenPromise, options) {
        if (!this.examReviewMode) {
            return this._super(...arguments);
        }
        // Review navigation must not depend on a fadeOut callback: the form
        // was hidden on the confirmation screen and may already be invisible.
        try {
            const [, result] = await nextScreenPromise;
            this.nextScreenResult = result;
            this._onNextScreenDone(options);
        } catch (error) {
            this.preventEnterSubmit = false;
            this.$('.o_survey_error').removeClass('d-none');
            console.error('Exam review navigation failed', error);
        } finally {
            this.$('.o_survey_form_content').stop(true, true).show();
        }
    },

    _showExamSubmissionConfirmation() {
        if (this.examSubmissionPage) {
            return;
        }
        const form = this.el.querySelector('form');
        if (!form || !this._validateForm($(form), new FormData(form))) {
            return;
        }
        const dialog = document.createElement('section');
        dialog.className = 'o_exam_submission_confirmation';
        dialog.dir = 'rtl';
        dialog.innerHTML = `
            <h3>تسليم الامتحان</h3>
            <p>وصلت إلى نهاية الأسئلة. اضغط «تسليم وخروج» لإنهاء الامتحان، أو راجع إجاباتك من السؤال الأول.</p>
            <div class="d-flex gap-3 justify-content-center">
                <button type="button" class="btn btn-secondary" data-action="back">مراجعة الإجابات</button>
                <button type="button" class="btn btn-primary" data-action="finish">تسليم وخروج</button>
            </div>`;
        dialog.querySelector('[data-action="back"]').addEventListener('click', () => {
            const reviewPages = JSON.parse(form.dataset.examReviewPageIds || '[]');
            const firstPageId = reviewPages[0] || Number(form.dataset.firstExamPageId);
            this._closeExamSubmissionConfirmation();
            if (firstPageId) {
                this.examReviewMode = true;
                this._submitForm({ previousPageId: firstPageId });
            }
        });
        dialog.querySelector('[data-action="finish"]').addEventListener('click', () => {
            this._closeExamSubmissionConfirmation();
            this._submitForm({ isFinish: true, explicitExamSubmit: true });
        });
        this.examSubmissionPage = dialog;
        form.classList.add('d-none');
        this.$surveyNavigation.addClass('d-none');
        this.el.appendChild(dialog);
        dialog.querySelector('[data-action="back"]').focus();
    },

    _closeExamSubmissionConfirmation() {
        if (this.examSubmissionPage) {
            this.examSubmissionPage.remove();
            this.examSubmissionPage = null;
            const form = this.el.querySelector('form');
            if (form) {
                form.classList.remove('d-none');
            }
            this.$surveyNavigation.removeClass('d-none');
        }
    },

    destroy() {
        if (this.examStartClick) {
            this.el.removeEventListener('click', this.examStartClick, true);
            document.removeEventListener('keydown', this.examStartKey, true);
        }
        this._closeExamSubmissionConfirmation();
        return this._super(...arguments);
    },

    _submitForm(options = {}) {
        if (this.examStartPending && this.options.isStartScreen) {
            return;
        }
        if (this.options.isStartScreen) {
            this.examStartPending = true;
            const submit = this._super.bind(this);
            return Promise.resolve(submit(options)).finally(() => {
                this.examStartPending = false;
            });
        }
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
        if (this.examReviewMode && !options.previousPageId
            && !options.skipValidation && !options.explicitExamSubmit) {
            const form = this.el.querySelector('form');
            const pages = JSON.parse(form.dataset.examReviewPageIds || '[]');
            const current = form.querySelector('input[name="question_id"], input[name="page_id"]');
            const index = current ? pages.indexOf(Number(current.value)) : -1;
            if (index >= 0 && index + 1 < pages.length) {
                // Save this answer and render the exact next review question.
                // Avoid Odoo's skipped-question/last-displayed navigation state.
                options = { ...options, isFinish: false, previousPageId: pages[index + 1] };
            }
        }
        return this._super(options);
    },
});
