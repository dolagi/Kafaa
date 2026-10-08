/** @odoo-module **/

import SurveyFormWidget from "@survey/js/survey_form";
import { rpc } from "@web/core/network/rpc";

SurveyFormWidget.include({
    _updateExamProgress() {
        const meta = this.el.querySelector('.o_exam_progress_data');
        const form = this.el.querySelector('form');
        if (!meta || !form) {
            return;
        }
        const ids = JSON.parse(meta.dataset.questionIds || '[]');
        const answered = new Set(JSON.parse(meta.dataset.answeredIds || '[]'));
        const params = {};
        this._prepareSubmitValues(new FormData(form), params);
        const current = form.querySelector('input[name="question_id"]');
        if (current && !Object.prototype.hasOwnProperty.call(params, current.value)) {
            answered.delete(Number(current.value));
        }
        for (const id of ids) {
            if (Object.prototype.hasOwnProperty.call(params, String(id))) {
                const value = params[id];
                const hasAnswer = value !== '' && value !== null && value !== undefined
                    && value !== false && value !== '[]' && value !== '{}'
                    && (!Array.isArray(value) || value.length > 0);
                if (hasAnswer) {
                    answered.add(id);
                } else {
                    answered.delete(id);
                }
            }
        }
        this.$surveyProgress.text(`تمت الإجابة على ${answered.size} من ${ids.length}`);
    },

    _onNextScreenDone(options) {
        this._examCloseConfirmation();
        const result = this._super(...arguments);
        this._updateExamProgress();
        return result;
    },

    _onChangeChoiceItem(event) {
        const result = this._super(...arguments);
        this._updateExamProgress();
        return result;
    },

    _onSubmit(event) {
        if (this.examConfirmation) {
            event.preventDefault();
            if (event.currentTarget.value === 'previous') {
                this._examCloseConfirmation();
            } else {
                this.examConfirmation.querySelector('[data-finish]').focus();
            }
            return;
        }
        return this._super(...arguments);
    },
    async _nextScreen(nextScreenPromise, options) {
        const nextScreen = this._super.bind(this);
        try {
            return await nextScreen(nextScreenPromise, options);
        } catch (error) {
            // Odoo fades the current content before awaiting the RPC. A failed
            // request/render must restore it instead of leaving a blank screen.
            this.preventEnterSubmit = false;
            this._examCloseConfirmation();
            this.$('.o_survey_form_content').stop(true, true).show();
            this.$('button[type="submit"]').removeClass('disabled').prop('disabled', false);
            this.$('.o_survey_error').removeClass('d-none');
            console.error('Exam screen transition failed', error);
        }
    },

    _examConfirmation() {
        if (this.examConfirmation) {
            return;
        }
        const form = this.el.querySelector('form');
        if (!this._validateForm($(form), new FormData(form))) {
            return;
        }
        const panel = document.createElement('section');
        panel.className = 'o_exam_confirmation text-center my-auto py-5';
        panel.dir = 'rtl';
        panel.innerHTML = `<h3>نهاية الأسئلة</h3>
            <p>يمكنك مراجعة إجاباتك أو تسليم الامتحان.</p>
            <div class="d-flex justify-content-center gap-3">
                <button type="button" class="btn btn-secondary" data-review="1">مراجعة الإجابات</button>
                <button type="button" class="btn btn-primary" data-finish="1">تسليم وخروج</button>
            </div>`;
        panel.querySelector('[data-review]').addEventListener('click', () => {
            const ids = JSON.parse(form.dataset.examReviewIds || '[]');
            this._examCloseConfirmation();
            if (ids.length) {
                this.examReview = true;
                this._submitForm({ previousPageId: ids[0] });
            }
        });
        panel.querySelector('[data-finish]').addEventListener('click', () => {
            panel.querySelectorAll('button').forEach(button => { button.disabled = true; });
            this._submitForm({ isFinish: true, examConfirmed: true });
        });
        // Hide only the questions, preserving the timer and the original form.
        this.$('.o_survey_form_content').hide();
        this.$surveyNavigation.removeClass('d-none');
        this._updateExamProgress();
        this.examConfirmation = panel;
        this.el.appendChild(panel);
        panel.querySelector('[data-review]').focus();
    },

    _examCloseConfirmation() {
        if (this.examConfirmation) {
            this.examConfirmation.remove();
            this.examConfirmation = null;
            this.$('.o_survey_form_content').stop(true, true).show();
            this.$surveyNavigation.removeClass('d-none');
        }
    },

    async _examReviewQuestion(targetId) {
        if (this.examReviewPending) {
            return;
        }
        const form = this.el.querySelector('form');
        const data = new FormData(form);
        if (!this._validateForm($(form), data)) {
            return;
        }
        const params = { previous_page_id: targetId };
        this._prepareSubmitValues(data, params);
        this.examReviewPending = true;
        this.preventEnterSubmit = true;
        try {
            const [, result] = await rpc(
                `/survey/submit/${this.options.surveyToken}/${this.options.answerToken}`, params
            );
            if (!result || result.error) {
                console.error('Exam review response rejected', {
                    targetId,
                    questionId: params.question_id,
                    pageId: params.page_id,
                    result,
                });
            } else {
                this.$('.o_survey_error').addClass('d-none');
            }
            this.nextScreenResult = result;
            // Render the response directly, without a fade callback or the
            // scoring-after-page detour used by normal answer submission.
            this._onNextScreenDone({ previousPageId: targetId });
        } catch (error) {
            this.$('.o_survey_error').removeClass('d-none');
            console.error('Exam review request failed', error);
        } finally {
            this.examReviewPending = false;
            this.preventEnterSubmit = false;
            this.$('.o_survey_form_content').stop(true, true).show();
        }
    },

    _submitForm(options = {}) {
        // Start Exam always uses Odoo's original handlers and request flow.
        if (this.options.isStartScreen || this.options.sessionInProgress) {
            return this._super(...arguments);
        }
        if (this.examReviewPending) {
            return;
        }
        const final = this.el.querySelector('button[data-exam-final="1"]');
        if (final && !options.previousPageId && !options.skipValidation && !options.examConfirmed) {
            return this._examConfirmation();
        }
        if (!options.examConfirmed) {
            this._examCloseConfirmation();
        }
        if (this.examReview && !options.skipValidation && !options.examConfirmed) {
            if (options.previousPageId) {
                return this._examReviewQuestion(options.previousPageId);
            }
            const form = this.el.querySelector('form');
            const ids = JSON.parse(form.dataset.examReviewIds || '[]');
            const current = form.querySelector('input[name="question_id"], input[name="page_id"]');
            const index = current ? ids.indexOf(Number(current.value)) : -1;
            if (index >= 0 && index + 1 < ids.length) {
                return this._examReviewQuestion(ids[index + 1]);
            }
            return this._examConfirmation();
        }
        return this._super(options);
    },

    destroy() {
        this._examCloseConfirmation();
        return this._super(...arguments);
    },
});
