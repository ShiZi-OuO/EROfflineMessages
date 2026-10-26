"""Local release checklist. Never turns registration/binding into a UI pass."""
import argparse
import json
from pathlib import Path


def evaluate(state):
    checks = {
        'frozen_runtime': state.get('binary_frozen_sha256') == 'b9e623b68ac2415df24bbcd5f7f67415c9cdbc1f5ff4e63ffc08feacf47b82e5',
        'frozen_data': state.get('pack_frozen_sha256') == '661a694ded9cac3b3bfa0bdcea520171a625020f6a3fbe9a741db294b0624f76',
        'host_tests': state.get('host_tests_passed') == 5,
        'archived_source_tests': state.get('archive_source_rebuild_passed') == 5,
        'two_new_native_readings': state.get('chinese_target_reading') == 'both_new_v10_readings_verified',
        'nearest_selection_explained': state.get('nearest_selection_diagnosis') == 'both_targets_read_with_unchanged_dll_and_payload',
        'english_reading': state.get('english') == 'same_record_ui_verified',
        'natural_cache_recovery': state.get('natural_expiry_recovery') == 'natural_clear_and_read_verified',
    }
    for kind in ('title','death','teleport','normal_restart'):
        checks[kind+'_three_rounds'] = type(state.get(kind+'_rounds_passed')) is int and state[kind+'_rounds_passed'] >= 3
    return dict(stable_finite_snapshot_acceptance=all(checks.values()),
        checks=checks, remaining=[k for k, v in checks.items() if not v],
        full_world_coverage=state.get('full_world_coverage') is True,
        external_publication_authorized=state.get('publication_authorized') is True,
        excluded_by_user={'fps_p99':state.get('fps_p99'),'one_hour':state.get('one_hour')},
        warning='This checks recorded acceptance states only. It does not create evidence, prove all-map coverage or authorize uploading.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=evaluate(json.loads(Path(a.state).read_text(encoding='utf-8')))
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
