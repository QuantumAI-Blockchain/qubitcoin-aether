// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC20.sol";
import "../proxy/Initializable.sol";

/// @title QBC20 — Reference Implementation of QBC-20 Fungible Token Standard
/// @notice ERC-20 compatible token standard for the Qubitcoin QVM.
///         Use this as a base for deploying fungible tokens on QBC chain.
contract QBC20 is IQBC20, Initializable {
    string  public name;
    string  public symbol;
    uint8   public decimals;
    uint256 public totalSupply;
    address public owner;

    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    event OwnershipTransferred(address indexed prev, address indexed next);

    modifier onlyOwner() {
        require(msg.sender == owner, "QBC20: not owner");
        _;
    }

    function initialize(
        string memory _name,
        string memory _symbol,
        uint8  _decimals,
        uint256 initialSupply
    ) external initializer {
        name     = _name;
        symbol   = _symbol;
        decimals = _decimals;
        owner    = msg.sender;

        if (initialSupply > 0) {
            _balances[msg.sender] = initialSupply;
            totalSupply = initialSupply;
            emit Transfer(address(0), msg.sender, initialSupply);
        }
    }

    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    function allowance(address _owner, address spender) external view returns (uint256) {
        return _allowances[_owner][spender];
    }

    /// @notice Approve `spender` to spend `amount` tokens on behalf of msg.sender.
    /// @dev Front-running mitigation: to change an existing non-zero allowance to
    ///      another non-zero value, you MUST first set it to 0 (or use the safe
    ///      increaseAllowance/decreaseAllowance methods). This prevents the classic
    ///      ERC-20 approve front-running vulnerability where a spender could spend
    ///      both the old and new allowance by observing the approve tx in the mempool.
    function approve(address spender, uint256 amount) external returns (bool) {
        require(
            amount == 0 || _allowances[msg.sender][spender] == 0,
            "QBC20: approve from non-zero to non-zero, set to 0 first"
        );
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    /// @notice Atomically increase the allowance granted to `spender`.
    ///         Safer alternative to approve() — immune to front-running.
    function increaseAllowance(address spender, uint256 addedValue) external returns (bool) {
        _allowances[msg.sender][spender] += addedValue;
        emit Approval(msg.sender, spender, _allowances[msg.sender][spender]);
        return true;
    }

    /// @notice Atomically decrease the allowance granted to `spender`.
    ///         Safer alternative to approve() — immune to front-running.
    function decreaseAllowance(address spender, uint256 subtractedValue) external returns (bool) {
        uint256 currentAllowance = _allowances[msg.sender][spender];
        require(currentAllowance >= subtractedValue, "QBC20: decreased allowance below zero");
        _allowances[msg.sender][spender] = currentAllowance - subtractedValue;
        emit Approval(msg.sender, spender, _allowances[msg.sender][spender]);
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(to != address(0), "QBC20: to zero");
        require(_balances[msg.sender] >= amount, "QBC20: insufficient");
        _balances[msg.sender] -= amount;
        _balances[to]         += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(to != address(0), "QBC20: to zero");
        require(_balances[from] >= amount, "QBC20: insufficient");
        require(_allowances[from][msg.sender] >= amount, "QBC20: allowance");
        _allowances[from][msg.sender] -= amount;
        _balances[from]               -= amount;
        _balances[to]                 += amount;
        emit Transfer(from, to, amount);
        return true;
    }

    function mint(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "QBC20: to zero");
        totalSupply       += amount;
        _balances[to]     += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(uint256 amount) external {
        require(_balances[msg.sender] >= amount, "QBC20: insufficient");
        _balances[msg.sender] -= amount;
        totalSupply           -= amount;
        emit Transfer(msg.sender, address(0), amount);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "QBC20: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
