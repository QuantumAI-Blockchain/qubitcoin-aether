# qubitcoin-qvm — Production Docker Build
# Multi-stage: Build Go binaries, then copy to minimal runtime image.

# ─── Stage 1: Build ──────────────────────────────────────────────────
FROM golang:1.23-bookworm AS builder

WORKDIR /build

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build all binaries
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-s -w" -o /bin/qvm ./cmd/qvm && \
    go build -trimpath -ldflags="-s -w" -o /bin/qvm-cli ./cmd/qvm-cli && \
    go build -trimpath -ldflags="-s -w" -o /bin/plugin-loader ./cmd/plugin-loader

# ─── Stage 2: Runtime ────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12:nonroot

LABEL org.opencontainers.image.title="qubitcoin-qvm" \
      org.opencontainers.image.description="Qubitcoin Quantum Virtual Machine" \
      org.opencontainers.image.vendor="BlockArtica" \
      org.opencontainers.image.licenses="MIT"

COPY --from=builder /bin/qvm /usr/local/bin/qvm
COPY --from=builder /bin/qvm-cli /usr/local/bin/qvm-cli
COPY --from=builder /bin/plugin-loader /usr/local/bin/plugin-loader

# gRPC + REST
EXPOSE 50052 8080

USER nonroot:nonroot

ENTRYPOINT ["/usr/local/bin/qvm"]
CMD ["serve"]
