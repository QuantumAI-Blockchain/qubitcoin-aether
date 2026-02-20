# qubitcoin-qvm — Production QVM (Go Implementation)

.PHONY: all build test lint bench clean proto docker

# ─── Variables ──────────────────────────────────────────────────────
GO          := go
BINARY_QVM  := bin/qvm
BINARY_CLI  := bin/qvm-cli
BINARY_PLUG := bin/plugin-loader
VERSION     := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
LDFLAGS     := -ldflags "-X main.version=$(VERSION) -s -w"
GOFLAGS     := -trimpath

# ─── Build ──────────────────────────────────────────────────────────
all: build

build: build-qvm build-cli build-plugins

build-qvm:
	$(GO) build $(GOFLAGS) $(LDFLAGS) -o $(BINARY_QVM) ./cmd/qvm

build-cli:
	$(GO) build $(GOFLAGS) $(LDFLAGS) -o $(BINARY_CLI) ./cmd/qvm-cli

build-plugins:
	$(GO) build $(GOFLAGS) $(LDFLAGS) -o $(BINARY_PLUG) ./cmd/plugin-loader

# ─── Test ───────────────────────────────────────────────────────────
test:
	$(GO) test ./... -v -race -count=1

test-evm:
	$(GO) test ./test/evm/... -v -count=1

test-quantum:
	$(GO) test ./test/quantum/... -v -count=1

test-compliance:
	$(GO) test ./test/compliance/... -v -count=1

test-coverage:
	$(GO) test ./... -coverprofile=coverage.out -covermode=atomic
	$(GO) tool cover -html=coverage.out -o coverage.html

# ─── Benchmark ──────────────────────────────────────────────────────
bench:
	$(GO) test ./test/benchmark/... -bench=. -benchmem -count=3

bench-evm:
	$(GO) test ./test/benchmark/... -bench=BenchmarkEVM -benchmem

bench-quantum:
	$(GO) test ./test/benchmark/... -bench=BenchmarkQuantum -benchmem

# ─── Lint ───────────────────────────────────────────────────────────
lint:
	golangci-lint run ./...

fmt:
	gofmt -s -w .
	goimports -w .

vet:
	$(GO) vet ./...

# ─── Proto ──────────────────────────────────────────────────────────
proto:
	protoc --go_out=. --go_opt=paths=source_relative \
	       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
	       --grpc-gateway_out=. --grpc-gateway_opt=paths=source_relative \
	       api/proto/*.proto

# ─── Docker ─────────────────────────────────────────────────────────
docker:
	docker build -t qubitcoin-qvm:$(VERSION) -f deployments/docker/Dockerfile .

docker-push:
	docker tag qubitcoin-qvm:$(VERSION) ghcr.io/blockartica/qubitcoin-qvm:$(VERSION)
	docker push ghcr.io/blockartica/qubitcoin-qvm:$(VERSION)

# ─── Clean ──────────────────────────────────────────────────────────
clean:
	rm -rf bin/ coverage.out coverage.html
	$(GO) clean -cache
