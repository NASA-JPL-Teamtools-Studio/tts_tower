import sys
import unittest
from unittest.mock import MagicMock, patch, ANY

# ==========================================
# :: Imports
# ==========================================
from tts_tower.tower import Tower
from tts_tower.inputs.input_client import FailedClient

# ==========================================
# :: Concrete Implementation
# ==========================================
class ConcreteTower(Tower):
    def build_rule_metadata(self, dictionary_record):
        return {"meta": "data"}

# ==========================================
# :: Unit Tests
# ==========================================
class TestTower(unittest.TestCase):
    def setUp(self):
        self.tower = ConcreteTower()

    def test_add_input_client(self):
        self.tower.add_input_client('test_client', 'ClientClass', ['arg1'], {'kwarg1': 'val1'})
        self.assertEqual(len(self.tower.input_clients), 1)
        self.assertEqual(
            self.tower.input_clients[0], 
            ('test_client', 'ClientClass', ['arg1'], {'kwarg1': 'val1'})
        )

    def test_add_checker(self):
        checker = MagicMock()
        self.tower.add_checker(checker)
        self.assertEqual(len(self.tower.checkers), 1)
        self.assertEqual(self.tower.checkers[0], checker)

    @patch('tts_tower.tower.InputManager')
    def test_initialize_and_populate_clients(self, mock_im_cls):
        mock_icm = mock_im_cls.return_value.__enter__.return_value
        
        self.tower.add_input_client('c1', 'cls1', [], {})
        self.tower.add_input_client('c2', 'cls2', [], {})
        
        self.tower.initialize_and_populate_clients()
        
        self.assertEqual(mock_icm.add_client.call_count, 2)
        mock_icm.populate_all_clients.assert_called_once()
        self.assertEqual(self.tower.icm, mock_icm)

    @patch('tts_tower.tower.CheckerManager')
    @patch('tts_tower.tower.load_checkers')
    @patch('tts_tower.tower.util.reverse_prio_dict_merge')
    def test_run_success(self, mock_merge, mock_load, mock_cm_cls):
        mock_icm = MagicMock()
        self.tower.icm = mock_icm
        
        mock_rule_dict = MagicMock()
        mock_icm.get.return_value = mock_rule_dict
        
        mock_cm = mock_cm_cls.return_value
        
        # Configure consolidate_and_verify to not fail if called
        with patch.object(self.tower, 'consolidate_and_verify') as mock_consolidate:
            self.tower.run()
            
            mock_merge.assert_called()
            mock_load.assert_called()
            mock_cm_cls.assert_called_with(self.tower.checkers)
            mock_cm.set_rule_status_enum.assert_called()
            mock_cm.do_all_checks.assert_called_with(mock_icm)
            
            mock_icm.get.assert_called_with('rule_dictionary')
            self.assertEqual(self.tower.rules_role_manual, mock_rule_dict.rules)
            
            mock_consolidate.assert_called_once()

    def test_run_fails_with_bad_dictionary(self):
        self.tower.icm = MagicMock()
        self.tower.icm.get.return_value = FailedClient("DictionaryClient", Exception("Init failed"))
        
        self.tower.run_info = {}
        
        with patch('tts_tower.tower.util.reverse_prio_dict_merge'), \
             patch('tts_tower.tower.load_checkers'), \
             patch('tts_tower.tower.CheckerManager'):
            
            with self.assertRaises(TypeError) as cm:
                self.tower.run()
            
            self.assertIn("Failed to initialize a rule dictionary client", str(cm.exception))

    @patch('tts_tower.tower.consolidate_rule_results')
    @patch('tts_tower.tower.verify_rule_revisions')
    @patch('tts_tower.tower.RuleResults')
    def test_consolidate_and_verify(self, mock_rr_cls, mock_verify, mock_consolidate):
        # 1. Setup Mocks
        mock_icm = MagicMock()
        self.tower.icm = mock_icm
        mock_cm = MagicMock()
        self.tower.cm = mock_cm
        self.tower.RULE_STATUS = MagicMock()
        
        # Configure verify_rule_revisions to return a tuple of 3 lists
        # This fixes the "ValueError: not enough values to unpack"
        mock_verify.return_value = ([], [], [])

        # 2. Setup Data
        mock_rule_dict = MagicMock()
        mock_icm.get.return_value = mock_rule_dict
        
        rule_1_source = MagicMock()
        rule_1_source.row = {'Maturity': 'APPROVED'}
        
        rule_2_deleted = MagicMock()
        rule_2_deleted.title = "Deleted Rule Title"
        rule_2_deleted.rev = 5
        rule_2_deleted.row = {'Maturity': 'DELETED'}
        
        mock_rule_dict.rules = {
            'RULE-1': rule_1_source,
            'RULE-DELETED': rule_2_deleted
        }
        
        rr1 = MagicMock(id='RULE-1')
        mock_cm.get_all_rule_results.return_value = [rr1]
        
        # 3. Run Method
        self.tower.consolidate_and_verify()
        
        # 4. Assertions
        args, _ = mock_consolidate.call_args
        passed_results = args[0]
        
        self.assertEqual(len(passed_results), 2)
        self.assertEqual(passed_results[0].id, 'RULE-1')
        
        mock_rr_cls.assert_called_with('RULE-DELETED', 5, user_title="Deleted Rule Title")
        mock_verify.assert_called()

    @patch('tts_tower.tower.HtmlCompiler')
    @patch('tts_tower.tower.RuleResultContainer')
    @patch('tts_tower.tower.TowerKeyContainer')
    @patch('tts_tower.tower.GenericContainer')
    @patch('tts_tower.tower.consolidate_rule_reports')
    @patch('tts_tower.tower.DispositionContainer')
    def test_write_reports(self, mock_dispo_cont, mock_report_consolidate, mock_gen_cont, mock_key_cont, mock_rr_cont, mock_html_compiler):
        self.tower.verified_rr = [MagicMock(id='RULE-1', _reports={}, _dispositions=[])]
        self.tower.nonmatching_rr = []
        self.tower.bad_version_rr = []
        
        self.tower.rules_role_manual = {
            'RULE-1': MagicMock(crit='A', title='T', maturity='M')
        }
        
        self.tower.run_info = {'Time': 'Now'}
        
        self.tower.RULE_CRITICALITY = MagicMock()
        self.tower.RULE_MATURITY = [MagicMock(name='M', sort_order=1)]
        self.tower.RULE_STATUS = [MagicMock(name='S', sort_order=1)]
        
        mock_rr_cont_instance = mock_rr_cont.return_value
        mock_rr_cont_instance.sort.return_value = mock_rr_cont_instance 
        mock_rr_cont_instance.__iter__.return_value = [{'Criticality': 'A', 'Maturity': 'M', 'Status': 'S'}]
        
        mock_html_instance = mock_html_compiler.return_value

        self.tower.write_reports('output.html', 'Test Report')
        
        mock_rr_cont.assert_called()
        mock_key_cont.assert_called() 
        mock_gen_cont.assert_called()
        
        mock_html_compiler.assert_called_with('Test Report')
        self.assertEqual(mock_rr_cont_instance.sort.call_count, 3)
        mock_html_instance.render_to_file.assert_called_with('output.html')

if __name__ == '__main__':
    unittest.main()