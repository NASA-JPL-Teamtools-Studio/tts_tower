#Standard Library Imports
from uuid import uuid4
import pdb

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_html_utils.core.components import (
    HtmlComponent,
    Div,
    Paragraph,
    Span,
    Strong,
    HorizontalBreak,
    Button,
    Link,
    PowerTable, Row, Cell,
)
from tts_utilities.util import as_list

logger = create_logger(__name__)

class TowerSection:
    DESCRIPTION=None
    DOCUMENTATION = None

    STYLESHEETS = []

    def __init__(self, name, components=None, contributors=None, id=None, source_rules=None):
        self.source_rules = source_rules
        self.name = name
        self.id = id or str(uuid4())
        self._components = as_list(components or [])
        self._contributors = as_list(contributors or [])

    @property
    def components(self):
        return self._components

    def add_component(self, new_component):
        new_component.parent_id = self.id
        self._components += as_list(new_component)

    @property
    def rendered(self):
        return self.render()

    def render(self):
        all_components = []
        # >> Contributing Checks
        if self._contributors:
            contrib_table = PowerTable(extra_class_name=['top_contrib'])
            #contrib_table.add_header(column_names=['Rule Name', 'Rule Status'])
            contrib_table.add_superheader('Contributing Rules')
            for result in self._contributors:
                table_link =Link(result.id, f'#RR_{result.id.replace(" ", "_")}', new_tab=False)
                table_link.attr['onclick'] = f"openTab(event, 'RR_table_sectionTab')"
                if result.id in self.source_rules.keys():
                    if result.user_title is None:
                        title = self.source_rules[result.id].title
                    elif result.user_title is None:
                        title = '???'
                    crit = self.source_rules[result.id].crit
                    maturity = self.source_rules[result.id].maturity
                else:
                    title = result.user_title
                    crit = '?'
                    maturity = '?'

                maturity = maturity.lower().replace(' ','-')
                contrib_table.add_row(
                    Row(children=[
                        Cell(children=table_link),
                        Cell(children=crit, extra_class_name=['center', 'bold', f'cell-{crit.lower()}', 'border-col']),
                        Cell(children=title),
                        Cell(children=maturity, extra_class_name=['center', 'bold', f'cell-{maturity}', 'border-col']),
                        Cell(children=result.status.name, extra_class_name=['center', 'bold', f'cell-{result.status.name.lower()}', 'border-col']),
                    ])
                )
            all_components.append(contrib_table)

        # >> Description
        if self.DESCRIPTION is not None:
            if isinstance(self.DESCRIPTION, HtmlComponent):
                desc = self.DESCRIPTION
            else:
                desc = Paragraph(self.DESCRIPTION)
            full_desc = Div([Span(Strong('Description:')), desc], extra_class_name='top_description')
            all_components.append(full_desc)

        if self.DOCUMENTATION is not None:
            docs = Div(self.DOCUMENTATION, extra_class_name='top_documentation')
            docs_button = Button("Click for Documentation", extra_class_name=['top_documentation', 'collapsible',' active-clicked'])
            all_components.extend([docs_button, docs])

        # Add a divider between top and components
        all_components.append(HorizontalBreak())

        # >> Sub-report components
        all_components += self.components
        return '\n'.join([component.render() for component in all_components])

    def get_stylesheets(self):
        return list(set(self.STYLESHEETS + sum([_.recurse_stylesheets() for _ in self.components], [])))
