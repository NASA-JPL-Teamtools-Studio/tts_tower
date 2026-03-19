#Standard Library Imports
from abc import ABC, abstractmethod
import pdb

#Installed Library Importsimport pdb
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

class DispositionItem(DataItem):
    """
    DataItem subclass representing a single disposition (e.g. check result) within a RuleResult.

    This item stores the core details of an individual check event, including the
    message, status (e.g., PASSED, FLAGGED), target object, and a test flag.

    :param tbd: tbd
    :type tbd: tbd
    """

    #Note that these data types won't hold. Maturity, Criticality, and status will
    #need to become their respective enums, Reports should become html_utils objects.
    #This is a stopgap for the experimental moment of starting to move Tower over
    #to data_utils
    DICT_VALID_KEYS = [
        ('message', str),
        ('status', str),
        ('target', (str, None)),
        ('flag', (str, None))
        ]

    TIME_FORMATS = {}
    NAME = 'Tower Disposition'

    STATUS_PALETTE = {
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
        Defines the default CSS styles for the HTML table row representing this item.
        Currently returns an empty dict (no custom row style).
        """
        return {}
    
    @property
    def time(self):
        """
        Required property for DataItem interface, but not used for dispositions.
        """
        return

    @property
    def time_str(self):
        """
        Required property for DataItem interface, but not used for dispositions.
        """
        return

    @property
    def default_html_cell_styles(self):
        """
        Defines default CSS styles for specific cells based on their content.
        
        Specifically colors the 'status' cell based on the `STATUS_PALETTE`.
        """
        return {
            'status': self.STATUS_PALETTE.get(self['status'].upper(), PALETTE['red']),
            }

class DispositionContainer(DataContainer):
    """
    DataContainer subclass for holding a collection of DispositionItem objects.

    Used to manage lists of dispositions attached to a rule result, primarily for
    rendering them in reports or structured data outputs.

    For parameters and types, see DataContainer docs
    """

    NAME = 'Disposition Container'
    DATA_ITEM_CLS = DispositionItem

    def _impl_init(self):
        """
        Implementation-specific initialization logic (currently a no-op).
        """
        return

    @property
    def repr_cols(self):
        """
        Returns the list of columns to be displayed in representations (e.g. tables).
        """
        return self._repr_cols

    @property
    def default_time_label(self):
        """
        Returns the default label for the time column (inherited/unused).
        """
        return self._default_time_label

class RuleResultItem(DataItem):
    """
    DataItem subclass representing the summary of a single Rule Check Result.

    This item contains high-level metadata about the rule execution, including
    the Rule ID, Criticality, Title, Maturity, Status, and links to any generated reports.

    :param tbd: tbd
    :type tbd: tbd
    """

    #Note that these data types won't hold. Maturity, Criticality, and status will
    #need to become their respective enums, Reports should become html_utils objects.
    #This is a stopgap for the experimental moment of starting to move Tower over
    #to data_utils
    DICT_VALID_KEYS = [
        ('Rule ID', str),
        ('Criticality', str),
        ('Title', str),
        ('Maturity', str),
        ('Status', str),
        ('Reports', str)
        ]

    TIME_FORMATS = {}
    NAME = 'Tower Rule Result'

    STATUS_PALETTE = {
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

    MATURITY_PALETTE = {
        'DRAFT': PALETTE['red'],
        'APPROVED': PALETTE['orange'],
        'IMPLEMENTED': PALETTE['orange'],
        'UNIT TESTED': PALETTE['orange'],
        'VERIFIED': PALETTE['green'],
        'UNKNOWN': PALETTE['red'],
        'DELETED': PALETTE['grey'],
        'NA': PALETTE['grey'],
    }

    CRITICALITY_PALETTE = {
        'A':   PALETTE['red'],
        'B':  PALETTE['orange'],
        'C':   PALETTE['yellow'],
        'I':    PALETTE['white'],
        'DELETED':  PALETTE['grey'], 
        'USER':  PALETTE['grey'], 
    }

    @property
    def default_html_row_style(self):
        """
        Defines the default CSS styles for the HTML table row representing this item.
        Currently returns an empty dict.
        """
        return {}
    
    @property
    def time(self):
        """
        Required property for DataItem interface, but not used for rule results.
        """
        return

    @property
    def time_str(self):
        """
        Required property for DataItem interface, but not used for rule results.
        """
        return

    @property
    def default_html_cell_styles(self):
        """
        Defines default CSS styles for cells based on their content values.
        
        Applies specific palettes to 'Criticality', 'Maturity', and 'Status' cells.
        """
        return {
            'Criticality': self.CRITICALITY_PALETTE.get(self['Criticality'].upper(), PALETTE['red']),
            'Maturity': self.MATURITY_PALETTE.get(self['Maturity'].upper(), PALETTE['red']),
            'Status': self.STATUS_PALETTE.get(self['Status'].upper(), PALETTE['red']),
            }

class RuleResultContainer(DataContainer):
    """
    DataContainer subclass for holding a collection of RuleResultItem objects.

    This container aggregates all rule results from a Tower run, providing structure for
    filtering, sorting, and rendering the final report table.

    For parameters and types, see DataContainer docs
    """

    NAME = 'Rule Result Container'
    DATA_ITEM_CLS = RuleResultItem

    def _impl_init(self):
        """
        Implementation-specific initialization logic (currently a no-op).
        """
        return

    @property
    def repr_cols(self):
        """
        Returns the list of columns to be displayed in representations (e.g. tables).
        """
        return self._repr_cols

    @property
    def default_time_label(self):
        """
        Returns the default label for the time column (inherited/unused).
        """
        return self._default_time_label