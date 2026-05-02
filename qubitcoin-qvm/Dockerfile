# Build stage
FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /qvm ./cmd/qvm

# Runtime stage
FROM alpine:3.21

RUN apk add --no-cache ca-certificates

COPY --from=builder /qvm /usr/local/bin/qvm

EXPOSE 8080 50053

ENTRYPOINT ["/usr/local/bin/qvm", "serve"]
