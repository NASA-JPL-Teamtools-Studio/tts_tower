#Standard Library Imports
import hashlib
import json
import pdb

#Installed Dependency Imports
import pandas as pd

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
from tts_tower import util
from tts_tower.checkers.util import load_checkers
from tts_tower.checkers.checker_manager import CheckerManager
from tts_tower.rule_results import (
    consolidate_rule_results,
    verify_rule_revisions,
    consolidate_rule_reports,
)

log = create_logger(__name__)

def assert_exception_is_raised(method, args, kwargs, expected_exception_message, expected_exception_type):
    actual_exception_message = ''
    try:
        method(*args, **kwargs)
    except expected_exception_type as e:
        actual_exception_message = str(e)
    if actual_exception_message == expected_exception_message:
        assert actual_exception_message == expected_exception_message
    else:
        pdb.set_trace()

#need to keep this here so pytest will run. Can remove
#when all tests are no longer trying to import it.
def assert_records_match_hash():
    return

def set_up_common_checker_test(icm, checkers):    
    run_info = {}
    run_info = util.reverse_prio_dict_merge(run_info, icm.get_run_info())
    rule_dictionary = icm.get('rule_dictionary')
    checkers = load_checkers(checkers)
    checkers = CheckerManager(checkers)
    checkers.do_all_checks(icm)
    all_rr = checkers.get_all_rule_results()
    consolidated_rr = consolidate_rule_results(all_rr)
    verified_rr, nonmatching_rr, bad_version_rr = verify_rule_revisions(consolidated_rr, rule_dictionary.rules)
    verified_reports = consolidate_rule_reports(verified_rr, {})
    assert nonmatching_rr == []
    assert bad_version_rr == []
    return verified_rr, nonmatching_rr, bad_version_rr, icm

def set_up_icms(rule_id, setup_mthd, test_file_dir, filter_for_rule_id=True):
    rule_id_dirpath = rule_id.lower().replace('-','_')
    passed = setup_mthd(test_file_dir.joinpath(f'{rule_id_dirpath}/passed'), rule_id)
    flagged = setup_mthd(test_file_dir.joinpath(f'{rule_id_dirpath}/flagged'), rule_id)
    violating = setup_mthd(test_file_dir.joinpath(f'{rule_id_dirpath}/violating'), rule_id)

    passed = [rr for rr in passed[0] if rr._RuleResults__status.name == 'PASSED']
    flagged = [rr for rr in flagged[0] if rr._RuleResults__status.name == 'FLAGGED']
    violating = [rr for rr in violating[0] if rr._RuleResults__status.name == 'VIOLATING'] 

    if filter_for_rule_id:
        passed = [rr for rr in passed if rr.id == rule_id]
        flagged = [rr for rr in flagged if rr.id == rule_id]
        violating = [rr for rr in violating if rr.id == rule_id]

    return passed, flagged, violating

def assert_expected_result_counts(passed, failed, violating, n_passed, n_flagged, n_violated):
    assert len(passed) == n_passed
    assert len(failed) == n_flagged
    assert len(violating) == n_violated