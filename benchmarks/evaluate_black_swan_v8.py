#!/usr/bin/env python3
"""Measured synthetic evaluation; no network traffic, deployment or real attacks.

Run from any cwd: python3 benchmarks/evaluate_black_swan_v8.py
Results retain timing samples, route denominators, code hashes and commands.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests'), str(HERE), str(HERE/'support/v7_latency_audit')]
from black_swan.engine import BlackSwanV8, WindowUpdate, Limits
from black_swan.runtime import IsolatedDecisionPool
from fixtures.v8_synthetic import trusted_fixtures, update_for
from black_swan_v7_engine import BlackSwanV7
from black_swan_v7_latency_edge_audit import (
    calibration, scenario, pool, timed_calls, summary, environment,
    SCENARIOS, EDGE_CASES, edge_input, NOVEL, novel_input, quantile,
)

FALLBACK_ROUTES = {'OVERLOAD_REVIEW', 'TIMEOUT_REVIEW', 'WORKER_ERROR_REVIEW',
                   'CANCELLED_REVIEW', 'VERIFIER_ERROR_REVIEW', 'CONFIGURATION_REVIEW',
                   'INVALID_INPUT_REVIEW', 'BASELINE_REVIEW'}


def clean_decision(d):
    return {'route': d.final_route, 'security_alert': d.security_alert,
            'review': d.operational_escalation, 'score': d.composite_score,
            'reason': getattr(d, 'reason_code', None)}


def ms_summary(xs):
    return summary([x * 1e6 for x in xs]) if xs else {'count': 0}


def paired_microbenchmark(trusted):
    inputs = pool()
    old, full, prepared = BlackSwanV7(calibration()), BlackSwanV8(calibration(), trusted_contexts=trusted), BlackSwanV8(calibration(), trusted_contexts=trusted)
    updates = [update_for(prepared, f'entity_{i}', s) for i, s in enumerate(inputs)]
    class PreparedAdapter:
        def decide(self, item):
            return prepared.decide_update(item)
    adapter = PreparedAdapter()
    for model, items in [(old, inputs), (full, inputs), (adapter, updates)]:
        for i in range(200):
            model.decide(items[i % len(items)])
    rounds = {'v7_full': [], 'v8_full': [], 'v8_registered_window': []}
    # Alternate order between rounds, keeping the exact full-input mix identical.
    choices = [('v7_full', old, inputs), ('v8_full', full, inputs), ('v8_registered_window', adapter, updates)]
    for repeat in range(3):
        order = choices if repeat % 2 == 0 else list(reversed(choices))
        for name, model, items in order:
            rounds[name].append(timed_calls(model, items, 1500))
    result = {}
    for name, rows in rounds.items():
        ns = [x for row in rows for x in row['raw_latency_ns']]
        result[name] = {**summary(ns), 'throughput_per_s': len(ns)/sum(row['elapsed_s'] for row in rows), 'rounds': rows}
    cold_inputs = [scenario(seed=1_410_000+i) for i in range(200)]
    result['v8_unique_history_cache_miss'] = timed_calls(BlackSwanV8(calibration()), cold_inputs, len(cold_inputs))
    result['v8_cache_disabled'] = timed_calls(BlackSwanV8(calibration(), limits=replace(Limits(), cache_entries=0), trusted_contexts=trusted), inputs, 500)
    result['cache_stats_full'] = {'hits': full.cache_hits, 'misses': full.cache_misses, 'entries': len(full._cache)}
    result['note'] = 'v7_full vs v8_full use identical 1800-scalar payloads. Registered-window uses prevalidated immutable history, so it is a separate operating mode, not an apples-to-apples full-payload speedup.'
    return result


def quality(trusted):
    old, new = BlackSwanV7(calibration()), BlackSwanV8(calibration(), trusted_contexts=trusted)
    conservative = BlackSwanV8(calibration())
    rows = []
    for definition in SCENARIOS:
        for i in range(100):
            seed = 1_421_000 + i
            s = scenario(definition.scenario_id, seed=seed)
            a, b = old.decide(s), new.decide(s)
            rows.append({'family': definition.scenario_id, 'group': definition.group, 'seed': seed,
                         'attack_present': definition.attack_present, 'desired_alert': definition.desired_security_alert,
                         'v7': clean_decision(a), 'v8': clean_decision(b),
                         'default_registry_empty_alert': conservative.decide(s).security_alert if definition.group in ('control','benign') else None})
    complete_ids = {x.scenario_id for x in SCENARIOS[:15]}
    complete = [r for r in rows if r['family'] in complete_ids]
    summary_rows = {}
    for label in ['v7','v8']:
        benign = [r for r in rows if r['group'] in ('control','benign')]
        strong = [r for r in rows if r['group'] == 'attack']
        evasive = [r for r in rows if r['group'] == 'evasive_attack' and r['desired_alert']]
        attacks = [r for r in rows if r['attack_present']]
        summary_rows[label] = {
            'benign_false_alerts': sum(r[label]['security_alert'] for r in benign), 'benign_n': len(benign),
            'strong_alerts': sum(r[label]['security_alert'] for r in strong), 'strong_n': len(strong),
            'evasive_observable_alerts': sum(r[label]['security_alert'] for r in evasive), 'evasive_n': len(evasive),
            'attack_operational_capture': sum(r[label]['review'] for r in attacks), 'attack_n': len(attacks),
            'all_routes': dict(Counter(r[label]['route'] for r in rows)),
            'automatic_no_review': sum(not r[label]['review'] for r in rows),
        }
    return {'n': len(rows), 'complete_numeric_n': len(complete),
            'identical_scores': sum(r['v7']['score'] == r['v8']['score'] for r in complete),
            'identical_routes': sum(r['v7']['route'] == r['v8']['route'] for r in complete),
            'summary': summary_rows,
            'empty_trust_registry_benign_alerts': sum(r['default_registry_empty_alert'] is True for r in rows),
            'rows': rows,
            'note': 'Fresh seeds, same original synthetic generator. Registry entries are operator-installed synthetic benign fixtures, not authenticated production records.'}


def novel_and_edges(trusted):
    m = BlackSwanV8(calibration(), trusted_contexts=trusted)
    novel = {}
    for name, description in NOVEL.items():
        rows = []
        for i in range(100):
            seed = 1_451_000 + i
            item = novel_input(name, seed)
            d = m.decide(item)
            row = {'seed': seed, **clean_decision(d)}
            if name == 'no_observable_footprint':
                row['identical_to_normal'] = asdict(d) == asdict(m.decide(scenario(seed=seed)))
            rows.append(row)
        novel[name] = {'description': description, 'n': len(rows), 'alerts': sum(r['security_alert'] for r in rows),
                        'review_including_alerts': sum(r['review'] for r in rows),
                        'routes': dict(Counter(r['route'] for r in rows)), 'rows': rows}
    edges = []
    for name in EDGE_CASES:
        s, c = edge_input(name)
        d = BlackSwanV8(c).decide(s)
        json.dumps(d.as_record(), allow_nan=False)
        edges.append({'case': name, **clean_decision(d)})
    faults = []
    with IsolatedDecisionPool(calibration(), workers=1, queue_capacity=8, deadline_s=.25, test_faults=True) as runtime:
        for fault in ['stall', 'stall', 'stall', 'crash', 'exception']:
            r = runtime.submit(scenario(), test_fault=fault).future.result(timeout=3)
            recovery = runtime.submit(scenario('exfiltration_burst')).future.result(timeout=3)
            faults.append({'fault': fault, **clean_decision(r['decision']), 'elapsed_ms': r['end_to_end_ms'],
                           'recovery_alert': recovery['decision'].security_alert,
                           'recovery_ms': recovery['end_to_end_ms']})
        stats = runtime.stats()
    return {'novel_patterns': novel, 'edge_cases': edges, 'faults': faults,
            'fault_runtime_stats': stats, 'workers_after_close': runtime.stats()['alive_workers']}


def rss_bytes(pids):
    total = 0
    for pid in pids:
        try:
            for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    total += int(line.split()[1]) * 1024
                    break
        except (FileNotFoundError, ProcessLookupError):
            pass
    return total


def load_run(mode, rate, duration, trusted, repeat=0):
    import os
    inputs = pool()
    helper = BlackSwanV8(calibration(), trusted_contexts=trusted)
    updates = [update_for(helper, f'entity_{i}', s) for i,s in enumerate(inputs)]
    baselines = [(f'entity_{i}', s) for i,s in enumerate(inputs)]
    offered_items = inputs if mode == 'full' else updates
    tickets, lags, queue_samples = [], [], []
    count = int(rate * duration)
    child_cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    parent_cpu0 = time.process_time()
    with IsolatedDecisionPool(calibration(), workers=8, queue_capacity=256,
                              deadline_s=.5, trusted_contexts=trusted, baselines=baselines) as runtime:
        warm = [runtime.submit(offered_items[i % len(offered_items)]) for i in range(128)]
        for ticket in warm:
            ticket.future.result(timeout=3)
        warm_stats = runtime.stats()
        pids = [os.getpid()] + [r['process'].pid for r in runtime._workers.values()]
        memory_peak = rss_bytes(pids)
        start = time.monotonic()
        next_sample = start
        for i in range(count):
            target = start + i / rate
            now = time.monotonic()
            if now < target:
                time.sleep(target - now)
            ticket = runtime.submit(offered_items[i % len(offered_items)])
            tickets.append(ticket)
            lags.append(max(0, (ticket.submitted - target) * 1000))
            now = time.monotonic()
            if now >= next_sample:
                snap = runtime.stats()
                queue_samples.append({'offset_s': now-start, 'pending': snap['pending'], 'queued': snap['queued']})
                memory_peak = max(memory_peak, rss_bytes(pids))
                next_sample = now + .25
        offer_end = time.monotonic()
        responses = [ticket.future.result(timeout=5) for ticket in tickets]
        complete_end = max(r['completed'] for r in responses)
        stats = runtime.stats()
        memory_peak = max(memory_peak, rss_bytes(pids))
    child_cpu1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    computed = [r for r in responses if r['decision'].final_route not in FALLBACK_ROUTES]
    fallbacks = [r for r in responses if r['decision'].final_route in FALLBACK_ROUTES]
    received = len(tickets)
    arrivals_elapsed = max(offer_end-start, duration)
    total_elapsed = max(complete_end-start, arrivals_elapsed)
    counts = Counter(r['decision'].final_route for r in responses)
    accepted = sum(t.accepted for t in tickets)
    completed_within_horizon = sum(r['completed'] <= start+duration for r in computed)
    return {
        'mode': mode, 'repeat': repeat, 'target_rate_per_s': rate, 'scheduled_duration_s': duration,
        'workers': 8, 'queue_capacity': 256, 'deadline_s': .5, 'warmup': 128,
        'scheduled': count, 'offered': received, 'accepted': accepted, 'rejected': received-accepted,
        'computed_decisions': len(computed), 'fallback_responses': len(fallbacks),
        'computed_security_alerts': sum(r['decision'].security_alert for r in computed),
        'computed_review_including_security': sum(r['decision'].operational_escalation for r in computed),
        'computed_automatic_no_review': sum(not r['decision'].operational_escalation for r in computed),
        'route_counts': dict(counts), 'actual_offer_duration_s': arrivals_elapsed,
        'achieved_offer_rate_per_s': received/arrivals_elapsed, 'drain_s': max(0,complete_end-offer_end),
        'computed_throughput_including_drain_per_s': len(computed)/total_elapsed,
        'computed_within_scheduled_horizon': completed_within_horizon,
        'computed_throughput_within_horizon_per_s': completed_within_horizon/duration,
        'emitter_lag': ms_summary(lags),
        'all_response_latency': ms_summary([r['end_to_end_ms'] for r in responses]),
        'computed_response_latency': ms_summary([r['end_to_end_ms'] for r in computed]),
        'fallback_response_latency': ms_summary([r['end_to_end_ms'] for r in fallbacks]),
        'computed_queue_latency': ms_summary([r['queue_ms'] for r in computed]),
        'computed_processing_latency': ms_summary([r['compute_ms'] for r in computed]),
        'pending_after_drain': stats['pending'], 'peak_pending_including_warmup': stats['peak_pending'],
        'peak_queue_including_warmup': stats['peak_queue'], 'queue_samples': queue_samples,
        'monitor_error': stats['monitor_error'], 'worker_restarts': stats['worker_restarts']-warm_stats['worker_restarts'],
        'sampled_aggregate_rss_peak_bytes': memory_peak,
        'parent_cpu_s_including_setup': time.process_time()-parent_cpu0,
        'children_cpu_s_including_setup': (child_cpu1.ru_utime+child_cpu1.ru_stime)-(child_cpu0.ru_utime+child_cpu0.ru_stime),
        'raw_computed_e2e_ms': [round(r['end_to_end_ms'],6) for r in computed],
        'raw_computed_queue_ms': [round(r['queue_ms'],6) for r in computed],
        'raw_fallback_e2e_ms': [round(r['end_to_end_ms'],6) for r in fallbacks],
        'raw_emitter_lag_ms': [round(x,6) for x in lags],
        'accounting_ok': received == len(computed)+len(fallbacks) == len(responses) and stats['pending']==0,
        'offered_target_all_computed': received == len(computed) and received/arrivals_elapsed >= rate*.98,
        'note': 'Open-loop local submissions scheduled independently of responses. Includes local IPC/queue/watchdog, not network, raw-event ingestion, authentication, or durable output. Actual rate/lag exposes emitter limitations.'
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT/'experiments/local'/time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())/'v8_results.json'))
    parser.add_argument('--load-only', action='store_true')
    parser.add_argument('--skip-load', action='store_true')
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error('Output already exists; choose a new run path to preserve prior evidence.')
    trusted = trusted_fixtures()
    names = ['src/black_swan/engine.py', 'src/black_swan/runtime.py', 'tests/test_black_swan_v8.py', 'tests/fixtures/v8_synthetic.py', 'benchmarks/evaluate_black_swan_v8.py', 'src/black_swan_v7_engine.py', 'benchmarks/support/v7_latency_audit/black_swan_v7_latency_edge_audit.py', 'benchmarks/support/v7_latency_audit/sources/black_swan_v7_manifest.json']
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    report = {'version': 'v8-evaluation-organized-1', 'environment': environment(), 'code_sha256': hashes,
              'calibration': asdict(calibration()), 'quantiles': 'sorted linear interpolation at (n-1)*q',
              'data_provenance': 'Original v7 hourly synthetic cybersecurity metric generator; no production or public real-data replay.',
              'trust_fixtures': [asdict(x) for x in trusted], 'load': []}
    def checkpoint():
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    if not args.load_only:
        command = [sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_black_swan_v8.py','-v']
        tests = subprocess.run(command, capture_output=True, text=True, timeout=90)
        report['unit_tests'] = {'command': command, 'exit_code': tests.returncode, 'stdout': tests.stdout, 'stderr': tests.stderr}
        if tests.returncode:
            checkpoint()
            raise RuntimeError('Regression failure; stop before performance claims')
        report['microbenchmark'] = paired_microbenchmark(trusted)
        print('Microbenchmark:', json.dumps({k:{'mean_ms':v['mean_ms'],'p99_ms':v['p99_ms']} for k,v in report['microbenchmark'].items() if isinstance(v,dict) and 'mean_ms' in v}), flush=True)
        report['quality'] = quality(trusted)
        print('Quality:', json.dumps(report['quality']['summary']), flush=True)
        report['resilience'] = novel_and_edges(trusted)
        print('Faults:', json.dumps(report['resilience']['faults']), flush=True)
        checkpoint()
    if not args.skip_load:
        for mode in ['full','registered_window']:
            for rate in [500, 2000, 10000, 10000, 20000]:
                repeat = 1 if rate==10000 and any(r['mode']==mode and r['target_rate_per_s']==rate for r in report['load']) else 0
                row = load_run(mode, rate, 3.0, trusted, repeat)
                report['load'].append(row)
                print('Load:', json.dumps({k:row[k] for k in ['mode','target_rate_per_s','repeat','achieved_offer_rate_per_s','computed_throughput_including_drain_per_s','rejected','fallback_responses','monitor_error','accounting_ok']}), flush=True)
                checkpoint()
        row = load_run('registered_window',1000,30.0,trusted)
        report['load'].append(row)
        print('Mini-soak:', json.dumps({k:row[k] for k in ['offered','computed_decisions','rejected','fallback_responses','accounting_ok']}), flush=True)
    report['code_unchanged_during_evaluation'] = all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    checkpoint()
    print('Saved:',args.output, flush=True)


if __name__ == '__main__':
    main()
