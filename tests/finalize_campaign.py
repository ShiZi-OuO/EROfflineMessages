import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from finalize_campaign import clear_inherited_gameplay_claims


class ProvenanceClaims(unittest.TestCase):
    def test_changed_pack_cannot_inherit_runtime_pass(self):
        value=dict(merged_pack_loaded_in_game=True,sampled_reading_and_lifecycle_verified=True,
                   gameplay_evidence='old-record.json',current_install_individual_ui_witnesses=['old-ui'],
                   new_bulk_individual_ui_witnesses=3,cohorts=[{'records':23385}])
        result=clear_inherited_gameplay_claims(value)
        self.assertFalse(result['merged_pack_loaded_in_game'])
        self.assertFalse(result['sampled_reading_and_lifecycle_verified'])
        self.assertNotIn('gameplay_evidence',result)
        self.assertNotIn('current_install_individual_ui_witnesses',result)
        self.assertEqual(result['base_pack_historical_gameplay_evidence']['new_bulk_individual_ui_witnesses'],3)
        self.assertEqual(result['cohorts'],[{'records':23385}])


if __name__=='__main__':unittest.main()
