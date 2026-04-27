#!/usr/bin/env bash
set -euo pipefail

REPO="QuantumAI-Blockchain/aether-cli"
INSTALL_DIR="/usr/local/bin"
BINARY_NAME="aether"

main() {
    local os arch artifact

    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Linux)  os="linux" ;;
        Darwin) os="macos" ;;
        *)      echo "Unsupported OS: $os" >&2; exit 1 ;;
    esac

    case "$arch" in
        x86_64|amd64)   arch="x86_64" ;;
        aarch64|arm64)  arch="aarch64" ;;
        *)              echo "Unsupported architecture: $arch" >&2; exit 1 ;;
    esac

    artifact="aether-${os}-${arch}"

    echo "Aether CLI installer"
    echo "  OS:   $os"
    echo "  Arch: $arch"
    echo ""

    # Get latest release tag
    local tag
    tag="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | grep '"tag_name"' | head -1 | cut -d'"' -f4)"

    if [ -z "$tag" ]; then
        echo "Error: could not find latest release" >&2
        exit 1
    fi

    echo "Latest release: $tag"

    local url="https://github.com/${REPO}/releases/download/${tag}/${artifact}"
    local tmp
    tmp="$(mktemp)"

    echo "Downloading ${url}..."
    curl -fsSL -o "$tmp" "$url"
    chmod +x "$tmp"

    # Install — try sudo if needed
    if [ -w "$INSTALL_DIR" ]; then
        mv "$tmp" "${INSTALL_DIR}/${BINARY_NAME}"
    else
        echo "Installing to ${INSTALL_DIR} (requires sudo)..."
        sudo mv "$tmp" "${INSTALL_DIR}/${BINARY_NAME}"
    fi

    echo ""
    echo "Installed: ${INSTALL_DIR}/${BINARY_NAME}"
    echo ""
    "${INSTALL_DIR}/${BINARY_NAME}" --version
    echo ""
    echo "Run 'aether' to start chatting with Aether Mind."
}

main
