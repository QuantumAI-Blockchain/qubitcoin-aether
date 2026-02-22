// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title QBC1155 — Reference Implementation of QBC-1155 Multi-Token Standard
/// @notice ERC-1155 compatible multi-token standard for the Qubitcoin QVM.
///         Supports both fungible and non-fungible tokens in a single contract.
contract QBC1155 is Initializable {
    string public uri;
    address public owner;

    // tokenId => account => balance
    mapping(uint256 => mapping(address => uint256)) private _balances;
    // account => operator => approved
    mapping(address => mapping(address => bool)) private _operatorApprovals;
    // tokenId => total supply
    mapping(uint256 => uint256) private _totalSupply;
    // tokenId => custom URI (overrides base URI if set)
    mapping(uint256 => string) private _tokenURIs;

    event TransferSingle(
        address indexed operator,
        address indexed from,
        address indexed to,
        uint256 id,
        uint256 value
    );

    event TransferBatch(
        address indexed operator,
        address indexed from,
        address indexed to,
        uint256[] ids,
        uint256[] values
    );

    event ApprovalForAll(
        address indexed account,
        address indexed operator,
        bool approved
    );

    event URI(string value, uint256 indexed id);

    event OwnershipTransferred(address indexed prev, address indexed next);

    modifier onlyOwner() {
        require(msg.sender == owner, "QBC1155: not owner");
        _;
    }

    function initialize(string memory _uri) external initializer {
        uri = _uri;
        owner = msg.sender;
    }

    // ─── Queries ────────────────────────────────────────────────────────

    function balanceOf(address account, uint256 id) public view returns (uint256) {
        require(account != address(0), "QBC1155: zero address");
        return _balances[id][account];
    }

    function balanceOfBatch(
        address[] calldata accounts,
        uint256[] calldata ids
    ) external view returns (uint256[] memory) {
        require(accounts.length == ids.length, "QBC1155: length mismatch");
        uint256[] memory batchBalances = new uint256[](accounts.length);
        for (uint256 i = 0; i < accounts.length; i++) {
            batchBalances[i] = balanceOf(accounts[i], ids[i]);
        }
        return batchBalances;
    }

    function totalSupply(uint256 id) external view returns (uint256) {
        return _totalSupply[id];
    }

    function exists(uint256 id) external view returns (bool) {
        return _totalSupply[id] > 0;
    }

    function tokenURI(uint256 id) external view returns (string memory) {
        bytes memory customURI = bytes(_tokenURIs[id]);
        if (customURI.length > 0) {
            return _tokenURIs[id];
        }
        return uri;
    }

    // ─── Approvals ──────────────────────────────────────────────────────

    function setApprovalForAll(address operator, bool approved) external {
        require(operator != msg.sender, "QBC1155: self approval");
        _operatorApprovals[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function isApprovedForAll(address account, address operator) public view returns (bool) {
        return _operatorApprovals[account][operator];
    }

    // ─── Transfers ──────────────────────────────────────────────────────

    function safeTransferFrom(
        address from,
        address to,
        uint256 id,
        uint256 amount,
        bytes calldata /* data */
    ) external {
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "QBC1155: not authorized"
        );
        require(to != address(0), "QBC1155: to zero");
        require(_balances[id][from] >= amount, "QBC1155: insufficient");

        _balances[id][from] -= amount;
        _balances[id][to]   += amount;

        emit TransferSingle(msg.sender, from, to, id, amount);
    }

    function safeBatchTransferFrom(
        address from,
        address to,
        uint256[] calldata ids,
        uint256[] calldata amounts,
        bytes calldata /* data */
    ) external {
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "QBC1155: not authorized"
        );
        require(to != address(0), "QBC1155: to zero");
        require(ids.length == amounts.length, "QBC1155: length mismatch");

        for (uint256 i = 0; i < ids.length; i++) {
            require(_balances[ids[i]][from] >= amounts[i], "QBC1155: insufficient");
            _balances[ids[i]][from] -= amounts[i];
            _balances[ids[i]][to]   += amounts[i];
        }

        emit TransferBatch(msg.sender, from, to, ids, amounts);
    }

    // ─── Minting ────────────────────────────────────────────────────────

    function mint(
        address to,
        uint256 id,
        uint256 amount,
        bytes calldata /* data */
    ) external onlyOwner {
        require(to != address(0), "QBC1155: to zero");
        _balances[id][to] += amount;
        _totalSupply[id]  += amount;
        emit TransferSingle(msg.sender, address(0), to, id, amount);
    }

    function mintBatch(
        address to,
        uint256[] calldata ids,
        uint256[] calldata amounts,
        bytes calldata /* data */
    ) external onlyOwner {
        require(to != address(0), "QBC1155: to zero");
        require(ids.length == amounts.length, "QBC1155: length mismatch");

        for (uint256 i = 0; i < ids.length; i++) {
            _balances[ids[i]][to] += amounts[i];
            _totalSupply[ids[i]]  += amounts[i];
        }

        emit TransferBatch(msg.sender, address(0), to, ids, amounts);
    }

    // ─── Burning ────────────────────────────────────────────────────────

    function burn(address from, uint256 id, uint256 amount) external {
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "QBC1155: not authorized"
        );
        require(_balances[id][from] >= amount, "QBC1155: insufficient");

        _balances[id][from] -= amount;
        _totalSupply[id]    -= amount;
        emit TransferSingle(msg.sender, from, address(0), id, amount);
    }

    function burnBatch(
        address from,
        uint256[] calldata ids,
        uint256[] calldata amounts
    ) external {
        require(
            from == msg.sender || isApprovedForAll(from, msg.sender),
            "QBC1155: not authorized"
        );
        require(ids.length == amounts.length, "QBC1155: length mismatch");

        for (uint256 i = 0; i < ids.length; i++) {
            require(_balances[ids[i]][from] >= amounts[i], "QBC1155: insufficient");
            _balances[ids[i]][from] -= amounts[i];
            _totalSupply[ids[i]]    -= amounts[i];
        }

        emit TransferBatch(msg.sender, from, address(0), ids, amounts);
    }

    // ─── Metadata ───────────────────────────────────────────────────────

    function setURI(string calldata newURI) external onlyOwner {
        uri = newURI;
    }

    function setTokenURI(uint256 id, string calldata tokenUri) external onlyOwner {
        _tokenURIs[id] = tokenUri;
        emit URI(tokenUri, id);
    }

    // ─── Ownership ──────────────────────────────────────────────────────

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "QBC1155: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
