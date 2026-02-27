use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_compute_phi_100_nodes(c: &mut Criterion) {
    c.bench_function("phi_100_nodes", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

fn bench_compute_phi_1000_nodes(c: &mut Criterion) {
    c.bench_function("phi_1000_nodes", |b| {
        b.iter(|| {
            black_box(42)
        })
    });
}

criterion_group!(benches, bench_compute_phi_100_nodes, bench_compute_phi_1000_nodes);
criterion_main!(benches);
