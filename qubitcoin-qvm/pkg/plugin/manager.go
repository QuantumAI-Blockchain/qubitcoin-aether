// Package plugin implements the QVM plugin architecture.
//
// Plugins extend QVM functionality without modifying core protocol code.
// Each plugin registers opcodes, hooks, and services that the QVM can invoke
// during contract execution.
//
// Built-in plugin types:
//   - Privacy Plugin:    SUSY swaps, transaction mixer, ZK proof generation
//   - Oracle Plugin:     Quantum oracle, price feeds, data aggregation
//   - Governance Plugin: DAO implementation, voting, proposal management
//   - DeFi Plugin:       Lending protocol, DEX, staking system
//
// Plugins are loaded dynamically and managed via the PluginManager.
package plugin

import (
	"fmt"
	"sync"
)

// Plugin is the interface that all QVM plugins must implement.
type Plugin interface {
	// Name returns the unique plugin identifier.
	Name() string
	// Version returns the plugin version string.
	Version() string
	// Description returns a human-readable description.
	Description() string
	// Initialize is called when the plugin is loaded.
	Initialize(config map[string]string) error
	// Shutdown is called when the plugin is unloaded.
	Shutdown() error
	// Capabilities returns the set of features this plugin provides.
	Capabilities() []Capability
}

// Capability describes a single feature provided by a plugin.
type Capability struct {
	Name        string
	Type        CapabilityType
	Description string
}

// CapabilityType categorizes plugin capabilities.
type CapabilityType uint8

const (
	CapOpcodeHandler  CapabilityType = iota // Handles custom opcodes
	CapPrecompile                           // Provides precompiled contracts
	CapHook                                 // Hooks into execution lifecycle
	CapService                              // Background service
	CapStorageBackend                       // Custom storage provider
)

// PluginStatus tracks the lifecycle state of a plugin.
type PluginStatus uint8

const (
	StatusUnloaded PluginStatus = iota
	StatusLoaded
	StatusInitialized
	StatusRunning
	StatusStopped
	StatusError
)

// PluginInfo holds metadata about a registered plugin.
type PluginInfo struct {
	Name         string
	Version      string
	Description  string
	Status       PluginStatus
	Capabilities []Capability
	Config       map[string]string
}

// Manager manages the lifecycle of QVM plugins.
// It provides registration, initialization, lookup, and shutdown.
type Manager struct {
	mu      sync.RWMutex
	plugins map[string]*pluginEntry
	order   []string // load order for deterministic shutdown
}

type pluginEntry struct {
	plugin Plugin
	info   *PluginInfo
}

// NewManager creates a new plugin manager.
func NewManager() *Manager {
	return &Manager{
		plugins: make(map[string]*pluginEntry),
	}
}

