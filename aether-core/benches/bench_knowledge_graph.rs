use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_add_nodes(c: &mut Criterion) {
    c.bench_function("add_1000_nodes", |b| {
        b.iter(|| {
            // Will be filled once knowledge_graph module compiles
            black_box(42)
        })
    });
}

fn bench_merkle_root(c: &mut Criterion) {
    c.bench_function("merkle_root_1000_nodes", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

fn bench_search(c: &mut Criterion) {
    c.bench_function("tfidf_search_1000_nodes", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

criterion_group!(benches, bench_add_nodes, bench_merkle_root, bench_search);
criterion_main!(benches);
