#Standard Library Imports
from abc import ABC, abstractmethod
import pdb
from datetime import datetime

#JPL Imports
from jpl_time import Time

#Teamtool Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

log = create_logger(__name__)


PALETTE = {
    'green': {'background-color': '#9FC793', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'grey': {'background-color': 'lightgray', 'color': 'black', 'font-weight': 'bold', 'text-align': 'center'},
    'yellow': {'background-color': '#FFF0B5', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'orange': {'background-color': '#F5C692', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'red': {'background-color': '#E89392', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    'white': {'background-color': '#FFFFF', 'color': '#333333', 'font-weight': 'bold', 'text-align': 'center'},
    }

class TowerKeyItem(DataItem):
    """
    Data item representing a single entry in a Tower Legend/Key table.
    
    Used to display definitions for Status, Maturity, and Criticality enums
    within the HTML report.
    """

    #Note that these data types won't hold. Maturity, Criticality, and status will
    #need to become their respective enums, Reports should become html_utils objects.
    #This is a stopgap for the experimental moment of starting to move Tower over
    #to data_utils
    DICT_VALID_KEYS = []

    TIME_FORMATS = {}
    NAME = 'Tower Disposition'

    PALETTE = {
        'DELETED': PALETTE['grey'],
        'PENDING': PALETTE['grey'],
        'INFO_ONLY': PALETTE['grey'],
        'NA': PALETTE['grey'],
        'PASSED': PALETTE['green'],
        'FLAGGED': PALETTE['orange'],
        'VIOLATING': PALETTE['red'],
        'ERROR': PALETTE['red'],
        'MISMATCH': PALETTE['red']
    }

    @property
    def default_html_row_style(self):
        """
        Returns the default CSS style for the row.
        
        :return: Empty dictionary.
        :rtype: dict
        """
        return {}
    
    @property
    def time(self):
        """
        Unused time property for this item type.
        """
        return

    @property
    def time_str(self):
        """
        Unused time string property for this item type.
        """
        return

    @property
    def default_html_cell_styles(self):
        """
        Proxies to ``default_html_cell_styles_override`` to allow dynamic styling injection.
        
        This property exists to satisfy the ``power_table`` interface while allowing
        the container to inject specific styles based on the Enum values via monkey-patching.
        
        :return: The result of the override method.
        :rtype: dict
        """
        #Why did we do it this way? Becaust power_table expects
        #this to be an attribute since we made it a @property elsewhere, 
        #but I can't override it here. It was either this or
        #make a separate key for every class, and who wants that?
        return self.default_html_cell_styles_override()

    def default_html_cell_styles_override(self):
        """
        Placeholder method intended to be overwritten by the parent container
        during initialization to apply specific Enum-based styling.
        """
        return

class TowerKeyContainer(DataContainer):
    """
    Container class for generating Legend/Key tables in Tower reports.

    This container translates Tower Enums (like Status, Maturity, Criticality)
    into ``DataContainer`` tables for the HTML report.
    """

    NAME = 'Tower Key Container'
    DATA_ITEM_CLS = TowerKeyItem

    def _impl_init(self):
        """
        Implementation initialization (No-op).
        """
        return

    @property
    def repr_cols(self):
        """
        Returns the columns to be represented in the output table.
        """
        return self._repr_cols

    @property
    def default_time_label(self):
        """
        Returns the default time label (if any).
        """
        return self._default_time_label

    def from_enum(self, enum, name_label):
        """
        Populates the container based on a Tower-compatible Enum.

        This method:
        1. Creates records for every item in the Enum.
        2. Sorts them based on the Enum's internal sort order.
        3. Dynamically injects a ``default_html_cell_styles_override`` method into
           each record instance to apply the styles defined in the Enum.

        :param enum: The Enum class containing Tower configuration (must have .name, .description, and .style attributes).
        :type enum: Enum
        :param name_label: The header label to use for the name column (e.g., 'Status', 'Maturity').
        :type name_label: str
        """
        self.records = sorted(
            [TowerKeyItem({name_label: x.name, '': x.description}) for x in enum],
            key=lambda x: enum.get(x[name_label]), reverse=True)
        for r in self.records: 
            #pass r like that or else it'll pass by reference and all
            #rows get the same style
            def default_html_cell_style(r=r):
                return {name_label: enum.get(r[name_label]).style, '': {}}
            r.default_html_cell_styles_override = default_html_cell_style

        self._repr_cols = [name_label, '']