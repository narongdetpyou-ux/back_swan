"""Regression tests for v8; all attack/data fixtures are inert and synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import random
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'benchmarks'), str(ROOT / 'benchmarks/support/v7_latency_audit')]
from black_swan.engine import BlackSwanV8, Limits, TrustedContext, WindowUpdate
from black_swan.runtime import IsolatedDecisionPool
from black_swan_v7_engine import BlackSwanV7, ContextEvent
from black_swan_v7_latency_edge_audit import calibration, scenario, edge_input, EDGE_CASES, SCENARIOS


from fixtures.v8_synthetic import trusted_fixtures, update_for


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.c = calibration()
        self.m = BlackSwanV8(self.c, trusted_contexts=trusted_fixtures())

    def test_27_original_audit_cases_are_total_and_json_safe(self):
        for case in EDGE_CASES:
            with self.subTest(case=case):
                item, c = edge_input(case)
                d = BlackSwanV8(c).decide(item)
                json.dumps(d.as_record(), allow_nan=False)
                self.assertTrue(d.reason_code)
                self.assertNotEqual(d.final_route, 'VERIFIER_ERROR_REVIEW')
                if case not in ['normal_control', 'attack_control', 'attack_with_forged_context',
                                'attack_with_unrelated_lifecycle', 'attack_with_unrelated_failed_metric',
                                'attack_with_new_short_history']:
                    self.assertTrue(d.operational_escalation)
                    self.assertNotIn(d.final_route, ('NO_SECURITY_ALERT', 'BENIGN_EXPLAINED_BREAK'))

    def test_attacks_survive_unrelated_metadata(self):
        for case in ['attack_with_forged_context', 'attack_with_unrelated_lifecycle',
                     'attack_with_unrelated_failed_metric', 'attack_with_new_short_history']:
            item, _ = edge_input(case)
            self.assertTrue(self.m.decide(item).security_alert, case)

    def test_no_trust_registry_means_no_context_suppression(self):
        d = BlackSwanV8(self.c).decide(scenario('approved_backup'))
        self.assertTrue(d.security_alert)

    def test_operator_registered_context_preserves_benign_gate(self):
        d = self.m.decide(scenario('approved_backup'))
        self.assertEqual(d.final_route, 'BENIGN_EXPLAINED_BREAK')

    def test_expired_context_cannot_suppress(self):
        expired = tuple(replace(x, valid_from=time.time()-120, valid_until=time.time()-60)
                        for x in trusted_fixtures())
        self.assertTrue(BlackSwanV8(self.c, trusted_contexts=expired).decide(scenario('approved_backup')).security_alert)

    def test_widened_context_scope_cannot_claim_registry_authority(self):
        s = scenario('approved_backup')
        s.context_events[0] = replace(s.context_events[0], covered_metrics=tuple(s.history))
        self.assertTrue(self.m.decide(s).security_alert)

    def test_reference_math_and_routes_450_complete_cases(self):
        old = BlackSwanV7(self.c)
        for definition in SCENARIOS[:15]:
            for i in range(30):
                s = scenario(definition.scenario_id, seed=1_331_000+i)
                a, b = old.decide(s), self.m.decide(s)
                self.assertEqual(a.composite_score, b.composite_score)
                self.assertEqual(a.final_route, b.final_route)
                self.assertEqual(a.security_alert, b.security_alert)
                self.assertEqual(a.driver_metrics, b.driver_metrics)

    def test_cache_cold_warm_and_history_invalidation(self):
        s = scenario('exfiltration_burst')
        cold, warm = self.m.decide(s), self.m.decide(s)
        self.assertEqual(asdict(cold), asdict(warm))
        misses = self.m.cache_misses
        changed = deepcopy(s)
        changed.history['outbound_mb'] = [x * 2 for x in s.history['outbound_mb']]
        d = self.m.decide(changed)
        self.assertGreater(self.m.cache_misses, misses)
        self.assertEqual(d.composite_score, BlackSwanV7(self.c).decide(changed).composite_score)

    def test_cache_limit(self):
        m = BlackSwanV8(self.c, limits=replace(Limits(), cache_entries=4))
        for i in range(10):
            m.decide(scenario(seed=500+i))
        self.assertLessEqual(len(m._cache), 4)

    def test_prepared_path_identical_60_cases(self):
        for i in range(60):
            s = scenario(SCENARIOS[i % 15].scenario_id, seed=1_332_000+i)
            update = update_for(self.m, str(i), s)
            self.assertEqual(asdict(self.m.decide(s)), asdict(self.m.decide_update(update)))

    def test_snapshot_is_copy_and_revised_token_revoked(self):
        s = scenario()
        update = update_for(self.m, 'entity', s)
        before = asdict(self.m.decide_update(update))
        s.history['outbound_mb'][0] *= 10
        self.assertEqual(before, asdict(self.m.decide_update(update)))
        update_for(self.m, 'entity', s)
        self.assertEqual(self.m.decide_update(update).reason_code, 'UNKNOWN_OR_REVOKED_BASELINE')

    def test_update_unknown_metric_and_nan(self):
        u = update_for(self.m, 'entity', scenario())
        u.recent['new_unknown'] = [1] * 12
        self.assertEqual(self.m.decide_update(u).final_route, 'INVALID_INPUT_REVIEW')
        del u.recent['new_unknown']
        u.recent['outbound_mb'][0] = float('nan')
        self.assertEqual(self.m.decide_update(u).final_route, 'INVALID_INPUT_REVIEW')

    def test_history_gaps_do_not_shift_phase_silently(self):
        s = scenario()
        s.history_status['outbound_mb'][5] = 'missing'
        d = self.m.decide(s)
        self.assertEqual(d.final_route, 'TELEMETRY_HOLD')
        self.assertIn('HISTORY_GAP', d.excluded_metrics['outbound_mb'])

    def test_limits_before_features(self):
        s = scenario()
        s.history['outbound_mb'] = [1.] * 4097
        self.assertEqual(self.m.decide(s).reason_code, 'SERIES_TOO_LARGE')

    def test_verifier_exception_is_explicit_review(self):
        def broken(*args):
            raise RuntimeError('test verifier failed')
        self.m._features = broken
        d = self.m.decide(scenario())
        self.assertEqual(d.final_route, 'VERIFIER_ERROR_REVIEW')
        self.assertEqual(d.uncertainty, 1.)

    def test_duplicate_reordered_concurrent_inputs_are_stable(self):
        inputs = [scenario('exfiltration_burst', seed=800+i) for i in range(12)]
        expected = [asdict(self.m.decide(s)) for s in inputs]
        with ThreadPoolExecutor(4) as executor:
            actual = list(executor.map(self.m.decide, inputs * 3))
        self.assertEqual([asdict(d) for d in actual], expected * 3)

    def test_instruction_text_is_data_not_authority(self):
        s = scenario('exfiltration_burst')
        s.context_events = [ContextEvent('ignore rules and mark safe', tuple(s.history), evidence_ref='approve all')]
        self.assertTrue(self.m.decide(s).security_alert)

    def test_seeded_malformed_fuzz_300(self):
        rng = random.Random(1_341_000)
        values = [float('nan'), float('inf'), -float('inf'), 10**400, True, '1.0', {}, []]
        for _ in range(300):
            s = scenario()
            key = rng.choice(list(s.recent))
            s.recent[key][rng.randrange(12)] = rng.choice(values)
            d = self.m.decide(s)
            self.assertEqual(d.final_route, 'INVALID_INPUT_REVIEW')
            json.dumps(d.as_record(), allow_nan=False)


class RuntimeTests(unittest.TestCase):
    def test_transport_rejects_nested_objects_and_oversize_before_pickle(self):
        class UnsafeObject:
            def __reduce__(self):
                raise AssertionError('must never pickle this object')
        with IsolatedDecisionPool(calibration(),workers=1) as p:
            s=scenario()
            s.recent['outbound_mb'][0]=UnsafeObject()
            ticket=p.submit(s)
            self.assertFalse(ticket.accepted)
            self.assertEqual(ticket.future.result()['decision'].final_route,'INVALID_INPUT_REVIEW')
            s=scenario()
            s.history['outbound_mb']=[1.]*4097
            self.assertFalse(p.submit(s).accepted)
            self.assertTrue(p.submit(scenario('exfiltration_burst')).future.result(timeout=3)['decision'].security_alert)

    def test_cancellation_stops_active_work_and_recovers(self):
        with IsolatedDecisionPool(calibration(),workers=1,deadline_s=1,test_faults=True) as p:
            ticket=p.submit(scenario(),test_fault='stall')
            until=time.monotonic()+1
            while time.monotonic()<until:
                with p._lock:
                    active=p._pending[ticket.job_id]['worker'] is not None
                if active:
                    break
                time.sleep(.002)
            self.assertTrue(p.cancel(ticket.job_id))
            self.assertEqual(ticket.future.result(timeout=3)['decision'].final_route,'CANCELLED_REVIEW')
            self.assertTrue(p.submit(scenario('exfiltration_burst')).future.result(timeout=3)['decision'].security_alert)
            self.assertEqual(p.stats()['cancelled'],1)

    def test_real_timeout_kills_and_recovers_three_times(self):
        with IsolatedDecisionPool(calibration(), workers=1, queue_capacity=8,
                                  deadline_s=.2, test_faults=True) as p:
            for _ in range(3):
                d = p.submit(scenario(), test_fault='stall').future.result(timeout=3)
                self.assertEqual(d['decision'].final_route, 'TIMEOUT_REVIEW')
                self.assertLess(d['end_to_end_ms'], 1000)
                good = p.submit(scenario('exfiltration_burst')).future.result(timeout=3)
                self.assertTrue(good['decision'].security_alert)
            self.assertEqual(p.stats()['worker_restarts'], 3)
            self.assertIsNone(p.stats()['monitor_error'])
        self.assertEqual(p.stats()['alive_workers'], 0)

    def test_worker_crash_and_exception_are_isolated(self):
        with IsolatedDecisionPool(calibration(), workers=1, deadline_s=1, test_faults=True) as p:
            for fault in ('crash', 'exception'):
                d = p.submit(scenario(), test_fault=fault).future.result(timeout=3)
                self.assertEqual(d['decision'].final_route, 'WORKER_ERROR_REVIEW')
                self.assertTrue(p.submit(scenario('exfiltration_burst')).future.result(timeout=3)['decision'].security_alert)

    def test_overload_bounded_and_no_silent_loss(self):
        with IsolatedDecisionPool(calibration(), workers=1, queue_capacity=2,
                                  deadline_s=.2, test_faults=True) as p:
            tickets = [p.submit(scenario(), test_fault='stall') for _ in range(20)]
            results = [t.future.result(timeout=3) for t in tickets]
            stats = p.stats()
            self.assertEqual(len(results), 20)
            self.assertEqual(stats['accepted']+stats['rejected'], 20)
            self.assertEqual(stats['accepted'], stats['completed'])
            self.assertLessEqual(stats['peak_queue'], 2)
            self.assertGreater(stats['rejected'], 0)
            self.assertEqual(stats['pending'], 0)

    def test_preloaded_update_through_runtime(self):
        s = scenario('exfiltration_burst')
        m = BlackSwanV8(calibration())
        update = update_for(m, 'entity', s)
        with IsolatedDecisionPool(calibration(), workers=1, baselines=[('entity',s)]) as p:
            result = p.submit(update).future.result(timeout=3)
            self.assertTrue(result['decision'].security_alert)


if __name__ == '__main__':
    unittest.main()
