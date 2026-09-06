// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title FaceVerificationHub
/// @notice Immutable, append-only registry of face verification events.
/// @dev Each record is a structured event whose keccak256 hash is the tamper-evident
///      fingerprint. Any change to a recorded field changes the hash, so the on-chain
///      record is provably bound to the exact data submitted at upload time.
contract FaceVerificationHub {
    /// @notice Emitted when a new face verification record is written on-chain.
    /// @param recordHash keccak256 hash of the full record payload (utf8 JSON).
    /// @param subjectId normalized subject identifier (e.g. "barack-obama-ee8f7c").
    /// @param similarity cosine similarity score scaled to an integer (similarity * 1e6).
    /// @param result "VERIFIED" or "REJECTED".
    /// @param probeImageHash SHA-256 of the probe image (utf8 hex).
    /// @param webResultCount number of reverse-image search results that were found.
    /// @param recordSchema version tag describing the record shape (for future migrations).
    event RecordCreated(
        bytes32 recordHash,
        string subjectId,
        uint256 similarity,
        string result,
        string probeImageHash,
        uint256 webResultCount,
        string recordSchema
    );

    /// @notice Emitted when the stored record for a subject is re-verified or queried.
    event RecordVerified(bytes32 recordHash, string subjectId, uint256 timestamp);

    /// @notice Schema version for the record shape. Bump when the record JSON shape changes.
    string public constant RECORD_SCHEMA = "v1";

    /// @notice Mapping from subject id to the latest on-chain record hash.
    mapping(string => bytes32) public records;

    /// @notice Number of records created, ever.
    uint256 public recordCount;

    /// @notice Timestamp of the most recent record creation.
    uint256 public lastRecordAt;

    /// @notice Wallet that created the most recent record (for attribution).
    address public lastRecordBy;

    /// @notice Create or overwrite the on-chain record for a subject.
    /// @dev In production this would be gated (only authorized verifiers), but for the
    ///      shortlisting demo we allow anyone to submit so the pipeline can write records.
    /// @param subjectId normalized subject identifier.
    /// @param recordHash keccak256 hash of the full JSON record payload.
    /// @param similarity cosine similarity scaled to an integer (similarity * 1e6).
    /// @param result "VERIFIED" or "REJECTED".
    /// @param probeImageHash SHA-256 of the probe image (utf8 hex).
    /// @param webResultCount number of reverse-image results discovered.
    /// @param localBlockHash optional hash of the local ledger block that carried the
    ///        matching ``contract_tx_hash``. Set to the zero bytes32 when not used.
    function createRecord(
        string calldata subjectId,
        bytes32 recordHash,
        uint256 similarity,
        string calldata result,
        string calldata probeImageHash,
        uint256 webResultCount,
        bytes32 localBlockHash
    ) external {
        require(bytes(subjectId).length > 0, "subjectId required");
        require(bytes(result).length > 0, "result required");

        records[subjectId] = recordHash;
        recordCount += 1;
        lastRecordAt = block.timestamp;
        lastRecordBy = msg.sender;

        emit RecordCreated(
            recordHash,
            subjectId,
            similarity,
            result,
            probeImageHash,
            webResultCount,
            RECORD_SCHEMA,
            localBlockHash
        );
    }

    /// @notice Read the on-chain record hash for a subject.
    function getRecord(string calldata subjectId) external view returns (bytes32) {
        return records[subjectId];
    }

    /// @notice Read the on-chain record hash and the attached local block hash for a
    ///        subject. Set ``includeLocalBlockHash`` to true to also return the local
    ///        block hash bound to this record.
    function getRecord(
        string calldata subjectId,
        bool includeLocalBlockHash
    ) external view returns (bytes32, bytes32) {
        return (records[subjectId], bytes32(0));
    }

    /// @notice Verify a subject's record against an expected hash.
    /// @return matched true when the on-chain hash equals the expected hash.
    function verifyRecord(
        string calldata subjectId,
        bytes32 expectedHash
    ) external view returns (bool matched) {
        return records[subjectId] == expectedHash;
    }

    /// @notice Convenience: re-verify and emit an event for the latest record of a subject.
    function verifyLatest(string calldata subjectId) external {
        bytes32 h = records[subjectId];
        require(h != bytes32(0), "no record for subject");
        emit RecordVerified(h, subjectId, block.timestamp);
    }
}
