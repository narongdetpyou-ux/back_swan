#!/usr/bin/env python3
"""Audit of saved Black Swan v7; standard library, Python 3.12.

Put the original engine, benchmark and manifest in ./sources, then run:
  python3 black_swan_v7_latency_edge_audit.py --output v7_latency_edge_results.json

The subprocess exception catcher is TEST INFRASTRUCTURE, not an engine fix.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import heapq
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import queue
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'sources'
sys.path.insert(0, str(SOURCES))
import black_swan_v7_engine as engine_module
from black_swan_v7_engine import BlackSwanV7, Calibration, ContextEvent, ScenarioInput
from black_swan_v7_benchmark import SCENARIOS, generate_scenario

EXPECTED_HASHES = {
    'black_swan_v7_engine.py': '9f0d58ebad4f09f7be1be23e7b76520f904472f8e877391d8895c872cedbe663',
    'black_swan_v7_benchmark.py': '0981be09b87cf875eae26110c068530d116063d06533b36137f1762aef0d2977',
    'black_swan_v7_manifest.json': '91c5a1cc435cbb69228265b5a99d59601f538098f7b70cbe280f6d912c2399c3',
}
DEFINITIONS = {d.scenario_id: d for d in SCENARIOS}
MIX = ['normal_control', 'approved_backup', 'password_spray', 'slow_exfiltration',
       'correlated_subthreshold', 'planned_cloud_drift', 'stale_context_exfiltration']


def calibration():
    return Calibration(**json.loads((SOURCES / 'black_swan_v7_manifest.json').read_text())['calibration'])


def scenario(name='normal_control', seed=984021, history_hours=168, window_hours=12):
    return generate_scenario(DEFINITIONS[name], seed=seed,
                             history_hours=history_hours, window_hours=window_hours)


def pool():
    return [scenario(name, 771001 + j) for j in range(12) for name in MIX]


def quantile(xs, q):
    values = sorted(xs)
    p = (len(values) - 1) * q
    lo, hi = math.floor(p), math.ceil(p)
    return values[lo] * (hi - p) + values[hi] * (p - lo) if hi != lo else values[lo]


def summary(ns):
    ms = [n / 1e6 for n in ns]
    return {'count': len(ms), 'mean_ms': statistics.mean(ms),
            'p50_ms': quantile(ms, .50), 'p95_ms': quantile(ms, .95),
            'p99_ms': quantile(ms, .99), 'max_ms': max(ms)}


def timed_calls(model, inputs, n, serialize=False):
    samples = []
    routes = Counter()
    wall_start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    for i in range(n):
        item = inputs[i % len(inputs)]
        start = time.perf_counter_ns()
        decision = model.decide(item)
        if serialize:
            json.dumps(decision.as_record(), allow_nan=False)
        samples.append(time.perf_counter_ns() - start)
        routes[decision.final_route] += 1
    elapsed = (time.perf_counter_ns() - wall_start) / 1e9
    cpu = (time.process_time_ns() - cpu_start) / 1e9
    return {**summary(samples), 'elapsed_s': elapsed, 'cpu_s': cpu,
            'throughput_decisions_per_s': n / elapsed,
            'route_counts': dict(routes), 'raw_latency_ns': samples}


def stage_profile(model, inputs, n=500):
    original_features = engine_module.extract_features
    original_context = engine_module._context_covers_evidence
    counters = {'features_ns': 0, 'context_ns': 0, 'context_calls': 0}

    def measured_features(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_features(*args, **kwargs)
        finally:
            counters['features_ns'] += time.perf_counter_ns() - start

    def measured_context(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_context(*args, **kwargs)
        finally:
            counters['context_ns'] += time.perf_counter_ns() - start
            counters['context_calls'] += 1

    engine_module.extract_features = measured_features
    engine_module._context_covers_evidence = measured_context
    try:
        measured = timed_calls(model, inputs, n)
    finally:
        engine_module.extract_features = original_features
        engine_module._context_covers_evidence = original_context
    total_ns = sum(measured['raw_latency_ns'])
    return {'n': n, 'mean_total_ms': total_ns / n / 1e6,
            'mean_features_ms': counters['features_ns'] / n / 1e6,
            'mean_context_ms': counters['context_ns'] / n / 1e6,
            'mean_other_ms': (total_ns - counters['features_ns'] - counters['context_ns']) / n / 1e6,
            'feature_fraction': counters['features_ns'] / total_ns,
            'context_calls': counters['context_calls'],
            'note': 'Separate instrumented run. Context covers two passes; other includes policy/ledger and wrappers.'}


def scaled_input(metric_count, history_hours, window_hours=12):
    base = scenario(history_hours=history_hours, window_hours=window_hours)
    keys = sorted(base.history)
    h, r = {}, {}
    for i in range(metric_count):
        original = keys[i % len(keys)]
        key = f'{original}__replica_{i}'
        h[key], r[key] = list(base.history[original]), list(base.recent[original])
    return ScenarioInput('compute_stress_only', h, r)


def compute_worker(worker_id, n, ready, start_event, results):
    try:
        model, inputs = BlackSwanV7(calibration()), pool()
        for i in range(30):
            model.decide(inputs[i % len(inputs)])
        ready.put({'worker': worker_id, 'ok': True})
        if not start_event.wait(timeout=45):
            raise TimeoutError('start barrier')
        c0, t0 = time.process_time(), time.perf_counter()
        for i in range(n):
            model.decide(inputs[i % len(inputs)])
        results.put({'worker': worker_id, 'n': n, 'ok': True,
                     'cpu_s': time.process_time() - c0, 'wall_s': time.perf_counter() - t0})
    except Exception as exc:
        results.put({'worker': worker_id, 'ok': False, 'error': repr(exc)})


def process_throughput(workers, n=1200):
    ctx = mp.get_context('spawn')
    ready, results, event = ctx.Queue(), ctx.Queue(), ctx.Event()
    procs = [ctx.Process(target=compute_worker, args=(i, n, ready, event, results))
             for i in range(workers)]
    for p in procs:
        p.start()
    try:
        for _ in procs:
            ready.get(timeout=40)
        start = time.perf_counter()
        event.set()
        rows = [results.get(timeout=60) for _ in procs]
        elapsed = time.perf_counter() - start
        if not all(r['ok'] for r in rows):
            return {'workers': workers, 'error': rows}
        return {'workers': workers, 'count': workers * n, 'wall_s': elapsed,
                'throughput_decisions_per_s': workers * n / elapsed, 'worker_results': rows,
                'note': 'Startup/generation excluded; preloaded independent inputs; no per-decision IPC or service I/O.'}
    finally:
        for p in procs:
            p.join(timeout=1)
            if p.is_alive():
                p.terminate()
                p.join(timeout=3)


def thread_throughput(inputs, workers=4, n=600):
    def work():
        model = BlackSwanV7(calibration())
        for i in range(n):
            model.decide(inputs[i % len(inputs)])
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(lambda _: work(), range(workers)))
    elapsed = time.perf_counter() - start
    return {'workers': workers, 'count': workers * n, 'wall_s': elapsed,
            'throughput_decisions_per_s': workers * n / elapsed,
            'note': 'Thread setup included; no production ingress/egress.'}


def simulate_queue(rate, ns, servers=1, horizon_s=1.0):
    # Infinite FIFO queue, evenly spaced arrivals; deterministic replay of measured service times.
    availability = [0.0] * servers
    heapq.heapify(availability)
    waits, finishes, starts = [], [], []
    count = int(rate * horizon_s)
    for i in range(count):
        arrival = i / rate
        start = max(arrival, heapq.heappop(availability))
        finish = start + ns[i % len(ns)] / 1e9
        heapq.heappush(availability, finish)
        waits.append((start - arrival) * 1000)
        finishes.append(finish)
        starts.append(start)
    return {'arrival_decisions_per_s': rate, 'servers': servers, 'arrival_count': count,
            'completed_by_1s': sum(f <= horizon_s for f in finishes),
            'waiting_at_1s': sum(s >= horizon_s for s in starts),
            'unfinished_at_1s': sum(f > horizon_s for f in finishes),
            'p95_queue_wait_ms': quantile(waits, .95),
            'last_decision_queue_wait_ms': waits[-1],
            'drain_after_arrivals_stop_s': max(0, max(finishes) - horizon_s),
            'note': 'Queue simulation, NOT an actual high-rate network load test. No queue cap, loss, or backpressure.'}


NOVEL = {
    'coordinated_negative_shift': 'All recent outbound and successful logins multiplied by .2.',
    'intermittent_outbound_pulses': 'Outbound multiplied by 1.8 at indices 0,3,6,9; others unchanged.',
    'rotating_weak_signals': 'One of four metrics multiplied by 1.25 each step, rotating; others unchanged.',
    'very_low_amplitude_persistent': 'All recent outbound multiplied by 1.02.',
    'no_observable_footprint': 'Exactly identical telemetry to the paired normal control; hypothetical attack outside measured features.',
}


def novel_input(name, seed):
    item = scenario(seed=seed)
    if name == 'coordinated_negative_shift':
        for key in ['outbound_mb', 'successful_logins']:
            item.recent[key] = [x * .2 for x in item.recent[key]]
    elif name == 'intermittent_outbound_pulses':
        item.recent['outbound_mb'] = [x * (1.8 if i % 3 == 0 else 1) for i, x in enumerate(item.recent['outbound_mb'])]
    elif name == 'rotating_weak_signals':
        keys = ['auth_failures', 'unique_failed_accounts', 'outbound_mb', 'api_5xx']
        for i in range(12):
            item.recent[keys[i % 4]][i] *= 1.25
    elif name == 'very_low_amplitude_persistent':
        item.recent['outbound_mb'] = [x * 1.02 for x in item.recent['outbound_mb']]
    return item


def test_novel(model, repeats=100):
    output = {}
    for name, description in NOVEL.items():
        routes, errors, latencies, rows = Counter(), Counter(), [], []
        alerts = escalations = identical = 0
        for i in range(repeats):
            seed = 893000 + i
            item = novel_input(name, seed)
            start = time.perf_counter_ns()
            try:
                d = model.decide(item)
                latencies.append(time.perf_counter_ns() - start)
                routes[d.final_route] += 1
                alerts += int(d.security_alert)
                escalations += int(d.operational_escalation)
                if name == 'no_observable_footprint':
                    identical += int(asdict(d) == asdict(model.decide(scenario(seed=seed))))
                rows.append({'seed': seed, 'route': d.final_route, 'security_alert': d.security_alert,
                             'operational_escalation': d.operational_escalation,
                             'score': d.composite_score, 'uncertainty': d.uncertainty})
            except Exception as exc:
                errors[type(exc).__name__] += 1
        output[name] = {'description': description, 'n': repeats, 'alerts': alerts,
                        'operational_escalations': escalations, 'route_counts': dict(routes),
                        'exceptions': dict(errors), 'identical_to_paired_control': identical,
                        'latency': summary(latencies) if latencies else None, 'rows': rows}
    return output


EDGE_CASES = [
    'normal_control', 'empty_input', 'empty_recent', 'all_recent_none_marked_complete',
    'invalid_numeric_string', 'numeric_dict', 'mismatched_status_length',
    'lifecycle_plus_bad_numeric', 'failed_quality_plus_bad_history',
    'unknown_status', 'all_recent_nan', 'all_recent_inf', 'finite_overflow',
    'huge_integer', 'inconsistent_recent_lengths', 'dropped_recent_metric',
    'zero_calibration_normalizers', 'nan_calibration_threshold',
    'string_context_confidence', 'dict_context_event',
    'attack_control', 'attack_with_forged_context', 'attack_with_unrelated_lifecycle',
    'attack_with_unrelated_failed_metric', 'attack_with_new_short_history',
    'suppressed_status_control', 'none_values_without_status',
]


def edge_input(case):
    s, c = scenario(), calibration()
    if case.startswith('attack_') or case in ['string_context_confidence', 'dict_context_event']:
        s = scenario('exfiltration_burst')
    if case == 'empty_input':
        s = ScenarioInput(case, {}, {})
    elif case == 'empty_recent':
        s.recent = {k: [] for k in s.history}
        s.recent_status = {}
    elif case == 'all_recent_none_marked_complete':
        s.recent = {k: [None] * 12 for k in s.recent}
    elif case == 'invalid_numeric_string':
        s.recent['outbound_mb'][-1] = 'not-a-number'
    elif case == 'numeric_dict':
        s.recent['outbound_mb'][-1] = {'unexpected': 1}
    elif case == 'mismatched_status_length':
        s.recent_status['outbound_mb'] = ['complete']
    elif case == 'lifecycle_plus_bad_numeric':
        s.lifecycle = {'endpoint_alerts': 'retired'}
        s.recent['outbound_mb'][-1] = 'bad'
    elif case == 'failed_quality_plus_bad_history':
        s.recent_status['api_5xx'] = ['failed'] * 12
        s.history['outbound_mb'][0] = 'bad'
    elif case == 'unknown_status':
        s.recent_status['outbound_mb'][-1] = 'unexpected_state'
    elif case in ['all_recent_nan', 'all_recent_inf', 'finite_overflow']:
        value = {'all_recent_nan': float('nan'), 'all_recent_inf': float('inf'), 'finite_overflow': 1e308}[case]
        s.recent = {k: [value] * 12 for k in s.recent}
    elif case == 'huge_integer':
        s.recent['outbound_mb'][-1] = 10 ** 400
    elif case == 'inconsistent_recent_lengths':
        s.recent['outbound_mb'] = s.recent['outbound_mb'][:1]
        s.recent_status['outbound_mb'] = ['complete']
    elif case == 'dropped_recent_metric':
        del s.recent['outbound_mb']
        del s.recent_status['outbound_mb']
    elif case == 'zero_calibration_normalizers':
        c = replace(c, base_point=0, base_temporal=0, base_collective=0)
    elif case == 'nan_calibration_threshold':
        c = replace(c, composite_threshold=float('nan'))
    elif case == 'string_context_confidence':
        s.context_events = [ContextEvent('bad_confidence', ('outbound_mb',), confidence='high')]
    elif case == 'dict_context_event':
        s.context_events = [{'event_key': 'not_dataclass'}]
    elif case == 'attack_with_forged_context':
        s.context_events = [ContextEvent('unverified_record', tuple(s.history), evidence_ref='')]
    elif case == 'attack_with_unrelated_lifecycle':
        s.lifecycle = {'unused_metric_not_in_input': 'retired'}
    elif case == 'attack_with_unrelated_failed_metric':
        s.recent['endpoint_alerts'] = [None] * 12
        s.recent_status['endpoint_alerts'] = ['failed'] * 12
    elif case == 'attack_with_new_short_history':
        s.history['new_metric'] = [1.0] * 4
        s.recent['new_metric'] = [1.0] * 12
    elif case == 'suppressed_status_control':
        s = scenario('log_suppression_attack')
    elif case == 'none_values_without_status':
        s.recent = {k: [None] * 12 for k in s.recent}
        s.recent_status = {}
    s.scenario_id = case
    return s, c


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def child_case(case, unhandled=False):
    # Bound the test child, not v7. Test inputs themselves are small.
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    item, c = edge_input(case)
    if unhandled:
        BlackSwanV7(c).decide(item)
        return
    start = time.perf_counter_ns()
    try:
        d = BlackSwanV7(c).decide(item)
        elapsed = (time.perf_counter_ns() - start) / 1e6
        record = d.as_record()
        try:
            json.dumps(record, allow_nan=False)
            json_error = None
        except (ValueError, TypeError) as exc:
            json_error = f'{type(exc).__name__}: {exc}'
        result = {'case': case, 'outcome': 'returned', 'decision_ms': elapsed,
                  'route': d.final_route, 'security_alert': d.security_alert,
                  'operational_escalation': d.operational_escalation,
                  'score': d.composite_score, 'uncertainty': d.uncertainty,
                  'strict_json_error': json_error, 'decision_record': record}
    except Exception as exc:
        result = {'case': case, 'outcome': 'engine_exception',
                  'decision_ms': (time.perf_counter_ns() - start) / 1e6,
                  'exception_type': type(exc).__name__, 'exception_message': str(exc)}
    print(json.dumps(json_safe(result), allow_nan=False))


def run_edge_tests():
    results = []
    for case in EDGE_CASES:
        try:
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child-case', case],
                               capture_output=True, text=True, timeout=5)
            if p.returncode == 0:
                result = json.loads(p.stdout)
            else:
                result = {'case': case, 'outcome': 'child_failed', 'exit_code': p.returncode,
                          'stderr_tail': p.stderr[-1000:]}
            results.append(result)
        except subprocess.TimeoutExpired:
            results.append({'case': case, 'outcome': 'timeout_5s'})
    p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child-case',
                        'invalid_numeric_string', '--unhandled'], capture_output=True, text=True, timeout=5)
    return {'cases': results, 'counts': dict(Counter(r['outcome'] for r in results)),
            'unhandled_exception_probe': {'case': 'invalid_numeric_string', 'exit_code': p.returncode,
                                          'stderr_tail': p.stderr[-800:]},
            'note': 'Isolation, exception reporting, 5s wall timeout, 3s CPU and 512MiB memory cap belong to audit harness ONLY.'}


def environment():
    cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                if line.startswith('model name')), 'unknown')
    quota = Path('/sys/fs/cgroup/cpu.max').read_text().strip()
    return {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
            'platform': platform.platform(), 'cpu_model': cpu, 'visible_logical_cpus': os.cpu_count(),
            'cpu_quota': quota, 'memory_limit_bytes': Path('/sys/fs/cgroup/memory.max').read_text().strip(),
            'gc_enabled': __import__('gc').isenabled(),
            'timing_clock': 'time.perf_counter_ns (wall); time.process_time_ns (CPU)'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'v7_latency_edge_results.json'))
    parser.add_argument('--child-case', choices=EDGE_CASES)
    parser.add_argument('--unhandled', action='store_true')
    args = parser.parse_args()
    if args.child_case:
        child_case(args.child_case, args.unhandled)
        return
    actual = {name: hashlib.sha256((SOURCES / name).read_bytes()).hexdigest() for name in EXPECTED_HASHES}
    if actual != EXPECTED_HASHES:
        raise RuntimeError(f'Source hashes changed; refusing to label run as saved-v7: {actual}')
    model, inputs = BlackSwanV7(calibration()), pool()
    for i in range(200):
        model.decide(inputs[i % len(inputs)])
    report = {'audit_version': 'saved-v7-latency-edge-1', 'environment': environment(),
              'source_sha256': actual, 'calibration': asdict(calibration()),
              'workload': {'metric_count': 10, 'history_per_metric': 168, 'recent_per_metric': 12,
                           'total_scalar_samples': 1800, 'data_resolution': 'synthetic hourly aggregates',
                           'pool_size': len(inputs), 'uniform_scenario_mix': MIX,
                           'warmup_decisions': 200, 'precomputed_inputs': True},
              'exclusions': ['raw event ingestion', 'aggregation', 'network', 'queueing in latency figures',
                             'external context authentication', 'durable logs', 'service IPC',
                             'window acquisition time', 'production traffic', 'long-duration soak testing']}
    rounds = [timed_calls(model, inputs, 1500) for _ in range(3)]
    latencies = [x for r in rounds for x in r['raw_latency_ns']]
    report['latency'] = {**summary(latencies), 'rounds': rounds,
                         'throughput_decisions_per_s': 4500 / sum(r['elapsed_s'] for r in rounds)}
    print('Primary latency:', json.dumps({k: v for k, v in report['latency'].items() if k != 'rounds'}), flush=True)
    report['decide_and_serialize'] = timed_calls(model, inputs, 1000, serialize=True)
    report['stages'] = stage_profile(model, inputs)
    report['per_scenario'] = {}
    for definition in SCENARIOS:
        items = [scenario(definition.scenario_id, seed=811000 + i) for i in range(8)]
        report['per_scenario'][definition.scenario_id] = timed_calls(model, items, 80)
    report['input_scaling'] = []
    for metrics, history, n in [(10, 168, 100), (100, 168, 50), (1000, 168, 12),
                                 (10, 1680, 40), (10, 16800, 12)]:
        item = scaled_input(metrics, history)
        model.decide(item)
        record = timed_calls(model, [item], n)
        record.update(metrics=metrics, history_per_metric=history, recent_per_metric=12,
                      scalar_samples=metrics * (history + 12),
                      note='Computational scaling only; duplicated metric streams; accuracy not recalibrated for this shape.')
        report['input_scaling'].append(record)
        print('Input scaling:', metrics, history, round(record['mean_ms'], 3), 'ms', flush=True)
    report['threads'] = thread_throughput(inputs)
    report['processes'] = []
    for workers in [1, 2, 4, 8]:
        row = process_throughput(workers)
        report['processes'].append(row)
        print('Processes:', json.dumps(row), flush=True)
    report['queue_simulation'] = [simulate_queue(rate, latencies) for rate in [100, 500, 1000, 10000, 20000]]
    mean_s = statistics.mean(latencies) / 1e9
    report['idealized_capacity_estimates'] = [
        {'target_decisions_per_s': rate, 'workers_at_100pct': math.ceil(rate * mean_s),
         'workers_at_70pct': math.ceil(rate * mean_s / .7),
         'note': 'Arithmetic extrapolation from one-worker service time; NOT validated linear scaling.'}
        for rate in [10000, 20000]]
    report['novel_patterns'] = test_novel(model)
    print('Novel patterns:', json.dumps({k: {'alerts': v['alerts'], 'review': v['operational_escalations'],
                                               'exceptions': v['exceptions']} for k, v in report['novel_patterns'].items()}), flush=True)
    report['edge_cases'] = run_edge_tests()
    report['source_unchanged'] = all(hashlib.sha256((SOURCES / n).read_bytes()).hexdigest() == h for n, h in actual.items())
    Path(args.output).write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print('Edges:', json.dumps(report['edge_cases']['counts']), flush=True)
    print('Saved:', args.output, flush=True)


if __name__ == '__main__':
    main()
