from odoo import models, api


class HiredSelectionDecisionReport(models.AbstractModel):
    _name = 'report.hr_recruitment_custom.hired_selection_decision_report'
    _description = 'Selection Decision Report (قرار اختيار)'

    @api.model
    def _get_report_values(self, docids, data=None):
        decisions = self.env['hr.selection.decision'].browse(docids)
        reports = []

        for decision in decisions:
            rows = []
            idx = 0
            for applicant in decision.applicant_ids:
                candidate = applicant.candidate_id
                idx += 1

                # Take the most recently completed education entry for
                # university / specialization (falls back to empty).
                latest_edu = candidate.education_ids.sorted(
                    key=lambda e: e.graduation_year or '0', reverse=True
                )[:1]

                rows.append({
                    'index': idx,
                    'nationality_no': candidate.nationality_no,
                    'name': candidate.partner_name or applicant.partner_name or '',
                    'specialization': latest_edu.specialization_id.name if latest_edu else '',
                    'university': latest_edu.university if latest_edu else '',
                    # 'degree': decision.degree or '',
                })

            reports.append({
                'decision': decision,
                'rows': rows,
                'count': len(rows),
                'first_name': rows[0]['name'] if rows else '',
                'last_name': rows[-1]['name'] if rows else '',
            })

        return {
            'doc_ids': docids,
            'doc_model': 'hr.selection.decision',
            'reports': reports,
            'company': self.env.company,
        }