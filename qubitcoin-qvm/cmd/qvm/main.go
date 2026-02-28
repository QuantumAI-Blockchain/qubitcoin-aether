// Package main implements the QVM server binary.
//
// The QVM (Quantum Virtual Machine) is the production-grade EVM-compatible
// bytecode interpreter for the Qubitcoin blockchain. It extends standard
// EVM execution with quantum opcodes (0xC0-0xDE), AGI opcodes (0xC2-0xC3),
// compliance enforcement, and institutional-grade features.
//
// Usage:
//
//	qvm serve [--http :8080] [--grpc :50052] [--chain-id 3301]
//	qvm version
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"go.uber.org/zap"

	"github.com/BlockArtica/qubitcoin-qvm/pkg/rpc"
)

var (
	version   = "0.1.0"
	buildTime = "unknown"
	gitCommit = "unknown"
)

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "version", "--version", "-v":
			fmt.Printf("qubitcoin-qvm %s (commit %s, built %s)\n", version, gitCommit, buildTime)
			os.Exit(0)
		case "serve":
			serve()
			return
		case "help", "--help", "-h":
			printUsage()
			os.Exit(0)
		}
	}

	// Default: start the server
	serve()
}

func printUsage() {
	fmt.Println("qubitcoin-qvm — Quantum Virtual Machine Server")
	fmt.Println()
	fmt.Println("Usage:")
	fmt.Println("  qvm serve [flags]    Start the QVM server")
	fmt.Println("  qvm version          Print version information")
	fmt.Println("  qvm help             Show this help message")
	fmt.Println()
	fmt.Println("Server flags:")
	fmt.Println("  --http ADDR          HTTP listen address (default :8080, env QVM_HTTP_ADDR)")
	fmt.Println("  --grpc ADDR          gRPC listen address (default :50052, env QVM_GRPC_ADDR)")
	fmt.Println("  --chain-id ID        Chain ID (default 3301, env QVM_CHAIN_ID)")
	fmt.Println()
	fmt.Println("Environment variables:")
	fmt.Println("  QVM_HTTP_ADDR        HTTP listen address")
	fmt.Println("  QVM_GRPC_ADDR        gRPC listen address")
	fmt.Println("  QVM_CHAIN_ID         Chain ID (3301=mainnet, 3302=testnet)")
	fmt.Println("  QVM_CORS_ORIGINS     Comma-separated CORS origins")
	fmt.Println("  QVM_LOG_LEVEL        Log level: debug, info, warn, error")
}

func serve() {
	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("starting qubitcoin-qvm",
		zap.String("version", version),
		zap.String("commit", gitCommit),
	)

	// Build config from env + flags
	config := rpc.DefaultServerConfig()

	if addr := getEnvOrFlag("QVM_HTTP_ADDR", "--http"); addr != "" {
		config.HTTPAddr = addr
	}
	if addr := getEnvOrFlag("QVM_GRPC_ADDR", "--grpc"); addr != "" {
		config.GRPCAddr = addr
	}
	if idStr := getEnvOrFlag("QVM_CHAIN_ID", "--chain-id"); idStr != "" {
		if id, err := strconv.ParseUint(idStr, 10, 64); err == nil {
			config.ChainID = id
		}
	}

	// Block height tracking (updated by consensus engine in production)
	var blockHeight atomic.Uint64

	services := &rpc.ServiceRegistry{
		ChainID:     config.ChainID,
		BlockHeight: func() uint64 { return blockHeight.Load() },
		Version:     version,
	}

	// Create and start server
	server := rpc.NewServer(config, services, logger)
	if err := server.Start(); err != nil {
		logger.Fatal("failed to start server", zap.Error(err))
	}

	logger.Info("QVM server is ready",
		zap.String("http", config.HTTPAddr),
		zap.String("grpc", config.GRPCAddr),
		zap.Uint64("chain_id", config.ChainID),
	)

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh

	logger.Info("received shutdown signal", zap.String("signal", sig.String()))

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := server.Stop(ctx); err != nil {
		logger.Error("error during shutdown", zap.Error(err))
		os.Exit(1)
	}

	logger.Info("QVM server stopped cleanly")
}

// getEnvOrFlag returns the env var value, or searches os.Args for --flag value.
func getEnvOrFlag(envKey, flagName string) string {
	if v := os.Getenv(envKey); v != "" {
		return v
	}
	for i, arg := range os.Args {
		if arg == flagName && i+1 < len(os.Args) {
			return os.Args[i+1]
		}
	}
	return ""
}
