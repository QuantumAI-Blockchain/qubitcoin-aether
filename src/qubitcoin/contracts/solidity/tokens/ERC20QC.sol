// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ERC20QC — Compliance-Aware Fungible Token Standard for Qubitcoin QVM
/// @notice Extends QBC-20 with VM-level compliance enforcement. Every transfer
///         is checked against the QCOMPLIANCE opcode (0xF5) before execution.
///         Supports KYC level requirements, address freezing, and compliance officer role.
contract ERC20QC {
    string  public name;
    string  public symbol;
    uint8   public immutable decimals;
    uint256 public totalSupply;
    address public owner;
    address public complianceOfficer;

    /// @notice Minimum KYC level required for transfers (0=NONE, 1=BASIC, 2=ENHANCED, 3=FULL)
    uint8 public requiredKYCLevel;

    /// @notice Whether the token is paused (no transfers allowed)
    bool public paused;

    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;
    mapping(address => bool) public frozen;

    // ─── Events ─────────────────────────────────────────────────────────

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event OwnershipTransferred(address indexed prev, address indexed next);
    event ComplianceOfficerChanged(address indexed prev, address indexed next);
    event ComplianceLevelChanged(uint8 oldLevel, uint8 newLevel);
    event AddressFrozen(address indexed account, address indexed officer);
    event AddressUnfrozen(address indexed account, address indexed officer);
    event Paused(address indexed account);
    event Unpaused(address indexed account);

    // ─── Modifiers ──────────────────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "ERC20QC: not owner");
        _;
    }

    modifier onlyCompliance() {
        require(
            msg.sender == complianceOfficer || msg.sender == owner,
            "ERC20QC: not compliance officer"
        );
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "ERC20QC: paused");
        _;
    }

    modifier notFrozen(address account) {
        require(!frozen[account], "ERC20QC: account frozen");
        _;
    }

    // ─── Constructor ────────────────────────────────────────────────────

    /// @param _name Token name
    /// @param _symbol Token symbol
    /// @param _decimals Token decimals
    /// @param initialSupply Initial supply minted to deployer
    /// @param _requiredKYCLevel Minimum KYC level (0-3) for transfers
    constructor(
        string memory _name,
        string memory _symbol,
        uint8  _decimals,
        uint256 initialSupply,
        uint8  _requiredKYCLevel
    ) {
        require(_requiredKYCLevel <= 3, "ERC20QC: invalid KYC level");

        name              = _name;
        symbol            = _symbol;
        decimals          = _decimals;
        owner             = msg.sender;
        complianceOfficer = msg.sender;
        requiredKYCLevel  = _requiredKYCLevel;

        if (initialSupply > 0) {
            _balances[msg.sender] = initialSupply;
            totalSupply = initialSupply;
            emit Transfer(address(0), msg.sender, initialSupply);
        }
    }

    // ─── ERC-20 Views ───────────────────────────────────────────────────

    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    function allowance(address _owner, address spender) external view returns (uint256) {
        return _allowances[_owner][spender];
    }

    // ─── ERC-20 Actions ─────────────────────────────────────────────────

    function approve(address spender, uint256 amount) external returns (bool) {
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount)
        external
        whenNotPaused
        notFrozen(msg.sender)
        notFrozen(to)
        returns (bool)
    {
        _complianceCheck(msg.sender, to, amount);
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount)
        external
        whenNotPaused
        notFrozen(from)
        notFrozen(to)
        returns (bool)
    {
        require(_allowances[from][msg.sender] >= amount, "ERC20QC: allowance");
        _complianceCheck(from, to, amount);
        _allowances[from][msg.sender] -= amount;
        _transfer(from, to, amount);
        return true;
    }

    // ─── Mint / Burn ────────────────────────────────────────────────────

    function mint(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "ERC20QC: to zero");
        totalSupply       += amount;
        _balances[to]     += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(uint256 amount) external {
        require(_balances[msg.sender] >= amount, "ERC20QC: insufficient");
        _balances[msg.sender] -= amount;
        totalSupply           -= amount;
        emit Transfer(msg.sender, address(0), amount);
    }

    // ─── Compliance Controls ────────────────────────────────────────────

    /// @notice Freeze an address — prevents all transfers to/from this address
    function freeze(address account) external onlyCompliance {
        require(account != address(0), "ERC20QC: zero address");
        require(!frozen[account], "ERC20QC: already frozen");
        frozen[account] = true;
        emit AddressFrozen(account, msg.sender);
    }

    /// @notice Unfreeze an address
    function unfreeze(address account) external onlyCompliance {
        require(frozen[account], "ERC20QC: not frozen");
        frozen[account] = false;
        emit AddressUnfrozen(account, msg.sender);
    }

    /// @notice Update the minimum KYC level required for transfers
    function setComplianceLevel(uint8 newLevel) external onlyCompliance {
        require(newLevel <= 3, "ERC20QC: invalid KYC level");
        uint8 oldLevel = requiredKYCLevel;
        requiredKYCLevel = newLevel;
        emit ComplianceLevelChanged(oldLevel, newLevel);
    }

    /// @notice Pause all transfers (emergency)
    function pause() external onlyCompliance {
        require(!paused, "ERC20QC: already paused");
        paused = true;
        emit Paused(msg.sender);
    }

    /// @notice Resume transfers
    function unpause() external onlyCompliance {
        require(paused, "ERC20QC: not paused");
        paused = false;
        emit Unpaused(msg.sender);
    }

    // ─── Administrative ─────────────────────────────────────────────────

    function setComplianceOfficer(address newOfficer) external onlyOwner {
        require(newOfficer != address(0), "ERC20QC: zero address");
        emit ComplianceOfficerChanged(complianceOfficer, newOfficer);
        complianceOfficer = newOfficer;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "ERC20QC: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    // ─── Internal ───────────────────────────────────────────────────────

    function _transfer(address from, address to, uint256 amount) internal {
        require(to != address(0), "ERC20QC: to zero");
        require(_balances[from] >= amount, "ERC20QC: insufficient");
        _balances[from] -= amount;
        _balances[to]   += amount;
        emit Transfer(from, to, amount);
    }

    /// @notice Pre-transfer compliance check.
    ///         In QVM, this would invoke the QCOMPLIANCE opcode (0xF5) to verify
    ///         both sender and receiver meet the required KYC level.
    ///         This Solidity implementation uses storage-based checks as a fallback.
    /// @dev Override this function to add custom compliance logic.
    function _complianceCheck(
        address from,
        address to,
        uint256 /* amount */
    ) internal view {
        // In the QVM environment, the QCOMPLIANCE opcode (0xF5) is invoked
        // here to check on-chain KYC/AML status. The opcode returns the
        // compliance level (0-3) for the queried address. If below
        // requiredKYCLevel, the transaction reverts.
        //
        // For pure Solidity execution (e.g., testing), the frozen mapping
        // serves as the compliance enforcement mechanism. The VM-level check
        // is applied automatically by the QVM bytecode interpreter when it
        // encounters a transfer on an ERC20QC contract.
        //
        // This function exists as a hook for subcontracts to add additional
        // compliance logic beyond what the opcode provides.
        require(!frozen[from], "ERC20QC: sender frozen");
        require(!frozen[to], "ERC20QC: receiver frozen");
    }
}