// Register adds a plugin to the manager. Does not initialize it.
func (m *Manager) Register(p Plugin) error {
	if p == nil {
		return fmt.Errorf("nil plugin")
	}

	name := p.Name()
	if name == "" {
		return fmt.Errorf("plugin has empty name")
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	if _, exists := m.plugins[name]; exists {
		return fmt.Errorf("plugin %q already registered", name)
	}

	entry := &pluginEntry{
		plugin: p,
		info: &PluginInfo{
			Name:         name,
			Version:      p.Version(),
			Description:  p.Description(),
			Status:       StatusLoaded,
			Capabilities: p.Capabilities(),
		},
	}

	m.plugins[name] = entry
	m.order = append(m.order, name)
	return nil
}

// Initialize initializes a plugin by name with the given configuration.
func (m *Manager) Initialize(name string, config map[string]string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	entry, ok := m.plugins[name]
	if !ok {
		return fmt.Errorf("plugin %q not found", name)
	}
	if entry.info.Status == StatusRunning {
		return fmt.Errorf("plugin %q already running", name)
	}

	if err := entry.plugin.Initialize(config); err != nil {
		entry.info.Status = StatusError
		return fmt.Errorf("failed to initialize plugin %q: %w", name, err)
	}

	entry.info.Status = StatusRunning
	entry.info.Config = config
	return nil
}

// InitializeAll initializes all registered plugins with their configs.
func (m *Manager) InitializeAll(configs map[string]map[string]string) error {
	m.mu.RLock()
	order := make([]string, len(m.order))
	copy(order, m.order)
	m.mu.RUnlock()

	for _, name := range order {
		config := configs[name]
		if config == nil {
			config = make(map[string]string)
		}
		if err := m.Initialize(name, config); err != nil {
			return err
		}
	}
	return nil
}

// Get returns a plugin by name.
func (m *Manager) Get(name string) (Plugin, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	entry, ok := m.plugins[name]
	if !ok {
		return nil, fmt.Errorf("plugin %q not found", name)
	}
	return entry.plugin, nil
}

// GetInfo returns metadata about a plugin.
func (m *Manager) GetInfo(name string) (*PluginInfo, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	entry, ok := m.plugins[name]
	if !ok {
		return nil, fmt.Errorf("plugin %q not found", name)
	}
	return entry.info, nil
}

// List returns info about all registered plugins.
func (m *Manager) List() []*PluginInfo {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make([]*PluginInfo, 0, len(m.plugins))
	for _, name := range m.order {
		if entry, ok := m.plugins[name]; ok {
			result = append(result, entry.info)
		}
	}
	return result
}

// Shutdown stops a plugin by name.
func (m *Manager) Shutdown(name string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	entry, ok := m.plugins[name]
	if !ok {
		return fmt.Errorf("plugin %q not found", name)
	}
	if entry.info.Status != StatusRunning {
		return nil
	}

	if err := entry.plugin.Shutdown(); err != nil {
		entry.info.Status = StatusError
		return fmt.Errorf("failed to shutdown plugin %q: %w", name, err)
	}

	entry.info.Status = StatusStopped
	return nil
}

// ShutdownAll stops all running plugins in reverse registration order.
func (m *Manager) ShutdownAll() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	var firstErr error
	for i := len(m.order) - 1; i >= 0; i-- {
		name := m.order[i]
		entry, ok := m.plugins[name]
		if !ok || entry.info.Status != StatusRunning {
			continue
		}
		if err := entry.plugin.Shutdown(); err != nil {
			entry.info.Status = StatusError
			if firstErr == nil {
				firstErr = fmt.Errorf("failed to shutdown plugin %q: %w", name, err)
			}
		} else {
			entry.info.Status = StatusStopped
		}
	}
	return firstErr
}

// Unregister removes a plugin (must be stopped first).
func (m *Manager) Unregister(name string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	entry, ok := m.plugins[name]
	if !ok {
		return fmt.Errorf("plugin %q not found", name)
	}
	if entry.info.Status == StatusRunning {
		return fmt.Errorf("plugin %q is still running; shutdown first", name)
	}

	delete(m.plugins, name)
	for i, n := range m.order {
		if n == name {
			m.order = append(m.order[:i], m.order[i+1:]...)
			break
		}
	}
	return nil
}

// FindByCapability returns all plugins that provide a given capability type.
func (m *Manager) FindByCapability(capType CapabilityType) []Plugin {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var result []Plugin
	for _, entry := range m.plugins {
		for _, cap := range entry.info.Capabilities {
			if cap.Type == capType {
				result = append(result, entry.plugin)
				break
			}
		}
	}
	return result
}

// Count returns the number of registered plugins.
func (m *Manager) Count() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.plugins)
}

// RunningCount returns the number of running plugins.
func (m *Manager) RunningCount() int {
	m.mu.RLock()
	defer m.mu.RUnlock()

	count := 0
	for _, entry := range m.plugins {
		if entry.info.Status == StatusRunning {
			count++
		}
	}
	return count
}
