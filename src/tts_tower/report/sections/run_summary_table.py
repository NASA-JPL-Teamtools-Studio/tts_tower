import pdb

from tts_html_utils.core.components.table import PowerTable, Row, Cell

from tts_tower.rule_results import RULE_STATUS, RuleResults
from tts_tower.report.resource import get_tower_stylesheet
from tts_tower.report.sections.base import TowerSection
#TODO: Transition the rest of these over to html_utils
from tts_html_utils.core.components import (
    Span, Strong,
    Div, Link, HorizontalBreak, LineBreak
)
from tts_tower.report.utilities import split_with_hr

T_ROW_PRIME = '<tr class="prime_row"><td><strong>{}:</strong></td><td class="value">{}</td></tr>'
T_ROW_EXTRA = '<tr class="extra_row"><td></td><td class="value">{}</td></tr>'

#================================================
# :: Run Info Summary
#================================================
class RunSummaryTableSection(TowerSection):
    def __init__(self, run_info):
        super().__init__('Run Info')
        self.add_component(RunInfoComponent(run_info))

class RunInfoComponent(PowerTable):
    def __init__(self, run_info):
        self.run_info = run_info
        super().__init__()

        for _key, _value in self.run_info.items():
            if isinstance(_value, list):
                if len(_value) == 0:
                    continue
                extra_values = _value[1:]
                _value = _value[0]
            else:
                extra_values = None
            # Always write in a first row
            self.add_row([Cell(children=_key, class_name='bold'), _value])
            if extra_values is not None:
                for _e_value in extra_values:
                    self.add_row(['', _e_value])

#================================================
# :: Rule Results Summary
#================================================
class RuleResultSummaryTableSection(TowerSection):
    def __init__(self, rule_results, source_rules, section_reports=None, expandable=True):
        super().__init__('Rule Results', id='RR_table_section', source_rules=source_rules)
        self.add_component(RuleResultsComponent(rule_results, source_rules, section_reports=section_reports, expandable=expandable, add_filters='local', add_sorting='local'))

class RuleResultsComponent(PowerTable):
    DEFAULT_CLASS = ['rule-table', 'report-table', 'alternating']
    STYLESHEETS = [get_tower_stylesheet('rule_result_table.css')]
    def __init__(self, rule_results, source_rules, section_reports=None, expandable=True, add_filters=None, add_sorting=None):
        super().__init__(add_filters=add_filters, add_sorting=add_sorting)
        # Start with unrecognized status, shouldn't happen but we don't want to miss these if they do

        for source_rule_id, source_rule in source_rules.items():
            if len([rr for rr in rule_results if rr.id == source_rule_id]) == 0:
                rule_results.append(
                    RuleResults(source_rule_id, source_rule.rev, user_title=source_rule.title)
                    )

        rules_in_order = sorted(
            sorted(
                sorted(
                    rule_results, key=lambda x: x.id
                ),
                key=lambda x: source_rules.get(x.id.upper()).level if x.id.upper() in source_rules else 'U'
            )[::-1],
            key=lambda x: x.status.sort_order
        )[::-1]
        
        for i, result in enumerate(rules_in_order):
            rule = source_rules.get(result.id.upper())
            row = []
            if rule is not None:
                row.append(Cell(Link(result.id, rule.url), extra_class_name='center'))
                row.append(Cell(children=rule.crit, extra_class_name=['center', 'bold', f'crit-{rule.level}', 'border-col']))
                rule_title = rule.title
            else:
                row.append(Cell(children=result.id, extra_class_name='center'))
                row.append(Cell(children='USER', extra_class_name=['center', 'bold', 'crit-I', 'border-col']))
                rule_title = result.user_title
            row.append(Cell(children=rule_title, extra_class_name='rule-title'))
            _status = result.status.name
            if rule is not None:
                _maturity = rule.maturity.upper()
            else:
                _maturity = 'Unknown'

            _maturity_classname = _maturity.lower().replace(' ','-')
            row.append(Cell(children=_maturity, extra_class_name=['center', 'bold', f'cell-{_maturity_classname}', 'border-col']))
            row.append(Cell(children=_status, extra_class_name=['center', 'bold', f'cell-{_status.lower()}', 'border-col']))

            if section_reports:
                section_list = []
                for report_name in result.get_reports():
                    section_matches = [_ for _ in section_reports if _.name == report_name]
                    if len(section_matches) < 1:
                        continue
                    section_id = section_matches[0].id
                    section_link = Link(report_name, f'#{section_id}-section-header', new_tab=False)
                    section_link.attr['onclick'] = f"openTab(event, '{section_id}Tab')"
                    section_list.append(section_link)
                if len(section_list) == 0:
                    section_list.append(Span('None'))
                row.append(Cell(children=split_with_hr(section_list)))

            if expandable:
                self.add_row(Row(children=row, extra_class_name=['collapsible', 'active-clicked'], id=f'RR_{result.id.replace(" ", "_")}'))
                desc_cell = Cell(self.make_description_row(rule, result))
                desc_cell.attr['colspan'] = '100%'
                self.add_row(Row(children=desc_cell, extra_class_name=['rule-table-hidden', 'non-alternating', 'no-hover'], id=f'RR_{result.id.replace(" ", "_")}_details'))
            else:
                self.add_row(Row(children=row, id=f'RR_{result.id.replace(" ", "_")}'))

        header_names = ['Rule ID', 'CAT', 'Title', 'Maturity', 'Status']
        if section_reports:
            header_names.insert(4, 'Reports')
        self.add_header(header_names)

    @staticmethod
    def make_description_row(rule, result):
        breakout = []
        if rule is not None:
            breakout.extend([Span(rule.make_breakout()), HorizontalBreak()])

        dispo_list = []
        for dispo in result.dispositions:
            dispo_list.append(HorizontalBreak())
            if dispo.status is not None:
                status_class = f'cell-{dispo.status.name.lower()}'
            else:
                status_class = None
            dispo_list.append(Div(Span(dispo.text), extra_class_name=status_class))
        breakout.append(
            Div(
                [
                    Div(Strong('All Dispositions')),
                    *dispo_list,
                    HorizontalBreak()
                ],
                extra_class_name='dispos'
            )
        )
        return breakout

