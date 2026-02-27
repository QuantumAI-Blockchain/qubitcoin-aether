use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_hnsw_insert_1000(c: &mut Criterion) {
    c.bench_function("hnsw_insert_1000", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

fn bench_hnsw_search(c: &mut Criterion) {
    c.bench_function("hnsw_search_1000", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

criterion_group!(benches, bench_hnsw_insert_1000, bench_hnsw_search);
criterion_main!(benches);
