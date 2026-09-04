# Benchmarks

- `evaluate_black_swan_v8.py`: relocated v8 evaluator. Writes new results and hashes of the actual relocated source. `--skip-load` runs the original correctness, microbenchmark and resilience evaluation; `--load-only` runs local runtime load cases.
- `black_swan_v7_benchmark.py`: original v7 generator and quality benchmark, byte-for-byte preserved. From repository root use `PYTHONPATH=src python3 benchmarks/black_swan_v7_benchmark.py --output-dir experiments/local/v7`.
- `support/v7_latency_audit/`: original immutable audit and source copies. These duplicates intentionally preserve the source-hash gate and the fixtures used by v8 tests. They are reference files, not an alternative active engine.

Performance results are synthetic/local and exclude production ingestion, authentication and durable outputs. The repository reorganization does not establish a new throughput target.
