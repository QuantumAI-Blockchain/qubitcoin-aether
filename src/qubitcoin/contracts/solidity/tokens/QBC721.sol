// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC721.sol";

/// @title QBC721 — Reference Implementation of QBC-721 Non-Fungible Token Standard
/// @notice ERC-721 compatible NFT standard for the Qubitcoin QVM.
///         Use this as a base for deploying NFTs on QBC chain.
contract QBC721 is IQBC721 {
    string public name;
    string public symbol;
    address public owner;

    uint256 private _tokenIdCounter;

    mapping(uint256 => address)                  private _owners;
    mapping(address => uint256)                  private _balances;
    mapping(uint256 => address)                  private _tokenApprovals;
    mapping(address => mapping(address => bool)) private _operatorApprovals;
    mapping(uint256 => string)                   private _tokenURIs;

    event OwnershipTransferred(address indexed prev, address indexed next);

    modifier onlyOwner() {
        require(msg.sender == owner, "QBC721: not owner");
        _;
    }

    constructor(string memory _name, string memory _symbol) {
        name   = _name;
        symbol = _symbol;
        owner  = msg.sender;
    }

    function balanceOf(address tokenOwner) external view returns (uint256) {
        require(tokenOwner != address(0), "QBC721: zero address");
        return _balances[tokenOwner];
    }

    function ownerOf(uint256 tokenId) external view returns (address) {
        address tokenOwner = _owners[tokenId];
        require(tokenOwner != address(0), "QBC721: nonexistent");
        return tokenOwner;
    }

    function approve(address to, uint256 tokenId) external {
        address tokenOwner = _owners[tokenId];
        require(msg.sender == tokenOwner || _operatorApprovals[tokenOwner][msg.sender], "QBC721: not authorized");
        _tokenApprovals[tokenId] = to;
        emit Approval(tokenOwner, to, tokenId);
    }

    function getApproved(uint256 tokenId) external view returns (address) {
        require(_owners[tokenId] != address(0), "QBC721: nonexistent");
        return _tokenApprovals[tokenId];
    }

    function setApprovalForAll(address operator, bool approved) external {
        _operatorApprovals[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function isApprovedForAll(address tokenOwner, address operator) external view returns (bool) {
        return _operatorApprovals[tokenOwner][operator];
    }

    function transferFrom(address from, address to, uint256 tokenId) public {
        require(_isApprovedOrOwner(msg.sender, tokenId), "QBC721: not authorized");
        require(to != address(0), "QBC721: to zero");
        _transfer(from, to, tokenId);
    }

    function safeTransferFrom(address from, address to, uint256 tokenId) external {
        transferFrom(from, to, tokenId);
    }

    function safeTransferFrom(address from, address to, uint256 tokenId, bytes calldata) external {
        transferFrom(from, to, tokenId);
    }

    // ─── Minting ─────────────────────────────────────────────────────────
    function mint(address to, string calldata tokenURI) external onlyOwner returns (uint256 tokenId) {
        require(to != address(0), "QBC721: to zero");
        tokenId = ++_tokenIdCounter;
        _owners[tokenId] = to;
        _balances[to]++;
        _tokenURIs[tokenId] = tokenURI;
        emit Transfer(address(0), to, tokenId);
    }

    function burn(uint256 tokenId) external {
        require(_isApprovedOrOwner(msg.sender, tokenId), "QBC721: not authorized");
        address tokenOwner = _owners[tokenId];
        delete _tokenApprovals[tokenId];
        _balances[tokenOwner]--;
        delete _owners[tokenId];
        delete _tokenURIs[tokenId];
        emit Transfer(tokenOwner, address(0), tokenId);
    }

    function tokenURI(uint256 tokenId) external view returns (string memory) {
        require(_owners[tokenId] != address(0), "QBC721: nonexistent");
        return _tokenURIs[tokenId];
    }

    function totalSupply() external view returns (uint256) {
        return _tokenIdCounter;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _transfer(address from, address to, uint256 tokenId) internal {
        require(_owners[tokenId] == from, "QBC721: wrong owner");
        delete _tokenApprovals[tokenId];
        _balances[from]--;
        _balances[to]++;
        _owners[tokenId] = to;
        emit Transfer(from, to, tokenId);
    }

    function _isApprovedOrOwner(address spender, uint256 tokenId) internal view returns (bool) {
        address tokenOwner = _owners[tokenId];
        return (spender == tokenOwner ||
                _tokenApprovals[tokenId] == spender ||
                _operatorApprovals[tokenOwner][spender]);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
